# qa_rca_agent

An enterprise-oriented QA Root Cause Analysis (RCA) platform blueprint implemented as a lightweight Flask application.

## What is included

- Hybrid RCA design blueprint for enterprise QA operations
- Multi-agent architecture specification
- Processing pipeline, API contracts, data models, and confidence scoring strategy
- Example production workflows and agent prompts
- A minimal `/api/v1/rca/analyze` endpoint that demonstrates structured RCA output using deterministic correlation and rule-based reasoning

## Quick start

```bash
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000/` to view the architecture console.

## API endpoints

- `GET /health` - health check
- `GET /api/v1/blueprint` - enterprise RCA platform blueprint
- `POST /api/v1/rca/analyze` - generate a structured RCA decision from issue context

## Running tests

```bash
python -m unittest discover -s tests -v
```
