"""Camera entity für das Hauptbild eines Hofladens.

Bietet das erste gültige Bild eines Hofladens als Camera-Entity an,
wenn ein Hauptbild vorhanden ist. Dies ermöglicht eine saubere Darstellung
in Home Assistants Lovelace-UI sowie programmatischen Zugriff über die
Camera-Plattform.

Camera Entities sind in Home Assistant der Standard für Remote-Images.
Das hat mehrere Vorteile:
- Native Caching und Image-Handling durch HA
- Lovelace zeigt Camera Entities standardmäßig mit Vollbild-Viewer
- Bessere Integration mit Automationen und Services
- Weniger Speicherverbrauch als lokale Bildkopien
"""

from __future__ import annotations

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HofKarteUpdateCoordinator
from .entity import HofKarteEntity, async_setup_hofladen_entities
from .images import get_main_image_url, is_valid_image_url
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from aiohttp import ClientTimeout, ClientError
import asyncio


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Camera entity für alle aktuellen und künftigen Hofläden einrichten."""
    coordinator: HofKarteUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entry.async_on_unload(
        async_setup_hofladen_entities(
            coordinator,
            async_add_entities,
            [HofKarteMainImageCamera],
        )
    )


class HofKarteMainImageCamera(HofKarteEntity, Camera):
    """Camera entity für das Hauptbild eines Hofladens.

    Bietet das erste gültige Bild als Camera an, falls vorhanden.
    Falls kein Bild existiert oder alle Bilder ungültig sind,
    wird die Entity nicht verfügbar sein.
    """

    _attr_name = "Hauptbild"

    def __init__(
        self, coordinator: HofKarteUpdateCoordinator, hofladen_id: str
    ) -> None:
        super().__init__(coordinator, hofladen_id)
        self._attr_unique_id = f"{DOMAIN}_{hofladen_id}_hauptbild"

    @property
    def available(self) -> bool:
        """Entity ist nur verfügbar, wenn ein gültiges Bild existiert."""
        hofladen = self.hofladen
        if hofladen is None:
            return False
        return get_main_image_url(hofladen.bilder) is not None

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Bild vom Hofladen abrufen.

        Home Assistant kümmert sich um die Skalierung und das Caching.
        Diese Implementierung delegiert an Home Assistants built-in
        Image-Fetching, um lokale Datei-Zugriffe oder andere
        Sicherheitsprobleme zu vermeiden.
        """
        hofladen = self.hofladen
        if hofladen is None:
            return None

        image_url = get_main_image_url(hofladen.bilder)
        if not image_url:
            return None

        return await self._async_fetch_image(image_url)

    async def _async_fetch_image(self, url: str) -> bytes | None:
        """Image von einer Remote-URL abrufen (HA shared session, safety checks)."""
        session = async_get_clientsession(self.hass)
        timeout = ClientTimeout(total=10)
        try:
            async with session.get(url, timeout=timeout) as resp:
                # Nach Redirects: final host prüfen (SSRF-Schutz)
                final_url = str(resp.url)
                if not is_valid_image_url(final_url):
                    return None
                content_type = (resp.headers.get("Content-Type") or "").lower()
                if not content_type.startswith("image/"):
                    return None
                if resp.status == 200:
                    return await resp.read()
                return None
        except (asyncio.TimeoutError, ClientError):
            # Netzwerkfehler, Timeout, etc. – robust handhaben
            return None
