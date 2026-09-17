# HofKarte

Private, lokal betriebene Home-Assistant-Custom-Integration zur Verwaltung
und Darstellung von Hofläden (Direktvermarkter, Selbstbedienungsläden,
Hofläden mit und ohne Personal).

> **Status:** MVP-Release. Die Integration ist funktional vollständig
> und getestet. Home Assistant ist sowohl Laufzeit- als auch
> Verwaltungsoberfläche für HofKarte – die vom Benutzer gepflegten
> Hofläden werden in einem integrationsinternen, persistenten Store
> gehalten (keine externe Datenbank, kein externer Dienst). Zusätzlich
> zu den regulären Home-Assistant-Entities bietet HofKarte eine
> **eigene grafische Verwaltungsoberfläche** (Sidebar-Panel) für
> Administrator:innen.

**📖 Für die vollständige Anleitung als Endanwender:in siehe das
[Anwendungshandbuch](docs/handbuch.md)** – Installation, Ersteinrichtung,
alle Entities, Öffnungszeiten, Actions/Automationen, Dashboard-Beispiele,
Fehlerbehebung, Datenschutz und Support in einem Dokument.

## Zweck

HofKarte verwaltet Hofläden lokal in Home Assistant: Stammdaten,
Öffnungszeiten, Sortiment (Angebote, Zahlungsarten) und Bilder. Jeder
Hofladen erscheint als Device
mit Entities für Öffnungsstatus, nächste Öffnung/Schliessung, Entfernung
zum eigenen Zuhause und Hauptbild. Eine Home-Assistant-Action erlaubt
das Durchsuchen und Filtern aus Automationen und Skripten heraus. Es
gibt keine eigenständige Webanwendung, kein externes Backend und keine
externe Datenbank – Home Assistant ist Laufzeit- **und**
Verwaltungsumgebung zugleich.

## Voraussetzungen

- Eine laufende Home-Assistant-Installation, Version **2025.1 oder
  neuer** (getestet gegen 2025.1.4; siehe `hacs.json`).
- [HACS](https://hacs.xyz/) für die empfohlene Installation (nicht
  zwingend – manuelle Installation ist möglich, siehe unten).
- Kein Cloud-Konto, kein externer Dienst und keine zusätzlichen
  Python-Pakete für HofKarte selbst nötig (`requirements: []` in
  `manifest.json`). Der geführte Bilder-Upload nutzt Home Assistants
  eingebaute `image_upload`-Komponente (Abhängigkeit `Pillow`), die von
  Home Assistant automatisch mitinstalliert wird.
- Für den Entfernungs-Sensor: eine sinnvoll gesetzte Position der
  Home-Assistant-Installation (**Einstellungen → System → Allgemein**).
  Ohne diese bleibt der Sensor auf „unbekannt“.

## Installation

### Über HACS (empfohlen)

1. HACS öffnen.
2. Über die Drei-Punkte-Menü-Schaltfläche **Benutzerdefinierte
   Repositories** auswählen.
3. Dieses Repository (`https://github.com/rest-be/HofKarte`) als
   **Integration** hinzufügen.
4. „HofKarte“ in HACS suchen und installieren.
5. Home Assistant neu starten.

*Hinweis: Solange dieses Projekt nicht im HACS-Default-Store gelistet
ist, sind die Schritte 2–3 (benutzerdefiniertes Repository) nötig.*

### Manuelle Installation

Nur nötig, wenn HACS nicht zur Verfügung steht oder eine
Entwicklungsversion getestet werden soll:

1. Den Ordner `custom_components/hofkarte/` in das
   `custom_components`-Verzeichnis der Home-Assistant-Konfiguration
   kopieren.
2. Home Assistant neu starten.
3. Prüfen, dass beim Start keine Fehler zur Domain `hofkarte` im Log
   erscheinen (siehe „Fehlerbehebung“ unten).

### Deinstallation

1. Unter **Einstellungen → Geräte & Dienste** die HofKarte-Integration
   entfernen (Drei-Punkte-Menü → **Löschen**). Dabei werden Devices und
   Entities automatisch entfernt.
2. Die gespeicherten Hofladen-Daten liegen als JSON-Datei unter
   `.storage/hofkarte_hoflaeden` im Home-Assistant-Konfigurationsverzeichnis
   und werden **nicht** automatisch mitgelöscht – bei Bedarf manuell
   entfernen.
3. Bei manueller Installation zusätzlich den Ordner
   `custom_components/hofkarte/` löschen. Bei einer Installation über
   HACS die Integration in HACS deinstallieren.
4. Home Assistant neu starten.

## Einrichtung

Nach der Installation:

1. In Home Assistant zu **Einstellungen → Geräte & Dienste** wechseln.
2. **Integration hinzufügen** wählen und nach „HofKarte“ suchen.
3. Im Einrichtungsdialog einen Anzeigenamen für die Integration vergeben
   (z. B. „HofKarte“) und bestätigen.

HofKarte ist als Single-Instance-Integration konzipiert: Es kann nur
eine Instanz pro Home-Assistant-Installation eingerichtet werden, da sie
eine zentrale, HA-weite Hofladen-Verwaltung darstellt. Ein erneuter
Einrichtungsversuch wird entsprechend abgelehnt.

