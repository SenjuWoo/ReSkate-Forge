"""ReSkate full-body character swap builder.

  python build.py CONFIG.json [--stage dump|tex|glb|import|all] [--blender PATH] [--game DIR]

Stages (each reuses earlier outputs in <workspace>/build/):
  dump    Blender: rest-pose mesh/weight dump with decimated LODs
  tex     bake albedo/normal atlases per native section
  glb     fit + reskin onto skate.'s render skeleton, write exact-bind GLB
  import  ReSkate Studio CLI cosmetic-mesh-import against the donor -> .fbproject
The GLB embeds the baked textures, so ReSkate Studio's Model > Import mesh
picks them up automatically ("Matching textures are added automatically").
"""
import argparse, io, json, os, subprocess, sys, time
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fbx_bind, fit_reskin, glb_writer, skate_skeleton, textures  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
STUDIO_CLI = os.path.join(ROOT, "ReSkate Studio", "reskate_cli.exe")
DEFAULT_BLENDER = r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe"


def log(*a):
    print(time.strftime("[%H:%M:%S]"), *a, flush=True)


def png_bytes(path, max_size=None):
    im = Image.open(path).convert("RGB")
    if max_size and max(im.size) > max_size:
        im = im.resize((max_size, max_size), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "PNG", optimize=False); return b.getvalue()


