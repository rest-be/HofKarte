# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden in dieser Datei
dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.0.0/),
die Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/).

## [Unveröffentlicht]

### Hinzugefügt

- Zentraler `HofKarteUpdateCoordinator` (`coordinator.py`) für den
  asynchronen Abruf, die Validierung und Bereitstellung der
  Hofladen-Daten als `dict[str, Hofladen]`.
- Data-Provider-Abstraktion (`data_provider.py`) mit
  `HofladenDataProvider`-Schnittstelle und einer Testdaten-Implementierung
  (`StaticTestDataProvider`), solange die tatsächliche Datenquelle nicht
  feststeht.
- Konfigurierbares Update-Intervall (Standard 15 Minuten) und
  Abruf-Timeout (Standard 30 Sekunden) als Coordinator-Parameter.
- Initialer Datenabruf beim Einrichten der Config Entry über
  `async_config_entry_first_refresh` (inkl. automatischem Retry via
  `ConfigEntryNotReady` bei Fehlschlag).
- Tests für erfolgreichen Abruf, Zeitüberschreitung, Datenquellenfehler,
  einzelne ungültige Datensätze, leere Datenquelle und Verhalten bei
  einem Fehlversuch nach vorherigem Erfolg.

### Geändert

- `__init__.py`: `async_setup_entry` erstellt und startet nun den
  Coordinator und legt ihn (statt eines leeren Platzhalter-Dicts) unter
  `hass.data[DOMAIN][entry.entry_id]` ab.
- `const.py`: `DEFAULT_UPDATE_INTERVAL` und
  `DEFAULT_FETCH_TIMEOUT_SECONDS` ergänzt.

### Offene Architekturentscheidung

- Die konkrete Datenquelle für Hofladen-Rohdaten steht weiterhin nicht
  fest. Der Coordinator nutzt bewusst einen Testdaten-Provider
  (`StaticTestDataProvider`) statt einer erfundenen externen API.
- Das Update-Intervall ist aktuell nur auf Code-Ebene konfigurierbar,
  nicht über einen Options Flow in der Home-Assistant-Oberfläche.

### Noch nicht enthalten

- Options Flow
- Devices und Entities
- Öffnungszeitenlogik (Berechnung des aktuellen Öffnungsstatus)
- Persistenz / reale Datenquelle
- HACS-Releaseprozess im Detail

## [0.3.0] - Unveröffentlicht

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
