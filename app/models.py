from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class EventIn(BaseModel):
	"""Incoming event payload from Zapier webhook."""

	event_id: Optional[str] = Field(default=None, description="Client-provided ID; generated if absent")
	source: str = Field(..., description="Source name of the event")
	payload: Any = Field(..., description="Arbitrary JSON payload")
	session_id: Optional[str] = Field(default=None, description="Logical session id for conversation memory")


class EventStored(BaseModel):
	"""Event as stored in memory."""

	event_id: str
	source: str
	payload: Any
	received_at: datetime
	session_id: Optional[str] = None


class EventAck(BaseModel):
	"""Acknowledgement returned for POST /events."""

	status: Literal["ok"] = "ok"
	event_id: str
	stored_at: datetime


class EventSummary(BaseModel):
	"""Reduced representation of the latest event for status endpoint."""

	event_id: str
	source: str
	received_at: datetime
	payload: Any


class StatusResponse(BaseModel):
	"""Response model for GET /status."""

	service: Literal["zapier-webhook-receiver"] = "zapier-webhook-receiver"
	status: Literal["healthy"] = "healthy"
	events_received: int
	last_event: Optional[EventSummary] = None


class EventsListResponse(BaseModel):
	"""Paginated list of events."""

	total: int
	offset: int
	limit: int
	items: list[EventStored]


class ContextSetRequest(BaseModel):
	"""Request body to set/replace the in-memory context."""

	context: str = Field(..., description="Context text to include with LLM requests")


class ContextResponse(BaseModel):
	"""Response model for context endpoints."""

	context: Optional[str] = Field(default=None, description="Current in-memory context, if any")


class ConversationMessage(BaseModel):
	"""A single conversation message stored for a session."""

	role: Literal["user", "assistant"]
	content: str


class SessionHistoryResponse(BaseModel):
	"""Response model for session history endpoints."""

	session_id: str
	messages: list[ConversationMessage]


