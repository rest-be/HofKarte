"""Tests für den HofKarte-Config-Flow."""

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hofkarte.const import DEFAULT_NAME, DOMAIN


async def test_form_shown(hass: HomeAssistant) -> None:
    """Der erste Aufruf muss das Eingabeformular anzeigen."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Eine gültige Eingabe muss eine Config Entry erzeugen."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "Mein Hofladen-Netzwerk"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Mein Hofladen-Netzwerk"
    assert result["data"] == {CONF_NAME: "Mein Hofladen-Netzwerk"}


async def test_user_flow_default_name(hass: HomeAssistant) -> None:
    """Das Formular muss den Standardnamen als Vorschlag enthalten."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    schema = result["data_schema"].schema
    name_key = next(key for key in schema if key == CONF_NAME)
    assert name_key.default() == DEFAULT_NAME


async def test_user_flow_invalid_empty_name(hass: HomeAssistant) -> None:
    """Ein leerer bzw. nur aus Leerzeichen bestehender Name muss abgelehnt werden."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "   "},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_NAME: "invalid_name"}


async def test_user_flow_duplicate_setup_aborts(hass: HomeAssistant) -> None:
    """Eine zweite Einrichtung muss abgebrochen werden (Single Instance)."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data={CONF_NAME: DEFAULT_NAME},
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
