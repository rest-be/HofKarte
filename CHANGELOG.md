# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden in dieser Datei
dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.0.0/),
die Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/).

## [Unveröffentlicht]

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

### Offene Architekturentscheidung

- Die konkrete Datenquelle für Hofladen-Daten steht noch nicht fest.
  Der Config Flow beschränkt sich daher bewusst auf einen Anzeigenamen
  als einzige Konfigurationsoption.

## [0.1.0] - Unveröffentlicht

### Hinzugefügt

- Minimales, ladbares Home-Assistant-Integrationsgrundgerüst (Domain `hofkarte`).
- Grundlegende HACS-kompatible Repository-Struktur (`hacs.json`).
- README mit Installations- und Entwicklungsgrundlagen.
- Minimale Teststruktur (pytest + Home-Assistant-Testwerkzeuge).

### Noch nicht enthalten

- Options Flow
- Hofladen-Datenmodell
- DataUpdateCoordinator
- Devices und Entities
- Öffnungszeitenlogik
- HACS-Releaseprozess im Detail
