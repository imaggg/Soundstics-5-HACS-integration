import json
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_EFFECT
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
    aioclient_mock.get(
        URL,
        params={"command": "getSmartButtonConfig"},
        json={"smart_config": {"soundscape": {"active_soundscape_id": "1"}, "timer": {"sleep_timer": "0"}}},
    )
    aioclient_mock.get(URL, params={"command": "getSoundscapeV2Config"}, json={"soundscapeV2_list": []})
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


def _last_post_payload(aioclient_mock):
    for method, url, data, _headers in reversed(aioclient_mock.mock_calls):
        if method.lower() == "post":
            body = data if isinstance(data, str) else data.decode()
            assert body.startswith("command=")
            command, payload_json = body.split("&payload=", 1)
            return command.removeprefix("command="), json.loads(payload_json)
    raise AssertionError("no POST recorded")


async def test_light_state_reflects_coordinator_data(hass, setup_entry):
    state = hass.states.get("light.imaggg_s_soundsticks")
    assert state is not None
    assert state.state == "on"
    assert state.attributes["brightness"] == round(45 * 255 / 100)
    assert state.attributes["effect"] == "Ocean"
    assert state.attributes["effect_list"] == [
        "Ocean", "Aurora", "Blossom", "Sunrise", "Fireplace", "Calm", "Nebula",
    ]


async def test_light_turn_on_with_brightness(hass, setup_entry, aioclient_mock):
    entity_id = hass.states.async_entity_ids("light")[0]
    await hass.services.async_call(
        "light", SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 128}, blocking=True
    )
    command, payload = _last_post_payload(aioclient_mock)
    assert command == "setLightInfo"
    assert payload["enable"] == "1"
    assert payload["brightness"] == str(round(128 * 100 / 255))


async def test_light_turn_on_with_effect(hass, setup_entry, aioclient_mock):
    entity_id = hass.states.async_entity_ids("light")[0]
    await hass.services.async_call(
        "light", SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id, ATTR_EFFECT: "Aurora"}, blocking=True
    )
    command, payload = _last_post_payload(aioclient_mock)
    assert command == "setLightInfo"
    assert payload["active_pattern"] == {"id": "2", "level": "50"}


async def test_light_turn_off(hass, setup_entry, aioclient_mock):
    entity_id = hass.states.async_entity_ids("light")[0]
    await hass.services.async_call("light", SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True)
    command, payload = _last_post_payload(aioclient_mock)
    assert command == "setLightInfo"
    assert payload == {"enable": "0"}


async def test_animation_speed_number(hass, setup_entry, aioclient_mock):
    entity_id = "number.imaggg_s_soundsticks_animation_speed"
    state = hass.states.get(entity_id)
    assert state.state == "2"

    await hass.services.async_call(
        "number", SERVICE_SET_VALUE, {ATTR_ENTITY_ID: entity_id, "value": 4}, blocking=True
    )
    command, payload = _last_post_payload(aioclient_mock)
    assert command == "setLightInfo"
    assert payload == {"dynamic_level": "4"}


async def test_pattern_color_number(hass, setup_entry, aioclient_mock):
    entity_id = "number.imaggg_s_soundsticks_pattern_color"
    state = hass.states.get(entity_id)
    assert state.state == "50"

    await hass.services.async_call(
        "number", SERVICE_SET_VALUE, {ATTR_ENTITY_ID: entity_id, "value": 75}, blocking=True
    )
    command, payload = _last_post_payload(aioclient_mock)
    assert command == "setLightInfo"
    assert payload["active_pattern"] == {"id": "1", "level": "75"}
