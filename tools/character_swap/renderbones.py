"""Read a costume's native physics render bones (DingoRenderbonesData) via the Studio CLI.

Costume meshes can be skinned to these bones; in game the costume's Verlet
expression graph drives them (cloth, hoods, antennas, soft-body). Studio's
importer exposes them as glTF joints named PROC_Bone<i>, children of their
root joint, with the donor's local pose and bind pose.

  python renderbones.py <reskate_cli.exe> <game> <renderbones-asset> [render_skeleton.json]
"""
import json, re, subprocess, sys


def _blocks(lines, start, indent):
    """Split the list that starts after `lines[start]` into item blocks at `indent`."""
    out, cur = [], None
    for l in lines[start + 1:]:
        if not l.startswith(" " * indent) and l.strip():
            break
        if re.match(r"^\s{%d}\[\d+\] \{" % indent, l):
            cur = []; out.append(cur)
        elif cur is not None:
            cur.append(l)
    return out


def _mat(block, name):
    i = next(i for i, l in enumerate(block) if l.strip() == name + " {")
    m = {}; key = None
    for l in block[i + 1:]:
        s = l.strip()
        if s.endswith("{"):
            key = s[:-1].strip()
            if key not in ("right", "up", "forward", "trans"): break
            m[key] = [0.0, 0.0, 0.0]
        elif "=" in s and key:
            a, b = s.split("="); a = a.strip()
            if a in "xyz" and len(a) == 1: m[key]["xyz".index(a)] = float(b)
            else: break
        if len(m) == 4 and all(k in m for k in ("right", "up", "forward", "trans")) and s.startswith("z"):
            if key == "trans": break
    return m


def parse(text):
    L = text.split("\n")
    bi = next(i for i, l in enumerate(L) if re.match(r"^  Bones \[\d+\]", l))
    ri = next(i for i, l in enumerate(L) if re.match(r"^  RootPoses \[\d+\]", l))
    bones = []
    for b in _blocks(L, bi, 4):
        slot = int(next(l for l in b if "TransformSlot =" in l and "Parent" not in l).split("=")[1])
        parent = int(next(l for l in b if "ParentTransformSlot" in l).split("=")[1])
        bones.append({"slot": slot, "parent_slot": parent, "pose": _mat(b, "Pose"), "bind": _mat(b, "BindPose")})
    roots = []
    for r in _blocks(L, ri, 4):
        roots.append({"bone_index": int(next(l for l in r if "BoneIndex" in l).split("=")[1]),
                      "slot": int(next(l for l in r if "TransformSlot" in l).split("=")[1]),
                      "bind": _mat(r, "BindPose")})
    exprs = sorted(set(re.findall(r"exp_renderbones_[a-z0-9]+", text)))
    return {"bones": bones, "roots": roots, "expressions": exprs}


def load(cli, game, asset):
    txt = subprocess.run([cli, "ebx-values", game, asset], capture_output=True, text=True, timeout=600).stdout
    return parse(txt)


if __name__ == "__main__":
    d = load(sys.argv[1], sys.argv[2], sys.argv[3])
    names = json.load(open(sys.argv[4]))["names"] if len(sys.argv) > 4 else None
    slot_root = {r["slot"]: (names[r["bone_index"]] if names else r["bone_index"]) for r in d["roots"]}
    print(d["expressions"])
    for i, b in enumerate(d["bones"]):
        p = b["parent_slot"]
        par = slot_root.get(p, f"PROC_Bone{next((j for j, x in enumerate(d['bones']) if x['slot'] == p), '?')}")
        t = b["bind"]["trans"]
        print(f"PROC_Bone{i:<3} slot {b['slot']:<3} parent {par:<22} bind x={t[0]:+.3f} y={t[1]:.3f} z={t[2]:+.3f}")
