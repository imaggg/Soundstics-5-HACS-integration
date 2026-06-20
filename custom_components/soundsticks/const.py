"""Constants for the SoundSticks 5 integration."""

from homeassistant.const import Platform

DOMAIN = "soundsticks"

# Filled in incrementally as each entity platform is implemented (Phases 4-7).
PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.NUMBER, Platform.SELECT, Platform.SWITCH]

# mDNS / discovery
ZEROCONF_SERVICE_TYPE = "_jbl-product._tcp.local."
UPNP_DESCRIPTION_PORT = 59152

# Config entry data keys
CONF_CERT_PEM = "cert_pem"
CONF_KEY_PEM = "key_pem"
CONF_UUID = "uuid"
CONF_DEVICE_NAME = "device_name"

# Polling
DEFAULT_POLL_INTERVAL = 5  # seconds, matches the tray app

# Light patterns (active_pattern.id)
LIGHT_PATTERNS = {
    1: "Ocean",
    2: "Aurora",
    3: "Blossom",
    4: "Sunrise",
    5: "Fireplace",
    6: "Calm",
    7: "Nebula",
}

# EQ presets (active_eq_id)
EQ_PRESETS = {
    0: "Custom",
    1: "Signature Sound",
    2: "Vocal",
    3: "Energetic",
    4: "Chill",
}

EQ_BANDS_HZ = [125, 250, 500, 1000, 2000, 4000, 8000]

# Firmware-exact fs/gain pairs required by setActiveEQ to recognise a preset
# switch (sending active_eq_id alone is ignored by the device). Must match
# internal/api/eq.go's builtinPresets verbatim.
EQ_PRESET_PAYLOADS = {
    1: {"fs": [125, 250, 500, 1000, 2000, 4000, 8000], "gain": [0, 0, 0, 0, 0, 0, 0]},
    2: {"fs": [80, 250, 500, 1000, 9000, 4000, 9000], "gain": [-5, 0, 0, 4, -2, 4, 0]},
    3: {"fs": [60, 200, 500, 1500, 2000, 7000, 8000], "gain": [-2, 7, 0, 3, 0, 2, 0]},
    4: {"fs": [200, 250, 500, 1000, 1500, 10000, 6000], "gain": [-4, 0, 0, 0, -3, 0, -3]},
}

# Moment / soundscape modes (soundscape_id)
MOMENT_MODES = {
    1: "Forest",
    2: "Rain",
    3: "Ocean",
    4: "City",
}

# Moment sleep timer options, in seconds
MOMENT_SLEEP_TIMERS = {
    0: "Off",
    900: "15 min",
    1800: "30 min",
    2700: "45 min",
    3600: "60 min",
}
