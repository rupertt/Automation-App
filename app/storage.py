from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from app.models import EventStored, EventSummary


@dataclass
class InMemoryEventStore:
	"""A simple FIFO in-memory store with bounded size."""

	max_size: int = 100

	def __post_init__(self) -> None:
		self._events: list[EventStored] = []

	def add_event(self, event: EventStored) -> None:
		self._events.append(event)
		# FIFO eviction
		if len(self._events) > self.max_size:
			self._events.pop(0)

	def count(self) -> int:
		return len(self._events)

	def latest(self) -> EventStored | None:
		if not self._events:
			return None
		return self._events[-1]

	def latest_summary(self) -> EventSummary | None:
		latest = self.latest()
		if not latest:
			return None
		return EventSummary(
			event_id=latest.event_id,
			source=latest.source,
			received_at=latest.received_at,
			payload=latest.payload,
		)

	def list_events(self, offset: int = 0, limit: int = 10) -> Tuple[list[EventStored], int]:
		total = len(self._events)
		if offset < 0:
			offset = 0
		if limit < 0:
			limit = 0
		end = min(offset + limit, total)
		return self._events[offset:end], total

	def clear(self) -> None:
		self._events.clear()


# Shared store instance used by the app
store = InMemoryEventStore()


