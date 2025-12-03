from __future__ import annotations

import os
from typing import Any, Optional

from app.models import EventStored
from app.storage import store
import httpx


def _resolve_api_key() -> tuple[Optional[str], str]:
	"""
	Return (api_key, source). Source is 'env', 'file', or 'none'.
	"""
	key_raw = os.getenv("OPENAI_API_KEY")
	if isinstance(key_raw, str) and key_raw.strip():
		return key_raw.strip(), "env"
	file_path = os.getenv("OPENAI_API_KEY_FILE")
	if isinstance(file_path, str) and file_path.strip():
		try:
			with open(file_path, "r", encoding="utf-8") as f:
				content = f.read().strip()
				if content:
					return content, "file"
		except Exception:
			pass
	return None, "none"


def llm_env_status() -> dict[str, Any]:
	"""Return a small diagnostic snapshot about LLM readiness without leaking secrets."""
	key, source = _resolve_api_key()
	return {
		"library_available": True,
		"has_api_key": bool(key),
		"key_source": source,
		"model": os.getenv("OPENAI_MODEL", "gpt-4.1-nano"),
	}


def generate_one_sentence_response(event: EventStored) -> Optional[str]:
	"""
	Generate a single-sentence response using OpenAI chat completions.
	Returns None if API is not configured.
	Raises RuntimeError for API errors so the caller can log detailed reasons.
	"""
	api_key, _ = _resolve_api_key()
	if not api_key:
		return None

	model = os.getenv("OPENAI_MODEL", "gpt-4.1-nano")
	url = "https://api.openai.com/v1/chat/completions"
	# Build messages with prior assistant responses as context
	context_messages = store.llm_context_messages(limit=20)
	payload = {
		"model": model,
		"messages": [
			{
				"role": "system",
				"content": (
					"You are a concise assistant. Respond in one single sentence only. "
					"Do not include extra explanations or multiple sentences."
				),
			},
			*context_messages,
			{
				"role": "user",
				"content": (
					f"Source: {event.source}\n"
					f"Event ID: {event.event_id}\n"
					f"Payload JSON (stringified): {event.payload}"
				),
			},
		],
		"temperature": 0.2,
		"max_tokens": 80,
	}
	headers = {
		"Authorization": f"Bearer {api_key}",
		"Content-Type": "application/json",
	}

	with httpx.Client(timeout=20) as client:
		response = client.post(url, json=payload, headers=headers)
		if response.status_code != 200:
			# Raise with details so caller logs them
			raise RuntimeError(f"openai_http_error status={response.status_code} body={response.text[:400]}")
		data: dict[str, Any] = response.json()
		choices = data.get("choices") or []
		if not choices:
			return None
		message = (choices[0] or {}).get("message") or {}
		content = message.get("content")
		if not isinstance(content, str) or not content.strip():
			return None
		return content.strip().replace("\n", " ")


