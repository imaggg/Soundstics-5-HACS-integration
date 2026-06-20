from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.number import SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, SERVICE_TURN_OFF, SERVICE_TURN_ON
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
    CONF_CERT_PEM: "CERT",
    CONF_KEY_PEM: "KEY",
    CONF_UUID: "9051b2f7-084f-3405-812c-1a0fda8c6c05",
    CONF_DEVICE_NAME: "imaggg's SoundSticks",
}

LIGHT_INFO_JSON = {
    "light_info": {
        "enable": "1",
        "brightness": "45",
        "dynamic_level": "2",
        "active_pattern": {"id": "1", "level": "50"},
        "light_element": "1",
    },
    "error_code": "0",
}


def _mock_all_endpoints(aioclient_mock, vol="30", mute="0"):
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        URL,
        params={"command": "getDeviceInfo"},
        json={"error_code": "0", "device_info": {"firmware": "26.22.31.63.00", "name": "imaggg's SoundSticks", "uuid": "9051b2f7-084f-3405-812c-1a0fda8c6c05"}},
    )
    aioclient_mock.get(URL, params={"command": "getLightInfo"}, json=LIGHT_INFO_JSON)
    aioclient_mock.get(URL, params={"command": "getEQList"}, json={"active_eq_id": "1", "eq_list": []})
    aioclient_mock.get(
        URL, params={"command": "getPlayerStatus"}, json={"status": "stop", "vol": vol, "mute": mute, "eq": "0"}
    )
    aioclient_mock.get(
        URL,
        params={"command": "getSmartButtonConfig"},
        json={"smart_config": {"soundscape": {"active_soundscape_id": "1"}, "timer": {"sleep_timer": "0"}}},
    )
    aioclient_mock.get(URL, params={"command": "getSoundscapeV2Config"}, json={"soundscapeV2_list": []})
    aioclient_mock.post(URL, text="")
    # raw GET for setPlayerCmd:vol:N / mute:N — matched without query params
    aioclient_mock.get(f"{URL}?command=setPlayerCmd:vol:70", text="OK")
    aioclient_mock.get(f"{URL}?command=setPlayerCmd:mute:1", text="OK")
    aioclient_mock.get(f"{URL}?command=setPlayerCmd:mute:0", text="OK")


@pytest.fixture
async def setup_entry(hass, enable_custom_integrations, aioclient_mock):
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
    return entry


async def test_volume_number_reflects_state(hass, setup_entry):
    state = hass.states.get("number.imaggg_s_soundsticks_volume")
    assert state is not None
    assert state.state == "30"


async def test_volume_number_set_value_issues_raw_get(hass, setup_entry, aioclient_mock):
    await hass.services.async_call(
        "number", SERVICE_SET_VALUE, {ATTR_ENTITY_ID: "number.imaggg_s_soundsticks_volume", "value": 70}, blocking=True
    )
    calls = [c for c in aioclient_mock.mock_calls if "setPlayerCmd:vol:70" in str(c[1])]
    assert calls, aioclient_mock.mock_calls


async def test_mute_switch_reflects_state(hass, setup_entry):
    state = hass.states.get("switch.imaggg_s_soundsticks_mute")
    assert state is not None
    assert state.state == "off"


async def test_mute_switch_turn_on(hass, setup_entry, aioclient_mock):
    await hass.services.async_call(
        "switch", SERVICE_TURN_ON, {ATTR_ENTITY_ID: "switch.imaggg_s_soundsticks_mute"}, blocking=True
    )
    calls = [c for c in aioclient_mock.mock_calls if "setPlayerCmd:mute:1" in str(c[1])]
    assert calls, aioclient_mock.mock_calls


async def test_mute_switch_turn_off(hass, setup_entry, aioclient_mock):
    await hass.services.async_call(
        "switch", SERVICE_TURN_OFF, {ATTR_ENTITY_ID: "switch.imaggg_s_soundsticks_mute"}, blocking=True
    )
    calls = [c for c in aioclient_mock.mock_calls if "setPlayerCmd:mute:0" in str(c[1])]
    assert calls, aioclient_mock.mock_calls
