
from pathlib import Path
import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from agent import (
    answer_sales_question,
    answer_real_sales_question,
)

from sales_service import (
    get_sales_overview,
    get_trend,
    compare_months,
    get_available_months,
)

from sql_reporting import get_real_sales_summary


# ==========================================
# CONFIGURATION
# ==========================================

BASE_DIR = Path(__file__).resolve().parent

logger = logging.getLogger("victoria-api")

app = FastAPI(
    title="Victoria Sales Agent MVP",
    version="1.2",
)


# ==========================================
# REQUEST AND RESPONSE MODELS
# ==========================================

class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(
        min_length=1,
        max_length=2000,
    )


class ChatResponse(BaseModel):
    answer: str
    mode: str = "sample_database"


# ==========================================
# FRONTEND
# ==========================================

@app.get("/", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
def index():
    return FileResponse(BASE_DIR / "index.html")


@app.get("/victoria-logo.png", include_in_schema=False)
def logo():
    filename = BASE_DIR / "victoria-logo.png"

    if not filename.exists():
        raise HTTPException(
            status_code=404,
            detail="Logo not available",
        )

    return FileResponse(filename)


# ==========================================
# HEALTH CHECK
# ==========================================

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "Victoria Sales Agent MVP",
        "demo_database": "available",
        "real_sql_reporting": "configured",
    }


# ==========================================
# EXISTING DEMO SALES ENDPOINTS
# ==========================================

@app.get("/api/sales/months")
def months():
    try:
        return {"months": get_available_months()}

    except Exception:
        logger.exception("Unable to retrieve demo months")
        raise HTTPException(
            status_code=503,
            detail="Sales database unavailable",
        )


@app.get("/api/sales/overview")
def overview(month: str = "2026-09"):
    try:
        return get_sales_overview(month)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception:
        logger.exception("Demo overview failed")
        raise HTTPException(
            status_code=503,
            detail="Sales database unavailable",
        )


@app.get("/api/sales/trend")
def trend():
    try:
        return {
            "currency": "USD",
            "mode": "sample_database",
            "trend": get_trend(),
        }

    except Exception:
        logger.exception("Demo sales trend failed")
        raise HTTPException(
            status_code=503,
            detail="Sales database unavailable",
        )


@app.get("/api/sales/compare")
def compare(first: str, second: str):
    try:
        return compare_months(first, second)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception:
        logger.exception("Demo comparison failed")
        raise HTTPException(
            status_code=503,
            detail="Sales database unavailable",
        )


# ==========================================
# EXISTING OLLAMA DEMO CHATBOT
# ==========================================

@app.post("/api/chat", response_model=ChatResponse)
def chat(body: ChatRequest):
    try:
        return ChatResponse(
            answer=answer_sales_question(body.question),
            mode="sample_database",
        )

    except Exception:
        logger.exception("Demo chat failed")
        raise HTTPException(
            status_code=503,
            detail="Chat service unavailable",
        )


# ==========================================
# REAL SQL SERVER REPORTING
# ==========================================

@app.get("/api/sales/real-summary")
def real_sales_summary():
    try:
        return get_real_sales_summary()

    except Exception:
        logger.exception("SQL reporting query failed")
        raise HTTPException(
            status_code=503,
            detail="SQL reporting service unavailable",
        )


# ==========================================
# REAL SQL SERVER + OLLAMA CHATBOT
# ==========================================

@app.post("/api/chat/real", response_model=ChatResponse)
def real_chat(body: ChatRequest):
    try:
        return ChatResponse(
            answer=answer_real_sales_question(body.question),
            mode="real_database",
        )

    except Exception:
        logger.exception("Real database chat failed")
        raise HTTPException(
            status_code=503,
            detail="Real-data chat service unavailable",
        )
