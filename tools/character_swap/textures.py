"""Bake game-ready albedo/normal atlases from Illusion (HS2/AI) texture sets.

HS2 skin and hair MainTex are mostly transparent overlays; their visible colour
comes from shader parameters. This module bakes that colour into plain albedo
so a stock costume shader (base colour + normal) shows the character as intended.

  python textures.py CONFIG.json FORGE_ROOT OUT_DIR   -> OUT_DIR/section<N>_c.png, _n.png, atlas.json
"""
import json, os, sys
import numpy as np
from PIL import Image

PAD = 8


def _load(tdir, name, mode="RGBA"):
    p = os.path.join(tdir, name if name.endswith(".png") else name + ".png")
    return np.asarray(Image.open(p).convert(mode)).astype(np.float32) / 255.0 if os.path.exists(p) else None


def _fit(img, shape):
    if img.shape[:2] == shape: return img
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    return np.asarray(im.resize((shape[1], shape[0]), Image.LANCZOS)).astype(np.float32) / 255.0


def _rgb(c): return np.array(c, np.float32) / 255.0


def _over(base_rgb, top_rgba, k=1.0):
    a = top_rgba[..., 3:4] * k
    return base_rgb * (1 - a) + top_rgba[..., :3] * a


def bake(tdir, spec):
    kind = spec["kind"]
    if kind == "plain":
        img = _load(tdir, spec["base"])
        if img.shape[2] == 4 and img[..., 3].min() < 0.99:
            fill = _rgb(spec["fill"]) if "fill" in spec else (img[..., :3] * img[..., 3:4]).sum((0, 1)) / max(img[..., 3].sum(), 1)
            return _over(np.broadcast_to(fill, img.shape[:2] + (3,)).copy(), img)
        return img[..., :3]
    if kind == "skin":
        main = _load(tdir, spec["base"] + "_MainTex")
        # HS2 "OcclusionMap" is a packed shader mask with UV-island patches, not AO: using it
        # blotched the skin. Shade only from the normal map's Z (creases) and keep the tone even.
        col = np.broadcast_to(_rgb(spec["tone"]), main.shape[:2] + (3,)).copy()
        nrm = _load(tdir, spec.get("normal", "")) if spec.get("normal") else None
        if nrm is not None:
            nz = _fit(nrm, main.shape[:2])[..., 2:3]
            col = col * (0.82 + 0.18 * np.clip((nz - 0.5) * 2, 0, 1))
        over = main.copy(); over[..., 3] = np.clip(over[..., 3] * spec.get("overlay_gain", 1.0), 0, 1)
        return np.clip(_over(col, over), 0, 1)
    if kind == "hair":
        main = _load(tdir, spec["base"] + "_MainTex")
        occ = _fit(_load(tdir, spec["base"] + "_Occlusion"), main.shape[:2])[..., :3].mean(2, keepdims=True)
        col = _rgb(spec["color"]) * (0.55 + 0.9 * occ)
        hl = main.copy(); hl[..., :3] = np.clip(_rgb(spec["color"]) * 3.0 + 0.08, 0, 1)
        return np.clip(_over(col, hl, 0.35), 0, 1)
    if kind == "eye":
        sclera = _load(tdir, spec["base"] + "_MainTex")[..., :3]
        iris = _fit(_load(tdir, spec["base"] + "_Texture2"), sclera.shape[:2])
        hi = _fit(_load(tdir, spec["base"] + "_Texture4"), sclera.shape[:2])
        m = iris[..., 2:3]
        pattern = 1 - iris[..., 0:1]
        col = _rgb(spec["iris"]) * (0.45 + 0.9 * pattern)
        h, w = m.shape[:2]; yy, xx = np.mgrid[0:h, 0:w]
        r = np.hypot(xx - w / 2, yy - h / 2)[..., None] / (w / 2)
        pupil = np.clip((0.16 - r) / 0.03, 0, 1)
        out = sclera * (1 - m) + col * m
        out = out * (1 - pupil) + 0.02 * pupil
        return np.clip(out + hi[..., :3].mean(2, keepdims=True) * 0.8, 0, 1)
    if kind == "tinted":
        base = _load(tdir, spec["base"])
        mask = _fit(_load(tdir, spec["mask"]), base.shape[:2])
        c = [_rgb(x) for x in spec["colors"]]
        tint = c[0] * (1 - mask[..., 0:1]) + c[1] * mask[..., 0:1]
        tint = tint * (1 - mask[..., 1:2]) + c[2] * mask[..., 1:2]
        g = base[..., :3].mean(2, keepdims=True)
        out = np.clip(tint * (0.25 + 1.3 * g), 0, 1)
        if base[..., 3].min() < 0.99:
            out = _over(np.broadcast_to(tint * 0.5, out.shape).copy(), np.concatenate([out, base[..., 3:4]], 2))
        return out
    raise ValueError("unknown texture kind " + kind)


