r"""Run *inside Blender*; inspect a source FBX/GLB and optionally export a GLB.

Example (Windows PowerShell):
  & 'C:\Program Files\Blender Foundation\Blender 4.5\blender.exe' --background --python tools/blender_preflight.py -- --input 'C:\models\Kitana.fbx' --report 'C:\models\blender-report.json'

This is NOT a player-rig retargeter and does not synthesize a ReSkate game-data patch.
It reports what an agent needs to compare against an actual free donor exported by Studio.
"""

import argparse
import json
import sys
from pathlib import Path

import bpy


def run():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--export-glb", help="Optional GLB export; does NOT retarget rig")
    args = parser.parse_args(argv)
    source = Path(args.input).resolve()
    if not source.is_file(): raise FileNotFoundError(source)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ext = source.suffix.lower()
    if ext == ".fbx": bpy.ops.import_scene.fbx(filepath=str(source), use_anim=False)
    elif ext in (".gltf", ".glb"): bpy.ops.import_scene.gltf(filepath=str(source))
    elif ext == ".obj": bpy.ops.wm.obj_import(filepath=str(source))
    elif ext == ".blend": bpy.ops.wm.open_mainfile(filepath=str(source))
    else: raise ValueError(f"Unsupported Blender input: {ext}")
    meshes, rigs, missing_images = [], [], []
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            mesh = obj.data
            meshes.append({
                "name": obj.name, "vertices": len(mesh.vertices), "faces": len(mesh.polygons),
                "triangles_estimate": sum(max(0, len(p.vertices) - 2) for p in mesh.polygons),
                "shape_keys": max(0, len(mesh.shape_keys.key_blocks) - 1) if mesh.shape_keys else 0,
                "vertex_groups": len(obj.vertex_groups), "materials": [m.name if m else None for m in obj.data.materials],
                "armature_modifiers": [m.object.name for m in obj.modifiers if m.type == "ARMATURE" and m.object],
            })
        elif obj.type == "ARMATURE":
            rigs.append({"name": obj.name, "bone_count": len(obj.data.bones),
                         "bones": [bone.name for bone in obj.data.bones]})
    for image in bpy.data.images:
        if image.source == "FILE" and image.filepath and not image.packed_file:
            resolved = Path(bpy.path.abspath(image.filepath, library=image.library))
            if not resolved.is_file(): missing_images.append({"image": image.name, "expected": str(resolved)})
    report = {
        "source": str(source), "blender_version": bpy.app.version_string,
        "mesh_count": len(meshes), "total_vertices": sum(m["vertices"] for m in meshes),
        "total_estimated_triangles": sum(m["triangles_estimate"] for m in meshes),
        "rig_count": len(rigs), "rigs": rigs, "meshes": meshes, "missing_images": missing_images,
        "warnings": ["No automatic ReSkate bone remapping or skater replacement occurred.",
                     "Compare against a free donor item exported through ReSkate Studio before fitting weights/animations."]
    }
    target = Path(args.report).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.export_glb:
        output = Path(args.export_glb).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.export_scene.gltf(filepath=str(output), export_format="GLB", export_apply=False)
        report["exported_glb"] = str(output)
        target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(target), "meshes": len(meshes), "rigs": len(rigs),
                      "triangles": report["total_estimated_triangles"], "missing_textures": len(missing_images)}))


if __name__ == "__main__":
    run()
