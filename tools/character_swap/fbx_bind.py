"""Read true skin bind matrices from a binary FBX (7.x) without Blender.

Blender's importer can rebuild armature rest poses from the BindPose node,
which for Illusion/HS2 exports differs from the clusters' TransformLink
(the matrices the mesh was actually bound with, height slider included).
This returns, per bone name, the TransformLink global bind matrix
(column-vector, FBX file units/axes) so joint positions match the mesh.
"""
import struct, zlib
import numpy as np


def _read_props(buf, off, n):
    props = []
    for _ in range(n):
        t = chr(buf[off]); off += 1
        if t in "YCIFDL":
            fmt = {"Y": "<h", "C": "<?", "I": "<i", "F": "<f", "D": "<d", "L": "<q"}[t]
            props.append(struct.unpack_from(fmt, buf, off)[0]); off += struct.calcsize(fmt)
        elif t in "fdlib":
            length, enc, clen = struct.unpack_from("<III", buf, off); off += 12
            raw = buf[off:off + clen]; off += clen
            if enc == 1: raw = zlib.decompress(raw)
            dt = {"f": "<f4", "d": "<f8", "l": "<i8", "i": "<i4", "b": "u1"}[t]
            props.append(np.frombuffer(raw, dt, length))
        elif t in "SR":
            length = struct.unpack_from("<I", buf, off)[0]; off += 4
            props.append(bytes(buf[off:off + length])); off += length
        else:
            raise ValueError("bad FBX property type %r" % t)
    return props, off


def _parse(buf, off, end, wide):
    nodes = []
    hdr = "<QQQB" if wide else "<IIIB"; hs = struct.calcsize(hdr)
    while off < end:
        e, n, plen, nl = struct.unpack_from(hdr, buf, off)
        if e == 0: break
        name = bytes(buf[off + hs:off + hs + nl]).decode("ascii", "replace")
        p0 = off + hs + nl
        props, _ = _read_props(buf, p0, n)
        kids = _parse(buf, p0 + plen, e, wide) if p0 + plen < e else []
        nodes.append((name, props, kids)); off = e
    return nodes


def read_bind(path):
    buf = open(path, "rb").read()
    ver = struct.unpack_from("<I", buf, 23)[0]
    top = _parse(buf, 27, len(buf), ver >= 7500)
    objs = next(k for n, p, k in top if n == "Objects")
    conns = next(k for n, p, k in top if n == "Connections")
    models, clusters = {}, {}
    for n, p, k in objs:
        if n == "Model":
            models[p[0]] = p[1].split(b"\x00")[0].decode("ascii", "replace")
        elif n == "Deformer" and p[2] == b"Cluster":
            d = {kn: kp[0] for kn, kp, _ in k if kn in ("Transform", "TransformLink")}
            if "TransformLink" in d: clusters[p[0]] = d
    out = {}
    for n, p, k in conns:
        if n == "C" and p[0] == b"OO" and p[1] in models and p[2] in clusters:
            c = clusters[p[2]]
            out[models[p[1]]] = {"link": np.array(c["TransformLink"]).reshape(4, 4).T,
                                 "mesh": np.array(c["Transform"]).reshape(4, 4).T}
    return out


if __name__ == "__main__":
    import sys
    b = read_bind(sys.argv[1])
    print(len(b), "bound bones")
    for n in sys.argv[2:]:
        if n in b: print(n, b[n]["link"][:3, 3].round(3), "mesh-T", b[n]["mesh"][:3, 3].round(3), "scale", np.linalg.norm(b[n]["link"][:3, :3], axis=0).round(3))
