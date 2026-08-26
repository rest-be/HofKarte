"""Tests für die Such- und Filter-Fachlogik (search.py)."""

from __future__ import annotations

from datetime import datetime, time, timezone

import pytest

from custom_components.hofkarte.models import (
    Hofladen,
    Kategorie,
    Merkmal,
    Oeffnungszeit,
    Produkt,
    Verkaufsart,
    Zahlungsart,
)
from custom_components.hofkarte.search import filter_hoflaeden

_UTC = timezone.utc


def _hof(**kwargs) -> Hofladen:
    defaults = {"id": "hof-1", "name": "Hofladen Eins"}
    defaults.update(kwargs)
    return Hofladen(**defaults)


def _now(hour: int = 10) -> datetime:
    # Montag, 2026-01-05
    return datetime(2026, 1, 5, hour, 0, tzinfo=_UTC)


def test_ohne_kriterien_liefert_alle() -> None:
    hoefen = [_hof(id="a", name="A"), _hof(id="b", name="B")]
    assert [h.id for h in filter_hoflaeden(hoefen)] == ["a", "b"]


def test_suchbegriff_findet_name_ort_und_produkt() -> None:
    treffer_name = _hof(id="n", name="Apfelhof")
    treffer_ort = _hof(id="o", name="Anderer", ort="Apfelingen")
    treffer_produkt = _hof(
        id="p",
        name="Dritter",
        produkte=(Produkt(id="kart", name="Kartoffeln"),),
    )
    daneben = _hof(id="x", name="Milchhof", ort="Zürich")

    nach_apfel = filter_hoflaeden(
        [treffer_name, treffer_ort, treffer_produkt, daneben],
        suchbegriff="apfel",
    )
    assert [h.id for h in nach_apfel] == ["n", "o"]

    nach_kartoffel = filter_hoflaeden(
        [treffer_name, treffer_ort, treffer_produkt, daneben],
        suchbegriff="kartoffel",
    )
    assert [h.id for h in nach_kartoffel] == ["p"]


def test_leerer_suchbegriff_wird_ignoriert() -> None:
    hoefen = [_hof()]
    assert filter_hoflaeden(hoefen, suchbegriff="   ") == hoefen


def test_filter_kategorie_ueber_stamm_und_produktzuordnung() -> None:
    gemuese = Kategorie(id="kat-gemuese", name="Gemüse")
    mit_kategorie = _hof(id="k", name="A", kategorien=(gemuese,))
    nur_produkt = _hof(
        id="p",
        name="B",
        produkte=(Produkt(id="tom", name="Tomaten", kategorie_ids=("kat-gemuese",)),),
    )
    ohne = _hof(id="x", name="C", kategorien=(Kategorie(id="milch", name="Milch"),))

    treffer = filter_hoflaeden(
        [mit_kategorie, nur_produkt, ohne], kategorie="gemüse"
    )
    assert [h.id for h in treffer] == ["k", "p"]


def test_filter_produkt_zahlungsart_verkaufsart_merkmal() -> None:
    passend = _hof(
        id="ok",
        name="Passend",
        produkte=(Produkt(id="apfel", name="Äpfel"),),
        zahlungsarten=(Zahlungsart(id="twint", name="TWINT"),),
        verkaufsarten=(Verkaufsart(id="sb", name="Selbstbedienung"),),
        merkmale=(Merkmal(id="bio", name="Bio"),),
    )
    daneben = _hof(id="no", name="Daneben")

    assert [h.id for h in filter_hoflaeden([passend, daneben], produkt="äpfel")] == [
        "ok"
    ]
    assert [
        h.id for h in filter_hoflaeden([passend, daneben], zahlungsart="twint")
    ] == ["ok"]
    assert [
        h.id
        for h in filter_hoflaeden([passend, daneben], verkaufsart="selbstbedienung")
    ] == ["ok"]
    assert [h.id for h in filter_hoflaeden([passend, daneben], merkmal="bio")] == [
        "ok"
    ]


def test_mehrere_filter_sind_und_verknuepft() -> None:
    beide = _hof(
        id="beide",
        name="Beide",
        produkte=(Produkt(id="apfel", name="Äpfel"),),
        merkmale=(Merkmal(id="bio", name="Bio"),),
    )
    nur_produkt = _hof(
        id="produkt",
        name="Nur Produkt",
        produkte=(Produkt(id="apfel", name="Äpfel"),),
    )
    treffer = filter_hoflaeden([beide, nur_produkt], produkt="äpfel", merkmal="bio")
    assert [h.id for h in treffer] == ["beide"]


def test_geoeffnet_filter_ohne_now_wirft() -> None:
    with pytest.raises(ValueError, match="now"):
        filter_hoflaeden([_hof()], geoeffnet=True)


def test_geoeffnet_true_false_und_unbekannt() -> None:
    offen = _hof(
        id="offen",
        name="Offen",
        oeffnungszeiten=(
            Oeffnungszeit(wochentag=1, beginn=time(8, 0), ende=time(12, 0)),
        ),
    )
    geschlossen = _hof(
        id="zu",
        name="Zu",
        oeffnungszeiten=(
            Oeffnungszeit(wochentag=1, beginn=time(14, 0), ende=time(18, 0)),
        ),
    )
    unbekannt = _hof(id="?", name="Ohne Zeiten")
    now = _now(10)

    assert [
        h.id
        for h in filter_hoflaeden(
            [offen, geschlossen, unbekannt], geoeffnet=True, now=now
        )
    ] == ["offen"]
    assert [
        h.id
        for h in filter_hoflaeden(
            [offen, geschlossen, unbekannt], geoeffnet=False, now=now
        )
    ] == ["zu"]
