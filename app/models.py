from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class EventIn(BaseModel):
	"""Incoming event payload from Zapier webhook."""

	event_id: Optional[str] = Field(default=None, description="Client-provided ID; generated if absent")
	source: str = Field(..., description="Source name of the event")
	payload: Any = Field(..., description="Arbitrary JSON payload")


class EventStored(BaseModel):
	"""Event as stored in memory."""

	event_id: str
	source: str
	payload: Any
	received_at: datetime


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


