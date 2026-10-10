import os
import pytest
os.environ['DISABLE_OLLAMA']='1'
from seed_data import seed_database
from sales_service import get_sales_overview, compare_months, get_trend
from agent import detect_months, answer_sales_question
from fastapi.testclient import TestClient
from main import app

@pytest.fixture(autouse=True)
def setup():
    seed_database()

def test_months():
    assert detect_months('August 2026 compared with 2026-09')==['2026-08','2026-09']

def test_september_totals():
    x=get_sales_overview('2026-09')
    assert x['summary']['revenue']==3740
    assert x['summary']['orders']==4
    assert x['summary']['units_sold']==49

def test_comparison():
    x=compare_months('2026-08','2026-09')
    assert x['has_data']
    assert x['percent_change']==49.0

def test_missing_month():
    assert not get_sales_overview('2025-01')['has_data']

def test_endpoints():
    client=TestClient(app)
    assert client.get('/health').status_code==200
    assert client.get('/api/sales/overview?month=2026-09').json()['summary']['revenue']==3740
    assert client.get('/api/sales/trend').status_code==200
    assert client.get('/api/sales/overview?month=oops').status_code==400
    assert client.post('/api/chat',json={'question':'What is September 2026 revenue?'}).status_code==200

def test_no_fake_profit():
    assert 'cannot be calculated' in answer_sales_question('What is profit in September 2026?')
