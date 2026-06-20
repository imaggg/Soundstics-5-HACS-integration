# SoundSticks 5 — Home Assistant Integration

Unofficial [HACS](https://hacs.xyz/) custom integration for **Harman Kardon
SoundSticks 5 WiFi** speakers. No cloud, no account — pure local mTLS to the
device, same protocol used by the official Harman Kardon One app.



## Entities

| Entity | Domain | Notes |
| --- | --- | --- |
| Light | `light` | on/off, brightness, effect = one of 7 patterns (Ocean, Aurora, Blossom, Sunrise, Fireplace, Calm, Nebula) |
| Animation speed | `number` | pattern animation speed, 1–5 |
| Pattern color | `number` | pattern color/level, 0–100 |
| EQ preset | `select` | Custom + 4 factory presets (Signature Sound, Vocal, Energetic, Chill) |
| 125 Hz … 8 kHz | `number`  | Custom EQ band gain, ±12 dB |
| Volume | `number` | speaker output volume, 0–100 |
| Mute | `switch` | |
| Moment | `switch` | starts/stops soundscape playback |
| Moment mode | `select` | Forest, Rain, Ocean, City |
| Moment sleep timer | `select` | off / 15 / 30 / 45 / 60 min |
| Moment volume | `number` | soundscape playback volume, 0–100 |
| Moment element 1–3 | `number` | per-mode element sliders (meaning changes with the active mode) |

All polled every 5 seconds via a `DataUpdateCoordinator`.

## Setup

The speaker requires a client certificate (mTLS) that ships inside the
official **Harman Kardon One** Android app. This integration does **not**
embed or distribute that certificate. Instead:

1. Download the Harman Kardon One XAPK (e.g. from APKPure).
2. `pip install -r scripts/requirements.txt`
3. Run `python3 scripts/extract_cert.py path/to/harman-kardon-one.xapk` —
   produces `cert.pem` and `key.pem` locally.
4. In Home Assistant: **Settings → Devices & Services → Add Integration →
   SoundSticks
5. The speaker is usually auto-discovered via mDNS; if not,
   enter its IP manually. Paste the contents of the generated `cert.pem` /
   `key.pem` when prompted.

## Installation (HACS)

1. HACS → Integrations → ⋮ → Custom repositories → add this repo URL,
   category "Integration".
2. Install **SoundSticks 5**, restart Home Assistant.
3. Add the integration as described above.

## Development

```bash
pip install -r requirements_test.txt
pytest
```

Tests run against a mocked speaker (`aioclient_mock`), using response shapes
captured from a real device — no physical speaker needed to run the suite.

## Credits

Protocol reverse-engineered as part of [soundsticks-app](https://github.com/imaggg/soundsticks-app).
Built in collaboration with [Claude](https://claude.ai) (Anthropic).

## License

MIT
