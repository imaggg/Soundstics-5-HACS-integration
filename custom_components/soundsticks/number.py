"""Number platform for the SoundSticks 5 integration.

Light entities (animation speed, pattern color) added in Phase 4, EQ bands
in Phase 5, volume in Phase 6. Moment sliders appended in Phase 7.
"""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import api_gain_to_ui
from .const import EQ_BANDS_HZ
from .entity import SoundSticksEntity


def _format_hz(hz: int) -> str:
    return f"{hz // 1000} kHz" if hz >= 1000 else f"{hz} Hz"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    entities: list[NumberEntity] = [
        SoundSticksAnimationSpeed(coordinator, entry),
        SoundSticksPatternColor(coordinator, entry),
    ]
    entities.extend(
        SoundSticksEQBandGain(coordinator, entry, band_index=i, hz=hz) for i, hz in enumerate(EQ_BANDS_HZ)
    )
    entities.append(SoundSticksVolume(coordinator, entry))
    entities.append(SoundSticksMomentVolume(coordinator, entry))
    entities.extend(SoundSticksMomentElement(coordinator, entry, slider_index=i) for i in range(3))
    async_add_entities(entities)


class SoundSticksAnimationSpeed(SoundSticksEntity, NumberEntity):
    """Speed of the active light pattern's animation (dynamic_level, 1-5)."""

    _attr_translation_key = "animation_speed"
    _attr_icon = "mdi:speedometer"
    _attr_native_min_value = 1
    _attr_native_max_value = 5
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "animation_speed")

    @property
    def native_value(self) -> float:
        return self.coordinator.data.light.dynamic_level

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.client.set_light_info(dynamic_level=int(value))
        await self.coordinator.async_request_refresh()


class SoundSticksPatternColor(SoundSticksEntity, NumberEntity):
    """Color/level of the active light pattern (active_pattern.level, 0-100)."""

    _attr_translation_key = "pattern_color"
    _attr_icon = "mdi:palette"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "pattern_color")

    @property
    def native_value(self) -> float:
        return self.coordinator.data.light.pattern.level

    async def async_set_native_value(self, value: float) -> None:
        pattern_id = self.coordinator.data.light.pattern.id
        await self.coordinator.client.set_light_info(active_pattern={"id": pattern_id, "level": int(value)})
        await self.coordinator.async_request_refresh()


class SoundSticksEQBandGain(SoundSticksEntity, NumberEntity):
    """One band of the Custom EQ curve (±12 dB at a standard frequency).

    Always reads/writes the eq_id=0 (Custom) entry, regardless of which
    preset is currently active — the device's factory presets (Vocal,
    Energetic, Chill) use non-standard, per-preset band frequencies
    (e.g. Vocal's 5th band is 9kHz, not 2kHz), so they can't be displayed
    under these fixed standard-frequency labels. Adjusting any band here
    switches the device to the Custom preset, matching device behavior.
    """

    _attr_icon = "mdi:tune-vertical"
    _attr_native_min_value = -12
    _attr_native_max_value = 12
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = "dB"
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, entry: ConfigEntry, band_index: int, hz: int) -> None:
        self._band_index = band_index
        super().__init__(coordinator, entry, f"eq_band_{hz}hz")
        # Frequency labels (125 Hz, 1 kHz, ...) don't need translation_key —
        # they're set directly per HA's guidance for dynamic entity names.
        self._attr_name = _format_hz(hz)

    def _custom_gain_ui(self) -> list[float]:
        custom = next((p for p in self.coordinator.data.eq.presets if p.eq_id == 0), None)
        if custom is None:
            return [0.0] * len(EQ_BANDS_HZ)
        return api_gain_to_ui(custom.gain)

    @property
    def native_value(self) -> float:
        return self._custom_gain_ui()[self._band_index]

    async def async_set_native_value(self, value: float) -> None:
        gain = self._custom_gain_ui()
        gain[self._band_index] = value
        await self.coordinator.client.set_custom_eq(EQ_BANDS_HZ, gain)
        await self.coordinator.async_request_refresh()


class SoundSticksVolume(SoundSticksEntity, NumberEntity):
    """Speaker output volume (0-100)."""

    _attr_translation_key = "volume"
    _attr_icon = "mdi:volume-high"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "volume")

    @property
    def native_value(self) -> float:
        return self.coordinator.data.player.vol

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.client.set_player_vol(int(value))
        await self.coordinator.async_request_refresh()


class SoundSticksMomentVolume(SoundSticksEntity, NumberEntity):
    """Volume of Moment soundscape playback (percent_of_volume, 0-100)."""

    _attr_translation_key = "moment_volume"
    _attr_icon = "mdi:volume-high"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "moment_volume")

    @property
    def native_value(self) -> float:
        return self.coordinator.data.smart_button.volume

    async def async_set_native_value(self, value: float) -> None:
        sb = self.coordinator.data.smart_button
        await self.coordinator.client.set_smart_button_config(sb.soundscape_id, int(value), sb.sleep_timer)
        await self.coordinator.async_request_refresh()


class SoundSticksMomentElement(SoundSticksEntity, NumberEntity):
    """One of the 3 element-volume sliders for the currently active Moment
    mode. Slider meaning changes with the mode (e.g. Forest's 3 elements
    differ from Rain's) — same UI behavior as the tray app's per-mode tabs.
    """

    _attr_icon = "mdi:tune-variant"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, entry: ConfigEntry, slider_index: int) -> None:
        self._slider_index = slider_index
        super().__init__(coordinator, entry, f"moment_element_{slider_index + 1}")
        self._attr_translation_key = f"moment_element_{slider_index + 1}"

    @property
    def native_value(self) -> float:
        mode_id = self.coordinator.data.smart_button.soundscape_id
        mode_entry = next((e for e in self.coordinator.data.soundscape if e.soundscape_id == mode_id), None)
        if mode_entry is None:
            return 0
        device_id = 2 - self._slider_index
        element = next((el for el in mode_entry.elements if el.id == device_id), None)
        return element.value if element else 0

    async def async_set_native_value(self, value: float) -> None:
        mode_id = self.coordinator.data.smart_button.soundscape_id
        await self.coordinator.client.set_soundscape_element(mode_id, self._slider_index, int(value))
        await self.coordinator.async_request_refresh()
