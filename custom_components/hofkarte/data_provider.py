"""Data Provider für Hofladen-Rohdaten.

Architekturentscheid (löst die zuvor offene Frage der Datenquelle, siehe
CHANGELOG): Home Assistant ist sowohl Laufzeitumgebung als auch
Verwaltungsoberfläche für HofKarte. Die vom Benutzer gepflegten Hofläden
werden in einem integrationsinternen, persistenten Store gehalten (Home
Assistants ``helpers.storage.Store``, siehe
:class:`StorageHofladenDataProvider`) – keine externe Datenbank, kein
externer Dienst. Der ``HofladenDataProvider`` kapselt diesen Store;
Coordinator und Entities greifen ausschliesslich über diese Abstraktion
darauf zu und kennen die konkrete Speicherform nicht.

Dieses Modul definiert dazu eine klar abgegrenzte Provider-Schnittstelle
(:class:`HofladenDataProvider`), deren produktive Implementierung
(:class:`StorageHofladenDataProvider`) sowie eine reine
Testdaten-Implementierung ohne Persistenz
(:class:`StaticTestDataProvider`) für die Testsuite.

``MutableHofladenDataProvider`` deckt sowohl das Hinzufügen neuer
Hofläden als auch das teilweise Aktualisieren bestehender Hofläden ab
(z. B. um die nutzereditierbaren Fachbereiche aus Einheit 8 – Kategorien,
Produkte, Zahlungsarten, Verkaufsarten, Merkmale – zu ändern).
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store


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


class MutableHofladenDataProvider(HofladenDataProvider):
    """Optionale Erweiterung für Provider, die auch Schreibzugriffe erlauben.

    Nicht jede künftige Datenquelle wird Schreibzugriffe unterstützen (z. B.
    ein rein lesender externer Dienst). Dieses zusätzliche Interface hält
    Schreiboperationen daher bewusst getrennt von der grundlegenden,
    nur-lesenden Provider-Schnittstelle.
    """

    @abstractmethod
    async def async_add_raw_hofladen(self, raw_hofladen: dict[str, Any]) -> None:
        """Einen neuen, rohen Hofladen-Datensatz zur Datenquelle hinzufügen.

        Implementierungen müssen sicherstellen, dass ein bereits
        vorhandener Datensatz mit identischer ``id`` nicht stillschweigend
        überschrieben wird (siehe ``StaticTestDataProvider`` für ein
        Beispiel).
        """

    @abstractmethod
    async def async_update_raw_hofladen(
        self, hofladen_id: str, updates: dict[str, Any]
    ) -> None:
        """Einzelne Felder eines bestehenden Hofladens aktualisieren.

        ``updates`` enthält nur die zu ändernden Felder; alle übrigen,
        nicht in ``updates`` enthaltenen Felder des bestehenden
        Datensatzes bleiben unverändert (teilweise Aktualisierung, kein
        vollständiger Ersatz). Wirft :class:`HofladenNotFoundError`, wenn
        keine ``id`` mit diesem Wert existiert.
        """


class DuplicateHofladenIdError(ValueError):
    """Es existiert bereits ein Hofladen mit der angegebenen ID."""


class HofladenNotFoundError(KeyError):
    """Es existiert kein Hofladen mit der angegebenen ID."""


# Home Assistant migriert die gespeicherte Struktur automatisch, falls
# diese Versionsnummer künftig erhöht wird (siehe Store-Dokumentation).
_STORAGE_VERSION = 1
_STORAGE_KEY = "hofkarte_hoflaeden"


class StorageHofladenDataProvider(MutableHofladenDataProvider):
    """Produktiver, persistenter Hofladen-Datenspeicher.

    Kapselt Home Assistants ``helpers.storage.Store`` (JSON-Datei unter
    ``.storage/`` im Konfigurationsverzeichnis) gemäss Architekturentscheid:
    HofKarte verwaltet die vom Benutzer gepflegten Hofläden vollständig
    integrationsintern – keine externe Datenbank, kein externer Dienst,
    kein manuelles Bearbeiten der Datei nötig (Bearbeitung erfolgt
    ausschliesslich über ``async_add_raw_hofladen``/
    ``async_update_raw_hofladen``, die diese Klasse implementiert).

    Die geladenen Daten werden nach dem ersten Zugriff im Arbeitsspeicher
    gehalten (keine wiederholten Store-Lesezugriffe bei jedem
    Coordinator-Update) und bei jeder Schreiboperation sowohl im Speicher
    als auch im Store aktualisiert, sodass beide stets konsistent sind.
    Ein ``asyncio.Lock`` verhindert verlorene Schreibzugriffe bei
    gleichzeitigen Änderungen.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[list[dict[str, Any]]] = Store(
            hass, _STORAGE_VERSION, _STORAGE_KEY
        )
        self._raw_hoflaeden: list[dict[str, Any]] | None = None
        self._lock = asyncio.Lock()

    async def _async_geladene_daten(self) -> list[dict[str, Any]]:
        """Daten bei Bedarf einmalig aus dem Store laden (Lazy Load)."""
        if self._raw_hoflaeden is None:
            geladen = await self._store.async_load()
            # Ein frisch eingerichteter Store enthält noch keine Datei
            # (async_load liefert dann None). Bewusst mit einer leeren
            # Liste starten statt erfundener Beispieldaten – die
            # Hofläden werden vollständig von der Nutzerin/dem Nutzer
            # gepflegt.
            self._raw_hoflaeden = geladen if geladen is not None else []
        return self._raw_hoflaeden

    async def async_fetch_raw_hoflaeden(self) -> list[dict[str, Any]]:
        """Alle im Store gehaltenen Hofladen-Rohdaten zurückgeben."""
        daten = await self._async_geladene_daten()
        return list(daten)

    async def async_add_raw_hofladen(self, raw_hofladen: dict[str, Any]) -> None:
        """Einen neuen Hofladen persistent ergänzen.

        Wirft :class:`DuplicateHofladenIdError`, falls bereits ein
        Datensatz mit derselben ``id`` vorhanden ist.
        """
        async with self._lock:
            daten = await self._async_geladene_daten()

            neue_id = raw_hofladen.get("id")
            if any(vorhanden.get("id") == neue_id for vorhanden in daten):
                raise DuplicateHofladenIdError(
                    f"Ein Hofladen mit der ID '{neue_id}' existiert bereits."
                )

            daten.append(dict(raw_hofladen))
            await self._store.async_save(daten)

    async def async_update_raw_hofladen(
        self, hofladen_id: str, updates: dict[str, Any]
    ) -> None:
        """Einzelne Felder eines bestehenden Hofladens persistent aktualisieren.

        Wirft :class:`HofladenNotFoundError`, falls keine ``id`` mit
        diesem Wert existiert.
        """
        async with self._lock:
            daten = await self._async_geladene_daten()

            for index, vorhandener in enumerate(daten):
                if vorhandener.get("id") == hofladen_id:
                    daten[index] = {**vorhandener, **updates}
                    await self._store.async_save(daten)
                    return

            raise HofladenNotFoundError(
                f"Kein Hofladen mit der ID '{hofladen_id}' gefunden."
            )


