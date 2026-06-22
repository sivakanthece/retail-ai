from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, DetectionEvent, Inventory, Product, Alert, ProductReference
from security import get_current_user, User
from config import settings
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont
import io
import json
import base64
import os
import re
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/detection", tags=["detection"])

# ── In-memory image cache keyed by event_id ──────────────────────
# Stores the uploaded PIL image so we can crop it for identification
_image_cache: dict[int, Image.Image] = {}

# ── Lazy-load YOLO ───────────────────────────────────────────────
_model = None

def _ensure_model_file():
    """
    If the configured model file doesn't exist on disk, try to download it
    from Hugging Face Model Hub using the HF_TOKEN runtime env var.
    Falls back to yolov8n.pt (auto-downloaded by ultralytics) if unavailable.
    """
    import os
    model_name = settings.YOLO_MODEL
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(backend_dir, model_name)

    if os.path.exists(model_path):
        return model_name  # already on disk

    if model_name == "yolov8n.pt":
        return model_name  # ultralytics downloads this automatically

    # Try to download from HF Model Hub
    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    hf_repo  = os.environ.get("HF_MODEL_REPO", "sivakanthece/retail-ai-yolo")
    if hf_token:
        try:
            from huggingface_hub import hf_hub_download
            logger.info(f"Downloading {model_name} from {hf_repo} ...")
            downloaded = hf_hub_download(
                repo_id=hf_repo,
                filename=model_name,
                token=hf_token,
                local_dir=backend_dir,
            )
            logger.info(f"Downloaded {model_name} to {downloaded}")
            return model_name
        except Exception as e:
            logger.warning(f"HF Model Hub download failed: {e}")

    logger.warning(f"{model_name} not found and could not be downloaded — falling back to yolov8n.pt")
    return "yolov8n.pt"


def get_model():
    global _model
    if _model is None:
        import torch
        resolved = _ensure_model_file()
        _original_torch_load = torch.load
        def _patched_load(f, *args, **kwargs):
            kwargs.setdefault("weights_only", False)
            return _original_torch_load(f, *args, **kwargs)
        torch.load = _patched_load
        try:
            from ultralytics import YOLO
            _model = YOLO(resolved)
            logger.info(f"YOLO model loaded: {resolved}")
        finally:
            torch.load = _original_torch_load
    return _model


