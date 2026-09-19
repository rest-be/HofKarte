"""Tests für webseite_info.py (Issue #8, "Informationen aus Homepage").

Deckt beide Ebenen ab: die reine HTML-/JSON-LD-Extraktion (ohne
Netzwerk) sowie den asynchronen Abruf inkl. SSRF-Schutz, Grössen-/
Content-Type-/Timeout-Limits und der drei geforderten Fehlerfälle. Der
HTTP-Abruf wird dabei über eine leichtgewichtige Fake-Session
nachgebildet (kein echtes Netzwerk, kein zusätzliches Test-Framework).
"""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
import pytest

from custom_components.hofkarte.webseite_info import (
    MAX_ANTWORT_BYTES,
    WebseiteInfo,
    WebseiteInformationenNichtGefundenError,
    WebseiteNichtErreichbarError,
    WebseiteUngueltigeUrlError,
    _extrahiere_aus_html,
    async_ermittle_webseite_info,
)


# ---------------------------------------------------------------------------
# Reine HTML-/JSON-LD-Extraktion (kein Netzwerk)
# ---------------------------------------------------------------------------


def _json_ld_seite(payload: str) -> str:
    return (
        "<html><head><title>Seitentitel</title>"
        '<meta name="description" content="Meta-Beschreibung">'
        f'<script type="application/ld+json">{payload}</script>'
        "</head><body></body></html>"
    )


def test_extrahiert_vollstaendiges_local_business_objekt() -> None:
    payload = """
    {
      "@context": "https://schema.org",
      "@type": "FoodEstablishment",
      "name": "Hofladen Muster",
      "description": "Frische Eier, Gemüse und Honig direkt vom Bauernhof.",
      "address": {
        "@type": "PostalAddress",
        "streetAddress": "Musterweg 1",
        "postalCode": "3000",
        "addressLocality": "Bern",
        "addressCountry": {"@type": "Country", "name": "Schweiz"}
      },
      "openingHoursSpecification": [
        {"@type": "OpeningHoursSpecification", "dayOfWeek": ["https://schema.org/Monday", "https://schema.org/Tuesday"], "opens": "08:00", "closes": "18:00"},
        {"@type": "OpeningHoursSpecification", "dayOfWeek": "Saturday", "opens": "08:00", "closes": "12:00"}
      ],
      "paymentAccepted": "Cash, Twint",
      "makesOffer": [{"itemOffered": {"name": "Eier"}}, {"itemOffered": {"name": "Honig"}}]
    }
    """
    info = _extrahiere_aus_html(_json_ld_seite(payload))

    assert info.name == "Hofladen Muster"
    assert info.beschreibung == "Frische Eier, Gemüse und Honig direkt vom Bauernhof."
    assert info.adresse == "Musterweg 1"
    assert info.plz == "3000"
    assert info.ort == "Bern"
    assert info.land == "Schweiz"
    assert info.oeffnungszeiten == (
        {"wochentag": 1, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 2, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 6, "beginn": "08:00", "ende": "12:00"},
    )
    assert info.angebote == ("Eier", "Honig")
    assert info.zahlungsarten == ("Cash", "Twint")
    assert not info.ist_leer()


def test_ignoriert_json_ld_ohne_business_merkmale() -> None:
    """Ein blosses 'WebSite'-Objekt ohne Adresse/Öffnungszeiten/etc. gilt
    nicht als Hofladen-Kandidat - die Meta-Beschreibung/der Titel greifen
    als Fallback."""
    payload = '{"@context": "https://schema.org", "@type": "WebSite", "name": "Meine Seite"}'
    info = _extrahiere_aus_html(_json_ld_seite(payload))

    assert info.name == "Seitentitel"
    assert info.beschreibung == "Meta-Beschreibung"
    assert info.adresse is None


def test_ungueltiges_json_ld_wird_ignoriert_kein_absturz() -> None:
    html = _json_ld_seite("{kaputtes json")
    info = _extrahiere_aus_html(html)

    assert info.name == "Seitentitel"
    assert info.beschreibung == "Meta-Beschreibung"


