# Changelog

## Unreleased - 2026-11-25

Documentation and CI only; the package is unchanged.

- README rewritten: install steps for Windows and pip, a full command table, the MCP tool list including `forge_plan` and the inspectors, and terminal shots from real runs in `docs/presentation/`.
- README and AGENTS.md no longer describe ReSkate Studio or a staged model as bundled in this repository. Both stay out of Git.
- The pip install step is editable (`pip install -e .`): Studio, `tools/` and `local-config/` are found next to the package.
- The map-compile and converter bridges are listed as implemented with no live run recorded yet; the headless character swap is listed as run on the maintainer's machine and not loaded in game, matching STATE.md.
- `docs/icon.svg` and `docs/icon.png`: the RS tile that `new` draws for workspaces, as the repository mark.
- CI: Dependabot for pip and GitHub Actions; `actions/checkout` and `actions/setup-python` moved to v7.

## 0.2.0 - 2026-11-12

First public source release.

- CLI and opt-in MCP server: `doctor`, `plan`, archive inspection, `new` for plugin, park, map and cosmetic workspaces, static validation, Thunderstore packaging, release preparation and a preview-by-default install.
- Bridges to ReSkate Studio's command-line compiler and Blender tools, and a headless character-swap pipeline under `tools/character_swap/`.
- ReSkate Studio is not included; place your own copy in `ReSkate Studio/`.
- The four `.cmd` launchers pin delayed expansion off, so a folder whose name contains `!` works.
- Nothing has been verified in game yet.