# ── Upload & detect ──────────────────────────────────────────────
@router.post("/upload")
async def detect_products(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")
    contents = await file.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large (max {settings.MAX_UPLOAD_SIZE_MB}MB).")

    image = Image.open(io.BytesIO(contents)).convert("RGB")
    model = get_model()
    results = model(image, conf=0.25)

    detections = []
    for r in results:
        for box in r.boxes:
            cls_name = r.names[int(box.cls)]
            conf = float(box.conf)
            x1, y1, x2, y2 = [round(float(v), 2) for v in box.xyxy[0]]
            detections.append({
                "class": cls_name,
                "confidence": round(conf, 3),
                "bbox": [x1, y1, x2, y2],
                "category": _map_to_retail_category(cls_name),
            })

    event = DetectionEvent(
        image_path=file.filename,
        detected_at=datetime.utcnow(),
        total_items_detected=len(detections),
        results_json=json.dumps(detections),
    )
    db.add(event)
    inventory_updates = _update_inventory_from_detections(detections, db)
    db.commit()

    # Cache image for later identification calls
    _image_cache[event.id] = image
    # Keep cache small — evict oldest if > 20 entries
    if len(_image_cache) > 20:
        oldest_key = next(iter(_image_cache))
        del _image_cache[oldest_key]

    return {
        "event_id": event.id,
        "total_detected": len(detections),
        "detections": detections,
        "inventory_updates": inventory_updates,
    }


# ── GPT-4o Vision: identify a single detected product crop ───────
class IdentifyRequest(BaseModel):
    event_id: int
    bbox: list[float]   # [x1, y1, x2, y2]

@router.post("/identify-product")
async def identify_product(
    payload: IdentifyRequest,
    current_user: User = Depends(get_current_user),
):
    """Crop the bounding box from the cached image and ask GPT-4o to identify the product."""
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY not configured.")

    image = _image_cache.get(payload.event_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found. Re-upload the shelf image.")

    # Crop with a small padding
    iw, ih = image.size
    x1, y1, x2, y2 = payload.bbox
    pad = 10
    x1c = max(0, int(x1) - pad)
    y1c = max(0, int(y1) - pad)
    x2c = min(iw, int(x2) + pad)
    y2c = min(ih, int(y2) + pad)

    crop = image.crop((x1c, y1c, x2c, y2c))

    # Resize crop to max 300px for faster API call
    crop.thumbnail((300, 300), Image.LANCZOS)

    buf = io.BytesIO()
    crop.save(buf, format="JPEG", quality=85)
    img_b64 = base64.b64encode(buf.getvalue()).decode()

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    prompt = (
        "This is a cropped image of a single retail product from a store shelf. "
        "Identify it as precisely as possible and return ONLY a JSON object with these fields:\n"
        "- name: full product name including brand (e.g. 'Coca-Cola Classic 330ml Can')\n"
        "- brand: brand name only (e.g. 'Coca-Cola')\n"
        "- category: one of [Beverages, Snacks, Dairy, Bakery, Produce, Frozen, "
        "Canned Goods, Condiments, Cereals, Personal Care, Household, General]\n"
        "- estimated_price: estimated retail price in USD as a number (e.g. 1.99)\n"
        "- sku_suggestion: short alphanumeric SKU suggestion (e.g. 'CC-330-CAN')\n"
        "- low_stock_threshold: suggested reorder point as integer (e.g. 20)\n"
        "If you cannot identify the product clearly, use your best guess based on "
        "shape, color, and packaging. Return ONLY valid JSON, no markdown."
    )

    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                    {"type": "text", "text": prompt},
                ]
            }],
            max_tokens=300,
            temperature=0.2,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        product_info = json.loads(raw)
        return {"status": "ok", "product": product_info}
    except json.JSONDecodeError:
        return {"status": "ok", "product": {
            "name": "", "brand": "", "category": "General",
            "estimated_price": 0.0, "sku_suggestion": "", "low_stock_threshold": 10
        }}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GPT-4o identification failed: {str(e)}")


# ── Vision: identify ALL products in batches of 10 ───────────────
class IdentifyAllRequest(BaseModel):
    event_id: int
    detections: list  # [{bbox, confidence, ...}]

class IdentifyBatchRequest(BaseModel):
    event_id:    int
    detections:  list   # the FULL detections slice for this batch
    batch_start: int    # global offset (so prompt numbers are correct)
    provider:    str = ""  # locked provider from previous batch ("" = auto-probe)

def _parse_json(raw: str) -> list:
    """Robustly extract a JSON array from LLM output regardless of wrapping."""
    raw = raw.strip()
    raw = re.sub(r'```[a-zA-Z]*', '', raw).strip()
    # Fast path
    try:
        r = json.loads(raw)
        return r if isinstance(r, list) else [r]
    except json.JSONDecodeError:
        pass
    # Fix trailing commas then retry
    cleaned = re.sub(r',\s*([\]}])', r'\1', raw)
    try:
        r = json.loads(cleaned)
        return r if isinstance(r, list) else [r]
    except json.JSONDecodeError:
        pass
    # Extract outermost [{ ... }] block (handles preamble/trailing text)
    for pattern in (r'\[\s*\{.*\}\s*\]', r'\[.*\]'):
        m = re.search(pattern, cleaned, re.DOTALL)
        if m:
            try:
                r = json.loads(m.group())
                return r if isinstance(r, list) else [r]
            except json.JSONDecodeError:
                # Truncation recovery: chop after last complete }
                fragment = m.group()
                last = fragment.rfind('}')
                if last != -1:
                    try:
                        r = json.loads(fragment[:last + 1] + ']')
                        return r if isinstance(r, list) else [r]
                    except json.JSONDecodeError:
                        pass
    raise ValueError(f"Cannot parse JSON from: {raw[:200]!r}")


