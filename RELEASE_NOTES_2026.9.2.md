# HofKarte 2026.9.2

Dieses Release macht „Angaben automatisch ermitteln“ deutlich
mächtiger (jetzt auch mit OpenStreetMap-Suche, Kontaktdaten und
einstellbarem Suchradius), bringt Kontaktfelder und eine
Sterne-Bewertung für eure Hofläden, eine neue „Einstellungen“-Maske
mit dauerhaft gespeicherten Vorgaben sowie eingefärbte Kartenmarker.
Ein Update wird allen Nutzer:innen empfohlen.

## Neu

- **Angaben automatisch ermitteln – jetzt aus zwei Quellen
  gleichzeitig:** Die bisherige Funktion „Infos ermitteln“ (aus der
  hinterlegten Website) und die neue Suche „Ort in der Nähe“ über
  OpenStreetMap wurden zu einer einzigen Aktion „🔍 Angaben automatisch
  ermitteln“ zusammengelegt. Sind eine Website-Adresse **und** gültige
  Koordinaten eingetragen, werden beide Quellen gleichzeitig
  abgefragt und zu einem gemeinsamen Vorschlag zusammengeführt – ihr
  seht dabei immer, aus welcher Quelle welche Angabe stammt. Der
  Suchradius für die OpenStreetMap-Suche lässt sich direkt im
  Formular anpassen; findet OpenStreetMap mehrere mögliche Orte in der
  Nähe, wählt ihr aus einer übersichtlichen Liste aus. Wie bisher wird
  dabei **nichts automatisch gespeichert** – jeder Vorschlag muss
  ausdrücklich über „Übernehmen“ bestätigt werden.
- **Kontaktdaten je Hofladen:** Mobilnummer und E-Mail lassen sich
  jetzt direkt am Hofladen hinterlegen. In der Detailansicht
  erscheinen sie als anklickbare Links, die direkt die Telefon-App
  bzw. euer Mailprogramm öffnen. Auch „Angaben automatisch ermitteln“
  findet diese Angaben jetzt mit, sofern sie auf der Website oder bei
  OpenStreetMap hinterlegt sind.
- **Bewertung mit 0–5 Sternen:** Jeder Hofladen lässt sich jetzt mit
  einer Sterne-Bewertung versehen – bequem per Klick im
  Bearbeitungsformular. Die Bewertung erscheint als zusätzliche,
  sortierbare Spalte in der Listenansicht, kompakt in der Kachelansicht
  und steht ausserdem als eigener Sensor zur Verfügung, den ihr z. B.
  in eigenen Dashboards oder Automationen nutzen könnt.
- **Neue „Einstellungen“-Maske:** Über „Konfigurieren“ bei der
  HofKarte-Integration lassen sich jetzt zwei Dinge dauerhaft
  vorgeben: nach welcher Spalte und Richtung die Hofladen-Übersicht
  standardmässig sortiert sein soll, sowie ein Standard-Suchradius für
  „Angaben automatisch ermitteln“ (neu wählbar zwischen 20 und
  2000 Metern, voreingestellt 200 Meter).
- **Eingefärbte Kartenmarker:** In der eingebetteten Kartenansicht sind
  die Stecknadeln jetzt grün eingefärbt, wenn der jeweilige Hofladen
  gerade geöffnet hat, und grau, wenn er geschlossen ist – auf einen
  Blick erkennbar, ohne erst jede Stecknadel einzeln anklicken zu
  müssen.

## Verbessert

- **Zuverlässigere OpenStreetMap-Suche:** Findet HofKarte über die
  Haupt-Overpass-Instanz keine Verbindung (z. B. weil diese gerade
  überlastet ist), wird automatisch eine von mehreren bekannten,
  freien Ausweich-Instanzen versucht, bevor eine Fehlermeldung
  erscheint. Ausserdem werden jetzt auch Orte gefunden, die auf
  OpenStreetMap zwar nicht als Laden getaggt sind, deren Name aber
  eindeutig auf einen Hofladen hindeutet (z. B. „Hof“, „Bauernhof“,
  „Hofladen“) – solche Treffer sind in der Auswahl klar entsprechend
  gekennzeichnet.

## Behoben

- **Datenverlust im Bearbeitungsformular:** Ein Klick auf „Infos
  ermitteln“ (bzw. jetzt „Angaben automatisch ermitteln“) konnte zuvor
  dazu führen, dass bereits eingetragene, aber noch nicht gespeicherte
  Formularwerte verschwanden – unabhängig davon, ob die Ermittlung
  erfolgreich war. Das ist behoben: eure Eingaben bleiben jetzt in
  jedem Fall erhalten, bis ihr bewusst speichert.
