"""Sortiment und Eigenschaften als Entity-Attribute.

Kategorien, Produkte, Zahlungsarten, Verkaufsarten und Merkmale eines
Hofladens sind fachlich keine Messwerte und rechtfertigen keine eigenen
Entities (Regeln dieser Einheit: „Keine künstlichen Messwerte“, „Keine
unnötigen Entities“). Stattdessen werden sie als ``extra_state_attributes``
einer einzigen bestehenden Entity bereitgestellt (Binary Sensor
„Geöffnet“, siehe ``binary_sensor.py``) statt auf mehrere Entities
dupliziert zu werden.

Dieses Modul ist die alleinige Stelle, die diese Rohdaten aus
``models.Hofladen`` in eine einfache, JSON-serialisierbare und stabile
Attributstruktur überführt (nur ``str``/``list``/``dict`` – keine
dataclass-Instanzen direkt als State-Attribut).
"""

from __future__ import annotations

from typing import Any

from .models import Hofladen


def _kategorie_namen_je_id(hofladen: Hofladen) -> dict[str, str]:
    """Mapping von Kategorie-ID auf Kategorie-Name für die Auflösung bei Produkten."""
    return {kategorie.id: kategorie.name for kategorie in hofladen.kategorien}


def _sortierte_namen(namen: list[str]) -> list[str]:
    """Für eine stabile, deterministische Darstellung sortieren.

    Verwendet ``str.casefold`` für eine gross-/kleinschreibungsunabhängige
    Sortierung nach Unicode-Codepoint. Dies ist bewusst *keine*
    lokalisierte (z. B. deutsche) alphabetische Kollation – dafür wäre
    eine Locale-Abhängigkeit nötig, die auf unterschiedlichen Systemen
    unterschiedliche und damit nicht deterministische Ergebnisse liefern
    könnte. Effekt: Umlaute (Ä, Ö, Ü) werden nach "Z" einsortiert statt
    wie im deutschen Alphabet neben A/O/U.
    """
    return sorted(namen, key=str.casefold)


def _produkt_eintraege(
    hofladen: Hofladen, kategorie_namen_je_id: dict[str, str]
) -> list[dict[str, Any]]:
    """Produkte inkl. aufgelöster Kategorie-Namen, alphabetisch nach Name.

    Verweist ein Produkt auf eine ``kategorie_id``, die in
    ``hofladen.kategorien`` nicht vorhanden ist (vom Datenmodell nicht
    ausgeschlossen), wird ersatzweise die rohe ID verwendet, statt die
    Zuordnung stillschweigend zu verwerfen.
    """
    eintraege = [
        {
            "name": produkt.name,
            "kategorien": _sortierte_namen(
                [
                    kategorie_namen_je_id.get(kategorie_id, kategorie_id)
                    for kategorie_id in produkt.kategorie_ids
                ]
            ),
        }
        for produkt in hofladen.produkte
    ]
    return sorted(eintraege, key=lambda eintrag: eintrag["name"].casefold())


def build_sortiment_attributes(hofladen: Hofladen) -> dict[str, Any]:
    """Sortiment und Eigenschaften als stabile Attributstruktur.

    Fehlen einzelne Sammlungen (z. B. keine Zahlungsarten hinterlegt),
    liefert das jeweilige Feld stets eine leere Liste statt eines
    fehlenden Schlüssels oder ``None`` – für eine vorhersagbare,
    stabile Struktur unabhängig vom Vollständigkeitsgrad der Daten.
    """
    kategorie_namen_je_id = _kategorie_namen_je_id(hofladen)

    return {
        "kategorien": _sortierte_namen(
            [kategorie.name for kategorie in hofladen.kategorien]
        ),
        "produkte": _produkt_eintraege(hofladen, kategorie_namen_je_id),
        "zahlungsarten": _sortierte_namen(
            [zahlungsart.name for zahlungsart in hofladen.zahlungsarten]
        ),
        "verkaufsarten": _sortierte_namen(
            [verkaufsart.name for verkaufsart in hofladen.verkaufsarten]
        ),
        "merkmale": _sortierte_namen(
            [merkmal.name for merkmal in hofladen.merkmale]
        ),
    }
