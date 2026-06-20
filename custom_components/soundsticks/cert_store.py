"""Persists the user-supplied mTLS cert/key PEM to disk.

ssl.SSLContext.load_cert_chain only accepts file paths, not in-memory PEM
data, so the PEM text stored in the config entry has to be written out
before building an SSLContext. Shared by config_flow (connection test) and
__init__.py (runtime setup).
"""

from __future__ import annotations

from pathlib import Path

from homeassistant.core import HomeAssistant

from .const import DOMAIN


def _cert_dir(hass: HomeAssistant, entry_id: str) -> Path:
    return Path(hass.config.path(".storage", DOMAIN, entry_id))


def _write_cert_files(hass: HomeAssistant, entry_id: str, cert_pem: str, key_pem: str) -> tuple[str, str]:
    cert_dir = _cert_dir(hass, entry_id)
    cert_dir.mkdir(parents=True, exist_ok=True)
    cert_path = cert_dir / "cert.pem"
    key_path = cert_dir / "key.pem"
    cert_path.write_text(cert_pem)
    key_path.write_text(key_pem)
    key_path.chmod(0o600)
    return str(cert_path), str(key_path)


async def async_write_cert_files(hass: HomeAssistant, entry_id: str, cert_pem: str, key_pem: str) -> tuple[str, str]:
    """Write cert/key PEM text to disk, returning (cert_path, key_path)."""
    return await hass.async_add_executor_job(_write_cert_files, hass, entry_id, cert_pem, key_pem)
