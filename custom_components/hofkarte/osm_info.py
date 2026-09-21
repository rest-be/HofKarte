"""Ermittlung von Hofladen-Informationen anhand der im Verwaltungsformular
eingetragenen GPS-Koordinaten, über die OpenStreetMap-Overpass-API
(Issue #10, "Erweiterung OpenStreetMap zu #8").

## Architektonische Einordnung: eine zweite, bewusst begrenzte Ausnahme

HofKarte verfolgt den Grundsatz "kein externer/Cloud-/KI-Dienst" (siehe
``webseite_info.py``, Moduldoc). Dieses Modul führt dennoch eine zweite,
eigene ausgehende Netzwerkanfrage ein - diesmal an einen von HofKarte nicht
kontrollierten, aber öffentlichen, kostenlosen, kontofreien
OpenStreetMap-Community-Dienst (die Overpass API, ``overpass-api.de``).
Das wird bewusst als zweite, eng begrenzte Ausnahme behandelt, analog zur
bereits bestehenden Ausnahme für Leaflet/OpenStreetMap-Kartenkacheln
(siehe ``docs/architecture.md``, Abschnitt "Eingebettete Kartenansicht") -
kein kommerzieller Cloud-Dienst, kein LLM/KI-Dienst, kein
"Scraping-as-a-Service".

Anders als die rein clientseitig vom Browser geladenen Kartenkacheln (die
keine hofladenspezifischen Daten an OpenStreetMap übertragen, nur
generische Kachel-Indizes) sendet dieses Modul die **konkreten
Koordinaten eines bestimmten Hofladens serverseitig** an die Overpass API
- ausschliesslich auf ausdrücklichen Klick auf "📍 Ort in der Nähe
suchen" im Bearbeitungsformular, nie automatisch oder im Hintergrund
(siehe README.md, Abschnitt "Datenschutz- und Standort-Hinweise", sowie
SECURITY.md für die ausführliche Begründung dieser Ausnahme).

## Kein SSRF-Schutz über ``url_sicherheit.py`` nötig

Anders als bei ``webseite_info.py`` (dort bestimmt die Benutzerin/der
Benutzer die abgerufene URL selbst - klassisches SSRF-Risiko) ist das
Anfrageziel hier **fest im Code hinterlegt** (``OVERPASS_URL``) und wird
nie durch Benutzereingaben beeinflusst - nur Koordinaten und Radius
fliessen (als reine Zahlenwerte, nicht als Freitext) in den Anfragetext
ein. Eine SSRF-Prüfung à la ``url_sicherheit.py`` (Schema-/Host-Prüfung
einer benutzergesteuerten Ziel-URL) ist daher nicht anwendbar. Es gelten
stattdessen dieselben allgemeinen Abwehrmassnahmen gegen eine
möglicherweise übergrosse oder fehlerhafte Antwort wie in
``webseite_info.py``: ein Antwortgrössen-Limit (``MAX_ANTWORT_BYTES``)
sowie eine Zeitüberschreitung (``ABRUF_TIMEOUT_SEKUNDEN``).

## Tag-Auswahl

Das im Issue mitgelieferte Beispiel filtert nach dem generischen
``amenity``-Tag - dafür sind Hofläden auf OpenStreetMap in aller Regel
nicht getaggt (das ist die Tag-Familie für z. B. Cafés, Bänke, Briefkästen
u. Ä.). Läden werden auf OpenStreetMap stattdessen über ``shop=*``
getaggt; für landwirtschaftliche Hofläden ergänzend über
``craft=agricultural``. Diese Auswahl ist bewusst nicht abschliessend
(z. B. ``leisure=*``-Objekte werden nicht berücksichtigt), sondern eine
nachvollziehbare, auf den Anwendungsfall "Hofladen" zugeschnittene
Annäherung - lieber eine sinnvolle Teilmenge als eine überhastete
Rundum-Suche mit vielen irrelevanten Treffern.

## ``opening_hours``: begrenzter, dokumentierter Parser statt Freitext-Raten

OpenStreetMaps ``opening_hours``-Tag folgt einer eigenen, formal
spezifizierten Syntax (https://wiki.openstreetmap.org/wiki/Key:opening_hours)
- kein Fliesstext wie bei der Text-Heuristik aus Issue #9. Dieses Modul
unterstützt bewusst nur eine gängige Teilmenge dieser Syntax:
Semikolon-getrennte Regeln der Form ``<Tag(e)/-bereich(e)> <Zeit(en)>``,
mit englischen Zwei-Buchstaben-Wochentagskürzeln (``Mo,Tu,We,Th,Fr,Sa,Su``),
Wochentagbereichen (``Mo-Fr``), kommagetrennten Aufzählungen sowie
``HH:MM-HH:MM``-Zeitintervallen (auch mehrere pro Tag, kommagetrennt),
sowie den Sonderfall ``24/7``. **Nicht** unterstützt und bewusst
ignoriert (nicht interpretiert, nicht geraten): Feiertagsregeln (``PH``),
Datums-/Monatsbereiche, Kommentare in Klammern, ``off``/Ausnahmeregeln
sowie jede andere Syntax ausserhalb der genannten Teilmenge - eine Regel,
die nicht in dieses einfache Muster passt, wird komplett übersprungen,
statt eine falsche oder unvollständige Interpretation zu riskieren
("lieber nichts als falsch", siehe ``webseite_info.py``). Wie schon bei
der Text-Heuristik aus Issue #9 gilt zusätzlich: Liefern mehrere Regeln
unterschiedliche, widersprüchliche Zeiten für denselben Wochentag, wird
für diesen Wochentag kein Vorschlag geliefert.

## Review vor dem Speichern

Wie bei ``webseite_info.py`` liefert dieses Modul ausschliesslich
**Vorschlagsdaten zur Überprüfung** (siehe ``management.py``,
``ws_osm_info``) - das in Issue #9 eingeführte Bestätigungs-Popup wird
für diese zweite Datenquelle mitgenutzt (siehe
``static/hofkarte-panel.js``); es wird nichts automatisch gespeichert.
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
STANDARD_RADIUS_METER = 50
ABRUF_TIMEOUT_SEKUNDEN = 15
# Overpass-Antworten für einen kleinen Umkreis sind normalerweise winzig;
# 1 MB ist grosszügig genug für viele Treffer und begrenzt gleichzeitig
# den Ressourcenverbrauch durch eine übergrosse Antwort (siehe Moduldoc).
MAX_ANTWORT_BYTES = 1 * 1024 * 1024
_LESE_CHUNK_BYTES = 65536

_ERDRADIUS_METER = 6_371_000.0

# Für Hofläden relevante OpenStreetMap-Tags (siehe Moduldoc, "Tag-Auswahl").
_OVERPASS_FILTER = ('["shop"]', '["craft"="agricultural"]')

_OSM_WOCHENTAG = {
    "Mo": 1, "Tu": 2, "We": 3, "Th": 4, "Fr": 5, "Sa": 6, "Su": 7,
}
_OSM_TAG_ALTERNATIVEN = "|".join(_OSM_WOCHENTAG)
_OSM_TAG_REGEX = re.compile(
    rf"^({_OSM_TAG_ALTERNATIVEN})(-({_OSM_TAG_ALTERNATIVEN}))?$"
)
_OSM_ZEIT_REGEX = re.compile(r"^(\d{2}):(\d{2})-(\d{2}):(\d{2})$")


class OsmUngueltigeKoordinatenError(Exception):
    """Es wurden keine gültigen Latitude-/Longitude-Werte übergeben
    (Fehlerfall 1)."""


class OsmNichtErreichbarError(Exception):
    """Die Overpass API konnte nicht erreicht oder ihre Antwort nicht
    gelesen werden (Fehlerfall 2: Verbindungsfehler, Timeout,
    HTTP-Fehlerstatus, unlesbare/zu grosse Antwort)."""


class OsmKeineOrteGefundenError(Exception):
    """Die Overpass API war erreichbar, im angegebenen Umkreis wurden
    aber keine (benannten) Orte gefunden (Fehlerfall 3)."""


@dataclass(frozen=True, slots=True)
class OsmOrt:
    """Ein über die Overpass API gefundener, noch ungeprüfter
    Orts-Vorschlag (Issue #10). Reine Vorschlagsdaten zur Überprüfung
    durch die Benutzerin/den Benutzer im Verwaltungs-Panel - nichts
    hiervon wird automatisch gespeichert (siehe ``management.py``,
    ``ws_osm_info``). Optionale Felder sind ``None`` bzw. leer, wenn die
    jeweilige Information nicht vorhanden war (siehe Moduldoc, Prinzip
    "lieber nichts als falsch")."""

    name: str
    adresse: str | None = None
    plz: str | None = None
    ort: str | None = None
    website: str | None = None
    oeffnungszeiten: tuple[dict[str, Any], ...] = ()
    entfernung_meter: float | None = None


def _str_or_none(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _sind_gueltige_koordinaten(latitude: Any, longitude: Any) -> bool:
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        return False
    return -90 <= lat <= 90 and -180 <= lon <= 180


def _entfernung_meter(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Grosskreisentfernung zweier WGS84-Koordinaten (Haversine-Formel) -
    dient nur der Sortierung/Anzeige in der Trefferauswahl bei mehreren
    Treffern, nicht der eigentlichen Umkreis-Filterung (die übernimmt die
    Overpass API selbst über ``around:``)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return _ERDRADIUS_METER * 2 * math.asin(math.sqrt(a))


def _adresse_aus_tags(tags: dict[str, Any]) -> str | None:
    strasse = _str_or_none(tags.get("addr:street"))
    hausnummer = _str_or_none(tags.get("addr:housenumber"))
    if strasse and hausnummer:
        return f"{strasse} {hausnummer}"
    return strasse or hausnummer


def _wochentag_bereich(von_tag: int, bis_tag: int | None) -> list[int]:
    """Liste der Wochentage eines Bereichs (z. B. Mo-Fr -> [1,2,3,4,5]),
    inkl. über die Wochengrenze laufender Bereiche (z. B. Sa-Mo ->
    [6,7,1]). Bewusst als eigene, kleine Kopie statt eines Imports aus
    ``webseite_info.py`` gehalten - beide Module sollen unabhängig
    voneinander lesbar/wartbar bleiben, ohne dass ein privater Helfer
    modulübergreifend geteilt wird."""
    if bis_tag is None:
        return [von_tag]
    if von_tag <= bis_tag:
        return list(range(von_tag, bis_tag + 1))
    return list(range(von_tag, 8)) + list(range(1, bis_tag + 1))


def _normalisiere_osm_uhrzeit(stunde: str, minute: str) -> str | None:
    try:
        h = int(stunde)
        m = int(minute)
    except ValueError:
        return None
    if h == 24 and m == 0:
        # OpenStreetMap erlaubt "24:00" als Tagesende. HofKarte speichert
        # "durchgehend geöffnet" als 00:00-23:59 (siehe FULL_DAY in
        # static/hofkarte-panel.js) - dieselbe Konvention wird hier
        # angewendet.
        return "23:59"
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return f"{h:02d}:{m:02d}"


def _parse_osm_regel(regel: str) -> dict[int, list[tuple[str, str]]] | None:
    """Parst eine einzelne, semikolon-getrennte ``opening_hours``-Regel
    (z. B. ``"Mo-Fr 08:00-18:00"`` oder ``"Sa,Su 08:00-12:00,14:00-16:00"``)
    zu einer Zuordnung Wochentag -> Liste der Zeitintervalle, die **diese
    eine Regel** für den jeweiligen Tag festlegt (mehrere Intervalle pro
    Tag, z. B. eine Mittagspause, sind hier ausdrücklich kein Widerspruch
    - erst wenn zwei **unterschiedliche Regeln** für denselben Tag
    abweichende Angaben liefern, ist das ein Widerspruch, siehe
    ``_extrahiere_oeffnungszeiten_osm``). Liefert ``None``, wenn die Regel
    nicht der unterstützten Teilmenge entspricht (siehe Moduldoc) - dann
    wird sie vom Aufrufer vollständig ignoriert, nicht teilweise
    interpretiert."""
    teile = regel.strip().split(None, 1)
    if len(teile) != 2:
        return None
    tage_teil, zeiten_teil = teile

    tage: list[int] = []
    for stueck in tage_teil.split(","):
        treffer = _OSM_TAG_REGEX.match(stueck.strip())
        if not treffer:
            return None
        von = _OSM_WOCHENTAG[treffer.group(1)]
        bis = _OSM_WOCHENTAG[treffer.group(3)] if treffer.group(3) else None
        tage.extend(_wochentag_bereich(von, bis))

    zeiten: list[tuple[str, str]] = []
    for stueck in zeiten_teil.split(","):
        treffer = _OSM_ZEIT_REGEX.match(stueck.strip())
        if not treffer:
            return None
        beginn = _normalisiere_osm_uhrzeit(treffer.group(1), treffer.group(2))
        ende = _normalisiere_osm_uhrzeit(treffer.group(3), treffer.group(4))
        if beginn is None or ende is None or beginn == ende:
            return None
        zeiten.append((beginn, ende))

    return {tag: list(zeiten) for tag in tage}


def _extrahiere_oeffnungszeiten_osm(opening_hours: Any) -> tuple[dict[str, Any], ...]:
    """Übersetzt den ``opening_hours``-Tag eines OSM-Objekts in HofKartes
    ``oeffnungszeiten``-Modell (siehe Moduldoc für die unterstützte
    Teilmenge und deren Grenzen).

    Pro Wochentag wird die Menge der von den einzelnen Regeln jeweils
    dafür festgelegten Zeit-"Signaturen" gesammelt (eine Signatur = alle
    Zeitintervalle, die EINE Regel für diesen Tag festlegt). Liefern alle
    Regeln, die sich zu einem Tag äussern, dieselbe Signatur (der übliche
    Fall: nur eine einzige Regel betrifft den Tag), werden deren
    Intervalle übernommen - auch wenn es mehrere sind (z. B.
    Mittagspause). Liefern unterschiedliche Regeln unterschiedliche
    Signaturen für denselben Tag, ist das ein echter Widerspruch - dann
    gibt es für diesen Tag keinen Vorschlag (andere, eindeutige
    Wochentage sind davon nicht betroffen)."""
    if not isinstance(opening_hours, str) or not opening_hours.strip():
        return ()

    wert = opening_hours.strip()
    if wert.lower() == "24/7":
        return tuple({"wochentag": tag, "beginn": "00:00", "ende": "23:59"} for tag in range(1, 8))

    kandidaten: dict[int, set[frozenset[tuple[str, str]]]] = {}
    for regel in wert.split(";"):
        regel = regel.strip()
        if not regel:
            continue
        geparst = _parse_osm_regel(regel)
        if geparst is None:
            continue  # nicht unterstützte Syntax - wird ignoriert, nicht geraten
        for tag, zeiten_liste in geparst.items():
            kandidaten.setdefault(tag, set()).add(frozenset(zeiten_liste))

    ergebnis: list[dict[str, Any]] = []
    for tag in sorted(kandidaten):
        signaturen = kandidaten[tag]
        if len(signaturen) != 1:
            continue  # widersprüchliche Regeln für diesen Tag -> kein Vorschlag
        for beginn, ende in sorted(next(iter(signaturen))):
            ergebnis.append({"wochentag": tag, "beginn": beginn, "ende": ende})
    return tuple(ergebnis)


def _baue_overpass_query(latitude: float, longitude: float, radius_meter: int) -> str:
    umkreis = f"around:{int(radius_meter)},{latitude},{longitude}"
    zeilen = []
    for filt in _OVERPASS_FILTER:
        zeilen.append(f"  node({umkreis}){filt};")
        zeilen.append(f"  way({umkreis}){filt};")
    return "[out:json][timeout:10];\n(\n" + "\n".join(zeilen) + "\n);\nout center tags;"


async def _rufe_overpass_ab(session: aiohttp.ClientSession, query: str) -> dict[str, Any]:
    """Ruft die Overpass API mit ``query`` auf und liefert die (begrenzt
    gelesene) JSON-Antwort. Das Anfrageziel ist fest (``OVERPASS_URL``),
    keine Weiterleitungsauflösung/SSRF-Prüfung nötig (siehe Moduldoc)."""
    timeout = aiohttp.ClientTimeout(total=ABRUF_TIMEOUT_SEKUNDEN)
    try:
        async with session.post(
            OVERPASS_URL, data={"data": query}, timeout=timeout
        ) as antwort:
            if antwort.status >= 400:
                raise OsmNichtErreichbarError(
                    "Die Overpass API hat einen Fehler zurückgegeben "
                    f"(Status {antwort.status})."
                )

            rohdaten = bytearray()
            async for chunk in antwort.content.iter_chunked(_LESE_CHUNK_BYTES):
                rohdaten.extend(chunk)
                if len(rohdaten) > MAX_ANTWORT_BYTES:
                    raise OsmNichtErreichbarError(
                        "Die Antwort der Overpass API ist zu gross, um "
                        "verarbeitet zu werden."
                    )

            try:
                return json.loads(bytes(rohdaten).decode("utf-8", errors="replace"))
            except json.JSONDecodeError as err:
                raise OsmNichtErreichbarError(
                    "Die Antwort der Overpass API konnte nicht gelesen werden."
                ) from err
    except OsmNichtErreichbarError:
        raise
    except (aiohttp.ClientError, TimeoutError) as err:
        raise OsmNichtErreichbarError(
            "Die Overpass API konnte nicht erreicht werden."
        ) from err


def _koordinaten_aus_element(element: dict[str, Any]) -> tuple[float, float] | None:
    """Liefert die Koordinate eines Overpass-Elements - bei Nodes direkt
    ``lat``/``lon``, bei Ways/Relations der von ``out center`` gelieferte
    Mittelpunkt (``center``)."""
    if element.get("type") == "node":
        lat, lon = element.get("lat"), element.get("lon")
    else:
        zentrum = element.get("center")
        lat, lon = (zentrum or {}).get("lat"), (zentrum or {}).get("lon")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        return float(lat), float(lon)
    return None


async def async_ermittle_osm_orte(
    hass: HomeAssistant,
    latitude: Any,
    longitude: Any,
    radius_meter: int = STANDARD_RADIUS_METER,
) -> tuple[OsmOrt, ...]:
    """Sucht über die Overpass API nach Hofladen-artigen Orten im Umkreis
    von ``latitude``/``longitude`` und liefert sie nach Entfernung
    sortiert zurück.

    Wirft (siehe Moduldoc für die jeweilige Bedeutung):

    - :class:`OsmUngueltigeKoordinatenError` - keine gültigen
      Latitude-/Longitude-Werte übergeben (Fehlerfall 1).
    - :class:`OsmNichtErreichbarError` - Verbindungsfehler, Timeout,
      HTTP-Fehlerstatus oder unlesbare/zu grosse Antwort (Fehlerfall 2).
    - :class:`OsmKeineOrteGefundenError` - die Overpass API war
      erreichbar, es wurden aber keine (benannten) Orte im Umkreis
      gefunden (Fehlerfall 3).

    Das Ergebnis ist ausschliesslich eine Liste von Vorschlägen zur
    Überprüfung - siehe ``management.py``, ``ws_osm_info``.
    """
    if not _sind_gueltige_koordinaten(latitude, longitude):
        raise OsmUngueltigeKoordinatenError(
            "Es sind keine gültigen Latitude-/Longitude-Werte vorhanden."
        )

    lat, lon = float(latitude), float(longitude)
    query = _baue_overpass_query(lat, lon, radius_meter)
    session = async_get_clientsession(hass)
    daten = await _rufe_overpass_ab(session, query)

    elemente = daten.get("elements")
    if not isinstance(elemente, list):
        raise OsmNichtErreichbarError(
            "Die Antwort der Overpass API hat nicht das erwartete Format."
        )

    orte: list[OsmOrt] = []
    for element in elemente:
        if not isinstance(element, dict):
            continue
        tags = element.get("tags")
        if not isinstance(tags, dict):
            continue

        name = _str_or_none(tags.get("name"))
        if name is None:
            continue  # kein sinnvoller Auswahleintrag ohne Namen (siehe Moduldoc)

        koordinate = _koordinaten_aus_element(element)
        entfernung = (
            _entfernung_meter(lat, lon, koordinate[0], koordinate[1])
            if koordinate is not None
            else None
        )

        orte.append(
            OsmOrt(
                name=name,
                adresse=_adresse_aus_tags(tags),
                plz=_str_or_none(tags.get("addr:postcode")),
                ort=_str_or_none(tags.get("addr:city")),
                website=(
                    _str_or_none(tags.get("website"))
                    or _str_or_none(tags.get("contact:website"))
                ),
                oeffnungszeiten=_extrahiere_oeffnungszeiten_osm(tags.get("opening_hours")),
                entfernung_meter=round(entfernung, 1) if entfernung is not None else None,
            )
        )

    if not orte:
        raise OsmKeineOrteGefundenError(
            "Im angegebenen Umkreis wurden keine Orte gefunden."
        )

    orte.sort(key=lambda ort: (ort.entfernung_meter is None, ort.entfernung_meter))
    return tuple(orte)
