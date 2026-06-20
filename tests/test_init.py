from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.soundsticks.const import (
    CONF_CERT_PEM,
    CONF_DEVICE_NAME,
    CONF_KEY_PEM,
    CONF_UUID,
    DOMAIN,
)

HOST = "192.168.1.97"
URL = f"https://{HOST}/httpapi.asp"

FAKE_DATA = {
    CONF_HOST: HOST,
    CONF_CERT_PEM: "CERT PEM CONTENT",
    CONF_KEY_PEM: "KEY PEM CONTENT",
    CONF_UUID: "9051b2f7-084f-3405-812c-1a0fda8c6c05",
    CONF_DEVICE_NAME: "imaggg's SoundSticks",
}

LIGHT_INFO_JSON = {
    "light_info": {
        "enable": "0",
        "brightness": "45",
        "dynamic_level": "2",
        "active_pattern": {"id": "1", "level": "50"},
        "light_element": "1",
    },
    "error_code": "0",
}
EQ_LIST_JSON = {"active_eq_id": "1", "eq_list": []}
PLAYER_STATUS_JSON = {"status": "stop", "vol": "30", "mute": "0", "eq": "0"}
SMART_BUTTON_JSON = {"smart_config": {"soundscape": {"active_soundscape_id": "1"}, "timer": {"sleep_timer": "0"}}}
SOUNDSCAPE_JSON = {"soundscapeV2_list": []}


def _mock_all_endpoints(aioclient_mock):
    aioclient_mock.get(
        URL,
        params={"command": "getDeviceInfo"},
        json={"error_code": "0", "device_info": {"firmware": "26.22.31.63.00", "name": "imaggg's SoundSticks", "uuid": "9051b2f7-084f-3405-812c-1a0fda8c6c05"}},
    )
    aioclient_mock.get(URL, params={"command": "getLightInfo"}, json=LIGHT_INFO_JSON)
    aioclient_mock.get(URL, params={"command": "getEQList"}, json=EQ_LIST_JSON)
    aioclient_mock.get(URL, params={"command": "getPlayerStatus"}, json=PLAYER_STATUS_JSON)
    aioclient_mock.get(URL, params={"command": "getSmartButtonConfig"}, json=SMART_BUTTON_JSON)
    aioclient_mock.get(URL, params={"command": "getSoundscapeV2Config"}, json=SOUNDSCAPE_JSON)


async def test_setup_and_unload_entry(hass, enable_custom_integrations, aioclient_mock):
    entry = MockConfigEntry(
        domain=DOMAIN, title=FAKE_DATA[CONF_DEVICE_NAME], unique_id=FAKE_DATA[CONF_UUID], data=FAKE_DATA
    )
    entry.add_to_hass(hass)
    _mock_all_endpoints(aioclient_mock)

    with (
        patch("custom_components.soundsticks.build_ssl_context"),
        patch(
            "custom_components.soundsticks.async_write_cert_files",
            new=AsyncMock(return_value=("/tmp/cert.pem", "/tmp/key.pem")),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        coordinator = entry.runtime_data
        assert coordinator.data.light.brightness == 45
        assert coordinator.data.light.enable is False
        assert coordinator.data.eq.active_eq_id == 1
        assert coordinator.data.player.vol == 30
        assert coordinator.data.smart_button.soundscape_id == 1
        assert coordinator.data.soundscape == []

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_not_ready_on_transport_error(hass, enable_custom_integrations, aioclient_mock):
    entry = MockConfigEntry(
        domain=DOMAIN, title=FAKE_DATA[CONF_DEVICE_NAME], unique_id=FAKE_DATA[CONF_UUID], data=FAKE_DATA
    )
    entry.add_to_hass(hass)
    # getLightInfo deliberately left unmocked -> aioclient_mock raises AssertionError,
    # which the coordinator should turn into a setup-retry, not a crash.

    with (
        patch("custom_components.soundsticks.build_ssl_context"),
        patch(
            "custom_components.soundsticks.async_write_cert_files",
            new=AsyncMock(return_value=("/tmp/cert.pem", "/tmp/key.pem")),
        ),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.SETUP_RETRY
