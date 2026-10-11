"""Victoria MVP. Confidential reporting APIs are restricted to loopback connections."""
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from agent import answer_sales_question, answer_real_sales_question
from sales_service import get_sales_overview, get_trend, compare_months, get_available_months
from sql_reporting import get_real_sales_summary, get_dashboard_data
import logging

logger = logging.getLogger('victoria')
ROOT = Path(__file__).resolve().parent
app = FastAPI(title='Victoria Sales Agent MVP', version='2.0')

class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=2000)

@app.middleware('http')
async def local_only(request: Request, call_next):
    # This is an MVP local-only guard, NOT enterprise authentication.
    # Do not deploy this app behind an exposed reverse proxy without proper auth.
    if request.client and request.client.host not in ('127.0.0.1', '::1', 'testclient'):
        return JSONResponse({'detail':'Local access only'}, status_code=403)
    return await call_next(request)

@app.get('/', include_in_schema=False)
@app.get('/index.html', include_in_schema=False)
def index():
    return FileResponse(ROOT / 'index.html')

@app.get('/victoria-logo.png', include_in_schema=False)
def logo():
    if not (ROOT / 'victoria-logo.png').exists():
        raise HTTPException(404, 'Logo not found')
    return FileResponse(ROOT / 'victoria-logo.png')

@app.get('/health')
def health():
    return {'status':'healthy', 'mode':'real_reporting_mvp'}

@app.get('/api/sales/months')
def months():
    try:
        return {'months': get_available_months(), 'mode':'sample_database'}
    except Exception:
        raise HTTPException(503, 'Sample sales database unavailable')

@app.get('/api/sales/overview')
def overview(month: str = '2026-09'):
    try:
        return get_sales_overview(month)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception:
        logger.exception('Demo overview failed')
        raise HTTPException(503, 'Sample sales database unavailable')

@app.get('/api/sales/trend')
def trend():
    return {'mode':'sample_database', 'trend':get_trend()}

@app.get('/api/sales/compare')
def compare(first: str, second: str):
    return compare_months(first, second)

@app.post('/api/chat')
def demo_chat(body: ChatRequest):
    return {'mode':'sample_database', 'answer':answer_sales_question(body.question)}

@app.get('/api/sales/real-summary')
def real_summary():
    try:
        return get_real_sales_summary()
    except Exception:
        logger.exception('SQL reporting unavailable')
        raise HTTPException(503, 'SQL reporting unavailable: check server, login and password')

@app.get('/api/sales/real-overview')
def real_overview(month: str | None = None):
    if month is not None:
        import re
        if not re.fullmatch(r'20\d\d-(0[1-9]|1[0-2])', month):
            raise HTTPException(400, 'Month must be YYYY-MM')
    try:
        return get_dashboard_data(month)
    except Exception:
        logger.exception('Real dashboard failed')
        raise HTTPException(503, 'SQL dashboard unavailable: check SQL connection or reporting views')

@app.post('/api/chat/real')
def real_chat(body: ChatRequest):
    try:
        return {'mode':'real_database', 'answer':answer_real_sales_question(body.question)}
    except Exception:
        logger.exception('Real chat failed')
        raise HTTPException(503, 'SQL reporting unavailable: check server, password, and reporting views')
