"""Sichere Verarbeitung und Validierung von Hofladen-Bildern.

Dieses Modul stellt sicher, dass Bild-URLs sicher sind und keinen
Sicherheitsrisiken entsprechen:

- Nur http und https URLs werden akzeptiert
- file:// Zugriffe sind explizit nicht gestattet
- IP-Literale, die auf private/interne Ziele zeigen (z. B. 127.0.0.1,
  192.168.x.x, 169.254.169.254 – Cloud-Metadata-Endpunkte), werden
  abgelehnt, ebenso der Hostname "localhost"
- Fehlende oder ungültige Bilder werden robust behandelt

## Bewusste Grenze: rein syntaktische Prüfung, keine DNS-Auflösung

Die Prüfung erfolgt ausschliesslich anhand der URL-Syntax (Schema,
Zugangsdaten, IP-Literale) – es findet **keine DNS-Auflösung** statt.
Das ist eine bewusste Entscheidung: Eine Auflösung über
``socket.getaddrinfo`` ist ein blockierender Aufruf und dürfte aus
synchronen Home-Assistant-Entity-Properties (siehe ``image.py``:
``image_url`` wird von Home Assistant als reguläre, synchrone Property
aufgerufen) nicht direkt erfolgen, ohne den Event Loop zu blockieren.

Ein Domainname wie ``https://böser-domain.example`` wird daher nicht per
DNS geprüft; er wird akzeptiert und Home Assistants eigener
(asynchroner) Bild-Abruf (``ImageEntity.async_image``) übernimmt den
eigentlichen HTTP-Request. Ein DNS-Rebinding-Angriff (Domainname löst
zum Zeitpunkt des Requests auf eine private IP auf) wird durch diese
Prüfung nicht abgedeckt – IP-Literale und der Hostname "localhost"
werden aber zuverlässig abgelehnt, was den Hauptteil versehentlicher
oder offensichtlich böswilliger interner Ziele abdeckt.

Das Hauptbild eines Hofladens wird über Home Assistants natives
``image``-Entity-Platform dargestellt (siehe ``image.py``) – das ist die
plattformgerechte Lösung, da nur echte Image-Entities in Lovelace
automatisch als Bild gerendert werden (ein beliebiges Attribut würde das
nicht tun). Weitere Bilder (über das Hauptbild hinaus) werden als
Attribut an dieser Entity bereitgestellt, da Home Assistant keine native
"Galerie"-Darstellung für mehrere Bilder pro Entity kennt.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

from .models import Bild

_UNSICHERE_HOSTNAMEN = frozenset({"localhost"})


def _ist_unsicheres_ip_literal(hostname: str) -> bool:
    """Ob ein Hostname ein IP-Literal ist, das auf ein privates/internes
    Ziel zeigt (Loopback, privates Netz, Link-Local, reserviert,
    Multicast). Reine String-/Literal-Prüfung, **keine DNS-Auflösung**:
    Ist ``hostname`` kein IP-Literal (sondern ein Domainname), liefert
    diese Funktion ``False`` – die Domain wird dann nicht weiter geprüft
    (siehe Moduldoc, Abschnitt „Bewusste Grenze“).
    """
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return False  # kein IP-Literal, sondern ein Domainname.
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
    )


def is_valid_image_url(url: str | None) -> bool:
    """Überprüft, ob eine URL ein gültiges, sicheres Bild ist.

    Akzeptiert nur http/https URLs. Lehnt ab:
    - file:// URLs (lokale Dateizugriffe)
    - data: URLs (Embedded Data)
    - Andere unsichere Protokolle
    - URLs mit eingebetteten Zugangsdaten
    - Den Hostnamen "localhost" sowie IP-Literale, die auf ein
      privates/internes Ziel zeigen (siehe Moduldoc zur bewussten Grenze
      dieser rein syntaktischen, nicht-blockierenden Prüfung)
    - Ungültige/leere URLs

    Args:
        url: Die zu validierende URL (oder None)

    Returns:
        True, wenn die URL den syntaktischen Sicherheitsprüfungen genügt.
    """
    if not url or not isinstance(url, str):
        return False

    url = url.strip()
    if not url:
        return False

    try:
        parsed = urlparse(url)
    except ValueError:
        return False

    # Nur http und https erlaubt
    if parsed.scheme not in ("http", "https"):
        return False
    # Keine Credentials in URL
    if parsed.username or parsed.password:
        return False
    # Zumindest Host erforderlich
    hostname = parsed.hostname
    if not hostname:
        return False
    if hostname.lower() in _UNSICHERE_HOSTNAMEN:
        return False
    if _ist_unsicheres_ip_literal(hostname):
        return False
    return True


def get_main_image_url(bilder: tuple[Bild, ...]) -> str | None:
    """Ermittelt die URL des Hauptbildes aus einer Liste von Bildern.

    Das erste Bild mit gültiger, sicherer URL ist das Hauptbild
    (Reihenfolge in ``Hofladen.bilder`` bestimmt die Priorität). Gibt
    ``None`` zurück, wenn keine gültigen Bilder vorhanden sind.

    Args:
        bilder: Tupel von Bild-Objekten

    Returns:
        URL des Hauptbildes oder None.
    """
    if not bilder:
        return None

    for bild in bilder:
        if is_valid_image_url(bild.url):
            return bild.url

    return None


def get_additional_images(bilder: tuple[Bild, ...]) -> list[dict[str, str | None]]:
    """Alle sicheren Bilder ausser dem Hauptbild, als einfache Attributliste.

    Home Assistant kennt keine native Mehrbild-/Galerie-Darstellung pro
    Entity; diese Liste wird daher als ``extra_state_attributes`` am
    Hauptbild-Entity bereitgestellt (siehe ``image.py``), nicht als
    eigene Entities. Unsichere Bilder werden konsequent ausgeschlossen,
    genau wie beim Hauptbild.

    Args:
        bilder: Tupel von Bild-Objekten

    Returns:
        Liste von ``{"url": ..., "beschreibung": ...}``, ohne das
        Hauptbild. Leer, wenn keine weiteren sicheren Bilder existieren.
    """
    hauptbild_url = get_main_image_url(bilder)
    weitere: list[dict[str, str | None]] = []
    hauptbild_bereits_uebersprungen = False

    for bild in bilder:
        if not is_valid_image_url(bild.url):
            continue
        if not hauptbild_bereits_uebersprungen and bild.url == hauptbild_url:
            hauptbild_bereits_uebersprungen = True
            continue
        weitere.append({"url": bild.url, "beschreibung": bild.beschreibung})

    return weitere
