"""Konvertierung zwischen WGS84 und dem Schweizer Koordinatensystem LV95.

Architekturentscheid: Das interne Datenmodell (``models.Hofladen``)
speichert Koordinaten weiterhin als WGS84-Dezimalgrad
(``latitude``/``longitude``), **nicht** als LV95. Gründe:

- Home Assistants eigene Konventionen (``hass.config.latitude``/
  ``longitude``, Zonen, `device_tracker`, Kartenkarten) verwenden
  ausnahmslos WGS84 – eine Umstellung des internen Modells auf LV95
  würde die Integration inkompatibel mit dem gesamten
  Home-Assistant-Ökosystem machen.
- ``distance.py`` (Haversine-Formel) rechnet mit WGS84-Dezimalgrad.
- Eine Umstellung des Datenmodells wäre eine grundlegende
  Architekturänderung mit Migrationsrisiko für bestehende Daten
  (Regeln: „keine grundlegende Architekturänderung“, „keine
  stillschweigende Datenbeschädigung“).

LV95 wird daher **ausschliesslich als Eingabe-/Anzeigeformat** in der
grafischen Verwaltungsoberfläche verwendet (siehe
``static/hofkarte-panel.js``): Der Browser zeigt/erfasst LV95, rechnet
vor dem Speichern nach WGS84 um und beim Anzeigen von WGS84 nach LV95
um. Am gespeicherten Datenformat und an bestehenden Daten ändert sich
dadurch **nichts** – keine Migration nötig.

Dieses Modul implementiert dieselben Näherungsformeln wie das
JavaScript-Gegenstück im Verwaltungs-Panel (dort dupliziert, da Browser
und Python-Backend keine gemeinsame Laufzeitumgebung teilen und ein
Build-Schritt eine neue, hier nicht gewünschte Abhängigkeit wäre). Wird
aktuell nicht vom Python-Code direkt verwendet, sondern für serverseitige
Validierung/Tests sowie als eindeutige, getestete Referenzimplementierung
bereitgestellt.

## Genauigkeit

Es handelt sich um die von swisstopo veröffentlichten Näherungsformeln
(„Formeln und Konstanten für die Berechnung der Schweizerischen
schiefachsigen Zylinderprojektion und der Transformation zwischen
Koordinatensystemen“). Genauigkeit: ca. 1–5 Meter im Schweizer
Mittelland – deutlich ausreichend, um einen Hofladen einem Gebäude
zuzuordnen, aber **nicht** vermessungstechnisch exakt. Verifiziert gegen
den amtlichen swisstopo-Referenzpunkt „Wabern“ (E=2'600'980, N=1'197'450
↔ ca. 46.9281°N, 7.4515°E) mit einer Abweichung von unter 5 Metern.
"""

from __future__ import annotations

# Gültigkeitsbereich von LV95 (grobe Bounding Box Schweiz/Liechtenstein,
# siehe EPSG:2056 "Projected bounds"). Dient nur der Plausibilisierung,
# nicht einer exakten Landesgrenzen-Prüfung.
_LV95_EASTING_MIN = 2_485_000.0
_LV95_EASTING_MAX = 2_834_000.0
_LV95_NORTHING_MIN = 1_075_000.0
_LV95_NORTHING_MAX = 1_296_000.0


def wgs84_to_lv95(latitude: float, longitude: float) -> tuple[float, float]:
    """WGS84-Dezimalgrad in LV95 (Easting, Northing) umrechnen.

    Liefert ``(easting, northing)`` in Metern. Reine, deterministische
    Berechnung ohne Seiteneffekte.
    """
    phi_s = (latitude * 3600 - 169028.66) / 10000
    lam_s = (longitude * 3600 - 26782.5) / 10000

    easting = (
        2600072.37
        + 211455.93 * lam_s
        - 10938.51 * lam_s * phi_s
        - 0.36 * lam_s * phi_s**2
        - 44.54 * lam_s**3
    )
    northing = (
        1200147.07
        + 308807.95 * phi_s
        + 3745.25 * lam_s**2
        + 76.63 * phi_s**2
        - 194.56 * lam_s**2 * phi_s
        + 119.79 * phi_s**3
    )
    return easting, northing


def lv95_to_wgs84(easting: float, northing: float) -> tuple[float, float]:
    """LV95 (Easting, Northing) in WGS84-Dezimalgrad umrechnen.

    Liefert ``(latitude, longitude)`` in Dezimalgrad.
    """
    y_s = (easting - 2600000) / 1_000_000
    x_s = (northing - 1200000) / 1_000_000

    lambda_s = (
        2.6779094
        + 4.728982 * y_s
        + 0.791484 * y_s * x_s
        + 0.1306 * y_s * x_s**2
        - 0.0436 * y_s**3
    )
    phi_s = (
        16.9023892
        + 3.238272 * x_s
        - 0.270978 * y_s**2
        - 0.002528 * x_s**2
        - 0.0447 * y_s**2 * x_s
        - 0.0140 * x_s**3
    )

    longitude = lambda_s * 100 / 36
    latitude = phi_s * 100 / 36
    return latitude, longitude


def is_valid_lv95(easting: float, northing: float) -> bool:
    """Ob ein LV95-Koordinatenpaar plausibel innerhalb der Schweiz/
    Liechtensteins liegt (grobe Bounding-Box-Prüfung, siehe EPSG:2056).

    Dient der Fehlermeldung bei offensichtlichen Eingabefehlern (z. B.
    vertauschte Werte oder WGS84-Werte versehentlich als LV95
    eingegeben) – keine exakte Landesgrenzen-Prüfung.
    """
    return (
        _LV95_EASTING_MIN <= easting <= _LV95_EASTING_MAX
        and _LV95_NORTHING_MIN <= northing <= _LV95_NORTHING_MAX
    )
