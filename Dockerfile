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

# Download custom trained YOLOv8 model from HF Model Hub at build time
# Set HF_MODEL_REPO build arg to your model repo, e.g. sivakanthece/retail-ai-yolo
ARG HF_MODEL_REPO=sivakanthece/retail-ai-yolo
ARG HF_TOKEN
RUN pip install huggingface_hub --quiet && \
    python -c "\
from huggingface_hub import hf_hub_download; \
import os, shutil; \
token = os.environ.get('HF_TOKEN') or None; \
path = hf_hub_download(repo_id='${HF_MODEL_REPO}', filename='best.pt', token=token); \
shutil.copy(path, '/app/backend/best.pt'); \
print('best.pt downloaded OK')" || \
    python -c "from ultralytics import YOLO; YOLO('yolov8n.pt'); print('Fallback: yolov8n.pt cached OK')"

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
