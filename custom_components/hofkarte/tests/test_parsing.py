"""Tests für das Parsing und die Validierung roher Hofladen-Daten."""

from datetime import date, time

import pytest

from custom_components.hofkarte.parsing import (
    HofladenValidationError,
    parse_hofladen,
)

VOLLSTAENDIGER_ROHDATENSATZ = {
    "id": "hof-1",
    "name": "Hofladen Müller",
    "beschreibung": "Frisches Gemüse direkt ab Hof.",
    "adresse": "Dorfstrasse 12",
    "plz": "3000",
    "ort": "Bern",
    "land": "Schweiz",
    "latitude": 46.948,
    "longitude": 7.4474,
    "oeffnungszeiten": [
        {"wochentag": 1, "beginn": "08:00", "ende": "12:00"},
        {"wochentag": 1, "beginn": "14:00", "ende": "18:00"},
    ],
    "sonderoeffnungszeiten": [
        {
            "datum_von": "2026-12-24",
            "datum_bis": "2026-12-26",
            "geschlossen": True,
        },
        {
            "datum_von": "2026-12-31",
            "datum_bis": "2026-12-31",
            "geschlossen": False,
            "beginn": "09:00",
            "ende": "13:00",
        },
    ],
    "produkte": [
        {"id": "kartoffeln", "name": "Kartoffeln", "kategorie_ids": ["gemuese"]},
    ],
    "kategorien": [{"id": "gemuese", "name": "Gemüse"}],
    "zahlungsarten": [{"id": "bar", "name": "Bar"}],
    "verkaufsarten": [{"id": "ab-hof", "name": "Ab-Hof-Verkauf"}],
    "merkmale": [{"id": "bio", "name": "Bio"}],
    "bilder": [{"url": "https://example.com/hof.jpg", "beschreibung": "Hofeingang"}],
}


def test_parse_vollstaendiger_datensatz() -> None:
    """Ein vollständiger Rohdatensatz muss korrekt in alle Felder überführt werden."""
    hofladen = parse_hofladen(VOLLSTAENDIGER_ROHDATENSATZ)

    assert hofladen.id == "hof-1"
    assert hofladen.name == "Hofladen Müller"
    assert hofladen.beschreibung == "Frisches Gemüse direkt ab Hof."
    assert hofladen.plz == "3000"
    assert hofladen.latitude == pytest.approx(46.948)
    assert hofladen.longitude == pytest.approx(7.4474)

    assert len(hofladen.oeffnungszeiten) == 2
    erste = hofladen.oeffnungszeiten[0]
    assert erste.wochentag == 1
    assert erste.beginn == time(8, 0)
    assert erste.ende == time(12, 0)

    assert len(hofladen.sonderoeffnungszeiten) == 2
    weihnachten = hofladen.sonderoeffnungszeiten[0]
    assert weihnachten.geschlossen is True
    assert weihnachten.datum_von == date(2026, 12, 24)
    assert weihnachten.beginn is None

    silvester = hofladen.sonderoeffnungszeiten[1]
    assert silvester.geschlossen is False
    assert silvester.beginn == time(9, 0)

    assert len(hofladen.produkte) == 1
    assert hofladen.produkte[0].kategorie_ids == ("gemuese",)
    assert hofladen.kategorien[0].name == "Gemüse"
    assert hofladen.zahlungsarten[0].name == "Bar"
    assert hofladen.verkaufsarten[0].name == "Ab-Hof-Verkauf"
    assert hofladen.merkmale[0].name == "Bio"
    assert hofladen.bilder[0].url == "https://example.com/hof.jpg"


def test_parse_unvollstaendiger_datensatz_nur_pflichtfelder() -> None:
    """Nur id/name gesetzt: alle optionalen Felder müssen sauber defaulten."""
    hofladen = parse_hofladen({"id": "hof-2", "name": "Kleiner Hofladen"})

    assert hofladen.id == "hof-2"
    assert hofladen.name == "Kleiner Hofladen"
    assert hofladen.beschreibung is None
    assert hofladen.adresse is None
    assert hofladen.plz is None
    assert hofladen.latitude is None
    assert hofladen.longitude is None
    assert hofladen.oeffnungszeiten == ()
    assert hofladen.sonderoeffnungszeiten == ()
    assert hofladen.produkte == ()
    assert hofladen.bilder == ()


