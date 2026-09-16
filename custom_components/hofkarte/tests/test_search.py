"""Tests für search.py – Suche und Filter über Hofladen-Daten."""

from __future__ import annotations

from datetime import datetime, time, timezone

import pytest

from custom_components.hofkarte.models import (
    Angebot,
    Hofladen,
    Merkmal,
    Oeffnungszeit,
    Verkaufsart,
    Zahlungsart,
)
from custom_components.hofkarte.search import find_hoflaeden

_MONTAG = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)  # innerhalb 08-12 Uhr


def _hofladen(**kwargs) -> Hofladen:
    defaults = {"id": "hof", "name": "Hofladen"}
    defaults.update(kwargs)
    return Hofladen(**defaults)


_MUELLER = _hofladen(
    id="hof-mueller",
    name="Hofladen Müller",
    beschreibung="Frisches Gemüse direkt ab Hof.",
    ort="Bern",
    angebote=(Angebot(id="kartoffeln", name="Kartoffeln", gruppen=("Gemüse",)),),
    verkaufsarten=(Verkaufsart(id="ab-hof", name="Ab-Hof-Verkauf"),),
    zahlungsarten=(Zahlungsart(id="bar", name="Bargeld"),),
    merkmale=(Merkmal(id="bio", name="Bio"),),
    oeffnungszeiten=(
        Oeffnungszeit(wochentag=1, beginn=time(8, 0), ende=time(12, 0)),
    ),
)
_SCHMID = _hofladen(
    id="hof-schmid",
    name="Hofladen Schmid",
    beschreibung="Käse und Milchprodukte.",
    ort="Thun",
    angebote=(Angebot(id="kaese", name="Käse", gruppen=("Milchprodukte",)),),
    verkaufsarten=(Verkaufsart(id="automat", name="Verkaufsautomat"),),
    zahlungsarten=(Zahlungsart(id="twint", name="TWINT"),),
    merkmale=(),
    oeffnungszeiten=(),  # keine Öffnungszeiten -> is_open liefert None
)

_ALLE = [_MUELLER, _SCHMID]


# ---------------------------------------------------------------------------
# Ohne Filter
# ---------------------------------------------------------------------------


def test_ohne_filter_liefert_alle_hoflaeden() -> None:
    """Ohne gesetzte Kriterien müssen alle übergebenen Hofläden zurückkommen."""
    ergebnis = find_hoflaeden(_ALLE)

    assert ergebnis == _ALLE


def test_leere_eingabe_liefert_leeres_ergebnis() -> None:
    """Eine leere Liste muss ein leeres Ergebnis liefern, kein Fehler."""
    assert find_hoflaeden([]) == []


# ---------------------------------------------------------------------------
# Freitextsuche
# ---------------------------------------------------------------------------


def test_suchbegriff_findet_treffer_im_namen() -> None:
    ergebnis = find_hoflaeden(_ALLE, suchbegriff="müller")

    assert ergebnis == [_MUELLER]


def test_suchbegriff_findet_treffer_in_beschreibung() -> None:
    ergebnis = find_hoflaeden(_ALLE, suchbegriff="käse")

    assert ergebnis == [_SCHMID]


def test_suchbegriff_findet_treffer_im_ort() -> None:
    ergebnis = find_hoflaeden(_ALLE, suchbegriff="thun")

    assert ergebnis == [_SCHMID]


def test_suchbegriff_ist_case_insensitiv() -> None:
    ergebnis = find_hoflaeden(_ALLE, suchbegriff="MÜLLER")

    assert ergebnis == [_MUELLER]


def test_suchbegriff_ohne_treffer_liefert_leere_liste() -> None:
    ergebnis = find_hoflaeden(_ALLE, suchbegriff="nicht-vorhanden")

    assert ergebnis == []


def test_suchbegriff_ignoriert_hofladen_ohne_beschreibung() -> None:
    """Ein Hofladen ohne Beschreibung darf beim Durchsuchen nicht zum
    Absturz führen (None-Feld)."""
    hofladen_ohne_beschreibung = _hofladen(id="hof-x", name="Testhof")

    ergebnis = find_hoflaeden([hofladen_ohne_beschreibung], suchbegriff="testhof")

    assert ergebnis == [hofladen_ohne_beschreibung]


# ---------------------------------------------------------------------------
# Filter nach Angebot (Name oder Gruppe) / Verkaufsart / Zahlungsart / Merkmal
# ---------------------------------------------------------------------------


