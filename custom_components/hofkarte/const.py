"""Konstanten für die HofKarte-Integration."""

from datetime import timedelta

DOMAIN = "hofkarte"

# Config Flow / Config Entry
DEFAULT_NAME = "HofKarte"

# Coordinator / Datenabruf
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=15)
DEFAULT_FETCH_TIMEOUT_SECONDS = 30

# Sortiment und Eigenschaften (User Editierbar):
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

# Options Flow ("Einstellungen", Issue Options Flow): dauerhaft
# gespeicherte Vorgabewerte für die Verwaltungsoberfläche, analog zur
# globalen „Einstellungen“-Maske der parallel gepflegten iOS-App. Anders
# als z. B. STANDARD_ZAHLUNGSARTEN sind dies keine fachlichen
# Vorschlagswerte für Hofladen-Daten, sondern Bedienungs-Vorgaben für die
# Übersicht bzw. „Angaben automatisch ermitteln“ selbst.
CONF_LISTEN_SORT_SPALTE = "listen_sort_spalte"
CONF_LISTEN_SORT_RICHTUNG = "listen_sort_richtung"
CONF_OSM_RADIUS_METER = "osm_radius_meter"

DEFAULT_LISTEN_SORT_SPALTE = "name"
DEFAULT_LISTEN_SORT_RICHTUNG = "asc"
# An die iOS-App angeglichener Standardwert (siehe Options Flow) - weicht
# bewusst vom historischen, deutlich kleineren Fallback in osm_info.py
# (STANDARD_RADIUS_METER, weiterhin als harte Absicherung für den Fall
# genutzt, dass keine Config Entry ermittelt werden kann) ab.
DEFAULT_OSM_RADIUS_METER = 200

# Zulässige Werte für das Standard-Sortierfeld der Übersicht - müssen mit
# den in der Listenansicht sortierbaren Spalten in hofkarte-panel.js
# übereinstimmen (Name/Adresse/Status/Bewertung). "geoeffnet" ist dabei
# der dort bereits bestehende interne Spaltenname für "Status" (siehe
# ``sortierteGefilterteItems()``/``listTable()``) - bewusst beibehalten
# statt umbenannt, um die bestehende Sortierlogik nicht unnötig
# anzufassen.
LISTEN_SORT_SPALTEN: tuple[str, ...] = ("name", "adresse", "geoeffnet", "bewertung")
LISTEN_SORT_RICHTUNGEN: tuple[str, ...] = ("asc", "desc")