def normal(tdir, spec, shape):
    n = _load(tdir, spec["normal"]) if spec.get("normal") else None
    if n is None: return np.broadcast_to(np.array([0.5, 0.5, 1.0], np.float32), shape + (3,)).copy()
    return _fit(n[..., :3], shape)


def pack(items):
    """items: {key: (w, h)} -> canvas size, {key: (x, y, w, h)} using shelf packing with uniform scale."""
    big = max(max(w, h) for w, h in items.values())
    area = sum(w * h for w, h in items.values())
    canvases = [2048, 4096] if (big <= 2048 and area <= 2048 * 2048) else [4096]
    for C in canvases:
        for s in (2.0, 1.5, 1.25, 1.0, 0.75, 0.5):
            sz = {k: (int(w * s), int(h * s)) for k, (w, h) in items.items()}
            if max(max(v) for v in sz.values()) > C: continue
            x = y = rowh = 0; out = {}; ok = True
            for k in sorted(sz, key=lambda k: (-sz[k][1], k)):
                w, h = sz[k]
                if x + w > C: x, y, rowh = 0, y + rowh, 0
                if y + h > C: ok = False; break
                out[k] = (x, y, w, h); x += w; rowh = max(rowh, h)
            if ok: return C, out
    raise ValueError("atlas does not fit")


def build(cfg, root, out_dir):
    tdir = os.path.join(root, cfg["texture_dir"])
    os.makedirs(out_dir, exist_ok=True)
    per = {}
    for mname, m in cfg["meshes"].items():
        per.setdefault(m["section"], set()).add(m["texture"])
    atlas = {}
    for sec, keys in sorted(per.items()):
        baked = {k: bake(tdir, cfg["textures"][k]) for k in sorted(keys)}
        C, rects = pack({k: (v.shape[1], v.shape[0]) for k, v in baked.items()})
        col = np.zeros((C, C, 3), np.float32); nrm = np.broadcast_to(np.array([0.5, 0.5, 1.0], np.float32), (C, C, 3)).copy()
        # glTF metallic-roughness (R unused, G roughness, B metal): replaces the donor's packed
        # material mask so no donor metal/gloss/region layout leaks onto the new UVs.
        mr = np.zeros((C, C, 3), np.float32); mr[..., 0] = 1.0; mr[..., 1] = 0.6
        uvr = {}
        for k, (x, y, w, h) in rects.items():
            col[y:y + h, x:x + w] = _fit(baked[k], (h, w))
            nrm[y:y + h, x:x + w] = normal(tdir, cfg["textures"][k], (h, w))
            spec = cfg["textures"][k]
            mr[y:y + h, x:x + w, 1] = spec.get("rough", 0.6)
            metal = np.full((h, w), spec.get("metal", 0.0), np.float32)
            if spec["kind"] == "tinted" and spec.get("metal", 0) > 0:
                mask = _fit(_load(tdir, spec["mask"]), (h, w))
                metal = metal * (1 - mask[..., 0])  # tinted cloth regions stay dielectric
            mr[y:y + h, x:x + w, 2] = metal
            # UVs stay PAD px inside the cell so mip filtering never bleeds into a neighbour.
            uvr[k] = [(x + PAD) / C, (y + PAD) / C, (w - 2 * PAD) / C, (h - 2 * PAD) / C]
        Image.fromarray((np.clip(col, 0, 1) * 255 + 0.5).astype(np.uint8)).save(os.path.join(out_dir, f"section{sec}_c.png"))
        Image.fromarray((np.clip(nrm, 0, 1) * 255 + 0.5).astype(np.uint8)).save(os.path.join(out_dir, f"section{sec}_n.png"))
        Image.fromarray((np.clip(mr, 0, 1) * 255 + 0.5).astype(np.uint8)).save(os.path.join(out_dir, f"section{sec}_mr.png"))
        Image.fromarray(np.full((C, C, 3), 255, np.uint8)).save(os.path.join(out_dir, f"section{sec}_ao.png"))
        atlas[str(sec)] = {"size": C, "rects": uvr}
        print("section", sec, C, {k: rects[k] for k in rects})
    json.dump(atlas, open(os.path.join(out_dir, "atlas.json"), "w"), indent=1)
    return atlas


if __name__ == "__main__":
    cfg = json.load(open(sys.argv[1], encoding="utf-8"))
    build(cfg, sys.argv[2], sys.argv[3])
