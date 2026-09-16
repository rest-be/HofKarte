"""Tests für die Migration des alten Formats (getrennte 'kategorien'/
'produkte') zu 'angebote' (siehe parsing._migriere_kategorien_und_produkte_zu_angeboten).

Deckt exakt die im Migrationskonzept geforderten Testfälle ab: Produkt
mit einer Kategorie, Produkt mit mehreren Kategorien, Produkt ohne
Kategorie, Kategorie ohne Produkt (verwaist), sowie bereits im neuen
Format vorliegende Daten (Idempotenz).
"""

from __future__ import annotations

from custom_components.hofkarte.parsing import (
    _migriere_kategorien_und_produkte_zu_angeboten,
    parse_hofladen,
)


def test_produkt_mit_einer_kategorie() -> None:
    raw = {
        "kategorien": [{"id": "gemuese", "name": "Gemüse"}],
        "produkte": [
            {"id": "kartoffeln", "name": "Kartoffeln", "kategorie_ids": ["gemuese"]}
        ],
    }

    angebote = _migriere_kategorien_und_produkte_zu_angeboten(raw)

    assert angebote == [
        {"id": "kartoffeln", "name": "Kartoffeln", "gruppen": ["Gemüse"]}
    ]


def test_produkt_mit_mehreren_kategorien() -> None:
    raw = {
        "kategorien": [
            {"id": "gemuese", "name": "Gemüse"},
            {"id": "bio", "name": "Bio"},
        ],
        "produkte": [
            {
                "id": "kartoffeln",
                "name": "Kartoffeln",
                "kategorie_ids": ["gemuese", "bio"],
            }
        ],
    }

    angebote = _migriere_kategorien_und_produkte_zu_angeboten(raw)

    assert angebote == [
        {"id": "kartoffeln", "name": "Kartoffeln", "gruppen": ["Gemüse", "Bio"]}
    ]


def test_produkt_ohne_kategorie() -> None:
    """Ein Produkt ganz ohne kategorie_ids muss zu einem Angebot mit
    leeren Gruppen werden, nicht zu einem Fehler führen."""
    raw = {
        "kategorien": [],
        "produkte": [{"id": "honig", "name": "Honig"}],
    }

    angebote = _migriere_kategorien_und_produkte_zu_angeboten(raw)

    assert angebote == [{"id": "honig", "name": "Honig", "gruppen": []}]


def test_kategorie_ohne_produkt_bleibt_als_eigenes_angebot_erhalten() -> None:
    """Eine verwaiste Kategorie (kein Produkt referenziert sie) darf nicht
    stillschweigend verschwinden - ihr Name muss als eigenständiges
    Angebot mit leeren Gruppen erhalten bleiben."""
    raw = {
        "kategorien": [{"id": "sonstiges", "name": "Sonstiges"}],
        "produkte": [],
    }

    angebote = _migriere_kategorien_und_produkte_zu_angeboten(raw)

    assert angebote == [{"id": "sonstiges", "name": "Sonstiges", "gruppen": []}]


def test_gemischt_verwaiste_kategorie_neben_referenzierten() -> None:
    """Realistischer Mischfall: eine referenzierte und eine verwaiste
    Kategorie gleichzeitig - beide Namen müssen erhalten bleiben."""
    raw = {
        "kategorien": [
            {"id": "gemuese", "name": "Gemüse"},
            {"id": "verwaist", "name": "Verwaiste Kategorie"},
        ],
        "produkte": [
            {"id": "kartoffeln", "name": "Kartoffeln", "kategorie_ids": ["gemuese"]}
        ],
    }

    angebote = _migriere_kategorien_und_produkte_zu_angeboten(raw)

    assert {"id": "kartoffeln", "name": "Kartoffeln", "gruppen": ["Gemüse"]} in angebote
    assert {
        "id": "verwaist",
        "name": "Verwaiste Kategorie",
        "gruppen": [],
    } in angebote
    assert len(angebote) == 2


def test_bereits_neues_format_ist_idempotent() -> None:
    """Ein Datensatz, der bereits 'angebote' enthält, darf durch die
    Migration nicht verändert werden - auch nicht, wenn zufällig noch
    alte Schlüssel danebenliegen (angebote hat Vorrang)."""
    raw = {
        "angebote": [{"id": "kartoffeln", "name": "Kartoffeln", "gruppen": ["Gemüse"]}],
    }

    angebote = _migriere_kategorien_und_produkte_zu_angeboten(raw)

    assert angebote == [{"id": "kartoffeln", "name": "Kartoffeln", "gruppen": ["Gemüse"]}]


def test_weder_altes_noch_neues_format_ergibt_leere_liste() -> None:
    assert _migriere_kategorien_und_produkte_zu_angeboten({}) == []


def test_migration_ueber_den_vollen_parse_hofladen_pfad() -> None:
    """End-zu-Ende: Ein kompletter, alter Rohdatensatz muss über
    parse_hofladen() korrekt migriert und validiert werden."""
    raw = {
        "id": "hof-alt",
        "name": "Alter Hofladen",
        "kategorien": [
            {"id": "gemuese", "name": "Gemüse"},
            {"id": "verwaist", "name": "Verwaiste Kategorie"},
        ],
        "produkte": [
            {"id": "kartoffeln", "name": "Kartoffeln", "kategorie_ids": ["gemuese"]}
        ],
    }

    hofladen = parse_hofladen(raw)

    namen = {angebot.name for angebot in hofladen.angebote}
    assert namen == {"Kartoffeln", "Verwaiste Kategorie"}

    kartoffeln = next(a for a in hofladen.angebote if a.name == "Kartoffeln")
    assert kartoffeln.gruppen == ("Gemüse",)

    verwaist = next(a for a in hofladen.angebote if a.name == "Verwaiste Kategorie")
    assert verwaist.gruppen == ()


def test_migration_erneutes_einlesen_bereits_migrierter_daten_ist_stabil() -> None:
    """Wird ein bereits migrierter Hofladen (neues Format) erneut
    eingelesen, dürfen keine Duplikate oder Veränderungen entstehen."""
    raw_neu = {
        "id": "hof-neu",
        "name": "Neuer Hofladen",
        "angebote": [
            {"id": "kartoffeln", "name": "Kartoffeln", "gruppen": ["Gemüse"]}
        ],
    }

    erstes_parsen = parse_hofladen(raw_neu)
    zweites_parsen = parse_hofladen(raw_neu)

    assert erstes_parsen.angebote == zweites_parsen.angebote
    assert len(erstes_parsen.angebote) == 1
