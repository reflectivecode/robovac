"""Tests for the RoboVac config flow."""

from unittest.mock import patch, MagicMock
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_ACCESS_TOKEN,
    CONF_NAME,
    CONF_ID,
    CONF_MODEL,
    CONF_IP_ADDRESS,
    CONF_DESCRIPTION,
    CONF_MAC,
    CONF_CLIENT_ID,
    CONF_REGION,
    CONF_TIME_ZONE,
    CONF_COUNTRY_CODE,
)
from homeassistant.core import HomeAssistant

from custom_components.robovac.const import DOMAIN, CONF_AUTODISCOVERY, CONF_VACS


@pytest.fixture
def mock_eufy_response():
    """Create a mock response from the Eufy API."""
    user_info_response = MagicMock()
    user_info_response.status_code = 200
    user_info_response.json.return_value = {
        "res_code": 1,
        "user_info": {
            "id": "test_client_id",
            "request_host": "test_host",
            "phone_code": "44",
            "country": "GB",
            "timezone": "Europe/London",
        },
        "access_token": "test_access_token",
    }

    device_info_response = MagicMock()
    device_info_response.json.return_value = {
        "devices": [
            {
                "id": "test_device_id",
                "product": {
                    "appliance": "Cleaning",
                    "product_code": "T2259",
                },
                "alias_name": "Test RoboVac",
                "name": "RoboVac G32 Pro",
                "wifi": {"mac": "AA:BB:CC:DD:EE:FF"},
            }
        ]
    }

    settings_response = MagicMock()
    settings_response.json.return_value = {
        "setting": {
            "home_setting": {
                "tuya_home": {
                    "tuya_region_code": "EU",
                }
            }
        }
    }

    return {
        "user_info": user_info_response,
        "device_info": device_info_response,
        "settings": settings_response,
    }


@pytest.fixture
def mock_tuya_device():
    """Create a mock Tuya device response."""
    return {"localKey": "test_local_key"}


@pytest.mark.asyncio
async def test_user_form(hass: HomeAssistant):
    """Test we get the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_user_form_cannot_connect(hass: HomeAssistant, mock_eufy_response):
    """Test we handle cannot connect error."""
    # Mock the EufyLogon.get_user_info to return a 400 status code
    mock_eufy_response["user_info"].status_code = 400

    with patch(
        "custom_components.robovac.config_flow.EufyLogon",
        return_value=MagicMock(
            get_user_info=MagicMock(return_value=mock_eufy_response["user_info"])
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_user_form_invalid_auth(hass: HomeAssistant, mock_eufy_response):
    """Test we handle invalid auth error."""
    # Mock the EufyLogon.get_user_info to return a 200 status code but res_code != 1
    mock_eufy_response["user_info"].json.return_value["res_code"] = 0

    with patch(
        "custom_components.robovac.config_flow.EufyLogon",
        return_value=MagicMock(
            get_user_info=MagicMock(return_value=mock_eufy_response["user_info"])
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.asyncio
async def test_user_form_unexpected_exception(hass: HomeAssistant):
    """Test we handle unexpected exception."""
    with patch(
        "custom_components.robovac.config_flow.EufyLogon",
        side_effect=Exception("Unexpected error"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


@pytest.mark.asyncio
async def test_user_form_success(
    hass: HomeAssistant, mock_eufy_response, mock_tuya_device
):
    """Test successful form submission."""
    with (
        patch(
            "custom_components.robovac.config_flow.EufyLogon",
            return_value=MagicMock(
                get_user_info=MagicMock(return_value=mock_eufy_response["user_info"]),
                get_device_info=MagicMock(
                    return_value=mock_eufy_response["device_info"]
                ),
                get_user_settings=MagicMock(
                    return_value=mock_eufy_response["settings"]
                ),
            ),
        ),
        patch(
            "custom_components.robovac.config_flow.TuyaAPISession",
            return_value=MagicMock(get_device=MagicMock(return_value=mock_tuya_device)),
        ),
        patch("custom_components.robovac.async_setup", return_value=True),
        patch("custom_components.robovac.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"][CONF_USERNAME] == "test-username"
    assert result["data"][CONF_PASSWORD] == "test-password"
    assert result["data"][CONF_CLIENT_ID] == "test_client_id"
    assert result["data"][CONF_REGION] == "EU"
    assert result["data"][CONF_COUNTRY_CODE] == "44"
    assert result["data"][CONF_TIME_ZONE] == "Europe/London"
    assert CONF_VACS in result["data"]
    assert "test_device_id" in result["data"][CONF_VACS]
    assert result["data"][CONF_VACS]["test_device_id"][CONF_ID] == "test_device_id"
    assert result["data"][CONF_VACS]["test_device_id"][CONF_MODEL] == "T2259"
    assert result["data"][CONF_VACS]["test_device_id"][CONF_NAME] == "Test RoboVac"
    assert (
        result["data"][CONF_VACS]["test_device_id"][CONF_DESCRIPTION] == "RoboVac G32 Pro"
    )
    assert result["data"][CONF_VACS]["test_device_id"][CONF_MAC] == "AA:BB:CC:DD:EE:FF"
    assert result["data"][CONF_VACS]["test_device_id"][CONF_IP_ADDRESS] == ""
    assert result["data"][CONF_VACS]["test_device_id"][CONF_AUTODISCOVERY] is True
    assert (
        result["data"][CONF_VACS]["test_device_id"][CONF_ACCESS_TOKEN]
        == "test_local_key"
    )
