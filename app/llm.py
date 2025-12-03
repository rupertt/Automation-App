from __future__ import annotations

import os
from typing import Any, Optional

from app.models import EventStored

try:
	from openai import OpenAI
except Exception:  # pragma: no cover
	OpenAI = None  # type: ignore


def llm_env_status() -> dict[str, Any]:
	"""Return a small diagnostic snapshot about LLM readiness without leaking secrets."""
	key = os.getenv("OPENAI_API_KEY")
	return {
		"library_available": OpenAI is not None,
		"has_api_key": bool(key.strip()) if isinstance(key, str) else False,
		"model": os.getenv("OPENAI_MODEL", "gpt-4.1-nano"),
	}


def generate_one_sentence_response(event: EventStored) -> Optional[str]:
	"""
	Generate a single-sentence response using OpenAI chat completions.
	Returns None if API is not configured or client library unavailable.
	Raises exceptions for API errors so the caller can log detailed reasons.
	"""
	api_key_raw = os.getenv("OPENAI_API_KEY")
	api_key = api_key_raw.strip() if isinstance(api_key_raw, str) else None
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


