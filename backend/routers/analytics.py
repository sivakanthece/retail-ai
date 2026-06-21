from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db, Product, DetectionEvent, Alert, User
from security import get_current_user
from datetime import datetime, timedelta

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/dashboard")
def dashboard_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    products = db.query(Product).all()
    total_products  = len(products)
    total_quantity  = sum(p.inventory.quantity for p in products if p.inventory)
    low_stock       = [p for p in products if p.inventory and 0 < p.inventory.quantity < p.low_stock_threshold]
    out_of_stock    = [p for p in products if p.inventory and p.inventory.quantity == 0]

    # ── Category breakdown ─────────────────────────────────────
    category_data = {}
    for p in products:
        cat = p.category or "General"
        qty = p.inventory.quantity if p.inventory else 0
        if cat not in category_data:
            category_data[cat] = {"category": cat, "quantity": 0, "products": 0}
        category_data[cat]["quantity"] += qty
        category_data[cat]["products"] += 1

    category_chart = sorted(
        category_data.values(),
        key=lambda x: x["products"],
        reverse=True,
    )

    # ── Daily detections — last 14 days, every day filled in ──
    today        = datetime.utcnow().date()
    two_weeks_ago = datetime.utcnow() - timedelta(days=13)
    events = db.query(DetectionEvent).filter(
        DetectionEvent.detected_at >= two_weeks_ago
    ).all()

    # Aggregate by day
    day_counts: dict[str, dict] = {}
    for e in events:
        day  = e.detected_at.strftime("%Y-%m-%d")
        label = e.detected_at.strftime("%b %d")
        if day not in day_counts:
            day_counts[day] = {"date": label, "items": 0, "scans": 0}
        day_counts[day]["items"]  += e.total_items_detected
        day_counts[day]["scans"]  += 1

    # Fill every day in the range with 0 if no events
    daily_chart = []
    for offset in range(13, -1, -1):
        d     = today - timedelta(days=offset)
        key   = d.strftime("%Y-%m-%d")
        label = d.strftime("%b %d")
        if key in day_counts:
            daily_chart.append(day_counts[key])
        else:
            daily_chart.append({"date": label, "items": 0, "scans": 0})

    # ── Alerts ────────────────────────────────────────────────
    unread_alerts = db.query(Alert).filter(Alert.is_read == 0).count()

    # ── Recent detection events ────────────────────────────────
    recent_events = (
        db.query(DetectionEvent)
        .order_by(DetectionEvent.detected_at.desc())
        .limit(5)
        .all()
    )

    return {
        "total_products":    total_products,
        "total_quantity":    total_quantity,
        "low_stock_count":   len(low_stock),
        "out_of_stock_count": len(out_of_stock),
        "unread_alerts":     unread_alerts,
        "category_chart":    category_chart,
        "daily_detections_chart": daily_chart,
        "low_stock_products": [
            {
                "sku":       p.sku,
                "name":      p.name,
                "quantity":  p.inventory.quantity,
                "threshold": p.low_stock_threshold,
            }
            for p in low_stock
        ],
        "recent_scans": [
            {
                "id":           e.id,
                "detected_at":  e.detected_at.strftime("%b %d, %H:%M"),
                "total_items":  e.total_items_detected,
            }
            for e in recent_events
        ],
    }
