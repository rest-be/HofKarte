"""Tests für den Config-Entry-Lifecycle der HofKarte-Integration."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hofkarte.const import DOMAIN
from custom_components.hofkarte.coordinator import HofKarteUpdateCoordinator


async def test_domain_is_hofkarte() -> None:
    """Die technische Domain muss gemäss Vorgabe 'hofkarte' sein."""
    assert DOMAIN == "hofkarte"


async def test_setup_entry_loads_without_error(hass: HomeAssistant) -> None:
    """Eine gültige Config Entry muss ohne Fehler eingerichtet werden.

    Der initiale Datenabruf über den Coordinator muss dabei bereits
    erfolgt sein (Daten sind sofort verfügbar, kein zusätzliches Warten
    auf das erste Update-Intervall nötig).
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="HofKarte",
        data={CONF_NAME: "HofKarte"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert result is True
    assert entry.state is ConfigEntryState.LOADED
    assert entry.entry_id in hass.data[DOMAIN]

    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert isinstance(coordinator, HofKarteUpdateCoordinator)
    assert coordinator.last_update_success is True
    assert coordinator.data is not None


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Eine geladene Config Entry muss sauber entladen werden können."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="HofKarte",
        data={CONF_NAME: "HofKarte"},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    unload_result = await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert unload_result is True
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert entry.entry_id not in hass.data.get(DOMAIN, {})
