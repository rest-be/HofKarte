# HofKarte

Private, lokal betriebene Home-Assistant-Custom-Integration zur Verwaltung
und Darstellung von Hofläden.

> **Status:** DataUpdateCoordinator und Datenabruf (Einheit 4). Die
> Integration führt beim Einrichten und danach periodisch einen zentralen,
> asynchronen Datenabruf durch. Die tatsächliche Datenquelle steht noch
> nicht fest; es wird ein Testdaten-Provider verwendet (siehe unten). Es
> gibt noch keine Entities. Diese Funktion folgt in einer der nächsten
> Entwicklungseinheiten.

## Über dieses Projekt

Home Assistant ist die Laufzeitumgebung. Es gibt keine eigenständige
Webanwendung, kein eigenes Backend und keine eigene Datenbank. Die
Integration nutzt ausschliesslich Home-Assistant-eigene Mechanismen
(Config Flow, ConfigEntry, DataUpdateCoordinator, Device- und Entity-Registry).

## Installation über HACS

1. HACS öffnen.
2. Über die Drei-Punkte-Menü-Schaltfläche **Benutzerdefinierte Repositories**
   auswählen.
3. Dieses Repository als **Integration** hinzufügen.
4. "HofKarte" in HACS suchen und installieren.
5. Home Assistant neu starten.

*Hinweis: Solange dieses Projekt nicht im HACS-Default-Store gelistet ist,
ist Schritt 2–3 (benutzerdefiniertes Repository) erforderlich.*

## Manuelle Installation (Entwicklung)

1. Den Ordner `custom_components/hofkarte/` in das
   `custom_components`-Verzeichnis der Home-Assistant-Konfiguration kopieren.
2. Home Assistant neu starten.
3. Prüfen, dass beim Start keine Fehler zur Domain `hofkarte` im Log
   erscheinen (siehe Abschnitt „Prüfanleitung“ unten).

## Einrichtung

Nach der Installation:

1. In Home Assistant zu **Einstellungen → Geräte & Dienste** wechseln.
2. **Integration hinzufügen** wählen und nach „HofKarte“ suchen.
3. Im Einrichtungsdialog einen Anzeigenamen für die Integration vergeben
   (z. B. „HofKarte“) und bestätigen.

HofKarte ist als Single-Instance-Integration konzipiert: Es kann nur eine
Instanz pro Home-Assistant-Installation eingerichtet werden, da sie eine
zentrale, HA-weite Hofladen-Verwaltung darstellt. Ein erneuter
Einrichtungsversuch wird entsprechend abgelehnt.

## Entitäten

In dieser Einheit werden keine Entitäten bereitgestellt. Die Integration
lädt lediglich als leeres Grundgerüst.

## Internes Datenmodell

Intern verwaltet HofKarte einen Hofladen als typisierte, unveränderliche
Datenstruktur (`custom_components/hofkarte/models.py`) mit u. a.:

- Stammdaten (ID, Name, Beschreibung, Adresse, PLZ, Ort, Land, Koordinaten)
- regelmässigen Öffnungszeiten und datumsbezogenen Sonderöffnungszeiten
- Produkten, Kategorien, Zahlungsarten, Verkaufsarten und Merkmalen
- optionalen Bildern

Rohdaten (z. B. künftig aus einer lokalen Datenquelle) werden über
`custom_components/hofkarte/parsing.py` in dieses Modell überführt und
dabei validiert. Ungültige oder unvollständige Pflichtfelder führen zu
einer klaren Fehlermeldung (`HofladenValidationError`); fehlende optionale
Felder werden robust auf `None` bzw. leere Sammlungen abgebildet.

Dieses Datenmodell ist rein intern und noch nicht an eine konkrete
Datenquelle, einen Coordinator oder Home-Assistant-Entities angebunden.

## Datenabruf (Coordinator)

Ein zentraler `HofKarteUpdateCoordinator`
(`custom_components/hofkarte/coordinator.py`) ruft die Hofladen-Rohdaten
asynchron ab, validiert sie über `parsing.parse_hofladen` und stellt das
Ergebnis als `dict[str, Hofladen]` für die gesamte Integration bereit.
Künftige Entities lesen ausschliesslich aus dem Coordinator – es gibt
keine Mehrfachabfragen pro Entity.

Eigenschaften:

- Asynchroner Abruf mit konfigurierbarem Timeout (Standard: 30 Sekunden)
- Konfigurierbares Update-Intervall (Standard: 15 Minuten)
- Initialer Datenabruf beim Einrichten der Config Entry; schlägt dieser
  fehl, versucht Home Assistant die Einrichtung automatisch später erneut
  (`ConfigEntryNotReady`)
- Einzelne ungültige Datensätze werden übersprungen und geloggt, statt den
  gesamten Abruf scheitern zu lassen
- Bei einem späteren Fehlversuch bleiben die zuletzt erfolgreich
  abgerufenen Daten erhalten; `coordinator.last_update_success` zeigt die
  Verfügbarkeit an

### Data Provider (offene Architekturentscheidung)

Die tatsächliche Datenquelle für Hofladen-Daten steht weiterhin nicht
fest. Um den Coordinator dennoch sinnvoll umzusetzen, kapselt
`custom_components/hofkarte/data_provider.py` eine klar abgegrenzte
Provider-Schnittstelle (`HofladenDataProvider`) sowie eine
Testdaten-Implementierung (`StaticTestDataProvider`) ohne externe
Anbindung. Sobald die Datenquelle feststeht, wird eine neue
Provider-Implementierung ergänzt; Coordinator und übrige Integration
bleiben davon unberührt.

## Bekannte Einschränkungen (Stand dieser Einheit)

- Nur eine Instanz pro Home-Assistant-Installation möglich (Single Instance).
- Kein Options Flow (folgt erst, sobald eine sinnvolle Option existiert).
  Update-Intervall und Timeout des Coordinators sind aktuell nur auf
  Code-Ebene konfigurierbar (Konstruktorparameter), nicht über die
  Home-Assistant-Oberfläche.
- Es wird ein Testdaten-Provider ohne echte Hofladen-Daten verwendet – die
  konkrete Datenquelle für Hofläden ist weiterhin nicht festgelegt und
  eine offene Architekturentscheidung.
- Noch keine Home-Assistant-Entities (Sensoren, Devices).
- Keine eigene SQL-Datenbank und keine Persistenz in dieser Einheit.
- Keine HACS-Veröffentlichung/Release im Detail vorbereitet.

## Entwicklung

### Tests ausführen

```bash
pip install -r requirements_test.txt
pytest custom_components/hofkarte/tests
```

## Lizenz

Dieses Projekt steht unter der [MIT-Lizenz](LICENSE).
