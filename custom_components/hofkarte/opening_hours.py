"""Berechnung des Öffnungsstatus von Hofläden.

Dies ist die alleinig vorgesehene Stelle für die
Öffnungszeiten-Berechnungslogik (siehe Einheit 6, Grenzen: „Keine neue
Berechnungslogik außerhalb des dafür vorgesehenen Moduls“). Sensoren und
der Binary Sensor rufen ausschliesslich die Funktionen dieses Moduls auf
und enthalten selbst keine Berechnungslogik.

Die robuste Implementierung (mehrere Intervalle pro Tag, Sonderöffnungs-
zeiten, Mitternachtsüberschreitung, Zeitzone des Home-Assistant-Systems,
Grenzfälle) folgt in Einheit 7 – „Öffnungszeiten und Sonderöffnungszeiten“.

Bis dahin liefern die Funktionen bewusst keine berechneten Werte
(``None``), statt eine unvollständige oder naive Datums-/Zeitlogik zu
implementieren (siehe Einheit 7, Regeln: „keine naive
Datetime-Arithmetik“). Entities, die diese Funktionen aufrufen, zeigen in
der Zwischenzeit korrekt den Zustand „unbekannt“ statt eines erfundenen
Wertes.
"""

from __future__ import annotations

from datetime import datetime

from .models import Hofladen


def is_open(hofladen: Hofladen, now: datetime) -> bool | None:
    """Ob der Hofladen zum Zeitpunkt ``now`` geöffnet ist.

    Liefert ``None`` (Zustand „unbekannt“), solange die robuste
    Öffnungszeiten-Berechnung noch nicht implementiert ist (Einheit 7).
    """
    return None


def get_next_opening(hofladen: Hofladen, now: datetime) -> datetime | None:
    """Zeitpunkt der nächsten Öffnung nach ``now``.

    Liefert ``None`` (Zustand „unbekannt“), solange die robuste
    Öffnungszeiten-Berechnung noch nicht implementiert ist (Einheit 7).
    """
    return None


def get_next_closing(hofladen: Hofladen, now: datetime) -> datetime | None:
    """Zeitpunkt der nächsten Schliessung nach ``now``.

    Liefert ``None`` (Zustand „unbekannt“), solange die robuste
    Öffnungszeiten-Berechnung noch nicht implementiert ist (Einheit 7).
    """
    return None
