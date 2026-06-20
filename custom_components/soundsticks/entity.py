"""Shared base entity for the SoundSticks 5 integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_NAME, DOMAIN
from .coordinator import SoundSticksCoordinator


class SoundSticksEntity(CoordinatorEntity[SoundSticksCoordinator]):
    """Base entity tying a SoundSticks 5 entity to its coordinator and device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SoundSticksCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            name=entry.data.get(CONF_DEVICE_NAME, "SoundSticks 5"),
            manufacturer="Harman Kardon",
            model="SoundSticks 5",
            sw_version=coordinator.firmware,
        )
