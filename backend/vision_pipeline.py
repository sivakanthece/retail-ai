"""
vision_pipeline.py
==================
Stage 2 – Hierarchical Category Classification
    Uses CLIP (ViT-B/32) zero-shot classification against 38 retail category prompts.
    Requires: transformers>=4.40.0  (torch is already installed via ultralytics)

Stage 3 – Fine-Grained SKU Matching
    Extracts 512-dim CLIP image embeddings and compares them via cosine similarity
    against stored reference embeddings in the product library database.
    Match threshold default: 0.82 (tune higher for stricter matching).

Both stages use the SAME CLIP model — loaded once, cached for all requests.
First load downloads ~340 MB (ViT-B/32 weights); subsequent starts use disk cache.
"""

import os, json, logging
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

logger = logging.getLogger(__name__)

# ── Retail category taxonomy (38 categories) ─────────────────────────────────
CATEGORIES = [
    "Fresh Fruits",
    "Fresh Vegetables",
    "Milk & Dairy Drinks",
    "Cheese",
    "Yogurt",
    "Eggs",
    "Meat & Poultry",
    "Seafood",
    "Deli Meats",
    "Frozen Meals",
    "Ice Cream & Frozen Desserts",
    "Bread & Bakery",
    "Cookies & Crackers",
    "Cereals & Oats",
    "Snack Bars & Protein Bars",
    "Chips & Crisps",
    "Nuts & Seeds",
    "Candy & Chocolate",
    "Water & Juice",
    "Soda & Energy Drinks",
    "Tea & Coffee",
    "Beer",
    "Wine & Spirits",
    "Canned Goods",
    "Pasta & Noodles",
    "Rice & Grains",
    "Sauces & Condiments",
    "Cooking Oils",
    "Spreads & Jams",
    "Baby Products",
    "Pet Food",
    "Hair Care",
    "Body Wash & Soap",
    "Oral Care",
    "Health & Vitamins",
    "Household Cleaners",
    "Paper Products",
    "General Grocery",
]

