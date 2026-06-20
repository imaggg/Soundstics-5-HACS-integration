# Brand assets

`icon.png` / `icon@2x.png` / `logo.png` / `logo@2x.png` — generated from
[soundsticks-app](https://github.com/imaggg/soundsticks-app)'s
`assets/icon.svg` (original design, no Harman Kardon trademark).

These are **not used automatically** by Home Assistant — the device-page
logo and integration-list icon come exclusively from the separate
[home-assistant/brands](https://github.com/home-assistant/brands)
repository, keyed by domain (`soundsticks`).

## To make the logo show up in HA

1. Fork https://github.com/home-assistant/brands
2. Add these 4 files under `custom_integrations/soundsticks/`
3. Open a PR. Their CI validates dimensions/format automatically.
4. Once merged (their CDN updates within a day or so), the logo appears
   for everyone running this integration — no code change needed on our side.

This wasn't done automatically because it's a separate public repository
requiring its own PR/review from the `soundsticks-ha` maintainer.
