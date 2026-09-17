"""Backend support for the HofKarte management panel.

Alle Schreibzugriffe laufen ausschliesslich über die öffentlichen
``HofKarteUpdateCoordinator``-Methoden (``async_save_hofladen``,
``async_delete_hofladen``) – nicht direkt über den zugrunde liegenden
``HofladenDataProvider``. Das hält die in ``coordinator.py``
implementierte Fail-Fast-Validierung und Refresh-Logik an einer
einzigen Stelle, statt sie hier zu duplizieren.
"""

from __future__ import annotations

from datetime import date, time
from typing import Any
from uuid import uuid4

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .coordinator import HofKarteUpdateCoordinator
from .data_provider import HofladenNotFoundError
from .parsing import HofladenValidationError

WS_LIST = "hofkarte/management/list"
WS_SAVE = "hofkarte/management/save"
WS_DELETE = "hofkarte/management/delete"


def _json_value(value: Any) -> Any:
    if isinstance(value, time):
        # time.isoformat() liefert standardmässig Sekunden ("08:00:00").
        # Öffnungszeiten werden ausschliesslich über type="time"-Felder
        # ohne Sekundenauflösung erfasst (siehe hofkarte-panel.js) – die
        # Darstellung soll das widerspiegeln (hh:mm statt hh:mm:ss).
        return value.isoformat(timespec="minutes")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if hasattr(value, "__dataclass_fields__"):
        return {
            field: _json_value(getattr(value, field))
            for field in value.__dataclass_fields__
        }
    return value


def _serialize_hofladen(hofladen: Any) -> dict[str, Any]:
    return _json_value(hofladen)


def _get_coordinator(hass: HomeAssistant) -> HofKarteUpdateCoordinator:
    """Den (einzigen) HofKarte-Coordinator ermitteln.

    Wirft ``ValueError``, falls HofKarte nicht (oder mehrfach) geladen
    ist. Aufrufer müssen dies abfangen und als sauberen WebSocket-Fehler
    zurückmelden statt die Exception unbehandelt durchzureichen.
    """
    entries = hass.data.get(DOMAIN, {})
    if len(entries) != 1:
        raise ValueError(
            "HofKarte ist nicht eingerichtet oder nicht eindeutig geladen."
        )
    return next(iter(entries.values()))


@websocket_api.websocket_command({vol.Required("type"): WS_LIST})
@websocket_api.require_admin
@callback
def ws_list(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Return all current Hofläden."""
    try:
        coordinator = _get_coordinator(hass)
    except ValueError as err:
        connection.send_error(msg["id"], "not_ready", str(err))
        return

    connection.send_result(
        msg["id"],
        {"hoflaeden": [_serialize_hofladen(v) for v in coordinator.data.values()]},
    )


@websocket_api.websocket_command(
    {vol.Required("type"): WS_SAVE, vol.Required("hofladen"): dict}
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_save(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Create or update a Hofladen (delegiert vollständig an den Coordinator)."""
    try:
        coordinator = _get_coordinator(hass)
    except ValueError as err:
        connection.send_error(msg["id"], "not_ready", str(err))
        return

    raw = dict(msg["hofladen"])
    if not raw.get("id"):
        raw["id"] = f"hofladen-{uuid4().hex}"

    try:
        parsed = await coordinator.async_save_hofladen(raw)
    except HofladenValidationError as err:
        connection.send_error(msg["id"], "invalid_data", str(err))
        return
    except NotImplementedError as err:
        connection.send_error(msg["id"], "not_supported", str(err))
        return

    connection.send_result(msg["id"], {"hofladen": _serialize_hofladen(parsed)})


@websocket_api.websocket_command(
    {vol.Required("type"): WS_DELETE, vol.Required("hofladen_id"): str}
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_delete(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Delete a Hofladen from persistent storage (delegiert an den Coordinator)."""
    try:
        coordinator = _get_coordinator(hass)
    except ValueError as err:
        connection.send_error(msg["id"], "not_ready", str(err))
        return

    try:
        await coordinator.async_delete_hofladen(msg["hofladen_id"])
    except NotImplementedError as err:
        connection.send_error(msg["id"], "not_supported", str(err))
        return
    except HofladenNotFoundError as err:
        connection.send_error(msg["id"], "not_found", str(err))
        return

    connection.send_result(msg["id"], {})


def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """HofKarte-WebSocket-Befehle registrieren (einmalig, Domain-Ebene)."""
    websocket_api.async_register_command(hass, ws_list)
    websocket_api.async_register_command(hass, ws_save)
    websocket_api.async_register_command(hass, ws_delete)
