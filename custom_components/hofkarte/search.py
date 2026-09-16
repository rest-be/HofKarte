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
    """Ob eine der Sammlungen (Zahlungsarten, Verkaufsarten, ...) einen
    Eintrag mit exakt diesem Namen (case-insensitive) enthält."""
    gesucht = gesuchter_name.casefold()
    return any(
        getattr(eintrag, "name", "").casefold() == gesucht for eintrag in eintraege
    )


def _hat_angebot_mit_name_oder_gruppe(
    angebote: Iterable[object], gesuchter_text: str
) -> bool:
    """Ob eines der Angebote exakt diesen Namen trägt oder exakt diese
    Gruppe zugeordnet hat (case-insensitive). Deckt die früher getrennten
    Filter „Kategorie“ und „Produkt“ über ein gemeinsames Kriterium ab,
    seit beide Konzepte zu „Angebote“ zusammengelegt wurden."""
    gesucht = gesuchter_text.casefold()
    for angebot in angebote:
        if getattr(angebot, "name", "").casefold() == gesucht:
            return True
        if any(gruppe.casefold() == gesucht for gruppe in getattr(angebot, "gruppen", ())):
            return True
    return False


def find_hoflaeden(
    hoflaeden: Iterable[Hofladen],
    *,
    suchbegriff: str | None = None,
    angebot: str | None = None,
    verkaufsart: str | None = None,
    zahlungsart: str | None = None,
    merkmal: str | None = None,
    nur_geoeffnet: bool | None = None,
    now: datetime | None = None,
) -> list[Hofladen]:
    """Hofläden anhand der gesetzten Kriterien filtern (logisches UND).

    - ``suchbegriff``: Freitextsuche (case-insensitive Teilstring) über
      Name, Beschreibung und Ort.
    - ``angebot``: exakter, case-insensitiver Abgleich gegen den Namen
      **oder** eine der Gruppen eines Angebots (ersetzt die früher
      getrennten Filter „Kategorie“ und „Produkt“, siehe CHANGELOG).
    - ``verkaufsart``/``zahlungsart``/``merkmal``: exakter,
      case-insensitiver Namensabgleich gegen die jeweilige Sammlung des
      Hofladens (siehe ``models.Hofladen``).
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
        if angebot and not _hat_angebot_mit_name_oder_gruppe(
            hofladen.angebote, angebot
        ):
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
