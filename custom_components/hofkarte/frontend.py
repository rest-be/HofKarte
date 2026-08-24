"""Native Home Assistant sidebar panel for HofKarte management."""
from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import async_register_built_in_panel, async_remove_panel
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_PANEL_URL = "hofkarte"
_STATIC_URL = "/api/hofkarte/static"


async def async_setup_frontend_assets(hass: HomeAssistant) -> None:
    """Serve the bundled frontend assets once for the integration."""
    frontend_dir = Path(__file__).parent / "static"
    await hass.http.async_register_static_paths([
        StaticPathConfig(_STATIC_URL, str(frontend_dir), False)
    ])


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Register the HofKarte management panel."""
    if _PANEL_URL in hass.data.get("frontend_panels", {}):
        return
    async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title="HofKarte",
        sidebar_icon="mdi:store-edit",
        frontend_url_path=_PANEL_URL,
        config={
            "_panel_custom": {
                "name": "hofkarte-panel",
                "embed_iframe": False,
                "trust_external": False,
                "js_url": f"{_STATIC_URL}/hofkarte-panel.js",
            }
        },
        require_admin=True,
    )


def async_remove_frontend(hass: HomeAssistant) -> None:
    """Remove the panel during config-entry unload."""
    if _PANEL_URL in hass.data.get("frontend_panels", {}):
        async_remove_panel(hass, _PANEL_URL)
