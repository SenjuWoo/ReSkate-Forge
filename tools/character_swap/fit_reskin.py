"""Fit a source character onto skate.'s render skeleton and reskin it.

Pure numpy. Input is blender_dump.py's npz, the FBX's true bind matrices
(fbx_bind.py), the game skeleton (skate_skeleton.py) and the texture atlas
table (textures.py). Output: per LOD and per native section, game-space
vertex buffers with <=4 game-bone influences.

Method
  1. Source joint positions come from the clusters' TransformLink (the matrices
     the mesh was really bound with); unbound joints use a fitted affine map.
  2. A similarity (scale + translation) roughly aligns the source to the game rig.
  3. Every anchor joint gets a rigid delta: move its head onto the game joint
     and turn its aim segment onto the game's. Other joints inherit the delta of
     their nearest anchored ancestor. Vertices are deformed by linear blend
     skinning with the source weights, i.e. the source is re-posed into the game
     bind pose with its own skinning.
  4. Source influences are remapped to game bones by the rig profile; limb
     influences are spread over the game's twist (RM_) joints by position.
"""
import re
import numpy as np

# ---------------------------------------------------------------- rig profile
SIDES = (("L", "Left"), ("R", "Right"))
FINGERS = (("Thumb", "Thumb"), ("Index", "Index"), ("Middle", "Middle"), ("Ring", "Ring"), ("Little", "Pinky"))


def illusion_hs2_anchors():
    a = [("cf_J_Hips", "mid:cf_J_LegUp00_L,cf_J_LegUp00_R", "Hips", "cf_J_Spine03", "Spine3"),
         ("cf_J_Spine03", "cf_J_Spine03", "Spine3", "cf_J_Neck", "Neck"),
         ("cf_J_Neck", "cf_J_Neck", "Neck", "cf_J_Head", "Head"),
         ("cf_J_Head", "cf_J_Head", "Head", None, None)]
    for s, S in SIDES:
        a += [(f"cf_J_Shoulder_{s}", f"cf_J_Shoulder_{s}", f"{S}Shoulder", f"cf_J_ArmUp00_{s}", f"{S}Arm"),
              (f"cf_J_ArmUp00_{s}", f"cf_J_ArmUp00_{s}", f"{S}Arm", f"cf_J_ArmLow01_{s}", f"{S}ForeArm"),
              (f"cf_J_ArmLow01_{s}", f"cf_J_ArmLow01_{s}", f"{S}ForeArm", f"cf_J_Hand_{s}", f"{S}Hand"),
              (f"cf_J_Hand_{s}", f"cf_J_Hand_{s}", f"{S}Hand", f"cf_J_Hand_Middle01_{s}", f"{S}HandMiddle1"),
              (f"cf_J_LegUp00_{s}", f"cf_J_LegUp00_{s}", f"{S}UpLeg", f"cf_J_LegLow01_{s}", f"{S}Leg"),
              (f"cf_J_LegLow01_{s}", f"cf_J_LegLow01_{s}", f"{S}Leg", f"cf_J_Foot01_{s}", f"{S}Foot"),
              (f"cf_J_Foot01_{s}", f"cf_J_Foot01_{s}", f"{S}Foot", f"cf_J_Toes01_{s}", f"{S}ToeBase"),
              (f"cf_J_Toes01_{s}", f"cf_J_Toes01_{s}", f"{S}ToeBase", None, None)]
        for h, g in FINGERS:
            for k in (1, 2, 3):
                nxt = (f"cf_J_Hand_{h}0{k + 1}_{s}", f"{S}Hand{g}{k + 1}") if k < 3 else (None, None)
                a.append((f"cf_J_Hand_{h}0{k}_{s}", f"cf_J_Hand_{h}0{k}_{s}", f"{S}Hand{g}{k}") + nxt)
    return a