class StaticTestDataProvider(MutableHofladenDataProvider):
    """Reiner Testdaten-Provider ohne Persistenz und ohne externe Anbindung.

    Wird ausschliesslich von der Testsuite verwendet, um Coordinator und
    Entities isoliert und deterministisch zu testen, ohne einen echten
    Home-Assistant-Store zu benötigen. Für den produktiven Betrieb wird
    stattdessen :class:`StorageHofladenDataProvider` verwendet (siehe
    ``__init__.py``). Daten liegen nur im Arbeitsspeicher und gehen bei
    einem Neustart verloren.
    """

    def __init__(self, raw_hoflaeden: list[dict[str, Any]] | None = None) -> None:
        """Testdaten-Provider erzeugen.

        Ohne explizite ``raw_hoflaeden`` wird ein einzelner Beispiel-
        Hofladen als Platzhalter zurückgegeben.
        """
        self._raw_hoflaeden = (
            list(raw_hoflaeden) if raw_hoflaeden is not None else list(_DEFAULT_TEST_DATA)
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

    async def async_add_raw_hofladen(self, raw_hofladen: dict[str, Any]) -> None:
        """Einen rohen Hofladen-Datensatz im Arbeitsspeicher ergänzen.

        Wirft :class:`DuplicateHofladenIdError`, falls bereits ein
        Datensatz mit derselben ``id`` vorhanden ist. Die inhaltliche
        Validierung (Pflichtfelder, Wertebereiche etc.) obliegt bewusst
        nicht dem Provider, sondern ``parsing.parse_hofladen`` – siehe
        ``coordinator.HofKarteUpdateCoordinator.async_add_hofladen`` für
        den empfohlenen Aufrufweg inklusive Validierung.
        """
        await asyncio.sleep(0)

        neue_id = raw_hofladen.get("id")
        if any(vorhanden.get("id") == neue_id for vorhanden in self._raw_hoflaeden):
            raise DuplicateHofladenIdError(
                f"Ein Hofladen mit der ID '{neue_id}' existiert bereits."
            )

        self._raw_hoflaeden.append(dict(raw_hofladen))

    async def async_update_raw_hofladen(
        self, hofladen_id: str, updates: dict[str, Any]
    ) -> None:
        """Einzelne Felder eines bestehenden Hofladens im Arbeitsspeicher
        aktualisieren (teilweise Aktualisierung, siehe Basisklasse).

        Wirft :class:`HofladenNotFoundError`, falls keine ``id`` mit
        diesem Wert existiert. Die inhaltliche Validierung des
        resultierenden Gesamtdatensatzes obliegt bewusst nicht dem
        Provider, sondern ``parsing.parse_hofladen`` – siehe
        ``coordinator.HofKarteUpdateCoordinator.async_update_hofladen_sortiment``
        für den empfohlenen Aufrufweg inklusive Validierung.
        """
        await asyncio.sleep(0)

        for index, vorhandener in enumerate(self._raw_hoflaeden):
            if vorhandener.get("id") == hofladen_id:
                self._raw_hoflaeden[index] = {**vorhandener, **updates}
                return

        raise HofladenNotFoundError(
            f"Kein Hofladen mit der ID '{hofladen_id}' gefunden."
        )


_DEFAULT_TEST_DATA: list[dict[str, Any]] = [
    {
        "id": "platzhalter-hofladen",
        "name": "Platzhalter-Hofladen",
    },
]

