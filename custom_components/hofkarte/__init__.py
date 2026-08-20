"""Die HofKarte-Integration für Home Assistant.

Die Einrichtung erfolgt ausschliesslich über den Config Flow (siehe
``config_flow.py``). Eine YAML-Konfiguration ist nicht vorgesehen.

Diese Einheit stellt den Config-Entry-Lifecycle bereit. Datenmodell,
Coordinator und Entities folgen in späteren Einheiten.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Es werden noch keine Plattformen (Sensoren o. Ä.) benötigt.
PLATFORMS: list[str] = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HofKarte from a config entry.

    In dieser Einheit gibt es noch kein Datenmodell und keinen Coordinator.
    Die Funktion registriert lediglich den Eintrag in ``hass.data``, damit
    spätere Einheiten (z. B. Data Layer, Coordinator) darauf aufbauen können.
    """
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    if PLATFORMS:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug("HofKarte-Config-Entry eingerichtet: %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a HofKarte config entry."""
    unload_ok = True
    if PLATFORMS:
        unload_ok = await hass.config_entries.async_unload_platforms(
            entry, PLATFORMS
        )

    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)

    return unload_ok
