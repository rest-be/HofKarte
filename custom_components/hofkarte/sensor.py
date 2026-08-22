"""Sensoren für Hofläden: nächster Öffnungs- und Schliesszeitpunkt."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import HofKarteUpdateCoordinator
from .entity import HofKarteEntity, async_setup_hofladen_entities
from .opening_hours import get_next_closing, get_next_opening


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sensoren für alle aktuellen und künftigen Hofläden einrichten."""
    coordinator: HofKarteUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entry.async_on_unload(
        async_setup_hofladen_entities(
            coordinator,
            async_add_entities,
            [
                HofKarteNaechsteOeffnungSensor,
                HofKarteNaechsteSchliessungSensor,
            ],
        )
    )


class _HofKarteZeitpunktSensor(HofKarteEntity, SensorEntity):
    """Gemeinsame Basis für die beiden zeitpunktbasierten Sensoren.

    ``TIMESTAMP`` ist die einzige passende Device Class für einen
    zukünftigen Zeitpunkt (nächste Öffnung/Schliessung); ``native_value``
    muss dafür ein zeitzonenbewusstes ``datetime``-Objekt oder ``None``
    liefern – keine erfundenen bzw. naiven Werte.
    """

    _attr_device_class = SensorDeviceClass.TIMESTAMP


class HofKarteNaechsteOeffnungSensor(_HofKarteZeitpunktSensor):
    """Zeitpunkt der nächsten Öffnung eines Hofladens."""

    _attr_name = "Nächste Öffnung"

    def __init__(
        self, coordinator: HofKarteUpdateCoordinator, hofladen_id: str
    ) -> None:
        super().__init__(coordinator, hofladen_id)
        self._attr_unique_id = f"{DOMAIN}_{hofladen_id}_naechste_oeffnung"

    @property
    def native_value(self):
        """Nächster Öffnungszeitpunkt.

        Berechnet über ``opening_hours.get_next_opening``. Liefert
        ``None`` (Zustand „unbekannt“), wenn der Hofladen nicht (mehr)
        existiert oder keinerlei Öffnungszeiten hinterlegt sind.
        """
        hofladen = self.hofladen
        if hofladen is None:
            return None
        return get_next_opening(hofladen, dt_util.now())


class HofKarteNaechsteSchliessungSensor(_HofKarteZeitpunktSensor):
    """Zeitpunkt der nächsten Schliessung eines Hofladens."""

    _attr_name = "Nächste Schliessung"

    def __init__(
        self, coordinator: HofKarteUpdateCoordinator, hofladen_id: str
    ) -> None:
        super().__init__(coordinator, hofladen_id)
        self._attr_unique_id = f"{DOMAIN}_{hofladen_id}_naechste_schliessung"

    @property
    def native_value(self):
        """Nächster Schliesszeitpunkt.

        Berechnet über ``opening_hours.get_next_closing``. Liefert
        ``None`` (Zustand „unbekannt“), wenn der Hofladen nicht (mehr)
        existiert oder keinerlei Öffnungszeiten hinterlegt sind.
        """
        hofladen = self.hofladen
        if hofladen is None:
            return None
        return get_next_closing(hofladen, dt_util.now())
