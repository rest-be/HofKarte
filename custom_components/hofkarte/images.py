"""Sichere Verarbeitung und Validierung von Hofladen-Bildern.

Dieses Modul stellt sicher, dass Bild-URLs sicher sind und keinen
Sicherheitsrisiken entsprechen:

- Nur http und https URLs werden akzeptiert
- file:// Zugriffe sind explizit nicht gestattet
- URLs werden auf Gültigkeit geprüft
- Fehlende oder ungültige Bilder werden robust behandelt

Bilder sollten in Home Assistant über Entity-Attribute bereitgestellt
werden, nicht als separate Image-Entities, um die Anzahl der Entities
klein zu halten und den natürlichen Kontext zu bewahren.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse
import socket
import ipaddress

from .models import Bild


def _host_is_private(hostname: str) -> bool:
    """True wenn hostname auf private/loopback/link-local/reserved/multicast IP zeigt."""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except Exception:
        # DNS nicht auflösbar -> treat as unsafe
        return True
    for _family, _type, _proto, _canon, sockaddr in infos:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except Exception:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            return True
    return False


def is_valid_image_url(url: str | None) -> bool:
    """Überprüft, ob eine URL ein gültiges, sicheres Bild ist.

    Akzeptiert nur http/https URLs. Lehnt ab:
    - file:// URLs (lokale Dateizugriffe)
    - data: URLs (Embedded Data)
    - Andere unsichere Protokolle
    - Ungültige/leere URLs

    Args:
        url: Die zu validierende URL (oder None)

    Returns:
        True, wenn die URL sicher ist, False sonst.
    """
    if not url or not isinstance(url, str):
        return False

    url = url.strip()
    if not url:
        return False

    try:
        parsed = urlparse(url)
    except Exception:
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
    # DNS -> IP prüfen; private/loopback/link-local/reserved/multicast ablehnen
    if _host_is_private(hostname):
        return False
    return True


def get_main_image_url(bilder: tuple[Bild, ...]) -> str | None:
    """Ermittelt die URL des Hauptbildes aus einer Liste von Bildern.

    Das erste Bild mit gültiger, sicherer URL ist das Hauptbild.
    Gibt None zurück, wenn keine gültigen Bilder vorhanden sind.

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


def build_images_attribute(bilder: tuple[Bild, ...]) -> dict[str, Any]:
    """Erstellt eine sichere, JSON-serialisierbare Bildstruktur für Attribute.

    Enthält:
    - primary_image: URL des Hauptbildes (erstes gültiges Bild)
    - images: Liste aller gültigen Bilder mit Beschreibung

    Ungültige Bilder werden gefiltert. Fehlende oder alle ungültigen
    Bilder resultsieren in empty/None, nicht in Error.

    Args:
        bilder: Tupel von Bild-Objekten

    Returns:
        Dict mit primary_image und images Liste.
    """
    result: dict[str, Any] = {
        "primary_image": None,
        "images": [],
    }

    if not bilder:
        return result

    valid_images: list[dict[str, Any]] = []

    for bild in bilder:
        if is_valid_image_url(bild.url):
            image_entry: dict[str, Any] = {
                "url": bild.url,
            }
            if bild.beschreibung:
                image_entry["description"] = bild.beschreibung
            valid_images.append(image_entry)

    if valid_images:
        result["primary_image"] = valid_images[0]["url"]
        result["images"] = valid_images

    return result
