# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden in dieser Datei
dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.0.0/),
die Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/).

## [Unveröffentlicht]

### Hinzugefügt

- Internes, typisiertes Datenmodell für Hofläden (`models.py`): Stammdaten,
  Öffnungszeiten, Sonderöffnungszeiten, Produkte, Kategorien,
  Zahlungsarten, Verkaufsarten, Merkmale, optionale Bilder. Alle
  Datenstrukturen sind unveränderlich (frozen dataclasses).
- Parsing/Validierung roher Hofladen-Daten in das interne Modell
  (`parsing.py`) inkl. `HofladenValidationError` bei ungültigen oder
  unvollständigen Pflichtdaten.
- Umfangreiche Tests für vollständige und unvollständige Datensätze sowie
  für einzelne Validierungsregeln (Koordinatenbereich, Zeitformate,
  Öffnungszeit-Reihenfolge, Sonderöffnungszeit-Regeln).

### Offene Architekturentscheidung

- Die konkrete Datenquelle für Hofladen-Rohdaten steht weiterhin nicht
  fest. `parsing.py` kennt bewusst nur ein einfaches, quellenunabhängiges
  Mapping-Format und keine bestimmte externe API.

### Noch nicht enthalten

- Options Flow
- DataUpdateCoordinator
- Devices und Entities
- Öffnungszeitenlogik (Berechnung des aktuellen Öffnungsstatus)
- Persistenz / eigene Datenquelle
- HACS-Releaseprozess im Detail

## [0.2.0] - Unveröffentlicht

### Hinzugefügt

- Config Flow (`config_flow.py`) zur Einrichtung über die
  Home-Assistant-Oberfläche.
- Config-Entry-Lifecycle (`async_setup_entry` / `async_unload_entry`) in
  `__init__.py`.
- Übersetzungsgrundlage (`strings.json`) sowie Übersetzungen für Englisch
  (`translations/en.json`) und Deutsch (`translations/de.json`).
- Tests für erfolgreichen Flow, ungültige Eingaben und doppelte Einrichtung.
- Tests für Setup/Unload einer Config Entry.

### Geändert

- `manifest.json`: `config_flow` auf `true` gesetzt.
- YAML-basiertes `async_setup` entfernt zugunsten von Config Entries
  (siehe Globale Konventionen: keine YAML-Konfiguration parallel zum
  Config Flow).

## [0.1.0] - Unveröffentlicht

### Hinzugefügt

- Minimales, ladbares Home-Assistant-Integrationsgrundgerüst (Domain `hofkarte`).
- Grundlegende HACS-kompatible Repository-Struktur (`hacs.json`).
- README mit Installations- und Entwicklungsgrundlagen.
- Minimale Teststruktur (pytest + Home-Assistant-Testwerkzeuge).
