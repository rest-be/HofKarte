import socket
import pytest

from custom_components.hofkarte import images


def _fake_getaddrinfo_loopback(host, *args, **kwargs):
    return [(socket.AF_INET, None, None, None, ("127.0.0.1", 0))]


def _fake_getaddrinfo_public(host, *args, **kwargs):
    return [(socket.AF_INET, None, None, None, ("93.184.216.34", 0))]  # example.com


def test_rejects_localhost(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo_loopback)
    assert not images.is_valid_image_url("http://example.local/img.jpg")


def test_rejects_private_ipv4(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, None, None, None, ("192.168.1.1", 0))])
    assert not images.is_valid_image_url("http://192.168.1.1/img.jpg")


def test_accepts_public_host(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo_public)
    assert images.is_valid_image_url("https://example.com/pic.jpg")


def test_rejects_credentials(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo_public)
    assert not images.is_valid_image_url("http://user:pw@example.com/a.jpg")


def test_build_images_attribute_filters(monkeypatch):
    # valid + invalid + valid -> only valids kept, primary is first valid
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo_public)
    from custom_components.hofkarte.models import Bild

    images_list = (
        Bild(url="https://example.com/1.jpg", beschreibung="one"),
        Bild(url="http://127.0.0.1/x.png", beschreibung="local"),
        Bild(url="https://example.com/2.jpg", beschreibung=None),
    )
    attr = images.build_images_attribute(images_list)
    assert attr["primary_image"] == "https://example.com/1.jpg"
    assert len(attr["images"]) == 2
