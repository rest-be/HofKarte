"""Gemeinsame Test-Fixtures für die HofKarte-Tests."""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Aktiviert das Laden von Custom Integrations in allen Tests.

    ``enable_custom_integrations`` wird von
    ``pytest-homeassistant-custom-component`` bereitgestellt. Ohne diese
    Fixture ignoriert Home Assistant in Tests standardmässig alle
    ``custom_components``.
    """
    yield
