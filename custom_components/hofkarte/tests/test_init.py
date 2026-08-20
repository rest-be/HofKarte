"""Tests für das HofKarte-Grundgerüst (Einheit 1)."""

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.hofkarte.const import DOMAIN


async def test_domain_is_hofkarte() -> None:
    """Die technische Domain muss gemäss Vorgabe 'hofkarte' sein."""
    assert DOMAIN == "hofkarte"


async def test_setup_integration_loads_without_error(hass: HomeAssistant) -> None:
    """Home Assistant muss die Integration ohne Fehler laden können."""
    result = await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert result is True
    assert DOMAIN in hass.data
