import json
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.number import SERVICE_SET_VALUE
from homeassistant.components.select import SERVICE_SELECT_OPTION
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

SMART_BUTTON_JSON = {
    "error_code": "0",
    "smart_config": {
        "atmos": {"atmos_level": 0, "status": "off"},
        "music": {"album_cover": "", "music_id": ""},
        "soundscape": {"active_soundscape_id": 1, "supported_list": [1, 2, 3, 4, 0]},
        "soundscapeV2": {"mix_with_music": "disabled", "percent_of_volume": 70},
        "timer": {"sleep_timer": 0, "timer_status": "disabled"},
    },
}

# Real shape captured live from the device.
SOUNDSCAPE_JSON = {
    "soundscapeV2_list": [
        {"soundscape_id": 4, "element_list": [{"id": 2, "value": 46}, {"id": 1, "value": 54}, {"id": 0, "value": 47}]},
        {"soundscape_id": 1, "element_list": [{"id": 2, "value": 16}, {"id": 1, "value": 9}, {"id": 0, "value": 56}]},
        {"soundscape_id": 3, "element_list": [{"id": 2, "value": 10}, {"id": 1, "value": 31}, {"id": 0, "value": 80}]},
        {"soundscape_id": 2, "element_list": [{"id": 2, "value": 0}, {"id": 1, "value": 47}, {"id": 0, "value": 69}]},
    ]
}


def _mock_all_endpoints(aioclient_mock):
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        URL,
        params={"command": "getDeviceInfo"},
        json={"error_code": "0", "device_info": {"firmware": "26.22.31.63.00", "name": "imaggg's SoundSticks", "uuid": "9051b2f7-084f-3405-812c-1a0fda8c6c05"}},
    )
    aioclient_mock.get(URL, params={"command": "getLightInfo"}, json=LIGHT_INFO_JSON)
    aioclient_mock.get(URL, params={"command": "getEQList"}, json={"active_eq_id": "1", "eq_list": []})
    aioclient_mock.get(URL, params={"command": "getPlayerStatus"}, json={"status": "stop", "vol": "30", "mute": "0", "eq": "0"})
    aioclient_mock.get(URL, params={"command": "getSmartButtonConfig"}, json=SMART_BUTTON_JSON)
    aioclient_mock.get(URL, params={"command": "getSoundscapeV2Config"}, json=SOUNDSCAPE_JSON)
    aioclient_mock.post(URL, text="")


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


def _all_post_payloads(aioclient_mock):
    out = []
    for method, url, data, _headers in aioclient_mock.mock_calls:
        if method.lower() == "post":
            body = data if isinstance(data, str) else data.decode()
            command, payload_json = body.split("&payload=", 1)
            out.append((command.removeprefix("command="), json.loads(payload_json)))
    return out


def _raw_get_commands(aioclient_mock):
    return [str(url) for method, url, _data, _headers in aioclient_mock.mock_calls if method.lower() == "get"]


async def test_moment_mode_select_reflects_active_mode(hass, setup_entry):
    state = hass.states.get("select.imaggg_s_soundsticks_moment_mode")
    assert state is not None
    assert state.state == "Forest"  # soundscape_id=1
    assert set(state.attributes["options"]) == {"Forest", "Rain", "Ocean", "City"}


async def test_moment_sleep_timer_select_reflects_state(hass, setup_entry):
    state = hass.states.get("select.imaggg_s_soundsticks_moment_sleep_timer")
    assert state.state == "Off"


async def test_moment_volume_number_reflects_state(hass, setup_entry):
    state = hass.states.get("number.imaggg_s_soundsticks_moment_volume")
    assert state.state == "70"


async def test_moment_switch_initially_off(hass, setup_entry):
    state = hass.states.get("switch.imaggg_s_soundsticks_moment")
    assert state.state == "off"


