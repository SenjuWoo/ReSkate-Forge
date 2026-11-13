"""Minimal skinned glTF 2.0 binary writer for ReSkate cosmetic imports.

Joint nodes and inverse bind matrices are written straight from the game's
render skeleton (Frostbite row-vector LinearTransforms), so the bind pose is
bit-for-bit the game's instead of a DCC round trip.
"""
import json, struct
import numpy as np


def _quat_from_rot(R):
    # R: 3x3 column-vector rotation matrix -> (x, y, z, w)
    t = np.trace(R)
    if t > 0:
        s = np.sqrt(t + 1.0) * 2
        w = 0.25 * s; x = (R[2, 1] - R[1, 2]) / s; y = (R[0, 2] - R[2, 0]) / s; z = (R[1, 0] - R[0, 1]) / s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        w = (R[2, 1] - R[1, 2]) / s; x = 0.25 * s; y = (R[0, 1] + R[1, 0]) / s; z = (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        w = (R[0, 2] - R[2, 0]) / s; x = (R[0, 1] + R[1, 0]) / s; y = 0.25 * s; z = (R[1, 2] + R[2, 1]) / s
    else:
        s = np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        w = (R[1, 0] - R[0, 1]) / s; x = (R[0, 2] + R[2, 0]) / s; y = (R[1, 2] + R[2, 1]) / s; z = 0.25 * s
    q = np.array([x, y, z, w]); return q / np.linalg.norm(q)


class GLB:
    def __init__(self):
        self.bin = bytearray(); self.views = []; self.acc = []
        self.j = {"asset": {"version": "2.0", "generator": "ReSkateForge glb_writer"},
                  "scene": 0, "scenes": [{"nodes": []}], "nodes": [], "meshes": [],
                  "materials": [], "textures": [], "images": [], "samplers": [{}], "skins": []}

    def _view(self, data, target=None):
        while len(self.bin) % 4: self.bin += b"\0"
        off = len(self.bin); self.bin += data
        v = {"buffer": 0, "byteOffset": off, "byteLength": len(data)}
        if target: v["target"] = target
        self.views.append(v); return len(self.views) - 1

    def accessor(self, arr, ctype, typ, target=None, minmax=False):
        arr = np.ascontiguousarray(arr)
        a = {"bufferView": self._view(arr.tobytes(), target), "componentType": ctype,
             "count": int(arr.shape[0]), "type": typ}
        if minmax:
            a["min"] = arr.min(0).tolist(); a["max"] = arr.max(0).tolist()
        self.acc.append(a); return len(self.acc) - 1

    def image(self, png_bytes, name):
        self.j["images"].append({"bufferView": self._view(png_bytes), "mimeType": "image/png", "name": name})
        self.j["textures"].append({"source": len(self.j["images"]) - 1, "sampler": 0})
        return len(self.j["textures"]) - 1

    def material(self, name, base_png=None, normal_png=None, mr_png=None, ao_png=None):
        m = {"name": name, "pbrMetallicRoughness": {"metallicFactor": 1.0 if mr_png else 0.0, "roughnessFactor": 1.0 if mr_png else 0.8}}
        if base_png: m["pbrMetallicRoughness"]["baseColorTexture"] = {"index": self.image(base_png, name + "_c")}
        if normal_png: m["normalTexture"] = {"index": self.image(normal_png, name + "_n")}
        # glTF packing: G = roughness, B = metalness; R of the occlusion map = AO.
        if mr_png: m["pbrMetallicRoughness"]["metallicRoughnessTexture"] = {"index": self.image(mr_png, name + "_mr")}
        if ao_png: m["occlusionTexture"] = {"index": self.image(ao_png, name + "_ao")}
        self.j["materials"].append(m); return len(self.j["materials"]) - 1

    def skeleton(self, names, parents, local_rows, model_rows):
        """Adds joint nodes; returns skin index. local/model: 4x4 row-vector matrices."""
        base = len(self.j["nodes"])
        for n, L in zip(names, local_rows):
            C = L.T  # column-vector form
            R = C[:3, :3]; sc = np.linalg.norm(R, axis=0); R = R / sc
            node = {"name": n, "translation": C[:3, 3].tolist(), "rotation": _quat_from_rot(R).tolist()}
            if np.abs(sc - 1).max() > 1e-4: node["scale"] = sc.tolist()
            self.j["nodes"].append(node)
        for i, p in enumerate(parents):
            if p >= 0: self.j["nodes"][base + p].setdefault("children", []).append(base + i)
            else: self.j["scenes"][0]["nodes"].append(base + i)
        ibm = np.stack([np.linalg.inv(M).astype(np.float32).reshape(-1) for M in model_rows])  # row-major inv(M_row) == column-major inv(C)
        root = base + parents.index(-1)
        self.j["skins"].append({"joints": list(range(base, base + len(names))), "skeleton": root,
                                "inverseBindMatrices": self.accessor(ibm, 5126, "MAT4")})
        return len(self.j["skins"]) - 1

    def skinned_mesh(self, name, prims, skin):
        """prims: list of dict(pos, nrm, uv, joints, weights, idx, material)."""
        out = []
        for p in prims:
            attrs = {"POSITION": self.accessor(p["pos"].astype(np.float32), 5126, "VEC3", 34962, True),
                     "NORMAL": self.accessor(p["nrm"].astype(np.float32), 5126, "VEC3", 34962),
                     "TEXCOORD_0": self.accessor(p["uv"].astype(np.float32), 5126, "VEC2", 34962),
                     "TEXCOORD_1": self.accessor(p["uv"].astype(np.float32), 5126, "VEC2", 34962),
                     "JOINTS_0": self.accessor(p["joints"].astype(np.uint16), 5123, "VEC4", 34962),
                     "WEIGHTS_0": self.accessor(p["weights"].astype(np.float32), 5126, "VEC4", 34962)}
            if "tan" in p:
                attrs["TANGENT"] = self.accessor(p["tan"].astype(np.float32), 5126, "VEC4", 34962)
            out.append({"attributes": attrs, "material": p["material"],
                        "indices": self.accessor(p["idx"].astype(np.uint32), 5125, "SCALAR", 34963)})
        self.j["meshes"].append({"name": name, "primitives": out})
        self.j["nodes"].append({"name": name, "mesh": len(self.j["meshes"]) - 1, "skin": skin})
        self.j["scenes"][0]["nodes"].append(len(self.j["nodes"]) - 1)

    def save(self, path):
        self.j["bufferViews"] = self.views; self.j["accessors"] = self.acc
        self.j["buffers"] = [{"byteLength": len(self.bin)}]
        for k in ("textures", "images", "materials"):
            if not self.j[k]: del self.j[k]
        if "textures" not in self.j: self.j.pop("samplers", None)
        js = json.dumps(self.j, separators=(",", ":")).encode()
        js += b" " * ((4 - len(js) % 4) % 4)
        while len(self.bin) % 4: self.bin += b"\0"
        total = 12 + 8 + len(js) + 8 + len(self.bin)
        with open(path, "wb") as f:
            f.write(struct.pack("<III", 0x46546C67, 2, total))
            f.write(struct.pack("<II", len(js), 0x4E4F534A)); f.write(js)
            f.write(struct.pack("<II", len(self.bin), 0x004E4942)); f.write(self.bin)
