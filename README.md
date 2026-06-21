---
title: Retail AI Inventory System
emoji: 🛒
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
app_port: 7860
---

# Retail AI — Intelligent Inventory Management System

AI-powered shelf product detection and inventory management.

- Upload shelf images → YOLOv8 detects all products
- AI (GPT-4o / Gemini / Groq) identifies product names and brands in batches of 10
- Groups identical products, add to inventory with one click
- Dashboard with stock levels, alerts, and analytics

## Deploy to Hugging Face Spaces

### 1. Create a new Space

1. Go to [huggingface.co/new-space](https://huggingface.co/new-space)
2. Choose **Docker** as the SDK
3. Set visibility to Public or Private

### 2. Push this repository

```bash
# Clone your new Space repo
git clone https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME
cd YOUR_SPACE_NAME

# Copy all project files in
cp -r /path/to/retail-ai/. .

# If you have a trained model, copy it in
cp /path/to/best.pt backend/best.pt

# Commit and push — HF will build automatically
git add .
git commit -m "Initial deploy"
git push
```

> **Model file > 50 MB?** Use Git LFS:
> ```bash
> git lfs install
> git lfs track "*.pt"
> git add .gitattributes && git commit -m "Track .pt with LFS"
> ```

### 3. Add Secrets

In your Space → **Settings → Variables and Secrets**, add:

| Secret | Value |
|--------|-------|
| `GROQ_API_KEY` | Free at [console.groq.com](https://console.groq.com/keys) |
| `OPENAI_API_KEY` | Optional — GPT-4o (paid) |
| `GOOGLE_API_KEY` | Optional — Gemini free tier |
| `SECRET_KEY` | Any long random string (for JWT signing) |
| `YOLO_MODEL` | `best.pt` or `yolov8n.pt` (base model) |

At least one LLM key is required for product identification.  
Groq is free and works well — start there.

### 4. Wait for build (~5–10 min)

HF Spaces builds the Docker image automatically on every push.  
Your app will be live at:  
`https://YOUR_USERNAME-YOUR_SPACE_NAME.hf.space`

## Default login credentials

| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | Admin |
| manager | manager123 | Manager |
| analyst | analyst123 | Analyst |

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Recharts, Axios |
| Backend | FastAPI, SQLAlchemy, Uvicorn |
| Detection | YOLOv8 (ultralytics) |
| Database | SQLite (default) · PostgreSQL (set `DATABASE_URL`) |
| Vision AI | GPT-4o → Gemini → Groq (automatic fallback) |
| Auth | JWT (python-jose, passlib) |
