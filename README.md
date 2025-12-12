## Environment variables

1) Create an env file by copying the example:

```bash
cp env.example .env
```

2) Edit `.env` and fill in your values (keep it private and out of git).

## Run locally with uvicorn (auto-load .env)

```bash
uvicorn app.main:app --env-file .env
```

## Docker

Build the image:

```bash
docker build -t zapier-webhook-receiver:latest .
```

Run the container:

```bash
docker run --rm -p 8000:8000 \
  --env-file .env \
  --name zapier-webhook \
  zapier-webhook-receiver:latest
```

Alternatively, pass variables explicitly with multiple `-e` flags (not recommended).

Key endpoints:
- `POST /events` — receive events (accepts optional `session_id` or `X-Session-Id`)
- `GET /status` — health and brief stats
- `GET /events` — list stored events
- `GET/POST/DELETE /context` — manage ephemeral context
- `GET/DELETE /sessions/{session_id}` — inspect/clear conversation history

Note:
- The app listens on `$PORT` (default 8000) and binds to `0.0.0.0` inside the container.
- Context and session history are in-memory and reset on container restart.


