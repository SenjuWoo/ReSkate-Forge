"""Blender background importer: supported source mesh -> editable .blend scene.

Called by ``reskateforge map-import`` using Blender's Python interpreter. This
prepares geometry for Skate Map; it does not assert a valid spawn or gameplay.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    source = Path(args.input).resolve()
    target = Path(args.output).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if target.exists():
        raise FileExistsError(target)
    if target.suffix.lower() != ".blend":
        raise ValueError("Output needs .blend extension")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if source.suffix.lower() == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(source), use_anim=False)
    elif source.suffix.lower() in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(source))
    elif source.suffix.lower() == ".obj":
        bpy.ops.wm.obj_import(filepath=str(source))
    else:
        raise ValueError(f"Unsupported source: {source.suffix}")
    meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
    if not meshes:
        raise ValueError("Imported scene has no mesh objects")
    target.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target), check_existing=False)
    print("RESKATE_IMPORT_RESULT=" + json.dumps({"source": str(source),
          "blend": str(target), "meshes": len(meshes),
          "triangles_estimate": sum(sum(max(0, len(p.vertices)-2) for p in obj.data.polygons) for obj in meshes),
          "needs_studio_authoring": ["spawn", "collision surfaces", "grinds", "performance", "materials"]}))


if __name__ == "__main__":
    main()
