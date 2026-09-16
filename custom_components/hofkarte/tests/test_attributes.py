"""Tests für ``attributes.py`` – Sortiment und Eigenschaften als Attribute."""

from __future__ import annotations

from custom_components.hofkarte.attributes import build_sortiment_attributes
from custom_components.hofkarte.models import (
    Angebot,
    Hofladen,
    Merkmal,
    Verkaufsart,
    Zahlungsart,
)


def test_vollstaendiges_mapping() -> None:
    """Alle vier Fachbereiche müssen korrekt in die Attributstruktur überführt werden."""
    hofladen = Hofladen(
        id="hof-1",
        name="Hofladen Müller",
        angebote=(
            Angebot(id="kartoffeln", name="Kartoffeln", gruppen=("Gemüse",)),
            Angebot(id="milch-1", name="Vollmilch", gruppen=("Milchprodukte",)),
        ),
        zahlungsarten=(
            Zahlungsart(id="bar", name="Bargeld"),
            Zahlungsart(id="twint", name="TWINT"),
        ),
        verkaufsarten=(Verkaufsart(id="ab-hof", name="Ab-Hof-Verkauf"),),
        merkmale=(Merkmal(id="bio", name="Bio"),),
    )

    attribute = build_sortiment_attributes(hofladen)

    assert attribute["angebote"] == [
        {"name": "Kartoffeln", "gruppen": ["Gemüse"]},
        {"name": "Vollmilch", "gruppen": ["Milchprodukte"]},
    ]
    assert attribute["zahlungsarten"] == ["Bargeld", "TWINT"]
    assert attribute["verkaufsarten"] == ["Ab-Hof-Verkauf"]
    assert attribute["merkmale"] == ["Bio"]


def test_fehlende_werte_ergeben_leere_listen() -> None:
    """Ohne hinterlegte Daten müssen alle Felder leere Listen sein, nicht None."""
    hofladen = Hofladen(id="hof-2", name="Kleiner Hofladen")

    attribute = build_sortiment_attributes(hofladen)

    assert attribute == {
        "angebote": [],
        "zahlungsarten": [],
        "verkaufsarten": [],
        "merkmale": [],
    }


def test_angebot_mit_mehreren_gruppen_wird_sortiert() -> None:
    """Gruppen eines Angebots müssen sortiert werden (Details zur
    Sortierreihenfolge siehe ``attributes._sortierte_namen``)."""
    hofladen = Hofladen(
        id="hof-3",
        name="Hofladen",
        angebote=(
            Angebot(id="mix", name="Mischkorb", gruppen=("Zwiebeln", "Äpfel")),
        ),
    )

    attribute = build_sortiment_attributes(hofladen)

    # Codepoint-basierte Sortierung (str.casefold): "Zwiebeln" vor "Äpfel",
    # da 'z' (U+007A) < 'ä' (U+00E4) – siehe Dokumentation in attributes.py.
    assert attribute["angebote"][0]["gruppen"] == ["Zwiebeln", "Äpfel"]


def test_angebot_ohne_gruppen_ergibt_leere_liste() -> None:
    """Ein Angebot ohne Gruppenzuordnung muss eine leere Liste liefern,
    nicht fehlen oder None sein."""
    hofladen = Hofladen(
        id="hof-4",
        name="Hofladen",
        angebote=(Angebot(id="p1", name="Angebot Eins"),),
    )

    attribute = build_sortiment_attributes(hofladen)

    assert attribute["angebote"] == [{"name": "Angebot Eins", "gruppen": []}]


def test_namen_werden_alphabetisch_und_case_insensitiv_sortiert() -> None:
    """Die Sortierung muss gross-/kleinschreibungsunabhängig erfolgen."""
    hofladen = Hofladen(
        id="hof-5",
        name="Hofladen",
        merkmale=(
            Merkmal(id="p", name="parkplatz"),
            Merkmal(id="b", name="Barrierefrei"),
            Merkmal(id="eigen", name="eigener Anbau"),
        ),
    )

    attribute = build_sortiment_attributes(hofladen)

    assert attribute["merkmale"] == ["Barrierefrei", "eigener Anbau", "parkplatz"]


def test_angebote_werden_nach_name_sortiert() -> None:
    """Die Angebotsliste selbst muss deterministisch nach Name sortiert
    sein, unabhängig von der Reihenfolge im Quelldatensatz."""
    hofladen = Hofladen(
        id="hof-6",
        name="Hofladen",
        angebote=(
            Angebot(id="z", name="Zucchetti"),
            Angebot(id="a", name="Äpfel"),
            Angebot(id="k", name="Karotten"),
        ),
    )

    attribute = build_sortiment_attributes(hofladen)

    namen = [eintrag["name"] for eintrag in attribute["angebote"]]
    # Codepoint-basierte Sortierung: Karotten, Zucchetti vor Äpfel.
    assert namen == ["Karotten", "Zucchetti", "Äpfel"]
