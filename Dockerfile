# ── Stage 1: Build React frontend ────────────────────────────────
FROM node:20-slim AS frontend-builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm install --silent
COPY frontend/ ./
# Disable CI mode so build warnings don't abort the build
ENV CI=false
RUN npm run build

# ── Stage 2: Python backend + static file serving ────────────────
FROM python:3.11-slim
WORKDIR /app

# System libraries required by OpenCV / Pillow / ultralytics
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 libsm6 libxext6 libxrender-dev \
        libgomp1 libgl1 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Pre-download model weights at build time ──────────────────────
# CLIP ViT-B/32 (~340 MB) — baked into image so there's no runtime download
RUN python -c "\
from transformers import CLIPModel, CLIPProcessor; \
CLIPModel.from_pretrained('openai/clip-vit-base-patch32'); \
CLIPProcessor.from_pretrained('openai/clip-vit-base-patch32'); \
print('CLIP cached OK')"

# YOLOv8n base weights (~6 MB) — fallback if best.pt is not provided
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt'); print('YOLOv8n cached OK')"

# Backend source
COPY backend/ ./backend/

# React build output (served as static files by FastAPI)
COPY --from=frontend-builder /app/build ./frontend/build

# ── Custom trained models (optional) ─────────────────────────────
# Place your trained best.pt in backend/ before running docker build.
# The app uses best.pt if present, otherwise falls back to yolov8n.pt.
#
# For a fine-tuned CLIP (Stage 3 improvement — see note below):
# Place clip_retail.pt in backend/ — vision_pipeline.py will load it automatically.

# Hugging Face Spaces requires port 7860
EXPOSE 7860

WORKDIR /app/backend

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
