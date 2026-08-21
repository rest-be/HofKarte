"""Die HofKarte-Integration für Home Assistant.

Die Einrichtung erfolgt ausschliesslich über den Config Flow (siehe
``config_flow.py``). Eine YAML-Konfiguration ist nicht vorgesehen.

Diese Einheit hängt den zentralen ``HofKarteUpdateCoordinator`` in den
Config-Entry-Lifecycle ein. Entities folgen in einer späteren Einheit.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import HofKarteUpdateCoordinator
from .data_provider import StaticTestDataProvider

_LOGGER = logging.getLogger(__name__)

# Es werden noch keine Plattformen (Sensoren o. Ä.) benötigt.
PLATFORMS: list[str] = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HofKarte from a config entry.

    Erstellt den zentralen Coordinator, führt den initialen Datenabruf
    durch und stellt den Coordinator für spätere Einheiten (Entities)
    unter ``hass.data[DOMAIN][entry.entry_id]`` bereit.

    Schlägt der initiale Abruf fehl, hebt
    ``async_config_entry_first_refresh`` automatisch ``ConfigEntryNotReady``
    aus; Home Assistant versucht die Einrichtung dann später erneut.
    """
    # Der Data Provider ist bewusst eine Testdaten-Implementierung, da die
    # tatsächliche Datenquelle noch nicht feststeht (offene
    # Architekturentscheidung, siehe data_provider.py und README).
    provider = StaticTestDataProvider()
    coordinator = HofKarteUpdateCoordinator(hass, provider)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

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
