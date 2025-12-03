from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from app.models import EventStored, EventSummary


@dataclass
class InMemoryEventStore:
	"""A simple FIFO in-memory store with bounded size."""

	max_size: int = 100
	max_llm_history: int = 100

	def __post_init__(self) -> None:
		self._events: list[EventStored] = []
		self._llm_responses: list[str] = []

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
		self._llm_responses.clear()

	# ---- LLM response history ----
	def add_llm_response(self, text: str) -> None:
		self._llm_responses.append(text)
		if len(self._llm_responses) > self.max_llm_history:
			self._llm_responses.pop(0)

	def llm_context_messages(self, limit: int = 20) -> list[dict[str, str]]:
		if limit <= 0:
			return []
		start = max(0, len(self._llm_responses) - limit)
		# Represent prior replies as assistant messages
		return [{"role": "assistant", "content": t} for t in self._llm_responses[start:]]


# Shared store instance used by the app
store = InMemoryEventStore()


