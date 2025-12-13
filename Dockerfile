FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# System deps and ngrok
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    ca-certificates curl \
 && curl -fsSL https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz -o /tmp/ngrok.tgz \
 && tar -xzf /tmp/ngrok.tgz -C /usr/local/bin ngrok \
 && rm -rf /var/lib/apt/lists/* /tmp/ngrok.tgz

# Install Python dependencies first (better build caching)
COPY requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

# Copy source
COPY app /app/app
COPY README.md /app/README.md
COPY start.sh /app/start.sh
# Normalize Windows line endings to Unix to avoid /bin/sh^M issues
RUN sed -i 's/\r$//' /app/start.sh && chmod +x /app/start.sh

# Create non-root user
RUN useradd -m -u 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Start uvicorn and (optionally) ngrok
CMD ["/app/start.sh"]