def test_at_graph_wird_aufgeloest() -> None:
    payload = """
    {"@context": "https://schema.org", "@graph": [
        {"@type": "WebSite", "name": "Seite"},
        {"@type": "Store", "name": "Hofladen Graph", "telephone": "+41 00 000 00 00"}
    ]}
    """
    info = _extrahiere_aus_html(_json_ld_seite(payload))
    assert info.name == "Hofladen Graph"


def test_oeffnungszeiten_ohne_opens_oder_closes_werden_uebersprungen() -> None:
    payload = """
    {"@type": "Store", "name": "Hofladen", "telephone": "0",
     "openingHoursSpecification": [
        {"dayOfWeek": "Monday", "opens": "08:00"},
        {"dayOfWeek": "Tuesday", "opens": "08:00", "closes": "08:00"}
     ]}
    """
    info = _extrahiere_aus_html(_json_ld_seite(payload))
    assert info.oeffnungszeiten == ()


def test_zahlungsarten_als_liste() -> None:
    payload = '{"@type": "Store", "name": "Hofladen", "paymentAccepted": ["Bar", "Twint"]}'
    info = _extrahiere_aus_html(_json_ld_seite(payload))
    assert info.zahlungsarten == ("Bar", "Twint")


def test_leere_seite_ohne_jegliche_information_ist_leer() -> None:
    info = _extrahiere_aus_html("<html><head></head><body></body></html>")
    assert info.ist_leer()


# ---------------------------------------------------------------------------
# Vertiefte Text-Heuristik (Issue #9): Adresse/Öffnungszeiten als Fallback,
# wenn JSON-LD dafür nichts liefert.
# ---------------------------------------------------------------------------


def _text_seite(*absaetze: str) -> str:
    """Baut eine einfache HTML-Seite ohne JSON-LD aus mehreren
    Absätzen (<p>) - jeder Absatz landet als eigene Zeile im
    ``sichtbarer_text()`` der Seite (siehe ``_SeitenParser``)."""
    body = "".join(f"<p>{absatz}</p>" for absatz in absaetze)
    return f"<html><head><title>Hofladen Muster</title></head><body>{body}</body></html>"


def test_adresse_wird_aus_text_erkannt_wenn_kein_json_ld_vorhanden() -> None:
    info = _extrahiere_aus_html(_text_seite("Musterweg 1, 3000 Bern"))
    assert info.adresse == "Musterweg 1"
    assert info.plz == "3000"
    assert info.ort == "Bern"


def test_adresse_ohne_komma_wird_ebenfalls_erkannt() -> None:
    info = _extrahiere_aus_html(_text_seite("Bahnhofstrasse 12 8400 Winterthur"))
    assert info.adresse == "Bahnhofstrasse 12"
    assert info.plz == "8400"
    assert info.ort == "Winterthur"


def test_adresse_mit_mehrwortort_wird_erkannt() -> None:
    info = _extrahiere_aus_html(_text_seite("Dorfgasse 3, 9490 Vaduz Liechtenstein"))
    assert info.adresse == "Dorfgasse 3"
    assert info.plz == "9490"
    assert info.ort == "Vaduz Liechtenstein"


def test_adresse_ueber_getrennte_absaetze_wird_nicht_erkannt() -> None:
    """Dokumentierte Grenze: eine über zwei Absätze verteilte Adresse
    (Strasse in einer Zeile, PLZ/Ort in der nächsten) wird bewusst nicht
    erkannt, statt fälschlich mit unabhängigem Text kombiniert zu werden
    (siehe ``_SeitenParser.sichtbarer_text()``)."""
    info = _extrahiere_aus_html(_text_seite("Bahnhofstrasse 12", "8400 Winterthur"))
    assert info.adresse is None
    assert info.plz is None
    assert info.ort is None


def test_mehrdeutige_adresse_liefert_keinen_vorschlag() -> None:
    """Zwei unterschiedliche Adresskandidaten im Text -> uneindeutig,
    also lieber gar kein Vorschlag (Prinzip "lieber nichts als falsch")."""
    info = _extrahiere_aus_html(
        _text_seite("Musterweg 1, 3000 Bern", "Dorfweg 5, 3001 Bern")
    )
    assert info.adresse is None
    assert info.plz is None
    assert info.ort is None


