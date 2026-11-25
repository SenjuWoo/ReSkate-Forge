<div align="center">

![ReSkateForge: the pixel-letter RS tile with a cyan bar inside a violet frame, next to the tagline 'Scaffold, check and package ReSkate mods for skate., and drive ReSkate Studio's own compiler.' and chips for Luau plugins, parks, maps, cosmetics and Thunderstore zip](docs/presentation/hero.png)

[![Checks](https://github.com/SenjuWoo/ReSkate-Forge/actions/workflows/test.yml/badge.svg)](https://github.com/SenjuWoo/ReSkate-Forge/actions/workflows/test.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-35c8e3)](pyproject.toml)
[![Dependencies](https://img.shields.io/badge/runtime%20deps-none-a594ff)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-6757be)](LICENSE)

**[Install](#install)** · **[Tour](#a-short-tour)** · **[Commands](#commands)** · **[Pipelines](#pipelines)** · **[AI and MCP](#ai-and-mcp)** · **[How it works](#how-it-works)** · **[Changelog](CHANGELOG.md)**

</div>

ReSkateForge is a command-line workbench and an opt-in MCP server for
**ReSkate**, the mod platform for skate. It scaffolds plugin, park, map and
cosmetic workspaces, inspects source archives without extracting them, checks
packages against ReSkate and Thunderstore rules, builds deterministic
Thunderstore zips, and drives ReSkate Studio's own compiler and Blender tools
when you have them. It uses the Python standard library only. No game files,
Studio binaries, or character or map assets are in this repository.

Nothing here has been verified in game yet. A passing validation or a built
package is not proof that a mod loads; see [STATE.md](STATE.md).

## What you get

- **Workspaces that pass the rules.** `new` writes a Luau plugin (API 1), a park, a map or a cosmetic workspace with `manifest.json`, a 256x256 icon, README and starter files. Source stays in `source/`; only `mod/` is published.
- **Checks before you upload.** `validate` checks the manifest fields, name and version patterns, the icon, the plugin manifest and entry path, `reskate-levels.json`, park schema and item keys, and refuses executables, Windows scripts and MZ binaries inside a plugin.
- **Repeatable packages.** `package` validates first, then writes a deterministic Thunderstore zip and tests its CRC. `release-prep` writes the manual release checklist for that package kind.
- **Safe installs.** `install` only previews until you pass `--apply`, and `--apply` refuses an existing destination.
- **Source archives, read-only.** `inspect-archive` reads a split zip in the order you give without concatenating or extracting gigabytes. `inspect-model` reads FBX metadata, bones, meshes and PNG textures inside a zip.
- **Bridges to the real tools.** `build-map` runs Studio's `reskate_cli.exe compile-map` with the argument vector from Studio's own `Build Skate Map.bat`. `map-import`, `map-convert`, `blender-preflight` and `character-swap` run Blender headless.
- **JSON everywhere.** Every command prints JSON. Exit code 0 is ok, 1 means a check or an external build reported failure (`ready` or `success` false), 2 is a named error printed as `{"error": ...}` on stderr.

![Terminal: python -m reskateforge new Line_HUD creates a plugin workspace; validate reports ready true with one manual-plugin warning; package writes ExampleTeam-Line_HUD-0.1.0.zip with 6 files and 3535 bytes for the Mods and Plugins categories; install with --mods-dir Mods reports would_copy_files 6 and applied false](docs/presentation/screenshot-plugin.png)

## Install

Requirements: Python 3.10 or newer. Windows for anything that runs ReSkate
Studio or the game. Optional, and `doctor` tells you which ones it found:

| Tool | Unlocks |
|---|---|
| [ReSkate Studio](https://docs.reskate.dev/mods/studio), placed in a folder named `ReSkate Studio/` inside this one, with its `Native/` folder beside the executables | `build-map`, `map-convert`, `launch-studio`, `studio-probe`, `install-blender-addon`, the cosmetic import in `character-swap` |
| Blender (found on PATH, through Steam, or set `RESKATE_BLENDER`) | `map-import`, `map-convert`, `blender-preflight`, `character-swap` |
| The ReSkate-managed skate. game folder (set `RESKATE_GAME` or pass `--game`) | `build-map`, `character-swap` |

The validators, scaffolding and packaging work without any of them.

**Windows:**

```powershell
git clone https://github.com/SenjuWoo/ReSkate-Forge
cd ReSkate-Forge
.\Setup-Forge.cmd          # runs doctor, writes MCP examples into local-config\
.\Forge.cmd doctor
```

`Setup-Forge.cmd` does not change any installed AI app. `Forge.cmd <command>`
runs the CLI from this folder.

**Any OS:**

```bash
python -m pip install -e .  # adds the reskateforge command, run from this checkout
reskateforge doctor
```

Install it editable (`-e`) and keep the checkout: `ReSkate Studio/`, `tools/`
and `local-config/` are found next to the package, so a plain copy into
site-packages would lose them. From a checkout without installing,
`python -m reskateforge <command>` is the same CLI. Set `RESKATE_OWNER` (or put your team name in
`local-config/owner.txt`) to stop passing `--owner` each time.

## A short tour

```text
reskateforge doctor                                   # tools, Studio, Blender and game paths
reskateforge plan "make a speed HUD plugin"           # route an idea to a pipeline
reskateforge plan "Swap my skater with Kitana"
reskateforge new Line_HUD --kind plugin --owner YourTeam --description "Shows the skater's speed"
reskateforge validate workspaces/Line_HUD
reskateforge package workspaces/Line_HUD              # zip in workspaces/Line_HUD/dist
reskateforge install workspaces/Line_HUD --mods-dir "<ReSkate game>\Mods"           # preview
reskateforge install workspaces/Line_HUD --mods-dir "<ReSkate game>\Mods" --apply   # copy
```

Or drag the zip from `dist/` onto the launcher's MODS page and turn the plugin
on when the permission prompt appears. `plugin list` in the in-game console
(`~`) shows whether it loaded.

![Terminal: reskateforge plan "import my blender map into skate" classifies the request as a map and lists seven steps from staging the source through Studio's BUILD & INSTALL to map-only packaging; after a helper.dll is dropped into the plugin, validate reports ready false with the error plugin-program, executable or script extension forbidden in a plugin](docs/presentation/screenshot-plan-guard.png)

## Commands

| Command | Does | Needs |
|---|---|---|
| `doctor` | Reports Python, Blender, Studio, the game folder and what can be automated | - |
| `plan "<idea>"` | Routes an idea to a plugin, park, map or cosmetic pipeline with its limits | - |
| `new NAME --kind plugin\|park\|map\|cosmetic` | Creates a workspace with manifest, icon and starter files | - |
| `validate PROJECT` | Static checks for content and Thunderstore rules | - |
| `package PROJECT` | Validates, then writes a deterministic Thunderstore zip | - |
| `release-prep PROJECT` | Writes the release checklist and validation result | - |
| `install PROJECT --mods-dir DIR [--apply]` | Previews, or with `--apply` copies into an existing Mods folder | - |
| `inspect-archive PART...` | Inventories a split zip in the given order without extracting | - |
| `inspect-model ZIP` | FBX metadata, bones, meshes and textures inside a zip | - |
| `stage-model ZIP DEST` | Extracts allowed model files to a private workbench with safe path checks | - |
| `adopt-studio PROJECT --from DIR` | Copies real Studio build output and its stamp into `mod/`, never overwriting | - |
| `build-map BLEND --output DIR [--game G] [--deploy] [--dry-run]` | Runs Studio's `reskate_cli.exe compile-map` | Studio, game |
| `map-import SOURCE --output X.blend` | Imports FBX/GLB/GLTF/OBJ into a fresh editable Blender scene | Blender |
| `map-convert X.blend --output DIR` | Runs Studio's own `studio_map_import.py` to write the map handshake | Studio, Blender |
| `blender-preflight SOURCE --output R.json` | Mesh, rig and missing-texture report | Blender |
| `install-blender-addon --output R.json` | Installs Studio's Skate Map add-on into Blender | Studio, Blender |
| `launch-studio` / `studio-probe` | Opens Studio / prints its compiler help | Studio |
| `character-swap CONFIG [--stage dump\|tex\|glb\|import\|all]` | Fits a rigged FBX onto the skate. skeleton and imports it as a full-body costume ([docs/CHARACTER_SWAP.md](docs/CHARACTER_SWAP.md)) | Blender, Studio, game |
| `mcp` | MCP server on stdin/stdout | - |

Every compiler job writes an inspectable log next to its output
(`<output>.blender.log` or `<output>.compile.log`). `--dry-run` (MCP
`dry_run: true`) shows the command without running it.

### What is real today

| Feature | State |
| --- | --- |
| Analyze split zips without concatenating or extracting gigabytes | Implemented |
| Recognize mods, plugins, game patches, cosmetics and maps in a sample zip | Implemented (structural classification) |
| Inspect FBX model metadata, bones, meshes and PNG textures in a zip | Implemented |
| Stage a model privately, with safe zip path checks | Implemented |
| Luau plugin and park workspaces | Implemented |
| Model-swap and map workspaces ready for Studio | Implemented |
| Compile a map through Studio's `reskate_cli.exe` | Bridge implemented; no live map compile recorded yet |
| Drive Studio's Blender converter and map imports | Bridge implemented; no live run recorded yet |
| Headless character swap to a Studio `.fbproject` | Ran on the maintainer's machine; not loaded in game |
| Blender scene diagnostics and optional GLB export | Script ready; needs Blender |
| Adopt real ReSkate Studio patch files | Implemented (no fake stamps) |
| Validate ReSkate/Thunderstore JSON, icon, build stamp and executable bans | Implemented static checks |
| Repeatable Thunderstore zips, offline release report | Implemented |
| Install into a given ReSkate Mods folder | Implemented: preview by default, `--apply` explicit |
| A **full working player model swap** from an unrelated FBX, unattended | Not yet: needs a donor rig fit in Studio and an in-game check |
| Compile or play-test maps without the installed game on Windows | Not possible |
| Publish to Thunderstore | Deliberately manual |

Cosmetic donor fitting, skinning and the final cosmetic build go through the
Studio UI. The forge can launch Studio and run the headless Blender stages, but
it cannot claim it completed a whole-body Kitana swap until the final game
output is verified.

## Pipelines

### Cosmetic or model swap

```powershell
# Source model analysis and staging; the archive stays private
reskateforge inspect-model "<path>\Kitana.zip" --output kitana-report.json
reskateforge new Kitana_Skater --kind cosmetic --owner YourTeam --description "A custom Kitana-inspired skater outfit"
reskateforge stage-model "<path>\Kitana.zip" "workspaces\Kitana_Skater\source\kitana"

# After you import, fit and build in ReSkate Studio (BUILD & INSTALL):
reskateforge adopt-studio workspaces\Kitana_Skater --from "<Studio build output>"
reskateforge validate workspaces\Kitana_Skater
reskateforge release-prep workspaces\Kitana_Skater
reskateforge package workspaces\Kitana_Skater
```

### Custom map

1. `reskateforge new My_Map --kind map --owner YourTeam --description "My custom map"`.
2. Put your `.blend`, `.fbx`, `.glb`, `.gltf`, or Skater XL/Unity source in `source/`.
3. For FBX/GLB, `reskateforge map-import "<path>\level.fbx" --output "<path>\level.blend"`. An existing `.blend` works directly. The converter can also be called on its own: `reskateforge map-convert "<path>\level.blend" --output "<path>\level-handshake"`.
4. Use Studio's Skate Map add-on in Blender for collision, grind surfaces, spawn points, materials and lights (`reskateforge install-blender-addon --output addon-install.json` if it is missing).
5. `reskateforge build-map "<path>\level.blend" --output "<path>\My_Map_package" --game "<ReSkate game folder>"`. Add `--deploy` only if Studio's compiler should deploy the result; the game must be closed.
6. `reskateforge adopt-studio workspaces\My_Map --from "<Studio output folder>"`, then validate and package. For in-session map download, publish under **Mods** + **Maps** and keep the package map-only.

### Park (no Studio needed)

`reskateforge new My_Park --kind park --description "My rail park"` writes a
valid example `parks/<map>.park.json` with one demo object from the official
documentation. Change the placements for your map, or export a real park from
ReSkate's Park Editor, then test in game and package. The example coordinates
are not meant for your location.

## AI and MCP

Open this folder in your AI app so `AGENTS.md` and `CLAUDE.md` are read.
`Setup-Forge.cmd` writes MCP examples with this folder's absolute path into
`local-config/mcp-servers.json` and `local-config/codex-mcp.toml`; their entry
point is `Forge-MCP.cmd`. Started from this folder, the plain Python command
works too:

```json
{
  "mcpServers": {
    "reskateforge": {
      "command": "py",
      "args": ["-m", "reskateforge", "mcp"]
    }
  }
}
```

On macOS or Linux use `python3` instead of `py`. The server answers
`initialize`, `tools/list`, `tools/call` and `ping`. Client config schemas
differ, so copy this command and its arguments into your app's own format.

Then ask: **"Use ReSkateForge to import this map model, compile it through
Studio's tools, test what you can and prepare a Thunderstore release."** An
agent can run the compiler on Windows; the final in-game check still needs the
game itself. Cosmetic swaps stay limited to the verified Blender stages and
Studio's UI.

| MCP tool | Runs |
| --- | --- |
| `forge_doctor`, `forge_studio_probe` | Tool and path discovery, Studio compiler help |
| `forge_plan` | Route an idea to a pipeline |
| `forge_studio_launch` | Open your copy of Studio on Windows |
| `forge_inspect_archive`, `forge_inspect_model` | Read-only archive and model inventories |
| `forge_blender_preflight`, `forge_stage_model` | Mesh, rig and material audit; private source staging |
| `forge_map_import` | FBX/GLB/GLTF/OBJ into a fresh `.blend` scene |
| `forge_map_convert` | Studio's Blender converter, writing the map handshake |
| `forge_build_map` | `reskate_cli.exe compile-map`; deploys only with `deploy: true` |
| `forge_install_blender_addon` | Studio's Skate Map add-on into Blender |
| `forge_new`, `forge_adopt_studio`, `forge_validate` | Workspaces and real Studio output |
| `forge_package`, `forge_release_prep`, `forge_install` | Packaging, release checks, preview or apply install |

## How it works

- `reskateforge/cli.py` is the argparse front end; `mcp.py` maps each MCP tool onto the same CLI commands.
- `workflow.py` writes workspaces and packages; `validate.py` holds the static rules; `inspect.py` reads zips and FBX headers without extracting; `artifacts.py` does the safe file writes and draws the workspace icon.
- `studio.py` finds Studio, Blender and the game and builds the exact external command lines. Studio, Blender and the game are discovered, never bundled.
- `tools/` holds the Blender scripts and the headless character-swap stages (`tools/character_swap/`).
- Packages contain only `mod/`. Symlinks and unsafe paths are refused before packaging, and each zip's CRC is tested after writing.

Release rules and the manual gates the forge cannot pass for you are in
[docs/RELEASE.md](docs/RELEASE.md). Design notes are in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), official references in
[docs/SOURCES.md](docs/SOURCES.md), and a worked FBX evaluation in
[docs/KITANA.md](docs/KITANA.md).

## Safety and provenance

- ReSkate Studio is the ReSkate team's software. Bring your own copy; the `ReSkate Studio/` folder is ignored by Git so it is never redistributed.
- `workspaces/` and `local-config/` are ignored by Git. Staged source models and textures stay in a workspace's `source/` and never go into a package.
- `examples/` holds metadata reports about sample mod archives and one sample FBX, not the files themselves. Use them as packaging references, not content to copy.
- An FBX from another game's rig does not match skate.'s skeleton by itself. No full-player swap is claimed until it has been fitted and tested.

## Development

```bash
python -m unittest discover -s tests -v
```

The Studio-file tests skip where ReSkate Studio is not installed. CI runs the
suite on Python 3.10, 3.12 and 3.14, then a plugin `new`, `validate` and
`package` smoke run.

## License

MIT. See [LICENSE](LICENSE). ReSkate Studio, skate. and any game or
third-party assets are not covered and are not included.
