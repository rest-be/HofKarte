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
- Die Verwaltungsoberfläche (`frontend.py`, `management.py`) erfordert
  Home-Assistant-Administratorrechte (`require_admin`).
- Es findet keine Kommunikation mit externen Diensten durch HofKarte
  selbst statt (siehe README, Abschnitt „Datenschutz- und
  Standort-Hinweise“) – Ausnahme: das Laden von Hofladen-Bildern über
  die vom Benutzer hinterlegten Bild-URLs.
