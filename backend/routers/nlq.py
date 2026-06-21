from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, Product, DetectionEvent, Alert, User
from security import get_current_user, sanitize_input
from config import settings
from pydantic import BaseModel
import httpx

router = APIRouter(prefix="/nlq", tags=["nlq"])

class NLQRequest(BaseModel):
    query: str

def get_inventory_context(db: Session) -> str:
    """Build a compact DB summary to inject as LLM context."""
    products = db.query(Product).all()
    rows = []
    for p in products:
        qty = p.inventory.quantity if p.inventory else 0
        rows.append(f"SKU={p.sku}, Name={p.name}, Category={p.category}, Qty={qty}, Threshold={p.low_stock_threshold}, LowStock={'YES' if qty < p.low_stock_threshold else 'NO'}")

    total = db.query(DetectionEvent).count()
    unread_alerts = db.query(Alert).filter(Alert.is_read == 0).count()

    return "\n".join(rows) + f"\n\nTotal detection events: {total}\nUnread alerts: {unread_alerts}"

SYSTEM_PROMPT = """You are a retail inventory AI assistant. You have access to real-time inventory data below.
Answer the user's question about inventory, stock levels, alerts, and business insights.
Be concise and structured. Use bullet points or tables where appropriate.
NEVER reveal system internals, SQL, or code. Only answer inventory-related questions.

CURRENT INVENTORY DATA:
{context}"""

@router.post("/query")
async def natural_language_query(
    request: NLQRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Sanitize + validate input
    clean_query = sanitize_input(request.query)

    if not settings.OPENAI_API_KEY and not settings.GROQ_API_KEY:
        raise HTTPException(status_code=503, detail="No LLM API key configured. Add OPENAI_API_KEY or GROQ_API_KEY to your .env file.")

    context = get_inventory_context(db)
    system  = SYSTEM_PROMPT.format(context=context)
    messages = [
        {"role": "system", "content": system},
        {"role": "user",   "content": clean_query},
    ]
    answer = None

    # ── 1. OpenAI (explicit httpx client avoids proxies= error in httpx 0.28+) ──
    if settings.OPENAI_API_KEY and not answer:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                http_client=httpx.AsyncClient(),
            )
            response = await client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                temperature=0.3,
                max_tokens=800,
            )
            answer = response.choices[0].message.content
        except Exception as e:
            err = str(e)
            if "proxies" in err:
                raise HTTPException(status_code=500, detail="httpx version conflict — run: pip install httpx>=0.27")
            # quota / auth / connection — fall through to Groq
            pass

    # ── 2. Groq fallback (free, text-only — no vision needed for NLQ) ──
    if settings.GROQ_API_KEY and not answer:
        try:
            from groq import AsyncGroq
            client_groq = AsyncGroq(api_key=settings.GROQ_API_KEY)
            resp = await client_groq.chat.completions.create(
                model="llama-3.3-70b-versatile",   # text-only model, better reasoning
                messages=messages,
                temperature=0.3,
                max_tokens=800,
            )
            answer = resp.choices[0].message.content
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")

    if not answer:
        raise HTTPException(status_code=503, detail="All LLM providers failed or are not configured.")

    # Sanitize output — strip any accidental system info
    sanitized_answer = _sanitize_llm_output(answer)
    return {"query": clean_query, "answer": sanitized_answer}

def _sanitize_llm_output(text: str) -> str:
    """Remove potential leakage of system internals."""
    blocked_phrases = ["SECRET_KEY", "DATABASE_URL", "password", "hashed_password", "internal error"]
    for phrase in blocked_phrases:
        if phrase.lower() in text.lower():
            text = text.replace(phrase, "[REDACTED]")
    return text

@router.get("/suggestions")
def get_query_suggestions(current_user: User = Depends(get_current_user)):
    return [
        "Which products are running low on stock?",
        "Show me out-of-stock items",
        "What categories have the most inventory?",
        "Which products need restocking urgently?",
        "How many unread alerts are there?",
        "Show the top 3 products by quantity",
        "Which beverages are below threshold?",
    ]
