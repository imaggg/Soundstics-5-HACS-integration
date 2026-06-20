"""Data update coordinator for the SoundSticks 5 integration."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    EQList,
    LightInfo,
    PlayerStatus,
    SmartButtonState,
    SoundscapeEntry,
    SoundSticksClient,
)
from .const import DEFAULT_POLL_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class SoundSticksData:
    light: LightInfo
    eq: EQList
    player: PlayerStatus
    smart_button: SmartButtonState
    soundscape: list[SoundscapeEntry]


class SoundSticksCoordinator(DataUpdateCoordinator[SoundSticksData]):
    """Polls the speaker for light/EQ/player/moment state every 5s."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: SoundSticksClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_POLL_INTERVAL),
        )
        self.client = client
        # The device exposes no "is a soundscape currently playing" status —
        # only the configured mode/timer (getSmartButtonConfig) and volume.
        # Tracked client-side, same approach as the tray app's local
        # `momentPlaying` bool: set on controlSoundscapeV2 start/stop, not
        # part of the polled data so it survives across refreshes.
        self.moment_playing: bool = False
        self.firmware: str | None = None

    async def _async_update_data(self) -> SoundSticksData:
        try:
            light, eq, player, smart_button, soundscape = await asyncio.gather(
                self.client.get_light_info(),
                self.client.get_eq_list(),
                self.client.get_player_status(),
                self.client.get_smart_button_config(),
                self.client.get_soundscape_v2_config(),
            )
        except Exception as err:  # noqa: BLE001 - any transport error means the device is unreachable
            raise UpdateFailed(f"Error communicating with SoundSticks 5: {err}") from err

        return SoundSticksData(
            light=light, eq=eq, player=player, smart_button=smart_button, soundscape=soundscape
        )
