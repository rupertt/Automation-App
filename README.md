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

### Ngrok (public URL for webhooks)
- Set in `.env`:
  - `NGROK_AUTHTOKEN=your-token` (required to start ngrok)
  - Optional: `NGROK_DOMAIN=your-ngrok-domain.example` (requires paid plan)
  - Optional: `NGROK_DISABLE=1` to turn off ngrok
- When the container starts, it will launch uvicorn and ngrok (`ngrok http $PORT`).
- View the public URL:
  - The container will print a line like `NGROK_PUBLIC_URL=https://abcd-1234.ngrok-free.app` shortly after start; run:
    ```bash
    docker logs zapier-webhook | grep NGROK_PUBLIC_URL
    ```

## Kubernetes (single manifest in `k8s/manifest.yaml`)

1) Create or update the Secret (kept out of the manifest so re-applying doesn't wipe values):
```bash
kubectl create secret generic zapier-webhook-secrets \
  --from-literal=OPENAI_API_KEY='sk-...' \
  --from-literal=NGROK_AUTHTOKEN='your-ngrok-token' \
  --dry-run=client -o yaml | kubectl apply -f -
```

2) Edit the manifest if needed (image, domain/TLS in Ingress), then apply:
```bash
kubectl apply -f k8s/manifest.yaml
```

3) Verify:
```bash
kubectl get pods -l app=zapier-webhook
kubectl logs -l app=zapier-webhook
kubectl get svc zapier-webhook
```

Notes:
- The container image is `zapier-webhook-receiver:latest`; push it to a registry your cluster can pull from, or change the image in the manifest to a published one.
- Ngrok in Kubernetes:
  - Ngrok runs as a sidecar container; the app container keeps `NGROK_DISABLE=1`.
  - Set your authtoken in the Secret (step 1 above).
  - Get the public URL from ngrok logs:
    ```bash
    kubectl logs -l app=zapier-webhook -c ngrok | grep -E 'url=https?://'
    ```
- Liveness/readiness probes hit `/status` on port 8000 via the `http` port.

Key endpoints:
- `POST /events` — receive events (accepts optional `session_id` or `X-Session-Id`)
- `GET /status` — health and brief stats
- `GET /events` — list stored events
- `GET/POST/DELETE /context` — manage ephemeral context
- `GET/DELETE /sessions/{session_id}` — inspect/clear conversation history

Note:
- The app listens on `$PORT` (default 8000) and binds to `0.0.0.0` inside the container.
- Context and session history are in-memory and reset on container restart.


