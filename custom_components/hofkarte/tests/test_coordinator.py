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
    HofladenNotFoundError,
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


# ---------------------------------------------------------------------------
# async_update_hofladen_sortiment (Ergänzung zu Einheit 8: User Editierbar)
# ---------------------------------------------------------------------------


async def test_update_sortiment_aendert_gewaehltes_feld(hass: HomeAssistant) -> None:
    """Nur das übergebene Feld darf geändert werden, andere bleiben erhalten."""
    provider = StaticTestDataProvider(
        raw_hoflaeden=[
            {
                "id": "hof-1",
                "name": "Hofladen Eins",
                "merkmale": [{"id": "bio", "name": "Bio"}],
                "zahlungsarten": [{"id": "bar", "name": "Bargeld"}],
            }
        ]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    ergebnis = await coordinator.async_update_hofladen_sortiment(
        "hof-1",
        zahlungsarten=[
            {"id": "bar", "name": "Bargeld"},
            {"id": "twint", "name": "TWINT"},
        ],
    )

    assert [z.name for z in ergebnis.zahlungsarten] == ["Bargeld", "TWINT"]
    assert [m.name for m in ergebnis.merkmale] == ["Bio"]  # unverändert

    # Auch im Coordinator (nach Refresh) muss die Änderung sichtbar sein.
    aktualisiert = coordinator.data["hof-1"]
    assert [z.name for z in aktualisiert.zahlungsarten] == ["Bargeld", "TWINT"]
    assert [m.name for m in aktualisiert.merkmale] == ["Bio"]


async def test_update_sortiment_mehrere_fachbereiche_gleichzeitig(
    hass: HomeAssistant,
) -> None:
    """Mehrere Fachbereiche müssen in einem Aufruf gemeinsam änderbar sein."""
    provider = StaticTestDataProvider(
        raw_hoflaeden=[{"id": "hof-1", "name": "Hofladen Eins"}]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    ergebnis = await coordinator.async_update_hofladen_sortiment(
        "hof-1",
        kategorien=[{"id": "gemuese", "name": "Gemüse"}],
        verkaufsarten=[{"id": "hofladen", "name": "Hofladen"}],
        merkmale=[{"id": "bio", "name": "Bio"}],
    )

    assert [k.name for k in ergebnis.kategorien] == ["Gemüse"]
    assert [v.name for v in ergebnis.verkaufsarten] == ["Hofladen"]
    assert [m.name for m in ergebnis.merkmale] == ["Bio"]


async def test_update_sortiment_leere_liste_leert_feld(hass: HomeAssistant) -> None:
    """Eine explizit übergebene leere Liste muss das Feld leeren (kein 'unverändert')."""
    provider = StaticTestDataProvider(
        raw_hoflaeden=[
            {
                "id": "hof-1",
                "name": "Hofladen Eins",
                "merkmale": [{"id": "bio", "name": "Bio"}],
            }
        ]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    ergebnis = await coordinator.async_update_hofladen_sortiment(
        "hof-1", merkmale=[]
    )

    assert ergebnis.merkmale == ()


async def test_update_sortiment_ohne_parameter_aendert_nichts(
    hass: HomeAssistant,
) -> None:
    """Werden keine Parameter gesetzt, bleibt der Hofladen unverändert."""
    provider = StaticTestDataProvider(
        raw_hoflaeden=[
            {
                "id": "hof-1",
                "name": "Hofladen Eins",
                "merkmale": [{"id": "bio", "name": "Bio"}],
            }
        ]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    ergebnis = await coordinator.async_update_hofladen_sortiment("hof-1")

    assert [m.name for m in ergebnis.merkmale] == ["Bio"]


async def test_update_sortiment_unbekannte_id_wirft_fehler(
    hass: HomeAssistant,
) -> None:
    """Eine nicht existierende Hofladen-ID muss abgelehnt werden."""
    provider = StaticTestDataProvider(raw_hoflaeden=[])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    with pytest.raises(HofladenNotFoundError):
        await coordinator.async_update_hofladen_sortiment(
            "unbekannt", merkmale=[{"id": "bio", "name": "Bio"}]
        )


async def test_update_sortiment_ungueltige_daten_wirft_fehler_und_aendert_nichts(
    hass: HomeAssistant,
) -> None:
    """Ungültige Werte müssen abgelehnt werden, ohne den Provider zu verändern
    (Fail-Fast, analog zu async_add_hofladen)."""
    provider = StaticTestDataProvider(
        raw_hoflaeden=[{"id": "hof-1", "name": "Hofladen Eins"}]
    )
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    with pytest.raises(HofladenValidationError):
        await coordinator.async_update_hofladen_sortiment(
            "hof-1", merkmale=[{"id": "bio"}]  # 'name' fehlt
        )

    # Der Datensatz darf durch den fehlgeschlagenen Versuch nicht verändert
    # worden sein.
    unveraendert = coordinator.data["hof-1"]
    assert unveraendert.merkmale == ()


async def test_update_sortiment_nicht_unterstuetzt_bei_read_only_provider(
    hass: HomeAssistant,
) -> None:
    """Ein rein lesender Provider muss einen klaren Fehler liefern."""
    provider = _FakeProvider(raw_hoflaeden=[{"id": "hof-1", "name": "Hofladen Eins"}])
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()

    with pytest.raises(NotImplementedError):
        await coordinator.async_update_hofladen_sortiment(
            "hof-1", merkmale=[{"id": "bio", "name": "Bio"}]
        )
