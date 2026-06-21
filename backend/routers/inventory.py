from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from database import get_db, Product, Inventory, Alert, User
from security import get_current_user, require_role, UserRole
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/inventory", tags=["inventory"])

class InventoryUpdate(BaseModel):
    quantity: int
    shelf_location: Optional[str] = None

class ProductCreate(BaseModel):
    sku: str
    name: str
    category: str
    low_stock_threshold: int = 10
    initial_quantity: int = 0
    shelf_location: str = ""

@router.get("/")
def list_inventory(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    products = db.query(Product).options(joinedload(Product.inventory)).all()
    result = []
    for p in products:
        qty = p.inventory.quantity if p.inventory else 0
        result.append({
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
            "category": p.category,
            "quantity": qty,
            "shelf_location": p.inventory.shelf_location if p.inventory else "",
            "low_stock_threshold": p.low_stock_threshold,
            "is_low_stock": qty < p.low_stock_threshold,
            "last_updated": p.inventory.last_updated.isoformat() if p.inventory and p.inventory.last_updated else None,
        })
    return result

@router.get("/summary")
def inventory_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    products = db.query(Product).options(joinedload(Product.inventory)).all()
    total = len(products)
    low_stock = sum(1 for p in products if p.inventory and p.inventory.quantity < p.low_stock_threshold)
    out_of_stock = sum(1 for p in products if p.inventory and p.inventory.quantity == 0)
    categories = {}
    for p in products:
        cat = p.category
        qty = p.inventory.quantity if p.inventory else 0
        if cat not in categories:
            categories[cat] = {"category": cat, "total_items": 0, "total_quantity": 0}
        categories[cat]["total_items"] += 1
        categories[cat]["total_quantity"] += qty
    return {
        "total_products": total,
        "low_stock_count": low_stock,
        "out_of_stock_count": out_of_stock,
        "category_breakdown": list(categories.values()),
    }

@router.put("/{product_id}")
def update_inventory(
    product_id: int,
    update: InventoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.inventory:
        inv = Inventory(product_id=product_id, quantity=update.quantity, shelf_location=update.shelf_location or "")
        db.add(inv)
    else:
        product.inventory.quantity = update.quantity
        if update.shelf_location:
            product.inventory.shelf_location = update.shelf_location
        product.inventory.last_updated = datetime.utcnow()
    db.commit()
    return {"message": "Inventory updated", "product_id": product_id, "quantity": update.quantity}

@router.post("/products")
def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.manager)),
):
    existing = db.query(Product).filter(Product.sku == product.sku).first()
    if existing:
        raise HTTPException(status_code=400, detail="SKU already exists")
    new_product = Product(sku=product.sku, name=product.name, category=product.category, low_stock_threshold=product.low_stock_threshold)
    db.add(new_product)
    db.flush()
    inv = Inventory(product_id=new_product.id, quantity=product.initial_quantity, shelf_location=product.shelf_location)
    db.add(inv)
    db.commit()
    return {"message": "Product created", "id": new_product.id}

@router.get("/alerts")
def get_alerts(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Alert)
    if unread_only:
        query = query.filter(Alert.is_read == 0)
    alerts = query.order_by(Alert.created_at.desc()).limit(50).all()
    return [
        {
            "id": a.id,
            "product_id": a.product_id,
            "alert_type": a.alert_type,
            "message": a.message,
            "is_read": bool(a.is_read),
            "created_at": a.created_at.isoformat(),
        }
        for a in alerts
    ]

@router.put("/alerts/{alert_id}/read")
def mark_alert_read(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_read = 1
    db.commit()
    return {"message": "Alert marked as read"}