## Konfiguration

HofKarte unterscheidet zwei Arten von „Konfiguration“:

- **Die Integration selbst:** Der Config Flow fragt ausschliesslich
  einen Anzeigenamen ab (siehe „Einrichtung“). Es gibt aktuell keinen
  Options Flow – Update-Intervall und Abruf-Timeout des Coordinators
  sind nur auf Code-Ebene änderbar (siehe „Bekannte Einschränkungen“).
- **Die Hofladen-Daten:** Hofläden, ihre Stammdaten, Öffnungszeiten und
  ihr Sortiment werden **nicht** über die Home-Assistant-Konfiguration
  gepflegt, sondern über die grafische Verwaltungsoberfläche (siehe
  nächster Abschnitt) bzw. programmatisch über den Coordinator.

## Grafische Hofladenverwaltung

**Architekturentscheid:** Der ursprüngliche Umsetzungsplan sah für
Suche/Filter/Actions ohne eigene UI vor („Keine proprietäre REST-API“,
„Keine eigene UI“). Für HofKarte wurde davon bewusst abgewichen: Da Home
Assistant sowohl Laufzeit- als auch Verwaltungsoberfläche ist, wird die
Pflege der Hofladen-Daten über ein **eigenes Sidebar-Panel** mit
WebSocket-Backend abgebildet statt ausschliesslich über
Home-Assistant-Actions.

Nach der Einrichtung steht im Home-Assistant-Seitenmenü die
Verwaltungsseite **HofKarte** zur Verfügung (nur für Administratoren
sichtbar).

**Übersicht (Kacheln oder Liste):** Ein Umschalter oberhalb der
Übersicht wechselt zwischen einer **Kachel-Ansicht** (Hauptbild oder
Platzhalter, Name, Adresse, anklickbare Webseite, Öffnungsstatus,
Karten-Button) und einer **sortierbaren Listen-/Tabellenansicht** (Name,
Adresse, Status – jede Spalte einzeln sortierbar, inkl. Freitextfilter
und Karten-Button je Zeile). In beiden Ansichten öffnet ein Klick auf
den Namen direkt die Detailansicht. Der Öffnungsstatus wird
serverseitig über dieselbe Funktion berechnet, die auch die Entity
„Geöffnet“ verwendet (`opening_hours.is_open`, siehe
`management.py`) – keine abweichende Berechnung im Browser.

Dort können Administratoren:

- neue Hofläden erstellen,
- bestehende Hofläden bearbeiten,
- Stammdaten und Koordinaten ändern (Koordinateneingabe als
  WGS84-Dezimalgrad, siehe unten),
- reguläre und Sonderöffnungszeiten bearbeiten (pro Wochentag:
  Geschlossen / 24 Stunden geöffnet / Zeiten festlegen, mit beliebig
  vielen Intervallen),
- Angebote (vormals getrennt: Kategorien/Produkte, seither zusätzlich
  auf eine schlichte Namensliste ohne Gruppierung vereinfacht) und
  Zahlungsarten bearbeiten,
- eine optionale Bemerkung erfassen (freies Textfeld, unabhängig von
  der Beschreibung),
- Hofläden kontrolliert löschen.

Zusätzlich gibt es eine **read-only Detailansicht** je Hofladen
(„Details“-Button in der Liste): zeigt alle Stammdaten, Adresse,
Standort/Koordinaten (inkl. Karten-Button), Öffnungszeiten, Sortiment
und Bilder kompakt und übersichtlich an, **ohne** editierbare Felder –
gedacht für den schnellen Überblick, getrennt von der Bearbeitung. Die
Gruppierung der Informationen (Allgemeines, Adresse, Standort, Kontakt,
Öffnungszeiten, ...) ist bewusst konsistent mit der Bearbeitungsansicht
gehalten, damit dieselben Informationen in beiden Ansichten
wiedererkennbar sind.

Änderungen werden direkt im integrationsinternen Home-Assistant-Storage
persistiert und ohne Neustart an Coordinator, Devices und Entities
weitergegeben. Die Verwaltungsoberfläche verwendet ausschliesslich
lokale Home-Assistant-Mechanismen (kein externer Dienst).

### Koordinaten (WGS84)

Die Verwaltungsoberfläche erfasst und zeigt Koordinaten als
**WGS84-Dezimalgrad** (Latitude/Longitude) – identisch zum
Speicherformat (`Hofladen.latitude`/`longitude`) und zu Home Assistants
eigener Standortangabe, daher **ohne jede Umrechnung**. Ein deutlich
sichtbarer, blau hinterlegter Infobutton (ⓘ) neben den Eingabefeldern
erklärt Latitude/Longitude kurz direkt im Formular – farblich/
gestalterisch konsistent zur restlichen Home-Assistant-Oberfläche
(nutzt die Home-Assistant-Theme-Farbe `--info-color`, passt sich damit
hellen wie dunklen Themes an).

