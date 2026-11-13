"""Command-line entry point for the portable ReSkate mod workbench."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from .artifacts import json_write
from .inspect import inspect_mod_archive, inspect_model_zip, stage_model
from .validate import validate_mod
from .studio import blender_job, build_map, default_owner, diagnostics, launch_studio, probe_compiler
from .workflow import (adopt_studio, create_project, install_preview, package_project,
                       release_prep, task_plan, workspace_meta)


def doctor() -> dict:
    local = os.environ.get("LOCALAPPDATA")
    documents = Path(os.environ.get("USERPROFILE", "")) / "Documents" if os.environ.get("USERPROFILE") else None
    return {
        "platform": sys.platform, "python": sys.version.split()[0],
        "tools": {n: shutil.which(n) for n in ("blender", "git", "python", "py", "luau")},
        "studio": diagnostics(),
        "reskate_game_settings": str(Path(local) / "ReSkate" / "Game") if local else None,
        "reskate_studio_projects": str(documents / "ReSkate Studio" / "Projects") if documents else None,
        "notes": ["Studio/game builds require Windows, the installed skate. and ReSkate Studio.",
                  "Forge does not patch or inject into game executables.",
                  "Provide the actual ReSkate Mods folder to install --apply; no game folders are guessed."],
    }


def run(args: argparse.Namespace) -> object:
    action = args.action
    if action == "doctor": return doctor()
    if action == "launch-studio": return launch_studio()
    if action == "studio-probe": return probe_compiler()
    if action == "build-map":
        return build_map(Path(args.source), Path(args.output), game=args.game,
                         deploy=args.deploy, dry_run=args.dry_run)
    if action in {"blender-preflight", "map-import", "map-convert", "install-blender-addon"}:
        return blender_job(action, Path(args.source) if getattr(args, "source", None) else None,
                           output=Path(args.output), blender=args.blender, dry_run=args.dry_run)
    if action == "plan": return task_plan(args.request)
    if action == "inspect-archive":
        result = inspect_mod_archive([Path(x) for x in args.parts])
        if args.output: json_write(Path(args.output), result)
        return result if args.verbose else {k: v for k, v in result.items() if k != "mods"} | {"mods": [{"folder": m["folder"], "kinds": m["kinds"], "entries": m["entries"]} for m in result["mods"]]}
    if action == "inspect-model":
        result = inspect_model_zip(Path(args.archive))
        if args.output: json_write(Path(args.output), result)
        return result if args.verbose else {k: v for k, v in result.items() if k != "textures"}
    if action == "stage-model":
        result = stage_model(Path(args.archive), Path(args.destination))
        return {"destination": args.destination, "models": len(result["models"]), "textures": result["texture_count"]}
    if action == "new":
        path = create_project(Path(args.root), args.name, args.kind, args.owner, args.description, args.version)
        return {"project": str(path), "kind": args.kind}
    if action == "adopt-studio":
        paths = adopt_studio(Path(args.project), Path(args.from_dir))
        return {"adopted": paths, "count": len(paths)}
    if action == "validate":
        project = Path(args.project)
        meta = workspace_meta(project)
        return validate_mod(project / "mod", meta["owner"], meta["categories"])
    if action == "package": return package_project(Path(args.project), Path(args.output) if args.output else None, overwrite=args.overwrite)
    if action == "release-prep": return release_prep(Path(args.project))
    if action == "install": return install_preview(Path(args.project), Path(args.mods_dir), args.apply)
    if action == "character-swap":
        import subprocess
        script = Path(__file__).resolve().parent.parent / "tools" / "character_swap" / "build.py"
        cmd = [sys.executable, "-I", str(script), args.config, "--stage", args.stage]
        if args.blender: cmd += ["--blender", args.blender]
        if args.game: cmd += ["--game", args.game]
        rc = subprocess.run(cmd).returncode
        return {"success": rc == 0, "config": args.config, "stage": args.stage}
    if action == "mcp":
        from .mcp import serve
        return serve()
    raise ValueError(f"Unsupported action: {action}")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="reskateforge", description="ReSkateForge: build/validate/package AI-assisted ReSkate mods")
    sp = p.add_subparsers(dest="action", required=True)
    sp.add_parser("doctor", help="Report local tool and ReSkate Studio prerequisites")
    sp.add_parser("launch-studio", help="Launch bundled ReSkate Studio on Windows")
    sp.add_parser("studio-probe", help="Run the bundled compiler's --help for capability discovery on Windows")
    q = sp.add_parser("build-map", help="Compile a .blend through bundled ReSkate Studio CLI (verified BAT syntax)")
    q.add_argument("source", help="Existing .blend map scene")
    q.add_argument("--output", required=True, help="Fresh game-map build directory")
    q.add_argument("--game", help="Local ReSkate game directory; defaults to RESKATE_GAME or discovered local folder")
    q.add_argument("--deploy", action="store_true", help="Also deploy into the game; game must be closed")
    q.add_argument("--dry-run", action="store_true", help="Show command; do not run external executable")
    for name, description in (
        ("blender-preflight", "Read mesh/rig stats via Blender, detect missing textures"),
        ("map-import", "Import FBX/GLB/GLTF/OBJ into a new editable Blender map scene"),
        ("map-convert", "Run Studio's actual Blender map converter into its map.json handshake"),
        ("install-blender-addon", "Install/refresh the bundled Skate Map add-on in Blender"),
    ):
        q = sp.add_parser(name, help=description)
        if name != "install-blender-addon":
            q.add_argument("source")
        q.add_argument("--output", required=True)
        q.add_argument("--blender", help="Explicit blender.exe path (or RESKATE_BLENDER)")
        q.add_argument("--dry-run", action="store_true")
    q = sp.add_parser("plan", help="Route a natural-language idea to a realistic forge pipeline")
    q.add_argument("request")
    q = sp.add_parser("inspect-archive", help="Inspect a split archive in supplied sequential order without extracting")
    q.add_argument("parts", nargs="+", help="Parts in order (names may differ after uploads)")
    q.add_argument("--output", help="Write full JSON inventory")
    q.add_argument("--verbose", action="store_true", help="Print full file samples and manifests")
    q = sp.add_parser("inspect-model", help="Analyze a ZIP containing FBX and texture assets")
    q.add_argument("archive")
    q.add_argument("--output")
    q.add_argument("--verbose", action="store_true")
    q = sp.add_parser("stage-model", help="Extract allowed model files to a private workbench; never to public package")
    q.add_argument("archive")
    q.add_argument("destination")
    q = sp.add_parser("new", help="Create a new mod project with manifests, icon and starter files")
    q.add_argument("name")
    q.add_argument("--kind", choices=("plugin", "park", "map", "cosmetic"), required=True)
    q.add_argument("--owner", default=default_owner(), help="Thunderstore team name (default: RESKATE_OWNER, then local-config/owner.txt)")
    q.add_argument("--description", required=True)
    q.add_argument("--version", default="0.1.0")
    q.add_argument("--root", default="workspaces")
    q = sp.add_parser("adopt-studio", help="Bring authentic built data and version stamp into mod/")
    q.add_argument("project")
    q.add_argument("--from", dest="from_dir", required=True)
    q = sp.add_parser("validate", help="Validate content and Thunderstore categories")
    q.add_argument("project")
    q = sp.add_parser("package", help="Validate and produce a deterministic Thunderstore ZIP")
    q.add_argument("project")
    q.add_argument("--output")
    q.add_argument("--overwrite", action="store_true")
    q = sp.add_parser("release-prep", help="Write publication checks and validation results")
    q.add_argument("project")
    q = sp.add_parser("install", help="Preview or explicitly copy into a specified existing ReSkate Mods directory")
    q.add_argument("project")
    q.add_argument("--mods-dir", required=True)
    q.add_argument("--apply", action="store_true", help="Actually copy; without this flag makes no changes")
    q = sp.add_parser("character-swap", help="Fit a rigged FBX character onto the skate. skeleton and import it as a full-body costume (see docs/CHARACTER_SWAP.md)")
    q.add_argument("config", help="Workspace swap_config.json")
    q.add_argument("--stage", default="all", help="dump,tex,glb,import or all")
    q.add_argument("--blender", help="Explicit blender.exe (or RESKATE_BLENDER)")
    q.add_argument("--game", help="skate. game folder (or RESKATE_GAME)")
    sp.add_parser("mcp", help="Start MCP stdio server for Hermes, Codex, Claude, etc.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = run(args)
        if result is not None:
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return 1 if isinstance(result, dict) and (result.get("ready") is False or result.get("success") is False) else 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError, TimeoutError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
