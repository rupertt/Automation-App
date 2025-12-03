from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
import os
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, APIRouter, Query, BackgroundTasks
import httpx

from app.config import get_settings
from app.models import (
	EventIn,
	EventStored,
	EventAck,
	StatusResponse,
	EventsListResponse,
)
from app.storage import store
from app.llm import generate_one_sentence_response


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
		text = generate_one_sentence_response(event)
		if text is None:
			log_event("llm_skipped", event_id=event.event_id)
			return
		log_event("llm_result", event_id=event.event_id)
	except Exception as exc:
		# Log detailed error so operators can see quota/model/permission issues
		log_event("llm_error", event_id=event.event_id, error=str(exc))
		return
	# Forward LLM result the same way we forward events
	forward_url = _get_forward_url()
	if forward_url:
		payload = {
			"event_id": event.event_id,
			"source": "llm",
			"text": text,
		}
		_forward_to_zapier(forward_url, payload)
	else:
		log_event("forward_skipped", reason="no_forward_url_configured_llm", event_id=event.event_id)


@router.post("/events", response_model=EventAck)
def receive_event(event: EventIn, background_tasks: BackgroundTasks) -> EventAck:
	resolved_id = event.event_id or str(uuid4())
	received_at = _now_utc()

	stored = EventStored(
		event_id=resolved_id,
		source=event.source,
		payload=event.payload,
		received_at=received_at,
	)
	store.add_event(stored)

	log_event(
		"received_event",
		event_id=resolved_id,
		source=event.source,
		payload_size=_payload_size(event.payload),
	)
	# Log full received payload into output.log as JSON line
	log_event(
		"received_event_full",
		event_id=resolved_id,
		source=event.source,
		payload=event.payload,
	)

	# Forward the event to Zapier webhook if configured
	forward_url = _get_forward_url()
	if forward_url:
		log_event("forward_scheduled", event_id=resolved_id)
		forward_payload = {
			"event_id": resolved_id,
			"source": event.source,
			"payload": event.payload,
		}
		background_tasks.add_task(_forward_to_zapier, forward_url, forward_payload)
	else:
		log_event("forward_skipped", reason="no_forward_url_configured", event_id=resolved_id)

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