def alpha_cut(tri, uv, png, threshold=0.5):
    a = np.asarray(Image.open(png).convert("RGBA"))[..., 3] / 255.0
    h, w = a.shape

    def samp(u):
        x = np.clip((u[:, 0] % 1) * w, 0, w - 1).astype(int); y = np.clip((1 - u[:, 1] % 1) * h, 0, h - 1).astype(int)
        return a[y, x]
    # Sample a barycentric grid per triangle so thin opaque features (lace straps) narrower
    # than a triangle still keep a continuous strip.
    keep = np.zeros(len(tri), bool)
    T = uv[tri]
    for i in range(5):
        for j in range(5 - i):
            b = np.array([i, j, 4 - i - j]) / 4.0
            keep |= samp(np.einsum("k,nkd->nd", b, T)) > threshold
    return tri[keep]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--stage", default="all")
    ap.add_argument("--blender", default=os.environ.get("RESKATE_BLENDER", DEFAULT_BLENDER))
    ap.add_argument("--game", default=os.environ.get("RESKATE_GAME", r"C:\Games\ReSkate"))
    ap.add_argument("--max-texture", type=int, default=4096)
    a = ap.parse_args()
    cfg_path = os.path.abspath(a.config)
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    ws = os.path.dirname(os.path.dirname(cfg_path))
    bdir = os.path.join(ws, "build"); os.makedirs(bdir, exist_ok=True)
    src = os.path.join(ROOT, cfg["source_fbx"])
    dump_p = os.path.join(bdir, "dump.npz"); tex_d = os.path.join(bdir, "tex")
    skel_p = os.path.join(bdir, "skate_render_skeleton.json")
    item = cfg["item_name"]; glb_p = os.path.join(bdir, item + ".glb")
    stages = ["dump", "tex", "glb", "import"] if a.stage == "all" else a.stage.split(",")

    if "dump" in stages:
        log("dump via Blender", a.blender)
        r = subprocess.run([a.blender, "-b", "--factory-startup", "-P", os.path.join(HERE, "blender_dump.py"), "--", src, dump_p, cfg_path],
                           capture_output=True, text=True)
        open(os.path.join(bdir, "dump.blender.log"), "w", encoding="utf-8").write(r.stdout + r.stderr)
        if not os.path.exists(dump_p) or "WROTE" not in r.stdout:
            sys.exit("Blender dump failed; see build/dump.blender.log")

    if "tex" in stages:
        log("baking textures"); textures.build(cfg, ROOT, tex_d)

    if "glb" in stages:
        if not os.path.exists(skel_p):
            log("extracting render skeleton from", a.game); skate_skeleton.extract(STUDIO_CLI, a.game, skel_p)
        skel = skate_skeleton.load(skel_p)
        dump = np.load(dump_p); bind = fbx_bind.read_bind(src)
        atlas = json.load(open(os.path.join(tex_d, "atlas.json")))
        delta, report, G, gidx = fit_reskin.fit(cfg, dump, bind, skel)
        cfg["_rest_to_bind"] = report.pop("rest_to_bind")
        log("fit", report)
        sections = cfg["sections"]; nlod = len(cfg.get("lod_ratios", [1.0]))
        buckets = {}
        cache = {}
        stats = {}
        for tag in dump["mesh_tags"]:
            mname, lod = tag.rsplit("|", 1); lod = int(lod)
            key = mname.split(".")[0]
            m = cfg["meshes"].get(key)
            if m is None:
                log("WARN unmapped mesh", mname); continue
            pos, nrm, joints, weights = fit_reskin.reskin_mesh(tag, dump, delta, G, gidx, cfg, cache)
            src_uv = dump[tag + "|uv"]; tri = dump[tag + "|tri"]
            if m.get("alpha_cut"):
                # Native costume shaders are opaque: reproduce the source's alpha cut-out by
                # dropping triangles that are fully transparent in the source texture.
                tri = alpha_cut(tri, src_uv, os.path.join(ROOT, cfg["texture_dir"], m["alpha_cut"] + ".png"))
                used = np.unique(tri); remap = np.full(len(pos), -1); remap[used] = np.arange(len(used))
                pos, nrm, joints, weights, src_uv = pos[used], nrm[used], joints[used], weights[used], src_uv[used]
                tri = remap[tri].astype(np.int32)
            uv = fit_reskin.remap_uv(src_uv, atlas[str(m["section"])]["rects"][m["texture"]])
            buckets.setdefault((lod, m["section"]), []).append((pos, nrm, uv, joints, weights, tri))
        g = glb_writer.GLB()
        names, parents, local, model = skel
        sk = g.skeleton(names, parents, local, model)
        mats = {}
        for sec in range(len(sections)):
            c = os.path.join(tex_d, f"section{sec}_c.png"); n = os.path.join(tex_d, f"section{sec}_n.png")
            if os.path.exists(c):
                mats[sec] = g.material(sections[sec], png_bytes(c, a.max_texture), png_bytes(n, a.max_texture))
        for (lod, sec), parts in sorted(buckets.items()):
            off = 0; P = []; N = []; U = []; Jt = []; Wt = []; I = []
            for pos, nrm, uv, j, w, tri in parts:
                P.append(pos); N.append(nrm); U.append(uv); Jt.append(j); Wt.append(w); I.append(tri.reshape(-1) + off); off += len(pos)
            prim = dict(pos=np.concatenate(P), nrm=np.concatenate(N), uv=np.concatenate(U), joints=np.concatenate(Jt),
                        weights=np.concatenate(Wt), idx=np.concatenate(I), material=mats[sec])
            stats[f"LOD{lod}_S{sec}"] = {"verts": int(off), "tris": int(len(prim["idx"]) // 3)}
            if off > 65535:
                sys.exit(f"LOD{lod} section {sec} has {off} vertices; native sections use 16-bit indices (max 65535). Lower lod0_ratio for its meshes.")
            g.skinned_mesh(f"RS_LOD{lod}_SECTION{sec}_{sections[sec]}", [prim], sk)
        g.save(glb_p)
        used = sorted({names[int(j)] for (lod, sec), parts in buckets.items() if lod == 0 for p in parts for j in np.unique(p[3])})
        json.dump({"fit": report, "buffers": stats, "bones_used_lod0": used}, open(os.path.join(bdir, "build-report.json"), "w"), indent=1)
        log("wrote", glb_p, os.path.getsize(glb_p) // 1048576, "MB;", stats.get("LOD0_S0"), "...")

    if "import" in stages:
        proj = os.path.join(bdir, item + ".fbproject")
        log("cosmetic-mesh-import ->", proj)
        r = subprocess.run([STUDIO_CLI, "cosmetic-mesh-import", a.game, cfg["donor_item"], glb_p, proj], capture_output=True, text=True)
        open(os.path.join(bdir, "import.cli.log"), "w", encoding="utf-8").write(r.stdout + r.stderr)
        tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
        log("\n".join(tail))
        if not os.path.exists(proj): sys.exit("cosmetic-mesh-import failed; see build/import.cli.log")


if __name__ == "__main__":
    main()