**Standort auf Karte anzeigen:** Neben den Koordinaten steht in
„Bearbeiten“ **und** „Details“ ein Button „🗺️ Auf Google Maps anzeigen“
zur Verfügung, der den Standort anhand der gespeicherten
WGS84-Koordinaten in einem neuen Browser-Tab auf Google Maps öffnet.
Der Button ist deaktiviert, solange keine gültigen Koordinaten
hinterlegt sind. Beide Ansichten nutzen dieselbe Hilfsfunktion
(`mapButton`/`googleMapsUrl` in `hofkarte-panel.js`) für identisches
Verhalten. Öffnet nur eine externe, rein lesende Kartenansicht –
verändert keine Daten.

**Technischer Aufbau:** `frontend.py` registriert das Sidebar-Panel
sowie die statischen JS-Assets; `management.py` stellt dafür
WebSocket-Befehle bereit (`hofkarte/management/list|save|delete`,
require_admin-geschützt) und delegiert alle Schreibzugriffe an den
Coordinator (`async_save_hofladen`/`async_delete_hofladen`) – keine
eigene Datenhaltung neben dem Coordinator. Die Detailansicht benötigt
keinen eigenen Backend-Endpunkt: Sie zeigt read-only die über
`hofkarte/management/list` bereits geladenen Daten des jeweiligen
Hofladens an.

## Bereitgestellte Devices

Jeder Hofladen wird als logisches Device in der
Home-Assistant-Geräteverwaltung abgebildet
(`custom_components/hofkarte/device.py`) – **kein physisches Gerät**.

- Der Device-Identifier basiert ausschliesslich auf der stabilen
  Hofladen-ID und ändert sich nie zwischen Neustarts oder Reloads.
- Es werden bewusst **keine** Hersteller- oder Modell-Angaben gesetzt:
  Ein Hofladen hat fachlich weder Hersteller noch Modell.
- Die Device Registry wird beim Einrichten und bei jedem weiteren
  Coordinator-Update synchronisiert: neu hinzugekommene Hofläden
  erhalten ein Device, entfernte Hofläden verlieren ihres. Wiederholte
  Synchronisationen (z. B. bei einem Reload) erzeugen keine Duplikate.
- Mehrere Hofläden sind durch ihre eindeutigen Identifiers sauber
  voneinander getrennt.

## Bereitgestellte Entities

Für jeden Hofladen werden folgende Entities bereitgestellt (jeweils dem
zugehörigen Device zugeordnet, `unique_id` stabil aus der Hofladen-ID
gebildet):

| Plattform       | Entity                | Device Class | Attribute                     |
|------------------|------------------------|--------------|--------------------------------|
| `binary_sensor`  | Geöffnet               | –            | Sortiment & Eigenschaften (siehe unten) |
| `sensor`         | Nächste Öffnung        | `timestamp`  | –                              |
| `sensor`         | Nächste Schliessung    | `timestamp`  | –                              |
| `sensor`         | Entfernung             | `distance`   | –                              |
| `image`          | Hauptbild              | –            | Bilder (siehe unten)          |

Für den Binary Sensor wurde bewusst **keine** Device Class gesetzt: Es
gibt keine passende Home-Assistant-Device-Class für „Geschäft geöffnet“
(vorhandene Klassen wie `opening` beziehen sich auf physische Öffnungen
wie Türen/Fenster).

Neu über die Verwaltungsoberfläche hinzukommende Hofläden erhalten
automatisch alle fünf Entities, ohne dass ein Reload nötig ist. Entities
werden „unavailable“, sobald der letzte Coordinator-Abruf fehlgeschlagen
ist oder der Hofladen aus den Daten verschwunden ist.

### Öffnungsstatus

Die drei zeit-/öffnungsbezogenen Entities beziehen ihren Wert
ausschliesslich aus dem dafür vorgesehenen Modul
`custom_components/hofkarte/opening_hours.py`. Dieses Modul berechnet
den Öffnungsstatus deterministisch anhand der regulären Öffnungszeiten
und Sonderöffnungszeiten:

- Montag bis Sonntag, mehrere Intervalle pro Tag
- Sonderöffnungszeiten überschreiben reguläre Zeiten vollständig,
  inklusive Sonder-Schliessungen über einen Datumsbereich
- Mitternachtsüberschreitende Intervalle (z. B. 22:00–02:00)
- Wochenwechsel (z. B. ein Sonntagabend-Intervall, das in den Montag
  hineinreicht)
- Zeitzone des Home-Assistant-Systems (zeitzonenbewusste Berechnung
  statt naiver Datums-/Uhrzeit-Arithmetik)

Hat ein Hofladen überhaupt keine Öffnungszeiten hinterlegt, liefern die
Funktionen bewusst „unbekannt“ statt fälschlich „geschlossen“ zu
behaupten.

**Bekannte Grenze:** Bei Uhrzeiten, die exakt in eine
Sommerzeit-Umstellungslücke fallen oder im doppelt vorkommenden Bereich
beim Zurückstellen liegen, wird die von Python/`zoneinfo` standardmässig
gewählte Auflösung verwendet (keine explizite Disambiguierung für diese
seltenen Grenzfälle).

### Sortiment und Eigenschaften

