from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
import os
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, APIRouter, Query, BackgroundTasks, Header
import httpx

from app.config import get_settings
from app.models import (
	EventIn,
	EventStored,
	EventAck,
	StatusResponse,
	EventsListResponse,
	ContextSetRequest,
	ContextResponse,
	SessionHistoryResponse,
	ConversationMessage,
)
from app.storage import store, context_store, conversation_store
from app.llm import generate_one_sentence_response, llm_env_status


def _setup_logger() -> logging.Logger:
	logger = logging.getLogger("zapier_webhook_receiver")
	logger.setLevel(logging.INFO)
	if not logger.handlers:
		handler = logging.StreamHandler(sys.stdout)
		# Output raw JSON strings; keep formatter minimal
		handler.setFormatter(logging.Formatter("%(message)s"))
		logger.addHandler(handler)
		# Also log to output.log as requested
		file_handler = logging.FileHandler("output.log", encoding="utf-8")
		file_handler.setFormatter(logging.Formatter("%(message)s"))
		logger.addHandler(file_handler)
	return logger


logger = _setup_logger()
settings = get_settings()

router = APIRouter()


def _now_utc() -> datetime:
	return datetime.now(timezone.utc)


def _get_forward_url() -> str | None:
	# Prefer per-request environment overrides, then fall back to loaded settings
	return os.getenv("ZAPIER_FORWARD_URL") or os.getenv("FORWARD_URL") or settings.forward_url


def log_event(message: str, **fields: Any) -> None:
	record = {
		"timestamp": _now_utc().isoformat(),
		"level": "INFO",
		"message": message,
		**fields,
	}
	logger.info(json.dumps(record, ensure_ascii=False))


def _payload_size(payload: Any) -> int:
	try:
		if isinstance(payload, dict):
			return len(payload)
		# Fallback to length of JSON string
		return len(json.dumps(payload))
	except Exception:
		return 0


def _forward_to_zapier(url: str, payload: dict[str, Any]) -> None:
	try:
		with httpx.Client(timeout=10) as client:
			resp = client.post(url, json=payload)
			log_event("forward_result", status_code=resp.status_code, ok=resp.is_success, event_id=payload.get("event_id"))
	except Exception as exc:
		log_event("forward_error", error=str(exc))


def _llm_and_forward(event: EventStored) -> None:
	# Call LLM for a one-sentence response
	try:
		status = llm_env_status()
		if not status.get("library_available") or not status.get("has_api_key"):
			reason = "library_missing" if not status.get("library_available") else "missing_api_key"
			log_event("llm_skipped", event_id=event.event_id, reason=reason, model=status.get("model"))
			return
		text = generate_one_sentence_response(event)
		if text is None:
			# This path covers cases like empty completion; provide a reason
			log_event("llm_skipped", event_id=event.event_id, reason="empty_completion", model=status.get("model"))
			return
		log_event("llm_result", event_id=event.event_id)
	except Exception as exc:
		# Log detailed error so operators can see quota/model/permission issues
		log_event("llm_error", event_id=event.event_id, error=str(exc), model=llm_env_status().get("model"))
		return
	# Forward LLM result the same way we forward events
	forward_url = _get_forward_url()
	if forward_url:
		# Only send the reply text as requested by the integration contract
		payload = {"reply": text}
		_forward_to_zapier(forward_url, payload)
	else:
		log_event("forward_skipped", reason="no_forward_url_configured_llm", event_id=event.event_id)