def _build_strip(crops: list[Image.Image], global_start: int) -> str:
    """Build a horizontal strip of up to 5 crops and return as base64 JPEG."""
    CROP_W, CROP_H, LABEL_H, PAD = 160, 160, 20, 4
    n   = len(crops)
    img = Image.new("RGB", (n * (CROP_W + PAD) + PAD, CROP_H + LABEL_H + PAD * 2), (230, 230, 230))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
    except Exception:
        font = ImageFont.load_default()
    for i, crop in enumerate(crops):
        gx = PAD + i * (CROP_W + PAD)
        gy = PAD
        draw.rectangle([gx, gy, gx + CROP_W, gy + LABEL_H], fill=(30, 90, 200))
        draw.text((gx + 4, gy + 2), f"#{global_start + i + 1}", fill=(255, 255, 255), font=font)
        thumb = crop.resize((CROP_W, CROP_H), Image.LANCZOS)
        img.paste(thumb, (gx, gy + LABEL_H))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return base64.b64encode(buf.getvalue()).decode()


def _make_prompt(start: int, n: int) -> str:
    return (
        f"This image shows {n} retail product crops from a store shelf, "
        f"numbered #{start+1} to #{start+n}.\n"
        "Identify EACH product and return ONLY a JSON array — one object per crop:\n"
        f'[{{"index": {start+1}, "name": "Coca-Cola Classic 330ml Can", "brand": "Coca-Cola", '
        '"category": "Beverages", "estimated_price": 1.99, "sku": "CC-330-CAN"}, ...]\n'
        "Categories: Beverages, Snacks, Dairy, Bakery, Produce, Frozen, "
        "Canned Goods, Condiments, Cereals, Personal Care, Household, General.\n"
        "Use best guess from shape/color/packaging for unclear items. "
        "Return ONLY the JSON array, no markdown, no explanation."
    )


LLM_TIMEOUT = 45  # seconds — prevents hanging forever if API is slow


async def _call_openai(img_b64: str, prompt: str) -> list:
    import asyncio
    import httpx
    from openai import AsyncOpenAI
    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        http_client=httpx.AsyncClient(timeout=LLM_TIMEOUT),
    )
    resp = await asyncio.wait_for(
        client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                {"type": "text", "text": prompt},
            ]}],
            max_tokens=1200, temperature=0.1,
        ),
        timeout=LLM_TIMEOUT,
    )
    return _parse_json(resp.choices[0].message.content)


async def _call_gemini(img_b64: str, prompt: str) -> list:
    import asyncio
    from google import genai as google_genai
    from google.genai import types as genai_types
    for model_name in ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-2.5-flash"]:
        try:
            cg   = google_genai.Client(api_key=settings.GOOGLE_API_KEY)
            part = genai_types.Part.from_bytes(data=base64.b64decode(img_b64), mime_type="image/jpeg")
            resp = await asyncio.wait_for(
                asyncio.to_thread(
                    cg.models.generate_content,
                    model=model_name, contents=[part, prompt],
                    config=genai_types.GenerateContentConfig(temperature=0.1, max_output_tokens=1200),
                ),
                timeout=LLM_TIMEOUT,
            )
            return _parse_json(resp.text)
        except Exception as e:
            logger.warning(f"Gemini {model_name} failed: {e}")
    raise RuntimeError("All Gemini models failed")