**Architekturentscheid:** Die früher getrennten Fachbereiche
„Kategorien“ und „Produkte“ wurden zunächst zu einem gemeinsamen
Fachbereich „Angebote“ zusammengelegt und danach – nach weiterer
Vereinfachung – auf eine **schlichte Namensliste ohne Gruppierung**
reduziert: Ein Angebot ist heute nur noch ein Name (z. B.
„Kartoffeln“), ohne separate Kategorien-/Gruppen-Zuordnung. Ein
zwischenzeitlich eingeführtes Gruppen-Feld wurde wieder entfernt, da
der Mehrwert der Gruppierung den zusätzlichen Pflegeaufwand nicht
rechtfertigte. Bestehende, im alten Format gespeicherte Daten
(getrennte „Kategorien“/„Produkte“) werden beim Einlesen automatisch zu
flachen Angeboten migriert (siehe „Unter der Haube“ unten); ein
eventuell noch vorhandenes Gruppen-Feld wird dabei ignoriert.

**Ebenfalls entfernt:** Die früheren Fachbereiche „Verkaufsarten“ und
„Merkmale“ existieren nicht mehr. Bestehende Daten mit diesen Feldern
werden beim Einlesen weiterhin fehlerfrei verarbeitet, die Felder aber
nicht mehr angezeigt oder durchsucht.

Angebote und Zahlungsarten sind fachlich keine Messwerte und
rechtfertigen keine eigenen Sensoren. Sie werden daher als
Zusatzattribute **ausschliesslich** am Binary Sensor „Geöffnet“
bereitgestellt (`custom_components/hofkarte/attributes.py`). Diese
beiden Fachbereiche können pro Hofladen über die Verwaltungsseite
bearbeitet werden.

```yaml
angebote: ["Kartoffeln", "Honig"]
zahlungsarten: ["Bargeld", "TWINT"]
```

- Fehlende Sammlungen ergeben stets eine leere Liste, nie einen
  fehlenden Wert (stabile Struktur unabhängig vom
  Vollständigkeitsgrad der Daten).
- Namen werden für eine deterministische Darstellung sortiert
  (Unicode-Codepoint-Reihenfolge – **keine** lokalisierte deutsche
  Kollation; Umlaute landen dadurch nach „Z“ statt bei A/O/U
  einsortiert).
- Diese Attribute werden bewusst **nicht** auf die beiden
  Zeitpunkt-Sensoren dupliziert, um dieselben (teils umfangreichen)
  Daten nicht mehrfach über mehrere Entities hinweg zu wiederholen.

### Entfernung

Der Sensor „Entfernung“ zeigt die Luftlinien-Entfernung eines Hofladens
zur konfigurierten Home-Assistant-Position in Kilometern
(`custom_components/hofkarte/distance.py`), berechnet über die
Haversine-Formel. Zustand „unbekannt“, wenn der Hofladen keine
Koordinaten hinterlegt hat oder die Home-Assistant-Position nicht
bekannt ist – es wird kein Wert erfunden oder geschätzt (siehe
„Datenschutz- und Standort-Hinweise“ unten).

**Entfernung vom aktuellen Gerät:** Da eine Home-Assistant-Entity nur
**einen** Zustand für alle Betrachter:innen hat, kann der obige Sensor
nicht die Entfernung vom jeweils gerade verwendeten Gerät zeigen. In der
Detailansicht der Verwaltungsoberfläche steht dafür **zusätzlich** ein
Button „📍 Entfernung von diesem Gerät berechnen“ zur Verfügung, der
über die Browser-Geolocation-API rein clientseitig die Entfernung vom
aktuellen Gerät berechnet (dieselbe Haversine-Formel, in
`hofkarte-panel.js` dupliziert). Der Gerätestandort wird dabei
ausschliesslich lokal im Browser verwendet, nicht gespeichert und nicht
an das Backend übertragen.

**Wichtig – sichere Verbindung erforderlich:** Browser gewähren
Geolocation-Zugriff ausschliesslich in einem „sicheren Kontext“
(HTTPS oder `localhost`). Wird Home Assistant wie im Heimnetz üblich
über einfaches `http://` aufgerufen (z. B. `http://192.168.1.50:8123`),
zeigt der Button die Meldung „Standortermittlung erfordert eine sichere
Verbindung“ – das ist keine Fehlfunktion, sondern eine grundsätzliche
Browser-Einschränkung, die durch HofKarte nicht umgangen werden kann.

### Bilder

Jeder Hofladen zeigt sein Hauptbild über eine native
Home-Assistant-`image`-Entity (`custom_components/hofkarte/image.py`,
Sicherheitsprüfung in `images.py`):

- **Hauptbild:** das erste Bild mit einer sicheren, ladbaren URL.
  Reihenfolge der hinterlegten Bilder bestimmt die Priorität; über die
  Verwaltungsoberfläche lässt sich ein beliebiges Bild als Hauptbild
  festlegen (verschiebt es an den Anfang der Liste).
- **Weitere Bilder:** stehen als Zusatzattribut (`weitere_bilder`) an
  derselben Entity zur Verfügung, nicht als eigene Entities oder
  Galerie.