def illusion_hs2_weight_rule(name):
    """-> list of (target, fraction); target is a game bone or 'CHAIN:<kind>:<Side>', None = defer to parent."""
    m = re.search(r"_(L|R)$", name)
    S = {"L": "Left", "R": "Right"}[m.group(1)] if m else None
    if name.startswith("cf_J_Mune"):
        if re.match(r"cf_J_Mune00(_[tsd])?_", name):
            return [("Spine3", 0.5), (f"PS_{S}Shoulder_Sec_03", 0.5)]
        if name == "cf_J_Mune00":
            return [("Spine3", 1.0)]
        return [(f"PS_{S}Shoulder_Sec_03", 1.0)]
    if name.startswith("cf_J_Siri"):
        return [("Hips", 0.5), (f"PS_{S}UpLeg_Sec_04", 0.5)]
    if name.startswith("cf_J_LegUpDam"):
        return [("Hips", 0.5), (f"CHAIN:THIGH:{S}", 0.5)]
    if re.match(r"cf_J_(LegUp0|LegKnee)", name): return [(f"CHAIN:THIGH:{S}", 1.0)]
    if re.match(r"cf_J_LegLow", name): return [(f"CHAIN:SHIN:{S}", 1.0)]
    if name.startswith("cf_J_Foot"): return [(f"{S}Foot", 1.0)]
    if name.startswith("cf_J_Toes"): return [(f"{S}ToeBase", 1.0)]
    if name.startswith("cf_J_Shoulder"): return [(f"{S}Shoulder", 1.0)]
    if re.match(r"cf_J_(ArmUp|ArmElbo)", name): return [(f"CHAIN:UPPERARM:{S}", 1.0)]
    if re.match(r"cf_J_(ArmLow|Hand_Wrist)", name): return [(f"CHAIN:FOREARM:{S}", 1.0)]
    f = re.match(r"cf_J_Hand_(Thumb|Index|Middle|Ring|Little)0(\d)", name)
    if f: return [(f"{S}Hand{dict(FINGERS)[f.group(1)]}{min(int(f.group(2)), 3)}", 1.0)]
    if name.startswith("cf_J_Hand"): return [(f"{S}Hand", 1.0)]
    if name.startswith("cf_J_Neck"): return [("CHAIN:NECK:", 1.0)]
    if name in ("cf_J_Head", "cf_J_Head_s", "p_cf_head_bone"): return [("Head", 1.0)]
    if re.match(r"cf_J_(Hips|Kosi|Belly|Spine|Ana|Kokan|Vagina)", name): return [("CHAIN:TORSO:", 1.0)]
    return None


CHAINS = {
    "THIGH": lambda S: [f"RM_{S}UpLeg_0{i}" for i in (1, 2, 3, 4)],
    "SHIN": lambda S: [f"RM_{S}Leg_0{i}" for i in (1, 2, 3, 4)],
    "UPPERARM": lambda S: [f"RM_{S}Arm_0{i}" for i in (1, 2, 3, 4)],
    "FOREARM": lambda S: [f"RM_{S}ForeArm_0{i}" for i in (1, 2, 3, 4)],
    "NECK": lambda S: ["Neck", "Neck1"],
    "TORSO": lambda S: ["Hips", "Spine", "Spine1", "Spine2", "Spine3"],
}

# ---------------------------------------------------------------- math helpers


def rot_between(a, b):
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b)
    v = np.cross(a, b); c = float(np.dot(a, b))
    if c < -0.9999:
        p = np.cross(a, [1, 0, 0]); p = p if np.linalg.norm(p) > 1e-3 else np.cross(a, [0, 1, 0])
        p /= np.linalg.norm(p); return 2 * np.outer(p, p) - np.eye(3)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx / (1 + c)


def game_to_blender(p): return np.array([p[0], -p[2], p[1]])


def blender_to_game(P): return np.stack([P[:, 0], P[:, 2], -P[:, 1]], 1)


def chain_split(P, joints):
    """Tent weights of points P over an ordered joint polyline; returns (n, len(joints))."""
    J = np.asarray(joints); n = len(J)
    out = np.zeros((len(P), n))
    a, b = J[0], J[-1]; d = b - a
    t = np.clip(((P - a) @ d) / (d @ d), 0, 1) * (n - 1)
    k = np.minimum(np.floor(t).astype(int), n - 2); f = t - k
    out[np.arange(len(P)), k] = 1 - f; out[np.arange(len(P)), k + 1] += f
    return out


