import asyncio
import pytest

from types import SimpleNamespace

from custom_components.hofkarte.camera import HofKarteMainImageCamera


class DummyResp:
    def __init__(self, status=200, headers=None, url="https://example.com/img.jpg", body=b"data"):
        self.status = status
        self.headers = headers or {"Content-Type": "image/jpeg"}
        self.url = url
        self._body = body

    async def read(self):
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class DummySession:
    def __init__(self, resp):
        self._resp = resp

    def get(self, *args, **kwargs):
        return self._resp


@pytest.mark.asyncio
async def test_camera_fetch_returns_bytes(monkeypatch):
    # minimal stub for camera instance
    cam = HofKarteMainImageCamera.__new__(HofKarteMainImageCamera)
    cam.coordinator = SimpleNamespace(data={})
    cam.hass = SimpleNamespace()

    dummy = DummyResp()
    monkeypatch.setattr("custom_components.hofkarte.camera.async_get_clientsession", lambda hass: DummySession(dummy))
    monkeypatch.setattr("custom_components.hofkarte.camera.is_valid_image_url", lambda u: True)

    result = await cam._async_fetch_image("https://example.com/img.jpg")
    assert result == b"data"


@pytest.mark.asyncio
async def test_camera_fetch_rejects_non_image(monkeypatch):
    cam = HofKarteMainImageCamera.__new__(HofKarteMainImageCamera)
    cam.coordinator = SimpleNamespace(data={})
    cam.hass = SimpleNamespace()
    dummy = DummyResp(status=200, headers={"Content-Type": "text/html"}, body=b"ok")
    monkeypatch.setattr("custom_components.hofkarte.camera.async_get_clientsession", lambda hass: DummySession(dummy))
    monkeypatch.setattr("custom_components.hofkarte.camera.is_valid_image_url", lambda u: True)
    result = await cam._async_fetch_image("https://example.com/img.jpg")
    assert result is None


@pytest.mark.asyncio
async def test_camera_fetch_rejects_redirect_to_local(monkeypatch):
    cam = HofKarteMainImageCamera.__new__(HofKarteMainImageCamera)
    cam.coordinator = SimpleNamespace(data={})
    cam.hass = SimpleNamespace()
    dummy = DummyResp(status=200, headers={"Content-Type": "image/png"}, url="http://127.0.0.1/pic", body=b"ok")
    monkeypatch.setattr("custom_components.hofkarte.camera.async_get_clientsession", lambda hass: DummySession(dummy))
    monkeypatch.setattr("custom_components.hofkarte.camera.is_valid_image_url", lambda u: False)
    result = await cam._async_fetch_image("https://example.com/img.jpg")
    assert result is None
