"""
Run this script to manually seed the database with demo users and products.
Usage:  python reseed.py
"""
from database import Base, engine, SessionLocal, User, Product, Inventory, UserRole
from security import get_password_hash
from datetime import datetime

def reseed():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Clear existing users and products to avoid duplicates
        db.query(Inventory).delete()
        db.query(Product).delete()
        db.query(User).delete()
        db.commit()
        print("Cleared existing data.")

        # Seed users
        users = [
            User(username="admin",   hashed_password=get_password_hash("admin123"),   role=UserRole.admin),
            User(username="manager", hashed_password=get_password_hash("manager123"), role=UserRole.manager),
            User(username="analyst", hashed_password=get_password_hash("analyst123"), role=UserRole.analyst),
        ]
        db.add_all(users)
        db.flush()
        print(f"Inserted {len(users)} users.")

        # Seed products
        products = [
            Product(sku="SKU-001", name="Coca-Cola 330ml",    category="Beverages",     low_stock_threshold=15),
            Product(sku="SKU-002", name="Pepsi 500ml",        category="Beverages",     low_stock_threshold=12),
            Product(sku="SKU-003", name="Lays Classic Chips", category="Snacks",        low_stock_threshold=20),
            Product(sku="SKU-004", name="Doritos Nacho",      category="Snacks",        low_stock_threshold=18),
            Product(sku="SKU-005", name="Oreo Cookies",       category="Biscuits",      low_stock_threshold=10),
            Product(sku="SKU-006", name="Kit Kat",            category="Chocolate",     low_stock_threshold=25),
            Product(sku="SKU-007", name="Maggi Noodles",      category="Instant Food",  low_stock_threshold=30),
            Product(sku="SKU-008", name="Colgate Toothpaste", category="Personal Care", low_stock_threshold=8),
        ]
        db.add_all(products)
        db.flush()

        # Seed inventory
        quantities = [45, 8, 22, 5, 60, 12, 3, 35]
        locations  = ["A1","A2","B1","B2","C1","C2","D1","D2"]
        for product, qty, loc in zip(products, quantities, locations):
            db.add(Inventory(product_id=product.id, quantity=qty,
                             shelf_location=loc, last_updated=datetime.utcnow()))
        db.commit()
        print(f"Inserted {len(products)} products with inventory.")

        print("\n--- Seed complete. Login credentials ---")
        print("  admin    / admin123   (role: admin)")
        print("  manager  / manager123 (role: manager)")
        print("  analyst  / analyst123 (role: analyst)")

    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    reseed()
