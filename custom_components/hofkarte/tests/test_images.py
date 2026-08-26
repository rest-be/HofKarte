"""Tests für die sichere Bildverarbeitung (images.py)."""

from __future__ import annotations

import pytest

from custom_components.hofkarte.images import (
    build_images_attribute,
    get_main_image_url,
    is_valid_image_url,
)
from custom_components.hofkarte.models import Bild


class TestIsValidImageUrl:
    """Tests für die URL-Validierung."""

    def test_valid_https_url(self) -> None:
        """HTTPS URLs sollten akzeptiert werden."""
        assert is_valid_image_url("https://example.com/image.jpg")

    def test_valid_http_url(self) -> None:
        """HTTP URLs sollten akzeptiert werden."""
        assert is_valid_image_url("http://example.com/image.png")

    def test_https_url_with_path_and_query(self) -> None:
        """HTTPS URLs mit Pfad und Query sollten akzeptiert werden."""
        assert is_valid_image_url(
            "https://cdn.example.com/images/farm/12345/main.jpg?size=large&v=1"
        )

    def test_file_url_rejected(self) -> None:
        """file:// URLs sollten abgelehnt werden (Sicherheit)."""
        assert not is_valid_image_url("file:///etc/passwd")
        assert not is_valid_image_url("file://localhost/path/to/image.jpg")

    def test_data_url_rejected(self) -> None:
        """data: URLs sollten abgelehnt werden."""
        assert not is_valid_image_url("data:image/png;base64,iVBORw0KGgoAAAANS...")

    def test_ftp_url_rejected(self) -> None:
        """FTP und andere Protokolle sollten abgelehnt werden."""
        assert not is_valid_image_url("ftp://example.com/image.jpg")

    def test_empty_string_rejected(self) -> None:
        """Leere Strings sollten abgelehnt werden."""
        assert not is_valid_image_url("")

    def test_whitespace_only_rejected(self) -> None:
        """Nur Whitespace sollte abgelehnt werden."""
        assert not is_valid_image_url("   ")
        assert not is_valid_image_url("\t\n")

    def test_none_rejected(self) -> None:
        """None sollte abgelehnt werden."""
        assert not is_valid_image_url(None)

    def test_non_string_rejected(self) -> None:
        """Nicht-Strings sollten abgelehnt werden."""
        assert not is_valid_image_url(123)  # type: ignore
        assert not is_valid_image_url(["https://example.com"])  # type: ignore
        assert not is_valid_image_url({"url": "https://example.com"})  # type: ignore

    def test_url_without_netloc_rejected(self) -> None:
        """URLs ohne Netzwerk-Location sollten abgelehnt werden."""
        assert not is_valid_image_url("https://")
        assert not is_valid_image_url("http://")

    def test_url_with_leading_whitespace_stripped(self) -> None:
        """URLs mit führendem Whitespace sollten nach dem Trimmen validiert werden."""
        assert is_valid_image_url("  https://example.com/image.jpg")

    def test_url_with_trailing_whitespace_stripped(self) -> None:
        """URLs mit nachfolgendem Whitespace sollten nach dem Trimmen validiert werden."""
        assert is_valid_image_url("https://example.com/image.jpg  ")

    def test_malformed_url(self) -> None:
        """Ungültige URLs sollten abgelehnt werden."""
        assert not is_valid_image_url("not a url")
        assert not is_valid_image_url("ht!tp://example.com")


class TestGetMainImageUrl:
    """Tests für die Ermittlung des Hauptbildes."""

    def test_first_valid_image_is_main(self) -> None:
        """Das erste gültige Bild sollte das Hauptbild sein."""
        bilder = (
            Bild(url="https://example.com/image1.jpg", beschreibung="Bild 1"),
            Bild(url="https://example.com/image2.jpg", beschreibung="Bild 2"),
        )
        assert get_main_image_url(bilder) == "https://example.com/image1.jpg"

    def test_skips_invalid_images(self) -> None:
        """Ungültige Bilder sollten übersprungen werden."""
        bilder = (
            Bild(url="file:///etc/passwd", beschreibung="Invalid"),
            Bild(url="https://example.com/valid.jpg", beschreibung="Valid"),
        )
        assert get_main_image_url(bilder) == "https://example.com/valid.jpg"

    def test_empty_tuple_returns_none(self) -> None:
        """Ein leeres Tupel sollte None zurückgeben."""
        assert get_main_image_url(()) is None

    def test_all_invalid_images_returns_none(self) -> None:
        """Wenn alle Bilder ungültig sind, sollte None zurückgeben."""
        bilder = (
            Bild(url="file:///etc/passwd", beschreibung="Invalid 1"),
            Bild(url="data:image/png;base64,xxx", beschreibung="Invalid 2"),
            Bild(url="", beschreibung="Empty"),
        )
        assert get_main_image_url(bilder) is None

    def test_single_valid_image(self) -> None:
        """Ein einzelnes gültiges Bild sollte das Hauptbild sein."""
        bilder = (Bild(url="https://example.com/only.jpg", beschreibung="Einzig"),)
        assert get_main_image_url(bilder) == "https://example.com/only.jpg"


