"""Tests für den gemeinsamen SSRF-Prüfkern (url_sicherheit.py).

Ausgelagert aus ``images.py`` im Zuge von Issue #8 ("Informationen aus
Homepage"), das denselben Prüfkern ein zweites Mal benötigt (siehe
``webseite_info.py``). Bewusst ohne DNS-Mocking, siehe Moduldoc: die
Prüfung ist rein syntaktisch.
"""

from custom_components.hofkarte.url_sicherheit import (
    ist_sichere_externe_url,
    ist_unsicheres_ip_literal,
)


def test_akzeptiert_gewoehnliche_domain() -> None:
    assert ist_sichere_externe_url("https://www.beispiel-hofladen.ch/")


def test_lehnt_leere_oder_fehlende_url_ab() -> None:
    assert not ist_sichere_externe_url("")
    assert not ist_sichere_externe_url("   ")
    assert not ist_sichere_externe_url(None)


def test_lehnt_unsichere_schemata_ab() -> None:
    assert not ist_sichere_externe_url("file:///etc/passwd")
    assert not ist_sichere_externe_url("ftp://beispiel.example/")
    assert not ist_sichere_externe_url("data:text/html,<script>")


def test_lehnt_zugangsdaten_in_url_ab() -> None:
    assert not ist_sichere_externe_url("http://user:pw@beispiel.example/")


def test_lehnt_localhost_ab() -> None:
    assert not ist_sichere_externe_url("http://localhost/")
    assert not ist_sichere_externe_url("http://LOCALHOST/")


def test_lehnt_private_und_loopback_ip_literale_ab() -> None:
    assert not ist_sichere_externe_url("http://127.0.0.1/")
    assert not ist_sichere_externe_url("http://192.168.1.1/")
    assert not ist_sichere_externe_url("http://10.0.0.5/")
    assert not ist_sichere_externe_url("http://[::1]/")


def test_lehnt_link_local_und_cloud_metadata_ab() -> None:
    assert not ist_sichere_externe_url("http://169.254.169.254/latest/meta-data")


def test_kennt_keine_herkunfts_ausnahme() -> None:
    """Anders als images.is_valid_image_url(hochgeladen=True) - diese
    Funktion ist ausschliesslich für frei eingegebene, nicht
    vertrauenswürdige URLs gedacht."""
    assert not ist_sichere_externe_url("http://192.168.1.50:8123/api/image/serve/x")


def test_ist_unsicheres_ip_literal_liefert_false_fuer_domainnamen() -> None:
    assert ist_unsicheres_ip_literal("example.com") is False


def test_ist_unsicheres_ip_literal_erkennt_private_adresse() -> None:
    assert ist_unsicheres_ip_literal("192.168.0.1") is True
