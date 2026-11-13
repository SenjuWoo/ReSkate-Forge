"""Create a portable, reproducible source archive excluding caches and private assets.

Usage: python tools/build_distribution.py /absolute/path/ReSkateForge-v0.2.0.zip
       Add --include-private-sources only for a local/private bundle.
"""

from __future__ import annotations

import argparse
import os
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache", ".venv", "build"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".fbx", ".glb", ".gltf", ".blend", ".fbmod", ".fbproject", ".cas", ".fas"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--include-private-sources", action="store_true",
                        help="Package private model workbench assets (never for a public Forge repository)")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("Output must be outside the project tree to avoid recursive packaging")
    output.parent.mkdir(parents=True, exist_ok=True)
    paths = []
    for path in ROOT.rglob("*"):
        if path.is_symlink(): raise ValueError(f"Symlinks not allowed: {path}")
        if not path.is_file(): continue
        rel = path.relative_to(ROOT)
        if any(s in SKIP_DIRS for s in rel.parts):
            continue
        is_private_source = rel.parts[0] == "workspaces" and "source" in rel.parts
        if path.suffix.lower() in SKIP_SUFFIXES and not (is_private_source and args.include_private_sources):
            continue
        if is_private_source and not args.include_private_sources:
            continue  # Private model and donor workbench inputs never ship.
        paths.append(path)
    if output.exists(): raise FileExistsError(output)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=8) as archive:
        for path in sorted(paths):
            rel = "ReSkateForge/" + path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(rel, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    print(f"Built {output} ({len(paths)} files, {output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
