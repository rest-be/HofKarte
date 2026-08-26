"""Tests für ``attributes.py`` – Sortiment, Eigenschaften und Bilder als Attribute."""

from __future__ import annotations

from custom_components.hofkarte.attributes import build_sortiment_attributes
from custom_components.hofkarte.models import (
    Bild,
    Hofladen,
    Kategorie,
    Merkmal,
    Produkt,
    Verkaufsart,
    Zahlungsart,
)


def test_vollstaendiges_mapping() -> None:
    """Alle fünf Fachbereiche müssen korrekt in die Attributstruktur überführt werden."""
    hofladen = Hofladen(
        id="hof-1",
        name="Hofladen Müller",
        kategorien=(
            Kategorie(id="gemuese", name="Gemüse"),
            Kategorie(id="milch", name="Milchprodukte"),
        ),
        produkte=(
            Produkt(id="kartoffeln", name="Kartoffeln", kategorie_ids=("gemuese",)),
            Produkt(id="milch-1", name="Vollmilch", kategorie_ids=("milch",)),
        ),
        zahlungsarten=(
            Zahlungsart(id="bar", name="Bargeld"),
            Zahlungsart(id="twint", name="TWINT"),
        ),
        verkaufsarten=(Verkaufsart(id="ab-hof", name="Ab-Hof-Verkauf"),),
        merkmale=(Merkmal(id="bio", name="Bio"),),
    )

    attribute = build_sortiment_attributes(hofladen)

    assert attribute["kategorien"] == ["Gemüse", "Milchprodukte"]
    assert attribute["produkte"] == [
        {"name": "Kartoffeln", "kategorien": ["Gemüse"]},
        {"name": "Vollmilch", "kategorien": ["Milchprodukte"]},
    ]
    assert attribute["zahlungsarten"] == ["Bargeld", "TWINT"]
    assert attribute["verkaufsarten"] == ["Ab-Hof-Verkauf"]
    assert attribute["merkmale"] == ["Bio"]


def test_fehlende_werte_ergeben_leere_listen() -> None:
    """Ohne hinterlegte Daten müssen alle Felder leere Listen sein, nicht None.

    Bilder müssen auch abwesend sein (primary_image=None, images=[]).
    """
    hofladen = Hofladen(id="hof-2", name="Kleiner Hofladen")

    attribute = build_sortiment_attributes(hofladen)

    assert attribute == {
        "kategorien": [],
        "produkte": [],
        "zahlungsarten": [],
        "verkaufsarten": [],
        "merkmale": [],
        "primary_image": None,
        "images": [],
    }


def test_produkt_mit_mehreren_kategorien_wird_sortiert() -> None:
    """Kategorien eines Produkts müssen sortiert werden (Details zur
    Sortierreihenfolge siehe ``attributes._sortierte_namen``)."""
    hofladen = Hofladen(
        id="hof-3",
        name="Hofladen",
        kategorien=(
            Kategorie(id="z", name="Zwiebeln"),
            Kategorie(id="a", name="Äpfel"),
        ),
        produkte=(
            Produkt(id="mix", name="Mischkorb", kategorie_ids=("z", "a")),
        ),
    )

    attribute = build_sortiment_attributes(hofladen)

    # Codepoint-basierte Sortierung (str.casefold): "Zwiebeln" vor "Äpfel",
    # da 'z' (U+007A) < 'ä' (U+00E4) – siehe Dokumentation in attributes.py.
    assert attribute["produkte"][0]["kategorien"] == ["Zwiebeln", "Äpfel"]


def test_produkt_mit_unbekannter_kategorie_id_faellt_auf_id_zurueck() -> None:
    """Verweist ein Produkt auf eine nicht existierende Kategorie-ID, wird
    diese ID als Platzhalter verwendet statt die Zuordnung zu verwerfen."""
    hofladen = Hofladen(
        id="hof-4",
        name="Hofladen",
        kategorien=(),  # keine Kategorien hinterlegt
        produkte=(
            Produkt(id="p1", name="Produkt Eins", kategorie_ids=("unbekannt",)),
        ),
    )

    attribute = build_sortiment_attributes(hofladen)

    assert attribute["produkte"] == [
        {"name": "Produkt Eins", "kategorien": ["unbekannt"]}
    ]


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


