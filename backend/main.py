from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from database import init_db
from routers import auth, detection, inventory, nlq, analytics, library
import os

FRONTEND_BUILD = os.path.join(os.path.dirname(__file__), "..", "frontend", "build")

def _warmup_models():
    """Download and pre-load models at startup so the first request is instant."""
    import os, logging
    logger = logging.getLogger("startup")

    # ── Download best.pt from HF Model Hub if not on disk ────────────────────
    from config import settings
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    model_name  = settings.YOLO_MODEL          # reads from .env correctly
    model_path  = os.path.join(backend_dir, model_name)
    hf_token    = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN", "")
    hf_repo     = os.environ.get("HF_MODEL_REPO", "sivakanthece/retail-ai-yolo")

    if not os.path.exists(model_path) and model_name != "yolov8n.pt" and hf_token:
        try:
            from huggingface_hub import hf_hub_download
            import shutil
            logger.info(f"Downloading {model_name} from {hf_repo} ...")
            downloaded = hf_hub_download(repo_id=hf_repo, filename=model_name, token=hf_token)
            shutil.copy2(downloaded, model_path)
            logger.info(f"Model downloaded: {model_path} ({os.path.getsize(model_path)//1024//1024} MB)")
        except Exception as e:
            logger.warning(f"Could not download {model_name}: {e} — will use yolov8n.pt")

    # ── Pre-load YOLO so first detection request is instant ──────────────────
    try:
        from routers.detection import get_model
        get_model()
        logger.info("YOLO model pre-loaded OK")
    except Exception as e:
        logger.warning(f"YOLO pre-load failed: {e}")

    # ── Pre-load CLIP so first pipeline request is instant ───────────────────
    try:
        import vision_pipeline as vp
        vp._load_clip()
        logger.info(f"CLIP pre-loaded OK: {vp._clip_ready}")
    except Exception as e:
        logger.warning(f"CLIP pre-load failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Run model warmup in a background thread so it doesn't block app startup
    import asyncio
    await asyncio.to_thread(_warmup_models)
    yield

app = FastAPI(
    title="Retail AI Inventory System",
    description="Intelligent product detection and inventory management using Computer Vision and LLM",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # open for HF Spaces; tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(detection.router)
app.include_router(inventory.router)
app.include_router(nlq.router)
app.include_router(analytics.router)
app.include_router(library.router)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/debug/yolo")
def debug_yolo():
    """Check which YOLO model is loaded and attempt download if missing."""
    import os
    from config import settings
    backend_dir  = os.path.dirname(os.path.abspath(__file__))
    best_path    = os.path.join(backend_dir, "best.pt")
    hf_token     = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN", "")
    hf_repo      = os.environ.get("HF_MODEL_REPO", "sivakanthece/retail-ai-yolo")

    result = {
        "YOLO_MODEL_setting": settings.YOLO_MODEL,
        "backend_dir":        backend_dir,
        "best_pt_exists":     os.path.exists(best_path),
        "HF_TOKEN_set":       bool(hf_token),
        "HF_MODEL_REPO":      hf_repo,
        "download_error":     None,
        "download_success":   False,
    }

    if not os.path.exists(best_path) and hf_token:
        try:
            from huggingface_hub import hf_hub_download
            import shutil
            downloaded = hf_hub_download(
                repo_id=hf_repo,
                filename="best.pt",
                token=hf_token,
            )
            shutil.copy2(downloaded, best_path)
            result["download_success"] = True
            result["best_pt_exists"]   = os.path.exists(best_path)
            result["best_pt_size_mb"]  = round(os.path.getsize(best_path) / 1024 / 1024, 1)
        except Exception as e:
            result["download_error"] = str(e)

    if os.path.exists(best_path):
        result["best_pt_size_mb"] = round(os.path.getsize(best_path) / 1024 / 1024, 1)

    result["status"] = "ready" if os.path.exists(best_path) else "failed"
    return result

@app.get("/debug/clip")
def debug_clip():
    """
    Diagnostic endpoint — open in browser: http://localhost:8000/debug/clip
    Shows whether CLIP loaded, any error, and runs a quick test classification.
    """
    import vision_pipeline as vp
    result = {
        "clip_ready": vp._clip_ready,
        "clip_error": str(vp._clip_error) if vp._clip_error else None,
    }

    # Try to force-load CLIP now
    loaded = vp._load_clip()
    result["load_attempt"] = "success" if loaded else "failed"
    result["clip_error_after_load"] = str(vp._clip_error) if vp._clip_error else None

    if loaded:
        # Quick test: classify a synthetic red image
        from PIL import Image as PILImage
        test_img = PILImage.new("RGB", (224, 224), color=(220, 50, 50))
        cats = vp.classify_categories_batch([test_img])
        result["test_classification"] = {"category": cats[0][0], "confidence": cats[0][1]}
        result["message"] = "CLIP is working correctly"
    else:
        result["message"] = (
            "CLIP failed to load. Most likely causes:\n"
            "1. transformers not installed: pip install transformers>=4.40.0\n"
            "2. No internet to download model weights (~340 MB from HuggingFace)\n"
            "3. Not enough memory (CLIP needs ~600 MB RAM)\n"
            "Check the server terminal for the full traceback."
        )
    return result

# ── Serve React SPA (only when build folder is present) ──────────
if os.path.exists(os.path.join(FRONTEND_BUILD, "static")):
    # Static assets (JS / CSS / images generated by react-scripts build)
    app.mount(
        "/static",
        StaticFiles(directory=os.path.join(FRONTEND_BUILD, "static")),
        name="static",
    )

    # Any path not matched by an API router → serve index.html (client-side routing)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        index = os.path.join(FRONTEND_BUILD, "index.html")
        return FileResponse(index)
else:
    @app.get("/")
    def root():
        return {"message": "Retail AI System API", "docs": "/docs"}
