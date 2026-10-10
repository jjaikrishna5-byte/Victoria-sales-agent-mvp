from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from agent import answer_sales_question
from sales_service import get_sales_overview, get_trend, compare_months, get_available_months

BASE_DIR=Path(__file__).resolve().parent
app=FastAPI(title='Victoria Sales Agent MVP',version='1.0')

class ChatRequest(BaseModel):
    model_config=ConfigDict(str_strip_whitespace=True)
    question: str=Field(min_length=1,max_length=2000)

class ChatResponse(BaseModel):
    answer:str
    mode:str='sample_database'

@app.get('/',include_in_schema=False)
@app.get('/index.html',include_in_schema=False)
def index():
    return FileResponse(BASE_DIR/'index.html')

@app.get('/victoria-logo.png',include_in_schema=False)
def logo():
    filename=BASE_DIR/'victoria-logo.png'
    if not filename.exists():
        raise HTTPException(404,'Logo not available')
    return FileResponse(filename)

@app.get('/health')
def health():
    return {'status':'healthy','service':'Victoria Sales Agent','mode':'sample_database'}

@app.get('/api/sales/months')
def months():
    try:
        return {'months':get_available_months()}
    except Exception:
        raise HTTPException(503,'Sales database unavailable')

@app.get('/api/sales/overview')
def overview(month:str='2026-09'):
    try:
        return get_sales_overview(month)
    except ValueError as e:
        raise HTTPException(400,str(e))
    except Exception:
        raise HTTPException(503,'Sales database unavailable')

@app.get('/api/sales/trend')
def trend():
    try:
        return {'currency':'USD','mode':'sample_database','trend':get_trend()}
    except Exception:
        raise HTTPException(503,'Sales database unavailable')

@app.get('/api/sales/compare')
def compare(first:str,second:str):
    try:
        return compare_months(first,second)
    except ValueError as e:
        raise HTTPException(400,str(e))
    except Exception:
        raise HTTPException(503,'Sales database unavailable')

@app.post('/api/chat',response_model=ChatResponse)
def chat(body:ChatRequest):
    try:
        return ChatResponse(answer=answer_sales_question(body.question))
    except Exception:
        raise HTTPException(503,'Chat service unavailable')