def test_parse_leere_optionale_strings_werden_zu_none() -> None:
    """Leere bzw. nur aus Leerzeichen bestehende optionale Strings -> None."""
    hofladen = parse_hofladen(
        {"id": "hof-3", "name": "Hofladen", "beschreibung": "   "}
    )

    assert hofladen.beschreibung is None


@pytest.mark.parametrize("missing_field", ["id", "name"])
def test_parse_fehlt_pflichtfeld(missing_field: str) -> None:
    """Fehlt id oder name, muss ein HofladenValidationError geworfen werden."""
    raw = {"id": "hof-4", "name": "Hofladen"}
    del raw[missing_field]

    with pytest.raises(HofladenValidationError):
        parse_hofladen(raw)


@pytest.mark.parametrize("leerer_wert", ["", "   "])
def test_parse_leerer_name_ist_ungueltig(leerer_wert: str) -> None:
    """Ein leerer Name (auch nur Leerzeichen) ist kein gültiger Pflichtwert."""
    with pytest.raises(HofladenValidationError):
        parse_hofladen({"id": "hof-5", "name": leerer_wert})


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("latitude", 91),
        ("latitude", -91),
        ("longitude", 181),
        ("longitude", -181),
    ],
)
def test_parse_koordinaten_ausserhalb_gueltiger_bereich(
    field_name: str, value: float
) -> None:
    """Koordinaten ausserhalb der gültigen Wertebereiche müssen abgelehnt werden."""
    with pytest.raises(HofladenValidationError):
        parse_hofladen({"id": "hof-6", "name": "Hofladen", field_name: value})


def test_parse_koordinate_kein_zahlwert() -> None:
    """Ein nicht-numerischer Wert für Koordinaten ist ungültig."""
    with pytest.raises(HofladenValidationError):
        parse_hofladen({"id": "hof-7", "name": "Hofladen", "latitude": "nord"})


def test_parse_oeffnungszeit_mitternachtsueberschreitung_ist_gueltig() -> None:
    """Ein Ende vor dem Beginn ist gültig und bedeutet Mitternachtsüberschreitung.

    Regel geändert in Einheit 7 (Öffnungszeiten-Berechnung): zuvor wurde
    'ende' vor 'beginn' abgelehnt; jetzt wird dies als Intervall über
    Mitternacht hinweg interpretiert (z. B. 22:00–02:00), siehe
    ``opening_hours.py``.
    """
    raw = {
        "id": "hof-8",
        "name": "Hofladen",
        "oeffnungszeiten": [{"wochentag": 1, "beginn": "18:00", "ende": "08:00"}],
    }

    hofladen = parse_hofladen(raw)

    assert hofladen.oeffnungszeiten[0].beginn == time(18, 0)
    assert hofladen.oeffnungszeiten[0].ende == time(8, 0)


def test_parse_oeffnungszeit_ende_gleich_beginn_ist_ungueltig() -> None:
    """Ein Ende gleich dem Beginn ist weiterhin ungültig (keine Dauer definierbar)."""
    raw = {
        "id": "hof-8b",
        "name": "Hofladen",
        "oeffnungszeiten": [{"wochentag": 1, "beginn": "08:00", "ende": "08:00"}],
    }

    with pytest.raises(HofladenValidationError):
        parse_hofladen(raw)


def test_parse_oeffnungszeit_ungueltiger_wochentag() -> None:
    """Ein Wochentag ausserhalb 1-7 muss abgelehnt werden."""
    raw = {
        "id": "hof-9",
        "name": "Hofladen",
        "oeffnungszeiten": [{"wochentag": 8, "beginn": "08:00", "ende": "12:00"}],
    }

    with pytest.raises(HofladenValidationError):
        parse_hofladen(raw)