def test_identisch_wiederholte_adresse_gilt_nicht_als_mehrdeutig() -> None:
    """Dieselbe Adresse an zwei Stellen der Seite (z. B. Kopf- und
    Fussbereich) ist kein Widerspruch."""
    info = _extrahiere_aus_html(
        _text_seite("Musterweg 1, 3000 Bern", "Kontakt: Musterweg 1, 3000 Bern")
    )
    assert info.adresse == "Musterweg 1"
    assert info.plz == "3000"
    assert info.ort == "Bern"


def test_strasse_ohne_erkannte_endung_wird_nicht_als_adresse_erkannt() -> None:
    """Strassennamen ohne eine der erkannten Endungen (-strasse, -weg,
    ...) werden bewusst nicht erkannt (dokumentierte Grenze)."""
    info = _extrahiere_aus_html(_text_seite("Via Nassa 1, 6900 Lugano"))
    assert info.adresse is None


def test_json_ld_adresse_hat_vorrang_vor_text_heuristik() -> None:
    """Die Text-Heuristik darf eine bereits aus JSON-LD ermittelte
    Adresse nicht überschreiben oder ergänzen."""
    payload = """
    {
      "@type": "Store", "name": "Hofladen",
      "address": {"streetAddress": "Musterweg 1", "postalCode": "3000", "addressLocality": "Bern"}
    }
    """
    html = (
        "<html><head><title>t</title>"
        f'<script type="application/ld+json">{payload}</script>'
        "</head><body><p>Andere Strasse 9, 8000 Zürich</p></body></html>"
    )
    info = _extrahiere_aus_html(html)
    assert info.adresse == "Musterweg 1"
    assert info.plz == "3000"
    assert info.ort == "Bern"


def test_oeffnungszeiten_werden_aus_tagesbereich_mit_bindestrich_erkannt() -> None:
    info = _extrahiere_aus_html(_text_seite("Mo-Fr 08:00-18:00 Uhr"))
    assert info.oeffnungszeiten == (
        {"wochentag": 1, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 2, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 3, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 4, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 5, "beginn": "08:00", "ende": "18:00"},
    )


def test_oeffnungszeiten_werden_aus_ausgeschriebenem_tagesbereich_erkannt() -> None:
    info = _extrahiere_aus_html(_text_seite("Montag bis Freitag: 8 – 18 Uhr"))
    assert info.oeffnungszeiten == (
        {"wochentag": 1, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 2, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 3, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 4, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 5, "beginn": "08:00", "ende": "18:00"},
    )


def test_oeffnungszeiten_werden_aus_einzelnem_tag_erkannt() -> None:
    info = _extrahiere_aus_html(_text_seite("Sa 08:00–12:00"))
    assert info.oeffnungszeiten == ({"wochentag": 6, "beginn": "08:00", "ende": "12:00"},)


def test_widerspruechliche_oeffnungszeiten_fuer_einen_tag_werden_ausgelassen() -> None:
    """Zwei unterschiedliche Angaben für Montag -> für Montag kein
    Vorschlag; die übrigen, eindeutigen Tage bleiben davon unberührt."""
    info = _extrahiere_aus_html(_text_seite("Mo-Fr 08:00-18:00 Uhr", "Mo 09:00-17:00 Uhr"))
    assert info.oeffnungszeiten == (
        {"wochentag": 2, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 3, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 4, "beginn": "08:00", "ende": "18:00"},
        {"wochentag": 5, "beginn": "08:00", "ende": "18:00"},
    )


def test_identisch_wiederholte_oeffnungszeit_gilt_nicht_als_widerspruch() -> None:
    info = _extrahiere_aus_html(_text_seite("Mo 08:00-12:00 Uhr", "Montag: 08:00-12:00 Uhr"))
    assert info.oeffnungszeiten == ({"wochentag": 1, "beginn": "08:00", "ende": "12:00"},)


