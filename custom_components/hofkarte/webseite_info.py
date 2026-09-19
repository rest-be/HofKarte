"""Ermittlung von Hofladen-Informationen aus einer vom Benutzer angegebenen
Website (Issue #8, "Informationen aus Homepage").

## Architektonische Tragweite: erste eigene ausgehende Netzwerkanfrage

Dieses Modul führt die **erste eigene, ausgehende HTTP-Anfrage im
Backend-Code von HofKarte** aus. Bisher delegierte HofKarte jede
Netzwerkkommunikation entweder an Home Assistants eigene
``image``-Entity-Infrastruktur (Hofladen-Bilder, siehe ``images.py``) oder
an den Browser (Leaflet/OpenStreetMap-Kartenkacheln). Diese Erweiterung ist
daher bewusst und ausführlich dokumentiert (siehe README.md, Abschnitt
„Datenschutz- und Standort-Hinweise“, SECURITY.md sowie
``quality_scale.yaml``, Kriterium ``inject-websession``).

## Kein externer/Cloud-/KI-Dienst

Die Extraktion erfolgt **vollständig lokal und deterministisch** – es wird
kein Cloud-Dienst, kein LLM und kein "Scraping-as-a-Service" eingebunden.
Das würde dem Kernprinzip "kein externer Dienst" widersprechen, das dieses
Projekt konsequent verfolgt. Stattdessen wird ausschliesslich
maschinenlesbare, von der Zielseite selbst veröffentlichte, strukturierte
Auszeichnung ausgewertet:

1. **Primär:** schema.org-konforme JSON-LD-Daten
   (``<script type="application/ld+json">``), typischerweise vom Typ
   ``LocalBusiness`` oder einer Unterart davon. Diese Daten sind
   maschinenlesbar und werden ohne Heuristik zuverlässig ausgewertet.
2. **Ergänzend, nur zur Lückenfüllung:** ``<title>`` (als schwacher,
   aber unverfälschter Namens-Fallback, falls JSON-LD keinen Namen
   liefert) sowie ``<meta name="description">`` (als Beschreibungs-
   Fallback). Beides sind Rohdaten der Seite selbst, nichts wird daraus
   interpretiert oder geraten.

Es findet **keine KI-artige Freitext-Interpretation** statt (z. B. aus
Fliesstext "vermutete" Öffnungszeiten oder Adressen). Keine
Python-Bibliothek ausserhalb der Standardbibliothek wird benötigt
(``html.parser``, ``json``) – es entsteht dadurch bewusst **keine neue
Abhängigkeit**.

## Prinzip "lieber nichts als falsch"

Felder, die sich nicht zuverlässig strukturiert auslesen lassen, bleiben
bewusst leer, statt eine möglicherweise falsche Angabe vorzuschlagen. Da
die Benutzerin/der Benutzer die ermittelten Werte ohnehin vor dem
Speichern prüft (siehe ``management.py``, ``ws_webseite_info``), ist ein
leeres Feld der Benutzererfahrung nicht abträglich, eine erfundene Angabe
hingegen schon.

Bekannte, bewusste Einschränkung: Das kompakte schema.org-Kurzformat für
Öffnungszeiten (``openingHours``, z. B. ``"Mo-Fr 08:00-18:00"``) wird
**nicht** ausgewertet – nur das vollständig strukturierte
``openingHoursSpecification`` (Liste einzelner Wochentag/Uhrzeit-Objekte).
Das Kurzformat erfordert Tagesbereich-Parsing (``Mo-Fr`` → mehrere
Wochentage), das eine zusätzliche, potenziell fehleranfällige
Interpretationsschicht wäre; angesichts von "lieber nichts als falsch"
wurde bewusst auf diese zusätzliche Komplexität verzichtet.

## SSRF-Schutz – über den Standard aus ``images.py`` hinaus

Diese Funktion ist ein **sensitiveres Angriffsziel** als die bestehende
Bild-URL-Prüfung in ``images.py``: HofKarte führt den HTTP-Request hier
selbst aus (nicht delegiert an eine Home-Assistant-Komponente) und
verarbeitet den Antwortinhalt selbst (nicht nur eine URL-Referenz). Neben
der syntaktischen Grundprüfung aus ``url_sicherheit.py`` (Schema,
Zugangsdaten, "localhost", private/interne IP-Literale – siehe dessen
Moduldoc zur bewussten Grenze ohne DNS-Auflösung) gelten hier zusätzlich:

- **Antwortgrössen-Limit** (``MAX_ANTWORT_BYTES``): verhindert
  übermässigen Speicher-/Bandbreitenverbrauch durch sehr grosse oder
  gezielt präparierte Antworten.
- **Content-Type-Prüfung**: nur HTML-artige Antworten werden geparst.
- **Zeitüberschreitung** (``ABRUF_TIMEOUT_SEKUNDEN``): ein nicht
  antwortender Server blockiert die Verwaltungsoberfläche nicht
  unbegrenzt.
- **Manuelle, erneut geprüfte Weiterleitungen**: Automatische
  Weiterleitungen (``aiohttp``s eingebautes ``allow_redirects``) würden
  eine erste, sichere URL akzeptieren und stillschweigend einem
  ``Location``-Header an ein beliebiges (auch internes) Ziel folgen. Hier
  wird jede Weiterleitung einzeln aufgelöst und erneut gegen dieselbe
  Sicherheitsprüfung wie die ursprüngliche URL geprüft, mit einer festen
  Obergrenze an Sprüngen (``_MAX_REDIRECTS``).

Der HTTP-Abruf verwendet Home Assistants verwaltete Client-Session
(``homeassistant.helpers.aiohttp_client.async_get_clientsession``) – keine
eigene, unverwaltete ``aiohttp.ClientSession`` (siehe ``quality_scale.yaml``,
Kriterium ``inject-websession``).

Weiterhin **nicht** abgedeckt (bewusst, wie in ``url_sicherheit.py``
dokumentiert): DNS-Rebinding (ein Domainname, der erst beim tatsächlichen
Verbindungsaufbau auf eine private IP auflöst). Das entspricht der
bestehenden, dokumentierten Grenze aus ``images.py``.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from yarl import URL as YarlURL

from .url_sicherheit import ist_sichere_externe_url

_LOGGER = logging.getLogger(__name__)

# 2 MB genügt für praktisch jede normale Homepage-HTML-Seite und begrenzt
# gleichzeitig den Ressourcenverbrauch durch übergrosse Antworten.
MAX_ANTWORT_BYTES = 2 * 1024 * 1024
ABRUF_TIMEOUT_SEKUNDEN = 10
_LESE_CHUNK_BYTES = 65536
_MAX_REDIRECTS = 3
_ERLAUBTE_CONTENT_TYPES = ("text/html", "application/xhtml+xml")
_WEITERLEITUNGS_STATUS = (301, 302, 303, 307, 308)

_WOCHENTAGE_SCHEMA_ORG = {
    "monday": 1,
    "tuesday": 2,
    "wednesday": 3,
    "thursday": 4,
    "friday": 5,
    "saturday": 6,
    "sunday": 7,
}


class WebseiteUngueltigeUrlError(Exception):
    """Es wurde keine Website-Adresse angegeben, oder sie ist syntaktisch
    ungültig bzw. zeigt auf ein nicht erlaubtes Ziel (Fehlerfall 1)."""


class WebseiteNichtErreichbarError(Exception):
    """Die Website konnte nicht erreicht oder nicht gelesen werden
    (Fehlerfall 2: Verbindungsfehler, Timeout, HTTP-Fehlerstatus,
    ungültiges/nicht-HTML-Antwortformat, zu grosse Antwort, unsichere
    Weiterleitung)."""


class WebseiteInformationenNichtGefundenError(Exception):
    """Die Website war erreichbar, es konnten aber keine verwertbaren
    Informationen ermittelt werden (Fehlerfall 3)."""


@dataclass(frozen=True, slots=True)
class WebseiteInfo:
    """Aus einer Website ermittelte, noch ungeprüfte Hofladen-Informationen.

    Reine Vorschlagsdaten zur Überprüfung durch die Benutzerin/den
    Benutzer im Verwaltungs-Panel – nichts hiervon wird automatisch
    gespeichert (siehe ``management.py``, ``ws_webseite_info``). Felder
    sind ``None`` bzw. leer, wenn die jeweilige Information nicht
    zuverlässig ermittelt werden konnte (siehe Moduldoc, Prinzip "lieber
    nichts als falsch").
    """

    name: str | None = None
    beschreibung: str | None = None
    adresse: str | None = None
    plz: str | None = None
    ort: str | None = None
    land: str | None = None
    oeffnungszeiten: tuple[dict[str, Any], ...] = ()
    angebote: tuple[str, ...] = ()
    zahlungsarten: tuple[str, ...] = ()

    def ist_leer(self) -> bool:
        """Ob überhaupt keine verwertbare Information ermittelt wurde."""
        return not (
            self.name
            or self.beschreibung
            or self.adresse
            or self.plz
            or self.ort
            or self.land
            or self.oeffnungszeiten
            or self.angebote
            or self.zahlungsarten
        )


def _str_or_none(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


class _SeitenParser(HTMLParser):
    """Extrahiert ausschliesslich ``<title>``, ``<meta name="description">``
    und den Inhalt aller ``<script type="application/ld+json">``-Blöcke aus
    einer HTML-Seite. Bewusst mit der Python-Standardbibliothek
    (``html.parser``) statt einer zusätzlichen Abhängigkeit umgesetzt."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.titel = ""
        self.beschreibung_meta: str | None = None
        self.json_ld_bloecke: list[str] = []
        self._in_title = False
        self._in_json_ld = False
        self._json_ld_puffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: (value or "") for key, value in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = attrs_dict.get("name", "").strip().lower()
            inhalt = attrs_dict.get("content", "").strip()
            if name == "description" and inhalt and self.beschreibung_meta is None:
                self.beschreibung_meta = inhalt
        elif tag == "script" and attrs_dict.get("type", "").strip().lower() == (
            "application/ld+json"
        ):
            self._in_json_ld = True
            self._json_ld_puffer = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "script" and self._in_json_ld:
            self._in_json_ld = False
            self.json_ld_bloecke.append("".join(self._json_ld_puffer))

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.titel += data
        elif self._in_json_ld:
            self._json_ld_puffer.append(data)


def _flatten_json_ld(wert: Any) -> list[dict[str, Any]]:
    """Baut eine flache Liste von JSON-LD-Objekten auf – löst dabei
    Listen sowie das schema.org-``@graph``-Konstrukt auf (mehrere
    Entitäten in einem einzigen ``<script>``-Block)."""
    if isinstance(wert, list):
        ergebnis: list[dict[str, Any]] = []
        for eintrag in wert:
            ergebnis.extend(_flatten_json_ld(eintrag))
        return ergebnis
    if isinstance(wert, dict):
        graph = wert.get("@graph")
        if isinstance(graph, list):
            return _flatten_json_ld(graph)
        return [wert]
    return []


def _iter_json_ld_objekte(bloecke: list[str]) -> list[dict[str, Any]]:
    objekte: list[dict[str, Any]] = []
    for roh in bloecke:
        try:
            geparst = json.loads(roh)
        except (json.JSONDecodeError, ValueError):
            continue
        objekte.extend(_flatten_json_ld(geparst))
    return objekte


def _ist_business_kandidat(obj: dict[str, Any]) -> bool:
    if not isinstance(obj.get("name"), str) or not obj["name"].strip():
        return False
    geeignete_felder = (
        "address",
        "openingHours",
        "openingHoursSpecification",
        "telephone",
        "priceRange",
        "paymentAccepted",
        "makesOffer",
    )
    return any(feld in obj for feld in geeignete_felder)


def _waehle_business_objekt(objekte: list[dict[str, Any]]) -> dict[str, Any] | None:
    for obj in objekte:
        if isinstance(obj, dict) and _ist_business_kandidat(obj):
            return obj
    return None


def _extrahiere_adresse(
    obj: dict[str, Any],
) -> tuple[str | None, str | None, str | None, str | None]:
    adresse = obj.get("address")
    if isinstance(adresse, str):
        return _str_or_none(adresse), None, None, None
    if isinstance(adresse, dict):
        strasse = _str_or_none(adresse.get("streetAddress"))
        plz = _str_or_none(adresse.get("postalCode"))
        ort = _str_or_none(adresse.get("addressLocality"))
        land_roh = adresse.get("addressCountry")
        if isinstance(land_roh, dict):
            land = _str_or_none(land_roh.get("name"))
        else:
            land = _str_or_none(land_roh)
        return strasse, plz, ort, land
    return None, None, None, None


def _wochentag_aus_schema_org(wert: str) -> int | None:
    kurz = wert.strip().rsplit("/", 1)[-1].strip().lower()
    return _WOCHENTAGE_SCHEMA_ORG.get(kurz)


def _parse_uhrzeit(wert: Any) -> str | None:
    if not isinstance(wert, str):
        return None
    wert = wert.strip()
    if re.fullmatch(r"\d{2}:\d{2}(:\d{2})?", wert):
        return wert[:5]
    return None


def _extrahiere_oeffnungszeiten(obj: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Wertet ausschliesslich das vollständig strukturierte
    ``openingHoursSpecification`` aus (siehe Moduldoc zur bewusst nicht
    unterstützten Kurzform ``openingHours``). Unvollständige oder
    widersprüchliche Einzeleinträge werden übersprungen, nicht geraten."""
    spec = obj.get("openingHoursSpecification")
    if spec is None:
        return ()
    eintraege = spec if isinstance(spec, list) else [spec]

    ergebnis: list[dict[str, Any]] = []
    for eintrag in eintraege:
        if not isinstance(eintrag, dict):
            continue
        opens = _parse_uhrzeit(eintrag.get("opens"))
        closes = _parse_uhrzeit(eintrag.get("closes"))
        if opens is None or closes is None or opens == closes:
            continue

        tage_roh = eintrag.get("dayOfWeek")
        tage = tage_roh if isinstance(tage_roh, list) else [tage_roh]
        for tag_roh in tage:
            if not isinstance(tag_roh, str):
                continue
            wochentag = _wochentag_aus_schema_org(tag_roh)
            if wochentag is None:
                continue
            ergebnis.append({"wochentag": wochentag, "beginn": opens, "ende": closes})

    return tuple(ergebnis)


def _extrahiere_zahlungsarten(obj: dict[str, Any]) -> tuple[str, ...]:
    wert = obj.get("paymentAccepted")
    if isinstance(wert, str):
        teile = [teil.strip() for teil in wert.split(",")]
        return tuple(teil for teil in teile if teil)
    if isinstance(wert, list):
        return tuple(
            str(teil).strip() for teil in wert if isinstance(teil, str) and teil.strip()
        )
    return ()


def _extrahiere_angebote(obj: dict[str, Any]) -> tuple[str, ...]:
    angebote_roh = obj.get("makesOffer")
    if angebote_roh is None:
        return ()
    eintraege = angebote_roh if isinstance(angebote_roh, list) else [angebote_roh]

    namen: list[str] = []
    for eintrag in eintraege:
        if not isinstance(eintrag, dict):
            continue
        name: str | None = None
        item = eintrag.get("itemOffered")
        if isinstance(item, dict):
            name = _str_or_none(item.get("name"))
        if name is None:
            name = _str_or_none(eintrag.get("name"))
        if name is not None:
            namen.append(name)

    return tuple(namen)


def _extrahiere_aus_html(html_text: str) -> WebseiteInfo:
    parser = _SeitenParser()
    try:
        parser.feed(html_text)
    except Exception:  # noqa: BLE001 - HTMLParser soll nie zum Absturz führen
        _LOGGER.debug("Website-HTML konnte nicht vollständig geparst werden.")

    objekte = _iter_json_ld_objekte(parser.json_ld_bloecke)
    business = _waehle_business_objekt(objekte)

    name: str | None = None
    beschreibung: str | None = None
    adresse = plz = ort = land = None
    oeffnungszeiten: tuple[dict[str, Any], ...] = ()
    angebote: tuple[str, ...] = ()
    zahlungsarten: tuple[str, ...] = ()

    if business is not None:
        name = _str_or_none(business.get("name"))
        beschreibung = _str_or_none(business.get("description"))
        adresse, plz, ort, land = _extrahiere_adresse(business)
        oeffnungszeiten = _extrahiere_oeffnungszeiten(business)
        angebote = _extrahiere_angebote(business)
        zahlungsarten = _extrahiere_zahlungsarten(business)

    if beschreibung is None:
        # Nicht erfunden, sondern die von der Seite selbst hinterlegte
        # Meta-Beschreibung - ein Standard-SEO-Feld.
        beschreibung = _str_or_none(parser.beschreibung_meta)

    if name is None:
        # Schwacher, aber unverfälschter Fallback: der komplette,
        # getrimmte Seitentitel. Ein Versuch, daraus nur den
        # "Betriebsnamen-Teil" herauszulösen (z. B. vor einem " - " oder
        # " | "), wäre Raten über die Struktur des Titels - siehe Moduldoc,
        # Prinzip "lieber nichts als falsch". Der volle Titel wird daher
        # unverändert übernommen; die Benutzerin/der Benutzer prüft und
        # kürzt ihn bei Bedarf selbst vor dem Speichern.
        name = _str_or_none(parser.titel)

    return WebseiteInfo(
        name=name,
        beschreibung=beschreibung,
        adresse=adresse,
        plz=plz,
        ort=ort,
        land=land,
        oeffnungszeiten=oeffnungszeiten,
        angebote=angebote,
        zahlungsarten=zahlungsarten,
    )


def _aufgeloeste_weiterleitungsziel(basis_url: str, location_header: str) -> str:
    """Löst einen (ggf. relativen) ``Location``-Header gegenüber der
    aktuellen URL auf."""
    return str(YarlURL(basis_url).join(YarlURL(location_header)))


async def _lese_antwort_text(antwort: aiohttp.ClientResponse) -> str:
    """Liest den Antwortkörper begrenzt auf ``MAX_ANTWORT_BYTES`` und
    dekodiert ihn. Muss innerhalb des ``async with``-Blocks der Anfrage
    aufgerufen werden."""
    content_type = (antwort.content_type or "").lower()
    if not any(content_type.startswith(t) for t in _ERLAUBTE_CONTENT_TYPES):
        raise WebseiteNichtErreichbarError(
            "Die Antwort der Website ist keine lesbare HTML-Seite "
            f"(Content-Type: '{content_type or 'unbekannt'}')."
        )

    rohdaten = bytearray()
    async for chunk in antwort.content.iter_chunked(_LESE_CHUNK_BYTES):
        rohdaten.extend(chunk)
        if len(rohdaten) > MAX_ANTWORT_BYTES:
            raise WebseiteNichtErreichbarError(
                "Die Antwort der Website ist zu gross, um verarbeitet zu werden."
            )

    try:
        encoding = antwort.get_encoding()
    except (LookupError, RuntimeError, UnicodeError):
        encoding = "utf-8"

    return bytes(rohdaten).decode(encoding, errors="replace")


async def _hole_html(session: aiohttp.ClientSession, url: str) -> str:
    """Ruft ``url`` ab und liefert den (begrenzten) HTML-Text zurück.

    Löst Weiterleitungen bewusst **manuell** auf (``allow_redirects=False``
    je Einzelanfrage) und prüft jedes Weiterleitungsziel erneut über
    ``ist_sichere_externe_url`` – siehe Moduldoc, Abschnitt „SSRF-Schutz“.
    """
    timeout = aiohttp.ClientTimeout(total=ABRUF_TIMEOUT_SEKUNDEN)
    aktuelle_url = url

    for sprung in range(_MAX_REDIRECTS + 1):
        try:
            async with session.get(
                aktuelle_url, timeout=timeout, allow_redirects=False
            ) as antwort:
                if antwort.status in _WEITERLEITUNGS_STATUS:
                    location = antwort.headers.get("Location")
                    if not location:
                        raise WebseiteNichtErreichbarError(
                            "Die Website hat eine Weiterleitung ohne Ziel gesendet."
                        )
                    ziel = _aufgeloeste_weiterleitungsziel(aktuelle_url, location)
                    if not ist_sichere_externe_url(ziel):
                        raise WebseiteNichtErreichbarError(
                            "Die Website hat auf ein nicht erlaubtes Ziel "
                            "weitergeleitet."
                        )
                    aktuelle_url = ziel
                    continue

                if antwort.status >= 400:
                    raise WebseiteNichtErreichbarError(
                        "Die Website hat einen Fehler zurückgegeben "
                        f"(Status {antwort.status})."
                    )

                return await _lese_antwort_text(antwort)
        except WebseiteNichtErreichbarError:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise WebseiteNichtErreichbarError(
                "Die Website konnte nicht erreicht werden."
            ) from err

    raise WebseiteNichtErreichbarError(
        "Die Website hat zu viele Weiterleitungen ausgelöst."
    )


async def async_ermittle_webseite_info(hass: HomeAssistant, url: str | None) -> WebseiteInfo:
    """Ruft ``url`` ab und ermittelt daraus Hofladen-Informationen.

    Wirft (siehe Moduldoc und Issue #8 für die drei geforderten
    Fehlerfälle):

    - :class:`WebseiteUngueltigeUrlError` - keine URL angegeben, oder sie
      ist syntaktisch ungültig bzw. zeigt auf ein nicht erlaubtes Ziel
      (Fehlerfall 1).
    - :class:`WebseiteNichtErreichbarError` - Verbindungsfehler, Timeout,
      HTTP-Fehlerstatus, unlesbares Antwortformat, zu grosse Antwort oder
      unsichere Weiterleitung (Fehlerfall 2).
    - :class:`WebseiteInformationenNichtGefundenError` - die Website war
      erreichbar, es konnten aber keine verwertbaren Informationen
      ermittelt werden (Fehlerfall 3).

    Das Ergebnis ist ausschliesslich ein Vorschlag zur Überprüfung - siehe
    ``management.py``, ``ws_webseite_info``.
    """
    if not url or not url.strip():
        raise WebseiteUngueltigeUrlError("Es wurde keine Website-Adresse angegeben.")

    url = url.strip()
    if not ist_sichere_externe_url(url):
        raise WebseiteUngueltigeUrlError(
            "Die Website-Adresse ist ungültig oder zeigt auf ein nicht "
            "erlaubtes Ziel."
        )

    session = async_get_clientsession(hass)
    html_text = await _hole_html(session, url)

    info = _extrahiere_aus_html(html_text)
    if info.ist_leer():
        raise WebseiteInformationenNichtGefundenError(
            "Auf der Website konnten keine verwertbaren Informationen "
            "gefunden werden."
        )
    return info