async def _call_groq(img_b64: str, prompt: str) -> list:
    import asyncio
    from groq import AsyncGroq
    cq   = AsyncGroq(api_key=settings.GROQ_API_KEY)
    resp = await asyncio.wait_for(
        cq.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                {"type": "text", "text": prompt},
            ]}],
            max_tokens=1200, temperature=0.1,
        ),
        timeout=LLM_TIMEOUT,
    )
    return _parse_json(resp.choices[0].message.content)


# Provider registry — tried in order until one works, then locked for the session
_PROVIDERS = [
    ("openai",  lambda: bool(settings.OPENAI_API_KEY),  _call_openai),
    ("gemini",  lambda: bool(settings.GOOGLE_API_KEY),  _call_gemini),
    ("groq",    lambda: bool(settings.GROQ_API_KEY),    _call_groq),
]

_PROVIDER_FN = {name: fn for name, _, fn in _PROVIDERS}


async def _run_batch(image, iw, ih, batch, batch_start, provider_hint=""):
    """Crop, build strip, call LLM. Returns (items, provider_used)."""
    import asyncio
    crops = []
    for d in batch:
        x1, y1, x2, y2 = d["bbox"]
        crops.append(image.crop((max(0,int(x1)), max(0,int(y1)),
                                  min(iw,int(x2)), min(ih,int(y2)))))
    strip_b64 = _build_strip(crops, batch_start)
    prompt    = _make_prompt(batch_start, len(batch))

    # Use locked provider if given
    if provider_hint and provider_hint in _PROVIDER_FN:
        try:
            items = await _PROVIDER_FN[provider_hint](strip_b64, prompt)
            return items, provider_hint
        except Exception as e:
            logger.warning(f"Locked provider {provider_hint} failed: {e} — re-probing")

    # Probe in order, lock on first success
    for name, available, fn in _PROVIDERS:
        if not available():
            logger.info(f"Skipping {name} — API key not configured")
            continue
        try:
            items = await fn(strip_b64, prompt)
            return items, name
        except asyncio.TimeoutError:
            logger.warning(f"{name} timed out after {LLM_TIMEOUT}s — trying next provider")
        except Exception as e:
            logger.warning(f"{name} failed: {e}")

    # Rule-based fallback
    items = []
    for bi, d in enumerate(batch):
        x1, y1, x2, y2 = d["bbox"]
        w, h = x2-x1, y2-y1
        aspect = w / max(h, 1)
        shape, cat = ("Bottle","Beverages") if aspect < 0.55 else \
                     ("Box","Snacks")       if aspect > 1.3  else \
                     ("Can","Beverages")
        gi  = batch_start + bi
        row = int((y1 / ih) * 5) + 1
        items.append({"index": gi+1, "name": f"{shape} — Row {row} Item {(gi%10)+1}",
                      "brand":"", "category":cat, "estimated_price":0.0,
                      "sku": f"PROD-R{row}-{gi+1:03d}"})
    return items, "rule-based"


