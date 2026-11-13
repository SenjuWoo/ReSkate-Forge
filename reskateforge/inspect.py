"""Inspect large Thunderstore example archives and 3D source assets without extraction."""

from __future__ import annotations

import bisect
import collections
import io
import json
import re
import struct
import zipfile
from pathlib import Path, PurePosixPath


class SegmentedReader(io.RawIOBase):
    """Random-access view of a split ZIP, avoiding a multi-GB concatenation."""

    def __init__(self, parts: list[Path]):
        if not parts:
            raise ValueError("Specify ZIP parts in order")
        self.parts = [Path(p) for p in parts]
        self.files = [p.open("rb") for p in self.parts]
        self.ends = []
        running = 0
        for p in self.parts:
            running += p.stat().st_size
            self.ends.append(running)
        self.pos = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = 0) -> int:
        base = 0 if whence == 0 else self.pos if whence == 1 else self.ends[-1]
        new = base + offset
        if new < 0:
            raise ValueError("Negative seek")
        self.pos = new
        return new

    def read(self, n: int = -1) -> bytes:
        remaining = max(0, self.ends[-1] - self.pos) if n is None or n < 0 else min(n, max(0, self.ends[-1] - self.pos))
        blocks: list[bytes] = []
        while remaining:
            idx = bisect.bisect_right(self.ends, self.pos)
            base = self.ends[idx - 1] if idx else 0
            take = min(remaining, self.ends[idx] - self.pos)
            handle = self.files[idx]
            handle.seek(self.pos - base)
            data = handle.read(take)
            if not data:
                break
            self.pos += len(data)
            remaining -= len(data)
            blocks.append(data)
        return b"".join(blocks)

    def close(self) -> None:
        for f in self.files:
            f.close()
        super().close()


def safe_zip_name(name: str) -> bool:
    if not name or "\\" in name or "\0" in name or name.startswith("/"):
        return False
    if any(s in ("", ".", "..") or ":" in s for s in name.rstrip("/").split("/")):
        return False
    path = PurePosixPath(name)
    return not path.is_absolute()


def zip_security_checks(z: zipfile.ZipFile) -> list[str]:
    issues = []
    seen = set()
    for i in z.infolist():
        if not safe_zip_name(i.filename):
            issues.append(f"Unsafe ZIP member: {i.filename}")
        key = i.filename.casefold()
        if key in seen:
            issues.append(f"Duplicate ZIP member: {i.filename}")
        seen.add(key)
        if (i.external_attr >> 16) & 0o170000 == 0o120000:
            issues.append(f"ZIP symlink: {i.filename}")
    return issues


def inspect_mod_archive(parts: list[Path], sample_limit: int = 60) -> dict:
    """Read manifests and file lists, not the potentially enormous game bundles."""
    reader = SegmentedReader(parts)
    try:
        with zipfile.ZipFile(reader) as z:
            names = z.namelist()
            roots = collections.defaultdict(list)
            for i in z.infolist():
                pieces = PurePosixPath(i.filename).parts
                if len(pieces) >= 3 and pieces[0].lower() == "mods":
                    roots[pieces[1]].append(i)
            mods = []
            for folder, files in sorted(roots.items()):
                paths = ["/".join(PurePosixPath(i.filename).parts[2:]) for i in files]
                by_name = {"/".join(PurePosixPath(i.filename).parts[2:]): i for i in files}

                def read_json(name: str, max_size: int) -> dict | None:
                    info = by_name.get(name)
                    if info is None or info.file_size > max_size: return None
                    try:
                        obj = json.loads(z.read(info).decode("utf-8-sig"))
                        return obj if isinstance(obj, dict) else None
                    except (UnicodeError, json.JSONDecodeError, RuntimeError, zipfile.BadZipFile):
                        return None

                manifest = read_json("manifest.json", 32768)
                plugin = read_json("reskate-plugin.json", 65536)
                maps = read_json("reskate-levels.json", 65536)
                kind = []
                if "reskate-plugin.json" in paths: kind.append("plugin")
                if "reskate-levels.json" in paths: kind.append("map")
                if any(x.startswith("parks/") for x in paths): kind.append("park")
                if "layout.toc" in paths or any(x.startswith("Win32/") for x in paths): kind.append("game-data")
                if not kind: kind.append("other")
                mods.append({
                    "folder": folder, "manifest": manifest, "kinds": kind,
                    "plugin": {"api": plugin.get("api"), "side": plugin.get("side", "client"), "permissions": plugin.get("permissions", [])} if plugin else None,
                    "map_titles": [row.get("displayName") for row in maps.get("levels", []) if isinstance(row, dict)] if maps and isinstance(maps.get("levels"), list) else [],
                    "has_build_stamp": ".reskate-studio-patch" in paths,
                    "entries": len(files), "uncompressed_bytes": sum(i.file_size for i in files),
                    "sample_files": paths[:sample_limit],
                })
            return {
                "parts": [p.name for p in parts], "part_sizes": [p.stat().st_size for p in parts],
                "entries": len(names), "uncompressed_bytes": sum(i.file_size for i in z.infolist()),
                "extensions": dict(collections.Counter(PurePosixPath(n).suffix.lower() or "[none]" for n in names if not n.endswith("/"))),
                "zip_issues": zip_security_checks(z), "mod_count": len(mods), "mods": mods,
            }
    finally:
        reader.close()


