# Automation Engine

FastAPI-based automation service for managing workflow tasks.

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file from example:
```bash
cp .env.example .env
```

3. Run the server:
```bash
uvicorn main:app --reload --port 8010
```

4. Test health endpoint:
```bash
curl http://localhost:8010/health
```

Expected response:
```json
{"status": "ok", "service": "automation_engine"}
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8010/docs
- ReDoc: http://localhost:8010/redoc
