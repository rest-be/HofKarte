# HofKarte 2026.9.1

Dieses Release bringt drei neue Ansichten für die Hofladen-Übersicht,
Export/Import eurer Hofladen-Daten, eine praktische Routenführung zu
jedem Hofladen sowie mehrere Fehlerbehebungen. Ein Update wird allen
Nutzer:innen empfohlen.

## Neu

- **Kacheln, Liste oder Karte – wählt eure bevorzugte Übersicht:** Die
  Hofladen-Übersicht bietet jetzt einen Umschalter zwischen einer
  Kachelansicht mit Bildern, einer sortier- und filterbaren
  Tabellenansicht sowie einer eingebetteten Karte, die alle Hofläden
  mit hinterlegten Koordinaten gleichzeitig als Stecknadeln anzeigt.
  In der Kartenansicht lässt sich zudem nach aktuell geöffneten
  Hofläden filtern.
- **Hofläden exportieren und importieren:** Einzelne Hofläden lassen
  sich per Checkbox auswählen und als Datei sichern oder weitergeben.
  Eine solche Datei lässt sich anschliessend wieder einlesen; erkennt
  HofKarte dabei einen möglichen Duplikat-Eintrag, werden euch die
  Unterschiede übersichtlich zur Entscheidung vorgelegt – ohne eure
  Entscheidung geht kein bestehender Eintrag verloren.
- **Route zum Hofladen öffnen:** Statt eines einfachen Kartenlinks
  steht in Kacheln-, Listen- und Detailansicht jetzt eine kompakte
  Auswahl bereit, die eine echte Wegbeschreibung zum Hofladen in
  Google Maps oder Apple Maps öffnet – ausgehend von eurem aktuellen
  Standort.

## Entfernt

- Die bisherige Funktion „Entfernung von diesem Gerät berechnen“ wurde
  entfernt. Die Entfernung zu eurer in Home Assistant konfigurierten
  Position steht weiterhin ganz normal als Sensor zur Verfügung.

## Behoben

- Nach einem Update auf eine neuere HofKarte-Version zeigte das
  Verwaltungs-Panel im Browser mitunter noch den alten Funktionsstand
  an, bis die Seite manuell neu geladen wurde. Das Panel lädt jetzt
  bei jedem Versionswechsel zuverlässig die aktuelle Fassung.
- In der Kartenansicht wurde der Standort-Marker teilweise als
  defektes Bild-Icon ("?") statt als richtiges Symbol dargestellt.
  Marker zeigen jetzt zuverlässig ein passendes Icon.
- Beim mehrfachen Hinzufügen weiterer Öffnungszeiten-Zeitfenster über
  den Button „+ weiteres Intervall“ konnten sich Zeilen verdoppeln,
  und beim Speichern entstanden dabei gelegentlich versehentlich
  mehrere, inhaltlich identische Hofladen-Einträge. Beides ist behoben.

## Installation/Update

Über HACS aktualisieren, oder die Installationsanleitung im
[Anwendungshandbuch](docs/handbuch.md) befolgen. Nach dem Update kann
– einmalig, für dieses Release – ein hartes Neuladen der
Verwaltungsseite im Browser nötig sein, damit die aktualisierte
Verwaltungsoberfläche zuverlässig geladen wird.

Die vollständige, technische Änderungshistorie steht im
[CHANGELOG](CHANGELOG.md).