async def test_moment_element_sliders_read_active_mode(hass, setup_entry):
    # active mode = soundscape_id 1 (Forest): elements id2=16(slider0), id1=9(slider1), id0=56(slider2)
    s0 = hass.states.get("number.imaggg_s_soundsticks_moment_element_1")
    s1 = hass.states.get("number.imaggg_s_soundsticks_moment_element_2")
    s2 = hass.states.get("number.imaggg_s_soundsticks_moment_element_3")
    assert float(s0.state) == 16
    assert float(s1.state) == 9
    assert float(s2.state) == 56


async def test_moment_turn_on_sets_config_then_starts(hass, setup_entry, aioclient_mock):
    await hass.services.async_call(
        "switch", SERVICE_TURN_ON, {ATTR_ENTITY_ID: "switch.imaggg_s_soundsticks_moment"}, blocking=True
    )
    payloads = _all_post_payloads(aioclient_mock)
    set_config_calls = [p for c, p in payloads if c == "setSmartButtonConfig"]
    control_calls = [p for c, p in payloads if c == "controlSoundscapeV2"]
    assert set_config_calls, payloads
    assert set_config_calls[-1]["soundscape"]["active_soundscape_id"] == 1
    assert control_calls, payloads
    assert control_calls[-1] == {"action_id": 6, "autoResume": True, "fadeOut": "true", "soundscape_id": 1}

    state = hass.states.get("switch.imaggg_s_soundsticks_moment")
    assert state.state == "on"


async def test_moment_turn_off_stops(hass, setup_entry, aioclient_mock):
    await hass.services.async_call(
        "switch", SERVICE_TURN_ON, {ATTR_ENTITY_ID: "switch.imaggg_s_soundsticks_moment"}, blocking=True
    )
    await hass.services.async_call(
        "switch", SERVICE_TURN_OFF, {ATTR_ENTITY_ID: "switch.imaggg_s_soundsticks_moment"}, blocking=True
    )
    payloads = _all_post_payloads(aioclient_mock)
    control_calls = [p for c, p in payloads if c == "controlSoundscapeV2"]
    assert control_calls[-1] == {"action_id": 7, "autoResume": True, "fadeOut": "true", "soundscape_id": 1}

    state = hass.states.get("switch.imaggg_s_soundsticks_moment")
    assert state.state == "off"


async def test_moment_mode_select_switch_stops_prev_and_starts_new(hass, setup_entry, aioclient_mock):
    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.imaggg_s_soundsticks_moment_mode", "option": "Rain"},
        blocking=True,
    )
    payloads = _all_post_payloads(aioclient_mock)
    control_calls = [p for c, p in payloads if c == "controlSoundscapeV2"]
    # stop Forest(1), then start Rain(2)
    assert control_calls[0] == {"action_id": 7, "autoResume": True, "fadeOut": "true", "soundscape_id": 1}
    assert control_calls[1] == {"action_id": 6, "autoResume": True, "fadeOut": "true", "soundscape_id": 2}

    set_config_calls = [p for c, p in payloads if c == "setSmartButtonConfig"]
    assert set_config_calls[-1]["soundscape"]["active_soundscape_id"] == 2


async def test_moment_sleep_timer_select_updates_config_only(hass, setup_entry, aioclient_mock):
    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.imaggg_s_soundsticks_moment_sleep_timer", "option": "30 min"},
        blocking=True,
    )
    payloads = _all_post_payloads(aioclient_mock)
    control_calls = [p for c, p in payloads if c == "controlSoundscapeV2"]
    assert not control_calls  # must not start/stop playback
    set_config_calls = [p for c, p in payloads if c == "setSmartButtonConfig"]
    assert set_config_calls[-1]["timer"] == {"sleep_timer": 1800, "timer_status": "enabled"}


async def test_moment_element_slider_set_value(hass, setup_entry, aioclient_mock):
    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.imaggg_s_soundsticks_moment_element_1", "value": 80},
        blocking=True,
    )
    payloads = _all_post_payloads(aioclient_mock)
    calls = [p for c, p in payloads if c == "setSoundscapeV2Config"]
    assert calls
    # slider_index=0 -> device element_id = 2-0 = 2; active mode soundscape_id=1
    assert calls[-1] == {"soundscape_id": 1, "element_id": 2, "element_value": 80}
