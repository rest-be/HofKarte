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
`Sonderoeffnungszeit`, `Angebot`, `Zahlungsart`, `Bild`). `parsing.py`
überführt rohe, JSON-kompatible `dict`-Daten in dieses Modell und
validiert dabei (`HofladenValidationError` bei ungültigen
Pflichtfeldern).

**Architekturentscheid – Angebote statt Kategorien/Produkte, ohne
Gruppierung:** Die früher getrennten Konzepte `Kategorie` (eigene, über
IDs referenzierte Liste) und `Produkt` (referenziert Kategorien über
`kategorie_ids`) wurden zunächst zu einem gemeinsamen `Angebot`
zusammengelegt und danach – nach weiterer Vereinfachung – auf
`Angebot(id, name)` reduziert: **keine Gruppierung mehr**. Ein
zwischenzeitlich eingeführtes Feld `gruppen` (frei formulierte
Textbezeichnungen direkt am Angebot) wurde wieder entfernt, da der
Mehrwert der Gruppierung den zusätzlichen Pflegeaufwand nicht
rechtfertigte (siehe CHANGELOG).

`parsing.py` enthält weiterhin `_migriere_kategorien_und_produkte_zu_angeboten`:
eine Migration, die beim Einlesen alter Rohdaten (Schlüssel
`kategorien`/`produkte`) automatisch greift, sobald der Schlüssel
`angebote` fehlt. Seit der Vereinfachung werden sowohl Kategorien als
auch Produkte gleichermassen zu flachen Angebot-Einträgen (nur
`id`/`name`) – eine `kategorie_ids`-Auflösung findet nicht mehr statt,
da es keine Gruppierung mehr gibt, in die sie einfliessen könnte. Liegt
bereits das neue Format vor (`angebote`-Schlüssel vorhanden), greift
die Migration nicht (Idempotenz, siehe
`tests/test_migration_kategorien_produkte_zu_angebote.py`). Ein
eventuell noch vorhandenes `gruppen`-Feld an einzelnen Angeboten wird
beim Einlesen ignoriert, nicht übernommen.

**Ebenfalls entfernt:** Die Fachbereiche `Verkaufsart` und `Merkmal`
wurden ersatzlos aus dem Datenmodell entfernt (siehe CHANGELOG).
Bestehende Rohdaten mit diesen Feldern werden beim Einlesen weiterhin
fehlerfrei verarbeitet (die Felder werden schlicht nicht mehr
ausgewertet).

**Neu: `Hofladen.bemerkung`** – ein von `beschreibung` unabhängiges,
optionales Freitextfeld auf Hofladen-Ebene (nicht je Angebot, da
Angebote seit der Vereinfachung bewusst keine weitere Struktur mehr
tragen).

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

### Entfernung vom aktuellen Gerät (clientseitig)

`haversineDistanceKm` in `hofkarte-panel.js` ist ein bewusstes,
dokumentiertes JS-Duplikat von `distance.haversine_distance_km`
(numerisch gegen die Python-Referenz verifiziert) – **nicht**
serverseitig implementiert, da der Gerätestandort aus
Datenschutzgründen nie an das Backend übertragen wird. Ergänzt in der
Detailansicht die bestehende, serverseitige Entfernungs-Entity, ersetzt
sie nicht: Eine Home-Assistant-Entity hat genau einen Zustand für alle
Betrachter:innen und kann sich nicht sinnvoll pro Gerät unterscheiden.
Nutzt `navigator.geolocation.getCurrentPosition` mit expliziter
Fehlerbehandlung für verweigerte/nicht unterstützte/zeitüberschreitende
Standortabfragen.

