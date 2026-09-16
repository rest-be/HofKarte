# Architektur

Technischer Überblick über HofKarte für Entwickler:innen und
Beitragende. Für die Endanwender-Perspektive siehe
[`docs/handbuch.md`](handbuch.md); für Installation/Kurzübersicht siehe
[`README.md`](../README.md).

## Grundprinzip

Home Assistant ist sowohl **Laufzeitumgebung als auch
Verwaltungsoberfläche** für HofKarte (Architekturentscheid, siehe
CHANGELOG). Es gibt:

- keine eigenständige Webanwendung,
- kein externes Backend,
- keine externe Datenbank,
- keine externe API, die HofKarte selbst aufruft (Ausnahme: das Laden
  vom Benutzer hinterlegter Hofladen-Bild-URLs).

Alle Daten liegen ausschliesslich lokal im
Home-Assistant-eigenen Storage.

## Zusammenspiel der Kernkomponenten

```text
┌─────────────────┐     ┌───────────────────────┐     ┌──────────────────┐
│   Config Flow    │────▶│      ConfigEntry       │────▶│  async_setup_entry │
│ (config_flow.py) │     │  (Anzeigename, Single-  │     │   (__init__.py)    │
└─────────────────┘     │   Instance erzwungen)   │     └────────┬──────────┘
                         └───────────────────────┘              │
                                                                  ▼
┌──────────────────┐     ┌────────────────────────┐     ┌──────────────────┐
│ StorageHofladen-  │◀───▶│ HofKarteUpdateCoordinator│────▶│  device.py        │
│ DataProvider      │     │   (coordinator.py)       │     │ (Device Registry)  │
│ (data_provider.py)│     └────────────┬─────────────┘     └──────────────────┘
└──────────────────┘                  │
                                        ▼
                         ┌──────────────────────────────┐
                         │ Entities (binary_sensor.py,   │
                         │ sensor.py, image.py)          │
                         │ – lesen ausschliesslich aus    │
                         │   coordinator.data             │
                         └──────────────────────────────┘
```

### Config Flow → ConfigEntry

`config_flow.py` fragt genau **ein** Feld ab (Anzeigename,
`CONF_NAME`). HofKarte ist als Single-Instance-Integration ausgelegt:
`self._async_current_entries()` verhindert eine zweite Einrichtung
(Abbruchgrund `single_instance_allowed`). Es gibt **keinen Options
Flow** (siehe `quality_scale.yaml`, Kriterium `reconfiguration-flow`).

### ConfigEntry → Setup

`__init__.py` unterscheidet zwei Setup-Ebenen:

- **`async_setup(hass, config)`** – läuft einmalig beim Laden der
  Domain (unabhängig von einer konkreten ConfigEntry): registriert die
  WebSocket-Verwaltungsbefehle (`management.py`), die statischen
  Frontend-Assets (`frontend.py`) und die Home-Assistant-Action
  (`services.py`).
- **`async_setup_entry(hass, entry)`** – läuft je ConfigEntry: erstellt
  `StorageHofladenDataProvider` und `HofKarteUpdateCoordinator`, führt
  den initialen Datenabruf durch, synchronisiert die Device Registry
  und leitet an die Entity-Plattformen weiter
  (`Platform.BINARY_SENSOR`, `Platform.SENSOR`, `Platform.IMAGE`).

### Coordinator → Data Provider

`HofKarteUpdateCoordinator` (`coordinator.py`, Subclass von
`DataUpdateCoordinator`) kennt nur die abstrakte Schnittstelle
`HofladenDataProvider`/`MutableHofladenDataProvider`
(`data_provider.py`) – nicht deren konkrete Implementierung. Produktiv
kommt `StorageHofladenDataProvider` zum Einsatz (kapselt Home
Assistants `helpers.storage.Store`, JSON-Datei unter `.storage/`);
`StaticTestDataProvider` ist eine reine In-Memory-Variante für die
Testsuite.

Der Coordinator bietet öffentliche Schreibmethoden
(`async_add_hofladen`, `async_update_hofladen_sortiment`,
`async_save_hofladen`, `async_delete_hofladen`) – **alle**
Schreibzugriffe (Verwaltungsoberfläche, künftige eigene Skripte) laufen
über diese Methoden, nie direkt über den Data Provider. Jede Methode
validiert Fail-Fast über `parsing.parse_hofladen`, bevor irgendetwas
geschrieben wird, und löst danach einen regulären Refresh aus.

