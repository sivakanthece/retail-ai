from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, DetectionEvent, Inventory, Product, Alert, ProductReference, Planogram
from security import get_current_user, User
from config import settings
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont
import asyncio
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
    # __file__ is backend/routers/detection.py — go up one level to backend/
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    model_path = os.path.join(backend_dir, model_name)

    if os.path.exists(model_path):
        return model_path  # return full path so YOLO loads it correctly

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
            full = os.path.join(backend_dir, model_name)
            logger.info(f"Downloaded {model_name} to {full}")
            return full
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


def _library_preflight(image, iw, ih, batch, db):
    """
    Run CLIP embedding + library match on a batch of detections.
    Returns a list parallel to `batch` — each entry is either a match dict
    (product_name, product_id, match_confidence, category) or None.
    Items that get a library match skip the LLM entirely.
    """
    try:
        from vision_pipeline import extract_embeddings_batch, find_best_matches
        refs_raw = db.query(ProductReference).all()
        if not refs_raw:
            return [None] * len(batch)

        refs = [
            {"product_name": r.product_name, "product_id": r.product_id, "embedding": r.embedding}
            for r in refs_raw
        ]

        crops = []
        for d in batch:
            x1, y1, x2, y2 = d["bbox"]
            crop = image.crop((max(0,int(x1)), max(0,int(y1)),
                               min(iw,int(x2)), min(ih,int(y2))))
            crop.thumbnail((224, 224))
            crops.append(crop)

        embeddings = extract_embeddings_batch(crops)
        matches    = find_best_matches(embeddings, refs)
        return matches   # None for non-matches, dict for matches
    except Exception as e:
        logger.warning(f"Library preflight failed: {e}")
        return [None] * len(batch)


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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check library first; only send unmatched items to LLM."""
    image = _image_cache.get(payload.event_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found. Re-upload the shelf image.")
    iw, ih = image.size
    batch  = payload.detections

    # ── Library preflight ─────────────────────────────────────────
    lib_matches = await asyncio.to_thread(
        _library_preflight, image, iw, ih, batch, db
    )

    # Detections with no library match go to LLM
    unmatched_indices = [i for i, m in enumerate(lib_matches) if m is None]
    items = []

    if unmatched_indices:
        unmatched_batch = [batch[i] for i in unmatched_indices]
        llm_items, provider_used = await _run_batch(
            image, iw, ih, unmatched_batch, payload.batch_start, payload.provider
        )
        # Re-index LLM results back to original batch positions
        for llm_pos, orig_pos in enumerate(unmatched_indices):
            matched = next((it for it in llm_items if it.get("index") == payload.batch_start + llm_pos + 1), None)
            if matched:
                matched["index"] = payload.batch_start + orig_pos + 1
                items.append(matched)
    else:
        provider_used = "library"

    # Fill in library matches
    for i, m in enumerate(lib_matches):
        if m is not None:
            items.append({
                "index":           payload.batch_start + i + 1,
                "name":            m["product_name"],
                "brand":           "",
                "category":        m.get("category", ""),
                "estimated_price": 0.0,
                "sku":             "",
                "from_library":    True,
                "match_confidence": m["match_confidence"],
            })

    items.sort(key=lambda x: x["index"])
    lib_count = sum(1 for m in lib_matches if m is not None)
    return {"items": items, "provider_used": provider_used,
            "library_hits": lib_count, "llm_calls": len(unmatched_indices)}


@router.post("/identify-all")
async def identify_all_products(
    payload: IdentifyAllRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check library first; send only unmatched detections to LLM in batches of 10."""
    image = _image_cache.get(payload.event_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found. Re-upload the shelf image.")

    iw, ih     = image.size
    detections = payload.detections
    BATCH      = 10

    # ── Library preflight across all detections ───────────────────
    all_lib_matches = await asyncio.to_thread(
        _library_preflight, image, iw, ih, detections, db
    )

    unmatched_indices = [i for i, m in enumerate(all_lib_matches) if m is None]
    identified: list[dict] = []
    locked_provider = ""

    # Only send unmatched detections to LLM
    for batch_start in range(0, len(unmatched_indices), BATCH):
        chunk_idx = unmatched_indices[batch_start: batch_start + BATCH]
        batch     = [detections[i] for i in chunk_idx]
        items, locked_provider = await _run_batch(
            image, iw, ih, batch, batch_start, locked_provider
        )
        # Re-map indices back to original positions
        for pos, (it, orig_i) in enumerate(zip(items, chunk_idx)):
            it["index"] = orig_i + 1
            identified.append(it)
        logger.info(f"Batch {batch_start//BATCH+1}: {locked_provider} → {len(items)} items")

    # Merge library matches into results
    for i, m in enumerate(all_lib_matches):
        if m is not None:
            identified.append({
                "index":            i + 1,
                "name":             m["product_name"],
                "brand":            "",
                "category":         m.get("category", ""),
                "estimated_price":  0.0,
                "sku":              "",
                "from_library":     True,
                "match_confidence": m["match_confidence"],
            })

    lib_count = sum(1 for m in all_lib_matches if m is not None)
    logger.info(f"identify-all: {lib_count} library hits, {len(unmatched_indices)} sent to LLM")

    # Map index → product info
    id_map = {item["index"]: item for item in identified}

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

# ── Stage 2 + 3 pipeline endpoint ────────────────────────────────
class PipelineRequest(BaseModel):
    event_id:      int
    detections:    list           # [{bbox, confidence, ...}]
    shelf_id:      str  = "SHELF-A1"   # which planogram shelf to check against
    use_planogram: bool = True    # set False to skip planogram lookup & compliance

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

    # ── Assign grid positions (row, col) from bounding box centres ─
    # Sort by y_centre to determine row bands, then by x_centre for col.
    # Works even when shelf rows aren't perfectly uniform.
    def _assign_grid(dets: list, img_h: int, num_rows: int = 3) -> list[tuple[int, int]]:
        """Return (row, col) for each detection using y-band bucketing."""
        if not dets:
            return []
        band_h = img_h / num_rows
        # Compute centre coords
        centres = [
            ((d["bbox"][1] + d["bbox"][3]) / 2, (d["bbox"][0] + d["bbox"][2]) / 2)
            for d in dets
        ]
        rows = [min(int(yc / band_h), num_rows - 1) + 1 for yc, _ in centres]

        # Within each row, rank by x_centre to assign col
        from collections import defaultdict
        row_groups: dict[int, list] = defaultdict(list)
        for idx, (r, (yc, xc)) in enumerate(zip(rows, centres)):
            row_groups[r].append((xc, idx))

        col_map = {}
        for r, items in row_groups.items():
            items.sort(key=lambda x: x[0])  # left → right
            for col_rank, (_, orig_idx) in enumerate(items, start=1):
                col_map[orig_idx] = col_rank

        return [(rows[i], col_map.get(i, 1)) for i in range(len(dets))]

    # ── Stage 3.5: planogram lookup (optional) ────────────────────
    shelf_id      = getattr(payload, "shelf_id", None) or "SHELF-A1"
    use_planogram = getattr(payload, "use_planogram", True)

    if use_planogram:
        pog_rows = db.query(Planogram).filter(Planogram.shelf_id == shelf_id).all()
    else:
        pog_rows = []

    pog_index: dict[tuple[int,int], Planogram] = {(p.row, p.col): p for p in pog_rows}
    pog_hits:  dict[int, dict] = {}   # detection index → {name, brand, sku}

    # Auto-detect shelf row count from planogram so grid bands are correct.
    # Falls back to 3 when planogram is empty or disabled.
    num_rows_from_pog = max((p.row for p in pog_rows), default=0)
    num_rows          = num_rows_from_pog if num_rows_from_pog > 0 else 3
    grid_positions    = _assign_grid(detections, ih, num_rows=num_rows)

    if use_planogram:
        for i, m in enumerate(matches):
            if m:
                continue  # already matched by library — skip planogram
            row, col = grid_positions[i] if i < len(grid_positions) else (0, 0)
            pog = pog_index.get((row, col))
            if pog:
                pog_hits[i] = {
                    "name":  pog.product_name,
                    "brand": pog.brand or "",
                    "sku":   pog.sku   or "",
                }
                logger.info(f"[pipeline] Stage 3.5 planogram hit: R{row}C{col} → {pog.product_name}")

    # ── Stage 3b: LLM identification — only for items still unmatched ──
    still_unmatched = [
        i for i, m in enumerate(matches)
        if not m and i not in pog_hits
    ]
    llm_names: dict[int, dict] = {}

    if still_unmatched:
        unmatched_batch = [detections[i] for i in still_unmatched]
        try:
            llm_items, llm_provider = await _run_batch(
                image, iw, ih, unmatched_batch, batch_start=0
            )
            logger.info(f"[pipeline] Stage 3b LLM: {len(llm_items)} names via {llm_provider}")
            for j, orig_i in enumerate(still_unmatched):
                if j < len(llm_items):
                    llm_names[orig_i] = {
                        "name":  llm_items[j].get("name", ""),
                        "brand": llm_items[j].get("brand", ""),
                    }
        except Exception as e:
            logger.warning(f"[pipeline] Stage 3b LLM failed: {e}")

    # ── Enrich detections + compliance ────────────────────────────
    enriched = []
    stage3_matched     = 0
    stage3_unmatched   = 0
    pog_matched        = 0
    compliance_results = []

    for i, d in enumerate(detections):
        cat, cat_conf = cat_results[i] if i < len(cat_results) else ("General", 0.5)
        match = matches[i] if i < len(matches) else None
        pog   = pog_hits.get(i)
        llm   = llm_names.get(i)
        row, col = grid_positions[i] if i < len(grid_positions) else (0, 0)

        # Priority: library > planogram > LLM > None
        if match:
            final_name  = match["product_name"]
            final_brand = None
            final_sku   = None
            id_stage    = 3
            stage3_matched += 1
        elif pog:
            final_name  = pog["name"]
            final_brand = pog["brand"]
            final_sku   = pog["sku"]
            id_stage    = 3   # treat planogram match as Stage 3 confidence
            pog_matched += 1
        elif llm:
            final_name  = llm.get("name") or None
            final_brand = llm.get("brand") or None
            final_sku   = None
            id_stage    = 2
            stage3_unmatched += 1
        else:
            final_name  = None
            final_brand = None
            final_sku   = None
            id_stage    = 2
            stage3_unmatched += 1

        # Compliance: compare final_name against planogram expectation
        pog_entry = pog_index.get((row, col)) if use_planogram else None
        if not use_planogram or pog_entry is None:
            compliance = "no_planogram"
        elif not final_name:
            compliance = "unidentified"
        else:
            # Normalise hyphens → spaces so "Coca-Cola" matches "Coca Cola"
            det_low  = final_name.lower().replace("-", " ").replace("_", " ")
            exp_low  = pog_entry.product_name.lower().replace("-", " ").replace("_", " ")
            words_ok = any(w in det_low for w in exp_low.split() if len(w) > 3)
            compliance = "ok" if words_ok else "mismatch"

        compliance_results.append({
            "row":      row,
            "col":      col,
            "detected": final_name,
            "expected": pog_entry.product_name if pog_entry else None,
            "status":   compliance,
        })

        enriched_d = {
            **d,
            "category":            cat,
            "category_confidence": round(cat_conf, 3),
            "matched_product":     final_name,
            "product_id":          match["product_id"] if match else None,
            "match_confidence":    match["match_confidence"] if match else None,
            "brand":               final_brand,
            "sku":                 final_sku,
            "llm_identified":      (not match and not pog) and bool(llm and llm.get("name")),
            "planogram_identified": bool(pog and not match),
            "stage":               id_stage,
            "grid_row":            row,
            "grid_col":            col,
            "compliance":          compliance,
        }
        enriched.append(enriched_d)

    # Compliance summary
    ok_count = sum(1 for c in compliance_results if c["status"] == "ok")
    compliance_rate = round(ok_count / len(compliance_results) * 100, 1) if compliance_results else 0

    from vision_pipeline import _clip_ready, _clip_error
    return {
        "event_id":   payload.event_id,
        "detections": enriched,
        "pipeline_stats": {
            "stage1_total":        len(detections),
            "stage2_classified":   len(detections),
            "stage3_matched":      stage3_matched,
            "stage3_planogram":    pog_matched,
            "stage3_llm":          len([l for l in llm_names.values() if l.get("name")]),
            "stage3_unmatched":    stage3_unmatched,
            "library_size":        len(refs),
            "planogram_size":      len(pog_rows),
            "planogram_enabled":   use_planogram,
            "num_rows_detected":   num_rows,
            "clip_ready":          _clip_ready,
            "clip_error":          str(_clip_error) if _clip_error else None,
        },
        "compliance": {
            "shelf_id":        shelf_id,
            "compliance_rate": compliance_rate,
            "ok":              ok_count,
            "mismatch":        sum(1 for c in compliance_results if c["status"] == "mismatch"),
            "unidentified":    sum(1 for c in compliance_results if c["status"] == "unidentified"),
            "no_planogram":    sum(1 for c in compliance_results if c["status"] == "no_planogram"),
            "details":         compliance_results,
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
