"""Blender (background) step of the ReSkate character-swap pipeline.

Imports a rigged source FBX and dumps, per mesh and per LOD, everything the
numpy fitter needs: world-space rest positions/normals, UV0, triangles,
sparse bone weights, plus the source armature's world-space bone heads.

  blender -b --factory-startup -P blender_dump.py -- SOURCE.fbx OUT.npz CONFIG.json

CONFIG keys used here: "drop_meshes" (list), "lod_ratios" (list, first is 1.0).
Rigid meshes parented to a bone get that bone as their single influence;
rigid meshes with no bone parent get CONFIG["rigid_fallback_bone"].
"""
import bpy, bmesh, sys, json
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
src, out, cfg_path = argv[0], argv[1], argv[2]
cfg = json.load(open(cfg_path, encoding="utf-8"))
drop = set(cfg.get("drop_meshes", []))
ratios = cfg.get("lod_ratios", [1.0])

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src, automatic_bone_orientation=False, ignore_leaf_bones=False)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
bones = list(arm.data.bones)
bidx = {b.name: i for i, b in enumerate(bones)}
data = {
    "bone_names": np.array([b.name for b in bones]),
    "bone_parent": np.array([bidx[b.parent.name] if b.parent else -1 for b in bones], np.int32),
    "bone_head": np.array([list(arm.matrix_world @ b.head_local) for b in bones], np.float64),
}
# Rest pose only: no action may move vertices before the dump.
arm.animation_data_clear()
for pb in arm.pose.bones:
    pb.matrix_basis.identity()

meshes = []
for o in [o for o in bpy.data.objects if o.type == "MESH"]:
    if o.name.split(".")[0] in drop or o.name in drop:
        continue
    meshes.append(o)

dg = bpy.context.evaluated_depsgraph_get()
names = []
for o in meshes:
    # Freeze shape keys at their basis and strip deform modifiers so the dump is the bind shape.
    if o.data.shape_keys:
        o.shape_key_clear()
    for md in list(o.modifiers):
        if md.type == "ARMATURE":
            o.modifiers.remove(md)
    # Rigid accessories (HS2 ca_slot/N_move empties) hang off a bone somewhere up the parent chain.
    rigid_bone = None
    p = o
    while p is not None and rigid_bone is None:
        if p.parent_type == "BONE" and p.parent_bone in bidx:
            rigid_bone = p.parent_bone
        p = p.parent
    # Per-mesh LOD0 trim keeps native sections under the 16-bit vertex index limit.
    mcfg = cfg.get("meshes", {}).get(o.name.split(".")[0], {})
    for li, r in enumerate(ratios):
        r = r * mcfg.get("lod0_ratio", 1.0)
        tmp = o.copy(); tmp.data = o.data.copy(); bpy.context.collection.objects.link(tmp)
        if r < 0.999:
            d = tmp.modifiers.new("dec", "DECIMATE"); d.ratio = r; d.use_collapse_triangulate = True
        dg = bpy.context.evaluated_depsgraph_get()
        ev = tmp.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
        me.transform(tmp.matrix_world)
        me.calc_loop_triangles()
        uvl = me.uv_layers[0].data if me.uv_layers else None
        nv = len(me.vertices)
        tris = me.loop_triangles
        loops = np.zeros(len(tris) * 3, np.int64); tris.foreach_get("loops", loops)
        lv = np.zeros(len(me.loops), np.int64); me.loops.foreach_get("vertex_index", lv)
        uv = np.zeros(len(me.loops) * 2); (uvl.foreach_get("uv", uv) if uvl else None)
        uv = uv.reshape(-1, 2)
        ln = np.zeros(len(me.loops) * 3)
        if hasattr(me, "corner_normals"):  # Blender 4.1+
            me.corner_normals.foreach_get("vector", ln)
        else:
            me.calc_normals_split(); me.loops.foreach_get("normal", ln)
        co = np.zeros(nv * 3); me.vertices.foreach_get("co", co)
        # Weld per-loop attributes into unique (vertex, uv, normal) render vertices.
        key = np.concatenate([lv[:, None].astype(np.float64), np.round(uv, 6), np.round(ln.reshape(-1, 3), 4)], 1)
        uk, inv = np.unique(key, axis=0, return_inverse=True)
        inv = inv.reshape(-1)
        first = np.zeros(len(uk), np.int64); first[inv[::-1]] = np.arange(len(inv))[::-1]
        vi = lv[first]
        tag = f"{o.name}|{li}"
        names.append(tag)
        data[tag + "|pos"] = co.reshape(-1, 3)[vi]
        data[tag + "|nrm"] = ln.reshape(-1, 3)[first]
        data[tag + "|uv"] = uv[first]
        data[tag + "|tri"] = inv[loops].reshape(-1, 3).astype(np.int32)
        # Sparse weights: rows (render vertex, bone index, weight).
        gmap = {g.index: bidx.get(g.name, -1) for g in tmp.vertex_groups}
        rows = []
        used_rigid = ""
        if rigid_bone is not None and not any(len(v.groups) for v in me.vertices):
            used_rigid = rigid_bone
            for k in range(len(vi)):
                rows.append((k, bidx[rigid_bone], 1.0))
        else:
            vw = [[(gmap.get(g.group, -1), g.weight) for g in v.groups if gmap.get(g.group, -1) >= 0 and g.weight > 1e-4] for v in me.vertices]
            for k, v in enumerate(vi):
                for b, w in vw[v]:
                    rows.append((k, b, w))
        data[tag + "|w"] = np.array(rows, np.float64).reshape(-1, 3)
        data[tag + "|rigid"] = np.array([used_rigid])  # non-empty: positions are in armature-rest space
        bpy.data.meshes.remove(me)
        bpy.data.objects.remove(tmp, do_unlink=True)
        print("dumped", tag, len(vi), "verts", len(data[tag + "|tri"]), "tris")
data["mesh_tags"] = np.array(names)
np.savez_compressed(out, **data)
print("WROTE", out)
