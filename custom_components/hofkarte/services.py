"""Home-Assistant-Actions (Services) für HofKarte.

Kapselt ausschliesslich die Anbindung der Fachfunktion aus ``search.py``
an eine Home-Assistant-Action: Schema-Validierung des Service-Aufrufs,
Ermittlung des (einzigen) Coordinators und Aufbau der Rückgabedaten.
Enthält selbst keine Such-/Filterlogik.

Home Assistant stellt mit der eingebauten Action
``homeassistant.update_entity`` bereits eine allgemeine Möglichkeit
bereit, coordinator-basierte Entities (wie alle HofKarte-Entities, siehe
``entity.py``) gezielt zu aktualisieren. Eine eigene
„Hofladen-Daten aktualisieren“-Action würde dies nur unnötig
duplizieren und wird daher bewusst **nicht** implementiert (Regeln
dieser Einheit: „Keine Actions bauen, die ... unnötig duplizieren“).

Analog wird auf separate Actions je Filterdimension (Angebot,
Verkaufsart, Zahlungsart, Merkmal) verzichtet – eine einzige, klar
strukturierte Such-Action mit mehreren optionalen, UND-verknüpften
Filterparametern deckt alle in der Einheit genannten Fälle ab, ohne
naheliegend redundanten Code zu erzeugen.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import HofKarteUpdateCoordinator
from .opening_hours import is_open
from .search import find_hoflaeden

SERVICE_HOFLAEDEN_SUCHEN = "hoflaeden_suchen"

_SERVICE_HOFLAEDEN_SUCHEN_SCHEMA = vol.Schema(
    {
        vol.Optional("suchbegriff"): cv.string,
        vol.Optional("angebot"): cv.string,
        vol.Optional("verkaufsart"): cv.string,
        vol.Optional("zahlungsart"): cv.string,
        vol.Optional("merkmal"): cv.string,
        vol.Optional("nur_geoeffnet"): cv.boolean,
    }
)


def _get_coordinator(hass: HomeAssistant) -> HofKarteUpdateCoordinator:
    """Den (einzigen) HofKarte-Coordinator ermitteln.

    HofKarte ist als Single-Instance-Integration ausgelegt (siehe
    Einheit 2); der Zugriff über den einzigen Eintrag ist daher
    eindeutig – analog zu ``management._get_coordinator``.
    """
    entries = list(hass.data.get(DOMAIN, {}).values())
    if len(entries) != 1:
        raise HomeAssistantError("HofKarte ist nicht (oder mehrfach) eingerichtet.")
    return entries[0]


def _hofladen_zu_ergebnis_eintrag(hofladen: Any, now) -> dict[str, Any]:
    """Ein Suchtreffer als knapper, JSON-tauglicher Datensatz.

    Bewusst keine vollständige Kopie aller Hofladen-Felder – nur eine
    kompakte, für Automationen unmittelbar nützliche Auswahl
    (Identifikation, Anzeigename, aktueller Öffnungsstatus).
    """
    return {
        "id": hofladen.id,
        "name": hofladen.name,
        "geoeffnet": is_open(hofladen, now),
    }


async def _async_hoflaeden_suchen(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Service-Handler für ``hofkarte.hoflaeden_suchen``."""
    coordinator = _get_coordinator(hass)

    nur_geoeffnet = call.data.get("nur_geoeffnet")
    now = dt_util.now()

    treffer = find_hoflaeden(
        coordinator.data.values() if coordinator.data else [],
        suchbegriff=call.data.get("suchbegriff"),
        angebot=call.data.get("angebot"),
        verkaufsart=call.data.get("verkaufsart"),
        zahlungsart=call.data.get("zahlungsart"),
        merkmal=call.data.get("merkmal"),
        nur_geoeffnet=nur_geoeffnet,
        now=now if nur_geoeffnet is not None else None,
    )

    return {
        "anzahl_treffer": len(treffer),
        "hoflaeden": [
            _hofladen_zu_ergebnis_eintrag(hofladen, now) for hofladen in treffer
        ],
    }


def async_register_services(hass: HomeAssistant) -> None:
    """HofKarte-Actions registrieren.

    Wird einmalig aus ``__init__.async_setup`` aufgerufen (Domain-Ebene,
    analog zu ``management.async_register_websocket_commands`` –
    Actions sind wie WebSocket-Befehle nicht an eine einzelne Config
    Entry gebunden).
    """

    async def _service_handler(call: ServiceCall) -> ServiceResponse:
        # Eine eigene async-Funktion (statt einer lambda, die lediglich
        # eine Coroutine zurückgibt) ist hier notwendig: Home Assistant
        # erkennt den Service-Handler nur dann korrekt als Koroutinen-
        # funktion und awaitet ihn entsprechend, wenn er selbst mit
        # ``async def`` definiert ist. Eine lambda-Hülle würde
        # stattdessen die (nicht ausgeführte) Coroutine als Rückgabewert
        # liefern.
        return await _async_hoflaeden_suchen(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_HOFLAEDEN_SUCHEN,
        _service_handler,
        schema=_SERVICE_HOFLAEDEN_SUCHEN_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
