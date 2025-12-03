from __future__ import annotations

from typing import Generator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage import store


@pytest.fixture(autouse=True)
def _clear_store() -> Generator[None, None, None]:
	# Ensure a clean store for each test
	store.clear()
	yield
	store.clear()


def test_post_events_with_valid_payload() -> None:
	client = TestClient(app)
	body = {
		"event_id": "evt-123",
		"source": "zapier",
		"payload": {"hello": "world"},
	}
	resp = client.post("/events", json=body)
	assert resp.status_code == 200
	data = resp.json()
	assert data["status"] == "ok"
	assert data["event_id"] == "evt-123"
	assert "stored_at" in data


def test_post_events_without_event_id_generates_one() -> None:
	client = TestClient(app)
	body = {
		"source": "zapier",
		"payload": {"hello": "world"},
	}
	resp = client.post("/events", json=body)
	assert resp.status_code == 200
	data = resp.json()
	assert data["status"] == "ok"
	assert isinstance(data["event_id"], str) and len(data["event_id"]) > 0


def test_status_shows_updated_events_received_and_last_event() -> None:
	client = TestClient(app)

	# Post first event
	client.post("/events", json={"event_id": "evt-1", "source": "zapier", "payload": {"a": 1}})
	# Post second event
	client.post("/events", json={"event_id": "evt-2", "source": "zapier", "payload": {"b": 2}})

	resp = client.get("/status")
	assert resp.status_code == 200
	data = resp.json()
	assert data["events_received"] == 2
	assert data["last_event"]["event_id"] == "evt-2"
	assert data["last_event"]["source"] == "zapier"
	assert "received_at" in data["last_event"]
	assert data["last_event"]["payload"] == {"b": 2}


