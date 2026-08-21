"""Tests für das interne, typisierte Hofladen-Datenmodell."""

from datetime import date, time

import pytest

from custom_components.hofkarte.models import (
    Hofladen,
    Kategorie,
    Oeffnungszeit,
    Sonderoeffnungszeit,
)


def test_hofladen_minimal_defaults() -> None:
    """Nur die Pflichtfelder gesetzt: alle Sammlungen müssen leer sein."""
    hofladen = Hofladen(id="hof-1", name="Hofladen Müller")

    assert hofladen.id == "hof-1"
    assert hofladen.name == "Hofladen Müller"
    assert hofladen.beschreibung is None
    assert hofladen.latitude is None
    assert hofladen.longitude is None
    assert hofladen.oeffnungszeiten == ()
    assert hofladen.sonderoeffnungszeiten == ()
    assert hofladen.produkte == ()
    assert hofladen.kategorien == ()
    assert hofladen.zahlungsarten == ()
    assert hofladen.verkaufsarten == ()
    assert hofladen.merkmale == ()
    assert hofladen.bilder == ()


def test_hofladen_is_immutable() -> None:
    """Hofladen-Objekte dürfen nach der Erzeugung nicht mutierbar sein."""
    hofladen = Hofladen(id="hof-1", name="Hofladen Müller")

    with pytest.raises(AttributeError):
        hofladen.name = "Anderer Name"  # type: ignore[misc]


def test_oeffnungszeit_holds_typed_values() -> None:
    """Öffnungszeiten müssen echte time-Objekte enthalten, keine Strings."""
    oeffnungszeit = Oeffnungszeit(wochentag=1, beginn=time(8, 0), ende=time(12, 0))

    assert oeffnungszeit.wochentag == 1
    assert oeffnungszeit.beginn == time(8, 0)
    assert oeffnungszeit.ende == time(12, 0)


def test_sonderoeffnungszeit_geschlossen_ohne_uhrzeiten() -> None:
    """Eine geschlossene Sonderöffnungszeit benötigt keine Uhrzeiten."""
    sonder = Sonderoeffnungszeit(
        datum_von=date(2026, 12, 24),
        datum_bis=date(2026, 12, 26),
        geschlossen=True,
    )

    assert sonder.geschlossen is True
    assert sonder.beginn is None
    assert sonder.ende is None


def test_kategorie_equality_by_value() -> None:
    """Frozen Dataclasses vergleichen nach Wert, nicht nach Identität."""
    assert Kategorie(id="gemuese", name="Gemüse") == Kategorie(
        id="gemuese", name="Gemüse"
    )
