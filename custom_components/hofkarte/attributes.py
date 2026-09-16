"""Sortiment und Eigenschaften als Entity-Attribute.

Angebote, Zahlungsarten, Verkaufsarten und Merkmale eines Hofladens sind
fachlich keine Messwerte und rechtfertigen keine eigenen Entities
(Regeln dieser Einheit: „Keine künstlichen Messwerte“, „Keine
unnötigen Entities“). Stattdessen werden sie als ``extra_state_attributes``
einer einzigen bestehenden Entity bereitgestellt (Binary Sensor
„Geöffnet“, siehe ``binary_sensor.py``) statt auf mehrere Entities
dupliziert zu werden.

Dieses Modul ist die alleinige Stelle, die diese Rohdaten aus
``models.Hofladen`` in eine einfache, JSON-serialisierbare und stabile
Attributstruktur überführt (nur ``str``/``list``/``dict`` – keine
dataclass-Instanzen direkt als State-Attribut).

„Angebote“ ersetzt die früher getrennten Attribute ``kategorien`` und
``produkte`` (siehe CHANGELOG, Zusammenlegung zu „Angebote“): ein
Angebot trägt seine Gruppen-Zugehörigkeit (vormals „Kategorie“) direkt
als einfache Textliste statt über eine separate, ID-referenzierte
Kategorienliste.
"""

from __future__ import annotations

from typing import Any

from .models import Hofladen


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


def _angebot_eintraege(hofladen: Hofladen) -> list[dict[str, Any]]:
    """Angebote inkl. ihrer Gruppen, alphabetisch nach Name sortiert."""
    eintraege = [
        {
            "name": angebot.name,
            "gruppen": _sortierte_namen(list(angebot.gruppen)),
        }
        for angebot in hofladen.angebote
    ]
    return sorted(eintraege, key=lambda eintrag: eintrag["name"].casefold())


def build_sortiment_attributes(hofladen: Hofladen) -> dict[str, Any]:
    """Sortiment und Eigenschaften als stabile Attributstruktur.

    Fehlen einzelne Sammlungen (z. B. keine Zahlungsarten hinterlegt),
    liefert das jeweilige Feld stets eine leere Liste statt eines
    fehlenden Schlüssels oder ``None`` – für eine vorhersagbare,
    stabile Struktur unabhängig vom Vollständigkeitsgrad der Daten.
    """
    return {
        "angebote": _angebot_eintraege(hofladen),
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
