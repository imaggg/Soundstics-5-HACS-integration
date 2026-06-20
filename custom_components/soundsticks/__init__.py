"""The SoundSticks 5 integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SoundSticksClient, build_ssl_context
from .cert_store import async_write_cert_files
from .const import CONF_CERT_PEM, CONF_KEY_PEM, PLATFORMS
from .coordinator import SoundSticksCoordinator

type SoundSticksConfigEntry = ConfigEntry[SoundSticksCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SoundSticksConfigEntry) -> bool:
    cert_path, key_path = await async_write_cert_files(
        hass, entry.entry_id, entry.data[CONF_CERT_PEM], entry.data[CONF_KEY_PEM]
    )
    ssl_context = await hass.async_add_executor_job(build_ssl_context, cert_path, key_path)

    session = async_get_clientsession(hass)
    client = SoundSticksClient(entry.data[CONF_HOST], ssl_context, session)

    coordinator = SoundSticksCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    try:
        device_info = await client.get_device_info()
        coordinator.firmware = device_info.get("device_info", {}).get("firmware")
    except Exception:  # noqa: BLE001 - cosmetic only, must not block setup
        coordinator.firmware = None

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SoundSticksConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
