"""Internes, typisiertes Datenmodell für Hofläden.

Dieses Modul enthält ausschliesslich die interne fachliche Darstellung
eines Hofladens. Es kennt keine Rohdatenformate, keine Home-Assistant-
Entities, keine Persistenz und keine Netzwerklogik – das ist bewusst nicht
Teil dieser Einheit. Die Überführung von Rohdaten in dieses Modell erfolgt
getrennt in ``parsing.py``.

Alle Datenstrukturen sind unveränderlich (``frozen``), damit einmal
erzeugte Hofladen-Objekte nicht versehentlich mutiert werden können.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time


@dataclass(frozen=True, slots=True)
class Kategorie:
    """Eine Produktkategorie (z. B. „Gemüse“, „Milchprodukte“)."""

    id: str
    name: str


@dataclass(frozen=True, slots=True)
class Zahlungsart:
    """Eine akzeptierte Zahlungsart (z. B. „Bar“, „Twint“)."""

    id: str
    name: str


@dataclass(frozen=True, slots=True)
class Verkaufsart:
    """Eine Verkaufsart (z. B. „Ab-Hof-Verkauf“, „Marktstand“, „Lieferservice“)."""

    id: str
    name: str


@dataclass(frozen=True, slots=True)
class Merkmal:
    """Ein Merkmal des Hofladens (z. B. „Bio“, „Barrierefrei“, „Hofcafé“)."""

    id: str
    name: str


@dataclass(frozen=True, slots=True)
class Produkt:
    """Ein im Hofladen angebotenes Produkt."""

    id: str
    name: str
    kategorie_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Bild:
    """Ein optionales Bild des Hofladens."""

    url: str
    beschreibung: str | None = None


@dataclass(frozen=True, slots=True)
class Oeffnungszeit:
    """Eine regelmässige wöchentliche Öffnungszeit (ein Intervall an einem
    Wochentag).

    ``wochentag`` folgt ISO 8601 (1 = Montag ... 7 = Sonntag), analog zu
    ``datetime.date.isoweekday()``. Mehrere Intervalle pro Wochentag sind
    zulässig (z. B. „08:00–12:00“ und „14:00–18:00“) und werden als separate
    ``Oeffnungszeit``-Objekte abgebildet.

    ``beginn``/``ende`` sind bewusst als naive ``datetime.time`` modelliert:
    Es handelt sich um wiederkehrende Uhrzeiten ohne festes Datum, keine
    absoluten Zeitpunkte. Die Auswertung gegen die tatsächliche
    Home-Assistant-Zeitzone (für den berechneten Öffnungsstatus) ist
    bewusst nicht Teil dieser Einheit.
    """

    wochentag: int
    beginn: time
    ende: time


@dataclass(frozen=True, slots=True)
class Sonderoeffnungszeit:
    """Eine datumsbezogene Ausnahme von den regulären Öffnungszeiten.

    Deckt sowohl Sonderöffnungen (z. B. verlängerte Zeiten an Feiertagen)
    als auch vollständige Schliessungen (``geschlossen=True``, z. B. Ferien)
    über einen Datumsbereich ab. ``beginn``/``ende`` sind nur gesetzt, wenn
    ``geschlossen`` False ist.
    """

    datum_von: date
    datum_bis: date
    geschlossen: bool
    beginn: time | None = None
    ende: time | None = None


@dataclass(frozen=True, slots=True)
class Hofladen:
    """Interne, vollständig typisierte Darstellung eines Hofladens.

    ``id`` ist die stabile, eindeutige Kennung des Hofladens. Sie wird von
    der Datenquelle vorgegeben (siehe ``parsing.py``) und darf sich über
    die Zeit nicht ändern, da spätere Einheiten (Devices, Entities) sich
    darauf verlassen.
    """

    id: str
    name: str
    beschreibung: str | None = None
    adresse: str | None = None
    plz: str | None = None
    ort: str | None = None
    land: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    oeffnungszeiten: tuple[Oeffnungszeit, ...] = ()
    sonderoeffnungszeiten: tuple[Sonderoeffnungszeit, ...] = ()
    produkte: tuple[Produkt, ...] = ()
    kategorien: tuple[Kategorie, ...] = ()
    zahlungsarten: tuple[Zahlungsart, ...] = ()
    verkaufsarten: tuple[Verkaufsart, ...] = ()
    merkmale: tuple[Merkmal, ...] = ()
    bilder: tuple[Bild, ...] = ()