- **Geführter Upload:** In der Verwaltungsoberfläche kann ein Bild
  über einen dedizierten Button „📤 Bild hochladen“ direkt hochgeladen
  werden (Dateiauswahl, JPEG/PNG/GIF, max. 10 MB) – alternativ bleibt
  die manuelle Eingabe einer externen Bild-Adresse verfügbar.
  Hochgeladene Bilder werden über Home Assistants eigene
  `image_upload`-Komponente gespeichert und ausgeliefert (kein eigener
  Upload-Mechanismus). Wird ein hochgeladenes Bild entfernt, wird die
  zugrunde liegende Datei ebenfalls gelöscht.
- **Sicherheitsprüfung:** Nur `http`/`https`-URLs werden akzeptiert
  (kein `file://`, `data:`, keine rohen Dateisystempfade), keine
  eingebetteten Zugangsdaten. Bei frei eingegebenen externen Adressen
  wird zusätzlich jede literale private/interne IP-Adresse abgelehnt;
  diese Prüfung ist rein syntaktisch (keine DNS-Auflösung, um den
  Home-Assistant-Event-Loop nicht zu blockieren) – ein Domainname, der
  erst später auf eine private Adresse auflöst, wird dadurch nicht
  erkannt. Über den geführten Upload erzeugte Bilder sind von der
  IP-Adressbereichs-Prüfung ausgenommen (ihre Vertrauenswürdigkeit
  ergibt sich aus der Herkunft – von HofKarte selbst über den
  offiziellen Home-Assistant-Upload-Weg erzeugt – nicht aus dem
  Adressbereich; sie zeigen typischerweise auf die eigene, private
  Home-Assistant-Instanz und würden sonst fälschlich abgelehnt).
- **Fehlende/ungültige Bilder** werden robust behandelt (leeres
  Hauptbild statt Fehler).

## Actions/Services

Für Automationen, Skripte und Dashboards steht die Action
`hofkarte.hoflaeden_suchen` zur Verfügung
(`custom_components/hofkarte/services.py`, Fachlogik in `search.py`):

**Parameter** (alle optional, werden UND-verknüpft):

| Parameter        | Typ     | Bedeutung                                              |
|-------------------|---------|----------------------------------------------------------|
| `suchbegriff`     | Text    | Freitextsuche (Gross-/Kleinschreibung egal) über Name, Beschreibung, Ort |
| `angebot`         | Text    | Exakter Name eines Angebots                              |
| `zahlungsart`     | Text    | Exakter Name einer Zahlungsart                            |
| `nur_geoeffnet`   | Bool    | Nur aktuell geöffnete Hofläden                            |

**Rückgabedaten** (`response_variable` in Skripten/Automationen
nutzbar):

```yaml
anzahl_treffer: 1
hoflaeden:
  - id: hof-mueller
    name: Hofladen Müller
    geoeffnet: true
```

- Filter (`angebot`, …) verlangen exakte Übereinstimmung
  (case-insensitive); der `suchbegriff` erlaubt Teilstring-Treffer.
- Ein Hofladen ohne bekannten Öffnungsstatus gilt bei
  `nur_geoeffnet: true` **nicht** als Treffer.
- Rückgabedaten sind bewusst knapp gehalten (ID, Name, Öffnungsstatus)
  statt einer vollständigen Kopie aller Hofladen-Felder.

**Bewusst nicht implementiert:** eine „Daten aktualisieren“-Action
(deckt Home Assistants eingebaute Action `homeassistant.update_entity`
bereits ab), separate Actions je Filterdimension, sowie eine
proprietäre REST-API oder eine Suche über andere Integrationen hinweg.

## Beispiele für Automationen

**Benachrichtigung, wenn ein Lieblings-Hofladen öffnet:**

```yaml
alias: "Hofladen Müller ist offen"
trigger:
  - trigger: state
    entity_id: binary_sensor.hofladen_mueller_geoeffnet
    to: "on"
action:
  - action: notify.mobile_app
    data:
      message: "Hofladen Müller hat gerade geöffnet."
```

**Abendliche Ansage geöffneter Hofläden mit Kartoffeln in der Nähe:**

```yaml
alias: "Kartoffel-Hofläden Abendübersicht"
trigger:
  - trigger: time
    at: "17:30:00"
action:
  - action: hofkarte.hoflaeden_suchen
    data:
      angebot: Kartoffeln
      nur_geoeffnet: true
    response_variable: treffer
  - action: notify.mobile_app
    data:
      message: >-
        {% if treffer.anzahl_treffer > 0 %}
          {{ treffer.anzahl_treffer }} Hofladen/-läden mit Kartoffeln noch geöffnet:
          {{ treffer.hoflaeden | map(attribute='name') | join(', ') }}
        {% else %}
          Aktuell ist kein Hofladen mit Kartoffeln geöffnet.
        {% endif %}
```

**Dashboard-Karte für einen Hofladen** (Beispiel, nicht Teil der
Integration): Da `image`-Entities in Lovelace-Bildkarten funktionieren,
kann eine Picture-Entity-Karte direkt `image.hofladen_mueller_hauptbild`
verwenden.

## Unter der Haube (technische Referenz)

