"""Tests for the RoboVac options flow."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant import data_entry_flow
from homeassistant.const import CONF_ID, CONF_IP_ADDRESS, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant

from custom_components.robovac.const import CONF_AUTODISCOVERY, CONF_VACS, DOMAIN


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add a config entry with two vacuums to Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test-username",
        data={
            CONF_VACS: {
                "test_device_id": {
                    CONF_ID: "test_device_id",
                    CONF_NAME: "Test RoboVac",
                    CONF_MODEL: "T2259",
                    CONF_AUTODISCOVERY: True,
                    CONF_IP_ADDRESS: "192.168.1.100",
                },
                "test_device_id_2": {
                    CONF_ID: "test_device_id_2",
                    CONF_NAME: "Test RoboVac 2",
                    CONF_MODEL: "T2259",
                    CONF_AUTODISCOVERY: False,
                    CONF_IP_ADDRESS: "192.168.1.101",
                },
            }
        },
    )
    entry.add_to_hass(hass)
    return entry


async def _start_edit(hass: HomeAssistant, entry: MockConfigEntry, vacuum_id: str):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"selected_vacuum": vacuum_id}
    )


async def test_options_flow_init_lists_vacuums(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """The init step offers every configured vacuum."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"
    selector = result["data_schema"].schema["selected_vacuum"]
    assert selector.container == {
        "test_device_id": "Test RoboVac",
        "test_device_id_2": "Test RoboVac 2",
    }


async def test_options_flow_edit_defaults(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """The edit step is pre-filled with the selected vacuum's settings."""
    result = await _start_edit(hass, config_entry, "test_device_id_2")

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "edit"
    defaults = {str(key): key.default() for key in result["data_schema"].schema}
    assert defaults == {
        CONF_AUTODISCOVERY: False,
        CONF_IP_ADDRESS: "192.168.1.101",
    }


async def test_options_flow_edit_submit_with_ip(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Submitting the edit step updates only the selected vacuum."""
    result = await _start_edit(hass, config_entry, "test_device_id")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_AUTODISCOVERY: False, CONF_IP_ADDRESS: "192.168.1.200"},
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    vacs = config_entry.data[CONF_VACS]
    assert vacs["test_device_id"][CONF_AUTODISCOVERY] is False
    assert vacs["test_device_id"][CONF_IP_ADDRESS] == "192.168.1.200"
    assert vacs["test_device_id_2"][CONF_IP_ADDRESS] == "192.168.1.101"


async def test_options_flow_edit_submit_without_ip(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """An empty IP address leaves the stored address unchanged."""
    result = await _start_edit(hass, config_entry, "test_device_id")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_AUTODISCOVERY: False, CONF_IP_ADDRESS: ""},
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    vacs = config_entry.data[CONF_VACS]
    assert vacs["test_device_id"][CONF_AUTODISCOVERY] is False
    assert vacs["test_device_id"][CONF_IP_ADDRESS] == "192.168.1.100"