### Coordinator → Devices/Entities

`device.py` (`async_sync_devices`) gleicht die Device Registry bei
jedem Coordinator-Update mit den aktuellen Hofladen-Daten ab: neue
Hofläden erhalten ein Device, entfernte Hofläden verlieren ihres
(idempotent, keine Duplikate bei Reload).

Entities (`binary_sensor.py`, `sensor.py`, `image.py`) erben von der
gemeinsamen Basisklasse `HofKarteEntity` (`entity.py`,
`CoordinatorEntity`-Subklasse) und lesen **ausschliesslich** aus
`coordinator.data` – keine eigenen Netzwerk- oder Datenzugriffe pro
Entity. `entity.async_setup_hofladen_entities` legt beim Setup Entities
für alle bekannten Hofläden an und reagiert über einen
Coordinator-Listener automatisch auf später hinzukommende Hofläden
(kein Reload nötig).

## Datenmodell und Datenquelle

`models.py` definiert das interne, unveränderliche (`frozen`
Dataclasses) Datenmodell (`Hofladen`, `Oeffnungszeit`,
`Sonderoeffnungszeit`, `Produkt`, `Kategorie`, `Zahlungsart`,
`Verkaufsart`, `Merkmal`, `Bild`). `parsing.py` überführt rohe,
JSON-kompatible `dict`-Daten in dieses Modell und validiert dabei
(`HofladenValidationError` bei ungültigen Pflichtfeldern).

Die Datenquelle ist final festgelegt (siehe CHANGELOG,
„Architekturentscheid: Datenquelle final festgelegt“): ein
integrationsinterner, persistenter Store
(`StorageHofladenDataProvider`), gepflegt über die grafische
Verwaltungsoberfläche. Keine externe Datenbank, kein externer Dienst.

## Öffnungszeiten-Logik

`opening_hours.py` ist die **alleinige** Stelle für die
Öffnungsstatus-Berechnung (`is_open`, `get_next_opening`,
`get_next_closing`). Statt Wochentage modular zu vergleichen, werden
für ein Zeitfenster rund um den Berechnungszeitpunkt konkrete,
zeitzonenbewusste Datum-Uhrzeit-Intervalle erzeugt
(`datetime.combine(datum, uhrzeit, tzinfo=...)` statt naiver
`timedelta`-Arithmetik). Das macht Mitternachtsüberschreitung und
Wochenwechsel zu Spezialfällen der allgemeinen Logik statt zu eigenem
Sonderfall-Code. Sonderöffnungszeiten überschreiben reguläre
Öffnungszeiten vollständig für ihr Datum.

## Geo-/Entfernungslogik

`distance.py` berechnet die Luftlinien-Entfernung
(Haversine-Formel) zwischen der konfigurierten
Home-Assistant-Position (`hass.config.latitude`/`longitude`) und den
Koordinaten eines Hofladens. Reine, HA-unabhängige Fachfunktionen;
`is_valid_home_position` behandelt das Standardpaar `0.0/0.0` einer
unkonfigurierten Installation als unbekannt.

### Koordinaten und Kartenanzeige (Google Maps)

Koordinaten werden in der Verwaltungsoberfläche als WGS84-Dezimalgrad
erfasst und angezeigt – identisch zum internen Datenmodell
(`models.Hofladen.latitude`/`longitude`). Es findet **keine
Koordinatentransformation** statt: Eingabe-, Speicher- und
Anzeigeformat sind durchgehend dasselbe.

Sowohl „Bearbeiten“ als auch „Details“ bieten einen Button, der den
Hofladen-Standort auf Google Maps öffnet (`hofkarte-panel.js`,
Funktionen `googleMapsUrl`/`mapButton` – **eine** gemeinsame
Implementierung für beide Ansichten, kein Code-Duplikat). Die
gespeicherten WGS84-Koordinaten werden direkt in Google Maps' offiziell
dokumentiertes URL-Schema übernommen
(`https://www.google.com/maps/search/?api=1&query={lat},{lon}`) – keine
Umrechnung nötig. Der Button ist deaktiviert, wenn keine gültigen
Koordinaten vorliegen (`isValidWgs84`); die Kartenansicht ist ein rein
lesender externer Link ohne neue Abhängigkeit.

## Sortiment-Logik