class TestBuildImagesAttribute:
    """Tests für die Strukturierung von Bildattributen."""

    def test_empty_bilder_returns_empty_structure(self) -> None:
        """Ein leeres Tupel sollte eine leere Struktur zurückgeben."""
        result = build_images_attribute(())
        assert result == {"primary_image": None, "images": []}

    def test_single_valid_image(self) -> None:
        """Ein einzelnes gültiges Bild sollte als primary_image und in images List erscheinen."""
        bilder = (Bild(url="https://example.com/image.jpg", beschreibung="Hauptbild"),)
        result = build_images_attribute(bilder)

        assert result["primary_image"] == "https://example.com/image.jpg"
        assert len(result["images"]) == 1
        assert result["images"][0]["url"] == "https://example.com/image.jpg"
        assert result["images"][0]["description"] == "Hauptbild"

    def test_multiple_valid_images(self) -> None:
        """Mehrere gültige Bilder sollten alle in images enthalten sein, erste als primary."""
        bilder = (
            Bild(url="https://example.com/img1.jpg", beschreibung="Erste"),
            Bild(url="https://example.com/img2.jpg", beschreibung="Zweite"),
            Bild(url="https://example.com/img3.jpg", beschreibung=None),
        )
        result = build_images_attribute(bilder)

        assert result["primary_image"] == "https://example.com/img1.jpg"
        assert len(result["images"]) == 3
        assert result["images"][0]["url"] == "https://example.com/img1.jpg"
        assert result["images"][0]["description"] == "Erste"
        assert result["images"][1]["url"] == "https://example.com/img2.jpg"
        assert result["images"][1]["description"] == "Zweite"
        assert result["images"][2]["url"] == "https://example.com/img3.jpg"
        assert "description" not in result["images"][2]

    def test_filters_invalid_images(self) -> None:
        """Ungültige Bilder sollten gefiltert werden."""
        bilder = (
            Bild(url="file:///etc/passwd", beschreibung="Invalid"),
            Bild(url="https://example.com/valid.jpg", beschreibung="Valid"),
        )
        result = build_images_attribute(bilder)

        assert result["primary_image"] == "https://example.com/valid.jpg"
        assert len(result["images"]) == 1
        assert result["images"][0]["url"] == "https://example.com/valid.jpg"

    def test_all_invalid_images(self) -> None:
        """Wenn alle Bilder ungültig sind, sollte ein leeres Struktur zurückgeben."""
        bilder = (
            Bild(url="", beschreibung="Empty"),
            Bild(url="ftp://example.com/img.jpg", beschreibung="FTP"),
        )
        result = build_images_attribute(bilder)

        assert result["primary_image"] is None
        assert result["images"] == []

    def test_image_without_description(self) -> None:
        """Bilder ohne Beschreibung sollten kein description Feld enthalten."""
        bilder = (Bild(url="https://example.com/nodesc.jpg", beschreibung=None),)
        result = build_images_attribute(bilder)

        assert len(result["images"]) == 1
        assert "description" not in result["images"][0]

    def test_image_with_empty_description(self) -> None:
        """Bilder mit leerer Beschreibung sollten kein description Feld enthalten."""
        bilder = (Bild(url="https://example.com/emptydesc.jpg", beschreibung=""),)
        result = build_images_attribute(bilder)

        assert len(result["images"]) == 1
        # Leere Strings werden als falsy behandelt
        assert "description" not in result["images"][0]

    def test_json_serializable(self) -> None:
        """Das Ergebnis sollte JSON-serialisierbar sein."""
        import json

        bilder = (
            Bild(url="https://example.com/img1.jpg", beschreibung="Bild 1"),
            Bild(url="https://example.com/img2.jpg", beschreibung=None),
        )
        result = build_images_attribute(bilder)

        # Sollte keine Fehler werfen
        json_str = json.dumps(result)
        assert json_str

        # Sollte zurück parsebar sein
        parsed = json.loads(json_str)
        assert parsed["primary_image"] == "https://example.com/img1.jpg"
        assert len(parsed["images"]) == 2