def test_json_ld_oeffnungszeiten_haben_vorrang_vor_text_heuristik() -> None:
    payload = """
    {
      "@type": "Store", "name": "Hofladen",
      "openingHoursSpecification": [
        {"dayOfWeek": "Saturday", "opens": "08:00", "closes": "12:00"}
      ]
    }
    """
    html = (
        "<html><head><title>t</title>"
        f'<script type="application/ld+json">{payload}</script>'
        "</head><body><p>Mo-Fr 08:00-18:00 Uhr</p></body></html>"
    )
    info = _extrahiere_aus_html(html)
    assert info.oeffnungszeiten == ({"wochentag": 6, "beginn": "08:00", "ende": "12:00"},)


def test_ohne_erkennbares_muster_bleiben_oeffnungszeiten_leer() -> None:
    info = _extrahiere_aus_html(_text_seite("Wir freuen uns auf Ihren Besuch."))
    assert info.oeffnungszeiten == ()


# ---------------------------------------------------------------------------
# async_ermittle_webseite_info: URL-Validierung (Fehlerfall 1)
# ---------------------------------------------------------------------------


async def test_leere_url_wirft_ungueltige_url_error(hass: Any) -> None:
    with pytest.raises(WebseiteUngueltigeUrlError):
        await async_ermittle_webseite_info(hass, "")


async def test_nur_leerzeichen_wirft_ungueltige_url_error(hass: Any) -> None:
    with pytest.raises(WebseiteUngueltigeUrlError):
        await async_ermittle_webseite_info(hass, "   ")


async def test_none_wirft_ungueltige_url_error(hass: Any) -> None:
    with pytest.raises(WebseiteUngueltigeUrlError):
        await async_ermittle_webseite_info(hass, None)


async def test_private_ip_literal_wirft_ungueltige_url_error(hass: Any) -> None:
    with pytest.raises(WebseiteUngueltigeUrlError):
        await async_ermittle_webseite_info(hass, "http://192.168.1.1/")


async def test_unsicheres_schema_wirft_ungueltige_url_error(hass: Any) -> None:
    with pytest.raises(WebseiteUngueltigeUrlError):
        await async_ermittle_webseite_info(hass, "file:///etc/passwd")


# ---------------------------------------------------------------------------
# async_ermittle_webseite_info: HTTP-Abruf (Fake-Session, kein echtes Netzwerk)
# ---------------------------------------------------------------------------


class _FakeContent:
    def __init__(self, data: bytes, chunk_size: int = 4096) -> None:
        self._data = data
        self._chunk_size = chunk_size

    def iter_chunked(self, _n: int):
        data = self._data
        chunk_size = self._chunk_size

        async def _generator():
            for i in range(0, len(data), chunk_size):
                yield data[i : i + chunk_size]

        return _generator()


class _FakeResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        content_type: str = "text/html",
        body: bytes = b"",
        headers: dict[str, str] | None = None,
        encoding: str = "utf-8",
    ) -> None:
        self.status = status
        self.content_type = content_type
        self.headers = headers or {}
        self.content = _FakeContent(body)
        self._encoding = encoding

    def get_encoding(self) -> str:
        return self._encoding

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False


class _RaisingGet:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def __call__(self, *args: Any, **kwargs: Any):
        raise self._exc


class _FakeSession:
    def __init__(self, antworten: list[_FakeResponse]) -> None:
        self._antworten = list(antworten)
        self.abgefragte_urls: list[str] = []

    def get(self, url: str, *, timeout: Any = None, allow_redirects: Any = None):
        self.abgefragte_urls.append(url)
        return self._antworten.pop(0)


def _patch_session(monkeypatch: pytest.MonkeyPatch, session: Any) -> None:
    monkeypatch.setattr(
        "custom_components.hofkarte.webseite_info.async_get_clientsession",
        lambda hass: session,
    )


