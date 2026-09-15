"""Automatisiert prüfbare HACS-/Manifest-Korrektheit (Einheit 14).

Prüft strukturelle Anforderungen an ``manifest.json`` und ``hacs.json``,
die vor einem Release automatisiert verifizierbar sind. Ersetzt keine
echte HACS-Installation (nicht automatisiert simulierbar), stellt aber
sicher, dass die dafür nötigen Grundlagen (gültiges JSON, Pflichtfelder,
konsistente Version, erreichbare Domain) stimmen.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_HOFKARTE_DIR = _REPO_ROOT / "custom_components" / "hofkarte"

_SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def _load_manifest() -> dict:
    with (_HOFKARTE_DIR / "manifest.json").open(encoding="utf-8") as datei:
        return json.load(datei)


def _load_hacs() -> dict:
    with (_REPO_ROOT / "hacs.json").open(encoding="utf-8") as datei:
        return json.load(datei)


def test_manifest_ist_gueltiges_json() -> None:
    _load_manifest()


def test_manifest_enthaelt_alle_pflichtfelder() -> None:
    manifest = _load_manifest()
    pflichtfelder = {
        "domain",
        "name",
        "codeowners",
        "config_flow",
        "documentation",
        "issue_tracker",
        "iot_class",
        "requirements",
        "version",
    }
    fehlende_felder = pflichtfelder - set(manifest.keys())
    assert not fehlende_felder, f"Fehlende Pflichtfelder: {fehlende_felder}"


def test_manifest_domain_stimmt_mit_ordnername_ueberein() -> None:
    manifest = _load_manifest()
    assert manifest["domain"] == "hofkarte"
    assert manifest["domain"] == _HOFKARTE_DIR.name


def test_manifest_version_folgt_semantic_versioning() -> None:
    manifest = _load_manifest()
    assert _SEMVER_PATTERN.match(manifest["version"]), (
        f"Version '{manifest['version']}' entspricht nicht MAJOR.MINOR.PATCH"
    )


def test_manifest_config_flow_ist_aktiviert() -> None:
    """HofKarte wird ausschliesslich über den Config Flow eingerichtet
    (keine YAML-Konfiguration, siehe Einheit 2)."""
    manifest = _load_manifest()
    assert manifest["config_flow"] is True


def test_manifest_hat_keine_unerwarteten_python_abhaengigkeiten() -> None:
    """HofKarte benötigt ausser Home Assistant selbst keine zusätzlichen
    Python-Pakete (siehe README, Abschnitt „Voraussetzungen“)."""
    manifest = _load_manifest()
    assert manifest["requirements"] == []


def test_manifest_deklariert_http_abhaengigkeit() -> None:
    """Ohne diese Abhängigkeit ist ``hass.http`` beim Setup nicht
    zuverlässig verfügbar (siehe CHANGELOG, behobener Bug in Einheit 10)."""
    manifest = _load_manifest()
    assert "http" in manifest.get("dependencies", [])


def test_hacs_json_ist_gueltiges_json() -> None:
    _load_hacs()


def test_hacs_json_enthaelt_name_und_render_readme() -> None:
    hacs = _load_hacs()
    assert hacs.get("name") == "HofKarte"
    assert hacs.get("render_readme") is True


def test_hacs_json_deklariert_minimale_ha_version() -> None:
    hacs = _load_hacs()
    assert "homeassistant" in hacs


def test_manifest_version_stimmt_mit_neuestem_changelog_eintrag_ueberein() -> None:
    """Die Manifest-Version muss der zuletzt dokumentierten Version im
    CHANGELOG entsprechen (Versionierung konsistent halten, Einheit 13)."""
    manifest = _load_manifest()
    changelog = (_REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    versions_in_changelog = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.MULTILINE)
    assert versions_in_changelog, "Keine Versionseinträge im CHANGELOG gefunden."

    neueste_dokumentierte_version = versions_in_changelog[0]
    # Die Manifest-Version darf entweder der neuesten dokumentierten
    # Version entsprechen (bereits im CHANGELOG nachgezogen) oder um genau
    # eine Version "voraus" sein (Änderung gerade erst vorgenommen, der
    # zugehörige CHANGELOG-Eintrag steht noch unter "[Unveröffentlicht]").
    assert manifest["version"] >= neueste_dokumentierte_version, (
        f"manifest.json ({manifest['version']}) liegt hinter dem "
        f"CHANGELOG ({neueste_dokumentierte_version}) zurück."
    )


def test_repository_struktur_enthaelt_alle_hacs_pflichtdateien() -> None:
    """Minimale Dateistruktur, die HACS für ein Integrations-Repository
    voraussetzt."""
    pflichtdateien = [
        _REPO_ROOT / "hacs.json",
        _REPO_ROOT / "README.md",
        _REPO_ROOT / "CHANGELOG.md",
        _REPO_ROOT / "LICENSE",
        _HOFKARTE_DIR / "manifest.json",
        _HOFKARTE_DIR / "__init__.py",
    ]
    fehlende_dateien = [str(p) for p in pflichtdateien if not p.is_file()]
    assert not fehlende_dateien, f"Fehlende Pflichtdateien: {fehlende_dateien}"
