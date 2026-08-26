"""Suche und Filter über Hofladen-Daten.

Reine Fachfunktionen ohne Home-Assistant-Abhängigkeit, damit Automationen
(über Actions) und Tests dieselbe Logik verwenden. Die Auswertung des
Öffnungsstatus erfolgt ausschliesslich über ``opening_hours.is_open``.

Mehrere gesetzte Kriterien gelten als UND-Verknüpfung. Ein leerer oder
nur aus Leerraum bestehender Filterwert wird ignoriert (kein Treffer-
Ausschluss).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from .models import Hofladen
from .opening_hours import is_open


def _norm(value: str) -> str:
    return value.casefold().strip()


def _bereinigen(value: str | None) -> str | None:
    """Leere bzw. nur-Leerraum-Angaben als «nicht gesetzt» behandeln."""
    if value is None:
        return None
    bereinigt = value.strip()
    return bereinigt if bereinigt else None


def _enthaelt(haystack: str | None, nadel: str) -> bool:
    if haystack is None:
        return False
    return _norm(nadel) in _norm(haystack)


def _sammlung_trifft(
    eintraege: Iterable[object], nadel: str, *, id_attr: str = "id", name_attr: str = "name"
) -> bool:
    """Treffer, wenn ID oder Name eines Eintrags den Filter (Teilstring) enthält."""
    nadel_norm = _norm(nadel)
    for eintrag in eintraege:
        eintrag_id = getattr(eintrag, id_attr, None)
        eintrag_name = getattr(eintrag, name_attr, None)
        if isinstance(eintrag_id, str) and nadel_norm in _norm(eintrag_id):
            return True
        if isinstance(eintrag_name, str) and nadel_norm in _norm(eintrag_name):
            return True
    return False


def _kategorie_trifft(hofladen: Hofladen, nadel: str) -> bool:
    """Kategorie-Filter: Treffer über Kategorie-Stammdaten oder Produktzuordnung."""
    if _sammlung_trifft(hofladen.kategorien, nadel):
        return True
    nadel_norm = _norm(nadel)
    passende_ids = {
        kategorie.id
        for kategorie in hofladen.kategorien
        if nadel_norm in _norm(kategorie.id) or nadel_norm in _norm(kategorie.name)
    }
    for produkt in hofladen.produkte:
        if any(kategorie_id in passende_ids for kategorie_id in produkt.kategorie_ids):
            return True
        if any(nadel_norm in _norm(kategorie_id) for kategorie_id in produkt.kategorie_ids):
            return True
    return False


def _suchbegriff_trifft(hofladen: Hofladen, suchbegriff: str) -> bool:
    """Freitext über Stammdaten, Sortiment und Eigenschaften."""
    felder = (
        hofladen.id,
        hofladen.name,
        hofladen.beschreibung,
        hofladen.adresse,
        hofladen.plz,
        hofladen.ort,
        hofladen.land,
        hofladen.website,
    )
    if any(_enthaelt(feld, suchbegriff) for feld in felder):
        return True
    return (
        _sammlung_trifft(hofladen.kategorien, suchbegriff)
        or _sammlung_trifft(hofladen.produkte, suchbegriff)
        or _sammlung_trifft(hofladen.zahlungsarten, suchbegriff)
        or _sammlung_trifft(hofladen.verkaufsarten, suchbegriff)
        or _sammlung_trifft(hofladen.merkmale, suchbegriff)
    )


def filter_hoflaeden(
    hoflaeden: Iterable[Hofladen],
    *,
    suchbegriff: str | None = None,
    kategorie: str | None = None,
    produkt: str | None = None,
    verkaufsart: str | None = None,
    zahlungsart: str | None = None,
    merkmal: str | None = None,
    geoeffnet: bool | None = None,
    now: datetime | None = None,
) -> list[Hofladen]:
    """Hofläden nach Freitext und Fachfiltern eingrenzen.

    ``geoeffnet=True`` liefert nur nachweislich geöffnete Hofläden,
    ``geoeffnet=False`` nur nachweislich geschlossene. Hofläden ohne
    Öffnungszeiten (Status unbekannt) erfüllen keinen der beiden Filter.

    Ist ``geoeffnet`` gesetzt, muss ``now`` zeitzonenbewusst übergeben
    werden – analog zu ``opening_hours.is_open``.
    """
    suchbegriff = _bereinigen(suchbegriff)
    kategorie = _bereinigen(kategorie)
    produkt = _bereinigen(produkt)
    verkaufsart = _bereinigen(verkaufsart)
    zahlungsart = _bereinigen(zahlungsart)
    merkmal = _bereinigen(merkmal)

    if geoeffnet is not None and now is None:
        raise ValueError(
            "'now' muss gesetzt sein, wenn nach dem Öffnungsstatus gefiltert wird."
        )

    treffer: list[Hofladen] = []
    for hofladen in hoflaeden:
        if suchbegriff is not None and not _suchbegriff_trifft(hofladen, suchbegriff):
            continue
        if kategorie is not None and not _kategorie_trifft(hofladen, kategorie):
            continue
        if produkt is not None and not _sammlung_trifft(hofladen.produkte, produkt):
            continue
        if verkaufsart is not None and not _sammlung_trifft(
            hofladen.verkaufsarten, verkaufsart
        ):
            continue
        if zahlungsart is not None and not _sammlung_trifft(
            hofladen.zahlungsarten, zahlungsart
        ):
            continue
        if merkmal is not None and not _sammlung_trifft(hofladen.merkmale, merkmal):
            continue
        if geoeffnet is not None:
            status = is_open(hofladen, now)
            if status is None or status is not geoeffnet:
                continue
        treffer.append(hofladen)

    return treffer
