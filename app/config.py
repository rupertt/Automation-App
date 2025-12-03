from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
	"""Basic runtime configuration derived from environment variables."""

	port: int = 8000
	env: str = "dev"


def get_settings() -> Settings:
	"""Load settings from environment with sensible defaults."""
	port_raw = os.getenv("PORT", "8000")
	env = os.getenv("ENV", "dev")
	try:
		port = int(port_raw)
	except ValueError:
		port = 8000
	return Settings(port=port, env=env)


