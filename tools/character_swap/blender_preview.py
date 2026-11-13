"""Render preview images of a built character GLB (LOD0) in Blender.

  blender -b --factory-startup -P blender_preview.py -- IN.glb OUT_PREFIX [pose]

pose: "rest" (default) or "action" (bends arms/legs/spine to check skinning).
Writes OUT_PREFIX_front.png, _side.png, _back.png.
"""
import bpy, sys, math
from mathutils import Vector, Euler

argv = sys.argv[sys.argv.index("--") + 1:]
src, out = argv[0], argv[1]
pose = argv[2] if len(argv) > 2 else "rest"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
for o in list(bpy.data.objects):
    if o.type == "MESH" and not o.name.startswith("RS_LOD0_"):
        bpy.data.objects.remove(o, do_unlink=True)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
if pose == "action":
    def rot(n, x=0, y=0, z=0):
        pb = arm.pose.bones.get(n)
        if pb: pb.rotation_mode = "XYZ"; pb.rotation_euler = Euler((math.radians(x), math.radians(y), math.radians(z)))
    rot("LeftArm", 0, 0, 50); rot("RightArm", 0, 0, -20); rot("LeftForeArm", 0, 0, 60); rot("RightForeArm", 40, 0, 0)
    rot("LeftUpLeg", 50, 0, 0); rot("LeftLeg", -70, 0, 0); rot("RightUpLeg", -20, 0, 0)
    rot("Spine2", 15, 0, 10); rot("Head", 0, 25, 0)
    for o in bpy.data.objects:
        if o.type == "MESH": o.hide_render = False
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items} else "BLENDER_EEVEE"
sc.render.resolution_x, sc.render.resolution_y = 900, 1400
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.5, 0.52, 0.56, 1); w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sc.collection.objects.link(sun)
sun.rotation_euler = Euler((math.radians(50), 0, math.radians(30))); sun.data.energy = 3
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = "ORTHO"; cam.data.ortho_scale = 2.0
views = {"front": (Vector((0, -4, 0.9)), (90, 0, 0)), "side": (Vector((4, 0, 0.9)), (90, 0, 90)), "back": (Vector((0, 4, 0.9)), (90, 0, 180))}
for name, (loc, r) in views.items():
    cam.location = loc; cam.rotation_euler = Euler([math.radians(x) for x in r])
    sc.render.filepath = f"{out}_{name}.png"; bpy.ops.render.render(write_still=True)
print("RENDERED", out)
