"""Tests für den HofKarteUpdateCoordinator."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.hofkarte.coordinator import HofKarteUpdateCoordinator
from custom_components.hofkarte.data_provider import (
    DuplicateHofladenIdError,
    HofladenDataProvider,
    StaticTestDataProvider,
)
from custom_components.hofkarte.parsing import HofladenValidationError


class _FakeProvider(HofladenDataProvider):
    """Test-Provider mit konfigurierbarem Verhalten (Daten, Fehler, Delay)."""

    def __init__(
        self,
        raw_hoflaeden: list[dict[str, Any]] | None = None,
        error: Exception | None = None,
        delay: float = 0.0,
    ) -> None:
        self.raw_hoflaeden = raw_hoflaeden if raw_hoflaeden is not None else []
        self.error = error
        self.delay = delay

    async def async_fetch_raw_hoflaeden(self) -> list[dict[str, Any]]:
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.raw_hoflaeden


async def test_successful_update(hass: HomeAssistant) -> None:
    """Ein erfolgreicher Abruf muss validierte Hofladen-Daten liefern."""
    provider = _FakeProvider(
        raw_hoflaeden=[{"id": "hof-1", "name": "Hofladen Eins"}]
    )
    coordinator = HofKarteUpdateCoordinator(
        hass, provider, update_interval=timedelta(minutes=15)
    )

    await coordinator.async_config_entry_first_refresh()

    assert coordinator.last_update_success is True
    assert set(coordinator.data.keys()) == {"hof-1"}
    assert coordinator.data["hof-1"].name == "Hofladen Eins"


async def test_invalid_record_is_skipped_not_fatal(hass: HomeAssistant) -> None:
    """Ein einzelner ungültiger Datensatz darf den gesamten Abruf nicht scheitern lassen."""
    provider = _FakeProvider(
        raw_hoflaeden=[
            {"id": "hof-1", "name": "Gültiger Hofladen"},
            {"name": "Ungültig, keine id"},
        ]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)

    await coordinator.async_config_entry_first_refresh()

    assert coordinator.last_update_success is True
    assert list(coordinator.data.keys()) == ["hof-1"]


async def test_timeout_results_in_update_failed(hass: HomeAssistant) -> None:
    """Eine Zeitüberschreitung beim Abruf muss sauber als Fehler behandelt werden."""
    provider = _FakeProvider(raw_hoflaeden=[], delay=1.0)
    coordinator = HofKarteUpdateCoordinator(
        hass, provider, fetch_timeout_seconds=0.01
    )

    with pytest.raises(ConfigEntryNotReady):
        await coordinator.async_config_entry_first_refresh()

    assert coordinator.last_update_success is False


async def test_provider_error_results_in_update_failed(hass: HomeAssistant) -> None:
    """Ein Fehler der Datenquelle darf Home Assistant nicht blockieren."""
    provider = _FakeProvider(error=RuntimeError("Datenquelle nicht erreichbar"))
    coordinator = HofKarteUpdateCoordinator(hass, provider)

    with pytest.raises(ConfigEntryNotReady):
        await coordinator.async_config_entry_first_refresh()

    assert coordinator.last_update_success is False


async def test_refresh_failure_after_success_keeps_previous_data(
    hass: HomeAssistant,
) -> None:
    """Ein späterer Fehlversuch darf vorhandene Daten aus dem letzten Erfolg
    nicht verwerfen (Availability über ``last_update_success`` abbildbar)."""
    provider = _FakeProvider(raw_hoflaeden=[{"id": "hof-1", "name": "Hofladen"}])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()
    assert coordinator.last_update_success is True

    provider.error = RuntimeError("Vorübergehend nicht erreichbar")
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert coordinator.data is not None
    assert "hof-1" in coordinator.data


async def test_empty_data_source_yields_empty_mapping(hass: HomeAssistant) -> None:
    """Eine leere Datenquelle ist kein Fehler, sondern ein leeres Mapping."""
    provider = _FakeProvider(raw_hoflaeden=[])
    coordinator = HofKarteUpdateCoordinator(hass, provider)

    await coordinator.async_config_entry_first_refresh()

    assert coordinator.last_update_success is True
    assert coordinator.data == {}


async def test_add_hofladen_appears_in_data_after_add(hass: HomeAssistant) -> None:
    """Ein neu hinzugefügter Hofladen muss danach in coordinator.data stehen."""
    provider = StaticTestDataProvider(raw_hoflaeden=[])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()
    assert coordinator.data == {}

    hofladen = await coordinator.async_add_hofladen(
        {"id": "hof-neu", "name": "Neuer Hofladen"}
    )

    assert hofladen.id == "hof-neu"
    assert "hof-neu" in coordinator.data
    assert coordinator.data["hof-neu"].name == "Neuer Hofladen"


async def test_add_hofladen_invalid_data_raises_and_does_not_add(
    hass: HomeAssistant,
) -> None:
    """Ungültige Rohdaten dürfen weder validiert noch zum Provider durchgereicht werden."""
    provider = StaticTestDataProvider(raw_hoflaeden=[])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    with pytest.raises(HofladenValidationError):
        await coordinator.async_add_hofladen({"name": "Ohne ID"})

    assert coordinator.data == {}


async def test_add_hofladen_duplicate_id_raises(hass: HomeAssistant) -> None:
    """Ein Duplikat der ID muss durchgereicht werden, nicht überschrieben."""
    provider = StaticTestDataProvider(
        raw_hoflaeden=[{"id": "hof-1", "name": "Bestehender Hofladen"}]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    with pytest.raises(DuplicateHofladenIdError):
        await coordinator.async_add_hofladen({"id": "hof-1", "name": "Anderer Name"})


async def test_add_hofladen_not_supported_by_read_only_provider(
    hass: HomeAssistant,
) -> None:
    """Ein rein lesender Provider muss einen klaren Fehler liefern."""
    provider = _FakeProvider(raw_hoflaeden=[])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    with pytest.raises(NotImplementedError):
        await coordinator.async_add_hofladen({"id": "hof-neu", "name": "Neu"})
