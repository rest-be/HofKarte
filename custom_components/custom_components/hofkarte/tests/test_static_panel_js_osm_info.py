"""Strukturelle Regressionstests für den "Ort in der Nähe suchen"-Workflow
(Issue #10, "Erweiterung OpenStreetMap zu #8").

Wie schon für frühere Frontend-Änderungen (siehe insbesondere
``test_static_panel_js_webseite_info.py``, dessen Bestätigungs-Popup
dieser Workflow wiederverwendet) wird ``hofkarte-panel.js`` als reines,
buildlos ausgeliefertes Frontend-JavaScript nicht über eine
JS-Testumgebung, sondern über gezielte strukturelle Prüfungen des
Quelltexts abgesichert.
"""

from __future__ import annotations

import re
from pathlib import Path

_PANEL_JS_PATH = (
    Path(__file__).resolve().parent.parent / "static" / "hofkarte-panel.js"
)


def _lade_panel_js() -> str:
    return _PANEL_JS_PATH.read_text(encoding="utf-8")


def test_formular_enthaelt_ort_suchen_button() -> None:
    quelltext = _lade_panel_js()
    assert "data-osm-info-btn" in quelltext
    assert "Ort in der Nähe suchen" in quelltext


def test_button_ist_mit_ermittle_osm_info_verkabelt() -> None:
    quelltext = _lade_panel_js()
    treffer = re.search(
        r'\[data-osm-info-btn\]"\)\?\.addEventListener\("click", \(\) => \{\s*'
        r"this\.ermittleOsmInfo\(\);",
        quelltext,
    )
    assert treffer, "Der 'Ort in der Nähe suchen'-Button ist nicht mit ermittleOsmInfo() verkabelt."


