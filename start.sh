#!/bin/sh
set -e

# Defaults
PORT="${PORT:-8000}"

# Start app first (background) so ngrok can connect reliably
uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" &
UVICORN_PID=$!

# If NGROK_AUTHTOKEN provided and not explicitly disabled, start ngrok
if [ -n "${NGROK_AUTHTOKEN}" ] && [ "${NGROK_DISABLE}" != "1" ]; then
	# Configure token (idempotent)
	ngrok config add-authtoken "${NGROK_AUTHTOKEN}" >/dev/null 2>&1 || true
	# Build args
	NGROK_ARGS="http --log=stdout"
	[ -n "${NGROK_REGION}" ] && NGROK_ARGS="$NGROK_ARGS --region ${NGROK_REGION}"
	if [ -n "${NGROK_DOMAIN}" ]; then
		# Custom domain requires a paid plan on ngrok
		NGROK_ARGS="$NGROK_ARGS --domain ${NGROK_DOMAIN}"
	fi
	# Allow extra args if needed
	[ -n "${NGROK_EXTRA_ARGS}" ] && NGROK_ARGS="$NGROK_ARGS ${NGROK_EXTRA_ARGS}"
	# Launch ngrok and parse stdout to print the public URL (no 4040 dependency)
	sh -lc "ngrok $NGROK_ARGS ${PORT} 2>&1 | awk '/started tunnel/ { for (i=1;i<=NF;i++) { if (\$i ~ /^url=/) { sub(\"url=\",\"\",\$i); print \"NGROK_PUBLIC_URL=\" \$i; fflush(); break } } } { print }' " &
fi

# Keep container attached to the app process
wait "${UVICORN_PID}"


