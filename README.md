# Victoria Sales Agent MVP

An end-to-end **sample-data** sales assistant using FastAPI, SQLite (read-only query connections), and locally hosted Qwen3 via Ollama. Built to work without any AWS permissions. Contains **no real Victoria business data**.

## Windows quick start

```powershell
cd victoria-sales-agent-mvp
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python seed_data.py
ollama pull qwen3:8b
python -m uvicorn main:app --reload --port 8000
```

Open http://127.0.0.1:8000 and http://127.0.0.1:8000/docs . Ollama must be installed/running separately. The chatbot falls back to verified Python-calculated facts after 25 seconds if Ollama is unavailable. To force fast deterministic mode, set `$env:DISABLE_OLLAMA='1'` **before starting** FastAPI.

## Endpoints
- `GET /health`
- `GET /api/sales/months`
- `GET /api/sales/overview?month=2026-09`
- `GET /api/sales/trend`
- `GET /api/sales/compare?first=2026-08&second=2026-09`
- `POST /api/chat` body `{"question":"Compare August 2026 and September 2026"}`

## Tests

```powershell
python -m pytest -q
```

## Scope and safeguards
- Only synthetic sample data is included. No raw arbitrary SQL execution by the model.
- Revenue, orders, growth, and comparisons are computed by SQL/Python, not the LLM.
- No profit/forecast claims without supporting data.
- This is a demonstrable local MVP, **not production-ready authentication, tenancy, or authorization**.
- Never expose port 8000 or Ollama API to the public internet without authentication and perimeter protections.

## AWS and real SQL Server integration (not implemented)

Do **not** point this at production SQL Server. Obtain an approved sanitized copy and database credentials with SQL-level SELECT-only permissions. Inspect the schema and map date, order ID, product, quantity, unit price, currency, and market into a reviewed, fixed SELECT query or read-only view. The SQLite demo schema is **not** assumed to match Victoria's real SQL Express schema.

The next phase should implement that read-only adapter and test against the authorized copy. Review authentication, TLS, encryption, IAM/VPC rules, secrets handling, licensing, and retention before cloud deployment. Dockerfile is a development packaging starting point only; it is not a secure public-production deployment.

## GitHub

This ZIP is not committed into the original repository. To apply it safely, extract to a **new working folder**, run tests, compare with the original, and commit on a feature branch. Do not blindly overwrite your existing code.
