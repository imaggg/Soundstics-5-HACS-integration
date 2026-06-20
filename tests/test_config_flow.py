from ipaddress import ip_address
from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.data_entry_flow import FlowResultType

from custom_components.soundsticks.const import DOMAIN

FAKE_DEVICE_INFO = {
    "name": "imaggg's SoundSticks",
    "uuid": "9051b2f7-084f-3405-812c-1a0fda8c6c05",
    "firmware": "26.22.31.63.00",
}


@pytest.fixture(autouse=True)
def mock_validate():
    with (
        patch(
            "custom_components.soundsticks.config_flow._async_validate_cert",
            return_value=FAKE_DEVICE_INFO,
        ),
        patch(
            "custom_components.soundsticks.config_flow._async_confirm_upnp",
            return_value=True,
        ),
    ):
        yield


async def test_user_flow_creates_entry(hass, enable_custom_integrations):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": "192.168.1.97"})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "cert"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"cert_pem": "CERT", "key_pem": "KEY"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "imaggg's SoundSticks"
    assert result["data"]["host"] == "192.168.1.97"
    assert result["data"]["uuid"] == FAKE_DEVICE_INFO["uuid"]
    assert result["data"]["cert_pem"] == "CERT"


async def test_zeroconf_flow_creates_entry(hass, enable_custom_integrations):
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.97"),
        ip_addresses=[ip_address("192.168.1.97")],
        port=443,
        hostname="audiocast_ABCD.local.",
        type="_jbl-product._tcp.local.",
        name="imaggg's SoundSticks._jbl-product._tcp.local.",
        properties={},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=discovery_info
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "cert"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"cert_pem": "CERT", "key_pem": "KEY"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["host"] == "192.168.1.97"


async def test_zeroconf_duplicate_aborts(hass, enable_custom_integrations):
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.97"),
        ip_addresses=[ip_address("192.168.1.97")],
        port=443,
        hostname="audiocast_ABCD.local.",
        type="_jbl-product._tcp.local.",
        name="imaggg's SoundSticks._jbl-product._tcp.local.",
        properties={},
    )
    # First flow completes and creates the entry.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=discovery_info
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"cert_pem": "CERT", "key_pem": "KEY"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Second discovery of the same hostname should abort early (before cert step).
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=discovery_info
    )
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_cert_step_invalid_cert_shows_error(hass, enable_custom_integrations):
    from custom_components.soundsticks.config_flow import InvalidCert

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"host": "192.168.1.97"})

    with patch(
        "custom_components.soundsticks.config_flow._async_validate_cert",
        side_effect=InvalidCert,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"cert_pem": "bad", "key_pem": "bad"}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "cert"
    assert result["errors"] == {"base": "invalid_cert"}
