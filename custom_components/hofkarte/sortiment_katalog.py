"""Standardkatalog für die editierbaren Fachbereiche (Einheit 8).

Bietet Hilfsfunktionen, um aus den Vorschlagswerten in ``const.py``
(``STANDARD_ZAHLUNGSARTEN``, ``STANDARD_VERKAUFSARTEN``,
``STANDARD_MERKMALE``) direkt verwendbare rohe Datensätze zu erzeugen,
wie sie ``parsing.parse_hofladen`` bzw.
``coordinator.HofKarteUpdateCoordinator.async_update_hofladen_sortiment``
erwarten (``{"id": ..., "name": ...}``).

Dies ist bewusst nur ein Vorschlagskatalog: Nutzer sind nicht auf diese
Werte beschränkt. Jeder beliebige Name ist über
``async_update_hofladen_sortiment`` zulässig – dieser Katalog erspart
lediglich das manuelle Vergeben von IDs für die gängigsten Standardwerte.
"""

from __future__ import annotations

import re
from typing import Any

from .const import STANDARD_MERKMALE, STANDARD_VERKAUFSARTEN, STANDARD_ZAHLUNGSARTEN

_NICHT_ALPHANUMERISCH = re.compile(r"[^a-z0-9]+")


def slug(name: str) -> str:
    """Eine stabile, URL-/ID-taugliche Kennung aus einem Namen ableiten.

    Beispiel: ``"eigener Anbau"`` -> ``"eigener-anbau"``. Rein
    informativ/praktisch – die tatsächliche ID-Vergabe obliegt letztlich
    der Nutzerin/dem Nutzer bzw. der Datenquelle; für die Standardwerte
    aus dieser Datei ist eine deterministische Ableitung aber
    naheliegend und vermeidet Tippfehler.
    """
    ergebnis = _NICHT_ALPHANUMERISCH.sub("-", name.strip().lower()).strip("-")
    return ergebnis or "eintrag"


def _rohdaten(namen: tuple[str, ...]) -> list[dict[str, Any]]:
    return [{"id": slug(name), "name": name} for name in namen]


def standard_zahlungsarten_rohdaten() -> list[dict[str, Any]]:
    """Rohdaten für die vorgeschlagenen Standard-Zahlungsarten."""
    return _rohdaten(STANDARD_ZAHLUNGSARTEN)


def standard_verkaufsarten_rohdaten() -> list[dict[str, Any]]:
    """Rohdaten für die vorgeschlagenen Standard-Verkaufsarten."""
    return _rohdaten(STANDARD_VERKAUFSARTEN)


def standard_merkmale_rohdaten() -> list[dict[str, Any]]:
    """Rohdaten für die vorgeschlagenen Standard-Merkmale."""
    return _rohdaten(STANDARD_MERKMALE)
