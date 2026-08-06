"""
Planogram router — CRUD, CSV import, and compliance checking.

Endpoints:
  GET    /planogram/            — list entries (filter by shelf_id)
  POST   /planogram/            — create a single entry
  PUT    /planogram/{id}        — update an entry
  DELETE /planogram/{id}        — delete an entry
  GET    /planogram/shelves     — list unique shelf IDs
  POST   /planogram/import-csv  — bulk import from uploaded CSV
  POST   /planogram/check       — compliance check given detected products + grid positions
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from database import get_db, Planogram
from security import get_current_user, User
from pydantic import BaseModel
from typing import Optional
import csv
import io
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/planogram", tags=["planogram"])


# ── Pydantic schemas ──────────────────────────────────────────────

class PlanogramEntry(BaseModel):
    store_id:        str = "default"
    shelf_id:        str
    shelf_name:      Optional[str] = ""
    row:             int
    col:             int
    product_name:    str
    brand:           Optional[str] = ""
    sku:             Optional[str] = ""
    category:        Optional[str] = ""
    facings:         int = 1
    depth:           int = 1   # units stacked back-to-front per shelf position
    unit_price_usd:  float = 0.0
    planogram_notes: Optional[str] = ""


class ComplianceItem(BaseModel):
    """One detected+identified product with its grid position."""
    row:             int
    col:             int
    shelf_id:        str
    matched_product: Optional[str] = None   # None = unidentified
    confidence:      Optional[float] = None


class ComplianceRequest(BaseModel):
    items: list[ComplianceItem]


# ── Helper ────────────────────────────────────────────────────────

def _row_to_dict(r: Planogram) -> dict:
    return {
        "id":             r.id,
        "store_id":       r.store_id,
        "shelf_id":       r.shelf_id,
        "shelf_name":     r.shelf_name,
        "row":            r.row,
        "col":            r.col,
        "product_name":   r.product_name,
        "brand":          r.brand,
        "sku":            r.sku,
        "category":       r.category,
        "facings":        r.facings,
        "depth":          r.depth if r.depth is not None else 1,
        "unit_price_usd": r.unit_price_usd,
        "planogram_notes":r.planogram_notes,
        "created_at":     r.created_at.isoformat() if r.created_at else None,
    }


# ── List entries ──────────────────────────────────────────────────

@router.get("/")
def list_planogram(
    shelf_id: Optional[str] = Query(None),
    store_id: str           = Query("default"),
    db: Session             = Depends(get_db),
    current_user: User      = Depends(get_current_user),
):
    q = db.query(Planogram).filter(Planogram.store_id == store_id)
    if shelf_id:
        q = q.filter(Planogram.shelf_id == shelf_id)
    rows = q.order_by(Planogram.shelf_id, Planogram.row, Planogram.col).all()
    return {"count": len(rows), "entries": [_row_to_dict(r) for r in rows]}


# ── Unique shelf IDs ──────────────────────────────────────────────

@router.get("/shelves")
def list_shelves(
    store_id: str      = Query("default"),
    db: Session        = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(Planogram.shelf_id, Planogram.shelf_name)
        .filter(Planogram.store_id == store_id)
        .distinct()
        .all()
    )
    shelves = [{"shelf_id": r[0], "shelf_name": r[1]} for r in rows]
    return {"shelves": shelves}


# ── Create single entry ───────────────────────────────────────────

@router.post("/")
def create_entry(
    payload:       PlanogramEntry,
    db:            Session = Depends(get_db),
    current_user:  User    = Depends(get_current_user),
):
    entry = Planogram(**payload.dict())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"status": "created", "entry": _row_to_dict(entry)}


# ── Update entry ──────────────────────────────────────────────────

@router.put("/{entry_id}")
def update_entry(
    entry_id:      int,
    payload:       PlanogramEntry,
    db:            Session = Depends(get_db),
    current_user:  User    = Depends(get_current_user),
):
    entry = db.query(Planogram).filter(Planogram.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    for k, v in payload.dict().items():
        setattr(entry, k, v)
    db.commit()
    db.refresh(entry)
    return {"status": "updated", "entry": _row_to_dict(entry)}


# ── Delete entry ──────────────────────────────────────────────────

@router.delete("/{entry_id}")
def delete_entry(
    entry_id:      int,
    db:            Session = Depends(get_db),
    current_user:  User    = Depends(get_current_user),
):
    entry = db.query(Planogram).filter(Planogram.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()
    return {"status": "deleted", "id": entry_id}


# ── CSV import ────────────────────────────────────────────────────

@router.post("/import-csv")
async def import_csv(
    file:          UploadFile    = File(...),
    store_id:      str           = Query("default"),
    replace_shelf: Optional[str] = Query(None, description="Delete existing rows for this shelf_id before import"),
    db:            Session       = Depends(get_db),
    current_user:  User          = Depends(get_current_user),
):
    """
    Upload a CSV with columns:
      shelf_id, shelf_name, row, col, product_name, brand, sku,
      category, facings, unit_price_usd, planogram_notes

    If replace_shelf is set (e.g. 'SHELF-A1'), all existing rows for that
    shelf are deleted before import. Use replace_shelf=ALL to wipe all shelves.
    """
    contents = await file.read()
    text     = contents.decode("utf-8-sig")  # handle BOM from Excel CSV export
    reader   = csv.DictReader(io.StringIO(text))

    required = {"shelf_id", "row", "col", "product_name"}
    if reader.fieldnames:
        missing = required - set(reader.fieldnames)
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"CSV missing required columns: {missing}"
            )

    # Optional: clear existing rows
    if replace_shelf:
        if replace_shelf.upper() == "ALL":
            db.query(Planogram).filter(Planogram.store_id == store_id).delete()
        else:
            db.query(Planogram).filter(
                Planogram.store_id == store_id,
                Planogram.shelf_id == replace_shelf
            ).delete()

    inserted = 0
    errors   = []
    for line_num, row in enumerate(reader, start=2):
        try:
            entry = Planogram(
                store_id        = store_id,
                shelf_id        = row.get("shelf_id", "").strip(),
                shelf_name      = row.get("shelf_name", "").strip(),
                row             = int(row.get("row", 0)),
                col             = int(row.get("col", 0)),
                product_name    = row.get("product_name", "").strip(),
                brand           = row.get("brand", "").strip(),
                sku             = row.get("sku", "").strip(),
                category        = row.get("category", "").strip(),
                facings         = int(row.get("facings", 1) or 1),
                depth           = int(row.get("depth", 1) or 1),
                unit_price_usd  = float(row.get("unit_price_usd", 0) or 0),
                planogram_notes = row.get("planogram_notes", "").strip(),
            )
            db.add(entry)
            inserted += 1
        except Exception as e:
            errors.append(f"Line {line_num}: {e}")

    db.commit()
    logger.info(f"Planogram CSV import: {inserted} rows, {len(errors)} errors")
    return {
        "status":   "ok",
        "inserted": inserted,
        "errors":   errors,
    }


# ── Compliance check ──────────────────────────────────────────────

@router.post("/check")
def check_compliance(
    payload:       ComplianceRequest,
    store_id:      str    = Query("default"),
    db:            Session = Depends(get_db),
    current_user:  User    = Depends(get_current_user),
):
    """
    Given a list of detected+identified products with grid positions,
    compare each against the planogram and return a compliance status.

    Status values:
      ok            — detected product matches planogram expectation
      mismatch      — wrong product in this slot
      unidentified  — product detected but no name available
      no_planogram  — position not in planogram data

    Also returns out_of_stock entries: planogram positions with no detection.
    """
    results = []
    detected_positions = set()

    for item in payload.items:
        key = (item.shelf_id, item.row, item.col)
        detected_positions.add(key)

        pog = (
            db.query(Planogram)
            .filter(
                Planogram.store_id == store_id,
                Planogram.shelf_id == item.shelf_id,
                Planogram.row      == item.row,
                Planogram.col      == item.col,
            )
            .first()
        )

        if pog is None:
            status = "no_planogram"
            expected = None
        elif not item.matched_product:
            status = "unidentified"
            expected = pog.product_name
        else:
            # Substring match (case-insensitive) — tolerates minor name differences
            detected_lower = item.matched_product.lower()
            expected_lower = pog.product_name.lower()
            # Match if either name contains the other's brand/key word
            words_match = any(
                w in detected_lower
                for w in expected_lower.split()
                if len(w) > 3
            )
            status   = "ok" if words_match else "mismatch"
            expected = pog.product_name

        results.append({
            "shelf_id":        item.shelf_id,
            "row":             item.row,
            "col":             item.col,
            "detected":        item.matched_product,
            "expected":        expected,
            "status":          status,
            "confidence":      item.confidence,
        })

    # ── Out-of-stock: planogram positions with no detection ───────
    all_pog_rows = (
        db.query(Planogram)
        .filter(Planogram.store_id == store_id)
        .all()
    )
    oos = []
    for pog in all_pog_rows:
        key = (pog.shelf_id, pog.row, pog.col)
        if key not in detected_positions:
            # Only report OOS for shelves that appear in the detections
            shelves_detected = {k[0] for k in detected_positions}
            if pog.shelf_id in shelves_detected:
                oos.append({
                    "shelf_id":     pog.shelf_id,
                    "row":          pog.row,
                    "col":          pog.col,
                    "expected":     pog.product_name,
                    "status":       "out_of_stock",
                })

    # Summary stats
    total   = len(results)
    ok      = sum(1 for r in results if r["status"] == "ok")
    compliance_rate = round(ok / total * 100, 1) if total else 0

    return {
        "compliance_rate": compliance_rate,
        "total_checked":   total,
        "ok":              ok,
        "mismatch":        sum(1 for r in results if r["status"] == "mismatch"),
        "unidentified":    sum(1 for r in results if r["status"] == "unidentified"),
        "no_planogram":    sum(1 for r in results if r["status"] == "no_planogram"),
        "out_of_stock":    len(oos),
        "results":         results,
        "oos_items":       oos,
    }
