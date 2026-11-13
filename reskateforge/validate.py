"""Offline, conservative publication checks from official ReSkate documentation."""

from __future__ import annotations

import json
import math
import re
import struct
from dataclasses import asdict, dataclass
from pathlib import Path

from .artifacts import NAME, VERSION, WINDOWS_PROGRAM_EXTENSIONS


@dataclass
class Issue:
    severity: str
    code: str
    message: str


def add(issues: list[Issue], severity: str, code: str, message: str) -> None:
    issues.append(Issue(severity, code, message))


def _load(path: Path, issues: list[Issue], max_size: int) -> object | None:
    if not path.is_file():
        add(issues, "error", "missing-file", f"Missing: {path.name}")
        return None
    if path.stat().st_size > max_size:
        add(issues, "error", "file-size", f"{path.name} exceeds {max_size} bytes")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        add(issues, "error", "json", f"{path.name}: {exc}")
        return None


def manifest_check(mod: Path, issues: list[Issue], owner: str | None) -> dict | None:
    m = _load(mod / "manifest.json", issues, 32 * 1024)
    if not isinstance(m, dict):
        if m is not None: add(issues, "error", "manifest-type", "manifest.json must be an object")
        return None
    name, ver, desc = m.get("name"), m.get("version_number"), m.get("description")
    if not isinstance(name, str) or not NAME.fullmatch(name) or len(name) > 64:
        add(issues, "error", "manifest-name", "Package name must be 1-64 ASCII letters, numbers, underscores")
    if not isinstance(ver, str) or not VERSION.fullmatch(ver):
        add(issues, "error", "manifest-version", "version_number must be x.y.z")
    if not isinstance(desc, str) or not 1 <= len(desc) <= 250:
        add(issues, "error", "manifest-description", "description must be 1-250 characters")
    website = m.get("website_url", "")
    if not isinstance(website, str) or (website and not website.startswith("https://")):
        add(issues, "warning", "website", "Use an HTTPS website_url or empty string")
    deps = m.get("dependencies")
    if not isinstance(deps, list) or any(not isinstance(x, str) or not re.fullmatch(r"[A-Za-z0-9_]+-[A-Za-z0-9_]+-\d+\.\d+\.\d+", x) for x in deps):
        add(issues, "error", "dependencies", "Use dependencies like Owner-Package-1.0.0")
    if owner and (not NAME.fullmatch(owner) or not name or len(owner + "-" + str(name)) > 64):
        add(issues, "error", "owner-folder", "Thunderstore Owner-Name must be valid and at most 64 characters")
    return m


def icon_readme_check(mod: Path, issues: list[Issue]) -> None:
    icon = mod / "icon.png"
    if not icon.exists():
        add(issues, "error", "icon", "Missing 256x256 icon.png")
    elif icon.stat().st_size < 24:
        add(issues, "error", "icon", "Invalid PNG")
    else:
        with icon.open("rb") as f: header = f.read(24)
        if not header.startswith(b"\x89PNG\r\n\x1a\n") or struct.unpack(">II", header[16:24]) != (256, 256):
            add(issues, "error", "icon", "icon.png must be a 256x256 PNG")
    readme = mod / "README.md"
    if not readme.is_file() or not readme.stat().st_size:
        add(issues, "error", "readme", "README.md must exist and explain mod use")
    elif readme.stat().st_size > 512 * 1024:
        add(issues, "error", "readme-size", "README.md exceeds launcher limit of 512 KB")
    elif len(readme.read_text(encoding="utf-8", errors="replace").splitlines()) > 400:
        add(issues, "warning", "readme-length", "Thunderstore launcher displays at most 400 lines")