def test_filter_nach_angebot_gruppe() -> None:
    """Der Filter 'angebot' muss auch über die Gruppen-Zugehörigkeit
    treffen (ersetzt den früheren separaten 'kategorie'-Filter)."""
    assert find_hoflaeden(_ALLE, angebot="Gemüse") == [_MUELLER]


def test_filter_nach_angebot_gruppe_case_insensitiv() -> None:
    assert find_hoflaeden(_ALLE, angebot="gemüse") == [_MUELLER]


def test_filter_nach_angebot_name() -> None:
    """Der Filter 'angebot' muss auch über den Angebotsnamen treffen
    (ersetzt den früheren separaten 'produkt'-Filter)."""
    assert find_hoflaeden(_ALLE, angebot="Käse") == [_SCHMID]


def test_filter_nach_verkaufsart() -> None:
    assert find_hoflaeden(_ALLE, verkaufsart="Verkaufsautomat") == [_SCHMID]


def test_filter_nach_zahlungsart() -> None:
    assert find_hoflaeden(_ALLE, zahlungsart="Bargeld") == [_MUELLER]


def test_filter_nach_merkmal() -> None:
    assert find_hoflaeden(_ALLE, merkmal="Bio") == [_MUELLER]


def test_filter_ist_exakter_abgleich_kein_teilstring() -> None:
    """Filterkriterien (im Unterschied zum Suchbegriff) müssen exakt
    übereinstimmen, kein Teilstring-Treffer."""
    assert find_hoflaeden(_ALLE, angebot="Gem") == []


def test_filter_ohne_treffer_liefert_leere_liste() -> None:
    assert find_hoflaeden(_ALLE, merkmal="Parkplatz") == []


# ---------------------------------------------------------------------------
# Kombinierte Filter (logisches UND)
# ---------------------------------------------------------------------------


def test_kombinierte_filter_werden_und_verknuepft() -> None:
    """Beide Kriterien zusammen dürfen nur Hofläden liefern, die beide
    erfüllen."""
    ergebnis = find_hoflaeden(_ALLE, angebot="Gemüse", zahlungsart="Bargeld")

    assert ergebnis == [_MUELLER]


def test_kombinierte_filter_ohne_gemeinsamen_treffer() -> None:
    """Erfüllt kein Hofladen alle Kriterien gemeinsam, ist das Ergebnis leer."""
    ergebnis = find_hoflaeden(_ALLE, angebot="Gemüse", zahlungsart="TWINT")

    assert ergebnis == []


# ---------------------------------------------------------------------------
# nur_geoeffnet
# ---------------------------------------------------------------------------


def test_nur_geoeffnet_filtert_auf_offene_hoflaeden() -> None:
    """Nur der Hofladen mit passender Öffnungszeit darf zurückkommen."""
    ergebnis = find_hoflaeden(_ALLE, nur_geoeffnet=True, now=_MONTAG)

    assert ergebnis == [_MUELLER]


def test_nur_geoeffnet_schliesst_unbekannten_status_aus() -> None:
    """Ein Hofladen ohne hinterlegte Öffnungszeiten (Status unbekannt) darf
    bei nur_geoeffnet=True nicht als Treffer gelten."""
    ergebnis = find_hoflaeden([_SCHMID], nur_geoeffnet=True, now=_MONTAG)

    assert ergebnis == []


def test_nur_geoeffnet_false_wirkt_nicht_als_filter() -> None:
    """``nur_geoeffnet=False`` bedeutet 'kein Filter', nicht 'nur geschlossene'."""
    ergebnis = find_hoflaeden(_ALLE, nur_geoeffnet=False, now=_MONTAG)

    assert ergebnis == _ALLE


def test_nur_geoeffnet_ohne_now_wirft_fehler() -> None:
    """Ohne 'now' kann der Öffnungsstatus nicht berechnet werden."""
    with pytest.raises(ValueError):
        find_hoflaeden(_ALLE, nur_geoeffnet=True)


# ---------------------------------------------------------------------------
# Reihenfolge / Unveränderlichkeit
# ---------------------------------------------------------------------------


def test_eingabereihenfolge_bleibt_erhalten() -> None:
    ergebnis = find_hoflaeden([_SCHMID, _MUELLER])

    assert ergebnis == [_SCHMID, _MUELLER]


def test_eingabe_wird_nicht_veraendert() -> None:
    eingabe = [_MUELLER, _SCHMID]
    find_hoflaeden(eingabe, angebot="Gemüse")

    assert eingabe == [_MUELLER, _SCHMID]