Dieser Abschnitt richtet sich an technisch interessierte
Nutzer:innen/Entwickler:innen und ist für den normalen Betrieb nicht
nötig.

### Internes Datenmodell

Intern verwaltet HofKarte einen Hofladen als typisierte, unveränderliche
Datenstruktur (`custom_components/hofkarte/models.py`) mit u. a.
Stammdaten (Name, Beschreibung, Bemerkung, Adresse, PLZ/Ort, Land,
Koordinaten, Webseite), regelmässigen Öffnungszeiten und
datumsbezogenen Sonderöffnungszeiten, Angeboten/Zahlungsarten sowie
optionalen Bildern. Rohdaten werden über
`custom_components/hofkarte/parsing.py` in dieses Modell überführt und
dabei validiert (`HofladenValidationError` bei ungültigen
Pflichtfeldern; fehlende optionale Felder werden robust auf leere
Werte abgebildet). Im alten Format (getrennte `kategorien`/`produkte`)
gespeicherte Daten werden dabei automatisch und verlustfrei in die
einheitliche `angebote`-Struktur migriert (siehe Abschnitt „Sortiment
und Eigenschaften“).

Für Öffnungszeiten und Sonderöffnungszeiten gilt: Ende gleich Beginn ist
ungültig; Ende **vor** Beginn ist hingegen gültig und bedeutet ein
Intervall, das die Mitternacht überschreitet (z. B. 22:00–02:00).

### Datenabruf (Coordinator)

Ein zentraler `HofKarteUpdateCoordinator`
(`custom_components/hofkarte/coordinator.py`) ruft die Hofladen-Rohdaten
asynchron ab, validiert sie und stellt das Ergebnis für die gesamte
Integration bereit. Alle Entities lesen ausschliesslich aus dem
Coordinator – es gibt keine Mehrfachabfragen pro Entity.

- Asynchroner Abruf mit konfigurierbarem Timeout (Standard: 30 Sekunden)
- Konfigurierbares Update-Intervall (Standard: 15 Minuten)
- Initialer Datenabruf beim Einrichten der Config Entry; schlägt dieser
  fehl, versucht Home Assistant die Einrichtung automatisch später
  erneut
- Einzelne ungültige Datensätze werden übersprungen und geloggt, statt
  den gesamten Abruf scheitern zu lassen
- Bei einem späteren Fehlversuch bleiben die zuletzt erfolgreich
  abgerufenen Daten erhalten

### Data Provider und Architekturentscheid zur Datenquelle

**Architekturentscheid:** Die vom Benutzer gepflegten Hofläden werden in
einem integrationsinternen, persistenten Store gehalten – keine externe
Datenbank, kein externer Dienst. Der `HofladenDataProvider` kapselt
diesen Store vollständig; Coordinator und Entities greifen
ausschliesslich über diese Abstraktion darauf zu.

- **`StorageHofladenDataProvider`** (produktiv): kapselt Home
  Assistants `helpers.storage.Store` (JSON-Datei unter `.storage/` im
  Konfigurationsverzeichnis). Startet leer; Hofläden werden vollständig
  über die Verwaltungsoberfläche gepflegt. Daten überstehen Neustarts
  und Reloads.
- **`StaticTestDataProvider`**: reiner In-Memory-Provider ausschliesslich
  für die Testsuite (keine Persistenz).

Für programmatischen Zugriff (z. B. eigene Skripte) stehen
`HofKarteUpdateCoordinator.async_add_hofladen`,
`async_update_hofladen_sortiment`, `async_save_hofladen` und
`async_delete_hofladen` zur Verfügung; alle validieren Fail-Fast und
lösen danach einen Refresh aus. `custom_components/hofkarte/sortiment_katalog.py`
bietet ausserdem vorgefertigte, gültige Rohdaten für gängige
Zahlungsarten (Bargeld/Debitkarte/Kreditkarte/TWINT) – ein
Vorschlagskatalog, keine Einschränkung. Für „Angebote“ gibt es bewusst
keinen Vorschlagskatalog, da es sich um frei formulierte Produktnamen
ohne sinnvolle Standardwerte handelt.

## Diagnostics, Fehlerbehandlung und Qualität

### Diagnostics

Über **Einstellungen → Geräte & Dienste → HofKarte → Diagnose
herunterladen** steht eine technische Übersicht zur Fehlersuche zur
Verfügung (`custom_components/hofkarte/diagnostics.py`): Status des
letzten Datenabrufs, Zeitpunkt der letzten erfolgreichen
Aktualisierung, konfiguriertes Update-Intervall, Typ des Data Providers
und dessen Schreibfähigkeit sowie die Anzahl verwalteter Hofläden.

**Bewusst nicht enthalten:** Hofladen-Inhalte (Namen, Adressen,
Koordinaten, Bild-URLs) sowie die Home-Assistant-Standortdaten. Auch
wenn diese Daten fachlich nicht „geheim“ sind, handelt es sich um
nutzerspezifische Daten, die in einer zur Fehlersuche geteilten und
damit potenziell öffentlich einsehbaren Diagnosedatei nichts verloren
haben.

### Fehlerbehandlung

