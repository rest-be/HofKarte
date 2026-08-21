"""Data Provider für Hofladen-Rohdaten.

Offene Architekturentscheidung (siehe auch README und CHANGELOG): Zum
Zeitpunkt dieser Einheit steht die tatsächliche Datenquelle für
Hofladen-Daten noch nicht fest (z. B. lokale Verwaltung durch die
Nutzerin/den Nutzer vs. externer Dienst). Um trotzdem einen echten,
asynchronen Datenabruf mit Home-Assistant-Lifecycle (Coordinator, Timeout,
Fehlerbehandlung) sinnvoll umzusetzen, ohne eine Datenquelle zu erfinden,
definiert dieses Modul eine klar abgegrenzte Provider-Schnittstelle
(:class:`HofladenDataProvider`) sowie eine Testdaten-Implementierung
(:class:`StaticTestDataProvider`).

Sobald die tatsächliche Datenquelle feststeht, wird hier eine neue
Provider-Implementierung ergänzt (z. B. ein Dateisystem- oder
HTTP-basierter Provider). Coordinator und übrige Integration greifen
ausschliesslich auf die abstrakte Schnittstelle zu und müssen dafür nicht
geändert werden.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any


class HofladenDataProvider(ABC):
    """Abstrakte Schnittstelle für den Abruf roher Hofladen-Daten.

    Implementierungen liefern eine Liste roher, noch nicht validierter
    Hofladen-Mappings, wie sie von ``parsing.parse_hofladen`` erwartet
    werden. Die Validierung selbst ist bewusst nicht Aufgabe des Providers.
    """

    @abstractmethod
    async def async_fetch_raw_hoflaeden(self) -> list[dict[str, Any]]:
        """Rohdaten aller bekannten Hofläden asynchron abrufen.

        Implementierungen müssen echte, nicht-blockierende Asynchronität
        verwenden (z. B. ``aiohttp`` oder Home-Assistant-Executor-Helper für
        Dateisystemzugriffe) und dürfen den Event Loop nicht blockieren.
        """


class StaticTestDataProvider(HofladenDataProvider):
    """Testdaten-Provider ohne externe Anbindung.

    Dient ausschliesslich dazu, den Coordinator in dieser Einheit
    lauffähig und testbar zu machen, solange die tatsächliche Datenquelle
    nicht feststeht. Enthält keine echten Hofladen-Daten und keine
    Netzwerk- oder Dateisystemzugriffe.
    """

    def __init__(self, raw_hoflaeden: list[dict[str, Any]] | None = None) -> None:
        """Testdaten-Provider erzeugen.

        Ohne explizite ``raw_hoflaeden`` wird ein einzelner Beispiel-
        Hofladen als Platzhalter zurückgegeben.
        """
        self._raw_hoflaeden = (
            raw_hoflaeden if raw_hoflaeden is not None else _DEFAULT_TEST_DATA
        )

    async def async_fetch_raw_hoflaeden(self) -> list[dict[str, Any]]:
        """Die konfigurierten Testdaten zurückgeben.

        ``asyncio.sleep(0)`` gibt die Kontrolle explizit an den Event Loop
        zurück, obwohl kein echter I/O-Zugriff stattfindet. Das hält die
        Funktion konsistent asynchron, analog zu einem künftigen echten
        Provider.
        """
        await asyncio.sleep(0)
        return list(self._raw_hoflaeden)


_DEFAULT_TEST_DATA: list[dict[str, Any]] = [
    {
        "id": "platzhalter-hofladen",
        "name": "Platzhalter-Hofladen",
    },
]