async def test_erfolgreicher_abruf_liefert_webseiteinfo(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    html = _json_ld_seite(
        '{"@type": "Store", "name": "Hofladen Erfolg", "telephone": "0"}'
    )
    session = _FakeSession([_FakeResponse(body=html.encode("utf-8"))])
    _patch_session(monkeypatch, session)

    info = await async_ermittle_webseite_info(hass, "https://beispiel-hofladen.example")

    assert isinstance(info, WebseiteInfo)
    assert info.name == "Hofladen Erfolg"


async def test_http_fehlerstatus_wirft_nicht_erreichbar_error(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _FakeSession([_FakeResponse(status=500)])
    _patch_session(monkeypatch, session)

    with pytest.raises(WebseiteNichtErreichbarError):
        await async_ermittle_webseite_info(hass, "https://beispiel.example")


async def test_unpassender_content_type_wirft_nicht_erreichbar_error(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _FakeSession(
        [_FakeResponse(content_type="application/pdf", body=b"%PDF-1.4")]
    )
    _patch_session(monkeypatch, session)

    with pytest.raises(WebseiteNichtErreichbarError):
        await async_ermittle_webseite_info(hass, "https://beispiel.example")


async def test_zu_grosse_antwort_wirft_nicht_erreichbar_error(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    zu_gross = b"<html>" + b"x" * (MAX_ANTWORT_BYTES + 1)
    session = _FakeSession([_FakeResponse(body=zu_gross)])
    _patch_session(monkeypatch, session)

    with pytest.raises(WebseiteNichtErreichbarError):
        await async_ermittle_webseite_info(hass, "https://beispiel.example")


async def test_verbindungsfehler_wirft_nicht_erreichbar_error(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _FakeSession([])
    session.get = _RaisingGet(aiohttp.ClientConnectionError("nope"))
    _patch_session(monkeypatch, session)

    with pytest.raises(WebseiteNichtErreichbarError):
        await async_ermittle_webseite_info(hass, "https://beispiel.example")


async def test_timeout_wirft_nicht_erreichbar_error(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _FakeSession([])
    session.get = _RaisingGet(asyncio.TimeoutError())
    _patch_session(monkeypatch, session)

    with pytest.raises(WebseiteNichtErreichbarError):
        await async_ermittle_webseite_info(hass, "https://beispiel.example")


async def test_erreichbare_seite_ohne_informationen_wirft_not_found(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _FakeSession(
        [_FakeResponse(body=b"<html><head></head><body>Nichts hier.</body></html>")]
    )
    _patch_session(monkeypatch, session)

    with pytest.raises(WebseiteInformationenNichtGefundenError):
        await async_ermittle_webseite_info(hass, "https://beispiel.example")


async def test_weiterleitung_auf_sicheres_ziel_wird_verfolgt(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    html = _json_ld_seite('{"@type": "Store", "name": "Nach Weiterleitung", "telephone": "0"}')
    session = _FakeSession(
        [
            _FakeResponse(status=301, headers={"Location": "https://ziel.example/neu"}),
            _FakeResponse(body=html.encode("utf-8")),
        ]
    )
    _patch_session(monkeypatch, session)

    info = await async_ermittle_webseite_info(hass, "https://beispiel.example")

    assert info.name == "Nach Weiterleitung"
    assert session.abgefragte_urls == [
        "https://beispiel.example",
        "https://ziel.example/neu",
    ]


async def test_weiterleitung_auf_unsicheres_ziel_wird_abgelehnt(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _FakeSession(
        [_FakeResponse(status=302, headers={"Location": "http://192.168.1.1/intern"})]
    )
    _patch_session(monkeypatch, session)

    with pytest.raises(WebseiteNichtErreichbarError):
        await async_ermittle_webseite_info(hass, "https://beispiel.example")


async def test_weiterleitung_ohne_location_header_wirft_nicht_erreichbar_error(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _FakeSession([_FakeResponse(status=302, headers={})])
    _patch_session(monkeypatch, session)

    with pytest.raises(WebseiteNichtErreichbarError):
        await async_ermittle_webseite_info(hass, "https://beispiel.example")


async def test_zu_viele_weiterleitungen_werden_abgelehnt(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    # _MAX_REDIRECTS erlaubt 3 Sprünge -> ein vierter muss scheitern.
    antworten = [
        _FakeResponse(status=302, headers={"Location": f"https://ziel-{i}.example/"})
        for i in range(5)
    ]
    session = _FakeSession(antworten)
    _patch_session(monkeypatch, session)

    with pytest.raises(WebseiteNichtErreichbarError):
        await async_ermittle_webseite_info(hass, "https://beispiel.example")