# 4 prompt templates per category — averaged at load time for prompt ensembling.
# Visually descriptive language helps CLIP distinguish similar-looking products.
CATEGORY_PROMPT_TEMPLATES = {
    "Fresh Fruits": [
        "fresh apples, oranges, or bananas in a grocery store",
        "a display of colourful fresh fruit on a produce shelf",
        "loose fruits or a bag of fruit in the produce section",
        "fresh berries, grapes, or tropical fruit on a store shelf",
    ],
    "Fresh Vegetables": [
        "fresh broccoli, carrots, or lettuce in a grocery store",
        "a bunch of vegetables on a produce shelf",
        "packaged salad greens or a bag of vegetables",
        "loose onions, peppers, or tomatoes in the produce section",
    ],
    "Milk & Dairy Drinks": [
        "a carton or bottle of milk on a supermarket shelf",
        "a jug of cow's milk or plant-based milk in a fridge",
        "a half-gallon milk carton in a grocery store",
        "a dairy drink like milk or cream in refrigerated packaging",
    ],
    "Cheese": [
        "a block or wedge of cheese on a store shelf",
        "a package of sliced cheese or shredded cheese in a bag",
        "a wheel or block of cheddar, mozzarella, or parmesan",
        "packaged cheese in a grocery store refrigerator section",
    ],
    "Yogurt": [
        "a plastic tub of yogurt in a grocery store fridge",
        "a small cup of Greek yogurt on a refrigerator shelf",
        "a multi-pack of yogurt cups in a supermarket",
        "a container of flavoured yogurt with fruit on the label",
    ],
    "Eggs": [
        "a cardboard carton of eggs on a grocery store shelf",
        "a box of 6 or 12 chicken eggs in a supermarket",
        "egg packaging in the dairy section of a grocery store",
        "a cardboard egg carton in a refrigerator section",
    ],
    "Meat & Poultry": [
        "a sealed tray of raw chicken breasts in plastic wrap",
        "a tray of ground beef or raw steak at the butcher counter",
        "packaged raw meat or poultry on a refrigerator shelf",
        "a sealed tray of pork chops or chicken thighs in a grocery store",
    ],
    "Seafood": [
        "a package of fresh or frozen fish fillets",
        "a bag of frozen shrimp or prawns on a store shelf",
        "packaged salmon or cod in a grocery store seafood section",
        "a tin of canned tuna or sardines on a shelf",
    ],
    "Deli Meats": [
        "a vacuum-sealed pack of sliced ham or turkey",
        "a packet of sliced salami or pepperoni in a fridge",
        "packaged lunch meat like bologna or roast beef on a shelf",
        "a re-sealable pack of sliced deli meats in a supermarket",
    ],
    "Frozen Meals": [
        "a cardboard box of frozen dinner or microwave meal",
        "a frozen pizza box in a supermarket freezer",
        "a frozen ready meal or TV dinner in a box",
        "a bag of frozen stir-fry or frozen vegetables in a freezer",
    ],
    "Ice Cream & Frozen Desserts": [
        "a large tub of ice cream in a freezer",
        "a box of ice cream bars or frozen popsicles",
        "an ice cream container with flavour name on the lid",
        "a carton of gelato or frozen yogurt in a supermarket freezer",
    ],
    "Bread & Bakery": [
        "a plastic bag of sliced sandwich bread",
        "a loaf of bread or bread rolls on a bakery shelf",
        "packaged bagels, burger buns, or English muffins",
        "a bag of white or wholemeal bread in a supermarket",
    ],
    "Cookies & Crackers": [
        "a box or packet of cookies on a store shelf",
        "a packet of crackers or water biscuits in a supermarket",
        "a resealable bag of chocolate chip cookies",
        "a box of cream crackers or rice cakes on a snack shelf",
    ],
    "Cereals & Oats": [
        "a cardboard box of breakfast cereal on a shelf",
        "a box of corn flakes, granola, or muesli in a supermarket",
        "a canister of rolled oats or instant porridge",
        "a large cereal box with colourful branding on the front",
    ],
    "Snack Bars & Protein Bars": [
        "a protein bar or granola bar in an individual wrapper",
        "a box of energy bars or cereal bars on a shelf",
        "individually wrapped nutrition bars in a supermarket display",
        "a muesli bar or meal replacement bar with nutritional labelling",
    ],
    "Chips & Crisps": [
        "a large foil bag of potato chips or crisps",
        "a packet of tortilla chips or corn chips on a shelf",
        "a colourful foil bag of flavoured crisps on a snack aisle",
        "a multi-pack of small crisp bags in a supermarket",
    ],
    "Nuts & Seeds": [
        "a resealable bag of mixed nuts or roasted almonds",
        "a packet of cashews, walnuts, or peanuts on a shelf",
        "a bag of sunflower seeds or pumpkin seeds in a store",
        "a jar or canister of roasted nuts in a grocery store",
    ],
    "Candy & Chocolate": [
        "a chocolate bar in a foil and paper wrapper",
        "a bag of gummy sweets, jelly beans, or hard candy",
        "a box of assorted chocolates or chocolate truffles",
        "a candy wrapper or confectionery packet on a store shelf",
    ],
    "Water & Juice": [
        "a plastic bottle of still or sparkling water",
        "a carton or glass bottle of orange juice or apple juice",
        "a six-pack of water bottles on a store shelf",
        "a bottle of fruit juice, coconut water, or smoothie",
    ],
    "Soda & Energy Drinks": [
        "a can of cola, lemonade, or fizzy soda",
        "a large plastic bottle of carbonated soft drink",
        "a tall can of energy drink like Red Bull or Monster",
        "a multi-pack of soda cans in a supermarket fridge",
    ],
    "Tea & Coffee": [
        "a rectangular box of tea bags on a grocery shelf",
        "a glass jar of instant coffee granules",
        "a bag of ground coffee beans or a coffee pod box",
        "a tin of loose leaf tea or a coffee canister",
    ],
    "Beer": [
        "a six-pack of beer cans or bottles with labels",
        "a glass bottle of lager or ale with a branded label",
        "a can of craft beer or stout on a store shelf",
        "a case or multi-pack of beer bottles in a supermarket",
    ],
    "Wine & Spirits": [
        "a tall glass bottle of red or white wine with a cork",
        "a bottle of whiskey, gin, vodka, or rum",
        "a wine bottle with a paper label and metal foil top",
        "a spirits bottle on a liquor store shelf",
    ],
    "Canned Goods": [
        "a metal tin can of soup or baked beans on a shelf",
        "a can of diced tomatoes, sweetcorn, or chickpeas",
        "a stack of tin cans in a grocery store aisle",
        "a tin of canned fish, canned fruit, or canned vegetables",
    ],
    "Pasta & Noodles": [
        "a cellophane packet of dried spaghetti or linguine",
        "a cardboard box of penne, macaroni, or fusilli pasta",
        "a packet of instant noodles or ramen in a foil wrapper",
        "boxes and bags of dried pasta on a supermarket aisle shelf",
    ],
    "Rice & Grains": [
        "a large bag of white rice or brown rice",
        "a box or packet of quinoa, couscous, or bulgur wheat",
        "a kilogram bag of long-grain or basmati rice",
        "a box of instant rice or a grain medley packet",
    ],
    "Sauces & Condiments": [
        "a plastic bottle of ketchup or tomato sauce",
        "a glass jar of mayonnaise, mustard, or relish",
        "a bottle of soy sauce, hot sauce, or barbecue sauce",
        "condiment bottles and sauce jars lined up on a store shelf",
    ],
    "Cooking Oils": [
        "a glass or plastic bottle of olive oil on a shelf",
        "a large plastic bottle of sunflower oil or vegetable oil",
        "a bottle of coconut oil or avocado oil in a grocery store",
        "oil and vinegar bottles on a supermarket cooking aisle",
    ],
    "Spreads & Jams": [
        "a glass jar of strawberry jam or orange marmalade",
        "a plastic jar of peanut butter or almond butter",
        "a tub or jar of Nutella or chocolate hazelnut spread",
        "a jar of honey, maple syrup, or lemon curd on a shelf",
    ],
    "Baby Products": [
        "a tin or cardboard box of infant formula on a shelf",
        "a pack of nappies or baby diapers in a supermarket",
        "a glass jar or pouch of baby food puree",
        "baby food jars and infant care products on a store shelf",
    ],
    "Pet Food": [
        "a large bag of dry dog kibble on a store shelf",
        "a tin or foil pouch of wet cat food",
        "a big sack of pet food with a dog or cat on the label",
        "canned or pouched pet food stacked on a supermarket shelf",
    ],
    "Hair Care": [
        "a pump or squeeze bottle of shampoo on a shelf",
        "a bottle of conditioner or hair treatment product",
        "shampoo and conditioner bottles with colourful labels",
        "hair care products lined up on a pharmacy shelf",
    ],
    "Body Wash & Soap": [
        "a rectangular bar of soap in a paper wrapper",
        "a pump bottle of liquid body wash or shower gel",
        "a multi-pack of soap bars on a store shelf",
        "a bottle of hand wash or bath foam with a pump dispenser",
    ],
    "Oral Care": [
        "a tube of toothpaste on a drugstore shelf",
        "a toothbrush in plastic packaging in a supermarket",
        "a bottle of mouthwash with a flip-top cap",
        "oral hygiene products including floss and toothpaste on a shelf",
    ],
    "Health & Vitamins": [
        "a brown or white bottle of vitamin capsules or tablets",
        "a box of over-the-counter medicine or pain relief tablets",
        "a bottle of multivitamins or fish oil supplements",
        "packaged health supplements on a pharmacy shelf",
    ],
    "Household Cleaners": [
        "a trigger spray bottle of household cleaning product",
        "a large bottle of laundry detergent with a measuring cap",
        "a box of dishwasher tablets or washing powder",
        "cleaning supplies including bleach and surface cleaner on a shelf",
    ],
    "Paper Products": [
        "a multi-pack of toilet paper rolls in plastic wrap",
        "a roll of kitchen paper towels on a store shelf",
        "a box of facial tissues with a pop-up opening",
        "packaged toilet paper and paper towels in a supermarket",
    ],
    "General Grocery": [
        "a grocery product on a store shelf",
        "a packaged consumer good in a supermarket aisle",
        "a retail product with a label and barcode",
        "a boxed or packaged product on a grocery shelf",
    ],
}

