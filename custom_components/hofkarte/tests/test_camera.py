"""Tests für ``camera.py`` – Camera entity für das Hauptbild."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.hofkarte.camera import HofKarteMainImageCamera
from custom_components.hofkarte.coordinator import HofKarteUpdateCoordinator
from custom_components.hofkarte.models import Bild, Hofladen
from custom_components.hofkarte.tests.conftest import (
    create_mock_coordinator,
)


@pytest.mark.asyncio
async def test_camera_entity_available_with_valid_image() -> None:
    """Camera entity sollte verfügbar sein, wenn ein gültiges Bild existiert."""
    hofladen = Hofladen(
        id="test-hof",
        name="Test Hofladen",
        bilder=(Bild(url="https://example.com/image.jpg", beschreibung="Test"),),
    )

    coordinator = create_mock_coordinator(hofladen)
    camera = HofKarteMainImageCamera(coordinator, "test-hof")

    assert camera.available is True


@pytest.mark.asyncio
async def test_camera_entity_unavailable_without_images() -> None:
    """Camera entity sollte nicht verfügbar sein, wenn keine Bilder existieren."""
    hofladen = Hofladen(id="test-hof", name="Test Hofladen", bilder=())

    coordinator = create_mock_coordinator(hofladen)
    camera = HofKarteMainImageCamera(coordinator, "test-hof")

    assert camera.available is False


@pytest.mark.asyncio
async def test_camera_entity_unavailable_with_only_invalid_images() -> None:
    """Camera entity sollte nicht verfügbar sein, wenn nur ungültige Bilder existieren."""
    hofladen = Hofladen(
        id="test-hof",
        name="Test Hofladen",
        bilder=(Bild(url="file:///etc/passwd", beschreibung="Invalid"),),
    )

    coordinator = create_mock_coordinator(hofladen)
    camera = HofKarteMainImageCamera(coordinator, "test-hof")

    assert camera.available is False


@pytest.mark.asyncio
async def test_camera_entity_unavailable_when_hofladen_deleted() -> None:
    """Camera entity sollte nicht verfügbar sein, wenn der Hofladen gelöscht wurde."""
    coordinator = create_mock_coordinator(None)
    camera = HofKarteMainImageCamera(coordinator, "deleted-hof")

    assert camera.available is False


@pytest.mark.asyncio
async def test_camera_fetch_image_returns_bytes() -> None:
    """Camera sollte Bilddaten als Bytes zurückgeben."""
    hofladen = Hofladen(
        id="test-hof",
        name="Test Hofladen",
        bilder=(Bild(url="https://example.com/image.jpg", beschreibung="Test"),),
    )

    coordinator = create_mock_coordinator(hofladen)
    camera = HofKarteMainImageCamera(coordinator, "test-hof")

    mock_image_data = b"\x89PNG\r\n\x1a\n..."  # Fake PNG header

    with patch.object(camera, "_async_fetch_image", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_image_data

        result = await camera.async_camera_image()

        assert result == mock_image_data
        mock_fetch.assert_called_once_with("https://example.com/image.jpg")


@pytest.mark.asyncio
async def test_camera_fetch_image_returns_none_when_no_image() -> None:
    """Camera sollte None zurückgeben, wenn kein Bild vorhanden ist."""
    hofladen = Hofladen(id="test-hof", name="Test Hofladen", bilder=())

    coordinator = create_mock_coordinator(hofladen)
    camera = HofKarteMainImageCamera(coordinator, "test-hof")

    result = await camera.async_camera_image()

    assert result is None


@pytest.mark.asyncio
async def test_camera_fetch_image_returns_none_when_hofladen_deleted() -> None:
    """Camera sollte None zurückgeben, wenn der Hofladen gelöscht wurde."""
    coordinator = create_mock_coordinator(None)
    camera = HofKarteMainImageCamera(coordinator, "deleted-hof")

    result = await camera.async_camera_image()

    assert result is None


@pytest.mark.asyncio
async def test_camera_name() -> None:
    """Camera sollte einen aussagekräftigen Namen haben."""
    hofladen = Hofladen(id="test-hof", name="Test Hofladen")
    coordinator = create_mock_coordinator(hofladen)
    camera = HofKarteMainImageCamera(coordinator, "test-hof")

    assert camera.name == "Hauptbild"


@pytest.mark.asyncio
async def test_camera_unique_id() -> None:
    """Camera sollte eine eindeutige ID basierend auf Hofladen-ID haben."""
    hofladen = Hofladen(id="unique-hof", name="Test Hofladen")
    coordinator = create_mock_coordinator(hofladen)
    camera = HofKarteMainImageCamera(coordinator, "unique-hof")

    assert camera.unique_id == "hofkarte_unique-hof_hauptbild"
