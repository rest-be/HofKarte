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
