"""Config flow for the SoundSticks 5 integration."""

from __future__ import annotations

import logging
import ssl
import tempfile
from pathlib import Path
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SoundSticksClient, build_ssl_context
from .const import CONF_CERT_PEM, CONF_DEVICE_NAME, CONF_KEY_PEM, CONF_UUID, DOMAIN, UPNP_DESCRIPTION_PORT

try:  # moved here in newer HA core; older core only has the components.zeroconf path
    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
except ImportError:
    from homeassistant.components.zeroconf import ZeroconfServiceInfo

_LOGGER = logging.getLogger(__name__)

_CERT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CERT_PEM): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
        vol.Required(CONF_KEY_PEM): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
    }
)


class CannotConnect(Exception):
    """Could not reach the device at all."""


class InvalidCert(Exception):
    """Device reachable but the cert/key was rejected."""


async def _async_confirm_upnp(hass, host: str) -> bool:
    """Mirror mdns.go's confirmDevice: plain HTTP GET, no auth required."""
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            f"http://{host}:{UPNP_DESCRIPTION_PORT}/description.xml",
            timeout=aiohttp.ClientTimeout(total=3),
        ) as resp:
            return resp.status == 200
    except aiohttp.ClientError:
        return False


def _build_context(cert_pem: str, key_pem: str, cert_dir: str) -> ssl.SSLContext:
    cert_path = Path(cert_dir) / "cert.pem"
    key_path = Path(cert_dir) / "key.pem"
    cert_path.write_text(cert_pem)
    key_path.write_text(key_pem)
    return build_ssl_context(str(cert_path), str(key_path))


async def _async_validate_cert(hass, host: str, cert_pem: str, key_pem: str) -> dict[str, Any]:
    """Try connecting with the supplied cert/key. Returns the device_info dict."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            ssl_context = await hass.async_add_executor_job(_build_context, cert_pem, key_pem, tmp_dir)
        except (ssl.SSLError, ValueError) as err:
            raise InvalidCert from err

        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            client = SoundSticksClient(host, ssl_context, session)
            try:
                raw = await client.get_device_info()
            except ssl.SSLError as err:
                raise InvalidCert from err
            except (aiohttp.ClientError, TimeoutError) as err:
                raise CannotConnect from err

    info = raw.get("device_info")
    if not info:
        raise CannotConnect
    return info


class SoundSticksConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SoundSticks 5."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._discovery_name: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._host = user_input[CONF_HOST]
            return await self.async_step_cert()

        schema = vol.Schema({vol.Required(CONF_HOST): str})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        host = discovery_info.host
        if not await _async_confirm_upnp(self.hass, host):
            return self.async_abort(reason="not_soundsticks")

        await self.async_set_unique_id(discovery_info.hostname)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        self._host = host
        self._discovery_name = discovery_info.name
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(
                step_id="zeroconf_confirm",
                description_placeholders={"name": self._discovery_name or self._host},
            )
        return await self.async_step_cert()

    async def async_step_cert(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await _async_validate_cert(
                    self.hass, self._host, user_input[CONF_CERT_PEM], user_input[CONF_KEY_PEM]
                )
            except InvalidCert:
                errors["base"] = "invalid_cert"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                uuid = info.get("uuid")
                name = info.get("name", "SoundSticks 5")
                # Zeroconf-sourced flows already set unique_id to the stable
                # mDNS hostname in async_step_zeroconf — don't clobber it, or
                # re-discovery of an already-configured device stops deduping.
                if uuid and self.unique_id is None:
                    await self.async_set_unique_id(uuid)
                    self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_HOST: self._host,
                        CONF_CERT_PEM: user_input[CONF_CERT_PEM],
                        CONF_KEY_PEM: user_input[CONF_KEY_PEM],
                        CONF_UUID: uuid,
                        CONF_DEVICE_NAME: name,
                    },
                )

        return self.async_show_form(step_id="cert", data_schema=_CERT_SCHEMA, errors=errors)
