"""Home-Assistant-Actions für HofKarte (Einheit 10).

Zwei Actions, die sich sinnvoll als Service darstellen lassen und
bestehende Sensorwerte nicht duplizieren:

- ``hofkarte.refresh``: Hofladen-Daten über den Coordinator neu laden.
- ``hofkarte.search``: Hofläden nach Begriff und Fachfiltern durchsuchen
  (Antwort nur bei ``return_response``).

CRUD der Hofläden bleibt der grafischen Verwaltungsoberfläche vorbehalten
(siehe ``management.py`` / ``frontend.py``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import voluptuous as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .attributes import build_sortiment_attributes
from .const import (
    ATTR_GEOEFFNET,
    ATTR_KATEGORIE,
    ATTR_MERKMAL,
    ATTR_PRODUKT,
    ATTR_SUCHBEGRIFF,
    ATTR_VERKAUFSART,
    ATTR_ZAHLUNGSART,
    DOMAIN,
    SERVICE_REFRESH,
    SERVICE_SEARCH,
)
from .management import _get_coordinator
from .models import Hofladen
from .opening_hours import is_open
from .search import filter_hoflaeden

SEARCH_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_SUCHBEGRIFF): cv.string,
        vol.Optional(ATTR_KATEGORIE): cv.string,
        vol.Optional(ATTR_PRODUKT): cv.string,
        vol.Optional(ATTR_VERKAUFSART): cv.string,
        vol.Optional(ATTR_ZAHLUNGSART): cv.string,
        vol.Optional(ATTR_MERKMAL): cv.string,
        vol.Optional(ATTR_GEOEFFNET): cv.boolean,
    },
    extra=vol.PREVENT_EXTRA,
)

REFRESH_SCHEMA = vol.Schema({}, extra=vol.PREVENT_EXTRA)


def _serialize_search_result(hofladen: Hofladen, now: datetime) -> dict[str, Any]:
    """Kompakte, JSON-taugliche Trefferzeile für Automationen."""
    status = is_open(hofladen, now)
    return {
        "id": hofladen.id,
        "name": hofladen.name,
        "beschreibung": hofladen.beschreibung,
        "adresse": hofladen.adresse,
        "plz": hofladen.plz,
        "ort": hofladen.ort,
        "land": hofladen.land,
        "latitude": hofladen.latitude,
        "longitude": hofladen.longitude,
        "geoeffnet": status,
        **build_sortiment_attributes(hofladen),
    }


async def _async_handle_refresh(call: ServiceCall) -> None:
    """Hofladen-Daten über den bestehenden Coordinator neu abrufen."""
    try:
        coordinator = _get_coordinator(call.hass)
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err

    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        raise HomeAssistantError(
            "Die Hofladen-Daten konnten nicht aktualisiert werden."
        )


async def _async_handle_search(call: ServiceCall) -> ServiceResponse:
    """Hofläden anhand der Action-Parameter filtern und zurückgeben."""
    try:
        coordinator = _get_coordinator(call.hass)
    except ValueError as err:
        raise HomeAssistantError(str(err)) from err

    if coordinator.data is None:
        raise HomeAssistantError("Es sind noch keine Hofladen-Daten geladen.")

    now = dt_util.now()
    data = call.data
    geoeffnet = data.get(ATTR_GEOEFFNET)

    try:
        treffer = filter_hoflaeden(
            coordinator.data.values(),
            suchbegriff=data.get(ATTR_SUCHBEGRIFF),
            kategorie=data.get(ATTR_KATEGORIE),
            produkt=data.get(ATTR_PRODUKT),
            verkaufsart=data.get(ATTR_VERKAUFSART),
            zahlungsart=data.get(ATTR_ZAHLUNGSART),
            merkmal=data.get(ATTR_MERKMAL),
            geoeffnet=geoeffnet,
            now=now if geoeffnet is not None else None,
        )
    except ValueError as err:
        raise ServiceValidationError(str(err)) from err

    return {
        "count": len(treffer),
        "hoflaeden": [_serialize_search_result(hofladen, now) for hofladen in treffer],
    }


@callback
def async_register_services(hass: HomeAssistant) -> None:
    """Domain-weite Actions einmalig registrieren."""
    if hass.services.has_service(DOMAIN, SERVICE_REFRESH):
        return

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        _async_handle_refresh,
        schema=REFRESH_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEARCH,
        _async_handle_search,
        schema=SEARCH_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
