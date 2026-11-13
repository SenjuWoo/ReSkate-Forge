# ReSkateForge

**AI-first toolkit for ReSkate (the skate. mod platform)**: a portable CLI and an opt-in MCP server that scaffold, inspect, validate and package mods, and drive ReSkate Studio's own compiler and Blender tools.

Python standard library only. No game files, no Studio binaries and no character or map assets are in this repository. Blender, the game and Studio are discovered on your PC.

## Start here (Windows)

1. Clone or download this repository.
2. Get **ReSkate Studio** from the ReSkate project (<https://docs.reskate.dev/mods/studio>) and put it in a folder named `ReSkate Studio/` inside this one, with its `Native/` folder beside the executables. The validators, scaffolding and packaging work without it; the map compiler, the Blender converter and cosmetic import need it.
3. Run `Setup-Forge.cmd` (or `powershell -ExecutionPolicy Bypass -File .\Setup-Forge.ps1`). It checks the tools and writes MCP connection examples with your paths into `local-config/`. It does not change any installed AI app.
4. Run `Forge.cmd doctor` to see what is ready, then `Forge.cmd plan "<what you want to make>"` to get a route.
5. Open this folder in your AI app so `AGENTS.md` is read. To use MCP, add the server from `local-config/mcp-servers.json` or `codex-mcp.toml`; its entry point is `Forge-MCP.cmd`.

Nothing here has been verified in game yet: a passing validation or a built package is not proof that a mod loads. See `STATE.md`.

### Executable AI tools

| MCP tool | Actual functionality |
| --- | --- |
| `forge_doctor`, `forge_studio_probe` | Discover available executables, local paths and compiler help |
| `forge_studio_launch` | Open your copy of Studio on Windows |
| `forge_blender_preflight`, `forge_stage_model` | Audit meshes, rigs, materials and private source assets |
| `forge_map_import` | Import FBX/GLB/GLTF/OBJ into a fresh editable `.blend` scene |
| `forge_map_convert` | Call Studio's authentic Blender converter to write a map handshake |
| `forge_build_map` | Run `reskate_cli.exe compile-map` as specified by Studio's bundled BAT; optional deployment |
| `forge_install_blender_addon` | Install the bundled Skate Map add-on in Blender |
| `forge_new`, `forge_adopt_studio`, `forge_validate` | Manage real source projects and Studio outputs |
| `forge_package`, `forge_release_prep`, `forge_install` | Package, release checks and safe install/apply |

All compiler jobs produce inspectable logs. For a dry run, use `--dry-run` or MCP `dry_run: true`.

**Honest limitation:** cosmetic donor fitting, skinning and final cosmetic build require the Studio UI or a documented unattended cosmetic compiler contract. The Forge can launch Studio and run headless Blender preparation, but cannot claim it completed a whole-body Kitana swap until the final game output is verified.

## What's real today

| Feature | State |
| --- | --- |
| Analyze split ZIPs without concatenating/extracting gigabytes | Implemented |
| Recognize mods, plugins, game patches, cosmetics and maps in sample ZIP | Implemented (structural classification) |
| Inspect FBX model metadata, bones/meshes and PNG textures in a ZIP | Implemented |
| Stage model privately, with safe ZIP path checks | Implemented |
| Generate Luau plugin and ReSkate park workspaces | Implemented |
| Generate model-swap / map Studio-ready workspaces | Implemented |
| Compile an actual map via Studio's `reskate_cli.exe` on your Windows PC | Implemented bridge, awaiting live Windows smoke test |
| Drive Studio's real Blender converter and map imports | Implemented bridge, awaiting live Windows smoke test |
| Blender scene diagnostics and optional GLB export | Script ready; requires Blender on your PC |
| Import authentic ReSkate Studio-built patch files | Implemented (no fake stamps) |
| Validate ReSkate/Thunderstore JSON, icon, build stamp and executable bans | Implemented static checks |
| Create repeatable Thunderstore ZIPs, offline release report | Implemented |
| Install into specified ReSkate Mods folder | Implemented: preview by default, `--apply` explicit |
| Automatically create a **full working player model swap** from unrelated FBX | Not yet possible without donor rig fit, ReSkate Studio and in-game verification |
| Automatically compile/play-test maps without the installed game or Windows | Not possible in this environment |
| Publish directly to Thunderstore | Deliberately a manual final review/upload step |

## Quick start (Windows, PowerShell)

```powershell
cd C:\Path\To\ReSkateForge
.\Forge.cmd doctor
.\Forge.cmd plan "Swap my skater with Kitana"

# Source model analysis and staging; archive remains private
reskateforge inspect-model "C:\Path\To\Kitana.zip" --output kitana-report.json
reskateforge new Kitana_Skater --kind cosmetic --owner YourTeam --description "A custom Kitana-inspired skater outfit"
reskateforge stage-model "C:\Path\To\Kitana.zip" "workspaces\Kitana_Skater\source\kitana"

# After you import/fit/build in ReSkate Studio (Studio's BUILD & INSTALL)
reskateforge adopt-studio workspaces\Kitana_Skater --from "C:\Path\To\StudioBuiltMod"
reskateforge validate workspaces\Kitana_Skater
reskateforge release-prep workspaces\Kitana_Skater
reskateforge package workspaces\Kitana_Skater
```

### A sample Luau plugin

Create a plugin workspace, then validate, package and preview the install. Workspaces are yours and are not committed.

```powershell
reskateforge new Line_HUD --kind plugin --owner YourTeam --description "Shows the skater's speed"
reskateforge validate workspaces\Line_HUD
reskateforge package workspaces\Line_HUD
reskateforge install workspaces\Line_HUD --mods-dir "C:\Actual\ReSkate\Skate\Mods"
# Review the dry-run path, then explicitly install:
reskateforge install workspaces\Line_HUD --mods-dir "C:\Actual\ReSkate\Skate\Mods" --apply
```

Or drag the ZIP from `dist/` onto the launcher's MODS page and turn the plugin on when the permission prompt appears. `plugin list` in the in-game console (`~`) shows whether it loaded.

Set `RESKATE_OWNER` (or put your team name in `local-config/owner.txt`) to stop passing `--owner` each time.

## Custom map pipeline

1. `reskateforge new My_Map --kind map --owner YourTeam --description "My custom map"`.
2. Put your `.blend`, `.fbx`, `.glb`, `.gltf`, Skater XL/Unity source in `source/`.
3. For source FBX/GLB, run `Forge.cmd map-import "C:\maps\level.fbx" --output "C:\maps\level.blend"`. Existing `.blend` scenes work directly. The map converter can also be invoked explicitly with `Forge.cmd map-convert "C:\maps\level.blend" --output "C:\maps\level-handshake"`.
4. Use the included Studio Blender add-on to set collision, grind surfaces, spawn points, materials and lights. If necessary: `Forge.cmd install-blender-addon --output "C:\maps\addon-install.json"`.
5. Run `Forge.cmd build-map "C:\maps\level.blend" --output "C:\maps\My_Map_package" --game "C:\Games\ReSkate"`. Add `--deploy` only if you want Studio's compiler to deploy the result. This uses the argument contract from the actual bundled `Build Skate Map.bat`.
6. Adopt actual Studio output into your workspace with `Forge.cmd adopt-studio workspaces\My_Map --from "<actual Studio output folder>"`; validate/package. For in-session map downloading, publish as **Mods** + **Maps** and keep the package map-only.

## Park pipeline (no Studio required)

`reskateforge new My_Park --kind park --description "My rail park"` creates a valid **example JSON structure** with a demo object from official documentation. Change placements to your map, or export a real park through ReSkate's Park Editor, then test in game and package. Do not assume the example coordinates suit your location.

## AI connections (Hermes / Claude / Codex / other MCP clients)

Run `Setup-Forge.ps1` for MCP configuration using the Forge's exact absolute Windows path. The portable `Forge-MCP.cmd` is the MCP entry point for clients configured from the generated JSON/TOML. The following direct Python command also works when the agent starts in this folder:

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

For macOS/Linux change `py` to `python3`. The server supports MCP initialization, tools/list, tools/call, ping. In Claude Code/Codex also open this directory so its `AGENTS.md` and `CLAUDE.md` are read. Client config schemas differ, so use this JSON's server command/args in your app's own configuration.

Then ask: **“Use ReSkateForge to import this map model, compile it through the bundled Studio tools, test what you can and prepare a Thunderstore release.”** An agent can run the compiler on Windows; final in-game verification still needs the game itself. Cosmetic swap commands remain limited to verified Blender stages and Studio's GUI.

## Safety and provenance

The included `examples/` reports came from your downloaded mods. The **private Forge bundle** also includes your already-staged Kitana FBX and 76 textures under `workspaces/Kitana_Skater/source/`; it is not included in any Thunderstore mod package. Your Studio binaries are ignored by Git to prevent accidental public redistribution. An FBX from another game's rig does not automatically match skate.'s skeleton; no full-player swap is claimed until tested and fitted.

Read `docs/ARCHITECTURE.md`, `docs/KITANA.md`, `docs/RELEASE.md` and `docs/SOURCES.md` for the design, asset findings, release rules and official documentation.
