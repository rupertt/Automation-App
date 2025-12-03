from __future__ import annotations

import os
from typing import Any, Optional

from app.models import EventStored

try:
	from openai import OpenAI
except Exception:  # pragma: no cover
	OpenAI = None  # type: ignore


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
		"library_available": OpenAI is not None,
		"has_api_key": bool(key),
		"key_source": source,
		"model": os.getenv("OPENAI_MODEL", "gpt-4.1-nano"),
	}


def generate_one_sentence_response(event: EventStored) -> Optional[str]:
	"""
	Generate a single-sentence response using OpenAI chat completions.
	Returns None if API is not configured or client library unavailable.
	Raises exceptions for API errors so the caller can log detailed reasons.
	"""
	api_key, _ = _resolve_api_key()
	if not api_key or OpenAI is None:
		return None

	model = os.getenv("OPENAI_MODEL", "gpt-4.1-nano")

	client = OpenAI(api_key=api_key)
	messages = [
		{
			"role": "system",
			"content": (
				"You are a concise assistant. Respond in one single sentence only. "
				"Do not include extra explanations or multiple sentences."
			),
		},
		{
			"role": "user",
			"content": (
				f"Source: {event.source}\n"
				f"Event ID: {event.event_id}\n"
				f"Payload JSON (stringified): {event.payload}"
			),
		},
	]

	# Use chat completions API
	resp = client.chat.completions.create(
		model=model,
		messages=messages,
		temperature=0.2,
		max_tokens=80,
	)

	content = resp.choices[0].message.content if resp and resp.choices else None
	if not content:
		return None
	# Ensure it's trimmed to one sentence best-effort
	return content.strip().replace("\n", " ")


