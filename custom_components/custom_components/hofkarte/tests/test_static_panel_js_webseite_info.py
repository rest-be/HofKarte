"""Strukturelle Regressionstests für den "Infos ermitteln"-Workflow
(Issue #8, "Informationen aus Homepage").

Wie schon für frühere Frontend-Änderungen (siehe
``test_static_panel_js.py``, ``test_static_panel_js_export_import.py``,
``test_static_panel_js_formular_listener.py``,
``test_static_panel_js_routing.py``) wird ``hofkarte-panel.js`` als
reines, buildlos ausgeliefertes Frontend-JavaScript nicht über eine
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


def test_formular_enthaelt_infos_ermitteln_button() -> None:
    quelltext = _lade_panel_js()
    assert "data-webseite-info-btn" in quelltext
    assert "Infos ermitteln" in quelltext


def test_button_ist_mit_ermittle_webseite_info_verkabelt() -> None:
    quelltext = _lade_panel_js()
    treffer = re.search(
        r'\[data-webseite-info-btn\]"\)\?\.addEventListener\("click", \(\) => \{\s*'
        r"this\.ermittleWebseiteInfo\(\);",
        quelltext,
    )
    assert treffer, (
        "Der 'Infos ermitteln'-Button ist nicht mit "
        "ermittleWebseiteInfo() verkabelt."
    )


def test_ermittle_webseite_info_ruft_erwarteten_websocket_befehl_auf() -> None:
    quelltext = _lade_panel_js()
    match = re.search(
        r"async ermittleWebseiteInfo\(\) \{(.*?)\n  \}",
        quelltext,
        re.DOTALL,
    )
    assert match, "ermittleWebseiteInfo() nicht gefunden."
    body = match.group(1)
    assert '"hofkarte/management/webseite_info"' in body
    # Fehlerfall 1 (Issue #8): keine Website-Adresse -> kein Backend-Aufruf.
    assert "if (!website)" in body
    assert "this.setWebseiteInfoStatus(" in body


def test_kein_backend_aufruf_ohne_eingegebene_website_adresse() -> None:
    """Fehlerfall 1 aus Issue #8: Ohne eingegebene Website-Adresse darf
    kein WebSocket-Aufruf ausgelöst werden - die leere Prüfung muss vor
    dem this.call(...) liegen und dabei aus der Funktion zurückkehren."""
    quelltext = _lade_panel_js()
    match = re.search(
        r"async ermittleWebseiteInfo\(\) \{(.*?)\n  \}",
        quelltext,
        re.DOTALL,
    )
    assert match
    body = match.group(1)
    leer_pruefung_index = body.index("if (!website)")
    call_index = body.index('this.call("hofkarte/management/webseite_info"')
    assert leer_pruefung_index < call_index

    leer_block = body[leer_pruefung_index : body.index("}", leer_pruefung_index) + 1]
    assert "return" in leer_block


def test_uebernehme_webseite_info_existiert_und_speichert_nicht_automatisch() -> None:
    """Die ermittelten Daten dürfen nur in this.editing (den
    Bearbeitungszustand) übernommen werden, nicht direkt gespeichert
    werden (kein this.call("hofkarte/management/save", ...) innerhalb
    der Übernahme-Funktion)."""
    quelltext = _lade_panel_js()
    match = re.search(
        r"uebernehmeWebseiteInfo\(info\) \{(.*?)\n  \}",
        quelltext,
        re.DOTALL,
    )
    assert match, "uebernehmeWebseiteInfo(info) nicht gefunden."
    body = match.group(1)
    assert "this.editing" in body
    assert "hofkarte/management/save" not in body
    assert "this.call(" not in body


def test_alle_drei_fehlercodes_aus_issue_8_werden_behandelt() -> None:
    quelltext = _lade_panel_js()
    assert "invalid_url" in quelltext
    assert "unreachable" in quelltext
    assert "not_found" in quelltext


def test_website_feld_bleibt_im_formular_vorhanden() -> None:
    """Regressionsschutz: Das Website-Eingabefeld existierte bereits vor
    Issue #8 (Datenmodell kennt 'website' schon) und darf durch die neue
    Funktion nicht versehentlich entfernt werden."""
    quelltext = _lade_panel_js()
    assert 'this.input("Webseite", "website", d.website || "")' in quelltext


# ---------------------------------------------------------------------------
# Issue #9, Korrektur 5.1: Regressionsschutz gegen den Datenverlust-Bug.
# ---------------------------------------------------------------------------


def test_ermittle_webseite_info_erfasst_formularzustand_vor_jedem_render() -> None:
    """Kern des Bugfixes: ermittleWebseiteInfo() muss den vollständigen
    Formularzustand VOR dem ersten this.render()-Aufruf sichern (siehe
    erfasseFormularZustand()) - nicht erst danach, und nicht nur punktuell
    für das Feld 'website'."""
    quelltext = _lade_panel_js()
    match = re.search(
        r"async ermittleWebseiteInfo\(\) \{(.*?)\n  \}",
        quelltext,
        re.DOTALL,
    )
    assert match, "ermittleWebseiteInfo() nicht gefunden."
    body = match.group(1)

    erfassen_index = body.index("this.erfasseFormularZustand()")
    call_index = body.index('this.call("hofkarte/management/webseite_info"')
    assert erfassen_index < call_index, (
        "Der Formularzustand muss bereits vor dem Backend-Aufruf gesichert "
        "werden, nicht erst danach."
    )
    # Es darf keinen this.render()-Aufruf VOR der Erfassung geben - sonst
    # wäre das Formular zu diesem Zeitpunkt bereits aus dem alten
    # this.editing-Stand neu aufgebaut worden.
    assert "this.render()" not in body[:erfassen_index]


def test_erfasse_formular_zustand_existiert_und_nutzt_formData_mechanismus() -> None:
    """erfasseFormularZustand() muss denselben Erfassungsmechanismus wie
    formData()/save() nutzen (leseEinfacheFelder()), nicht eine eigene,
    auf 'website' beschränkte Sonderlogik."""
    quelltext = _lade_panel_js()
    match = re.search(
        r"erfasseFormularZustand\(\) \{(.*?)\n  \}",
        quelltext,
        re.DOTALL,
    )
    assert match, "erfasseFormularZustand() nicht gefunden."
    body = match.group(1)
    assert "this.leseEinfacheFelder(f)" in body
    assert "this.editing" in body


def test_formdata_und_erfasse_formular_zustand_teilen_sich_feldlogik() -> None:
    """formData() (save()) und erfasseFormularZustand() ("Infos
    ermitteln", Issue #9) dürfen die Feld-Auslesung nicht dupliziert
    implementieren, sondern müssen denselben Helfer nutzen - sonst könnte
    künftig ein Feld in nur einem der beiden Pfade berücksichtigt werden."""
    quelltext = _lade_panel_js()
    formdata_match = re.search(r"  formData\(\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert formdata_match, "formData() nicht gefunden."
    assert "this.leseEinfacheFelder(f)" in formdata_match.group(1)


def test_regressionsbeispiel_aus_issue_9_website_ueberlebt_render() -> None:
    """Konkretes, im Issue gemeldetes Beispiel: this.editing.website muss
    nach der Erfassung den (zuvor nur im DOM stehenden) Live-Wert tragen,
    bevor render() das Formular aus this.editing neu aufbaut."""
    quelltext = _lade_panel_js()
    match = re.search(r"leseEinfacheFelder\(f\) \{(.*?)\n  \}", quelltext, re.DOTALL)
    assert match, "leseEinfacheFelder(f) nicht gefunden."
    body = match.group(1)
    assert 'data.website = value("website") || null;' in body


# ---------------------------------------------------------------------------
# Issue #9, Erweiterung 5.2: Bestätigungs-Popup vor der Übernahme.
# ---------------------------------------------------------------------------


def test_popup_wird_nicht_mehr_direkt_nach_dem_abruf_uebernommen() -> None:
    """Kernanforderung 5.2: ein erfolgreicher Abruf darf die Vorschläge
    nicht mehr direkt in this.editing schreiben (uebernehmeWebseiteInfo()
    aufrufen) - stattdessen müssen sie zunächst als Vorschlag
    zwischengespeichert werden."""
    quelltext = _lade_panel_js()
    match = re.search(
        r"async ermittleWebseiteInfo\(\) \{(.*?)\n  \}",
        quelltext,
        re.DOTALL,
    )
    assert match
    body = match.group(1)
    assert "this.webseiteInfoVorschlag = result.info || {};" in body
    assert "this.uebernehmeWebseiteInfo(result.info" not in body


def test_popup_markup_enthaelt_uebernehmen_und_abbrechen_buttons() -> None:
    quelltext = _lade_panel_js()
    assert "data-webseite-info-uebernehmen" in quelltext
    assert "data-webseite-info-abbrechen" in quelltext
    assert "Übernehmen" in quelltext
    assert "Abbrechen" in quelltext


def test_popup_wird_nur_bei_vorhandenem_vorschlag_gerendert() -> None:
    quelltext = _lade_panel_js()
    assert "${this.webseiteInfoVorschlag ? this.webseiteInfoPopup(this.webseiteInfoVorschlag) : \"\"}" in quelltext


def test_uebernehmen_button_ist_mit_uebernahme_verkabelt_und_schliesst_popup() -> None:
    quelltext = _lade_panel_js()
    treffer = re.search(
        r'\[data-webseite-info-uebernehmen\]"\)\?\.addEventListener\("click", '
        r"\(\) => this\.uebernehmeWebseiteInfoVorschlag\(\)\);",
        quelltext,
    )
    assert treffer, "'Übernehmen'-Button ist nicht mit uebernehmeWebseiteInfoVorschlag() verkabelt."

    match = re.search(
        r"uebernehmeWebseiteInfoVorschlag\(\) \{(.*?)\n  \}",
        quelltext,
        re.DOTALL,
    )
    assert match, "uebernehmeWebseiteInfoVorschlag() nicht gefunden."
    body = match.group(1)
    assert "this.uebernehmeWebseiteInfo(this.webseiteInfoVorschlag" in body
    assert "this.webseiteInfoVorschlag = null;" in body
    assert "this.render();" in body


def test_abbrechen_button_ist_mit_verwerfen_verkabelt_und_schreibt_nichts_in_editing() -> None:
    quelltext = _lade_panel_js()
    treffer = re.search(
        r'\[data-webseite-info-abbrechen\]"\)\?\.addEventListener\("click", '
        r"\(\) => this\.abbrechenWebseiteInfo\(\)\);",
        quelltext,
    )
    assert treffer, "'Abbrechen'-Button ist nicht mit abbrechenWebseiteInfo() verkabelt."

    match = re.search(
        r"abbrechenWebseiteInfo\(\) \{(.*?)\n  \}",
        quelltext,
        re.DOTALL,
    )
    assert match, "abbrechenWebseiteInfo() nicht gefunden."
    body = match.group(1)
    # "Abbrechen" darf die Vorschläge nur verwerfen (this.editing nicht
    # verändern) und das Popup schliessen.
    assert "this.webseiteInfoVorschlag = null;" in body
    assert "this.editing" not in body
    assert "this.uebernehmeWebseiteInfo" not in body


def test_popup_unterstuetzt_schliessen_per_escape_taste() -> None:
    """Barrierefreiheit (Anforderung 5.2): Escape muss das Popup wie
    'Abbrechen' schliessen."""
    quelltext = _lade_panel_js()
    match = re.search(
        r'\[data-webseite-info-overlay\]"\)\?\.addEventListener\("keydown", \(e\) => \{(.*?)\}\);',
        quelltext,
        re.DOTALL,
    )
    assert match, "Kein Escape-Handler auf dem Popup-Overlay gefunden."
    assert 'e.key === "Escape"' in match.group(1)
    assert "this.abbrechenWebseiteInfo();" in match.group(1)


def test_popup_hat_dialog_barrierefreiheits_attribute() -> None:
    quelltext = _lade_panel_js()
    assert 'role="dialog"' in quelltext
    assert 'aria-modal="true"' in quelltext
    assert "aria-labelledby=" in quelltext


def test_popup_zeigt_nicht_gefundene_felder_explizit_an() -> None:
    """Anforderung 5.2: leere/nicht gefundene Felder müssen klar als
    solche gekennzeichnet werden, nicht einfach weggelassen werden."""
    quelltext = _lade_panel_js()
    assert "nicht gefunden" in quelltext