def height_split(z, heights):
    h = np.asarray(heights); n = len(h)
    out = np.zeros((len(z), n))
    t = np.interp(z, h, np.arange(n))
    k = np.minimum(np.floor(t).astype(int), n - 2); f = t - k
    out[np.arange(len(z)), k] = 1 - f; out[np.arange(len(z)), k + 1] += f
    return out

# ---------------------------------------------------------------- main fit


def source_joints(dump, bind):
    names = list(dump["bone_names"]); H = dump["bone_head"]
    bound = [n for n in names if n in bind]
    P = np.array([bind[n]["link"][:3, 3] for n in bound]); P = np.c_[P[:, 0], -P[:, 2], P[:, 1]] * 0.01
    X = np.c_[np.array([H[names.index(n)] for n in bound]), np.ones(len(bound))]
    A = np.linalg.lstsq(X, P, rcond=None)[0]
    J = np.c_[H, np.ones(len(H))] @ A
    for n, p in zip(bound, P): J[names.index(n)] = p
    resid = float(np.abs(X @ A - P).max())
    return J, resid, A


def fit(cfg, dump, bind, skel):
    gnames, gpar, glocal, gmodel = skel
    G = {n: game_to_blender(M[3, :3]) for n, M in zip(gnames, gmodel)}
    gidx = {n: i for i, n in enumerate(gnames)}
    names = list(dump["bone_names"]); par = dump["bone_parent"]; idx = {n: i for i, n in enumerate(names)}
    J, resid, A = source_joints(dump, bind)

    def kp(spec):
        if spec.startswith("mid:"):
            a, b = spec[4:].split(","); return (J[idx[a]] + J[idx[b]]) / 2
        return J[idx[spec]]

    anchors = [a for a in illusion_hs2_anchors() if a[0] in idx and a[2] in G]
    core = [a for a in anchors if "Hand_" not in a[0]]
    K0 = np.array([kp(a[1]) for a in core]); G0 = np.array([G[a[2]] for a in core])
    s = ((K0 - K0.mean(0)) * (G0 - G0.mean(0))).sum() / ((K0 - K0.mean(0)) ** 2).sum()
    t = G0.mean(0) - s * K0.mean(0)
    Ssim = np.eye(4); Ssim[:3, :3] *= s; Ssim[:3, 3] = t

    delta = {}
    order = sorted(range(len(names)), key=lambda i: _depth(par, i))
    anchor_by_bone = {a[0]: a for a in anchors}
    rot_of = {}
    for i in order:
        n = names[i]
        if n in anchor_by_bone:
            _, kspec, gname, kaim, gaim = anchor_by_bone[n]
            k = s * kp(kspec) + t
            if kaim and kaim in idx and gaim in G:
                R = rot_between(s * kp(kaim) + t - k, G[gaim] - G[gname])
            else:
                p = par[i]
                while p >= 0 and names[p] not in rot_of: p = par[p]
                R = rot_of.get(names[p], np.eye(3)) if p >= 0 else np.eye(3)
            rot_of[n] = R
            D = np.eye(4); D[:3, :3] = R; D[:3, 3] = G[gname] - R @ k
            delta[i] = D @ Ssim
        else:
            p = par[i]
            delta[i] = delta[p] if p >= 0 else Ssim
    report = {"similarity_scale": float(s), "bind_affine_resid": resid,
              "anchor_error_before": float(np.abs(s * K0 + t - G0).max()), "rest_to_bind": A}
    return delta, report, G, gidx


def _depth(par, i):
    d = 0
    while par[i] >= 0: i = par[i]; d += 1
    return d


