"""End-to-end tests for the RoboVac G32 Pro (T2259) against Home Assistant."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED,
    ATTR_FAN_SPEED_LIST,
    DOMAIN as VACUUM_DOMAIN,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_ACCESS_TOKEN,
    CONF_DESCRIPTION,
    CONF_ID,
    CONF_IP_ADDRESS,
    CONF_MAC,
    CONF_MODEL,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from custom_components.robovac.const import CONF_AUTODISCOVERY, CONF_VACS, DOMAIN
from custom_components.robovac.robovac import ModelNotSupportedException, RoboVac
from custom_components.robovac.vacuums import ROBOVAC_MODELS
from custom_components.robovac.vacuums.base import RobovacCommand

DEVICE_ID = "test_g32_id"
VACUUM_ENTITY = "vacuum.g32_pro"

# DPS values as reported by a docked, charging G32 Pro
DOCKED_DPS = {
    "1": True,
    "2": False,
    "3": "forward",
    "5": "Auto",
    "15": "Charging",
    "101": False,
    "102": "Boost_IQ",
    "103": False,
    "104": 87,
    "106": "no_error",
    "107": False,
    "109": 1520,
    "110": 23,
    "135": True,
}


def _vac_config(model: str = "T2259") -> dict:
    return {
        CONF_ID: DEVICE_ID,
        CONF_NAME: "G32 Pro",
        CONF_MODEL: model,
        CONF_DESCRIPTION: "RoboVac G32 Pro",
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
        CONF_IP_ADDRESS: "192.168.1.50",
        CONF_AUTODISCOVERY: False,
        CONF_ACCESS_TOKEN: "0123456789abcdef",
    }


@pytest.fixture
def no_network():
    """Stop the integration from touching the network."""
    with (
        patch(
            "custom_components.robovac.TuyaLocalDiscovery.start",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.robovac.tuyalocalapi.TuyaDevice.process_queue",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.robovac.tuyalocalapi.TuyaDevice.async_get",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.robovac.tuyalocalapi.TuyaDevice.async_set",
            new=AsyncMock(),
        ) as async_set,
    ):
        yield async_set


async def _setup(hass: HomeAssistant, model: str = "T2259") -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="user@example.com",
        unique_id="user@example.com",
        data={CONF_VACS: {DEVICE_ID: _vac_config(model)}},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _push(hass: HomeAssistant, dps: dict) -> None:
    """Simulate the vacuum pushing a state update."""
    entity = hass.data[DOMAIN][CONF_VACS][DEVICE_ID]
    entity.vacuum._dps.update(dps)
    await entity.pushed_update_handler()
    await hass.async_block_till_done()


def test_only_t2259_is_supported() -> None:
    """The fork supports the G32 Pro and nothing else."""
    assert list(ROBOVAC_MODELS) == ["T2259"]


async def test_unknown_model_rejected() -> None:
    """Any other model code is refused."""
    with pytest.raises(ModelNotSupportedException):
        RoboVac(
            model_code="T2118",
            device_id=DEVICE_ID,
            host="192.168.1.50",
            local_key="0123456789abcdef",
            timeout=1,
            ping_interval=10,
            update_entity_state=AsyncMock(),
        )


async def test_dps_codes(no_network) -> None:
    """DPS codes come from the T2259 command table."""
    vac = RoboVac(
        model_code="T2259",
        device_id=DEVICE_ID,
        host="192.168.1.50",
        local_key="0123456789abcdef",
        timeout=1,
        ping_interval=10,
        update_entity_state=AsyncMock(),
    )
    assert vac.getDpsCodes() == {
        "START_PAUSE": "2",
        "DIRECTION": "3",
        "MODE": "5",
        "STATUS": "15",
        "RETURN_HOME": "101",
        "FAN_SPEED": "102",
        "LOCATE": "103",
        "BATTERY_LEVEL": "104",
        "ERROR_CODE": "106",
    }
    assert vac.getFanSpeeds() == ["Standard", "Turbo", "Max", "Boost_IQ"]
    assert vac.getRoboVacCommandValue(RobovacCommand.MODE, "small_room") == "SmallRoom"


async def test_setup_creates_entities(hass: HomeAssistant, no_network) -> None:
    """Setting up the entry creates the vacuum and battery sensor."""
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED

    registry = er.async_get(hass)
    entities = {
        e.entity_id: e.unique_id
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    assert entities == {
        VACUUM_ENTITY: DEVICE_ID,
        "sensor.g32_pro_battery": f"{DEVICE_ID}_battery",
    }

    state = hass.states.get(VACUUM_ENTITY)
    assert state is not None
    features = VacuumEntityFeature(state.attributes[ATTR_SUPPORTED_FEATURES])
    assert features == (
        VacuumEntityFeature.CLEAN_SPOT
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.LOCATE
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.SEND_COMMAND
        | VacuumEntityFeature.START
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.STOP
    )
    assert state.attributes[ATTR_FAN_SPEED_LIST] == [
        "Standard",
        "Turbo",
        "Max",
        "Boost_IQ",
    ]

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_docked_state(
    hass: HomeAssistant, no_network, caplog: pytest.LogCaptureFixture
) -> None:
    """A pushed update is reflected in the vacuum and battery sensor."""
    await _setup(hass)
    await _push(hass, DOCKED_DPS)
    assert "not found for model" not in caplog.text

    state = hass.states.get(VACUUM_ENTITY)
    assert state.state == VacuumActivity.DOCKED
    assert state.attributes[ATTR_FAN_SPEED] == "Boost IQ"
    assert state.attributes["mode"] == "Auto"
    assert state.attributes["cleaning_time"] == "1520"
    assert state.attributes["cleaning_area"] == "23"
    assert state.attributes["auto_return"] == "True"
    assert state.attributes["do_not_disturb"] == "False"
    assert "error" not in state.attributes
    assert "battery_level" not in state.attributes

    battery = "sensor.g32_pro_battery"
    await async_update_entity(hass, battery)
    assert hass.states.get(battery).state == "87"


@pytest.mark.parametrize(
    ("status", "activity"),
    [
        ("Charging", VacuumActivity.DOCKED),
        ("completed", VacuumActivity.DOCKED),
        ("Recharge", VacuumActivity.RETURNING),
        ("Sleeping", VacuumActivity.IDLE),
        ("standby", VacuumActivity.IDLE),
        ("Paused", VacuumActivity.PAUSED),
        ("Running", VacuumActivity.CLEANING),
    ],
)
async def test_status_mapping(
    hass: HomeAssistant, no_network, status: str, activity: VacuumActivity
) -> None:
    """Raw G32 statuses map to Home Assistant activities."""
    await _setup(hass)
    await _push(hass, {**DOCKED_DPS, "15": status})
    assert hass.states.get(VACUUM_ENTITY).state == activity


async def test_error_state(hass: HomeAssistant, no_network) -> None:
    """A non-zero error code puts the vacuum into the error state."""
    await _setup(hass)
    await _push(hass, {**DOCKED_DPS, "15": "Running", "106": "Wheel_stuck"})

    state = hass.states.get(VACUUM_ENTITY)
    assert state.state == VacuumActivity.ERROR
    assert state.attributes["error"] == "Wheel stuck"


@pytest.mark.parametrize(
    ("service", "data", "expected"),
    [
        ("start", {}, {"5": "Auto"}),
        ("pause", {}, {"2": "pause"}),
        ("stop", {}, {"101": "return"}),
        ("return_to_base", {}, {"101": "return"}),
        ("clean_spot", {}, {"5": "Spot"}),
        ("locate", {}, {"103": True}),
        ("set_fan_speed", {"fan_speed": "Boost IQ"}, {"102": "Boost_IQ"}),
        ("set_fan_speed", {"fan_speed": "Standard"}, {"102": "Standard"}),
        ("send_command", {"command": "edgeClean"}, {"5": "Edge"}),
        ("send_command", {"command": "smallRoomClean"}, {"5": "SmallRoom"}),
        ("send_command", {"command": "autoClean"}, {"5": "Auto"}),
        ("send_command", {"command": "autoReturn"}, {"135": False}),
        ("send_command", {"command": "doNotDisturb"}, {"107": True}),
    ],
)
async def test_services(
    hass: HomeAssistant, no_network, service: str, data: dict, expected: dict
) -> None:
    """Home Assistant vacuum services send the expected DPS values."""
    await _setup(hass)
    await _push(hass, DOCKED_DPS)
    no_network.reset_mock()

    await hass.services.async_call(
        VACUUM_DOMAIN,
        service,
        {ATTR_ENTITY_ID: VACUUM_ENTITY, **data},
        blocking=True,
    )
    no_network.assert_awaited_once_with(expected)


async def test_unsupported_model_entry(hass: HomeAssistant, no_network) -> None:
    """An entry for another model loads but exposes no features."""
    await _setup(hass, model="T2118")

    state = hass.states.get(VACUUM_ENTITY)
    assert state is not None
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
