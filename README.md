# HofKarte

Private, lokal betriebene Home-Assistant-Custom-Integration zur Verwaltung
und Darstellung von Hofläden.

> **Status:** Fachliches Datenmodell und Data Layer (Einheit 3). Die
> Integration besitzt eine typisierte, interne Darstellung eines Hofladens
> inkl. Parsing/Validierung. Es gibt noch keine Persistenz, keinen
> Coordinator und keine Entities. Diese Funktionen folgen in den nächsten
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

## Bekannte Einschränkungen (Stand dieser Einheit)

- Nur eine Instanz pro Home-Assistant-Installation möglich (Single Instance).
- Kein Options Flow (folgt erst, sobald eine sinnvolle Option existiert).
- Das interne Datenmodell existiert, ist aber noch an keine Datenquelle
  angebunden – es gibt noch keinen Coordinator und keine Sensoren.
- Die konkrete Datenquelle für Hofläden (z. B. lokale Verwaltung durch die
  Nutzerin/den Nutzer vs. externer Dienst) ist noch nicht festgelegt und
  eine offene Architekturentscheidung für eine der nächsten Einheiten.
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
