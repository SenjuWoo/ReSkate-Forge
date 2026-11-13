"""Extract skate.'s character render skeleton from the user's own install.

Uses the bundled reskate_cli.exe `ebx-values` dump, so no game data ships with
the Forge. Result JSON: names, parents, local/model transforms (row-vector
Frostbite LinearTransforms: right, up, forward, trans).
"""
import json, os, re, subprocess
import numpy as np

ASSET = "characters/maincharacters/common/animbase/animbase_default_renderskeleton"


def parse_dump(text):
    L = text.split("\n")

    def start(name):
        return next(i for i, l in enumerate(L) if l.startswith("  " + name + " [")) + 1

    names, i = [], start("BoneNames")
    while L[i].startswith("    ["): names.append(L[i].split('"')[1]); i += 1
    parents, i = [], start("Hierarchy")
    while L[i].startswith("    ["): parents.append(int(L[i].split("=")[1])); i += 1

    def poses(name):
        i, out, cur, key = start(name), [], None, None
        while i < len(L) and L[i].startswith("    "):
            l = L[i].strip()
            if re.match(r"\[\d+\] \{", l): cur = {}; out.append(cur)
            elif l.endswith("{"): key = l[:-1].strip(); cur[key] = [0.0, 0.0, 0.0]
            elif "=" in l: a, b = l.split("="); cur[key]["xyz".index(a.strip())] = float(b)
            i += 1
        return out

    return {"names": names, "parents": parents, "local": poses("LocalPose"), "model": poses("ModelPose")}


def extract(cli, game, out_json):
    txt = subprocess.run([cli, "ebx-values", game, ASSET], capture_output=True, text=True, timeout=600).stdout
    d = parse_dump(txt)
    if len(d["names"]) != len(d["parents"]) or len(d["model"]) != len(d["names"]):
        raise RuntimeError("render skeleton dump is incomplete")
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    json.dump(d, open(out_json, "w"))
    return d


def mat(t):
    M = np.eye(4)
    M[0, :3] = t["right"]; M[1, :3] = t["up"]; M[2, :3] = t["forward"]; M[3, :3] = t["trans"]
    return M


def load(path):
    d = json.load(open(path))
    return d["names"], d["parents"], [mat(t) for t in d["local"]], [mat(t) for t in d["model"]]
