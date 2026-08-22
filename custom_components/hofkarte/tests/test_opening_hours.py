"""Tests für ``opening_hours.py``.

Diese Tests dokumentieren den bewussten Zwischenstand aus Einheit 6: Die
Funktionen liefern noch keine berechneten Werte. Die robuste
Implementierung folgt in Einheit 7 und wird diese Tests entsprechend
ersetzen bzw. erweitern.
"""

from datetime import datetime, timezone

from custom_components.hofkarte.models import Hofladen
from custom_components.hofkarte.opening_hours import (
    get_next_closing,
    get_next_opening,
    is_open,
)

_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
_HOFLADEN = Hofladen(id="hof-1", name="Hofladen Eins")


def test_is_open_not_yet_implemented() -> None:
    """Solange Einheit 7 nicht implementiert ist, muss None geliefert werden."""
    assert is_open(_HOFLADEN, _NOW) is None


def test_get_next_opening_not_yet_implemented() -> None:
    """Solange Einheit 7 nicht implementiert ist, muss None geliefert werden."""
    assert get_next_opening(_HOFLADEN, _NOW) is None


def test_get_next_closing_not_yet_implemented() -> None:
    """Solange Einheit 7 nicht implementiert ist, muss None geliefert werden."""
    assert get_next_closing(_HOFLADEN, _NOW) is None
