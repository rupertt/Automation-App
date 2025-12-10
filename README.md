## Zapier Webhook Receiver (Linux)

A minimal FastAPI service that:
- Accepts `POST /events` with a payload.
- Generates a one‑sentence reply using OpenAI.
- Forwards only the reply to your Zapier webhook.
- Exposes `GET /status` and `GET /events` for quick local inspection.

### Run (Linux)
Prereqs: Python 3.11+, pip, and (optionally) ngrok.

1) Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Start the API (replace placeholders with your actual values):

```bash
OPENAI_API_KEY="API_KEY" OPENAI_MODEL="API_MODEL" \
uvicorn app.main:app --reload --host 0.0.0.0 --port "${PORT:-8000}"
```

3) (Optional) Expose locally via ngrok for Zapier:

```bash
ngrok http 8000
```

Endpoints:
- `POST /events`
- `GET /status`
- `GET /events`
*** End Patch