def plugin_check(mod: Path, issues: list[Issue]) -> None:
    data = _load(mod / "reskate-plugin.json", issues, 64 * 1024)
    if not isinstance(data, dict):
        add(issues, "error", "plugin-json", "reskate-plugin.json must be an object")
        return
    if type(data.get("api")) is not int or data["api"] != 1:
        add(issues, "error", "plugin-api", "Plugin api must be integer 1 for current documented API")
    entry = data.get("entry")
    if not isinstance(entry, str) or len(entry) > 260 or not entry.endswith((".lua", ".luau")) or "\\" in entry or ":" in entry or any(s in ("", ".", "..") or s.endswith((".", " ")) for s in entry.split("/")):
        add(issues, "error", "plugin-entry", "entry must be a safe, relative .lua/.luau path")
    elif not (mod / entry).is_file():
        add(issues, "error", "plugin-entry-missing", f"Missing plugin entry {entry}")
    elif (mod / entry).stat().st_size > 1024 * 1024:
        add(issues, "error", "plugin-entry-size", "Plugin entry exceeds 1 MB")
    if data.get("side", "client") not in ("client", "server", "both"):
        add(issues, "error", "plugin-side", "side must be client, server or both")
    permissions = data.get("permissions", [])
    if not isinstance(permissions, list) or any(not isinstance(x, str) for x in permissions):
        add(issues, "error", "plugin-permissions", "permissions must be an array of names")
    if len(list(mod.rglob("*"))) > 20000:
        add(issues, "error", "plugin-files", "Plugins cannot contain over 20,000 files")
    for path in mod.rglob("*"):
        if not path.is_file(): continue
        if path.suffix.lower() in WINDOWS_PROGRAM_EXTENSIONS:
            add(issues, "error", "plugin-program", f"Executable/script extension forbidden in a plugin: {path.relative_to(mod)}")
        else:
            with path.open("rb") as f: head = f.read(2)
            if head == b"MZ":
                add(issues, "error", "plugin-mz", f"Windows program signature forbidden: {path.relative_to(mod)}")


def map_check(mod: Path, issues: list[Issue]) -> None:
    m = _load(mod / "reskate-levels.json", issues, 64 * 1024)
    if not isinstance(m, dict):
        add(issues, "error", "maps", "reskate-levels.json must be an object")
        return
    if set(m) != {"schema", "levels"} or type(m.get("schema")) is not int or m["schema"] != 1:
        add(issues, "error", "map-schema", "reskate-levels.json requires exactly schema:1 and levels")
    levels = m.get("levels")
    if not isinstance(levels, list) or len(levels) > 64:
        add(issues, "error", "map-levels", "levels must be an array of at most 64 entries")
        return
    seen = set()
    for idx, level in enumerate(levels):
        if not isinstance(level, dict) or set(level) != {"asset", "displayName", "startPoints"}:
            add(issues, "error", "map-entry", f"Level {idx}: exactly asset, displayName, startPoints required")
            continue
        asset = level["asset"]
        if not isinstance(asset, str) or len(asset) > 255 or not re.fullmatch(r"levels/game/(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+", asset):
            add(issues, "error", "map-asset", f"Level {idx}: invalid level asset name")
        if asset in seen: add(issues, "error", "map-duplicate", f"Duplicate level asset: {asset}")
        seen.add(asset)
        title = level["displayName"]
        if not isinstance(title, str) or not 1 <= len(title.encode("utf-8")) <= 96 or any(ord(ch) < 32 for ch in title):
            add(issues, "error", "map-title", f"Level {idx}: displayName must be 1-96 UTF-8 bytes without control chars")
        points = level["startPoints"]
        if not isinstance(points, list) or len(points) > 64 or any(not isinstance(s, str) or not re.fullmatch(r"[A-Za-z0-9 /_.-]{1,127}", s) for s in points) or len(points) != len(set(points)):
            add(issues, "error", "map-start", f"Level {idx}: invalid/duplicate startPoints")