- **Netzwerk-/Datenquellenfehler und Timeouts:** werden im Coordinator
  sauber abgefangen; Home Assistant zeigt betroffene Entities als
  „unavailable“ an und versucht es beim nächsten Intervall erneut.
- **Ungültige/fehlende Pflichtfelder:** einzelne ungültige
  Hofladen-Datensätze werden übersprungen und geloggt, statt den
  gesamten Abruf abzubrechen.
- **Config-Entry-Fehler:** Schlägt der initiale Datenabruf beim
  Einrichten fehl, löst Home Assistant automatisch eine
  Wiederholung aus.
- **Reload/Unload:** mehrfache Reloads erzeugen keine doppelten Devices
  oder Entities; das Sidebar-Panel wird beim Entladen korrekt entfernt.
- **Verwaltungsoberfläche:** unterscheidet Fehler klar (nicht
  eingerichtet, ungültige Daten, nicht unterstützt, unbekannte ID).

### Performance

- Ein gemeinsamer Coordinator verhindert Mehrfachabfragen einzelner
  Entities.
- Update-Intervall 15 Minuten – für Öffnungszeiten-Aktualität
  angemessen, ohne unnötige Last zu erzeugen.
- Keine blockierenden Aufrufe (auch die Bild-URL-Sicherheitsprüfung ist
  bewusst rein syntaktisch, siehe oben).

## Fehlerbehebung

**Die Integration erscheint nicht in „Integration hinzufügen“:**
Home Assistant neu starten; bei manueller Installation den Pfad
`custom_components/hofkarte/` prüfen.

**„HofKarte ist bereits eingerichtet“ beim erneuten Hinzufügen:**
Erwartetes Verhalten – HofKarte ist eine Single-Instance-Integration
(siehe „Einrichtung“). Die bestehende Instanz unter **Einstellungen →
Geräte & Dienste** verwenden.

**Das Verwaltungs-Panel erscheint nicht im Seitenmenü:** Nur
Administratoren sehen das Panel. Home Assistant neu laden
(Browser-Cache leeren, falls das Panel nach einem Update von HofKarte
nicht aktualisiert erscheint).

**Entity „Geöffnet“ zeigt dauerhaft „unbekannt“:** Für den Hofladen sind
keine Öffnungszeiten hinterlegt. Über die Verwaltungsoberfläche
reguläre Öffnungszeiten ergänzen.

**Sensor „Entfernung“ zeigt „unbekannt“:** Entweder fehlen dem Hofladen
Koordinaten, oder die Home-Assistant-Position ist nicht sinnvoll
konfiguriert (**Einstellungen → System → Allgemein**).

**Hauptbild wird nicht angezeigt:** Bei hochgeladenen Bildern: prüfen,
ob die Datei erfolgreich hochgeladen wurde (Fehlermeldung im
Upload-Bereich der Verwaltungsoberfläche). Bei extern verlinkten
Bildern: Die hinterlegte Bild-Adresse ist entweder leer, kein
`http(s)`-Link, oder zeigt auf eine private/interne IP-Adresse (wird
bei manuell eingegebenen Adressen aus Sicherheitsgründen abgelehnt,
siehe Abschnitt „Bilder“) – Adresse in der Verwaltungsoberfläche
prüfen.

**Diagnose zur Fehlersuche:** Unter **Einstellungen → Geräte & Dienste →
HofKarte → Diagnose herunterladen** steht eine technische Übersicht zur
Verfügung (siehe oben). Für tiefergehende Logs das Logging für
`custom_components.hofkarte` in **Einstellungen → System → Logs** auf
„Debug“ stellen.

**Fehler melden:** über den Issue-Tracker des Repositories
(`manifest.json` → `issue_tracker`).

## Bekannte Einschränkungen

- Nur eine Instanz pro Home-Assistant-Installation möglich (Single
  Instance).
- Kein Options Flow; Update-Intervall und Timeout des Coordinators sind
  aktuell nur auf Code-Ebene konfigurierbar.
- Bei Uhrzeiten in einer Sommerzeit-Umstellungslücke bzw. im doppelt
  vorkommenden Bereich beim Zurückstellen wird die von `zoneinfo`
  standardmässig gewählte Auflösung verwendet, ohne explizite
  Disambiguierung.
- Verschwindet ein Hofladen dauerhaft aus den Daten, wird sein Device
  entfernt, seine Entities bleiben jedoch als „unavailable“ in der
  Entity Registry bestehen, statt automatisch entfernt zu werden.
- Der Entfernungs-Sensor behandelt das Standardpaar `0.0/0.0` einer
  frischen, noch nicht sinnvoll konfigurierten Installation als
  unbekannte Position; einzelne Koordinaten `0.0` bleiben gültig.
- Die Action `hofkarte.hoflaeden_suchen` filtert case-insensitiv aber
  exakt (kein Fuzzy-Matching, keine Tippfehler-Toleranz) – ausser beim
  Freitext-`suchbegriff`, der Teilstrings erlaubt.
- Die Bild-URL-Sicherheitsprüfung ist rein syntaktisch (keine
  DNS-Auflösung); ein Domainname, der erst später auf eine private
  Adresse auflöst, wird nicht erkannt.
