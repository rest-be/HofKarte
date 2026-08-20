# HofKarte

Private, lokal betriebene Home-Assistant-Custom-Integration zur Verwaltung
und Darstellung von Hofläden.

> **Status:** Grundgerüst (Einheit 1). Es gibt noch keinen Config Flow, keine
> Entities und keine Fachlogik. Diese Funktionen folgen in den nächsten
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

## Entitäten

In dieser Einheit werden keine Entitäten bereitgestellt. Die Integration
lädt lediglich als leeres Grundgerüst.

## Bekannte Einschränkungen (Stand dieser Einheit)

- Kein Config Flow (folgt in Einheit 2).
- Keine Hofladen-Daten, kein Coordinator, keine Sensoren.
- Keine HACS-Veröffentlichung/Release im Detail vorbereitet.
- `manifest.json` enthält Platzhalter für `codeowners`,
  `documentation` und `issue_tracker`, die vor einer echten
  Veröffentlichung durch die tatsächliche GitHub-Organisation/Benutzer
  ersetzt werden müssen.

## Entwicklung

### Tests ausführen

```bash
pip install -r requirements_test.txt
pytest custom_components/hofkarte/tests
```

## Lizenz

Dieses Projekt steht unter der [MIT-Lizenz](LICENSE).