def park_check(mod: Path, issues: list[Issue]) -> None:
    files = list((mod / "parks").rglob("*.park.json"))
    if len(files) > 16:
        add(issues, "error", "park-count", "Park mod may contain up to 16 park maps")
    for path in files:
        p = _load(path, issues, 2 * 1024 * 1024)
        if not isinstance(p, dict): continue
        key = path.name[:-len(".park.json")]
        if p.get("format") != "reskate-park" or p.get("schema_version") != 1:
            add(issues, "error", "park-schema", f"{path.name}: invalid reskate-park schema 1")
        if type(p.get("revision")) is not int or p["revision"] < 0:
            add(issues, "error", "park-revision", f"{path.name}: revision must be >= 0 integer")
        maps = p.get("maps")
        if not isinstance(maps, dict) or set(maps) != {key} or not isinstance(maps[key], list) or len(maps[key]) > 1024:
            add(issues, "error", "park-maps", f"{path.name}: must contain exactly one {key} map with <=1024 objects")
            continue
        ids = set()
        for obj in maps[key]:
            if not isinstance(obj, dict) or set(obj) != {"id", "item", "position", "rotation"}:
                add(issues, "error", "park-object", f"{path.name}: object needs id, item, position, rotation")
                continue
            id_ = obj["id"]
            if not isinstance(id_, (int, float)) or isinstance(id_, bool) or not math.isfinite(id_) or id_ == 0 or id_ in ids:
                add(issues, "error", "park-id", f"{path.name}: duplicate/invalid id {id_}")
            if isinstance(id_, (int, float)) and not isinstance(id_, bool): ids.add(id_)
            item = obj["item"]
            if not isinstance(item, str) or not item.lower().startswith("own_bk") or len(item.encode("utf-8")) > 255:
                add(issues, "error", "park-item", f"{path.name}: invalid Build Kit object key")
            pos, rot = obj["position"], obj["rotation"]
            if not isinstance(pos, list) or len(pos) != 3 or any(not isinstance(v, (int, float)) or not math.isfinite(v) or abs(v) > 100000 for v in pos):
                add(issues, "error", "park-position", f"{path.name}: position invalid")
            if not isinstance(rot, list) or len(rot) != 4 or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in rot) or not 0.98 <= math.sqrt(sum(v*v for v in rot)) <= 1.02:
                add(issues, "error", "park-rotation", f"{path.name}: rotation must be a unit quaternion")
        scales = p.get("object_scales", {})
        if not isinstance(scales, dict) or any(not isinstance(s, dict) or any(not isinstance(v, (int, float)) or not 0.01 <= v <= 100 for v in s.values()) for s in scales.values()):
            add(issues, "error", "park-scale", f"{path.name}: invalid object scales")
        elif set(scales) - {key}:
            add(issues, "error", "park-scales-map", f"{path.name}: scales must refer to {key}")


def validate_mod(mod: Path, owner: str | None = None, categories: list[str] | None = None) -> dict:
    issues: list[Issue] = []
    if not mod.is_dir():
        return {"ready": False, "issues": [asdict(Issue("error", "missing-directory", f"Not a mod directory: {mod}"))], "kinds": []}
    for p in mod.rglob("*"):
        if p.is_symlink(): add(issues, "error", "symlink", f"Cannot publish a symlink: {p.relative_to(mod)}")
    manifest = manifest_check(mod, issues, owner)
    icon_readme_check(mod, issues)
    has_plugin = (mod / "reskate-plugin.json").exists()
    has_map = (mod / "reskate-levels.json").exists()
    has_park = (mod / "parks").is_dir()
    has_data = (mod / "layout.toc").exists()
    kinds = [k for k, valid in (("plugin", has_plugin), ("map", has_map), ("park", has_park), ("game-data", has_data)) if valid]
    if has_plugin: plugin_check(mod, issues)
    if has_map: map_check(mod, issues)
    if has_park: park_check(mod, issues)
    if has_data and not (mod / ".reskate-studio-patch").is_file():
        add(issues, "error", "studio-stamp", "Game-data mod needs actual .reskate-studio-patch from ReSkate Studio")
    if has_data and (mod / ".reskate-studio-patch").is_file() and (mod / ".reskate-studio-patch").stat().st_size == 0:
        add(issues, "error", "studio-stamp-empty", "Studio build stamp is empty; use authentic Studio output")
    if has_map and not has_data:
        add(issues, "error", "map-no-build", "Map descriptor alone is not a playable level; adopt actual Studio layout.toc and build files")
    if not kinds and not (manifest and manifest.get("dependencies")):
        add(issues, "error", "empty-mod", "No loadable data, plugin, map, park, or dependencies")
    if has_park and not list((mod / "parks").rglob("*.park.json")):
        add(issues, "error", "empty-park", "Park folder holds no .park.json")
    if categories is not None:
        if has_plugin and "Plugins" not in categories:
            add(issues, "error", "plugin-category", "Thunderstore Plugins category required to run Luau")
        if has_map and "Maps" not in categories:
            add(issues, "error", "map-category", "Thunderstore Maps category required for in-session map download")
        if "Mods" not in categories:
            add(issues, "warning", "mods-category", "Include Mods so the launcher can offer GET MODS installation")
    if has_data:
        add(issues, "warning", "manual-build", "Verify .reskate-studio-patch matches your ReSkate-supported skate. build")
    if has_map:
        add(issues, "warning", "manual-map", "Test collisions, grindability, spawn, and multiplayer; static JSON checks cannot prove gameplay")
    if has_plugin:
        add(issues, "warning", "manual-plugin", "Luau source parsed structurally only; test in game's plugin list and logs")
    return {"ready": not any(x.severity == "error" for x in issues), "kinds": kinds, "issues": [asdict(x) for x in issues]}