MATCH_THRESHOLD = 0.82   # cosine similarity below this → "not in library"

# ── Singleton state ───────────────────────────────────────────────────────────
_processor       = None
_model           = None
_text_features   = None   # shape [N_CATS, 512] — pre-encoded category prompts
_clip_ready      = False
_clip_error      = None   # set on failure; cleared on each retry attempt


# ── Safe tensor extraction helpers ───────────────────────────────────────────

def _to_text_tensor(raw) -> torch.Tensor:
    """
    Safely extract a 2-D text-embedding tensor from get_text_features() output.

    BUG FIX: Using raw[0] on a CLIPTextModelOutput returns last_hidden_state
    (shape [batch, seq_len, 512]) — a 3-D tensor. Different categories have
    different sequence lengths, so torch.stack fails with mismatched shapes
    like [12, 512] vs [11, 512]. Use named attributes instead.
    """
    if isinstance(raw, torch.Tensor):
        return raw                         # modern transformers — direct tensor
    if hasattr(raw, "text_embeds") and raw.text_embeds is not None:
        return raw.text_embeds             # CLIPOutput wrapper
    if hasattr(raw, "pooler_output") and raw.pooler_output is not None:
        return raw.pooler_output
    return raw.last_hidden_state[:, 0, :] # CLS token fallback


