from __future__ import annotations

import os
from dataclasses import dataclass

try:
	from dotenv import load_dotenv  # type: ignore
	load_dotenv()
except Exception:
	pass


@dataclass(frozen=True)
class Settings:
	"""Basic runtime configuration derived from environment variables."""

	port: int = 8000
	env: str = "dev"
	forward_url: str | None = None
	forward_original_events: bool = False


def get_settings() -> Settings:
	"""Load settings from environment with sensible defaults."""
	port_raw = os.getenv("PORT", "8000")
	env = os.getenv("ENV", "dev")
	forward_url = os.getenv("ZAPIER_FORWARD_URL") or os.getenv("FORWARD_URL")
	forward_original_raw = os.getenv("FORWARD_ORIGINAL_EVENTS", "false").lower().strip()
	forward_original = forward_original_raw in {"1", "true", "yes", "on"}
	try:
		port = int(port_raw)
	except ValueError:
		port = 8000
	return Settings(port=port, env=env, forward_url=forward_url, forward_original_events=forward_original)