- Keine eigene SQL-Datenbank – Persistenz erfolgt über Home Assistants
  `helpers.storage.Store` (JSON-Datei unter `.storage/`).

## Datenschutz- und Standort-Hinweise

- **Keine Cloud, kein externer Dienst:** HofKarte kommuniziert nicht mit
  externen Servern (ausser dem Laden von Hofladen-Bildern über die vom
  Benutzer hinterlegten Bild-URLs, siehe „Bilder“). Es findet keine
  Telemetrie und keine Datenübertragung an Dritte statt.
- **Standort (Home-Assistant-Server):** Der Entfernungs-Sensor liest
  ausschliesslich die statische, in Home Assistant konfigurierte
  Position (`hass.config.latitude`/`longitude`) – kein `device_tracker`,
  keine Personen- oder Geräteverfolgung. Diese Position wird von
  HofKarte nicht gespeichert und nicht an externe Dienste übertragen;
  die Berechnung erfolgt vollständig lokal.
- **Standort (aktuelles Gerät):** Der optionale Button „Entfernung von
  diesem Gerät berechnen“ in der Detailansicht nutzt die
  Browser-Geolocation-API nur nach expliziter Zustimmung im Browser.
  Der Gerätestandort wird ausschliesslich im Browser für die einmalige
  Berechnung verwendet, nirgends gespeichert und **nicht** an das
  Home-Assistant-Backend übertragen.
- **Persistenz:** Alle Hofladen-Daten liegen ausschliesslich lokal im
  Home-Assistant-Storage (`.storage/`-Verzeichnis der
  Konfiguration) – keine Cloud-Synchronisation.
- **Diagnostics:** Die herunterladbare Diagnose enthält bewusst keine
  Hofladen-Inhalte und keine Standortdaten (siehe oben).
- **Bilder:** Extern eingegebene Bild-Adressen werden vor der Nutzung
  auf ein sicheres Format geprüft (siehe „Bilder“); dennoch lädt Home
  Assistant beim Anzeigen eines Hauptbilds das Bild von der
  hinterlegten externen Adresse – wer externe Bild-Adressen pflegt,
  sollte nur vertrauenswürdige Quellen verwenden. Hochgeladene Bilder
  werden lokal über Home Assistants eigene `image_upload`-Komponente
  gespeichert (keine externe Übertragung) und beim Entfernen wieder
  gelöscht.

## Entwicklung

### Tests ausführen

```bash
pip install -r requirements_test.txt
pytest custom_components/hofkarte/tests
```

### Release-Prozess und Versionierung

- **Versionierung folgt dem Schema von Home Assistant selbst:**
  `JAHR.MONAT.LAUFNUMMER` (z. B. `2026.9.0` = erste Veröffentlichung im
  September 2026, `2026.9.1` = zweite Veröffentlichung im selben Monat).
  Kein Semantic Versioning (`MAJOR.MINOR.PATCH`) – die drei Zahlen
  haben hier eine andere Bedeutung. Siehe `manifest.json` → `version`.
- Ein Release besteht aus: `manifest.json`-Version erhöhen,
  `CHANGELOG.md` mit den nutzerrelevanten Änderungen ergänzen, Commit,
  und ein GitHub Release mit **exakt demselben Versions-String** als
  Tag erstellen (z. B. `2026.9.0`). HACS erkennt neue Versionen über die
  GitHub-Releases-API.
- `hacs.json` deklariert die minimal unterstützte Home-Assistant-Version
  (`homeassistant`). Diese sollte bei Verwendung neuerer
  Home-Assistant-APIs entsprechend angehoben werden.

### Quality Scale

`custom_components/hofkarte/quality_scale.yaml` enthält eine ehrliche
Selbsteinschätzung gegen die Home-Assistant-Integration-Quality-Scale
(Bronze/Silber/Gold/Platin). Nicht erfüllte Kriterien sind mit
Begründung dokumentiert statt stillschweigend übersprungen oder
vorgetäuscht.

### Weiterführende Dokumentation

- [`docs/handbuch.md`](docs/handbuch.md) – vollständiges
  Anwendungshandbuch für Endanwender:innen.
- [`docs/architecture.md`](docs/architecture.md) – Architekturüberblick
  für Entwickler:innen und Beitragende.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) – Entwicklungsumgebung, Tests,
  Pull-Request-Ablauf.
- [`SECURITY.md`](SECURITY.md) – Meldeweg für Sicherheitsprobleme.

## Lizenz

Dieses Projekt steht unter der [MIT-Lizenz](LICENSE).

## Support

Fragen und Fehlermeldungen bitte über den [Issue-Tracker des
Repositories](https://github.com/rest-be/HofKarte/issues) einreichen –
siehe [`docs/handbuch.md`, Kapitel 15](docs/handbuch.md#15-support) für
Details, welche Angaben dabei hilfreich sind. Sicherheitsrelevante
Probleme bitte **nicht** öffentlich melden, sondern über den in
[`SECURITY.md`](SECURITY.md) beschriebenen privaten Meldeweg.

Dies ist ein privates Freizeitprojekt ohne kommerzielle
Support-Garantie (siehe `SECURITY.md`).
