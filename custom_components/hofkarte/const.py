"""Konstanten für die HofKarte-Integration."""

from datetime import timedelta

DOMAIN = "hofkarte"

# Config Flow / Config Entry
DEFAULT_NAME = "HofKarte"

# Coordinator / Datenabruf
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=15)
DEFAULT_FETCH_TIMEOUT_SECONDS = 30

# Sortiment und Eigenschaften (Einheit 8 / Ergänzung „User Editierbar“):
# Vorschlagswerte für den Fachbereich Zahlungsarten. Nutzer sind nicht auf
# diese Werte beschränkt – jeder beliebige Name ist zulässig (siehe
# parsing.py); dies ist lediglich ein sinnvoller Startkatalog, den z. B.
# ein künftiger Editier-Dialog vorschlagen kann. Die früheren Kataloge
# für „Verkaufsarten“ und „Merkmale“ wurden entfernt, da diese
# Fachbereiche selbst ersatzlos entfernt wurden (siehe CHANGELOG).
STANDARD_ZAHLUNGSARTEN: tuple[str, ...] = (
    "Bargeld",
    "Debitkarte",
    "Kreditkarte",
    "TWINT",
)
