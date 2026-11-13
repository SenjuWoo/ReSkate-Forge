# Release and validation procedure

## Published package contract

At the ZIP root: `manifest.json`, `icon.png` (256x256), `README.md`, optional `CHANGELOG.md`, and the actual loadable content (`reskate-plugin.json`, `parks/`, `reskate-levels.json`, or Studio's `layout.toc`/`Win32/`/stamp). `manifest.json` contains `name`, `version_number`, `website_url`, `description` (at most 250 chars) and `dependencies` array. Package name uses ASCII letters/digits/underscore, version is three numeric components; owner+name must fit the game's 64-character folder name. See official source links in `SOURCES.md`.

## Categories must be chosen on Thunderstore

| Kind | Category set | Notes |
| --- | --- | --- |
| Luau plugin | `Mods` + `Plugins` | Plugins category is **required** for ReSkate to run code from a Thunderstore-named folder |
| Custom map | `Mods` + `Maps` | Must hold **only** the map's data for in-session download; installed map-only package, not NSFW |
| Cosmetic | `Mods` + `Cosmetics` | Studio-generated game-data stamp, no paid-store donor clone |
| Park | `Mods` | An in-game Park Editor export is preferred over sample placement |

## Static checks in Forge

- Root manifest, description/version/owner/dependency patterns, README, 256px icon.
- Luau API 1 manifest, valid entry path, runtime executable/script extension/MZ restrictions, file-count gate.
- Strict `reskate-levels.json` level keys, asset name, display name, start points.
- Park schema, map key, object-count/position/quaternion/item-key rules.
- `layout.toc` requires a genuine Studio build stamp.
- Symlinks and unsafe paths refused before packaging; output ZIP CRC tested.

## Manual gates Forge cannot pretend to pass

1. Rebuild against currently supported skate. build; ensure no OUTDATED warnings in launcher.
2. Install/test on a clean profile; inspect `logs\ReSkate.log` for load/merge issues.
3. Cosmetic donor rights, UVs/materials, weight deformation, clipping, proper asset cards.
4. Map collision, grind geometry, surfaces, textures, lighting, spawn, performance and multiplayer downloading.
5. Plugin permissions, first-run approval, `plugin list`, actual behavior, reload and shutdown handling.
6. External asset licensing (e.g., Kitana mesh or modding examples), no embedded secrets, intended attribution.
7. New SemVer version, changelog, screenshots or fit check, accurate description, correct Thunderstore categories.

Release upload is deliberate and manual. This tool writes a `release-report.json` and checklist to the project, but never claims successful public upload or in-game validation.
