from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./retail.db"   # override with postgres:// if available
    REDIS_URL: str = "redis://localhost:6379"      # optional — app works without Redis
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    SECRET_KEY: str = "change-me-in-production-use-a-long-random-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    # Pre-trained baseline: yolov8n.pt
    # After Colab training: set to path of downloaded best.pt
    # e.g. YOLO_MODEL=best.pt  (copy best.pt into the backend/ folder)
    YOLO_MODEL: str = "yolov8n.pt"
    MAX_UPLOAD_SIZE_MB: int = 20
    GOOGLE_API_KEY: str = ""   # Free at aistudio.google.com/app/apikey
    GROQ_API_KEY: str = ""     # Free at console.groq.com/keys

    class Config:
        env_file = ".env"

settings = Settings()
