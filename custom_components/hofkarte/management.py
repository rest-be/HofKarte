"""Backend support for the HofKarte management panel."""
from __future__ import annotations

from datetime import date, time
from typing import Any
from uuid import uuid4

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
import voluptuous as vol

from .const import DOMAIN
from .coordinator import HofKarteUpdateCoordinator
from .data_provider import (
    DuplicateHofladenIdError,
    HofladenNotFoundError,
    MutableHofladenDataProvider,
)
from .parsing import HofladenValidationError, parse_hofladen

WS_LIST = "hofkarte/management/list"
WS_SAVE = "hofkarte/management/save"
WS_DELETE = "hofkarte/management/delete"


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
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
    entries = hass.data.get(DOMAIN, {})
    if len(entries) != 1:
        raise ValueError("HofKarte ist nicht eingerichtet oder nicht eindeutig geladen.")
    return next(iter(entries.values()))


@websocket_api.websocket_command({vol.Required("type"): WS_LIST})
@websocket_api.require_admin
@callback
def ws_list(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Return all current Hofläden."""
    coordinator = _get_coordinator(hass)
    connection.send_result(msg["id"], {"hoflaeden": [_serialize_hofladen(v) for v in coordinator.data.values()]})


@websocket_api.websocket_command(
    {vol.Required("type"): WS_SAVE, vol.Required("hofladen"): dict}
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_save(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Create or replace a Hofladen."""
    coordinator = _get_coordinator(hass)
    raw = dict(msg["hofladen"])
    try:
        if not raw.get("id"):
            raw["id"] = f"hofladen-{uuid4().hex}"
        parsed = parse_hofladen(raw)
        provider = coordinator._provider  # pylint: disable=protected-access
        if not isinstance(provider, MutableHofladenDataProvider):
            raise NotImplementedError("Der Data Provider unterstützt keine Schreibzugriffe.")
        if raw["id"] in coordinator.data:
            await provider.async_update_raw_hofladen(raw["id"], raw)
        else:
            await provider.async_add_raw_hofladen(raw)
        await coordinator.async_refresh()
    except (HofladenValidationError, DuplicateHofladenIdError, HofladenNotFoundError, NotImplementedError) as err:
        connection.send_error(msg["id"], "invalid_data", str(err))
        return
    connection.send_result(msg["id"], {"hofladen": _serialize_hofladen(parsed)})


@websocket_api.websocket_command(
    {vol.Required("type"): WS_DELETE, vol.Required("hofladen_id"): str}
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_delete(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Delete a Hofladen from persistent storage."""
    coordinator = _get_coordinator(hass)
    provider = coordinator._provider  # pylint: disable=protected-access
    if not isinstance(provider, MutableHofladenDataProvider):
        connection.send_error(msg["id"], "not_supported", "Der Data Provider unterstützt keine Schreibzugriffe.")
        return
    try:
        raw = await provider.async_fetch_raw_hoflaeden()
        if not any(item.get("id") == msg["hofladen_id"] for item in raw):
            raise HofladenNotFoundError(msg["hofladen_id"])
        await provider.async_delete_raw_hofladen(msg["hofladen_id"])
        await coordinator.async_refresh()
    except HofladenNotFoundError as err:
        connection.send_error(msg["id"], "not_found", str(err))
        return
    connection.send_result(msg["id"], {})


def async_register_websocket_commands(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_list)
    websocket_api.async_register_command(hass, ws_save)
    websocket_api.async_register_command(hass, ws_delete)
