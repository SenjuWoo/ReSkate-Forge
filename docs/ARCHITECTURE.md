# ReSkateForge technical design

## Trust and processing boundaries

```text
User instruction / AI agent
    | CLI or MCP tools (stdlib JSON-RPC stdio)
    v
ReSkateForge workspace (forge.json)
    |-- source/ : private model, map and donor analysis inputs
    |-- mod/    : installed/published files only
    `-- dist/   : validated deterministic Thunderstore zip

Private ZIP -> segmented inspection / FBX metadata -> workbench
                                                |
                             [on Windows: installed Blender + bundled ReSkate Studio]
                                                |
                                     real built mod files and stamp
                                                |
                                adopt-studio -> validate -> package
                                                |
                                      test in-game -> publish
```

No ReSkate-generated game-data patches are fabricated. ReSkate Studio is currently the documented compiler for cosmetics and maps. Pure Luau plugins and JSON park layouts have independent pipelines.

## Modules

| Module | Responsibility |
| --- | --- |
| `inspect.py` | Split ZIP random-access reader, safe ZIP listing, FBX 7400+/7500+ metadata parsing, model archive inventory, guarded staging |
| `validate.py` | Package/owner/version/icon/README, Luau plugin manifest/blocked programs, park JSON, custom level JSON, build stamp gate |
| `workflow.py` | Project scaffolds, official API-based Luau sample, Studio output adoption, reproducible ZIP, dry-run install, release report |
| `artifacts.py` | Safe path handling, JSON writing, stdlib PNG icon generation |
| `cli.py` | Human/operator CLI |
| `mcp.py` | Portable MCP stdio tools, without installing server dependencies |
| `tools/blender_preflight.py` | Blender-only import, mesh/rig stats, missing texture detection, optional GLB export |
| `reskateforge/studio.py` | Detect all bundled tools, launch Studio, run the real map CLI and Studio Blender scripts with bounded logs |
| `tools/blender_map_ingest.py` | Convert supported model geometry into a Blender `.blend` map scene headlessly |
| `Forge.cmd` / `Forge-MCP.cmd` | No-install Windows entry points for humans and AI agents |
| `Setup-Forge.ps1` | Generate absolute-path JSON/TOML MCP connection examples without modifying host AI configs |

## ABI and runtime caveats

- The Forge's FBX parser reads metadata and does not evaluate deformers or materials. It cannot validate animation retargeting or clothing physics.
- ReSkate's plugin API and allowed permission list evolve quickly. `validate.py` checks structural manifest invariants; it does not assert that every permission name or Luau call is supported by the installed runtime. Check official version-specific docs.
- Static maps can pass JSON checks and still crash, have no collision, have broken lighting or contain a bad spawn. A real Studio build and game test are release gates.
- `.reskate-studio-patch` compatibility is checked by ReSkate itself, not by blindly interpreting an undocumented stamp format.
- The bundled `Build Skate Map.bat` confirms `reskate_cli.exe compile-map GAME BLEND PACKAGE [--deploy]`; the Forge implements this exact argument vector. Model/cosmetic build commands remain unconfirmed and should be probed on Windows, not guessed.
- ZIPs from strangers are untrusted; do not execute or import their scripts as code. Existing `.toc`/`.cas`/`.fas` bundles are for structural analysis only.
- `new` never overwrites a project, `package` refuses an existing ZIP without explicit `--overwrite`, `adopt-studio` refuses collisions, and `install` refuses pre-existing mod folders even with `--apply`.

## Future backlog

1. Cosmetic donor fitting/build automation after confirming the CLI argument interface or Studio project schema (map compilation already implemented).
2. Donor-rig bone correspondence and configurable weight-transfer workflows in Blender, with screenshots and animation validation.
3. Optional map geometry QA (collision, rail length, normals, material budgets, large-scene LOD) from Blender mesh audits.
4. Launch ReSkate test profile and parse `ReSkate.log` on the user's Windows machine, without interfering with normal Steam skate.
5. CI publishing dry runs and Thunderstore API status polling for categories/build availability (no automatic credential capture).
6. Broader parsers for `.toc`/`.cas`/`.fas` dependency graphs, only after established binary format contracts and tests.

## Source input versus publication

Do not copy third-party mods into another author's release. Archive reports only list metadata. The Kitana FBX is the user's inspection sample, and its mesh/textures stay in the private staging area. Distribution rights and donor selection require separate confirmation.
