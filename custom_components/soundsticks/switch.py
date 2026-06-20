"""Switch platform for the SoundSticks 5 integration.

Mute added in Phase 6. Moment on/off appended in Phase 7.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import SoundSticksEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([SoundSticksMute(coordinator, entry), SoundSticksMoment(coordinator, entry)])


class SoundSticksMute(SoundSticksEntity, SwitchEntity):
    """Mutes the speaker output."""

    _attr_translation_key = "mute"
    _attr_icon = "mdi:volume-mute"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "mute")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.player.mute

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.client.set_player_mute(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.set_player_mute(False)
        await self.coordinator.async_request_refresh()


class SoundSticksMoment(SoundSticksEntity, SwitchEntity):
    """Starts/stops Moment soundscape playback.

    The device exposes no "is playing" status, so on/off state is tracked
    client-side (coordinator.moment_playing) — same approach the tray app
    uses (a local momentPlaying bool), since soundscape playback state isn't
    queryable.
    """

    _attr_translation_key = "moment"
    _attr_icon = "mdi:weather-partly-cloudy"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "moment")

    @property
    def is_on(self) -> bool:
        return self.coordinator.moment_playing

    async def async_turn_on(self, **kwargs: Any) -> None:
        sb = self.coordinator.data.smart_button
        await self.coordinator.client.set_smart_button_config(sb.soundscape_id, sb.volume, sb.sleep_timer)
        await self.coordinator.client.control_soundscape_v2(6, sb.soundscape_id)
        self.coordinator.moment_playing = True
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        soundscape_id = self.coordinator.data.smart_button.soundscape_id
        await self.coordinator.client.control_soundscape_v2(7, soundscape_id)
        self.coordinator.moment_playing = False
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
