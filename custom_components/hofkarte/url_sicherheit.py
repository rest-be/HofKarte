"""Gemeinsame, rein syntaktische SSRF-Grundprüfung für frei eingegebene URLs.

Dieses Modul bündelt die Sicherheitsprüfung, die ursprünglich ausschliesslich
in ``images.py`` für Hofladen-Bild-URLs existierte (siehe dessen Moduldoc für
die ausführliche Begründung) und die mit Issue #8 ("Informationen aus
Homepage") ein zweites Mal benötigt wird: Für die dort neu eingeführte,
serverseitige Website-Abfrage (siehe ``webseite_info.py``) gelten dieselben
Grundregeln (nur http/https, keine Zugangsdaten, kein "localhost" und keine
privaten/internen IP-Literale) – deshalb hier zentral statt zweimal
dupliziert.

## Bewusste Grenze: rein syntaktische Prüfung, keine DNS-Auflösung

Wie in ``images.py`` beschrieben, prüft dieses Modul ausschliesslich die
URL-Syntax – es findet **keine DNS-Auflösung** statt. Ein Domainname wird
akzeptiert, ohne zu prüfen, wohin er tatsächlich auflöst; ein
DNS-Rebinding-Angriff (Domainname löst zum Zeitpunkt des eigentlichen
Requests auf eine private IP auf) wird durch diese Prüfung **nicht**
abgedeckt. IP-Literale und der Hostname "localhost" werden aber zuverlässig
abgelehnt.

``webseite_info.py`` behandelt diese Grenze bewusst genauso wie
``images.py`` es für Bild-URLs tut (siehe dessen Moduldoc-Abschnitt zur
DNS-Auflösung als blockierendem Aufruf) – zusätzlich zur hier geprüften
URL-Syntax begrenzt ``webseite_info.py`` aber auch Antwortgrösse,
Content-Type und Zeitüberschreitung des eigentlichen HTTP-Abrufs, da es
(anders als ``images.py``) den Antwortinhalt selbst verarbeitet.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

UNSICHERE_HOSTNAMEN = frozenset({"localhost"})


def ist_unsicheres_ip_literal(hostname: str) -> bool:
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


def ist_sichere_externe_url(url: str | None) -> bool:
    """Prüft, ob eine frei eingegebene, nicht vertrauenswürdige URL den
    grundlegenden syntaktischen Sicherheitsanforderungen genügt.

    Akzeptiert nur http/https, lehnt eingebettete Zugangsdaten,
    den Hostnamen "localhost" sowie private/interne IP-Literale ab (siehe
    ``ist_unsicheres_ip_literal`` und die Moduldoc zur bewussten Grenze
    dieser rein syntaktischen Prüfung). Kennt – anders als
    ``images.is_valid_image_url`` mit ``hochgeladen=True`` – keine
    Herkunfts-Ausnahme: Diese Funktion ist ausschliesslich für frei
    eingegebene, potenziell nicht vertrauenswürdige URLs gedacht.

    Args:
        url: Die zu prüfende URL (oder ``None``).

    Returns:
        ``True``, wenn die URL den syntaktischen Sicherheitsprüfungen
        genügt.
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

    if parsed.scheme not in ("http", "https"):
        return False
    if parsed.username or parsed.password:
        return False

    hostname = parsed.hostname
    if not hostname:
        return False
    if hostname.lower() in UNSICHERE_HOSTNAMEN:
        return False
    if ist_unsicheres_ip_literal(hostname):
        return False

    return True