def _derive_session_id(event: EventIn, x_session_id: str | None) -> str | None:
	# Precedence: explicit in body > header > Slack/thread heuristics > common keys > fallback
	if event.session_id:
		return event.session_id
	if x_session_id:
		return x_session_id
	payload = event.payload
	if isinstance(payload, dict):
		# Helper to fetch first non-empty string from candidate keys
		def pick(d: dict[str, Any], keys: list[str]) -> str | None:
			for k in keys:
				val = d.get(k)
				if isinstance(val, str) and val.strip():
					return val.strip()
				# Slack timestamps may be numeric; accept non-str
				if not isinstance(val, str) and val is not None:
					try:
						s = str(val).strip()
						if s:
							return s
					except Exception:
						continue
			return None

		# Slack Events API style: payload.event.{channel,thread_ts,ts,user}
		ev = payload.get("event")
		if isinstance(ev, dict):
			channel = pick(ev, ["channel", "channel_id"])
			thread_ts = pick(ev, ["thread_ts", "ts"])
			user = pick(ev, ["user", "user_id"])
			if channel and thread_ts:
				return f"slack:{channel}:{thread_ts}"
			if channel and user:
				return f"slack:{channel}:{user}"
		# Slack slash/interactive style: flat keys
		channel = pick(payload, ["channel", "channel_id"])
		thread_ts = pick(payload, ["thread_ts", "ts"])
		user = pick(payload, ["user", "user_id"])
		if channel and thread_ts:
			return f"slack:{channel}:{thread_ts}"
		if channel and user:
			return f"slack:{channel}:{user}"
		# Common generic keys
		for key in ["session_id", "session", "conversation_id", "thread_id", "chat_id", "user_id", "user"]:
			val = payload.get(key)
			if isinstance(val, str) and val.strip():
				return val.strip()
	# As last resort, group by source to always include some history bucket
	source = (event.source or "default").lower()
	return f"{source}:global"


@router.post("/events", response_model=EventAck)
def receive_event(
	event: EventIn,
	background_tasks: BackgroundTasks,
	x_session_id: str | None = Header(default=None, convert_underscores=False, alias="X-Session-Id"),
) -> EventAck:
	resolved_id = event.event_id or str(uuid4())
	received_at = _now_utc()
	resolved_session = _derive_session_id(event, x_session_id)

	stored = EventStored(
		event_id=resolved_id,
		source=event.source,
		payload=event.payload,
		received_at=received_at,
		session_id=resolved_session,
	)
	store.add_event(stored)

	log_event(
		"received_event",
		event_id=resolved_id,
		source=event.source,
		payload_size=_payload_size(event.payload),
		session_id=resolved_session,
	)
	# Log full received payload into output.log as JSON line
	log_event(
		"received_event_full",
		event_id=resolved_id,
		source=event.source,
		payload=event.payload,
		session_id=resolved_session,
	)

	# Forward the event to Zapier webhook if configured
	# Per requirements, do not forward raw events; only forward the LLM reply later
	# Retain informative log that raw forward is intentionally skipped
	log_event("forward_skipped", reason="raw_event_forward_disabled", event_id=resolved_id)

	# Also invoke LLM and forward its single-sentence response
	background_tasks.add_task(_llm_and_forward, stored)

	return EventAck(event_id=resolved_id, stored_at=received_at)


@router.get("/status", response_model=StatusResponse)
def status() -> StatusResponse:
	return StatusResponse(
		events_received=store.count(),
		last_event=store.latest_summary(),
	)


@router.get("/events", response_model=EventsListResponse)
def list_events(offset: int = Query(default=0, ge=0), limit: int = Query(default=10, ge=0, le=100)) -> EventsListResponse:
	items, total = store.list_events(offset=offset, limit=limit)
	return EventsListResponse(total=total, offset=offset, limit=limit, items=items)


app = FastAPI(title="Zapier Webhook Receiver", version="1.0.0")
app.include_router(router)

# --- Context management endpoints (ephemeral; reset on restart) ---

@router.get("/context", response_model=ContextResponse)
def get_context() -> ContextResponse:
	current = context_store.get()
	return ContextResponse(context=current)


@router.post("/context", response_model=ContextResponse)
def set_context(body: ContextSetRequest) -> ContextResponse:
	context_store.set(body.context)
	log_event("context_set")
	return ContextResponse(context=body.context)


@router.delete("/context", response_model=ContextResponse)
def clear_context() -> ContextResponse:
	context_store.clear()
	log_event("context_cleared")
	return ContextResponse(context=None)

# --- Session history endpoints (ephemeral; reset on restart) ---

@router.get("/sessions/{session_id}", response_model=SessionHistoryResponse)
def get_session_history(session_id: str) -> SessionHistoryResponse:
	raw = conversation_store.get(session_id)
	return SessionHistoryResponse(
		session_id=session_id,
		messages=[ConversationMessage(role=m.role, content=m.content) for m in raw],
	)


@router.delete("/sessions/{session_id}", response_model=SessionHistoryResponse)
def clear_session_history(session_id: str) -> SessionHistoryResponse:
	conversation_store.clear(session_id)
	log_event("session_cleared", session_id=session_id)
	return SessionHistoryResponse(session_id=session_id, messages=[])


