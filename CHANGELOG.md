# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden in dieser Datei
dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.0.0/),
die Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/).

## [Unveröffentlicht]

### Hinzugefügt

- Binary Sensor „Geöffnet“ (`binary_sensor.py`) pro Hofladen. Bewusst
  ohne Device Class, da keine Home-Assistant-Device-Class für „Geschäft
  geöffnet“ passt.
- Sensoren „Nächste Öffnung“ und „Nächste Schliessung“ (`sensor.py`) pro
  Hofladen, Device Class `timestamp`.
- Gemeinsame Entity-Basisklasse `HofKarteEntity` (`entity.py`) mit
  Device-Zuordnung und Verfügbarkeit (abhängig vom letzten
  Coordinator-Abruf und der Existenz des Hofladens in den Daten).
- `async_setup_hofladen_entities`-Helper (`entity.py`): legt Entities für
  alle aktuellen und künftig über den Coordinator hinzukommenden
  Hofläden an, ohne dass ein Reload nötig ist.
- Vorgesehenes, aktuell bewusst leeres Berechnungsmodul
  `opening_hours.py` mit den Funktionen `is_open`, `get_next_opening`,
  `get_next_closing` (liefern derzeit `None`). Die robuste
  Implementierung folgt in einer kommenden Einheit
  („Öffnungszeiten und Sonderöffnungszeiten“).
- Tests für Entity-Erzeugung, `unique_id`-Muster, Device-Zuordnung,
  fehlende Device Class beim Binary Sensor, Verfügbarkeit, sowie die
  dynamische Entity-Erzeugung bei neu hinzugefügten Hofläden.

### Geändert

- `__init__.py`: `PLATFORMS` umfasst nun `binary_sensor` und `sensor`.

### Behoben

- `data_provider.py`: `StaticTestDataProvider()` ohne explizite Testdaten
  referenzierte bisher die geteilte Default-Liste direkt statt einer
  Kopie. `async_add_raw_hofladen` konnte dadurch globalen, über
  Testläufe hinweg geteilten Zustand verändern. Behoben, indem der
  Konstruktor in jedem Fall eine Kopie anlegt.

### Nicht enthalten (planmässig)

- Robuste Öffnungszeiten-Berechnung (mehrere Intervalle, Sonderöffnungs-
  zeiten, Mitternachtsüberschreitung, Zeitzone) – folgt in einer
  kommenden Einheit.
- Entfernungs-Sensor (Geosuche/Entfernung ist noch nicht zuverlässig
  verfügbar).
- Automatische Entfernung von Entities verschwundener Hofläden aus der
  Entity Registry (bekannte Einschränkung, siehe README).

## [0.5.1] - Unveröffentlicht

### Hinzugefügt

- `MutableHofladenDataProvider`-Schnittstelle in `data_provider.py` für
  Provider mit Schreibzugriff, implementiert von `StaticTestDataProvider`
  (`async_add_raw_hofladen`, lehnt doppelte IDs mit
  `DuplicateHofladenIdError` ab).
- `HofKarteUpdateCoordinator.async_add_hofladen(raw_hofladen)`: validiert
  neue Hofladen-Rohdaten (Fail-Fast), reicht sie an den Provider weiter
  und stösst einen Refresh an, sodass Daten und Device Registry
  automatisch konsistent bleiben.
- Tests für erfolgreiches Hinzufügen, ungültige Rohdaten, doppelte IDs,
  nicht unterstützende (rein lesende) Provider sowie einen
  End-zu-End-Test, der bestätigt, dass ein neuer Hofladen automatisch ein
  Device erhält.

## [0.5.0] - Unveröffentlicht

### Hinzugefügt

- Device-Repräsentation für Hofläden (`device.py`): stabile
  `identifiers`, die ausschliesslich auf `Hofladen.id` basieren, sowie
  Synchronisation mit der Device Registry.
- `async_sync_devices` erzeugt bzw. aktualisiert für jeden Hofladen ein
  Device und entfernt Devices von Hofläden, die nicht mehr in den
  Coordinator-Daten enthalten sind.
- Devices werden beim Einrichten der Config Entry und bei jedem weiteren
  Coordinator-Update synchronisiert (`coordinator.async_add_listener`).
- Tests für Identifier-Stabilität, keine Hersteller-/Modellangaben,
  Erstellung mehrerer sauber getrennter Devices, Idempotenz bei Reload,
  Aktualisierung bei Namensänderung, Entfernen verschwundener Hofläden
  sowie einen End-zu-End-Test über `async_setup_entry`.

### Geändert

- `__init__.py`: ruft nach dem initialen Datenabruf `async_sync_devices`
  auf und hält die Device Registry über einen Coordinator-Listener aktuell.

## [0.4.0] - Unveröffentlicht

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