def _to_image_tensor(raw) -> torch.Tensor:
    """Safely extract a 2-D image-embedding tensor from get_image_features() output."""
    if isinstance(raw, torch.Tensor):
        return raw
    if hasattr(raw, "image_embeds") and raw.image_embeds is not None:
        return raw.image_embeds
    if hasattr(raw, "pooler_output") and raw.pooler_output is not None:
        return raw.pooler_output
    return raw.last_hidden_state[:, 0, :]


def _load_clip() -> bool:
    """
    Lazy-loads CLIP on first call.  Returns True if ready, False if unavailable.

    Loading priority:
      1. clip_retail.pt  — fine-tuned weights in same dir (best accuracy)
      2. openai/clip-vit-base-patch32 — pretrained from HuggingFace cache
         (downloaded at Docker build time; no internet needed at runtime)
    """
    global _processor, _model, _text_features, _clip_ready, _clip_error

    if _clip_ready:
        return True
    _clip_error = None   # clear so retries work

    try:
        from transformers import CLIPModel, CLIPProcessor
        base_model = "openai/clip-vit-base-patch32"

        logger.info("[Pipeline] Loading CLIP processor …")
        _processor = CLIPProcessor.from_pretrained(base_model)

        local_pt = os.path.join(os.path.dirname(__file__), "clip_retail.pt")
        if os.path.exists(local_pt):
            logger.info(f"[Pipeline] Loading fine-tuned CLIP from {local_pt}")
            _model = CLIPModel.from_pretrained(base_model)
            state  = torch.load(local_pt, map_location="cpu", weights_only=False)
            _model.load_state_dict(state)
        else:
            logger.info("[Pipeline] Loading pretrained CLIP ViT-B/32 …")
            _model = CLIPModel.from_pretrained(base_model)

        _model.eval()

        # Pre-encode all category prompts using prompt ensembling.
        # Each category gets 4 templates encoded, averaged, then re-normalised.
        logger.info(f"[Pipeline] Encoding {len(CATEGORIES)} categories with prompt ensembling …")
        category_embeddings = []
        with torch.no_grad():
            for cat in CATEGORIES:
                templates = CATEGORY_PROMPT_TEMPLATES[cat]
                inputs = _processor(
                    text=templates, return_tensors="pt", padding=True, truncation=True
                )
                raw    = _model.get_text_features(**inputs)
                t      = _to_text_tensor(raw)         # always [4, 512]
                t      = F.normalize(t, dim=-1)        # normalise each template
                t_mean = t.mean(dim=0)                 # → [512]
                t_mean = F.normalize(t_mean, dim=0)    # re-normalise the mean
                category_embeddings.append(t_mean)     # [512] for every cat

        _text_features = torch.stack(category_embeddings)   # [N_CATS, 512]

        _clip_ready = True
        logger.info(
            f"[Pipeline] CLIP ready — {len(CATEGORIES)} categories, "
            f"text_features shape: {list(_text_features.shape)}"
        )
        return True

    except Exception as exc:
        _clip_error = exc
        logger.error(
            f"\n{'='*60}\n"
            f"[Pipeline] CLIP FAILED TO LOAD: {exc}\n"
            f"Stage 2 (category classification) and Stage 3 (SKU matching)\n"
            f"will return fallback values until this is resolved.\n"
            f"Fix: pip install transformers>=4.40.0  then restart the server.\n"
            f"{'='*60}"
        )
        return False


