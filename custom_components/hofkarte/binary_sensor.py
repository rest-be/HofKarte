"""Binary Sensor „Geöffnet“ für Hofläden."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import HofKarteUpdateCoordinator
from .entity import HofKarteEntity, async_setup_hofladen_entities
from .opening_hours import is_open


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Binary Sensors für alle aktuellen und künftigen Hofläden einrichten."""
    coordinator: HofKarteUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entry.async_on_unload(
        async_setup_hofladen_entities(
            coordinator,
            async_add_entities,
            [HofKarteGeoeffnetBinarySensor],
        )
    )


class HofKarteGeoeffnetBinarySensor(HofKarteEntity, BinarySensorEntity):
    """Zeigt an, ob ein Hofladen aktuell geöffnet ist.

    Es existiert keine passende Home-Assistant-``BinarySensorDeviceClass``
    für „Geschäft geöffnet“ – die vorhandenen Klassen (z. B. ``OPENING``)
    beziehen sich auf physische Öffnungen wie Türen oder Fenster. Es wird
    daher bewusst keine Device Class gesetzt, statt eine unpassende
    Semantik zu erfinden.
    """

    _attr_name = "Geöffnet"

    def __init__(
        self, coordinator: HofKarteUpdateCoordinator, hofladen_id: str
    ) -> None:
        super().__init__(coordinator, hofladen_id)
        self._attr_unique_id = f"{DOMAIN}_{hofladen_id}_geoeffnet"

    @property
    def is_on(self) -> bool | None:
        """Aktueller Öffnungsstatus.

        Berechnet über ``opening_hours.is_open``. Liefert ``None``
        (Zustand „unbekannt“), wenn der Hofladen nicht (mehr) existiert
        oder keinerlei Öffnungszeiten hinterlegt sind.
        """
        hofladen = self.hofladen
        if hofladen is None:
            return None
        return is_open(hofladen, dt_util.now())
