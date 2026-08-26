"""Konstanten für die HofKarte-Integration."""

from datetime import timedelta

DOMAIN = "hofkarte"

# Config Flow / Config Entry
DEFAULT_NAME = "HofKarte"

# Coordinator / Datenabruf
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=15)
DEFAULT_FETCH_TIMEOUT_SECONDS = 30

# Sortiment und Eigenschaften (Einheit 8 / Ergänzung „User Editierbar“):
# Vorschlagswerte für die Fachbereiche Zahlungsarten, Verkaufsarten und
# Merkmale. Nutzer sind nicht auf diese Werte beschränkt – jeder beliebige
# Name ist zulässig (siehe parsing.py); dies ist lediglich ein sinnvoller
# Startkatalog, den z. B. ein künftiger Editier-Dialog vorschlagen kann.
STANDARD_ZAHLUNGSARTEN: tuple[str, ...] = (
    "Bargeld",
    "Debitkarte",
    "Kreditkarte",
    "TWINT",
)
STANDARD_VERKAUFSARTEN: tuple[str, ...] = (
    "Hofladen",
    "Selbstbedienung",
    "Verkaufsautomat",
    "Ab-Hof-Verkauf",
)
STANDARD_MERKMALE: tuple[str, ...] = (
    "Bio",
    "eigener Anbau",
    "Parkplatz",
    "barrierefrei",
)

# Home-Assistant-Actions (Einheit 10)
SERVICE_REFRESH = "refresh"
SERVICE_SEARCH = "search"
ATTR_SUCHBEGRIFF = "suchbegriff"
ATTR_KATEGORIE = "kategorie"
ATTR_PRODUKT = "produkt"
ATTR_VERKAUFSART = "verkaufsart"
ATTR_ZAHLUNGSART = "zahlungsart"
ATTR_MERKMAL = "merkmal"
ATTR_GEOEFFNET = "geoeffnet"
