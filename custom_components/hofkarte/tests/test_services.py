"""Tests für die Home-Assistant-Actions hofkarte.refresh und hofkarte.search."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
import voluptuous as vol
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hofkarte.const import DOMAIN, SERVICE_REFRESH, SERVICE_SEARCH
from custom_components.hofkarte.coordinator import HofKarteUpdateCoordinator
from custom_components.hofkarte.services import async_register_services


def _entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, title="HofKarte", data={CONF_NAME: "HofKarte"}
    )
    entry.add_to_hass(hass)
    return entry


async def _setup(hass: HomeAssistant) -> HofKarteUpdateCoordinator:
    entry = _entry(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN][entry.entry_id]


def _antwort_payload(antwort: dict) -> dict:
    """HA kann die Service-Antwort direkt oder um den Domain-Schlüssel legen."""
    if "count" in antwort and "hoflaeden" in antwort:
        return antwort
    inner = antwort.get(DOMAIN, antwort)
    if "count" in inner:
        return inner
    # Fallback: erste Mapping-Wertebene
    for value in antwort.values():
        if isinstance(value, dict) and "count" in value:
            return value
    return antwort


async def test_services_werden_bei_setup_registriert(hass: HomeAssistant) -> None:
    await _setup(hass)
    assert hass.services.has_service(DOMAIN, SERVICE_REFRESH)
    assert hass.services.has_service(DOMAIN, SERVICE_SEARCH)


async def test_refresh_ohne_config_entry_schlaegt_fehl(hass: HomeAssistant) -> None:
    async_register_services(hass)

    with pytest.raises(HomeAssistantError, match="nicht eingerichtet"):
        await hass.services.async_call(DOMAIN, SERVICE_REFRESH, {}, blocking=True)


async def test_refresh_stosst_coordinator_an(hass: HomeAssistant) -> None:
    coordinator = await _setup(hass)
    original = coordinator.async_refresh
    coordinator.async_refresh = AsyncMock(wraps=original)

    await hass.services.async_call(DOMAIN, SERVICE_REFRESH, {}, blocking=True)

    coordinator.async_refresh.assert_awaited()


async def test_refresh_lehnt_unbekannte_felder_ab(hass: HomeAssistant) -> None:
    await _setup(hass)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, SERVICE_REFRESH, {"unnoetig": True}, blocking=True
        )


async def test_search_ohne_kriterien_liefert_alle(hass: HomeAssistant) -> None:
    coordinator = await _setup(hass)
    await coordinator.async_add_hofladen({"id": "hof-a", "name": "Hof A"})
    await coordinator.async_add_hofladen({"id": "hof-b", "name": "Hof B"})

    antwort = _antwort_payload(
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEARCH,
            {},
            blocking=True,
            return_response=True,
        )
    )

    assert antwort["count"] == 2
    assert {eintrag["id"] for eintrag in antwort["hoflaeden"]} == {"hof-a", "hof-b"}


async def test_search_filtert_nach_begriff_und_fachfeldern(
    hass: HomeAssistant,
) -> None:
    coordinator = await _setup(hass)
    await coordinator.async_add_hofladen(
        {
            "id": "bio-hof",
            "name": "Bio-Hof",
            "ort": "Bern",
            "kategorien": [{"id": "gemuese", "name": "Gemüse"}],
            "produkte": [
                {"id": "apfel", "name": "Äpfel", "kategorie_ids": ["gemuese"]}
            ],
            "zahlungsarten": [{"id": "twint", "name": "TWINT"}],
            "verkaufsarten": [{"id": "sb", "name": "Selbstbedienung"}],
            "merkmale": [{"id": "bio", "name": "Bio"}],
        }
    )
    await coordinator.async_add_hofladen({"id": "anderes", "name": "Anderer Hof"})

    antwort = _antwort_payload(
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEARCH,
            {
                "suchbegriff": "bio",
                "kategorie": "Gemüse",
                "produkt": "Äpfel",
                "zahlungsart": "TWINT",
                "verkaufsart": "Selbstbedienung",
                "merkmal": "Bio",
            },
            blocking=True,
            return_response=True,
        )
    )

    assert antwort["count"] == 1
    treffer = antwort["hoflaeden"][0]
    assert treffer["id"] == "bio-hof"
    assert treffer["ort"] == "Bern"
    assert "Äpfel" in [produkt["name"] for produkt in treffer["produkte"]]
    assert "geoeffnet" in treffer


async def test_search_lehnt_ungueltige_parameter_ab(hass: HomeAssistant) -> None:
    await _setup(hass)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEARCH,
            {"geoeffnet": "vielleicht"},
            blocking=True,
            return_response=True,
        )
