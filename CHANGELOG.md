## 0.10.2
- Stammdatenformular neu strukturiert: Name, Beschreibung, Adresse, PLZ/Ort, Land, Latitude/Longitude, Webseite.
- Neues Feld `website` durchgängig im Datenmodell, Parsing und Management-UI.

# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden in dieser Datei
dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.0.0/),
die Versionierung folgt [Semantic Versioning](https://semver.org/lang/de/).

## [Unveröffentlicht]

### Behoben

- **Kritischer Bug in `frontend.py`:** `manifest.json` deklarierte keine
  Abhängigkeit zu `http`. Dadurch war `hass.http` zum Zeitpunkt von
  `async_setup_frontend_assets` nicht zuverlässig initialisiert (`None`)
  und der Aufruf von `hass.http.async_register_static_paths(...)` konnte
  mit `AttributeError` fehlschlagen – was den Start der **gesamten**
  HofKarte-Integration verhindert hätte, nicht nur des Panels. Behoben
  durch `"dependencies": ["http"]` in `manifest.json`.
- `frontend.py`: ungenutzten Import (`const.DOMAIN`) entfernt
  (pyflakes-Fund).

### Hinzugefügt

- Tests für das Sidebar-Panel (`tests/test_frontend.py`): statische
  Asset-Registrierung, Panel-Registrierung inkl. Konfiguration
  (Sidebar-Titel, `require_admin`, JS-URL), Idempotenz bei
  Doppelregistrierung, korrektes Entfernen beim Entladen sowie
  No-Op-Verhalten, wenn kein Panel registriert ist.
- Tests für die WebSocket-Verwaltungs-API (`tests/test_management.py`):
  JSON-Serialisierung verschachtelter Hofladen-Daten (Zeiten, Tupel),
  Fehlerfall ohne eingerichtete Integration, Auflisten, Erstellen (mit
  automatisch generierter ID), Aktualisieren, Ablehnen ungültiger Daten,
  Löschen, Fehler bei unbekannter ID sowie bei einem nicht
  schreibfähigen Data Provider, und Registrierung aller drei
  WebSocket-Befehle.

### Architekturentscheid: eigene grafische Verwaltungsoberfläche

- Bestätigt und beibehalten: Abweichend vom ursprünglichen Plan für
  Einheit 10 („Keine eigene UI“, „Keine proprietäre REST-API“) verwaltet
  HofKarte Hofläden über ein eigenes Sidebar-Panel mit
  WebSocket-Backend (`frontend.py`, `management.py`) statt über
  Home-Assistant-Actions/Services. Diese Abweichung ist bewusst und
  dokumentiert (siehe README, Abschnitt „Grafische
  Hofladenverwaltung“).

### Abgleich Einheit 1–9

- Datenquelle als verbindliche Architekturentscheidung dokumentiert:
  Home Assistant `helpers.storage.Store` ist der persistente,
  integrationsinterne Speicher; keine externe Datenbank, kein externer Dienst
  und keine eigene REST-API.
- Veraltete Dokumentation im Config Flow und Parsing zum inzwischen
  festgelegten Data Provider entfernt.
- Verhalten bei entfernten Hofläden dokumentiert: Das Device wird entfernt,
  bereits registrierte Entities bleiben mit stabiler `unique_id` bestehen und
  werden `unavailable`.
- Home-Assistant-Position für den Distance Sensor plausibilisiert: Das
  Standardpaar `0.0/0.0` wird als unbekannt behandelt; gültige einzelne
  `0.0`-Koordinaten bleiben zulässig.
- Tests für die Positionsvalidierung ergänzt.


### Architekturentscheid

- **Datenquelle final festgelegt** (löst die seit Einheit 4 offene
  Architekturentscheidung): Home Assistant ist sowohl Laufzeitumgebung
  als auch Verwaltungsoberfläche für HofKarte. Die vom Benutzer
  gepflegten Hofläden werden in einem integrationsinternen, persistenten
  Store gehalten – keine externe Datenbank, kein externer Dienst. Der
  `HofladenDataProvider` kapselt diesen Store; Coordinator und Entities
  greifen ausschliesslich über diese Abstraktion darauf zu.

### Hinzugefügt

- `data_provider.py`: neue produktive Implementierung
  `StorageHofladenDataProvider`, basierend auf Home Assistants
  `helpers.storage.Store` (JSON-Datei unter `.storage/`). Startet leer
  (keine erfundenen Beispieldaten), lädt Daten einmalig (Lazy Load,
  In-Memory-Cache) und schreibt bei jeder Mutation sowohl in den Cache
  als auch persistent in den Store. Ein `asyncio.Lock` schützt vor
  verlorenen Schreibzugriffen bei gleichzeitigen Änderungen.
- Tests für `StorageHofladenDataProvider`: leerer Start, Kopie bei
  `fetch`, Hinzufügen/Abrufen, doppelte ID abgelehnt, Update mit
  Feld-Merge, unbekannte ID abgelehnt, sowie zwei Tests, die *echte*
  Persistenz über eine neue Provider-Instanz hinweg verifizieren
  (simuliert einen Neustart/Reload).
- `test_init.py`: neuer Test, der bestätigt, dass ein frischer Eintrag
  ohne Hofläden startet (`coordinator.data == {}`), sowie ein
  End-zu-End-Test, der einen echten `hass.config_entries.async_reload`
  durchführt und bestätigt, dass ein zuvor hinzugefügter Hofladen den
  Reload übersteht.

### Geändert

- `__init__.py`: `async_setup_entry` verwendet nun
  `StorageHofladenDataProvider(hass)` statt `StaticTestDataProvider()`.
  `StaticTestDataProvider` bleibt unverändert als reiner
  Testdaten-Provider für die Testsuite bestehen.
- `data_provider.py`: Moduldokumentation und Docstring von
  `StaticTestDataProvider` aktualisiert (nicht mehr „offene
  Architekturentscheidung“, sondern klar als testspezifisch markiert).
- Vier bestehende End-zu-End-Tests (`test_device.py`, `test_sensor.py`,
  `test_binary_sensor.py`), die implizit auf den bisherigen
  Standard-Platzhalter-Hofladen des alten `StaticTestDataProvider` in
  der Produktion angewiesen waren, wurden angepasst: Sie fügen den
  Testdatensatz jetzt explizit über `coordinator.async_add_hofladen`
  hinzu, da ein frischer Store ohne vorbelegte Daten startet.

## [0.9.1] - Unveröffentlicht

### Hinzugefügt

- Ergänzung zu Einheit 8: Sortiment und Eigenschaften eines **bestehenden**
  Hofladens sind jetzt nutzereditierbar.
- `data_provider.py`: `MutableHofladenDataProvider.async_update_raw_hofladen`
  (teilweise Aktualisierung eines bestehenden Rohdatensatzes), neue
  `HofladenNotFoundError`. Implementiert in `StaticTestDataProvider`.
- `coordinator.py`: `HofKarteUpdateCoordinator.async_update_hofladen_sortiment`
  – bewusst auf genau die fünf Fachbereiche beschränkt (Kategorien,
  Produkte, Zahlungsarten, Verkaufsarten, Merkmale); andere Felder
  (Name, Adresse, Öffnungszeiten, ...) bleiben unangetastet. Fail-Fast
  wie bei `async_add_hofladen`: Validierung vor jedem Schreibzugriff,
  Refresh danach für konsistente `coordinator.data` und Entities.
- `const.py`: `STANDARD_ZAHLUNGSARTEN` (Bargeld, Debitkarte, Kreditkarte,
  TWINT), `STANDARD_VERKAUFSARTEN` (Hofladen, Selbstbedienung,
  Verkaufsautomat, Ab-Hof-Verkauf), `STANDARD_MERKMALE` (Bio, eigener
  Anbau, Parkplatz, barrierefrei) als Vorschlagswerte.
- Neues Modul `sortiment_katalog.py`: erzeugt aus den Standardwerten
  direkt verwendbare, gültige Rohdaten (`{"id": ..., "name": ...}`) inkl.
  deterministischer ID-Ableitung (`slug`).
- Tests für Provider-Update (Feld-Merge, unbekannte ID), Coordinator-
  Update (einzelnes Feld, mehrere Felder gleichzeitig, explizites Leeren
  via `[]`, kein Parameter = keine Änderung, unbekannte ID, ungültige
  Daten ändern nichts, nicht unterstützt bei read-only Provider),
  Standardkatalog (Namen, Slug-Determinismus, Round-Trip-Gültigkeit über
  `parse_hofladen`) sowie ein End-zu-End-Test, der bestätigt, dass eine
  Sortiment-Änderung sich ohne Reload in den State-Attributen
  niederschlägt.

### Hinweis

- Wie beim Hinzufügen keine Home-Assistant-Oberfläche (Service/UI) –
  reine Python-Ebene.
- Der Standardkatalog ist ein Vorschlag; Nutzer sind auf keine
  bestimmten Werte beschränkt (siehe `parsing.py`: jeder nicht-leere
  Name ist gültig).

## [0.9.0] - Unveröffentlicht

### Hinzugefügt

- Entfernungsberechnung als reine, testbare Fachfunktionen in
  `distance.py`: `haversine_distance_km` (Grosskreisdistanz, korrekt auch
  über die Datumsgrenze hinweg), `calculate_distance_km` (liefert `None`
  bei fehlender Home- oder Hofladen-Position) und `round_distance_km`
  (Rundung für die Anzeige, standardmässig 1 Nachkommastelle).
- Sensor „Entfernung“ (`HofKarteEntfernungSensor` in `sensor.py`) pro
  Hofladen: Device Class `distance`, Einheit Kilometer,
  `state_class: measurement`, `suggested_display_precision: 1`. Nutzt
  ausschliesslich `hass.config.latitude`/`longitude` als Referenzpunkt.
- Tests für bekannte Koordinaten, identische Koordinaten (0 km),
  Symmetrie, Antipoden (halber Erdumfang), Datumsgrenze, Rundung,
  fehlende Home-Position, fehlende Hofladen-Koordinaten sowie
  End-zu-End-Tests über den tatsächlichen Home-Assistant-State.

### Geändert

- `sensor.py`: `async_setup_entry` registriert zusätzlich
  `HofKarteEntfernungSensor` über den bestehenden
  `async_setup_hofladen_entities`-Mechanismus (automatische Erzeugung
  auch für später hinzugefügte Hofläden, kein Reload nötig).

### Eingehaltene Grenzen

- Keine Speicherung der Home-Assistant-Position durch die Integration –
  `hass.config.latitude`/`longitude` wird bei jeder Berechnung live
  gelesen, nie zwischengespeichert.
- Keine Standortübertragung an externe Dienste – die Berechnung erfolgt
  vollständig lokal (reine Mathematik, kein Netzwerkzugriff).
- Keine eigene Kartenkomponente.

## [0.8.0] - Unveröffentlicht

### Hinzugefügt

- Sortiment und Eigenschaften (Kategorien, Produkte, Zahlungsarten,
  Verkaufsarten, Merkmale) als `extra_state_attributes` am Binary Sensor
  „Geöffnet“ (`attributes.py`, `build_sortiment_attributes`). Bewusst
  keine zusätzlichen Sensoren erstellt (Regeln: „Keine künstlichen
  Messwerte“, „Keine unnötigen Entities“).
- Produkte enthalten die aufgelösten Namen ihrer zugeordneten Kategorien
  (Fallback auf die rohe Kategorie-ID, falls diese im Hofladen nicht
  existiert).
- Fehlende Sammlungen ergeben stets eine leere Liste statt `None` oder
  einem fehlenden Schlüssel (stabile Attributstruktur).
- Namen werden für eine deterministische Darstellung sortiert
  (`str.casefold`, Unicode-Codepoint-Reihenfolge).
- Tests für vollständiges Mapping, fehlende Werte, Kategorie-Auflösung
  (inkl. unbekannter IDs), Sortierverhalten sowie End-zu-End-Tests über
  den tatsächlichen Home-Assistant-State.

### Geändert

- `binary_sensor.py`: `HofKarteGeoeffnetBinarySensor` liefert nun
  `extra_state_attributes` über `attributes.build_sortiment_attributes`.

### Bewusst nicht dupliziert

- Die Sensoren „Nächste Öffnung“/„Nächste Schliessung“ tragen diese
  Attribute nicht (Regeln dieser Einheit: grosse Datenmengen nicht bei
  jeder State-Änderung duplizieren) – durch einen expliziten Test
  abgesichert.

## [0.7.0] - Unveröffentlicht

### Hinzugefügt

- Vollständige, deterministische Öffnungszeiten-Berechnung in
  `opening_hours.py`: `is_open`, `get_next_opening`, `get_next_closing`.
  Unterstützt mehrere Intervalle pro Tag, Sonderöffnungszeiten
  (inkl. Sonder-Schliessung über einen Datumsbereich),
  Mitternachtsüberschreitung, Wochenwechsel und die Zeitzone des
  Home-Assistant-Systems (zeitzonenbewusste Berechnung statt naiver
  Datums-/Uhrzeit-Arithmetik).
- Binary Sensor „Geöffnet“ sowie die Sensoren „Nächste Öffnung“ und
  „Nächste Schliessung“ liefern nun echte berechnete Werte statt des
  bisherigen Platzhalter-Zustands „unbekannt“.
- Umfangreiche Tests für alle in Einheit 7 geforderten Mindestfälle:
  offen innerhalb eines Intervalls, geschlossen vor Öffnung, geschlossen
  nach Schliessung, zwei Intervalle am selben Tag, Mitternacht (vor/nach/
  nach Ende), Sonderöffnung, Sonder-Schliessung (Einzeltag und
  Datumsbereich), Wochenwechsel sowie Zeitzonen-/Sommerzeit-Grenzfälle.

### Geändert

- `parsing.py`: Validierungsregel für `beginn`/`ende` (Öffnungszeit und
  Sonderöffnungszeit) gelockert. Bisher wurde `ende <= beginn`
  grundsätzlich abgelehnt; nun ist nur noch `ende == beginn` ungültig.
  `ende < beginn` ist gültig und wird als Mitternachtsüberschreitung
  interpretiert. Diese Änderung war notwendig, um die von Einheit 7
  geforderte Mitternachtsüberschreitung überhaupt abbilden zu können
  (Grenzen: „Keine Änderung der Entitätsarchitektur außer soweit für
  korrekte Zustände notwendig“).
- Bestehende Parsing-Tests entsprechend angepasst: der bisherige Test
  „Ende vor Beginn wird abgelehnt“ wurde durch einen Test ersetzt, der
  bestätigt, dass dies nun gültig ist (Mitternachtsüberschreitung); ein
  neuer Test deckt weiterhin `ende == beginn` als ungültig ab.

### Bekannte Grenze

- Uhrzeiten, die exakt in eine Sommerzeit-Umstellungslücke fallen oder im
  doppelt vorkommenden Bereich beim Zurückstellen liegen, werden mit der
  von Python/`zoneinfo` standardmässig gewählten Auflösung berechnet
  (kein explizites Disambiguieren dieser seltenen Grenzfälle).

## [0.6.0] - Unveröffentlicht

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
- Vorgesehenes Berechnungsmodul `opening_hours.py` (in dieser Einheit
  noch als Stub, liefert `None`; die robuste Implementierung folgt in
  Einheit 7).
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

## [0.10.0] - Einheit 10

### Hinzugefügt

- Native Home-Assistant-Seitenleiste „HofKarte“ zur grafischen Verwaltung der Hofläden.
- Hofläden können über die Oberfläche neu erstellt, bearbeitet und gelöscht werden.
- Stammdaten, Koordinaten, reguläre und Sonderöffnungszeiten sowie Sortiment und Eigenschaften sind grafisch editierbar.
- Änderungen werden ohne Neustart über den bestehenden Storage-Provider und Coordinator in Devices und Entities übernommen.
- Neue WebSocket-Schnittstelle für die geschützte Verwaltungsoberfläche.
- Persistentes Löschen von Hofläden im Storage-Provider.

### Sicherheit

- Verwaltungsoberfläche und Schreiboperationen erfordern Home-Assistant-Administratorrechte.
- Keine externe Datenquelle, keine externe API und keine Standortübertragung.
