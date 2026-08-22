"""Tests für die Sensoren „Nächste Öffnung“ und „Nächste Schliessung“."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hofkarte.const import DOMAIN
from custom_components.hofkarte.coordinator import HofKarteUpdateCoordinator
from custom_components.hofkarte.data_provider import HofladenDataProvider
from custom_components.hofkarte.sensor import (
    HofKarteNaechsteOeffnungSensor,
    HofKarteNaechsteSchliessungSensor,
)


def _make_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, title="HofKarte", data={CONF_NAME: "HofKarte"}
    )
    entry.add_to_hass(hass)
    return entry


class _FakeProvider(HofladenDataProvider):
    def __init__(self, raw_hoflaeden: list[dict[str, Any]]) -> None:
        self.raw_hoflaeden = raw_hoflaeden

    async def async_fetch_raw_hoflaeden(self) -> list[dict[str, Any]]:
        return self.raw_hoflaeden


async def test_both_sensors_created_for_default_test_data(
    hass: HomeAssistant,
) -> None:
    """Für den Platzhalter-Hofladen müssen beide Sensoren entstehen."""
    entry = _make_entry(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    oeffnung_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DOMAIN}_platzhalter-hofladen_naechste_oeffnung"
    )
    schliessung_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DOMAIN}_platzhalter-hofladen_naechste_schliessung"
    )

    assert oeffnung_id is not None
    assert schliessung_id is not None
    # Solange Einheit 7 nicht implementiert ist, ist der Zustand "unbekannt".
    assert hass.states.get(oeffnung_id).state == "unknown"
    assert hass.states.get(schliessung_id).state == "unknown"


async def test_sensors_have_timestamp_device_class(hass: HomeAssistant) -> None:
    """Beide Sensoren müssen die Device Class TIMESTAMP tragen."""
    entry = _make_entry(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    oeffnung_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DOMAIN}_platzhalter-hofladen_naechste_oeffnung"
    )
    state = hass.states.get(oeffnung_id)

    assert state.attributes.get("device_class") == SensorDeviceClass.TIMESTAMP


async def test_unique_ids_follow_expected_pattern(hass: HomeAssistant) -> None:
    """Die unique_ids müssen stabil und eindeutig aus der Hofladen-ID gebildet werden."""
    provider = _FakeProvider([{"id": "hof-1", "name": "Hofladen Eins"}])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    oeffnung = HofKarteNaechsteOeffnungSensor(coordinator, "hof-1")
    schliessung = HofKarteNaechsteSchliessungSensor(coordinator, "hof-1")

    assert oeffnung.unique_id == f"{DOMAIN}_hof-1_naechste_oeffnung"
    assert schliessung.unique_id == f"{DOMAIN}_hof-1_naechste_schliessung"


async def test_native_value_none_when_hofladen_present(hass: HomeAssistant) -> None:
    """Solange Einheit 7 nicht implementiert ist, ist der Wert unbekannt."""
    provider = _FakeProvider([{"id": "hof-1", "name": "Hofladen Eins"}])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    oeffnung = HofKarteNaechsteOeffnungSensor(coordinator, "hof-1")
    schliessung = HofKarteNaechsteSchliessungSensor(coordinator, "hof-1")

    assert oeffnung.native_value is None
    assert schliessung.native_value is None


async def test_native_value_none_when_hofladen_missing(hass: HomeAssistant) -> None:
    """Ohne Hofladen darf kein Wert erfunden werden."""
    provider = _FakeProvider([])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    oeffnung = HofKarteNaechsteOeffnungSensor(coordinator, "unbekannt")

    assert oeffnung.native_value is None
    assert oeffnung.available is False


async def test_newly_added_hofladen_gets_both_sensors(hass: HomeAssistant) -> None:
    """Ein über den Coordinator hinzugefügter Hofladen erhält automatisch
    beide Sensoren, ohne dass ein Reload nötig ist."""
    entry = _make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_add_hofladen({"id": "hof-neu", "name": "Neuer Hofladen"})
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    oeffnung_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DOMAIN}_hof-neu_naechste_oeffnung"
    )
    schliessung_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DOMAIN}_hof-neu_naechste_schliessung"
    )

    assert oeffnung_id is not None
    assert schliessung_id is not None
