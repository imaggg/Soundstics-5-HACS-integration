"""Async mTLS client for the SoundSticks 5 / Linkplay httpapi.asp protocol.

Ported from soundsticks-app's internal/api/{client,lights,eq,moment}.go.
Keep in sync with that reference implementation.
"""

from __future__ import annotations

import json
import ssl
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from .const import EQ_PRESET_PAYLOADS

# Per-request timeout. The shared HA aiohttp session defaults to a 300s total
# timeout, which would let a hung Linkplay device stall a coordinator poll for
# minutes. Keep it short so a stuck request fails fast into UpdateFailed/retry.
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)


def build_ssl_context(cert_path: str, key_path: str) -> ssl.SSLContext:
    """Build the client-cert SSL context. Run in an executor — this does file I/O.

    Mirrors client.go's NewClient: client cert required, server verification
    disabled (the device's server cert isn't meant to be trusted by a CA chain).
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
    return ctx


def ui_gain_to_api(ui_gain: list[float]) -> list[float]:
    """Scale 7-band UI gain (±12 dB) to the value the device stores.

    125Hz (index 0) has a larger negative range on firmware: -12 UI -> -9 API.
    Everything else (and positive 125Hz) halves.
    """
    scaled = []
    for i, g in enumerate(ui_gain):
        if i == 0 and g < 0:
            scaled.append(g * 9.0 / 12.0)
        else:
            scaled.append(g / 2)
    return scaled


def api_gain_to_ui(api_gain: list[float]) -> list[float]:
    """Inverse of ui_gain_to_api — used to display values read from getEQList."""
    ui = []
    for i, g in enumerate(api_gain):
        if i == 0 and g < 0:
            ui.append(g * 12.0 / 9.0)
        else:
            ui.append(g * 2)
    return ui


def flex_int(value: Any, default: int = 0) -> int:
    """Parse a value the device may return as either a JSON string or number."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass
class Pattern:
    id: int
    level: int


@dataclass
class LightInfo:
    enable: bool
    brightness: int
    dynamic_level: int
    pattern: Pattern
    light_element: int


@dataclass
class EQPreset:
    eq_id: int
    name: str
    fs: list[float]
    gain: list[float]


@dataclass
class EQList:
    active_eq_id: int
    presets: list[EQPreset]


@dataclass
class PlayerStatus:
    status: str
    vol: int
    mute: bool
    eq: int


@dataclass
class SmartButtonState:
    soundscape_id: int
    sleep_timer: int
    volume: int


@dataclass
class SoundscapeElement:
    id: int
    value: int


@dataclass
class SoundscapeEntry:
    soundscape_id: int
    elements: list[SoundscapeElement] = field(default_factory=list)


class SoundSticksError(Exception):
    """Raised when the device returns an unexpected/invalid response."""


