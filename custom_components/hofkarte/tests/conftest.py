"""Gemeinsame Test-Fixtures für die HofKarte-Tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, PropertyMock

import pytest

from custom_components.hofkarte.models import Hofladen


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Aktiviert das Laden von Custom Integrations in allen Tests.

    ``enable_custom_integrations`` wird von
    ``pytest-homeassistant-custom-component`` bereitgestellt. Ohne diese
    Fixture ignoriert Home Assistant in Tests standardmässig alle
    ``custom_components``.
    """
    yield


def create_mock_coordinator(hofladen: Hofladen | None = None) -> MagicMock:
    """Erstellt einen Mock Coordinator für Tests.

    Args:
        hofladen: Der zu verwendende Hofladen oder None, wenn keine Daten
                  verfügbar sein sollen.

    Returns:
        Ein Mock Coordinator mit einer konfigurierten data Eigenschaft und
        available=True.
    """
    coordinator = MagicMock()
    if hofladen is not None:
        coordinator.data = {hofladen.id: hofladen}
    else:
        coordinator.data = {}
    # available Property für die Entity-Basisklasse
    type(coordinator).available = PropertyMock(return_value=True)
    return coordinator