def test_ermittle_osm_info_ruft_erwarteten_websocket_befehl_auf() -> None:
    quelltext = _lade_panel_js()
    match = re.search(r"async ermittleOsmInfo\(\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match, "ermittleOsmInfo() nicht gefunden."
    body = match.group(1)
    assert '"hofkarte/management/osm_info"' in body
    # Fehlerfall 1 (Issue #10): keine gültigen Koordinaten -> kein
    # Backend-Aufruf.
    assert "if (!isValidWgs84(latitude, longitude))" in body
    assert "this.setOsmInfoStatus(" in body


def test_kein_backend_aufruf_ohne_gueltige_koordinaten() -> None:
    """Fehlerfall 1 aus Issue #10: Ohne gültige Latitude-/Longitude-Werte
    darf kein WebSocket-Aufruf ausgelöst werden - die Prüfung muss vor
    dem this.call(...) liegen und dabei aus der Funktion zurückkehren."""
    quelltext = _lade_panel_js()
    match = re.search(r"async ermittleOsmInfo\(\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match
    body = match.group(1)
    pruefung_index = body.index("if (!isValidWgs84(latitude, longitude))")
    call_index = body.index('this.call("hofkarte/management/osm_info"')
    assert pruefung_index < call_index

    pruef_block = body[pruefung_index : body.index("}", pruefung_index) + 1]
    assert "return" in pruef_block


def test_alle_drei_fehlercodes_aus_issue_10_werden_behandelt() -> None:
    quelltext = _lade_panel_js()
    assert "invalid_coordinates" in quelltext
    assert "unreachable" in quelltext
    assert "not_found" in quelltext


def test_ermittle_osm_info_erfasst_formularzustand_vor_jedem_render() -> None:
    """Kern des in Issue #9 behobenen Datenverlust-Bugs, hier als
    Anti-Regressionsanforderung für den neuen OSM-Workflow (Issue #10,
    5.2): ermittleOsmInfo() muss den vollständigen Formularzustand VOR dem
    ersten this.render()-Aufruf sichern (siehe erfasseFormularZustand())."""
    quelltext = _lade_panel_js()
    match = re.search(r"async ermittleOsmInfo\(\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match, "ermittleOsmInfo() nicht gefunden."
    body = match.group(1)

    erfassen_index = body.index("this.erfasseFormularZustand()")
    call_index = body.index('this.call("hofkarte/management/osm_info"')
    assert erfassen_index < call_index, (
        "Der Formularzustand muss bereits vor dem Backend-Aufruf gesichert "
        "werden, nicht erst danach."
    )
    assert "this.render()" not in body[:erfassen_index]


def test_ein_treffer_ueberspringt_auswahlliste_und_oeffnet_popup_direkt() -> None:
    """Anforderung 5.2: Bei genau einem Treffer wird die Trefferauswahl
    übersprungen - der Treffer landet direkt in this.webseiteInfoVorschlag
    (dem wiederverwendeten Bestätigungs-Popup, siehe 5.3)."""
    quelltext = _lade_panel_js()
    match = re.search(r"async ermittleOsmInfo\(\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match
    body = match.group(1)
    assert "orte.length === 1" in body
    assert "this.webseiteInfoVorschlag = this.osmOrtZuVorschlag(orte[0]);" in body


def test_mehrere_treffer_zeigen_auswahlliste() -> None:
    """Anforderung 5.2: Bei mehr als einem Treffer wird zunächst die
    Trefferauswahl gezeigt (this.osmOrteAuswahl), nicht direkt das
    Bestätigungs-Popup."""
    quelltext = _lade_panel_js()
    match = re.search(r"async ermittleOsmInfo\(\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match
    body = match.group(1)
    assert "this.osmOrteAuswahl = orte;" in body


def test_trefferauswahl_wird_nur_bei_vorhandenen_treffern_gerendert() -> None:
    quelltext = _lade_panel_js()
    assert (
        '${this.osmOrteAuswahl ? this.osmOrteAuswahlPopup(this.osmOrteAuswahl) : ""}'
        in quelltext
    )


def test_trefferauswahl_eintraege_sind_mit_waehleosmort_verkabelt() -> None:
    quelltext = _lade_panel_js()
    assert "data-osm-orte-auswahl" in quelltext
    treffer = re.search(
        r'\[data-osm-orte-auswahl\]"\)\.forEach\(b =>\s*'
        r"b\.addEventListener\(\"click\", \(\) => this\.waehleOsmOrt\(",
        quelltext,
    )
    assert treffer, "Die Trefferauswahl-Einträge sind nicht mit waehleOsmOrt() verkabelt."


def test_waehle_osm_ort_oeffnet_gemeinsames_bestaetigungs_popup() -> None:
    """Anforderung 5.3: die Auswahl eines Treffers aus der Liste darf
    NICHT sofort in this.editing schreiben - sie muss stattdessen (wie
    beim einzelnen Treffer) zunächst das gemeinsame Bestätigungs-Popup
    öffnen (this.webseiteInfoVorschlag), damit der Treffer weiterhin vor
    der Übernahme geprüft werden kann."""
    quelltext = _lade_panel_js()
    match = re.search(r"waehleOsmOrt\(index\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match, "waehleOsmOrt(index) nicht gefunden."
    body = match.group(1)
    assert "this.webseiteInfoVorschlag = this.osmOrtZuVorschlag(ort);" in body
    assert "this.uebernehmeWebseiteInfo(" not in body
    assert "hofkarte/management/save" not in body


def test_abbrechen_der_trefferauswahl_verwirft_ohne_editing_zu_aendern() -> None:
    quelltext = _lade_panel_js()
    assert "data-osm-orte-abbrechen" in quelltext
    treffer = re.search(
        r'\[data-osm-orte-abbrechen\]"\)\?\.addEventListener\("click", '
        r"\(\) => this\.abbrechenOsmAuswahl\(\)\);",
        quelltext,
    )
    assert treffer, "'Abbrechen'-Button der Trefferauswahl ist nicht mit abbrechenOsmAuswahl() verkabelt."

    match = re.search(r"abbrechenOsmAuswahl\(\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match, "abbrechenOsmAuswahl() nicht gefunden."
    body = match.group(1)
    assert "this.osmOrteAuswahl = null;" in body
    assert "this.editing" not in body


def test_trefferauswahl_unterstuetzt_schliessen_per_escape_taste() -> None:
    """Barrierefreiheit (analog zum wiederverwendeten Bestätigungs-Popup,
    Issue #9, Anforderung 5.2): Escape muss die Trefferauswahl wie
    'Abbrechen' schliessen."""
    quelltext = _lade_panel_js()
    match = re.search(
        r'\[data-osm-orte-overlay\]"\)\?\.addEventListener\("keydown", \(e\) => \{(.*?)\}\);',
        quelltext,
        re.DOTALL,
    )
    assert match, "Kein Escape-Handler auf dem Trefferauswahl-Overlay gefunden."
    assert 'e.key === "Escape"' in match.group(1)
    assert "this.abbrechenOsmAuswahl();" in match.group(1)


def test_trefferauswahl_popup_hat_dialog_barrierefreiheits_attribute() -> None:
    quelltext = _lade_panel_js()
    match = re.search(r"osmOrteAuswahlPopup\(orte\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match, "osmOrteAuswahlPopup(orte) nicht gefunden."
    body = match.group(1)
    assert 'role="dialog"' in body
    assert 'aria-modal="true"' in body
    assert "aria-labelledby=" in body


def test_render_fokussiert_trefferauswahl_dialog_beim_oeffnen() -> None:
    quelltext = _lade_panel_js()
    match = re.search(
        r"if \(this\.osmOrteAuswahl\) \{\s*"
        r'this\.shadowRoot\.querySelector\("\[data-osm-orte-dialog\]"\)\?\.focus\(\);',
        quelltext,
    )
    assert match, "render() fokussiert den Trefferauswahl-Dialog beim Öffnen nicht."


def test_osm_info_button_ist_ohne_gueltige_koordinaten_deaktiviert() -> None:
    """Analog zu mapButton(): der Button darf ohne gültige WGS84-
    Koordinaten nicht klickbar sein (siehe isValidWgs84())."""
    quelltext = _lade_panel_js()
    assert (
        'data-osm-info-btn ${isValidWgs84(latValue === "" ? NaN : Number(latValue), '
        'lonValue === "" ? NaN : Number(lonValue)) ? "" : "disabled"}'
        in quelltext
    ), "Der 'Ort in der Nähe suchen'-Button ist nicht an isValidWgs84() gekoppelt."


def test_osm_zustand_wird_beim_start_und_abbrechen_zurueckgesetzt() -> None:
    """Regressionsschutz: start()/cancel() müssen den OSM-Zustand
    (Trefferauswahl, Statusmeldung) wie den Website-Info-Zustand
    zurücksetzen, sonst könnte eine alte Trefferauswahl/-meldung beim
    nächsten Bearbeiten eines (ggf. anderen) Hofladens wieder auftauchen."""
    quelltext = _lade_panel_js()
    start_match = re.search(r"start\(item = null\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    cancel_match = re.search(r"  cancel\(\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert start_match, "start(item) nicht gefunden."
    assert cancel_match, "cancel() nicht gefunden."
    for body in (start_match.group(1), cancel_match.group(1)):
        assert "this.osmOrteAuswahl = null;" in body


def test_uebernehme_webseite_info_verarbeitet_auch_website_feld() -> None:
    """Damit ein von der Overpass API gefundener Website-Vorschlag
    (osmOrtZuVorschlag()) beim Übernehmen nicht stillschweigend verloren
    geht, muss uebernehmeWebseiteInfo() auch das Feld 'website'
    berücksichtigen - nicht nur die von webseite_info.py bereits
    gelieferten Felder."""
    quelltext = _lade_panel_js()
    match = re.search(r"uebernehmeWebseiteInfo\(info\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match, "uebernehmeWebseiteInfo(info) nicht gefunden."
    body = match.group(1)
    assert '"website"' in body


def test_popup_zeigt_webseite_vorschlag_an() -> None:
    quelltext = _lade_panel_js()
    match = re.search(r"webseiteInfoPopup\(info\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match, "webseiteInfoPopup(info) nicht gefunden."
    body = match.group(1)
    assert 'zeile("Webseite", info.website)' in body


def test_datenschutz_hinweis_zur_uebertragung_der_koordinaten() -> None:
    """Anforderung aus dem Prompt (Architektur/Datenschutz): die
    Benutzerin/der Benutzer muss im Formular selbst erkennen können, dass
    beim Klick auf "Ort in der Nähe suchen" Koordinaten an einen externen
    Dienst übermittelt werden."""
    quelltext = _lade_panel_js()
    assert "OpenStreetMap-Overpass-API" in quelltext
    assert "externen, kostenlosen OpenStreetMap-Dienst" in quelltext