class SoundSticksClient:
    """Talks to a single SoundSticks 5 speaker over mTLS HTTPS."""

    def __init__(self, host: str, ssl_context: ssl.SSLContext, session: aiohttp.ClientSession) -> None:
        self._base_url = f"https://{host}"
        self._ssl_context = ssl_context
        self._session = session

    # -- transport ---------------------------------------------------------

    async def _get(self, command: str) -> Any:
        url = f"{self._base_url}/httpapi.asp"
        async with self._session.get(
            url, params={"command": command}, ssl=self._ssl_context, timeout=_REQUEST_TIMEOUT
        ) as resp:
            text = await resp.text()
        if not text:
            return {}
        return json.loads(text)

    async def _raw_get(self, command: str) -> None:
        # Some commands (setPlayerCmd:vol:N) need literal colons, unencoded.
        url = f"{self._base_url}/httpapi.asp?command={command}"
        async with self._session.get(url, ssl=self._ssl_context, timeout=_REQUEST_TIMEOUT) as resp:
            await resp.read()

    async def _post(self, command: str, payload: Any) -> None:
        # Device requires application/x-www-form-urlencoded with a *raw*
        # (not url-encoded) JSON payload: command=X&payload={"a":"b"}.
        # aiohttp's FormData would url-encode the JSON, so build the body by hand.
        body = f"command={command}&payload={json.dumps(payload)}"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        url = f"{self._base_url}/httpapi.asp"
        async with self._session.post(
            url, data=body.encode(), headers=headers, ssl=self._ssl_context, timeout=_REQUEST_TIMEOUT
        ) as resp:
            await resp.read()

    # -- lights --------------------------------------------------------------

    async def get_light_info(self) -> LightInfo:
        raw = await self._get("getLightInfo")
        li = raw.get("light_info", {})
        ap = li.get("active_pattern", {})
        return LightInfo(
            enable=flex_int(li.get("enable")) == 1,
            brightness=flex_int(li.get("brightness")),
            dynamic_level=flex_int(li.get("dynamic_level")),
            pattern=Pattern(id=flex_int(ap.get("id")), level=flex_int(ap.get("level"))),
            light_element=flex_int(li.get("light_element")),
        )

    async def set_light_info(self, **fields: Any) -> None:
        """Send a partial light update. Values are sent as device-format strings.

        Example: set_light_info(brightness=80) or
        set_light_info(active_pattern={"id": 3, "level": 50}).
        """
        payload: dict[str, Any] = {}
        for key, value in fields.items():
            if key == "active_pattern":
                payload[key] = {"id": str(value["id"]), "level": str(value["level"])}
            else:
                payload[key] = str(value)
        await self._post("setLightInfo", payload)

    # -- equalizer -------------------------------------------------------------

    async def get_eq_list(self) -> EQList:
        raw = await self._get("getEQList")
        presets = []
        for entry in raw.get("eq_list", []):
            ep = entry.get("eq_payload", {})
            presets.append(
                EQPreset(
                    eq_id=flex_int(entry.get("eq_id")),
                    name=entry.get("eq_name", ""),
                    fs=list(ep.get("fs", [])),
                    gain=list(ep.get("gain", [])),
                )
            )
        return EQList(active_eq_id=flex_int(raw.get("active_eq_id")), presets=presets)

    async def set_active_eq(self, eq_id: int) -> None:
        preset = EQ_PRESET_PAYLOADS.get(eq_id)
        if preset is None:
            raise SoundSticksError(f"unknown EQ preset id {eq_id}")
        await self._post(
            "setActiveEQ",
            {"active_eq_id": str(eq_id), "band": 7, "eq_payload": preset},
        )

    async def set_custom_eq(self, fs: list[float], gain: list[float]) -> None:
        scaled = ui_gain_to_api(gain)
        await self._post(
            "setActiveEQ",
            {"active_eq_id": "0", "band": 7, "eq_payload": {"fs": fs, "gain": scaled}},
        )

    # -- device / player -------------------------------------------------------

    async def get_device_info(self) -> dict[str, Any]:
        return await self._get("getDeviceInfo")

    async def get_player_status(self) -> PlayerStatus:
        raw = await self._get("getPlayerStatus")
        return PlayerStatus(
            status=raw.get("status", ""),
            vol=flex_int(raw.get("vol")),
            mute=flex_int(raw.get("mute")) == 1,
            eq=flex_int(raw.get("eq")),
        )

    async def set_player_vol(self, vol: int) -> None:
        await self._raw_get(f"setPlayerCmd:vol:{vol}")

    async def set_player_mute(self, mute: bool) -> None:
        await self._raw_get(f"setPlayerCmd:mute:{1 if mute else 0}")

    # -- moment / soundscape -------------------------------------------------

    async def get_smart_button_config(self) -> SmartButtonState:
        raw = await self._get("getSmartButtonConfig")
        smart = raw.get("smart_config", {})
        soundscape = smart.get("soundscape", {})
        timer = smart.get("timer", {})
        soundscape_v2 = smart.get("soundscapeV2", {})
        return SmartButtonState(
            soundscape_id=flex_int(soundscape.get("active_soundscape_id")),
            sleep_timer=flex_int(timer.get("sleep_timer")),
            volume=flex_int(soundscape_v2.get("percent_of_volume"), default=70),
        )

    async def set_smart_button_config(self, soundscape_id: int, volume: int, sleep_timer: int) -> None:
        await self._post(
            "setSmartButtonConfig",
            {
                "atmos": {"atmos_level": 0, "status": "off"},
                "music": {"album_cover": "", "music_id": ""},
                "soundscape": {
                    "active_soundscape_id": soundscape_id,
                    "supported_list": [1, 2, 3, 4, 0],
                },
                "soundscapeV2": {"mix_with_music": "disabled", "percent_of_volume": volume},
                "timer": {
                    "sleep_timer": sleep_timer,
                    "timer_status": "enabled" if sleep_timer > 0 else "disabled",
                },
            },
        )

    async def control_soundscape_v2(self, action_id: int, soundscape_id: int) -> None:
        """action_id: 6=start, 7=stop."""
        await self._post(
            "controlSoundscapeV2",
            {
                "action_id": action_id,
                "autoResume": True,
                "fadeOut": "true",
                "soundscape_id": soundscape_id,
            },
        )

    async def get_soundscape_v2_config(self) -> list[SoundscapeEntry]:
        raw = await self._get("getSoundscapeV2Config")
        entries = []
        for item in raw.get("soundscapeV2_list", []):
            elements = [
                SoundscapeElement(id=flex_int(e.get("id")), value=flex_int(e.get("value")))
                for e in item.get("element_list", [])
            ]
            entries.append(SoundscapeEntry(soundscape_id=flex_int(item.get("soundscape_id")), elements=elements))
        return entries

    async def set_soundscape_element(self, soundscape_id: int, slider_index: int, value: int) -> None:
        # Device element_id is reversed relative to left-to-right UI slider order.
        await self._post(
            "setSoundscapeV2Config",
            {
                "soundscape_id": soundscape_id,
                "element_id": 2 - slider_index,
                "element_value": value,
            },
        )
