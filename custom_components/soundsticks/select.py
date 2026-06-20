"""Select platform for the SoundSticks 5 integration.

EQ preset added in Phase 5. Moment mode/sleep timer appended in Phase 7.
"""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import api_gain_to_ui
from .const import EQ_BANDS_HZ, EQ_PRESETS, MOMENT_MODES, MOMENT_SLEEP_TIMERS
from .entity import SoundSticksEntity

PRESET_NAME_TO_ID = {name: preset_id for preset_id, name in EQ_PRESETS.items()}
MODE_NAME_TO_ID = {name: mode_id for mode_id, name in MOMENT_MODES.items()}
TIMER_NAME_TO_SECONDS = {name: seconds for seconds, name in MOMENT_SLEEP_TIMERS.items()}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            SoundSticksEQPresetSelect(coordinator, entry),
            SoundSticksMomentMode(coordinator, entry),
            SoundSticksMomentSleepTimer(coordinator, entry),
        ]
    )


class SoundSticksEQPresetSelect(SoundSticksEntity, SelectEntity):
    """Switches between the 5 EQ presets (4 factory + Custom)."""

    _attr_translation_key = "eq_preset"
    _attr_icon = "mdi:equalizer"
    _attr_options = list(EQ_PRESETS.values())
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "eq_preset")

    @property
    def current_option(self) -> str | None:
        return EQ_PRESETS.get(self.coordinator.data.eq.active_eq_id)

    async def async_select_option(self, option: str) -> None:
        preset_id = PRESET_NAME_TO_ID.get(option)
        if preset_id is None:
            return

        if preset_id == 0:
            # No direct "activate Custom" API call exists — re-push the
            # last-known custom curve, which the device accepts as eq_id=0.
            custom = next((p for p in self.coordinator.data.eq.presets if p.eq_id == 0), None)
            gain = api_gain_to_ui(custom.gain) if custom else [0.0] * len(EQ_BANDS_HZ)
            await self.coordinator.client.set_custom_eq(EQ_BANDS_HZ, gain)
        else:
            await self.coordinator.client.set_active_eq(preset_id)

        await self.coordinator.async_request_refresh()


class SoundSticksMomentMode(SoundSticksEntity, SelectEntity):
    """Switches the active Moment soundscape. Mirrors the tray app's
    "momentSwitch" behavior: stops whatever was playing, applies the new
    mode's config, and starts it — selecting a mode always plays it.
    """

    _attr_translation_key = "moment_mode"
    _attr_icon = "mdi:weather-partly-cloudy"
    _attr_options = list(MOMENT_MODES.values())
    # DIAGNOSTIC here is a pragmatic UI trick, not a literal "diagnostic"
    # entity — HA only has CONFIG/DIAGNOSTIC as secondary buckets, and using
    # both lets the device page show 3 groups (Controls / Configuration /
    # Diagnostic) instead of 2, keeping Moment visually separate from EQ.
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "moment_mode")

    @property
    def current_option(self) -> str | None:
        return MOMENT_MODES.get(self.coordinator.data.smart_button.soundscape_id)

    async def async_select_option(self, option: str) -> None:
        new_id = MODE_NAME_TO_ID.get(option)
        if new_id is None:
            return

        sb = self.coordinator.data.smart_button
        await self.coordinator.client.control_soundscape_v2(7, sb.soundscape_id)
        await self.coordinator.client.set_smart_button_config(new_id, sb.volume, sb.sleep_timer)
        await self.coordinator.client.control_soundscape_v2(6, new_id)
        self.coordinator.moment_playing = True

        await self.coordinator.async_request_refresh()


class SoundSticksMomentSleepTimer(SoundSticksEntity, SelectEntity):
    """Moment's sleep timer (off / 15 / 30 / 45 / 60 min). Updates config only —
    does not start or stop playback."""

    _attr_translation_key = "moment_sleep_timer"
    _attr_icon = "mdi:timer-outline"
    _attr_options = list(MOMENT_SLEEP_TIMERS.values())
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "moment_sleep_timer")

    @property
    def current_option(self) -> str | None:
        return MOMENT_SLEEP_TIMERS.get(self.coordinator.data.smart_button.sleep_timer)

    async def async_select_option(self, option: str) -> None:
        seconds = TIMER_NAME_TO_SECONDS.get(option)
        if seconds is None:
            return

        sb = self.coordinator.data.smart_button
        await self.coordinator.client.set_smart_button_config(sb.soundscape_id, sb.volume, seconds)
        await self.coordinator.async_request_refresh()
