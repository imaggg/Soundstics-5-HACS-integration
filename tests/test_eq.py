import json
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.select import SERVICE_SELECT_OPTION
from homeassistant.components.number import SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST
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
    CONF_DEVICE_NAME: "Test SoundSticks",
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

# Real shape captured live from the device (192.168.1.97).
EQ_LIST_JSON = {
    "active_eq_id": "1",
    "eq_list": [
        {"band": 7, "eq_id": 1, "eq_name": "JBL SIGNATURE", "eq_payload": {"fs": [125, 250, 500, 1000, 2000, 4000, 8000], "gain": [0, 0, 0, 0, 0, 0, 0]}},
        {"band": 7, "eq_id": 2, "eq_name": "VOCAL", "eq_payload": {"fs": [80, 250, 500, 1000, 9000, 4000, 9000], "gain": [-5, 0, 0, 4, -2, 4, 0]}},
        {"band": 7, "eq_id": 3, "eq_name": "ENERGETIC", "eq_payload": {"fs": [60, 200, 500, 1500, 2000, 7000, 8000], "gain": [-2, 7, 0, 3, 0, 2, 0]}},
        {"band": 7, "eq_id": 4, "eq_name": "CHILL", "eq_payload": {"fs": [200, 250, 500, 1000, 1500, 10000, 6000], "gain": [-4, 0, 0, 0, -3, 0, -3]}},
        {"band": 7, "eq_id": 0, "eq_name": "CUSTOMIZE", "eq_payload": {"fs": [125, 250, 500, 1000, 2000, 4000, 8000], "gain": [0, 0, 1.5, 4, 1, 0, 0]}},
    ],
}


def _mock_all_endpoints(aioclient_mock, active_eq_id="1"):
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        URL,
        params={"command": "getDeviceInfo"},
        json={"error_code": "0", "device_info": {"firmware": "26.22.31.63.00", "name": "Test SoundSticks", "uuid": "9051b2f7-084f-3405-812c-1a0fda8c6c05"}},
    )
    aioclient_mock.get(URL, params={"command": "getLightInfo"}, json=LIGHT_INFO_JSON)
    eq_json = dict(EQ_LIST_JSON, active_eq_id=active_eq_id)
    aioclient_mock.get(URL, params={"command": "getEQList"}, json=eq_json)
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
            command, payload_json = body.split("&payload=", 1)
            return command.removeprefix("command="), json.loads(payload_json)
    raise AssertionError("no POST recorded")


async def test_eq_preset_select_reflects_active_id(hass, setup_entry):
    state = hass.states.get("select.test_soundsticks_eq_preset")
    assert state is not None
    assert state.state == "Signature Sound"
    assert set(state.attributes["options"]) == {"Custom", "Signature Sound", "Vocal", "Energetic", "Chill"}


async def test_eq_preset_select_switches_factory_preset(hass, setup_entry, aioclient_mock):
    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.test_soundsticks_eq_preset", "option": "Vocal"},
        blocking=True,
    )
    command, payload = _last_post_payload(aioclient_mock)
    assert command == "setActiveEQ"
    assert payload["active_eq_id"] == "2"
    assert payload["eq_payload"]["gain"] == [-5, 0, 0, 4, -2, 4, 0]


async def test_eq_preset_select_custom_repushes_stored_curve(hass, setup_entry, aioclient_mock):
    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.test_soundsticks_eq_preset", "option": "Custom"},
        blocking=True,
    )
    command, payload = _last_post_payload(aioclient_mock)
    assert command == "setActiveEQ"
    assert payload["active_eq_id"] == "0"
    # stored [0,0,1.5,4,1,0,0] -> ui [0,0,3,8,2,0,0] -> api re-scaled back
    assert payload["eq_payload"]["gain"] == [0, 0, 1.5, 4, 1, 0, 0]


async def test_eq_band_gain_reads_custom_entry_unscaled(hass, setup_entry):
    # stored gain index 2 = 1.5 -> ui = 1.5*2 = 3.0
    state = hass.states.get("number.test_soundsticks_500_hz")
    assert state is not None
    assert float(state.state) == 3.0
    # index 3 stored=4 -> ui=8.0
    state_1k = hass.states.get("number.test_soundsticks_1_khz")
    assert float(state_1k.state) == 8.0


async def test_eq_band_gain_set_value_updates_only_that_band(hass, setup_entry, aioclient_mock):
    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.test_soundsticks_125_hz", "value": -6},
        blocking=True,
    )
    command, payload = _last_post_payload(aioclient_mock)
    assert command == "setActiveEQ"
    assert payload["active_eq_id"] == "0"
    # band0 negative: ui -6 -> api -6*9/12 = -4.5; other bands unchanged from stored->ui->stored roundtrip
    gain = payload["eq_payload"]["gain"]
    assert gain[0] == -4.5
    assert gain[2] == 1.5
    assert gain[3] == 4
