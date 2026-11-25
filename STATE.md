# State

- Version: 0.2.0 (first public source release).
- What it is: a CLI and an opt-in MCP server for ReSkate mods: archive inspection, workspace scaffolding for plugins, parks, maps and cosmetics, static validation, Thunderstore packaging, and bridges to ReSkate Studio's own compiler and Blender tools.
- Verified by execution: the unit suite; `new`, `validate` and `package` for a plugin workspace on Windows and Linux; the Studio command-line bridge and the headless character-swap import on the maintainer's machine.
- Not verified: anything in game. No mod built with this kit has been loaded and inspected in ReSkate yet, so every cosmetic, map and plugin result is a build or packaging result only.
- Not included: ReSkate Studio, the game, Blender, and any character or map assets. Studio is the ReSkate team's software; put your own copy in `ReSkate Studio/`.
- 2026-11-25: README rebuilt with an install section, a full command table, real-run terminal shots and the repository mark (`docs/icon.svg`); Dependabot actions update merged. No code change.
- Next: an in-game check of one cosmetic and one plugin, then record the log evidence here.
