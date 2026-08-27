"""Suche und Filter über Hofladen-Daten.

Reine, testbare Fachfunktion ohne Home-Assistant-Abhängigkeit – analog zu
``opening_hours.py``, ``distance.py`` und ``attributes.py``. ``services.py``
kapselt ausschliesslich die Anbindung an Home-Assistant-Actions (Parsing
des Service-Aufrufs, Validierung über das Schema, Aufbau der
Rückgabedaten) und enthält selbst keine Such-/Filterlogik.

Alle Filter werden UND-verknüpft: Ein Hofladen muss jedes gesetzte
Filterkriterium erfüllen, um in das Ergebnis aufgenommen zu werden. Nicht
gesetzte (``None``) Kriterien werden nicht angewendet.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from .models import Hofladen
from .opening_hours import is_open


def _enthaelt_suchbegriff(hofladen: Hofladen, suchbegriff: str) -> bool:
    """Ob der Suchbegriff (case-insensitive) in Name, Beschreibung oder Ort
    vorkommt."""
    begriff = suchbegriff.casefold()
    freitext_felder = (hofladen.name, hofladen.beschreibung, hofladen.ort)
    return any(
        feld is not None and begriff in feld.casefold() for feld in freitext_felder
    )


def _hat_eintrag_mit_namen(
    eintraege: Iterable[object], gesuchter_name: str
) -> bool:
    """Ob eine der Sammlungen (Kategorien, Produkte, ...) einen Eintrag mit
    exakt diesem Namen (case-insensitive) enthält."""
    gesucht = gesuchter_name.casefold()
    return any(
        getattr(eintrag, "name", "").casefold() == gesucht for eintrag in eintraege
    )


def find_hoflaeden(
    hoflaeden: Iterable[Hofladen],
    *,
    suchbegriff: str | None = None,
    kategorie: str | None = None,
    produkt: str | None = None,
    verkaufsart: str | None = None,
    zahlungsart: str | None = None,
    merkmal: str | None = None,
    nur_geoeffnet: bool | None = None,
    now: datetime | None = None,
) -> list[Hofladen]:
    """Hofläden anhand der gesetzten Kriterien filtern (logisches UND).

    - ``suchbegriff``: Freitextsuche (case-insensitive Teilstring) über
      Name, Beschreibung und Ort.
    - ``kategorie``/``produkt``/``verkaufsart``/``zahlungsart``/``merkmal``:
      exakter, case-insensitiver Namensabgleich gegen die jeweilige
      Sammlung des Hofladens (siehe ``models.Hofladen``).
    - ``nur_geoeffnet``: Wenn ``True``, werden nur aktuell geöffnete
      Hofläden geliefert (nutzt ``opening_hours.is_open`` – keine eigene
      Berechnungslogik, siehe Einheit 6/7). Ein Hofladen ohne bekannten
      Öffnungsstatus (``is_open`` liefert ``None``) gilt dabei als nicht
      passend, da nicht bestätigt werden kann, dass er geöffnet ist.
      ``now`` wird dafür benötigt; ist ``nur_geoeffnet`` gesetzt und
      ``now`` fehlt, wird ein ``ValueError`` ausgelöst.

    Gibt eine neue Liste zurück (Eingabereihenfolge bleibt erhalten);
    ``hoflaeden`` selbst wird nicht verändert.
    """
    if nur_geoeffnet is not None and now is None:
        raise ValueError(
            "'now' muss angegeben werden, wenn 'nur_geoeffnet' gesetzt ist."
        )

    ergebnis: list[Hofladen] = []
    for hofladen in hoflaeden:
        if suchbegriff and not _enthaelt_suchbegriff(hofladen, suchbegriff):
            continue
        if kategorie and not _hat_eintrag_mit_namen(hofladen.kategorien, kategorie):
            continue
        if produkt and not _hat_eintrag_mit_namen(hofladen.produkte, produkt):
            continue
        if verkaufsart and not _hat_eintrag_mit_namen(
            hofladen.verkaufsarten, verkaufsart
        ):
            continue
        if zahlungsart and not _hat_eintrag_mit_namen(
            hofladen.zahlungsarten, zahlungsart
        ):
            continue
        if merkmal and not _hat_eintrag_mit_namen(hofladen.merkmale, merkmal):
            continue
        if nur_geoeffnet:
            assert now is not None  # durch die Prüfung oben sichergestellt
            if is_open(hofladen, now) is not True:
                continue

        ergebnis.append(hofladen)

    return ergebnis