`attributes.py` überführt Kategorien/Produkte/Zahlungsarten/
Verkaufsarten/Merkmale eines Hofladens in eine stabile,
JSON-taugliche Attributstruktur für den Binary Sensor „Geöffnet“ (siehe
Handbuch, Kapitel 8). `sortiment_katalog.py` bietet einen optionalen
Vorschlagskatalog gängiger Werte.

## Bilder

`images.py` validiert Bild-URLs (nur `http`/`https`, keine
eingebetteten Zugangsdaten, keine literale private/interne IP-Adresse
– rein syntaktisch, keine DNS-Auflösung, siehe `SECURITY.md`).
`image.py` nutzt Home Assistants natives `image`-Entity und dessen
eigenen Bild-Proxy/Cache – HofKarte implementiert keine eigene
Bildabruf-Pipeline.

## Suche/Filter

`search.py` (`find_hoflaeden`) ist eine reine, HA-unabhängige
Fachfunktion für die UND-verknüpfte Filterung. `services.py` bindet sie
als Home-Assistant-Action (`hofkarte.hoflaeden_suchen`) an.

## Grafische Verwaltungsoberfläche (Architekturabweichung)

`frontend.py` (Sidebar-Panel-Registrierung) und `management.py`
(WebSocket-Befehle `hofkarte/management/list|save|delete`) bilden eine
**bewusste Abweichung** vom ursprünglichen Umsetzungsplan (der für
Suche/Filter/Actions keine eigene UI vorsah). Begründung: Da Home
Assistant sowohl Laufzeit- als auch Verwaltungsoberfläche ist, ist eine
native, in HA integrierte Verwaltungsseite konsistent mit diesem
Prinzip. Alle Schreibzugriffe der Oberfläche laufen über die
öffentlichen Coordinator-Methoden (siehe oben), nicht über eine eigene
Datenhaltung.

Das Panel (`static/hofkarte-panel.js`) trennt drei Ansichten
(client-seitiger Zustand, kein serverseitiges Routing): Liste,
Bearbeiten und eine reine **Detailansicht** (read-only). Die
Detailansicht benötigt keinen eigenen WebSocket-Befehl – sie zeigt die
bereits über `hofkarte/management/list` geladenen Daten an, ohne
Bearbeitungsmöglichkeit.

## Diagnostics

`diagnostics.py` liefert eine technische Übersicht (Status des letzten
Abrufs, Update-Intervall, Provider-Typ, Anzahl Hofläden) **ohne**
Hofladen-Inhalte oder Standortdaten (siehe README, Abschnitt
„Datenschutz“).

## Performance

- Ein gemeinsamer Coordinator verhindert Mehrfachabfragen einzelner
  Entities.
- `PARALLEL_UPDATES = 0` in allen drei Entity-Plattformen (keine
  pro-Entity-Netzwerkzugriffe, die gedrosselt werden müssten).
- Keine blockierenden Aufrufe im Event Loop – konkretes Beispiel: Die
  ursprüngliche Bild-URL-Sicherheitsprüfung nutzte testweise
  `socket.getaddrinfo` (blockierende DNS-Auflösung) und wurde durch
  eine rein syntaktische, nicht-blockierende Prüfung ersetzt (siehe
  CHANGELOG).

## Erweiterungspunkte

Für Beitragende, die HofKarte erweitern möchten:

- **Neue Fachlogik** (z. B. weitere Filterkriterien): eigenes,
  HA-unabhängiges Modul nach dem Muster von `opening_hours.py`/
  `distance.py`/`search.py` – reine Funktionen, kein `hass`-Zugriff,
  isoliert testbar.
- **Neue Entity:** eigene Plattform-Datei, `HofKarteEntity` als Basis,
  Registrierung über `entity.async_setup_hofladen_entities` für
  automatische Erzeugung bei neuen Hofläden.
- **Neuer Data Provider** (z. B. für eine andere Datenquelle):
  `MutableHofladenDataProvider` implementieren; Coordinator und
  Entities benötigen keine Änderung, da sie nur die abstrakte
  Schnittstelle kennen.
- **Neue Schreiboperation:** als öffentliche Methode auf
  `HofKarteUpdateCoordinator` ergänzen (Fail-Fast-Validierung +
  Refresh-Muster wie bei den bestehenden Methoden), nicht direkt am
  Data Provider vorbei.

Siehe auch `quality_scale.yaml` für offene, bewusst zurückgestellte
Verbesserungspunkte (z. B. `runtime-data`-Migration, Repair-Issues).
