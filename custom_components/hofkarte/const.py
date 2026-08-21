"""Konstanten für die HofKarte-Integration."""

from datetime import timedelta

DOMAIN = "hofkarte"

# Config Flow / Config Entry
DEFAULT_NAME = "HofKarte"

# Coordinator / Datenabruf
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=15)
DEFAULT_FETCH_TIMEOUT_SECONDS = 30
