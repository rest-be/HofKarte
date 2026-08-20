"""Die HofKarte-Integration für Home Assistant.

Diese Einheit stellt ausschliesslich das ladbare Grundgerüst der Integration
bereit. Config Flow, Datenmodell, Coordinator und Entities folgen in späteren
Einheiten.
"""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the HofKarte integration (YAML-Grundgerüst, keine Fachlogik).

    In dieser Einheit gibt es noch keinen Config Flow und keine
    Config Entries (folgt in Einheit 2). Diese Funktion sorgt lediglich
    dafür, dass Home Assistant die Domain ``hofkarte`` als bekannte
    Integration erkennt und fehlerfrei lädt.
    """
    hass.data.setdefault(DOMAIN, {})
    _LOGGER.debug("HofKarte-Grundgerüst geladen (Domain: %s)", DOMAIN)
    return True
