from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Enum, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import enum
from datetime import datetime
from config import settings

# SQLite needs check_same_thread=False; PostgreSQL needs pool settings
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Redis is optional — gracefully disabled when not available
redis_client = None
try:
    import redis as _redis
    _r = _redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)
    _r.ping()
    redis_client = _r
except Exception:
    pass  # Redis unavailable — caching simply disabled

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ── ORM Models ──────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    admin = "admin"
    manager = "manager"
    analyst = "analyst"
    viewer = "viewer"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.viewer)
    created_at = Column(DateTime, default=datetime.utcnow)

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    category = Column(String)
    low_stock_threshold = Column(Integer, default=10)
    inventory = relationship("Inventory", back_populates="product", uselist=False)

class Inventory(Base):
    __tablename__ = "inventory"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer, default=0)
    shelf_location = Column(String)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    product = relationship("Product", back_populates="inventory")

class DetectionEvent(Base):
    __tablename__ = "detection_events"
    id = Column(Integer, primary_key=True, index=True)
    image_path = Column(String)
    detected_at = Column(DateTime, default=datetime.utcnow)
    total_items_detected = Column(Integer, default=0)
    results_json = Column(String)  # JSON string of detections

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    alert_type = Column(String, default="low_stock")
    message = Column(String)
    is_read = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class ProductReference(Base):
    """
    Stage 3 product library.
    Each row = one reference image for a product + its CLIP embedding.
    Multiple rows per product → better matching via max-similarity aggregation.
    """
    __tablename__ = "product_references"
    id           = Column(Integer, primary_key=True, index=True)
    product_name = Column(String, nullable=False, index=True)   # human-readable name
    product_id   = Column(Integer, ForeignKey("products.id"), nullable=True)  # optional link
    image_path   = Column(String, nullable=False)               # saved crop file path
    embedding    = Column(Text,   nullable=False)               # JSON list of 512 floats
    created_at   = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)
    # Seed demo data
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            from security import get_password_hash
            users = [
                User(username="admin", hashed_password=get_password_hash("admin123"), role=UserRole.admin),
                User(username="manager", hashed_password=get_password_hash("manager123"), role=UserRole.manager),
                User(username="analyst", hashed_password=get_password_hash("analyst123"), role=UserRole.analyst),
            ]
            db.add_all(users)

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Seed error: {e}")
    finally:
        db.close()
