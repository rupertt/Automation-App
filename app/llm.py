from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
import os
from typing import Any, Optional

from app.models import EventStored, ConversationMessage
from app.storage import context_store, conversation_store

try:
	from openai import OpenAI
except Exception:  # pragma: no cover
	OpenAI = None  # type: ignore


def _setup_llm_debug_logger() -> logging.Logger:
	logger = logging.getLogger("llm_debug")
	logger.setLevel(logging.INFO)
	if not logger.handlers:
		# Write compact JSON lines to a dedicated debug file
		file_handler = logging.FileHandler("llm_output.log", encoding="utf-8")
		file_handler.setFormatter(logging.Formatter("%(message)s"))
		logger.addHandler(file_handler)
	return logger


_llm_debug_logger = _setup_llm_debug_logger()


def llm_env_status() -> dict[str, Any]:
	"""Return a small diagnostic snapshot about LLM readiness without leaking secrets."""
	return {
		"library_available": OpenAI is not None,
		"has_api_key": bool(os.getenv("OPENAI_API_KEY")),
		"model": os.getenv("OPENAI_MODEL", "gpt-4.1-nano"),
	}


def _extract_user_text(payload: Any) -> str:
	"""
	Best-effort extraction of the user's actual message from an arbitrary payload.
	- If payload is a dict, prefer common text fields over full JSON dump.
	- Otherwise, stringify the payload.
	"""
	if isinstance(payload, dict):
		candidate_keys = ["question", "message", "text", "content", "prompt", "query"]
		# Check case-insensitively
		lower_map = {str(k).lower(): v for k, v in payload.items()}
		for key in candidate_keys:
			if key in lower_map and isinstance(lower_map[key], str) and lower_map[key].strip():
				return lower_map[key].strip()
		# Fallback to compact JSON string for dicts
		try:
			return json.dumps(payload, ensure_ascii=False)
		except Exception:
			return str(payload)
	# For non-dict payloads, just stringify
	try:
		return json.dumps(payload, ensure_ascii=False)
	except Exception:
		return str(payload)


def generate_one_sentence_response(event: EventStored) -> Optional[str]:
	"""
	Generate a single-sentence response using OpenAI chat completions.
	Returns None if API is not configured or client library unavailable.
	Raises exceptions for API errors so the caller can log detailed reasons.
	"""
	api_key = os.getenv("OPENAI_API_KEY")
	if not api_key or OpenAI is None:
		return None

	model = os.getenv("OPENAI_MODEL", "gpt-4.1-nano")

	client = OpenAI(api_key=api_key)
	# Build system message, injecting any in-memory context if present
	base_system = (
		"You are a concise assistant. Respond in one single sentence only. "
		"Primary instruction: Answer the user's message provided under 'User message' below. "
		"Do not restate or summarize metadata such as Source or Event ID. "
		"If the message is not a question, reply with a brief, helpful acknowledgement related to the message. "
		"Do not include extra explanations or multiple sentences."
	)
	ctx = context_store.get()
	if ctx:
		system_content = f"{base_system}\n\nContext:\n{ctx}"
	else:
		system_content = base_system
	user_text = _extract_user_text(event.payload)
	metadata_text = f"Source: {event.source}\nEvent ID: {event.event_id}"
	# Fetch session history if a session_id exists
	history_messages: list[dict[str, str]] = []
	if event.session_id:
		for m in conversation_store.get(event.session_id):
			history_messages.append({"role": m.role, "content": m.content})
	# Compose final messages: system, history, current user
	messages = [
		{
			"role": "system",
			"content": system_content,
		},
	]
	messages.extend(history_messages)
	current_user_message = {
		"role": "user",
		"content": f"User message:\n{user_text}\n\n[Metadata - ignore for response]\n{metadata_text}",
	}
	messages.append(current_user_message)

	# Use chat completions API
	resp = client.chat.completions.create(
		model=model,
		messages=messages,
		temperature=0.2,
		max_tokens=80,
	)

	content = resp.choices[0].message.content if resp and resp.choices else None
	if not content:
		# Log roundtrip even if response empty
		_log_llm_roundtrip(event, messages, None, model, ctx)
		return None
	# Ensure it's trimmed to one sentence best-effort
	response_text = content.strip().replace("\n", " ")
	_log_llm_roundtrip(event, messages, response_text, model, ctx)
	# Update conversation history with this turn if session_id present
	if event.session_id:
		turns = [
			ConversationMessage(role="user", content=current_user_message["content"]),
			ConversationMessage(role="assistant", content=response_text),
		]
		conversation_store.append_messages(event.session_id, turns)
	return response_text


def _log_llm_roundtrip(event: EventStored, messages: list[dict[str, str]], response_text: Optional[str], model: str, context: Optional[str]) -> None:
	record = {
		"timestamp": datetime.now(timezone.utc).isoformat(),
		"type": "llm_roundtrip",
		"event_id": event.event_id,
		"source": event.source,
		"user_input": event.payload,  # raw payload as provided
		"openai_request": {
			"model": model,
			"messages": messages,
		},
		"openai_response": {
			"text": response_text,
		},
		"context": {
			"included": bool(context),
			"value": context,
		},
		"session": {
			"id": event.session_id,
			"history_included": any(m.get("role") in ("user", "assistant") for m in messages[1:-1]) if len(messages) > 2 else False,
			"history_count": max(0, len(messages) - 2),  # exclude system and current user
		},
	}
	_llm_debug_logger.info(json.dumps(record, ensure_ascii=False, default=str))