def _fbx_properties(f: io.BytesIO, count: int, limit: int) -> list[object]:
    values = []
    for idx in range(count):
        t = f.read(1)
        if not t:
            raise ValueError("Truncated FBX property")
        typ = t.decode("ascii", errors="replace")
        sized = {"Y": 2, "C": 1, "I": 4, "F": 4, "D": 8, "L": 8}
        if typ in sized:
            raw = f.read(sized[typ])
            if len(raw) != sized[typ]: raise ValueError("Truncated FBX number")
            if idx < limit:
                fmt = {"Y": "h", "C": "?", "I": "i", "F": "f", "D": "d", "L": "q"}[typ]
                values.append(struct.unpack("<" + fmt, raw)[0])
        elif typ in "fdlibc":
            hdr = f.read(12)
            if len(hdr) != 12: raise ValueError("Truncated FBX array")
            length, encoding, byte_len = struct.unpack("<III", hdr)
            f.seek(byte_len, 1)
            if idx < limit: values.append({"array_count": length, "encoding": encoding})
        elif typ in ("S", "R"):
            rawlen = f.read(4)
            if len(rawlen) != 4: raise ValueError("Truncated FBX blob")
            length = struct.unpack("<I", rawlen)[0]
            if idx < limit and typ == "S" and length <= 1024:
                values.append(f.read(length).decode("utf-8", errors="replace"))
            else:
                f.seek(length, 1)
                if idx < limit: values.append(f"<{typ} {length} bytes>")
        else:
            raise ValueError(f"Unknown FBX property type: {typ!r}")
    return values


