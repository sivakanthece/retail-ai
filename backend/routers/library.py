"""
routers/library.py
==================
Product Library — manages reference images for Stage 3 SKU matching.

Endpoints:
  POST   /library/references          upload a reference crop image for a product
  GET    /library/references          list all references grouped by product name
  DELETE /library/references/{id}     delete one reference
  GET    /library/products            unique product names + count of refs each
  GET    /library/stats               quick summary stats
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from database import get_db, ProductReference, User
from security import get_current_user
from vision_pipeline import extract_embeddings_batch
from PIL import Image
import io
import os
import json
import uuid

router = APIRouter(prefix="/library", tags=["library"])

# Directory to store product library reference crop images
REF_DIR = os.path.join(os.path.dirname(__file__), "..", "product_library")
os.makedirs(REF_DIR, exist_ok=True)


def _save_image(img: Image.Image, name: str) -> str:
    """Save PIL image to REF_DIR and return the file path."""
    filename = f"{name}_{uuid.uuid4().hex[:8]}.jpg"
    path     = os.path.join(REF_DIR, filename)
    img.convert("RGB").save(path, "JPEG", quality=90)
    return path


# ── Upload reference image ────────────────────────────────────────────────────
@router.post("/references")
async def add_reference(
    file:         UploadFile = File(...),
    product_name: str        = Form(...),
    product_id:   int | None = Form(None),
    db:           Session    = Depends(get_db),
    current_user: User       = Depends(get_current_user),
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image.")

    contents = await file.read()
    try:
        img = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Cannot decode image.")

    # Extract CLIP embedding
    embeddings = extract_embeddings_batch([img])
    emb = embeddings[0]
    if emb is None:
        raise HTTPException(
            status_code=503,
            detail="CLIP model unavailable — install transformers>=4.40.0 and restart."
        )

    # Save image file
    slug = product_name.lower().replace(" ", "_")[:30]
    img_path = _save_image(img, slug)

    ref = ProductReference(
        product_name = product_name.strip(),
        product_id   = product_id,
        image_path   = img_path,
        embedding    = json.dumps(emb),
    )
    db.add(ref)
    db.commit()
    db.refresh(ref)

    return {
        "id":           ref.id,
        "product_name": ref.product_name,
        "product_id":   ref.product_id,
        "created_at":   ref.created_at.isoformat(),
        "image_url":    f"/library/image/{ref.id}",
    }


# ── Serve a reference image by ID ─────────────────────────────────────────────
@router.get("/image/{ref_id}")
def get_reference_image(
    ref_id:       int,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    from fastapi.responses import FileResponse
    ref = db.query(ProductReference).filter(ProductReference.id == ref_id).first()
    if not ref or not os.path.exists(ref.image_path):
        raise HTTPException(status_code=404, detail="Image not found.")
    return FileResponse(ref.image_path, media_type="image/jpeg")


# ── List all references (grouped by product name) ────────────────────────────
@router.get("/references")
def list_references(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    refs = db.query(ProductReference).order_by(ProductReference.product_name).all()
    grouped: dict[str, list] = {}
    for r in refs:
        key = r.product_name
        if key not in grouped:
            grouped[key] = []
        grouped[key].append({
            "id":         r.id,
            "product_id": r.product_id,
            "image_url":  f"/library/image/{r.id}",
            "created_at": r.created_at.isoformat(),
        })
    return [
        {"product_name": name, "refs": items}
        for name, items in grouped.items()
    ]


# ── Unique product names with ref counts ─────────────────────────────────────
@router.get("/products")
def list_library_products(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    from sqlalchemy import func
    rows = (
        db.query(ProductReference.product_name, func.count(ProductReference.id).label("ref_count"))
        .group_by(ProductReference.product_name)
        .order_by(func.count(ProductReference.id).desc())
        .all()
    )
    return [{"product_name": r.product_name, "ref_count": r.ref_count} for r in rows]


# ── Delete a reference ────────────────────────────────────────────────────────
@router.delete("/references/{ref_id}")
def delete_reference(
    ref_id:       int,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    ref = db.query(ProductReference).filter(ProductReference.id == ref_id).first()
    if not ref:
        raise HTTPException(status_code=404, detail="Reference not found.")
    # Remove image file
    try:
        if os.path.exists(ref.image_path):
            os.remove(ref.image_path)
    except Exception:
        pass
    db.delete(ref)
    db.commit()
    return {"deleted": ref_id}


# ── Stats ─────────────────────────────────────────────────────────────────────
@router.get("/stats")
def library_stats(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    from sqlalchemy import func
    total_refs     = db.query(func.count(ProductReference.id)).scalar()
    unique_products = db.query(func.count(func.distinct(ProductReference.product_name))).scalar()
    return {
        "total_references":  total_refs,
        "unique_products":   unique_products,
        "clip_ready":        _clip_status(),
    }

def _clip_status() -> str:
    try:
        from vision_pipeline import _clip_ready, _clip_error
        if _clip_ready:
            return "ready"
        if _clip_error:
            return f"error: {_clip_error}"
        return "not_loaded"
    except Exception:
        return "unknown"
