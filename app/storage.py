from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from app.models import EventStored, EventSummary, ConversationMessage


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


# Ephemeral, in-memory context store. Resets when the process restarts.
class InMemoryContext:
	def __init__(self) -> None:
		self._context: str | None = None

	def set(self, context: str) -> None:
		self._context = context

	def get(self) -> str | None:
		return self._context

	def clear(self) -> None:
		self._context = None


class InMemoryConversationStore:
	"""Conversation history store keyed by session_id; resets on process restart."""

	def __init__(self, max_messages: int = 20) -> None:
		self._by_session: dict[str, list[ConversationMessage]] = {}
		self._max_messages = max_messages

	def get(self, session_id: str) -> list[ConversationMessage]:
		return list(self._by_session.get(session_id, []))

	def append_messages(self, session_id: str, messages: list[ConversationMessage]) -> None:
		if not session_id:
			return
		history = self._by_session.get(session_id)
		if history is None:
			history = []
			self._by_session[session_id] = history
		history.extend(messages)
		# Trim to last N messages
		if len(history) > self._max_messages:
			self._by_session[session_id] = history[-self._max_messages :]

	def clear(self, session_id: str) -> None:
		self._by_session.pop(session_id, None)

	def clear_all(self) -> None:
		self._by_session.clear()


# Shared store instance used by the app
store = InMemoryEventStore()
context_store = InMemoryContext()
conversation_store = InMemoryConversationStore()