def inspect_fbx(data: bytes) -> dict:
    """Parse binary FBX node headers and useful metadata; never modify mesh data."""
    marker = b"Kaydara FBX Binary  \x00\x1a\x00"
    if not data.startswith(marker) or len(data) < 27:
        return {"format": "unknown-or-ascii-fbx", "bytes": len(data), "warning": "Binary FBX metadata parser could not inspect this file"}
    version = struct.unpack_from("<I", data, 23)[0]
    fmt = "<QQQB" if version >= 7500 else "<IIIB"
    header_bytes = struct.calcsize(fmt)
    sentinel = 25 if version >= 7500 else 13
    f = io.BytesIO(data)
    nodes = collections.Counter()
    rig_nodes, mesh_nodes, material_nodes = [], [], []
    arrays = collections.Counter()
    errors = []
    seen = 0

    def walk(until: int, depth: int) -> None:
        nonlocal seen
        if depth > 80: raise ValueError("FBX node nesting limit exceeded")
        while f.tell() + header_bytes <= min(until, len(data)):
            start = f.tell()
            hdr = f.read(header_bytes)
            end, prop_count, prop_len, name_len = struct.unpack(fmt, hdr)
            if end == 0:
                return
            if end <= start or end > len(data) or prop_count > 100000:
                raise ValueError(f"Bad FBX node offset at {start}")
            name = f.read(name_len).decode("utf-8", errors="replace")
            node_props_start = f.tell()
            props = _fbx_properties(f, prop_count, 3)
            if f.tell() != node_props_start + prop_len:
                raise ValueError(f"Unexpected FBX property length in {name}")
            nodes[name] += 1
            seen += 1
            if seen > 150000: raise ValueError("FBX node-count limit exceeded")
            if name == "Model" and len(props) >= 3:
                entry = {"name": str(props[1]).split("\x00", 1)[0].replace("Model::", ""), "kind": str(props[2])}
                (rig_nodes if entry["kind"] in ("LimbNode", "Root", "Null") else mesh_nodes).append(entry)
            elif name == "Geometry" and len(props) >= 3:
                mesh_nodes.append({"name": str(props[1]).split("\x00", 1)[0].replace("Geometry::", ""), "kind": str(props[2])})
            elif name == "Material" and len(props) >= 2:
                material_nodes.append(str(props[1]).split("\x00", 1)[0].replace("Material::", ""))
            elif name in ("Vertices", "PolygonVertexIndex") and props and isinstance(props[0], dict):
                arrays[name] += int(props[0]["array_count"])
            if f.tell() < end - sentinel:
                walk(end, depth + 1)
            f.seek(end)
    try:
        f.seek(27)
        walk(len(data), 0)
    except (ValueError, struct.error, RecursionError) as e:
        errors.append(str(e))
    return {
        "format": "binary-fbx", "version": version, "bytes": len(data),
        "model_count": nodes["Model"], "geometry_count": nodes["Geometry"],
        "material_count": nodes["Material"], "deformer_count": nodes["Deformer"],
        "textures_in_fbx": nodes["Texture"], "bone_like_count": len(rig_nodes), "bone_like_nodes": rig_nodes[:180],
        "mesh_like_nodes": mesh_nodes[:70], "material_names": material_nodes[:70],
        "geometry_array_elements": dict(arrays), "node_count": seen, "parser_errors": errors,
    }


def inspect_model_zip(path: Path) -> dict:
    with zipfile.ZipFile(path) as z:
        issues = zip_security_checks(z)
        models = []
        textures = []
        for info in z.infolist():
            if info.is_dir(): continue
            suffix = PurePosixPath(info.filename).suffix.lower()
            if suffix in (".fbx", ".glb", ".gltf", ".obj", ".blend"):
                meta = {"path": info.filename, "size": info.file_size, "extension": suffix}
                if suffix == ".fbx" and info.file_size < 150_000_000:
                    meta["fbx"] = inspect_fbx(z.read(info))
                models.append(meta)
            elif suffix in (".png", ".jpg", ".jpeg", ".dds", ".tga", ".webp"):
                item = {"path": info.filename, "size": info.file_size}
                if suffix == ".png":
                    with z.open(info) as f:
                        head = f.read(24)
                        if head.startswith(b"\x89PNG\r\n\x1a\n"):
                            item["dimensions"] = list(struct.unpack(">II", head[16:24]))
                textures.append(item)
        return {"archive": path.name, "zip_issues": issues, "models": models,
                "texture_count": len(textures), "textures": textures,
                "total_uncompressed_bytes": sum(x.file_size for x in z.infolist())}


def stage_model(source: Path, destination: Path) -> dict:
    """Extract source model and textures into a private local workbench (not publication)."""
    if destination.exists():
        raise FileExistsError(destination)
    report = inspect_model_zip(source)
    if report["zip_issues"]:
        raise ValueError("Unsafe ZIP: " + "; ".join(report["zip_issues"][:5]))
    if not report["models"]:
        raise ValueError("No supported model found in archive")
    if report["total_uncompressed_bytes"] > 2_000_000_000:
        raise ValueError("Model archive exceeds safe 2 GB extraction limit")
    if len(report["textures"]) + len(report["models"]) > 2000:
        raise ValueError("Too many files in model source archive")
    destination.mkdir(parents=True)
    with zipfile.ZipFile(source) as z:
        for i in z.infolist():
            if i.is_dir(): continue
            if PurePosixPath(i.filename).suffix.lower() not in (".fbx", ".glb", ".gltf", ".obj", ".blend", ".png", ".jpg", ".jpeg", ".dds", ".tga", ".webp"):
                continue
            target = destination / i.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(i) as reader, target.open("xb") as writer:
                import shutil
                shutil.copyfileobj(reader, writer, 1024 * 1024)
    from .artifacts import json_write
    json_write(destination / "model-preflight.json", report)
    return report