def test_parse_oeffnungszeit_ungueltiges_zeitformat() -> None:
    """Ein nicht ISO-8601-konformes Zeitformat muss abgelehnt werden."""
    raw = {
        "id": "hof-10",
        "name": "Hofladen",
        "oeffnungszeiten": [{"wochentag": 1, "beginn": "8 Uhr", "ende": "12:00"}],
    }

    with pytest.raises(HofladenValidationError):
        parse_hofladen(raw)


def test_parse_sonderoeffnungszeit_bis_vor_von() -> None:
    """'datum_bis' vor 'datum_von' muss abgelehnt werden."""
    raw = {
        "id": "hof-11",
        "name": "Hofladen",
        "sonderoeffnungszeiten": [
            {
                "datum_von": "2026-06-10",
                "datum_bis": "2026-06-01",
                "geschlossen": True,
            }
        ],
    }

    with pytest.raises(HofladenValidationError):
        parse_hofladen(raw)


def test_parse_sonderoeffnungszeit_nicht_geschlossen_ohne_uhrzeiten() -> None:
    """Ist die Sonderöffnungszeit nicht geschlossen, sind Uhrzeiten Pflicht."""
    raw = {
        "id": "hof-12",
        "name": "Hofladen",
        "sonderoeffnungszeiten": [
            {
                "datum_von": "2026-06-01",
                "datum_bis": "2026-06-01",
                "geschlossen": False,
            }
        ],
    }

    with pytest.raises(HofladenValidationError):
        parse_hofladen(raw)


def test_parse_sonderoeffnungszeit_mitternachtsueberschreitung_ist_gueltig() -> None:
    """Auch Sonderöffnungszeiten dürfen die Mitternacht überschreiten (z. B.
    Silvester-Sonderöffnung 20:00–02:00)."""
    raw = {
        "id": "hof-12b",
        "name": "Hofladen",
        "sonderoeffnungszeiten": [
            {
                "datum_von": "2026-12-31",
                "datum_bis": "2026-12-31",
                "geschlossen": False,
                "beginn": "20:00",
                "ende": "02:00",
            }
        ],
    }

    hofladen = parse_hofladen(raw)

    assert hofladen.sonderoeffnungszeiten[0].beginn == time(20, 0)
    assert hofladen.sonderoeffnungszeiten[0].ende == time(2, 0)


def test_parse_sonderoeffnungszeit_ende_gleich_beginn_ist_ungueltig() -> None:
    """Ende gleich Beginn ist auch bei Sonderöffnungszeiten ungültig."""
    raw = {
        "id": "hof-12c",
        "name": "Hofladen",
        "sonderoeffnungszeiten": [
            {
                "datum_von": "2026-06-01",
                "datum_bis": "2026-06-01",
                "geschlossen": False,
                "beginn": "09:00",
                "ende": "09:00",
            }
        ],
    }

    with pytest.raises(HofladenValidationError):
        parse_hofladen(raw)


def test_parse_produkt_fehlende_id() -> None:
    """Ein Produkt ohne id muss abgelehnt werden."""
    raw = {
        "id": "hof-13",
        "name": "Hofladen",
        "produkte": [{"name": "Kartoffeln"}],
    }

    with pytest.raises(HofladenValidationError):
        parse_hofladen(raw)


def test_parse_kategorie_fehlender_name() -> None:
    """Eine Kategorie ohne name muss abgelehnt werden."""
    raw = {
        "id": "hof-14",
        "name": "Hofladen",
        "kategorien": [{"id": "gemuese"}],
    }

    with pytest.raises(HofladenValidationError):
        parse_hofladen(raw)


def test_parse_rohdaten_kein_mapping() -> None:
    """Rohdaten, die kein Mapping sind, müssen abgelehnt werden."""
    with pytest.raises(HofladenValidationError):
        parse_hofladen("kein-dict")  # type: ignore[arg-type]


def test_parse_bild_ohne_url() -> None:
    """Ein Bild ohne url muss abgelehnt werden."""
    raw = {
        "id": "hof-15",
        "name": "Hofladen",
        "bilder": [{"beschreibung": "Ohne URL"}],
    }

    with pytest.raises(HofladenValidationError):
        parse_hofladen(raw)