def reskin_mesh(tag, dump, delta, G, gidx, cfg, rule_cache):
    names = list(dump["bone_names"]); par = dump["bone_parent"]
    P = dump[tag + "|pos"]; N = dump[tag + "|nrm"]; W = dump[tag + "|w"]
    n = len(P)
    if str(dump[tag + "|rigid"][0]):
        # Bone-attached accessory: Blender placed it in armature-rest space, which for
        # Illusion rigs is not the mesh bind space. Map it with the same rest->bind affine.
        A = cfg["_rest_to_bind"]
        P = np.c_[P, np.ones(n)] @ A
        L = A[:3, :3]; N = N @ np.linalg.inv(L).T  # row-vector normal transform
        N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-8)
    if len(W) == 0:  # rigid mesh with no bone parent: follow the configured bone
        b = names.index(cfg.get("rigid_fallback_bone", "cf_J_Head"))
        W = np.c_[np.arange(n), np.full(n, b), np.ones(n)]
    vi = W[:, 0].astype(int); bi = W[:, 1].astype(int); w = W[:, 2]
    wsum = np.bincount(vi, w, n); w = w / wsum[vi]
    # 1. re-pose into the game bind pose with the source's own skinning
    Pd = np.zeros((n, 3)); Nd = np.zeros((n, 3))
    for b in np.unique(bi):
        sel = bi == b; D = delta[b]
        Rn = D[:3, :3] / np.cbrt(abs(np.linalg.det(D[:3, :3])))
        np.add.at(Pd, vi[sel], (P[vi[sel]] @ D[:3, :3].T + D[:3, 3]) * w[sel, None])
        np.add.at(Nd, vi[sel], (N[vi[sel]] @ Rn.T) * w[sel, None])
    Nd /= np.maximum(np.linalg.norm(Nd, axis=1, keepdims=True), 1e-8)
    # 2. remap influences to game bones
    acc = {}
    for b in np.unique(bi):
        rule = rule_cache.get(b)
        if rule is None:
            j = b
            while j >= 0 and illusion_hs2_weight_rule(names[j]) is None: j = par[j]
            rule = illusion_hs2_weight_rule(names[j]) if j >= 0 else [("Hips", 1.0)]
            rule_cache[b] = rule
        sel = bi == b; vs = vi[sel]; ws = w[sel]
        for target, frac in rule:
            if target.startswith("CHAIN:"):
                _, kind, S = target.split(":")
                chain = [c for c in CHAINS[kind](S) if c in gidx]
                if kind in ("TORSO", "NECK"):
                    split = height_split(Pd[vs, 2], [G[c][2] for c in chain])
                else:
                    split = chain_split(Pd[vs], [G[c] for c in chain])
                for ci, c in enumerate(chain):
                    acc.setdefault(gidx[c], np.zeros(n))
                    np.add.at(acc[gidx[c]], vs, ws * frac * split[:, ci])
            else:
                acc.setdefault(gidx[target], np.zeros(n))
                np.add.at(acc[gidx[target]], vs, ws * frac)
    bones = np.array(list(acc.keys())); M = np.stack([acc[b] for b in bones], 1)
    k = cfg.get("max_influences", 4)
    if M.shape[1] < k:  # fewer distinct bones than slots: pad with zero-weight columns
        M = np.c_[M, np.zeros((n, k - M.shape[1]))]; bones = np.r_[bones, np.full(k - len(bones), bones[0])]
    top = np.argsort(-M, axis=1)[:, :k]
    jw = np.take_along_axis(M, top, 1); jw[jw < 1e-3] = 0
    jw /= np.maximum(jw.sum(1, keepdims=True), 1e-8)
    joints = bones[top]; joints[jw == 0] = joints[:, :1].repeat(k, 1)[jw == 0]
    return blender_to_game(Pd), blender_to_game(Nd), joints.astype(np.uint16), jw.astype(np.float32)


def remap_uv(uv, rect):
    u = np.clip(uv[:, 0], 0, 1); v = np.clip(1 - uv[:, 1], 0, 1)  # Blender bottom-left -> glTF top-left
    return np.stack([rect[0] + u * rect[2], rect[1] + v * rect[3]], 1)
