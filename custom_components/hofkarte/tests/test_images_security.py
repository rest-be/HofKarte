"""Tests für die syntaktische Sicherheitsprüfung in images.py.

Bewusst ohne DNS-Mocking: Die Prüfung erfolgt seit dem Bugfix rein
syntaktisch (kein blockierender socket.getaddrinfo-Aufruf mehr, siehe
images.py-Moduldoc).
"""

from custom_components.hofkarte import images
from custom_components.hofkarte.models import Bild


def test_rejects_loopback_ip_literal() -> None:
    assert not images.is_valid_image_url("http://127.0.0.1/img.jpg")


def test_rejects_private_ipv4_literal() -> None:
    assert not images.is_valid_image_url("http://192.168.1.1/img.jpg")


def test_rejects_localhost_hostname() -> None:
    assert not images.is_valid_image_url("http://localhost/img.jpg")


def test_rejects_ipv6_loopback_literal() -> None:
    assert not images.is_valid_image_url("http://[::1]/img.jpg")


def test_rejects_link_local_literal() -> None:
    assert not images.is_valid_image_url("http://169.254.169.254/meta")


def test_accepts_public_domain_host() -> None:
    """Ein gewöhnlicher Domainname wird akzeptiert (keine DNS-Auflösung,
    siehe Moduldoc zu den bewussten Grenzen dieser Prüfung)."""
    assert images.is_valid_image_url("https://example.com/pic.jpg")


def test_rejects_credentials_in_url() -> None:
    assert not images.is_valid_image_url("http://user:pw@example.com/a.jpg")


def test_get_additional_images_excludes_hauptbild_and_unsafe_entries() -> None:
    """Das Hauptbild fehlt in der Liste; unsichere Einträge (IP-Literal,
    privat) werden ebenfalls gefiltert."""
    images_list = (
        Bild(url="https://example.com/1.jpg", beschreibung="one"),
        Bild(url="http://127.0.0.1/x.png", beschreibung="local"),
        Bild(url="https://example.com/2.jpg", beschreibung=None),
    )

    hauptbild = images.get_main_image_url(images_list)
    weitere = images.get_additional_images(images_list)

    assert hauptbild == "https://example.com/1.jpg"
    urls = [eintrag["url"] for eintrag in weitere]
    assert urls == ["https://example.com/2.jpg"]
    assert "http://127.0.0.1/x.png" not in urls
    assert "https://example.com/1.jpg" not in urls
