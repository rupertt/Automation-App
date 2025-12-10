from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
	"""Basic runtime configuration derived from environment variables."""

	port: int = 8000
	env: str = "dev"
	forward_url: str | None = None


def get_settings() -> Settings:
	"""Load settings from environment with sensible defaults."""
	port_raw = os.getenv("PORT", "8000")
	env = os.getenv("ENV", "dev")
	forward_url = os.getenv("ZAPIER_FORWARD_URL") or os.getenv("FORWARD_URL")
	try:
		port = int(port_raw)
	except ValueError:
		port = 8000
	return Settings(port=port, env=env, forward_url=forward_url)


