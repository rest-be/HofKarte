"""Tests für den HofKarte-Data-Provider."""

import pytest

from custom_components.hofkarte.data_provider import (
    DuplicateHofladenIdError,
    HofladenNotFoundError,
    StaticTestDataProvider,
)


async def test_static_provider_returns_default_data() -> None:
    """Ohne explizite Daten liefert der Provider einen Platzhalter-Datensatz."""
    provider = StaticTestDataProvider()

    raw_hoflaeden = await provider.async_fetch_raw_hoflaeden()

    assert len(raw_hoflaeden) == 1
    assert raw_hoflaeden[0]["id"] == "platzhalter-hofladen"


async def test_static_provider_returns_custom_data() -> None:
    """Explizit übergebene Testdaten müssen unverändert zurückgegeben werden."""
    custom_data = [{"id": "hof-x", "name": "Hofladen X"}]
    provider = StaticTestDataProvider(raw_hoflaeden=custom_data)

    raw_hoflaeden = await provider.async_fetch_raw_hoflaeden()

    assert raw_hoflaeden == custom_data
    # Rückgabe muss eine Kopie sein, keine Referenz auf die interne Liste.
    assert raw_hoflaeden is not provider._raw_hoflaeden


async def test_static_provider_add_raw_hofladen() -> None:
    """Ein neuer Hofladen muss beim nächsten Abruf enthalten sein."""
    provider = StaticTestDataProvider(raw_hoflaeden=[])

    await provider.async_add_raw_hofladen({"id": "hof-neu", "name": "Neuer Hofladen"})
    raw_hoflaeden = await provider.async_fetch_raw_hoflaeden()

    assert len(raw_hoflaeden) == 1
    assert raw_hoflaeden[0]["id"] == "hof-neu"


async def test_static_provider_add_raw_hofladen_rejects_duplicate_id() -> None:
    """Eine bereits vorhandene ID darf nicht stillschweigend überschrieben werden."""
    provider = StaticTestDataProvider(
        raw_hoflaeden=[{"id": "hof-1", "name": "Bestehender Hofladen"}]
    )

    with pytest.raises(DuplicateHofladenIdError):
        await provider.async_add_raw_hofladen({"id": "hof-1", "name": "Anderer Name"})


async def test_static_provider_update_raw_hofladen_merges_fields() -> None:
    """Ein Update darf nur die übergebenen Felder ändern, nicht die übrigen."""
    provider = StaticTestDataProvider(
        raw_hoflaeden=[
            {
                "id": "hof-1",
                "name": "Hofladen Eins",
                "plz": "3000",
                "zahlungsarten": [{"id": "bar", "name": "Bargeld"}],
            }
        ]
    )

    await provider.async_update_raw_hofladen(
        "hof-1", {"zahlungsarten": [{"id": "twint", "name": "TWINT"}]}
    )
    raw_hoflaeden = await provider.async_fetch_raw_hoflaeden()

    assert len(raw_hoflaeden) == 1
    aktualisiert = raw_hoflaeden[0]
    assert aktualisiert["name"] == "Hofladen Eins"  # unverändert
    assert aktualisiert["plz"] == "3000"  # unverändert
    assert aktualisiert["zahlungsarten"] == [{"id": "twint", "name": "TWINT"}]


async def test_static_provider_update_raw_hofladen_unbekannte_id() -> None:
    """Ein Update auf eine nicht existierende ID muss abgelehnt werden."""
    provider = StaticTestDataProvider(raw_hoflaeden=[])

    with pytest.raises(HofladenNotFoundError):
        await provider.async_update_raw_hofladen("unbekannt", {"name": "Neu"})