**Behobener Bug – unsicherer Kontext fälschlich als „verweigert“
gemeldet:** Browser gewähren Geolocation-Zugriff ausschliesslich in
einem sicheren Kontext (HTTPS oder `localhost`, siehe
[`window.isSecureContext`](https://developer.mozilla.org/docs/Web/API/Window/isSecureContext)).
Auf einer per einfachem `http://` erreichten Home-Assistant-Instanz
(im Heimnetz häufig, z. B. `http://192.168.1.50:8123`) lehnt der
Browser den Zugriff automatisch mit `PERMISSION_DENIED` ab, **ohne
jemals einen Freigabe-Dialog anzuzeigen** – das erschien fälschlich als
tatsächliche Ablehnung durch die Nutzerin/den Nutzer. Behoben durch
eine explizite `window.isSecureContext`-Prüfung **vor** dem eigentlichen
Geolocation-Aufruf, mit eigener, klar unterscheidbarer Fehlermeldung.

## Sortiment-Logik

`attributes.py` überführt Angebote und Zahlungsarten eines Hofladens in
eine stabile, JSON-taugliche Attributstruktur (jeweils eine schlichte
Namensliste) für den Binary Sensor „Geöffnet“ (siehe Handbuch,
Kapitel 8). `sortiment_katalog.py` bietet einen optionalen
Vorschlagskatalog gängiger Werte (nur für Zahlungsarten – nicht für
Angebote, da diese frei formuliert werden).

## Bilder

`images.py` validiert Bild-URLs (nur `http`/`https`, keine
eingebetteten Zugangsdaten, keine literale private/interne IP-Adresse
– rein syntaktisch, keine DNS-Auflösung, siehe `SECURITY.md`).
`image.py` nutzt Home Assistants natives `image`-Entity und dessen
eigenen Bild-Proxy/Cache – HofKarte implementiert keine eigene
Bildabruf-Pipeline.

### Geführter Bilder-Upload

Der Upload in der Verwaltungsoberfläche (`hofkarte-panel.js`)
implementiert **keinen eigenen** Upload-Endpunkt, sondern nutzt Home
Assistants eingebaute `image_upload`-Komponente vollständig:

- **Upload:** `POST /api/image/upload` (Multipart-Formular), liefert
  eine `image_id` zurück. **Erfordert Authentifizierung**
  (`ImageUploadView.requires_auth` ist nicht überschrieben, erbt also
  `True` von `HomeAssistantView`) – im Unterschied zur Auslieferung
  unten. Der clientseitige `fetch()`-Aufruf muss deshalb explizit einen
  `Authorization: Bearer <token>`-Header mit `this.hass.auth.accessToken`
  setzen; ohne diesen Header schlägt der Upload mit „Login attempt
  failed“/„invalid authentication“ im Home-Assistant-Log fehl, obwohl
  man in der Oberfläche angemeldet ist (behobener Bug, siehe
  CHANGELOG). WebSocket-Befehle (z. B. `image/delete`, `this.call()`)
  sind davon nicht betroffen, da die WebSocket-Verbindung bereits beim
  Verbindungsaufbau authentifiziert wird.
- **Auslieferung:** `GET /api/image/serve/{image_id}/original`
  (`requires_auth = False` in dieser Home-Assistant-Komponente – exakt
  passend zur bestehenden `image.py`-Entity, die eine öffentlich ohne
  zusätzliche Authentifizierung abrufbare Bild-URL erwartet).
- **Löschen:** WebSocket-Befehl `image/delete` (Teil der
  `image_upload`-Komponente, nicht von HofKarte selbst implementiert).
- Deklariert als `manifest.json`-Abhängigkeit (`image_upload`), analog
  zur bestehenden `http`-Abhängigkeit – ohne diese ist nicht garantiert,
  dass die Komponente beim Setup von HofKarte bereits initialisiert ist.

Die vom Upload erzeugte, absolute URL wird clientseitig aus
`window.location.origin` gebildet (der Browser kennt die tatsächlich
erreichbare Basis-URL der aktuellen Sitzung). **Bekannte Grenze:**
Läuft Home Assistant hinter einem Reverse Proxy mit unterschiedlichen
intern/extern erreichbaren Adressen, kann die vom Browser gebildete
URL für den serverseitigen Bildabruf (`ImageEntity._fetch_url`, siehe
oben) u. U. nicht erreichbar sein, obwohl sie im Browser selbst
funktioniert.

**Sicherheitsentscheid – `Bild.hochgeladen`:** Eine über den Upload
erzeugte URL zeigt zwangsläufig auf die eigene Home-Assistant-Instanz –
bei den meisten Installationen eine private LAN-Adresse. Die in
`images.py` beschriebene Ablehnung privater/interner IP-Adressen dient
dem Schutz vor SSRF über frei eingegebene, nicht vertrauenswürdige
externe URLs; sie ist bei einer von HofKarte selbst über den
offiziellen Upload-Weg erzeugten URL das falsche Kriterium. Das
Datenmodell (`models.Bild`) trägt daher ein explizites
`hochgeladen: bool`-Feld; `is_valid_image_url` überspringt bei
`hochgeladen=True` gezielt nur die Adressbereichs-Prüfung, nicht die
Schema-/Zugangsdaten-Prüfung (Defense in Depth). Die Vertrauensbasis
ist damit die **Herkunft** (von HofKarte selbst erzeugt), nicht der
Adressbereich – eine bewusste, im Modul dokumentierte Ausnahme statt
einer fragilen Erkennung anhand des URL-Musters.

## Suche/Filter

`search.py` (`find_hoflaeden`) ist eine reine, HA-unabhängige
Fachfunktion für die UND-verknüpfte Filterung. Der Parameter `angebot`
gleicht den Namen eines Angebots ab (ersetzt die früher getrennten
Parameter `kategorie`/`produkt`, siehe CHANGELOG; eine zwischenzeitliche
Erweiterung auf Gruppen-Abgleich wurde mit der Vereinfachung von
Angeboten wieder zurückgenommen). Die Parameter `verkaufsart` und
`merkmal` wurden ersatzlos entfernt, da die zugrunde liegenden
Fachbereiche selbst entfallen sind. `services.py` bindet die Funktion
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

### Übersicht: Kacheln/Liste, serverseitig berechnete Anzeigefelder

Die Listenansicht selbst bietet zwei Darstellungen (`uebersichtsAnsicht`,
rein clientseitiger Zustand, kein Backend-Unterschied): eine
Kachel-Ansicht (`listGrid`/`listCard`) und eine sortierbare
Tabellenansicht (`listTable`). Sortierung und Freitextfilter
(`sortierteGefilterteItems`) laufen vollständig clientseitig über die
bereits geladenen Daten – kein neuer WebSocket-Befehl nötig.

Für zwei Anzeigefelder wäre eine korrekte clientseitige Berechnung nur
durch Duplikation bereits bestehender, teils sicherheitsrelevanter
Backend-Logik möglich gewesen; stattdessen liefert
`management._serialize_hofladen` sie serverseitig vorberechnet mit:

- **`geoeffnet`** (`true`/`false`/`null`): über `opening_hours.is_open`
  – exakt dieselbe Funktion wie beim Binary Sensor „Geöffnet“
  (`binary_sensor.py`). `now` wird einmal pro WebSocket-Antwort ermittelt
  (`dt_util.now()`), nicht pro Hofladen, damit alle Hofläden einer
  Antwort konsistent gegen denselben Zeitpunkt bewertet werden.
- **`hauptbild_url`** (`str | None`): über `images.get_main_image_url`
  – exakt dieselbe Funktion (inkl. Sicherheitsprüfung gegen
  private/interne IP-Literale, siehe `SECURITY.md`) wie beim
  `image`-Entity für das tatsächliche Hauptbild (`image.py`).

Beide Felder werden von `ws_list` **und** `ws_save` mitgeliefert, damit
die Oberfläche nach dem Speichern eines einzelnen Hofladens dessen
Kachel/Zeile aktualisieren kann, ohne einen vollständigen `list`-Aufruf
zu benötigen.

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
