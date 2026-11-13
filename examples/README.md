# Observed examples (metadata only)

The user's four uploaded parts form a single valid continuous ZIP: in order,

1. `Mods.zip(2).001`
2. `Mods.zip(2).002`
3. `Mods.zip.003`
4. `Mods.zip.004`

The mixed filenames are upload-side naming; the final ZIP directory resolves correctly over all four. No multi-gigabyte extracted copy is required to inspect it.

Observed 922 ZIP entries spanning 27 mod folders, 2,666,285,679 uncompressed bytes. Structural type counts (overlapping categories) are 16 game-data mods, 14 Luau plugins and 2 custom map packages. Examples include `333-Skate_3_Improved`, `Aronixe-InfinitePark`, cosmetic bundles by Extilo and a range of HUD/gameplay Luau plugins.

- `thunderstore-sample-inventory.json`: each actual package manifest, source paths (capped at 60 sample files per mod), plugin manifest metadata and map names. No executable code or private assets were extracted.
- `kitana-preflight.json`: read-only metadata and texture names for the supplied Kitana FBX ZIP. The original third-party FBX/PNGs are not reproduced here.

**Use these examples as package references, not content to copy into releases.**
