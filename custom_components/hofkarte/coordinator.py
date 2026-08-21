"""DataUpdateCoordinator für HofKarte.

Ruft periodisch Rohdaten über einen :class:`HofladenDataProvider` ab,
validiert sie über ``parsing.parse_hofladen`` und stellt sie als Mapping
``Hofladen.id -> Hofladen`` für die gesamte Integration bereit.

Ein gemeinsamer Coordinator verhindert Mehrfachabfragen durch einzelne
Entities (siehe Globale Konventionen): Alle künftigen Entities lesen
ausschliesslich ``coordinator.data``, keine eigenen Abrufe.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DEFAULT_FETCH_TIMEOUT_SECONDS, DEFAULT_UPDATE_INTERVAL, DOMAIN
from .data_provider import HofladenDataProvider
from .models import Hofladen
from .parsing import HofladenValidationError, parse_hofladen

_LOGGER = logging.getLogger(__name__)


class HofKarteUpdateCoordinator(DataUpdateCoordinator[dict[str, Hofladen]]):
    """Koordiniert den Abruf und die Validierung der Hofladen-Daten."""

    def __init__(
        self,
        hass: HomeAssistant,
        provider: HofladenDataProvider,
        update_interval: timedelta = DEFAULT_UPDATE_INTERVAL,
        fetch_timeout_seconds: float = DEFAULT_FETCH_TIMEOUT_SECONDS,
    ) -> None:
        """Coordinator erzeugen.

        ``update_interval`` und ``fetch_timeout_seconds`` sind bewusst
        Konstruktorparameter (statt fest verdrahteter Werte) und damit
        konfigurierbar und testbar. Eine benutzerseitige Einstellung über
        einen Options Flow ist nicht Teil dieser Einheit, kann aber ohne
        Änderung an dieser Klasse ergänzt werden.
        """
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self._provider = provider
        self._fetch_timeout_seconds = fetch_timeout_seconds

    async def _async_update_data(self) -> dict[str, Hofladen]:
        """Rohdaten abrufen, validieren und als Hofladen-Mapping liefern.

        Netzwerk-/Datenquellenfehler und Zeitüberschreitungen werden in
        ``UpdateFailed`` übersetzt, damit sie Home Assistant nicht
        blockieren und über den Coordinator-Lifecycle (Availability,
        Retry) korrekt behandelt werden. Einzelne ungültige Datensätze
        führen nicht zum Abbruch des gesamten Abrufs, sondern werden
        übersprungen und geloggt.
        """
        try:
            async with asyncio.timeout(self._fetch_timeout_seconds):
                raw_hoflaeden = await self._provider.async_fetch_raw_hoflaeden()
        except TimeoutError as err:
            raise UpdateFailed(
                "Zeitüberschreitung beim Abruf der Hofladen-Daten."
            ) from err
        except Exception as err:  # noqa: BLE001 - unbekannte Provider-Fehler
            # Der Provider kann beliebige Fehler werfen (Netzwerk,
            # Dateisystem, etc.). Diese dürfen Home Assistant nicht
            # blockieren und werden daher in UpdateFailed übersetzt.
            raise UpdateFailed(
                f"Fehler beim Abruf der Hofladen-Daten: {err}"
            ) from err

        hoflaeden: dict[str, Hofladen] = {}
        for index, raw in enumerate(raw_hoflaeden):
            try:
                hofladen = parse_hofladen(raw)
            except HofladenValidationError as err:
                _LOGGER.warning(
                    "Ungültiger Hofladen-Datensatz #%s wird übersprungen: %s",
                    index,
                    err,
                )
                continue
            hoflaeden[hofladen.id] = hofladen

        return hoflaeden
