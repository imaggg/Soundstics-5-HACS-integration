"""Light platform for the SoundSticks 5 integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import LIGHT_PATTERNS
from .entity import SoundSticksEntity

PATTERN_NAME_TO_ID = {name: pattern_id for pattern_id, name in LIGHT_PATTERNS.items()}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([SoundSticksLight(coordinator, entry)])


class SoundSticksLight(SoundSticksEntity, LightEntity):
    """The speaker's LED light strip: on/off, brightness, pattern (effect)."""

    _attr_name = None
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = list(LIGHT_PATTERNS.values())

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "light")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.light.enable

    @property
    def brightness(self) -> int:
        return round(self.coordinator.data.light.brightness * 255 / 100)

    @property
    def effect(self) -> str | None:
        return LIGHT_PATTERNS.get(self.coordinator.data.light.pattern.id)

    async def async_turn_on(self, **kwargs: Any) -> None:
        fields: dict[str, Any] = {"enable": 1}

        if ATTR_BRIGHTNESS in kwargs:
            fields["brightness"] = round(kwargs[ATTR_BRIGHTNESS] * 100 / 255)

        if ATTR_EFFECT in kwargs:
            pattern_id = PATTERN_NAME_TO_ID.get(kwargs[ATTR_EFFECT])
            if pattern_id is not None:
                fields["active_pattern"] = {
                    "id": pattern_id,
                    "level": self.coordinator.data.light.pattern.level,
                }

        await self.coordinator.client.set_light_info(**fields)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.set_light_info(enable=0)
        await self.coordinator.async_request_refresh()
