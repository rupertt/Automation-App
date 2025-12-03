## Zapier Webhook Receiver (FastAPI)

A minimal FastAPI service to receive Zapier Webhooks (Option 3) and inspect them locally. It provides:

- POST `/events` to receive webhooks
- GET `/status` for a quick health check and stats
- GET `/events` (optional) to list recent events (paginated)

### Tech
- Python 3.11+
- FastAPI
- Uvicorn ASGI server
- Pydantic models and type hints
- Structured logging (JSON lines)

### Project Layout
```
app/
  config.py      # basic config (env, port)
  main.py        # FastAPI app and routes
  models.py      # Pydantic models
  storage.py     # in-memory event store (FIFO, max 100)
tests/
  test_events.py # pytest tests
requirements.txt
README.md
```

### Configuration
Environment variables:
- `PORT` (default: `8000`)
- `ENV` (default: `dev`)

### Setup

1) Create and activate a virtual environment (Windows PowerShell):
```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate
```

2) Install dependencies:
```powershell
pip install -r requirements.txt
```

3) Run the app:
```powershell
uvicorn app.main:app --reload --port 8000
```

App will be available at:
- http://127.0.0.1:8000/status
- http://127.0.0.1:8000/docs (interactive Swagger UI)

### Running on WSL (Ubuntu)

1) Ensure Python 3.11+ and venv support:
```bash
sudo apt update
sudo apt install -y python3-venv python3-pip
# Optional if default python3 < 3.11:
# sudo add-apt-repository ppa:deadsnakes/ppa -y
# sudo apt update && sudo apt install -y python3.11 python3.11-venv
```

2) Create and activate a virtual environment (inside your WSL project directory):
```bash
python3 -m venv .venv
source .venv/bin/activate
```

3) Install dependencies:
```bash
pip install -r requirements.txt
```

4) Run the app (bind to all interfaces for easy access from Windows):
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Access from Windows: http://localhost:8000/status and http://localhost:8000/docs
- For Zapier via ngrok, run inside WSL:
```bash
ngrok http 8000
```
Use the generated public URL with the `/events` path in your Zap’s Webhook action.

### Python version and venv notes

- This project targets **Python 3.11+**. If you see type errors like:
  - "Unable to evaluate type annotation 'list[T]'" or issues with `X | Y` unions, you're likely on Python 3.8/3.9. Upgrade to 3.11+.

#### Recreate venv with a specific Python
- Windows (PowerShell):
```powershell
deactivate 2>$null
Remove-Item -Recurse -Force .venv
py -3.11 -m venv .venv
.\.venv\Scripts\Activate
pip install -U pip
pip install -r requirements.txt
```

- WSL (Ubuntu/Debian):
```bash
deactivate || true
rm -rf .venv
# If your default python3 is 3.11+, this is enough:
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```
If your distro's python3 is older, either enable a newer Python (e.g., deadsnakes PPA on Ubuntu) or use pyenv (below).

#### Using pyenv (works on most distros)
```bash
curl -fsSL https://pyenv.run | bash
export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
pyenv install 3.11.9
pyenv local 3.11.9
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

#### Uvicorn/uvloop path tip
If `uvicorn` from the system path runs instead of the venv one (errors about `uvloop`), run via the module to force the venv interpreter:
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Using ngrok

Expose your local server to the internet for Zapier:
```powershell
ngrok http 8000
```
Copy the public URL from ngrok and use it in your Zapier “Webhooks by Zapier” action pointing to `/events`, e.g., `https://<YOUR-NGROK>.ngrok.io/events`.

### API

- POST `/events`
  - Request JSON:
    ```json
    {
      "event_id": "optional-string",
      "source": "zapier",
      "payload": { "any": "json" }
    }
    ```
  - If `event_id` is missing, the server generates a UUID.
  - Response JSON:
    ```json
    {
      "status": "ok",
      "event_id": "<resolved_id>",
      "stored_at": "<iso8601 timestamp>"
    }
    ```

- GET `/status`
  - Response JSON (example):
    ```json
    {
      "service": "zapier-webhook-receiver",
      "status": "healthy",
      "events_received": 2,
      "last_event": {
        "event_id": "123",
        "source": "zapier",
        "received_at": "2025-01-01T12:00:00Z"
      }
    }
    ```

- GET `/events`
  - Query params: `offset` (default 0), `limit` (default 10, max 100)
  - Returns paginated events as stored in memory (FIFO).

### Quick Test with curl
```bash
curl -X POST http://127.0.0.1:8000/events \
  -H "Content-Type: application/json" \
  -d '{"source":"zapier","payload":{"hello":"world"}}'

curl http://127.0.0.1:8000/status
curl "http://127.0.0.1:8000/events?offset=0&limit=5"
```

### Run Tests
```powershell
pytest -q
```


