# Security Policy

## Über dieses Projekt

HofKarte ist ein **privates, lokal betriebenes** Home-Assistant-Custom-Integrationsprojekt.
Es gibt kein kommerzielles Support-Team und keinen 24/7-Sicherheitsdienst –
Rückmeldungen erfolgen nach bestem Aufwand durch den/die Projektbetreuer:in
(siehe `codeowners` in `custom_components/hofkarte/manifest.json`).

## Unterstützte Versionen

Es wird ausschliesslich die **jeweils neueste veröffentlichte Version**
(siehe `CHANGELOG.md` bzw. GitHub Releases) mit Sicherheitskorrekturen
versorgt. Ältere Versionen werden nicht rückwirkend gepatcht – bitte vor
einer Fehlermeldung immer zuerst auf die neueste Version aktualisieren.

| Version         | Unterstützt              |
| ---------------- | -------------------------- |
| Neueste Release  | ✅                          |
| Ältere Versionen | ❌ (bitte aktualisieren)    |

## Meldeweg für Sicherheitsprobleme

Sicherheitsrelevante Probleme (z. B. eine Möglichkeit, über eine
Bild-URL interne Netzwerkressourcen zu erreichen, ein Weg, die
WebSocket-Verwaltungs-API ohne Administratorrechte zu nutzen, oder ein
Leck lokal gespeicherter Hofladen-Daten) bitte **nicht** als öffentliches
GitHub-Issue melden, sondern über den privaten Meldeweg:

- GitHub: [Security Advisory](https://github.com/rest-be/HofKarte/security/advisories/new)
  für dieses Repository erstellen (falls verfügbar), oder
- direkt den/die Codeowner (`@rest-be`) über GitHub kontaktieren.

Bitte folgende Angaben beifügen, soweit bekannt:

- Betroffene HofKarte-Version (`manifest.json` → `version`)
- Home-Assistant-Version
- Schritte zur Reproduktion
- Erwartetes vs. tatsächliches Verhalten
- Falls vorhanden: relevante Auszüge aus dem Home-Assistant-Log
  (**ohne** persönliche Daten oder Zugangsdaten)

## Erwartete Reaktionszeit

Da es sich um ein privates Freizeitprojekt ohne kommerzielle Garantien
handelt, gibt es **keine zugesicherte Reaktionszeit**. Nach bestem
Bemühen wird angestrebt:

- Erstbestätigung des Eingangs: in der Regel innerhalb einiger Tage.
- Einschätzung des Schweregrads und weiteres Vorgehen: nach Verfügbarkeit
  des/der Projektbetreuer:in.

Es besteht kein Anspruch auf eine bestimmte Bearbeitungsfrist.

## Bereich dieser Policy

Diese Policy deckt ausschliesslich Sicherheitsprobleme **im
HofKarte-Quellcode selbst** ab (`custom_components/hofkarte/`).
Sicherheitsprobleme in Home Assistant selbst, in HACS oder in
Drittanbieter-Abhängigkeiten sind an die jeweiligen Projekte zu melden.

## Bekannte, bewusste Sicherheitsentscheidungen

Zur Einordnung – diese Punkte sind bekannt, dokumentiert und keine
offenen Sicherheitslücken:

- Die Bild-URL-Prüfung (`custom_components/hofkarte/images.py`) ist rein
  syntaktisch (Schema, Zugangsdaten, literale private/interne
  IP-Adressen) und führt **keine DNS-Auflösung** durch, um den
  Home-Assistant-Event-Loop nicht zu blockieren. Ein Domainname, der
  erst zur Abrufzeit auf eine private Adresse auflöst (DNS-Rebinding),
  wird dadurch nicht erkannt. Siehe README, Abschnitt „Bekannte
  Einschränkungen“.
- Über den geführten Bilder-Upload erzeugte Bilder (`Bild.hochgeladen =
  True`) sind von der Ablehnung privater/interner IP-Adressen bewusst
  ausgenommen, da ihre URL zwangsläufig auf die eigene
  Home-Assistant-Instanz zeigt. Die Vertrauensbasis ist hier die
  Herkunft (über Home Assistants offiziellen `image_upload`-Mechanismus
  erzeugt), nicht der Adressbereich; Schema- und
  Zugangsdaten-Prüfung gelten unverändert auch für hochgeladene Bilder.
  Siehe `docs/architecture.md`, Abschnitt „Geführter Bilder-Upload“.
- Der Bilder-Upload selbst nutzt ausschliesslich Home Assistants eigene
  `image_upload`-Komponente (kein eigener Upload-Endpunkt); Format-
  (JPEG/PNG/GIF) und Grössenprüfung (max. 10 MB) erfolgen serverseitig
  durch diese Komponente.
- Die Verwaltungsoberfläche (`frontend.py`, `management.py`) erfordert
  Home-Assistant-Administratorrechte (`require_admin`) – auch für die
  Funktion „Infos ermitteln“ (`ws_webseite_info`, siehe unten).
- Es findet keine Kommunikation mit externen Diensten durch HofKarte
  selbst statt (siehe README, Abschnitt „Datenschutz- und
  Standort-Hinweise“) – Ausnahmen: das Laden von Hofladen-Bildern über
  die vom Benutzer hinterlegten externen Bild-Adressen, sowie (seit
  Issue #8) der Abruf einer vom Benutzer im Verwaltungs-Panel
  eingegebenen Website-Adresse über die Funktion „Infos ermitteln“.

### Funktion „Infos ermitteln“ (`webseite_info.py`, Issue #8)

Diese Funktion ist die **erste eigene ausgehende Netzwerkanfrage im
Backend-Code von HofKarte** – bisher wurde jede Netzwerkkommunikation an
Home-Assistant-Komponenten oder den Browser delegiert. Getroffene
Sicherheitsmassnahmen:

- **Kein externer/Cloud-/KI-Dienst:** Die Extraktion erfolgt
  ausschliesslich lokal und deterministisch (schema.org-JSON-LD,
  `<title>`/Meta-Beschreibung als Fallback). Es wird kein Cloud-Dienst,
  kein LLM und kein Scraping-Dienst eingebunden.
- **SSRF-Schutz über den Standard aus `images.py` hinaus:** Neben der
  syntaktischen Grundprüfung (Schema, Zugangsdaten, „localhost“,
  private/interne IP-Literale – ausgelagert in
  `custom_components/hofkarte/url_sicherheit.py` und von `images.py`
  und `webseite_info.py` gemeinsam genutzt) gelten zusätzlich ein
  Antwortgrössen-Limit (2 MB), eine Content-Type-Prüfung (nur
  HTML-artige Antworten), eine Zeitüberschreitung (10 Sekunden) sowie
  eine manuelle, bei jedem Sprung erneut geprüfte Weiterleitungsauflösung
  (maximal 3 Sprünge) – eine Weiterleitung auf ein privates/internes
  Ziel wird dadurch abgelehnt, statt ihr automatisch zu folgen.
- **Home Assistants verwaltete Client-Session:** Der Abruf verwendet
  `homeassistant.helpers.aiohttp_client.async_get_clientsession`, keine
  eigene, unverwaltete `aiohttp.ClientSession` (siehe
  `custom_components/hofkarte/quality_scale.yaml`, Kriterium
  `inject-websession`).
- **Review vor dem Speichern:** Das Ergebnis ist ausschliesslich ein
  Vorschlag im Bearbeitungsformular – es wird dabei nichts automatisch
  gespeichert; das eigentliche Speichern erfolgt unverändert über den
  bestehenden, administratorpflichtigen `ws_save`-Befehl.
- **Bekannte, bewusste Einschränkung (wie bei `images.py`):** Es findet
  **keine DNS-Auflösung** zur Prüfung statt – ein Domainname, der erst
  beim tatsächlichen Verbindungsaufbau auf eine private Adresse
  auflöst (DNS-Rebinding), wird nicht erkannt.