def test_produkte_werden_nach_name_sortiert() -> None:
    """Die Produktliste selbst muss deterministisch nach Name sortiert
    sein, unabhängig von der Reihenfolge im Quelldatensatz."""
    hofladen = Hofladen(
        id="hof-6",
        name="Hofladen",
        produkte=(
            Produkt(id="z", name="Zucchetti"),
            Produkt(id="a", name="Äpfel"),
            Produkt(id="k", name="Karotten"),
        ),
    )

    attribute = build_sortiment_attributes(hofladen)

    namen = [eintrag["name"] for eintrag in attribute["produkte"]]
    # Codepoint-basierte Sortierung: Karotten, Zucchetti vor Äpfel.
    assert namen == ["Karotten", "Zucchetti", "Äpfel"]


def test_einzelnes_gültiges_bild_wird_als_primary_bild_gespeichert() -> None:
    """Ein einziges gültiges Bild sollte als primary_image gespeichert werden."""
    hofladen = Hofladen(
        id="hof-mit-bild",
        name="Hofladen mit Bild",
        bilder=(
            Bild(
                url="https://example.com/hauptfoto.jpg",
                beschreibung="Hofansicht von vorne",
            ),
        ),
    )

    attribute = build_sortiment_attributes(hofladen)

    assert attribute["primary_image"] == "https://example.com/hauptfoto.jpg"
    assert len(attribute["images"]) == 1
    assert attribute["images"][0]["url"] == "https://example.com/hauptfoto.jpg"
    assert attribute["images"][0]["description"] == "Hofansicht von vorne"


def test_mehrere_gültige_bilder() -> None:
    """Mehrere gültige Bilder sollten alle in der images Liste enthalten sein."""
    hofladen = Hofladen(
        id="hof-mehrbilder",
        name="Hofladen mit mehreren Bildern",
        bilder=(
            Bild(url="https://example.com/bild1.jpg", beschreibung="Bild 1"),
            Bild(url="https://example.com/bild2.jpg", beschreibung="Bild 2"),
            Bild(url="https://example.com/bild3.jpg", beschreibung=None),
        ),
    )

    attribute = build_sortiment_attributes(hofladen)

    assert attribute["primary_image"] == "https://example.com/bild1.jpg"
    assert len(attribute["images"]) == 3
    assert [img["url"] for img in attribute["images"]] == [
        "https://example.com/bild1.jpg",
        "https://example.com/bild2.jpg",
        "https://example.com/bild3.jpg",
    ]


def test_ungültige_bilder_werden_gefiltert() -> None:
    """Ungültige Bilder (file://, data:, etc.) sollten aus den Attributen
    entfernt werden, aber nicht zu einem Fehler führen."""
    hofladen = Hofladen(
        id="hof-mit-bad-bilder",
        name="Hofladen mit unsicheren Bildern",
        bilder=(
            Bild(url="file:///etc/passwd", beschreibung="Sollte gefiltert werden"),
            Bild(url="https://example.com/valid.jpg", beschreibung="Valide"),
            Bild(url="data:image/png;base64,xxx", beschreibung="Data URI"),
        ),
    )

    attribute = build_sortiment_attributes(hofladen)

    # Nur das HTTPS Bild sollte vorhanden sein
    assert attribute["primary_image"] == "https://example.com/valid.jpg"
    assert len(attribute["images"]) == 1
    assert attribute["images"][0]["url"] == "https://example.com/valid.jpg"


def test_alle_bilder_ungültig() -> None:
    """Wenn alle Bilder ungültig sind, sollten primary_image und images leer sein."""
    hofladen = Hofladen(
        id="hof-keine-gültigen-bilder",
        name="Hofladen ohne gültige Bilder",
        bilder=(
            Bild(url="file:///local/image.jpg", beschreibung="Local File"),
            Bild(url="", beschreibung="Empty URL"),
        ),
    )

    attribute = build_sortiment_attributes(hofladen)

    assert attribute["primary_image"] is None
    assert attribute["images"] == []


def test_bild_mit_beschreibung_enthält_description_feld() -> None:
    """Bilder mit Beschreibung sollten ein description Feld enthalten."""
    hofladen = Hofladen(
        id="hof-beschreibung",
        name="Hofladen",
        bilder=(
            Bild(url="https://example.com/img.jpg", beschreibung="Schönes Foto"),
        ),
    )

    attribute = build_sortiment_attributes(hofladen)

    assert "description" in attribute["images"][0]
    assert attribute["images"][0]["description"] == "Schönes Foto"


def test_bild_ohne_beschreibung_enthält_kein_description_feld() -> None:
    """Bilder ohne Beschreibung sollten kein description Feld enthalten."""
    hofladen = Hofladen(
        id="hof-keine-beschreibung",
        name="Hofladen",
        bilder=(Bild(url="https://example.com/img.jpg", beschreibung=None),),
    )

    attribute = build_sortiment_attributes(hofladen)

    assert "description" not in attribute["images"][0]