@router.post("/identify-batch")
async def identify_single_batch(
    payload: IdentifyBatchRequest,
    current_user: User = Depends(get_current_user),
):
    """Process one batch of detections. Frontend calls this repeatedly to show real progress."""
    image = _image_cache.get(payload.event_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found. Re-upload the shelf image.")
    iw, ih = image.size
    items, provider_used = await _run_batch(
        image, iw, ih, payload.detections, payload.batch_start, payload.provider
    )
    return {"items": items, "provider_used": provider_used}


@router.post("/identify-all")
async def identify_all_products(
    payload: IdentifyAllRequest,
    current_user: User = Depends(get_current_user),
):
    """Send detections to vision AI in batches of 10. Locks in the first working LLM."""
    image = _image_cache.get(payload.event_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found. Re-upload the shelf image.")

    iw, ih     = image.size
    detections = payload.detections
    BATCH      = 10
    identified: list[dict] = []
    locked_provider = ""

    for batch_start in range(0, len(detections), BATCH):
        batch  = detections[batch_start: batch_start + BATCH]
        items, locked_provider = await _run_batch(
            image, iw, ih, batch, batch_start, locked_provider
        )
        identified.extend(items)
        logger.info(f"Batch {batch_start//BATCH+1}: {locked_provider} → {len(items)} items")

    # Map index → product info
    id_map = {item["index"]: item for item in identified}

    # Group identical product names
    groups: dict[str, dict] = {}
    for idx, d in enumerate(detections):
        info      = id_map.get(idx + 1, {})
        name      = info.get("name", f"Unknown Product #{idx + 1}")
        brand     = info.get("brand", "")
        category  = info.get("category", "General")
        price     = info.get("estimated_price", 0.0)
        sku       = info.get("sku", f"SKU-{idx + 1}")
        conf      = d.get("confidence", 0.0)

        key = name.lower().strip()
        if key not in groups:
            groups[key] = {
                "name":      name,
                "brand":     brand,
                "category":  category,
                "estimated_price": price,
                "sku":       sku,
                "count":     0,
                "confidences": [],
                "indices":   [],       # original detection indices
                "first_bbox": d["bbox"],
            }
        groups[key]["count"]       += 1
        groups[key]["confidences"].append(conf)
        groups[key]["indices"].append(idx)

    result = []
    for g in groups.values():
        g["avg_confidence"] = round(sum(g["confidences"]) / len(g["confidences"]), 3)
        del g["confidences"]
        result.append(g)

    # Sort by count descending
    result.sort(key=lambda x: x["count"], reverse=True)
    return {"status": "ok", "groups": result, "total_unique": len(result)}


# ── Save detected product to inventory ───────────────────────────
class SaveProductRequest(BaseModel):
    name: str
    sku: str
    category: str
    price: float = 0.0
    quantity: int = 1
    low_stock_threshold: int = 10
    shelf_location: str = ""
    detection_event_id: Optional[int] = None

@router.post("/save-product")
def save_detected_product(
    payload: SaveProductRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.query(Product).filter(Product.sku == payload.sku).first()
    if existing:
        if existing.inventory:
            existing.inventory.quantity += payload.quantity
            existing.inventory.last_updated = datetime.utcnow()
            if payload.shelf_location:
                existing.inventory.shelf_location = payload.shelf_location
        db.commit()
        return {
            "status": "updated",
            "product_id": existing.id,
            "message": f"Quantity updated for '{existing.name}'",
        }

    product = Product(
        sku=payload.sku,
        name=payload.name,
        category=payload.category,
        low_stock_threshold=payload.low_stock_threshold,
    )
    db.add(product)
    db.flush()

    inventory = Inventory(
        product_id=product.id,
        quantity=payload.quantity,
        shelf_location=payload.shelf_location,
        last_updated=datetime.utcnow(),
    )
    db.add(inventory)
    db.commit()

    return {
        "status": "created",
        "product_id": product.id,
        "message": f"'{payload.name}' added to inventory",
    }


# ── History ──────────────────────────────────────────────────────
@router.get("/history")
def get_detection_history(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    events = db.query(DetectionEvent).order_by(DetectionEvent.detected_at.desc()).limit(limit).all()
    return [
        {
            "id": e.id,
            "image_path": e.image_path,
            "detected_at": e.detected_at.isoformat(),
            "total_items": e.total_items_detected,
        }
        for e in events
    ]


# ── Helpers ──────────────────────────────────────────────────────
def _map_to_retail_category(cls_name: str) -> str:
    mapping = {
        "bottle": "Beverages", "cup": "Beverages",
        "apple": "Produce", "orange": "Produce", "banana": "Produce",
        "sandwich": "Food", "pizza": "Food", "donut": "Bakery", "cake": "Bakery",
        "bowl": "Kitchenware", "book": "Stationery",
        "cell phone": "Electronics", "laptop": "Electronics",
        "keyboard": "Electronics", "mouse": "Electronics",
        "backpack": "Bags", "handbag": "Bags",
    }
    return mapping.get(cls_name, "General")

# ── Open Food Facts category → tag mapping (covers all 38 categories) ────────
_OFF_TAG_MAP = {
    # Produce
    "Fresh Fruits":                  "fruits",
    "Fresh Vegetables":              "vegetables",
    # Dairy
    "Milk & Dairy Drinks":           "milks",
    "Cheese":                        "cheeses",
    "Yogurt":                        "yogurts",
    "Eggs":                          "eggs",
    # Protein
    "Meat & Poultry":                "meats",
    "Seafood":                       "seafood",
    "Deli Meats":                    "deli-meats",
    # Frozen
    "Frozen Meals":                  "frozen-foods",
    "Ice Cream & Frozen Desserts":   "ice-creams",
    # Bakery / Grains
    "Bread & Bakery":                "breads",
    "Cookies & Crackers":            "biscuits-and-cakes",
    "Cereals & Oats":                "cereals",
    "Snack Bars & Protein Bars":     "snack-bars",
    # Snacks
    "Chips & Crisps":                "chips-and-crisps",
    "Nuts & Seeds":                  "nuts",
    "Candy & Chocolate":             "chocolates",
    # Beverages
    "Water & Juice":                 "juices",
    "Soda & Energy Drinks":          "sodas",
    "Tea & Coffee":                  "coffees",
    "Beer":                          "beers",
    "Wine & Spirits":                "wines",
    # Pantry
    "Canned Goods":                  "canned-foods",
    "Pasta & Noodles":               "pastas",
    "Rice & Grains":                 "rice",
    "Sauces & Condiments":           "sauces",
    "Cooking Oils":                  "oils",
    "Spreads & Jams":                "spreads",
    # Baby / Pet
    "Baby Products":                 "baby-foods",
    "Pet Food":                      "pet-foods",
    # Personal Care
    "Hair Care":                     "hair-care",
    "Body Wash & Soap":              "soaps",
    "Oral Care":                     "oral-hygiene",
    "Health & Vitamins":             "dietary-supplements",
    # Household
    "Household Cleaners":            "household-products",
    "Paper Products":                "paper-products",
    # Fallback
    "General Grocery":               "grocery",
    "General":                       "grocery",
}

async def _query_open_food_facts_batch(
    categories: list,
    matches: list,
) -> list:
    """
    For each unmatched detection, query Open Food Facts and return up to 3 product
    suggestions based on the Stage 2 category.

    Key fix: fetches 20 results per tag and distributes them so different detections
    within the same category get DIFFERENT suggestions, not the same 3 repeated.

    Returns list parallel to detections:
      - None                                    → detection already has a library match
      - [{name, brand, nutriscore, image_url, off_url}]  → OFF suggestions (may be [])
    """
    import httpx

    # Step 1: collect unique tags we need to fetch
    tag_pool: dict[str, list] = {}   # tag → full list of suggestions fetched
    tag_counters: dict[str, int] = {}  # tag → how many we've handed out so far

    for cat, match in zip(categories, matches):
        if not match:
            tag = _OFF_TAG_MAP.get(cat, "grocery")
            tag_pool[tag] = []  # placeholder; filled below

    async with httpx.AsyncClient(timeout=8.0) as client:
        for tag in list(tag_pool.keys()):
            try:
                resp = await client.get(
                    "https://world.openfoodfacts.org/cgi/search.pl",
                    params={
                        "action":    "process",
                        "tagtype_0": "categories",
                        "tag_0":     tag,
                        "sort_by":   "popularity",
                        "page_size": "20",   # fetch 20 so multiple items can differ
                        "json":      "1",
                        "fields":    "product_name,brands,nutriscore_grade,image_front_small_url,url",
                    }
                )
                products = resp.json().get("products", [])
                suggestions = []
                for p in products:
                    name = (p.get("product_name") or "").strip()
                    if not name:
                        continue
                    suggestions.append({
                        "name":       name,
                        "brand":      p.get("brands", ""),
                        "nutriscore": p.get("nutriscore_grade", ""),
                        "image_url":  p.get("image_front_small_url", ""),
                        "off_url":    p.get("url", ""),
                    })
                tag_pool[tag] = suggestions
                tag_counters[tag] = 0
                logger.info(f"[OFF] tag='{tag}' → {len(suggestions)} products fetched")
            except Exception as e:
                logger.warning(f"[OFF] API error for tag '{tag}': {e}")
                tag_pool[tag] = []
                tag_counters[tag] = 0

    # Step 2: assign a distinct 3-item window to each unmatched detection
    results = []
    for cat, match in zip(categories, matches):
        if match:
            results.append(None)
            continue

        tag  = _OFF_TAG_MAP.get(cat, "grocery")
        pool = tag_pool.get(tag, [])

        if not pool:
            results.append([])
            continue

        # Slide a window of 3 forward for each request within this tag
        offset = tag_counters.get(tag, 0)
        window = pool[offset: offset + 3]
        # If we've exhausted the pool, wrap around
        if not window:
            offset = 0
            window = pool[:3]
        tag_counters[tag] = offset + 3

        results.append(window)

    return results


# ── Stage 2 + 3 pipeline endpoint ────────────────────────────────
class PipelineRequest(BaseModel):
    event_id:   int
    detections: list   # [{bbox, confidence, ...}]

@router.post("/pipeline")
async def run_pipeline(
    payload:      PipelineRequest,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """
    Runs Stage 2 (category classification) and Stage 3 (SKU matching) on all
    detected crops from a previous /upload call.

    Returns the same detections list enriched with:
      category, category_confidence      — Stage 2 result
      matched_product, product_id,
      match_confidence, stage            — Stage 3 result (None if not in library)
    """
    from vision_pipeline import (
        classify_categories_batch,
        extract_embeddings_batch,
        find_best_matches,
    )

    image = _image_cache.get(payload.event_id)
    if image is None:
        raise HTTPException(
            status_code=404,
            detail="Image not in cache — re-upload the shelf image first."
        )

    iw, ih = image.size
    detections = payload.detections

    # Crop every detection
    crops: list = []
    for d in detections:
        x1, y1, x2, y2 = d["bbox"]
        pad  = 4
        crop = image.crop((
            max(0, int(x1) - pad), max(0, int(y1) - pad),
            min(iw, int(x2) + pad), min(ih, int(y2) + pad),
        ))
        crop.thumbnail((224, 224))
        crops.append(crop)

    # ── Stage 2: category classification ─────────────────────────
    cat_results = classify_categories_batch(crops)

    # ── Stage 3: embedding extraction + library search ────────────
    refs_raw = db.query(ProductReference).all()
    refs = [
        {
            "product_name": r.product_name,
            "product_id":   r.product_id,
            "embedding":    r.embedding,
        }
        for r in refs_raw
    ]

    embeddings = extract_embeddings_batch(crops)
    matches    = find_best_matches(embeddings, refs)

    # ── Stage 3b: Open Food Facts fallback for unmatched items ────
    # For items not in the local library, query Open Food Facts API
    # using the Stage 2 category. Returns product suggestions with no
    # local image maintenance required.
    off_suggestions = await _query_open_food_facts_batch(
        [cat_results[i][0] if i < len(cat_results) else "General"
         for i in range(len(detections))],
        matches
    )

    # ── Enrich detections ─────────────────────────────────────────
    enriched = []
    stage3_matched   = 0
    stage3_unmatched = 0

    for i, d in enumerate(detections):
        cat, cat_conf = cat_results[i] if i < len(cat_results) else ("General", 0.5)
        match = matches[i] if i < len(matches) else None
        off   = off_suggestions[i] if i < len(off_suggestions) else None

        enriched_d = {
            **d,
            # Stage 2
            "category":            cat,
            "category_confidence": round(cat_conf, 3),
            # Stage 3 — local library match
            "matched_product":     match["product_name"]     if match else None,
            "product_id":          match["product_id"]       if match else None,
            "match_confidence":    match["match_confidence"]  if match else None,
            "stage":               3 if match else 2,
            # Stage 3b — Open Food Facts suggestions (when no library match)
            "off_suggestions":     off if not match else None,
        }
        enriched.append(enriched_d)

        if match:
            stage3_matched += 1
        else:
            stage3_unmatched += 1

    from vision_pipeline import _clip_ready, _clip_error
    return {
        "event_id":   payload.event_id,
        "detections": enriched,
        "pipeline_stats": {
            "stage1_total":      len(detections),
            "stage2_classified": len(detections),
            "stage3_matched":    stage3_matched,
            "stage3_unmatched":  stage3_unmatched,
            "library_size":      len(refs),
            "clip_ready":        _clip_ready,
            "clip_error":        str(_clip_error) if _clip_error else None,
        },
    }


# ── Add crop directly to product library ──────────────────────────
class AddToLibraryRequest(BaseModel):
    event_id:     int
    bbox:         list[float]
    product_name: str
    product_id:   int | None = None

@router.post("/add-to-library")
async def add_detection_to_library(
    payload: AddToLibraryRequest,
    db:      Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Crop a bbox from the cached image, extract embedding, store in product library."""
    from vision_pipeline import extract_embeddings_batch
    import uuid

    image = _image_cache.get(payload.event_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not in cache — re-upload first.")

    iw, ih = image.size
    x1, y1, x2, y2 = payload.bbox
    pad  = 4
    crop = image.crop((
        max(0, int(x1) - pad), max(0, int(y1) - pad),
        min(iw, int(x2) + pad), min(ih, int(y2) + pad),
    ))

    embeddings = extract_embeddings_batch([crop])
    emb = embeddings[0]
    if emb is None:
        raise HTTPException(status_code=503, detail="CLIP model not available.")

    # Save crop image to product library folder
    ref_dir = os.path.join(os.path.dirname(__file__), "..", "product_library")
    os.makedirs(ref_dir, exist_ok=True)
    slug     = payload.product_name.lower().replace(" ", "_")[:30]
    filename = f"{slug}_{uuid.uuid4().hex[:8]}.jpg"
    img_path = os.path.join(ref_dir, filename)
    crop.convert("RGB").save(img_path, "JPEG", quality=90)

    ref = ProductReference(
        product_name = payload.product_name.strip(),
        product_id   = payload.product_id,
        image_path   = img_path,
        embedding    = json.dumps(emb),
    )
    db.add(ref)
    db.commit()
    db.refresh(ref)

    return {
        "id":           ref.id,
        "product_name": ref.product_name,
        "image_url":    f"/library/image/{ref.id}",
        "message":      f"Added to library: {ref.product_name}",
    }


def _update_inventory_from_detections(detections: list, db: Session) -> list:
    updates = []
    category_counts = {}
    for d in detections:
        cat = d["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    products = db.query(Product).all()
    for product in products:
        if product.category in category_counts and product.inventory:
            detected_count = category_counts[product.category]
            old_qty = product.inventory.quantity
            product.inventory.quantity = detected_count
            product.inventory.last_updated = datetime.utcnow()

            if product.inventory.quantity < product.low_stock_threshold:
                alert = Alert(
                    product_id=product.id,
                    alert_type="low_stock",
                    message=f"{product.name} is low: {product.inventory.quantity} units",
                )
                db.add(alert)

            updates.append({
                "sku": product.sku,
                "name": product.name,
                "old_quantity": old_qty,
                "new_quantity": product.inventory.quantity,
            })
    return updates