# ── Stage 2 ───────────────────────────────────────────────────────────────────

def classify_categories_batch(crops: list) -> list:
    """
    Stage 2: classify a list of PIL crop images into retail categories.
    Returns list of (category_name, confidence) — one entry per crop.
    Falls back to ("General Grocery", 0.5) if CLIP is unavailable.
    """
    if not crops:
        return []

    if not _load_clip():
        return [("General Grocery", 0.5)] * len(crops)

    try:
        rgb_crops = [c.convert("RGB") for c in crops]
        inputs    = _processor(images=rgb_crops, return_tensors="pt")
        with torch.no_grad():
            raw       = _model.get_image_features(**inputs)
            img_feats = _to_image_tensor(raw)           # [N, 512]
            img_feats = F.normalize(img_feats, dim=-1)

        # Raw cosine similarities: [N, N_CATS]
        sims = img_feats @ _text_features.T

        results = []
        for i in range(len(crops)):
            row      = sims[i]
            idx      = int(row.argmax())
            raw_conf = float(row[idx])
            results.append((CATEGORIES[idx], round(raw_conf, 3)))

        logger.debug(f"[Stage2] {[r[0] for r in results]}, confs={[r[1] for r in results]}")
        return results

    except Exception as exc:
        logger.error(f"[Stage2] batch error: {exc}")
        return [("General Grocery", 0.5)] * len(crops)


# ── Stage 3 ───────────────────────────────────────────────────────────────────

def extract_embeddings_batch(crops: list) -> list:
    """
    Stage 3a: extract normalised 512-dim CLIP embeddings for a list of crops.
    Returns None for each crop if CLIP is unavailable.
    """
    if not crops:
        return []

    if not _load_clip():
        return [None] * len(crops)

    try:
        rgb_crops = [c.convert("RGB") for c in crops]
        inputs    = _processor(images=rgb_crops, return_tensors="pt")
        with torch.no_grad():
            raw   = _model.get_image_features(**inputs)
            feats = _to_image_tensor(raw)           # [N, 512]
            feats = F.normalize(feats, dim=-1)
        return [feats[i].tolist() for i in range(len(crops))]

    except Exception as exc:
        logger.error(f"[Stage3] embedding error: {exc}")
        return [None] * len(crops)


def cosine_similarity(a: list, b: list) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom < 1e-8:
        return 0.0
    return float(np.dot(va, vb) / denom)


def find_best_matches(
    query_embeddings: list,
    references: list,          # [{product_name, product_id, embedding (JSON str)}]
    threshold: float = MATCH_THRESHOLD,
) -> list:
    """
    Stage 3b: for each query embedding find the best-matching product in the library.

    Groups references by product_name, takes MAX similarity across all reference
    images for that product, returns None if below threshold.
    """
    if not references:
        return [None] * len(query_embeddings)

    parsed_refs = []
    for ref in references:
        try:
            emb = json.loads(ref["embedding"]) if isinstance(ref["embedding"], str) else ref["embedding"]
            parsed_refs.append({**ref, "emb_parsed": emb})
        except Exception:
            continue

    results = []
    for q_emb in query_embeddings:
        if q_emb is None:
            results.append(None)
            continue

        best_per_product: dict = {}
        for ref in parsed_refs:
            sim  = cosine_similarity(q_emb, ref["emb_parsed"])
            name = ref["product_name"]
            if name not in best_per_product or sim > best_per_product[name]["sim"]:
                best_per_product[name] = {
                    "sim":          sim,
                    "product_name": name,
                    "product_id":   ref.get("product_id"),
                }

        if not best_per_product:
            results.append(None)
            continue

        best = max(best_per_product.values(), key=lambda x: x["sim"])
        if best["sim"] < threshold:
            results.append(None)
        else:
            results.append({
                "product_name":     best["product_name"],
                "product_id":       best["product_id"],
                "match_confidence": round(best["sim"], 3),
            })

    return results
