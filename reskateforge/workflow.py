"""Project creation, Studio handoff, safe package production, local staging."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .artifacts import NAME, json_write, make_icon
from .inspect import safe_zip_name, zip_security_checks
from .validate import validate_mod


PLUGIN_MAIN = '''-- LineHUD: passive speed display, no physics or multiplayer edits.
-- ReSkate plugin API 1. Console: "gw hud on", "gw hud off", "gw hud kmh", "gw hud mph".
local shown = true
local units = "kmh"

reskate.console.command("gw hud", "LineHUD overlay: on | off | kmh | mph", function(args)
    local choice = args[1]
    if choice == "on" then
        shown = true
    elseif choice == "off" then
        shown = false
    elseif choice == "kmh" or choice == "mph" then
        units = choice
        shown = true
    else
        reskate.console.print("LineHUD: gw hud on | off | kmh | mph")
        return
    end
    reskate.console.print("LineHUD: " .. (shown and "on" or "off") .. ", " .. units)
end)

reskate.on("draw", function(d)
    if not shown then return end
    local skater = reskate.skater.get()
    if skater == nil then return end
    local speed = skater.speed or 0
    local value = units == "mph" and speed * 2.2369362921 or speed * 3.6
    d:rect(vector.create(38, 194, 0), vector.create(295, 250, 0),
           {colour = "#100b29bb", fill = true, rounding = 8})
    d:text(vector.create(53, 204, 0), string.format("%.0f %s", value, units),
           {colour = "#f0e6ff", size = 27})
end)

reskate.log("LineHUD loaded. Console: gw hud")
'''


def workspace_meta(project: Path) -> dict:
    path = project / "forge.json"
    if not path.is_file():
        raise FileNotFoundError(f"Not a ReSkateForge project: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != 1:
        raise ValueError("Unsupported forge.json schema")
    return data


def create_project(parent: Path, name: str, kind: str, owner: str, description: str, version: str = "0.1.0") -> Path:
    if kind not in {"plugin", "park", "map", "cosmetic"}:
        raise ValueError("kind must be plugin, park, map or cosmetic")
    if not NAME.fullmatch(name) or not NAME.fullmatch(owner) or len(owner + "-" + name) > 64:
        raise ValueError("Owner and name must use letters/numbers/underscore; combined Owner-Name <=64")
    if not 1 <= len(description) <= 250:
        raise ValueError("Description must have 1-250 characters")
    project = parent / name
    if project.exists():
        raise FileExistsError(project)
    mod = project / "mod"
    mod.mkdir(parents=True)
    (project / "source").mkdir()
    (project / "dist").mkdir()
    categories = {"plugin": ["Mods", "Plugins"], "park": ["Mods"], "map": ["Mods", "Maps"], "cosmetic": ["Mods", "Cosmetics"]}[kind]
    json_write(project / "forge.json", {"schema": 1, "kind": kind, "owner": owner, "name": name, "categories": categories,
                                          "notes": "Categories are selected manually at Thunderstore upload."})
    json_write(mod / "manifest.json", {"name": name, "version_number": version, "website_url": "", "description": description, "dependencies": []})
    make_icon(mod / "icon.png", "GW" if name.lower().startswith("gennywoo") else name[:2])
    (mod / "README.md").write_text(
        f"# {name.replace('_', ' ')}\n\n{description}\n\n"
        "## Install\n\nImport the zip into ReSkate Launcher's MODS page, "
        "or copy its contents into an appropriately named mod folder.\n\n"
        "## Compatibility\n\nDeveloped for ReSkate; see the release notes for tested game build and version.\n",
        encoding="utf-8")
    (mod / "CHANGELOG.md").write_text(f"# Changelog\n\n## {version}\n\n- Initial preview.\n", encoding="utf-8")
    if kind == "plugin":
        json_write(mod / "reskate-plugin.json", {"api": 1, "entry": "plugin/main.lua", "side": "client",
                                                    "permissions": ["console", "overlay", "skater.read"]})
        (mod / "plugin").mkdir()
        (mod / "plugin/main.lua").write_text(PLUGIN_MAIN, encoding="utf-8")
    elif kind == "park":
        json_write(mod / "parks" / "bam.park.json", {"format": "reskate-park", "schema_version": 1,
            "revision": 0, "maps": {"bam": [{"id": 86, "item": "own_bkpads_generic_padlow_00001",
                        "position": [-583.0, 1948.35, 1651.0], "rotation": [0.0, 0.3827, 0.0, 0.9239]}]},
            "object_scales": {"bam": {"86": 1.5}}})
    else:
        (project / "source" / "STUDIO_REQUIRED.md").write_text(
            "# Studio handoff (not yet a compiled mod)\n\n"
            "Import source meshes/maps into ReSkate Studio on Windows, then BUILD & INSTALL. "
            "Use `reskateforge adopt-studio PROJECT --from <built-mod-dir>` to copy authentic "
            "game data and build stamp into mod/. Do not fake layout.toc or .reskate-studio-patch.\n",
            encoding="utf-8")
    (project / "README.md").write_text(
        f"# {name} — Forge workspace\n\nKind: `{kind}`. Owner: `{owner}`.\n\n"
        "- `source/`: assets/workbench, NEVER automatically shipped.\n"
        "- `mod/`: only final installable files.\n"
        "- `dist/`: validated Thunderstore zip.\n\n"
        "Commands: `reskateforge validate .`, `reskateforge package .`, "
        "`reskateforge release-prep .`.\n",
        encoding="utf-8")
    return project


def adopt_studio(project: Path, source: Path) -> list[str]:
    """Import *actual* Studio output into mod/, preserving existing project files."""
    workspace_meta(project)
    if not source.is_dir(): raise NotADirectoryError(source)
    mod = project / "mod"
    allow = {"layout.toc", ".reskate-studio-patch", "reskate-levels.json", "reskate-objects.json", "reskate-build.json"}
    candidates = []
    for p in sorted(source.rglob("*")):
        if p.is_symlink(): raise ValueError(f"Studio source has symlink: {p}")
        if p.is_file():
            relative = p.relative_to(source)
            if relative.name in allow and len(relative.parts) == 1 or relative.parts[0] == "Win32":
                candidates.append(relative)
    if Path("layout.toc") not in candidates or Path(".reskate-studio-patch") not in candidates:
        raise ValueError("Studio source needs layout.toc and authentic .reskate-studio-patch")
    collisions = [r for r in candidates if (mod / r).exists()]
    if collisions:
        raise FileExistsError(f"Refusing overwrite of existing Studio files: {collisions[:5]}. Back up/remove them manually.")
    for rel in candidates:
        dst = mod / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / rel, dst)
    return [str(r).replace("\\", "/") for r in candidates]


def collect_mod_files(mod: Path) -> list[Path]:
    result = []
    for p in sorted(mod.rglob("*")):
        if p.is_symlink(): raise ValueError(f"Refusing symlink: {p}")
        if p.is_file():
            rel = p.relative_to(mod)
            if not safe_zip_name(rel.as_posix()): raise ValueError(f"Unsafe filename: {rel}")
            result.append(p)
    return result


def package_project(project: Path, output: Path | None = None, *, overwrite: bool = False) -> dict:
    meta = workspace_meta(project)
    mod = project / "mod"
    validation = validate_mod(mod, meta["owner"], meta["categories"])
    if not validation["ready"]:
        raise ValueError("Validation errors: " + "; ".join(i["message"] for i in validation["issues"] if i["severity"] == "error"))
    manifest = json.loads((mod / "manifest.json").read_text(encoding="utf-8"))
    if output is None:
        output = project / "dist" / f'{meta["owner"]}-{manifest["name"]}-{manifest["version_number"]}.zip'
    if output.resolve().is_relative_to(mod.resolve()):
        raise ValueError("Package output cannot be inside the mod/ source folder")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not overwrite: raise FileExistsError(f"Package already exists: {output}")
    files = collect_mod_files(mod)
    fd, temp = tempfile.mkstemp(prefix=".forge-", suffix=".zip", dir=output.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
            for p in files:
                rel = p.relative_to(mod).as_posix()
                info = zipfile.ZipInfo(rel, (1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                with p.open("rb") as src, z.open(info, "w", force_zip64=True) as target:
                    shutil.copyfileobj(src, target, 1024 * 1024)
        with zipfile.ZipFile(temp) as z:
            errors = zip_security_checks(z)
            if errors: raise ValueError("Unsafe produced ZIP: " + "; ".join(errors))
            if z.testzip(): raise ValueError("CRC verification failed")
        os.replace(temp, output)
    finally:
        if os.path.exists(temp): os.unlink(temp)
    return {"package": str(output), "files": len(files), "bytes": output.stat().st_size,
            "categories": meta["categories"], "validation": validation}


def release_prep(project: Path) -> dict:
    meta = workspace_meta(project)
    report = validate_mod(project / "mod", meta["owner"], meta["categories"])
    kind = meta["kind"]
    checks = [
        "Confirm there are no paid-store donor copies or third-party assets without redistribution rights.",
        "Install the package in an isolated ReSkate test profile; confirm clean load and inspect logs/ReSkate.log.",
        "Run reskateforge validate and package. Ensure no source models, internal notes, executables or secrets ship.",
        f'Select Thunderstore categories: {", ".join(meta["categories"])} (the ZIP cannot set these).',
        "Upload through Thunderstore; test installing the published package through the launcher and confirm its listing.",
    ]
    if kind in ("map", "cosmetic"):
        checks.insert(0, "Import source via current ReSkate Studio and rebuild for the current supported skate. build; preserve authentic build stamp.")
    if kind == "map":
        checks.extend(["Test map's spawn, collisions, grinds, surfaces, light, textures, loading screen and performance.",
                       "For multiplayer map download: Maps category, a map-only package, supported owner-name folder and not NSFW."])
    elif kind == "cosmetic":
        checks.append("Check original free donor, clothing fit, body visibility, textures, deformation and animations through a real Fit Check and skate session.")
    elif kind == "plugin":
        checks.extend(["Check permission prompt, plugin list, hot reload and behavior, including session/host constraints.",
                       "Plugins category is mandatory on Thunderstore; verify approved listing and user activation."])
    elif kind == "park":
        checks.append("Load actual park in the Park Editor and test every object's placement, collisions and scaling.")
    result = {"checked_utc": datetime.now(timezone.utc).isoformat(), "owner": meta["owner"],
              "name": meta["name"], "categories": meta["categories"], "validation": report,
              "human_release_checks": checks}
    json_write(project / "release-report.json", result)
    (project / "RELEASE_CHECKLIST.md").write_text("# ReSkateForge release gate\n\n" +
        "\n".join(f"- [ ] {c}" for c in checks) + "\n", encoding="utf-8")
    return result


def install_preview(project: Path, mods_dir: Path, apply: bool = False) -> dict:
    """Copy validated mod into an explicit Mods folder; no implicit game detection or overwrite."""
    meta = workspace_meta(project)
    result = validate_mod(project / "mod", meta["owner"], meta["categories"])
    if not result["ready"]: raise ValueError("Cannot install project with validation errors")
    if not mods_dir.is_dir(): raise NotADirectoryError("Pass an existing, explicit ReSkate Mods path")
    folder = f'{meta["owner"]}-{meta["name"]}'
    target = mods_dir / folder
    if target.exists(): raise FileExistsError(f"Target exists; no overwrite: {target}")
    if apply:
        from .artifacts import copy_tree
        copy_tree(project / "mod", target)
    return {"target": str(target), "would_copy_files": len(collect_mod_files(project / "mod")), "applied": apply}


def task_plan(prompt: str) -> dict:
    words = prompt.lower()
    if any(x in words for x in ("character", "model swap", "skater swap", "outfit", "cosmetic", "kitana", "mesh")):
        kind = "cosmetic"
        steps = ["Inspect source asset/rig and texture inventory", "Stage model source privately", "Compare against free donor item exported from ReSkate Studio",
                 "Retarget/fit/reweight in Blender as needed", "Import FBX/GLB in Studio's cosmetic editor and check fit/materials",
                 "Build & install against current skate. build", "Adopt actual Studio output, validate, test, package"]
    elif any(x in words for x in ("map", "world", "unity", "skater xl", "level")):
        kind = "map"
        steps = ["Inspect scene formats and licensing", "Stage Blender/FBX/GLB/Unity/Skater XL source", "Set ReSkate Studio + Skate Map add-on",
                 "Set collisions/grinds/surfaces/light/spawn", "BUILD & INSTALL in Studio", "Adopt map output with reskate-levels.json and build stamp",
                 "Validate map-only packaging, performance, multiplayer and publish"]
    elif any(x in words for x in ("park", "ramp", "rail", "build kit")):
        kind = "park"
        steps = ["Design placement data or export in-game Park Editor", "Validate .park.json object IDs/positions/quaternions",
                 "Load in game and confirm objects", "Package and test"]
    else:
        kind = "plugin"
        steps = ["Check official current Luau API and permissions", "Implement sandboxed plugin (no DLL/EXE)",
                 "Validate manifest/entry and local hot reload", "Test in game and package with Plugins category"]
    return {"classification": kind, "steps": steps,
            "boundary": "Real game-data compilation and skater rig fit need Windows/ReSkate Studio and local skate. build; never fabricate build stamps."}
