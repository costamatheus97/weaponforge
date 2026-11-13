"""weaponforge: the review. What a person did by hand on AssaultG3 over six passes, made something the pipeline runs:

    figures(weapon, objs, maps)           measured from the player's eyes and the front picture (the hero pictures `fp`, `ads`
                                          and the default one): sharpness, surface kinds, hardware and marks per area, faces
                                          with no surface kind, the largest bare stretch
    weaponforge <id> review               a review pack: the hero shots, a fixed set of native crops chosen from the weapon's own
                                          sockets and parts, the figures as JSON and a contact sheet (make_pack)
    ... --against DIR                     side-by-side pairs of every crop with another build (its pack, or a build folder: its
                                          pictures are taken from THIS build's cameras so the pairs line up), the change in every
                                          figure and a pixel difference per crop, so that unchanged crops can be skipped
    ... --critic 'command'                a pluggable judge of each pair (critic.py, run outside Blender); off by default

Why: looking back over AssaultG3's passes, part of the judging was measurement nobody had computed, and the rest was pairwise
("is B better than A in this crop?"), which held up, where marks out of ten did not (two reviewers gave one build 6.5 and 8.5).
The figures are said by the check for every weapon and counted only for one that sets Weapon.review (docs/review.md).

Everything here is measured on the game parts (the LP collection) at rest, in the weapon frame (cm), with the bake's maps
(bake/*.npy, or the texture stage's work images for a build that kept only those).
"""
import json
import math
import os
import re
import struct
import time

import numpy as np

# ---- the figures
SAMPLE = 3                 # the eyes' frames are looked at every SAMPLE-th pixel of hero.FP_RES (800 x 450 rays an eye)
SHARP_PX_CM = 80.0         # texture px per cm of surface (at the weapon's texture size) that reads sharp in the hero frames
KIND_MIN = 0.02            # a surface kind with less of the fp frame's weapon pixels than this is not counted as one the eye reads
BARE_REACH = 1.0           # cm: as check.BARE_REACH: a point is bare when nothing is modelled or marked within this of it
BARE_FLAT = 6.0            # degrees: neighbours further apart than this are a crease (modelled form), as check.BARE_FLAT
BARE_STEP = 0.5            # cm: neighbours further apart in depth than this are an edge
SMALL_PIECE_CM = 3.0       # a separate piece of the game mesh whose box is under this across is a piece of hardware
CODE_ON = 96               # an ID map channel over this is on (bake.Kind codes, one bit a channel)

# ---- what a weapon that sets Weapon.review = 'first_person' is held to: figure: ('min' or 'max', limit, what it is).
# Weapon.review_limits = {figure: limit} moves a limit. Chosen on AssaultG3 from three builds (docs/review.md has the table):
# the one rated 6.5 (_before_assemblies), the one before pass 5 and the one after pass 6. The kinds, hardware and marks limits
# lie between the 6.5 build and the pre-pass-5 one: they hold the modelling passes. The two sharpness limits lie between the
# pre-pass-5 build and today's: they hold the texel pass (tight pack and texel zones), which the 6.5 and pre-pass-5 builds both
# lack. Measured and said but not held, because they do not separate the builds: the largest bare stretch, the faces with
# no surface kind (docs/review.md says why).
LIMITS = {
    'fp_sharp_share': ('min', 0.60, 'of the hip view\'s weapon pixels at %.0f texture px/cm or more' % SHARP_PX_CM),
    'ads_sharp_share': ('min', 0.75, 'of the aiming view\'s weapon pixels at %.0f texture px/cm or more' % SHARP_PX_CM),
    'fp_kinds': ('min', 3, 'surface kinds with %.0f %% or more of the hip view' % (KIND_MIN * 100)),
    'front_kinds': ('min', 4, 'surface kinds with %.0f %% or more of the front picture' % (KIND_MIN * 100)),
    'pieces_per_100cm2': ('min', 0.25, 'separate pieces of hardware in the game mesh per 100 cm2 of its surface'),
    'marks_per_100cm2': ('min', 0.60, 'marks (lettering, pictograms) per 100 cm2 of the game mesh\'s surface'),
}


def limits(weapon):
    """LIMITS with the weapon's own overrides (Weapon.review_limits)."""
    out = dict(LIMITS)
    for key, value in (getattr(weapon, 'review_limits', None) or {}).items():
        op, _old, what = out[key]
        out[key] = (op, value, what)
    return out


def held(weapon, figs):
    """[(figure, ok, its value, the limit as text, what it is)] for every figure in limits(): a figure that could not be
    measured is a miss."""
    rows = []
    for key, (op, limit, what) in limits(weapon).items():
        value = figs.get(key)
        ok = value is not None and (value >= limit if op == 'min' else value <= limit)
        rows.append((key, ok, value, '%s %s' % ('at least' if op == 'min' else 'at most', _fmt(limit)), what))
    return rows


def _fmt(v):
    if v is None:
        return 'not measured'
    if isinstance(v, (int, np.integer)) and not isinstance(v, bool):
        return '%d' % v
    return '%.4g' % v


def _mesh(objs):
    """The parts joined, as triangles in the weapon frame: {'co' (n,3), 'tri' (m,3) vertex indices, 'part' (m) index into
    objs, 'uv' (m,3,2), 'area' (m) cm2, 'uvarea' (m) sheet units, 'normal' (m,3)}."""
    from . import uv as U
    cos, tris, parts, uvs = [], [], [], []
    base = 0
    for k, o in enumerate(objs):
        me = o.data
        me.calc_loop_triangles()
        co = np.empty(len(me.vertices) * 3, dtype=np.float64)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        m = np.array(o.matrix_world)
        cos.append(co @ m[:3, :3].T + m[:3, 3])
        n = len(me.loop_triangles)
        vi = np.empty(n * 3, dtype=np.int64)
        me.loop_triangles.foreach_get('vertices', vi)
        li = np.empty(n * 3, dtype=np.int64)
        me.loop_triangles.foreach_get('loops', li)
        tris.append(vi.reshape(-1, 3) + base)
        parts.append(np.full(n, k))
        layer = me.uv_layers.get(U.UV_NAME) or (me.uv_layers[0] if len(me.uv_layers) else None)
        if layer is not None:
            uv = np.empty(len(me.loops) * 2, dtype=np.float64)
            layer.data.foreach_get('uv', uv)
            uvs.append(uv.reshape(-1, 2)[li].reshape(-1, 3, 2))
        else:
            uvs.append(np.zeros((n, 3, 2)))
        base += len(co)
    co = np.concatenate(cos) if cos else np.zeros((0, 3))
    tri = np.concatenate(tris) if tris else np.zeros((0, 3), dtype=np.int64)
    uv = np.concatenate(uvs) if uvs else np.zeros((0, 3, 2))
    a, b, c = co[tri[:, 0]], co[tri[:, 1]], co[tri[:, 2]]
    cross = np.cross(b - a, c - a)
    area = np.linalg.norm(cross, axis=1) * 0.5
    normal = cross / np.maximum(area[:, None] * 2.0, 1.0e-12)
    e1, e2 = uv[:, 1] - uv[:, 0], uv[:, 2] - uv[:, 0]
    uvarea = np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) * 0.5
    return {'co': co, 'tri': tri, 'part': np.concatenate(parts) if parts else np.zeros(0, dtype=np.int64), 'uv': uv,
            'area': area, 'uvarea': uvarea, 'normal': normal, 'names': [o.name for o in objs],
            'bones': [o.get('bone') for o in objs], 'mats': [o.get('mat') for o in objs],
            'builders': [o.get('builder') for o in objs]}


def _tree(mesh):
    from mathutils.bvhtree import BVHTree
    return BVHTree.FromPolygons(mesh['co'].tolist(), mesh['tri'].tolist())


def length_m(mesh):
    """The weapon's length in m along its longer horizontal axis, as hero.make measures it (the parts are in cm)."""
    if not len(mesh['co']):
        return 0.0
    lo, hi = mesh['co'].min(axis=0), mesh['co'].max(axis=0)
    return float(max(hi[0] - lo[0], hi[1] - lo[1])) / 100.0


def eye_cameras(weapon, length):
    """{'fp': camera, 'ads': camera} in the weapon frame, from hero.player_eyes: what the hero pictures fp and ads see."""
    from . import hero
    out = {}
    for name, (eye, look) in hero.player_eyes(weapon, length).items():
        fwd = np.array(look.normalized())
        right = np.cross(fwd, (0.0, 0.0, 1.0))
        right /= np.linalg.norm(right)
        up = np.cross(right, fwd)
        out[name] = {'loc': list(map(float, eye)), 'right': right.tolist(), 'up': up.tolist(), 'fwd': fwd.tolist(),
                     'tan': math.tan(math.radians(hero.FP_FOV) / 2.0), 'res': list(hero.FP_RES)}
    return out


def project(cam, pts):
    """Pixel (x, y) in the camera's picture (top left 0, 0) and depth along its axis, for points (n, 3) in the weapon frame."""
    rel = np.asarray(pts, dtype=np.float64) - np.array(cam['loc'])
    x, y, z = rel @ np.array(cam['right']), rel @ np.array(cam['up']), rel @ np.array(cam['fwd'])
    w, h = cam['res']
    tan_w = cam['tan']
    tan_h = tan_w * h / w
    zz = np.maximum(z, 1.0e-9)
    return np.stack([w * 0.5 * (1.0 + x / (zz * tan_w)), h * 0.5 * (1.0 - y / (zz * tan_h))], axis=1), z


def _focal(cam):
    return cam['res'][0] * 0.5 / cam['tan']


def cast(tree, cam, sample=SAMPLE):
    """Look at every `sample`-th pixel of the camera's picture: {'tri' (h,w) triangle hit or -1, 'dist' (h,w) cm,
    'loc' (h,w,3), 'cos' (h,w) of the angle between the ray and the face, 'shape'}."""
    from mathutils import Vector
    w, h = cam['res']
    nx, ny = w // sample, h // sample
    tan_w = cam['tan']
    tan_h = tan_w * h / w
    xs = (np.arange(nx) * sample + sample * 0.5) / w * 2.0 - 1.0
    ys = 1.0 - (np.arange(ny) * sample + sample * 0.5) / h * 2.0
    right, up, fwd = np.array(cam['right']), np.array(cam['up']), np.array(cam['fwd'])
    d = fwd[None, None, :] + xs[None, :, None] * tan_w * right[None, None, :] + ys[:, None, None] * tan_h * up[None, None, :]
    d /= np.linalg.norm(d, axis=2, keepdims=True)
    origin = Vector(cam['loc'])
    tri = np.full((ny, nx), -1, dtype=np.int64)
    dist = np.zeros((ny, nx))
    loc = np.zeros((ny, nx, 3))
    cos = np.zeros((ny, nx))
    flat = d.reshape(-1, 3)
    ray = tree.ray_cast
    for k in range(len(flat)):
        v = Vector(flat[k])
        hit, nor, idx, dd = ray(origin, v, 1000.0)
        if hit is not None:
            j, i = divmod(k, nx)
            tri[j, i] = idx
            dist[j, i] = dd
            loc[j, i] = hit
            cos[j, i] = abs(nor.dot(v))
    return {'tri': tri, 'dist': dist, 'loc': loc, 'cos': cos, 'dir': d, 'sample': sample}


def _uv_at(mesh, view):
    """The UV (sheet units) under every pixel that hit, by the barycentric weights of the hit point in its triangle."""
    t = view['tri']
    hit = t >= 0
    idx = t[hit]
    co, tri = mesh['co'], mesh['tri'][idx]
    a, b, c = co[tri[:, 0]], co[tri[:, 1]], co[tri[:, 2]]
    p = view['loc'][hit]
    v0, v1, v2 = b - a, c - a, p - a
    d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1)
    d20, d21 = (v2 * v0).sum(1), (v2 * v1).sum(1)
    den = np.where(np.abs(d00 * d11 - d01 * d01) < 1.0e-18, 1.0, d00 * d11 - d01 * d01)
    wv = (d11 * d20 - d01 * d21) / den
    ww = (d00 * d21 - d01 * d20) / den
    wu = 1.0 - wv - ww
    uv = mesh['uv'][idx]
    return uv[:, 0] * wu[:, None] + uv[:, 1] * wv[:, None] + uv[:, 2] * ww[:, None]


def _texel(img, uv):
    """The map's value under each UV (nearest texel; row 0 is v = 0, as the bake writes its .npy)."""
    n = img.shape[0]
    x = np.clip((uv[:, 0] * n).astype(np.int64), 0, n - 1)
    y = np.clip((uv[:, 1] * n).astype(np.int64), 0, n - 1)
    return img[y, x]


def _near(mask, r):
    """True where a True of `mask` lies within r cells (a square reach): check._near's arithmetic, for a reach per cell."""
    h, w = mask.shape
    total = np.zeros((h + 1, w + 1), dtype=np.int64)
    total[1:, 1:] = np.cumsum(np.cumsum(mask.astype(np.int64), axis=0), axis=1)
    ys, xs = np.arange(h), np.arange(w)
    y0, y1 = np.clip(ys - r, 0, h), np.clip(ys + r + 1, 0, h)
    x0, x1 = np.clip(xs - r, 0, w), np.clip(xs + r + 1, 0, w)
    return (total[y1][:, x1] - total[y0][:, x1] - total[y1][:, x0] + total[y0][:, x0]) > 0


def _components(mask):
    """Label the 4-connected regions of a boolean mask: (labels (h,w) with -1 outside, count)."""
    h, w = mask.shape
    lab = np.full((h, w), -1, dtype=np.int64)
    n = 0
    for j0, i0 in zip(*np.nonzero(mask)):
        if lab[j0, i0] >= 0:
            continue
        stack = [(j0, i0)]
        lab[j0, i0] = n
        while stack:
            j, i = stack.pop()
            for jj, ii in ((j - 1, i), (j + 1, i), (j, i - 1), (j, i + 1)):
                if 0 <= jj < h and 0 <= ii < w and mask[jj, ii] and lab[jj, ii] < 0:
                    lab[jj, ii] = n
                    stack.append((jj, ii))
        n += 1
    return lab, n


def kind_codes(weapon):
    """{(r, g, b) bits: kind name} of the weapon's surface kinds (bake.kinds_of)."""
    from . import bake as B
    return {tuple(int(c > 0.5) for c in k.code): name for name, k in B.kinds_of(weapon).items()}


def _kinds_under(maps, uv, codes):
    """The surface kind's name under each UV, or None where the ID map has no kind there."""
    bits = (_texel(maps['id'], uv)[:, :3] > CODE_ON).astype(np.int64)
    key = bits[:, 0] * 4 + bits[:, 1] * 2 + bits[:, 2]
    names = {c[0] * 4 + c[1] * 2 + c[2]: n for c, n in codes.items()}
    return np.array([names.get(int(k)) for k in key], dtype=object)


def _detail(maps):
    """Where the bake found something modelled or marked (convex edges, cavities, lettering) on a 1024 grid, widened by a
    cell: check.bare_faces' test."""
    size = maps['masks'].shape[0]
    f = max(1, size // 1024)
    n = size // f

    def pool(a):
        return a[:n * f, :n * f].reshape(n, f, n, f).any(axis=(1, 3))
    det = pool((maps['masks'][..., 1] > 64) | (maps['masks'][..., 2] > 64))
    if maps.get('marks') is not None:
        det |= pool(maps['marks'][..., :3].max(axis=2) > 64)
    return _near(det, 1)


def sharpness(mesh, view, size):
    """(the mean texture px/cm under the weapon's pixels, the share of them at SHARP_PX_CM or more)."""
    t = view['tri']
    hit = t >= 0
    if not hit.any():
        return None, None
    idx = t[hit]
    ppc = np.sqrt(mesh['uvarea'][idx] * size * size / np.maximum(mesh['area'][idx], 1.0e-12))
    return float(np.sqrt((ppc ** 2).mean())), float((ppc >= SHARP_PX_CM).mean())


def kinds_seen(maps, mesh, view, codes):
    """{kind or 'none': share of the weapon's pixels}."""
    hit = view['tri'] >= 0
    if not hit.any():
        return {}
    names = _kinds_under(maps, _uv_at(mesh, view), codes)
    out = {}
    for n in names:
        key = n or 'none'
        out[key] = out.get(key, 0) + 1
    total = float(len(names))
    return {k: v / total for k, v in sorted(out.items(), key=lambda kv: -kv[1])}


def bare(maps, mesh, view, cam, detail=None, debug=None):
    """The largest stretch the eye sees with nothing modelled or marked within BARE_REACH cm of it: (cm2, share of the
    weapon's pixels, the part most of it is on). Edges are modelled form: the picture's outline, a crease between
    neighbours (BARE_FLAT), a step in depth (BARE_STEP) and a change of part all count as something there."""
    t = view['tri']
    hit = t >= 0
    if not hit.any():
        return 0.0, 0.0, None
    detail = _detail(maps) if detail is None else detail
    uv = _uv_at(mesh, view)
    busy = ~hit.copy()
    b = np.zeros(hit.shape, dtype=bool)
    b[hit] = _texel(detail[..., None], uv)[:, 0]
    busy |= b
    nrm = np.zeros(hit.shape + (3,))
    nrm[hit] = mesh['normal'][t[hit]]
    part = np.full(hit.shape, -1)
    part[hit] = mesh['part'][t[hit]]
    cos_flat = math.cos(math.radians(BARE_FLAT))
    for axis in (0, 1):
        a = [slice(None), slice(None)]
        c = [slice(None), slice(None)]
        a[axis], c[axis] = slice(0, -1), slice(1, None)
        a, c = tuple(a), tuple(c)
        edge = ((nrm[a] * nrm[c]).sum(-1) < cos_flat) | (np.abs(view['dist'][a] - view['dist'][c]) > BARE_STEP) | (part[a] != part[c])
        busy[a] |= edge
        busy[c] |= edge
    focal = _focal(cam) / view['sample']
    cosv = np.clip(view['cos'], 0.05, 1.0)
    px_cm = focal * np.sqrt(cosv) / np.maximum(view['dist'], 1.0e-6)      # this grid's cells per cm of surface
    reach = np.clip(np.ceil(BARE_REACH * px_cm), 1, 64).astype(np.int64)
    free = hit & ~busy
    for r in np.unique(reach[free]):
        sel = free & (reach == r)
        free[sel] &= ~_near(busy, int(r))[sel]
    lab, n = _components(free)
    if debug is not None:
        debug.update({'hit': hit, 'busy': busy, 'free': free, 'detail': b, 'lab': lab})
    if not n:
        return 0.0, 0.0, None
    cm2 = np.where(hit, view['dist'] ** 2 / (focal ** 2 * cosv), 0.0)
    sums = np.bincount(lab[lab >= 0], weights=cm2[lab >= 0], minlength=n)
    best = int(np.argmax(sums))
    on = part[lab == best]
    name = mesh['names'][int(np.bincount(on).argmax())] if len(on) else None
    return float(sums[best]), float((lab == best).sum()) / float(hit.sum()), name


def no_kind_faces(maps, mesh, codes):
    """(how many game triangles have no surface kind under their middle, their cm2)."""
    uv = mesh['uv'].mean(axis=1)
    names = _kinds_under(maps, uv, codes)
    none = np.array([n is None for n in names], dtype=bool)
    by = {}
    for k in mesh['part'][none]:
        by[mesh['names'][int(k)]] = by.get(mesh['names'][int(k)], 0) + 1
    return int(none.sum()), float(mesh['area'][none].sum()), by


def front_camera(mesh):
    """The hero front picture's camera (hero.SHOTS[0]: toward the muzzle and the weapon's left, 80 mm, hero.RES), framed by
    hero.make's rule (the nearest that keeps every point inside 7 % of the sides and 10 % of the top and bottom, aimed at the
    middle of what it sees), worked out here on the game parts in the weapon frame without rendering."""
    from . import hero
    _sfx, where, lens = hero.SHOTS[0]
    pts = mesh['co'][::max(1, len(mesh['co']) // 4000)]
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    centre = (lo + hi) / 2.0
    axis = 0 if (hi[0] - lo[0]) >= (hi[1] - lo[1]) else 1
    length = hi[axis] - lo[axis]
    muzzle = np.array((1.0, 0.0, 0.0))             # the weapon frame's +X, as hero.make takes it (it was the end farther from the grip)
    up = np.array((0.0, 0.0, 1.0))
    left = np.cross(up, muzzle)
    d = muzzle * where[0] + left * where[1] + up * where[2]
    d /= np.linalg.norm(d)
    fwd = -d
    right = np.cross(fwd, up)
    right /= np.linalg.norm(right)
    cam = {'right': right.tolist(), 'up': np.cross(right, fwd).tolist(), 'fwd': fwd.tolist(), 'tan': 18.0 / lens,
           'res': list(hero.RES)}
    target = centre.copy()
    w, h = hero.RES
    for attempt in range(6):
        dist = 0.3 * length
        for _ in range(300):
            cam['loc'] = (target + d * dist).tolist()
            xy, z = project(cam, pts)
            u, v = xy[:, 0] / w, 1.0 - xy[:, 1] / h
            if ((0.07 < u) & (u < 0.93) & (0.10 < v) & (v < 0.90) & (z > 0.0)).all():
                break
            dist *= 1.03
        off_x = (u.min() + u.max()) / 2.0 - 0.5
        off_y = (v.min() + v.max()) / 2.0 - 0.5
        if attempt == 5 or (abs(off_x) < 0.004 and abs(off_y) < 0.004):
            break
        wide = 2.0 * dist * cam['tan']
        target = target + right * off_x * wide + np.array(cam['up']) * off_y * wide * h / w
    return cam


MARK_POINTS = 200          # of a mark's vertices, this many are looked at from the eye (spread evenly over them)
MARK_SEEN = 0.5            # a mark the eye sees less than this of is named in the log and on the contact sheet (said, never held)
MARK_BLOCK_CM = 0.15       # a mark is cut into the surface: the first surface on the line to it may be this much nearer than it and still be it


def glyph_pieces(n, edges):
    """Which separate piece of the mesh each of n vertices belongs to, given its edges (m, 2): an array of piece numbers. A line of
    lettering is a piece a letter (a letter with a counter or two is still one)."""
    parent = np.arange(n)

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    roots = np.array([find(v) for v in range(n)])
    return np.unique(roots, return_inverse=True)[1]


def mark_figures(mesh, tree, cam, marks, pieces, scale=1.0):
    """For every mark (name, points) as the eye `cam` sees it, in the order given: how wide a letter is on the screen and how much of
    the mark the eye can see.

      letter_px_w, letter_px_h   the median width of a letter (a separate piece of the mark that is at least half as high as the
                                 highest) along the line of the lettering, and the height of the line, in picture pixels (cam's
                                 resolution times `scale`); None when the mark is not in front of the eye
      in_frame, seen             the share of the mark's points inside the picture; the share of them the eye sees (in the picture,
                                 and nothing nearer on the line from the eye)
      blocked_by                 {part: share of the mark's points} that another part of the game mesh is in front of: the part in the way

    The points are the mark's vertices, which lie in the surface the lettering is cut into (kit.keep_mark): a surface within
    MARK_BLOCK_CM in front of one is that surface itself."""
    from mathutils import Vector
    w, h = cam['res']
    eye = np.array(cam['loc'])
    rows = []
    for (name, pts), comp in zip(marks, pieces):
        pts = np.asarray(pts, dtype=np.float64)
        row = {'mark': name, 'at': [round(float(v), 2) for v in pts.mean(axis=0)], 'letter_px_w': None, 'letter_px_h': None,
               'in_frame': 0.0, 'seen': 0.0, 'blocked_by': {}}
        xy, z = project(cam, pts)
        front = z > 0.5
        if front.sum() >= 3:
            pxy = xy[front] * scale
            c = pxy - pxy.mean(axis=0)
            vals, vecs = np.linalg.eigh(c.T @ c)
            run, high = c @ vecs[:, 1], c @ vecs[:, 0]               # along the lettering, and across it
            comp_f = np.asarray(comp)[front]
            spans = [(float(np.ptp(run[comp_f == k])), float(np.ptp(high[comp_f == k]))) for k in np.unique(comp_f)]
            tall = max(sp[1] for sp in spans)
            row['letter_px_w'] = float(np.median([sp[0] for sp in spans if sp[1] >= 0.5 * tall]))
            row['letter_px_h'] = float(tall)
        idx = np.linspace(0, len(pts) - 1, min(len(pts), MARK_POINTS)).astype(np.int64)
        seen, framed, blocked = 0, 0, {}
        for i in idx:
            if z[i] <= 0.5 or not (0 <= xy[i, 0] < w and 0 <= xy[i, 1] < h):
                continue
            framed += 1
            to = pts[i] - eye
            dist = float(np.linalg.norm(to))
            hit = tree.ray_cast(Vector(eye), Vector(to / dist), dist + 1.0)
            if hit[2] is None or hit[3] >= dist - MARK_BLOCK_CM:
                seen += 1
            else:
                part = mesh['names'][int(mesh['part'][hit[2]])]
                blocked[part] = blocked.get(part, 0) + 1
        row['in_frame'] = framed / float(len(idx))
        row['seen'] = seen / float(len(idx))
        row['blocked_by'] = {k: round(v / float(len(idx)), 3) for k, v in sorted(blocked.items(), key=lambda kv: -kv[1])}
        rows.append(row)
    return rows


def loose_pieces(mesh, small_cm=SMALL_PIECE_CM):
    """Placed hardware in the game mesh: {part: how many of its connected pieces have a box under small_cm across (a screw
    head, a pin, a rivet)}, counted only in a part made of more than one piece, so that a small control that is a whole part
    on its own (a trigger, a release button) is not counted. Hardware modelled only in the detail model (a screw cut into a
    face) is never counted: it is in the marks and the normal map, not in the game mesh."""
    tri, co = mesh['tri'], mesh['co']
    parent = np.arange(len(co))

    def find(a):
        root = a
        while parent[root] != root:
            root = parent[root]
        while parent[a] != root:
            parent[a], a = root, parent[a]
        return root
    for a, b, c in tri:
        ra = find(a)
        parent[find(b)] = ra
        parent[find(c)] = ra
    used = np.unique(tri.ravel())
    roots = np.array([find(v) for v in used])
    vpart = np.full(len(co), -1)
    vpart[tri.ravel()] = np.repeat(mesh['part'], 3)
    pieces = {}
    for r in np.unique(roots):
        vs = used[roots == r]
        box = co[vs].max(axis=0) - co[vs].min(axis=0)
        pieces.setdefault(int(vpart[vs[0]]), []).append(float(np.linalg.norm(box)))
    out = {}
    for k, sizes in pieces.items():
        small = sum(1 for d in sizes if d < small_cm)
        if len(sizes) > 1 and small:
            out[mesh['names'][k]] = small
    return out


def figures(weapon, objs, maps, cams=None, size=None, marks=None):
    """Every figure, as {name: value}. objs: the game parts with UVs, at rest. maps: {'id', 'masks', 'marks' or None}
    (load_maps). cams: the eye cameras (default: eye_cameras of this build). size: the texture size px/cm is counted at
    (default: the weapon's texture_size). marks: the bake's mark objects (lettering, pictograms), counted when given."""
    t0 = time.time()
    mesh = _mesh(objs)
    tree = _tree(mesh)
    size = size or weapon.texture_size
    cams = dict(cams or eye_cameras(weapon, length_m(mesh)))
    cams.setdefault('front', front_camera(mesh))
    codes = kind_codes(weapon)
    detail = _detail(maps)
    out = {'eyes': {k: [round(v, 2) for v in c['loc']] for k, c in cams.items()}, 'texture_px': size}
    none_px = []
    for name in ('fp', 'ads', 'front'):
        if name not in cams:
            continue
        view = cast(tree, cams[name])
        n_hit = int((view['tri'] >= 0).sum())
        out['%s_pixels' % name] = n_hit * view['sample'] ** 2
        kinds = kinds_seen(maps, mesh, view, codes)
        none_px.append((kinds.get('none', 0.0), n_hit))
        if name in ('fp', 'ads'):
            out['%s_px_cm' % name], out['%s_sharp_share' % name] = sharpness(mesh, view, size)
        if name in ('fp', 'front'):
            out['%s_kind_shares' % name] = {k: round(v, 4) for k, v in kinds.items()}
            out['%s_kinds' % name] = sum(1 for k, v in kinds.items() if k != 'none' and v >= KIND_MIN)
            cm2, share_b, part = bare(maps, mesh, view, cams[name], detail)
            out['%s_bare_cm2' % name], out['%s_bare_part' % name] = cm2, part
    total = sum(n for _s, n in none_px)
    out['no_kind_seen'] = sum(s * n for s, n in none_px) / total if total else None
    out['no_kind_tris'], out['no_kind_cm2'], out['no_kind_by_part'] = no_kind_faces(maps, mesh, codes)
    area = float(mesh['area'].sum())
    out['surface_cm2'] = area
    pieces = loose_pieces(mesh)
    out['pieces'] = sum(pieces.values())
    out['pieces_by_part'] = pieces
    out['pieces_per_100cm2'] = 100.0 * out['pieces'] / area if area else None
    if marks is not None:
        out['marks'] = len(marks)
        out['marks_per_100cm2'] = 100.0 * len(marks) / area if area else None
    out['seconds'] = round(time.time() - t0, 1)
    return out


def load_maps(folder, tag=None):
    """The bake's maps for a build folder: bake/{id,masks,marks}.npy, or for a build that kept only the texture stage's work
    images, textures/work/<tag>_{id,masks,marks}.png (written upside down to the .npy). None when there is no ID map."""
    bake = os.path.join(folder, 'bake')
    if os.path.isfile(os.path.join(bake, 'id.npy')) and os.path.isfile(os.path.join(bake, 'masks.npy')):
        marks = os.path.join(bake, 'marks.npy')
        return {'id': np.load(os.path.join(bake, 'id.npy'), mmap_mode='r'), 'masks': np.load(os.path.join(bake, 'masks.npy'), mmap_mode='r'),
                'marks': np.load(marks, mmap_mode='r') if os.path.isfile(marks) else None, 'from': bake}
    work = os.path.join(folder, 'textures', 'work')
    if tag and os.path.isfile(os.path.join(work, '%s_id.png' % tag.lower())):
        out = {'from': work}
        for key in ('id', 'masks', 'marks'):
            path = os.path.join(work, '%s_%s.png' % (tag.lower(), key))
            out[key] = read_png(path)[::-1] if os.path.isfile(path) else None
        return out if out['masks'] is not None else None
    return None


# ------------------------------------------------------------------------------------------------------------ pictures
def read_png(path):
    """(h, w, 4) uint8, top row first, of a PNG as stored (no colour transform)."""
    import bpy
    img = bpy.data.images.load(path, check_existing=False)
    try:
        img.colorspace_settings.name = 'Non-Color'
        w, h = img.size
        buf = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(buf)
    finally:
        bpy.data.images.remove(img)
    return (np.clip(buf.reshape(h, w, 4)[::-1], 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def write_png(path, arr):
    """Write (h, w, 3 or 4) uint8, top row first, as an 8-bit PNG, exactly."""
    import bpy
    arr = np.asarray(arr)
    h, w = arr.shape[:2]
    if arr.shape[2] == 3:
        arr = np.concatenate([arr, np.full((h, w, 1), 255, dtype=np.uint8)], axis=2)
    img = bpy.data.images.new('review_out', w, h, alpha=True, float_buffer=False)
    try:
        img.colorspace_settings.name = 'Non-Color'
        img.pixels.foreach_set((arr[::-1].astype(np.float32) / 255.0).ravel())
        img.filepath_raw = path
        img.file_format = 'PNG'
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img.save()
    finally:
        bpy.data.images.remove(img)
    return path


def _plain(v):
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    return str(v)


def dump(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, indent=1, default=_plain)
    return path


def load(path):
    with open(path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


# ------------------------------------------------------------------------------------------------------------- the pack
SHOTS = ('default', 'beauty', 'fp', 'ads', 'left', 'right', 'outline')       # hero.make's pictures: front and rear, beauty, fp, ads,
#                                                                              the two sides, the silhouette from the left
SHOT_FILES = (('front', ''), ('rear', '_rear'), ('beauty', '_beauty'), ('fp', '_fp'), ('ads', '_ads'), ('left', '_left'),
              ('right', '_right'), ('outline', '_outline'))
SIDES = (('left', '_left', 1.0), ('right', '_right', -1.0))      # a side, the picture straight from it, the sign of its way on the weapon's Y
SIDE_CM = 0.4              # a control or a mark whose middle is this far or farther off the weapon's middle plane is on that side
WALL_FACING = 0.85         # a face is part of a side wall when its normal points this much along the side's axis
WALL_MIN_CM2 = 10.0        # a part has a wall on a side when its faces that look straight out of it add up to this (visible ones only)
WALL_PARTS = 2             # the crops of the walls of a side: its largest parts' walls, this many
WALL_SPLIT = 0.75          # a wall wider than this share of CROP_MAX is cut into several crops, side by side, none cut round its middle
CROP_PAD = 0.25            # a crop is the thing's own box on the picture widened by this share and 24 px on every side
CROP_MIN = 256             # px: and at least this wide and high (native pixels: a crop is never scaled)
CROP_MAX = (1200, 900)     # px: and at most this (a bigger box is cut round its middle; a wall is split instead)
CONTROL_CM2 = 40.0         # a part on a bone of its own with less surface than this is a control (trigger, safety, release)
CONTROL_SEEN = 8           # of up to 300 points of a control, at least this many must be seen for its crop
NEAR_SHARE = 0.30          # fp_near: the nearest share of the weapon's pixels in the hip view (the cover on AssaultG3)
GRIP_BOX = ((-7.0, -3.5, -14.0), (5.0, 3.5, 1.0))     # cm round the grip origin (the hold): the grip of any weapon
MUZZLE_BOX = ((-8.0, -4.0, -4.0), (1.0, 4.0, 4.0))    # cm round the Muzzle socket
DIFF_LEVEL = 12            # a pixel has changed when one of its channels moved by more than this (of 255)
UNCHANGED = 0.002          # a crop with less than this share of its pixels changed is unchanged: 100 times the most a
                           # self-pair moved (AssaultG3 against its own pack: 0.00002; docs/review.md)
AMMO_KINDS = ('brass', 'copper')                       # parts of these kinds are cartridges, not controls


def shot_camera(record, suffix):
    """A recorded hero picture's camera in the weapon frame (the dict project() takes), or None."""
    from mathutils import Matrix
    shot = record.get('shots', {}).get(suffix)
    if shot is None or shot.get('type') == 'ORTHO':           # the outline is a whole picture, never a crop box worked out from a camera
        return None
    m = Matrix(record['to_world']).inverted() @ Matrix(shot['camera'])
    rot = m.to_3x3()
    cols = [rot.col[i].normalized() for i in range(3)]
    return {'loc': list(m.translation), 'right': list(cols[0]), 'up': list(cols[1]), 'fwd': list(-cols[2]),
            'tan': math.tan(shot['angle'] / 2.0), 'res': list(shot['res'])}


def _fit(box, res):
    """A crop box [x0, y0, x1, y1] round a thing's box on the picture (CROP_PAD, CROP_MIN, CROP_MAX), inside the picture;
    None when the thing is not in the picture."""
    w, h = res
    x0, y0, x1, y1 = box
    if x1 <= 0 or y1 <= 0 or x0 >= w or y0 >= h:
        return None
    x0, y0, x1, y1 = max(x0, 0.0), max(y0, 0.0), min(x1, float(w)), min(y1, float(h))
    pw, ph = (x1 - x0) * CROP_PAD + 24.0, (y1 - y0) * CROP_PAD + 24.0
    bw = int(min(max(x1 - x0 + 2 * pw, CROP_MIN), CROP_MAX[0], w))
    bh = int(min(max(y1 - y0 + 2 * ph, CROP_MIN), CROP_MAX[1], h))
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    left = int(round(min(max(cx - bw / 2.0, 0.0), w - bw)))
    top = int(round(min(max(cy - bh / 2.0, 0.0), h - bh)))
    return [left, top, left + bw, top + bh]


def _bbox(cam, pts):
    xy, z = project(cam, pts)
    xy = xy[z > 0.5]
    if not len(xy):
        return None
    return [float(xy[:, 0].min()), float(xy[:, 1].min()), float(xy[:, 0].max()), float(xy[:, 1].max())]


def _seen_points(tree, mesh, cam, k, most=300):
    """How many of up to `most` triangle middles of part k the camera sees (in the picture, facing it, and the first thing
    on the line to it)."""
    from mathutils import Vector
    idx = np.nonzero(mesh['part'] == k)[0]
    if not len(idx):
        return 0
    idx = idx[np.argsort(-mesh['area'][idx], kind='stable')][:most]
    mid = mesh['co'][mesh['tri'][idx]].mean(axis=1)
    xy, z = project(cam, mid)
    w, h = cam['res']
    eye = np.array(cam['loc'])
    n = 0
    for i, t in enumerate(idx):
        if z[i] <= 0.5 or not (0 <= xy[i, 0] < w and 0 <= xy[i, 1] < h):
            continue
        to = mid[i] - eye
        dist = float(np.linalg.norm(to))
        if float(mesh['normal'][t] @ to) >= 0.0:
            continue
        hit = tree.ray_cast(Vector(eye), Vector(to / dist), dist + 0.05)
        if hit[2] is not None and mesh['part'][hit[2]] == k:
            n += 1
    return n


def _visible_tris(tree, mesh, cam, idx):
    """The triangles of idx whose middle the camera sees: in the picture, facing it, and the first thing on the line to it."""
    from mathutils import Vector
    mid = mesh['co'][mesh['tri'][idx]].mean(axis=1)
    xy, z = project(cam, mid)
    w, h = cam['res']
    eye = np.array(cam['loc'])
    keep = []
    for i, t in enumerate(idx):
        if z[i] <= 0.5 or not (0 <= xy[i, 0] < w and 0 <= xy[i, 1] < h):
            continue
        to = mid[i] - eye
        dist = float(np.linalg.norm(to))
        if float(mesh['normal'][t] @ to) >= 0.0:
            continue
        hit = tree.ray_cast(Vector(eye), Vector(to / dist), dist + 0.05)
        if hit[2] is not None and hit[2] == t:
            keep.append(t)
    return np.array(keep, dtype=np.int64)


def _pieces(box):
    """A box [x0, y0, x1, y1] wider than WALL_SPLIT of a crop is cut into as many equal ones side by side as it takes."""
    x0, y0, x1, y1 = box
    n = max(1, int(math.ceil((x1 - x0) / (CROP_MAX[0] * WALL_SPLIT))))
    step = (x1 - x0) / n
    return [[x0 + i * step, y0, x0 + (i + 1) * step, y1] for i in range(n)]


def _side_of(pts):
    """'_left' or '_right' when the points' middle is SIDE_CM or more off the weapon's middle plane (+Y is its left), else None."""
    y = float(np.asarray(pts)[:, 1].mean()) if len(pts) else 0.0
    return '_left' if y >= SIDE_CM else '_right' if y <= -SIDE_CM else None


def _prop_bones(weapon):
    bones = []
    for prop in weapon.props:
        bones += list(weapon.with_children(prop.bones))
    return set(bones)


def crop_plan(weapon, mesh, tree, record, marks=()):
    """The fixed set of crops, chosen from the weapon's own sockets and parts: [{'name', 'shot' (file suffix), 'box', 'what'}]
    and [what was left out and why]. marks: [(name, (n, 3) points in the weapon frame)] of the bake's mark objects."""
    plan, notes = [], []
    cams = {sfx: shot_camera(record, sfx) for _n, sfx in SHOT_FILES}
    sockets = {s[0]: np.array(s[2], dtype=np.float64) for s in weapon.sockets}
    co, tri = mesh['co'], mesh['tri']
    vpart = np.full(len(co), -1)
    vpart[tri.ravel()] = np.repeat(mesh['part'], 3)
    lo = np.array([co[vpart == k].min(axis=0) if (vpart == k).any() else np.zeros(3) for k in range(len(mesh['names']))])
    hi = np.array([co[vpart == k].max(axis=0) if (vpart == k).any() else np.zeros(3) for k in range(len(mesh['names']))])
    area = np.bincount(mesh['part'], weights=mesh['area'], minlength=len(mesh['names']))
    props = _prop_bones(weapon)

    def add_box(name, sfx, box, what):
        cam = cams.get(sfx)
        if cam is None:
            notes.append('%s: no %s picture' % (name, sfx.strip('_') or 'front'))
            return
        box = _fit(box, cam['res']) if box else None
        if box is None:
            notes.append('%s: not in the %s picture' % (name, sfx.strip('_') or 'front'))
            return
        plan.append({'name': name, 'shot': sfx, 'box': box, 'what': what})

    def add(name, sfx, pts, what):
        cam = cams.get(sfx)
        add_box(name, sfx, _bbox(cam, pts) if cam is not None and len(pts) else None, what)

    def pick(sides_first, seen):
        """The picture to cut a thing from: the one straight from the side it is on when that sees it well, else the one that sees most
        of it (the sides come first in `seen`, so that a tie goes to a side picture)."""
        if sides_first and seen.get(sides_first, 0) >= CONTROL_SEEN:
            return sides_first
        return max(seen, key=seen.get) if seen and max(seen.values()) >= CONTROL_SEEN else None

    def part_at(socket):
        """The smallest part whose box (1 cm wider all round) holds the socket, else the nearest box."""
        p = sockets[socket]
        inside = [k for k in range(len(lo)) if np.all(p >= lo[k] - 1.0) and np.all(p <= hi[k] + 1.0)]
        if inside:
            return min(inside, key=lambda k: float(np.prod(hi[k] - lo[k] + 0.01)))
        return int(np.argmin([np.linalg.norm(np.clip(p, lo[k], hi[k]) - p) for k in range(len(lo))]))

    sight = None
    if 'SightRear' in sockets:
        sight = part_at('SightRear')
    else:
        named = [k for k, n in enumerate(mesh['names']) if n == 'SightRear' or mesh['builders'][k] == 'rear_sight']
        sight = named[0] if named else None
    if sight is not None:
        pts = co[vpart == sight]
        how = 'at the SightRear socket' if 'SightRear' in sockets else 'by its name: the weapon has no SightRear socket'
        add('ads_rear_sight', '_ads', pts, 'the rear sight (%s, %s) down the sights' % (mesh['names'][sight], how))
        add('fp_rear_sight', '_fp', pts, 'the rear sight (%s, %s) from the hip' % (mesh['names'][sight], how))
    else:
        notes.append('ads_rear_sight, fp_rear_sight: no SightRear socket and no part named SightRear')
    if cams.get('_fp'):
        view = cast(tree, cams['_fp'], 6)
        hit = view['tri'] >= 0
        if hit.any():
            d = view['dist'][hit]
            near = hit & (view['dist'] <= np.quantile(d, NEAR_SHARE))
            ys, xs = np.nonzero(near)
            cx, cy = float(np.median(xs)) * 6 + 3, float(np.median(ys)) * 6 + 3
            half = (CROP_MAX[0] * 0.4, CROP_MAX[1] * 0.4)
            box = _fit([cx - half[0], cy - half[1], cx + half[0], cy + half[1]], cams['_fp']['res'])
            owner = mesh['names'][int(np.bincount(mesh['part'][view['tri'][near]]).argmax())]
            plan.append({'name': 'fp_near', 'shot': '_fp', 'box': box,
                         'what': 'the nearest %.0f %% of the weapon from the hip (most of it %s)' % (NEAR_SHARE * 100, owner)})
    if 'Muzzle' in sockets:
        m = sockets['Muzzle']
        keep = np.all((co >= m + MUZZLE_BOX[0]) & (co <= m + MUZZLE_BOX[1]), axis=1) & (vpart >= 0)
        add('muzzle', '', co[keep], 'the muzzle, from the front picture')
    else:
        notes.append('muzzle: the weapon has no Muzzle socket')
    body_bone = mesh['bones'][int(np.argmax(area))] if len(area) else None
    on_bone = {}
    for k, bone in enumerate(mesh['bones']):
        on_bone[bone] = on_bone.get(bone, 0.0) + float(area[k])
    for k, name in enumerate(mesh['names']):
        bone = mesh['bones'][k]
        # a control is a small part on a bone of its own that carries nothing big (a sight on the slide is not one)
        if (bone in (None, body_bone) or bone in props or on_bone[bone] >= CONTROL_CM2 or mesh['mats'][k] in AMMO_KINDS
                or k == sight):
            continue
        # a control is cut from the picture straight from the side it is on (its middle off the weapon's middle plane: +Y is the left),
        # else from whichever of the sides, the front and the rear sees most of it. The front picture shows one side only, so a control
        # on the other one used to come out as bare wall, or as "not seen"
        side = _side_of(co[vpart == k])
        seen = {sfx: _seen_points(tree, mesh, cams[sfx], k) for sfx in ('_left', '_right', '', '_rear') if cams.get(sfx)}
        sfx = pick(side, seen)
        if sfx is None:
            notes.append('control_%s: %s is not seen in the side, front or rear picture' % (name.lower(), name))
            continue
        add('control_%s' % name.lower(), sfx, co[vpart == k],
            '%s, a control on %s, from the %s picture' % (name, bone, sfx.strip('_') or 'front'))
    keep = np.all((co >= np.array(GRIP_BOX[0])) & (co <= np.array(GRIP_BOX[1])), axis=1)
    keep &= np.array([mesh['bones'][k] not in props if k >= 0 else False for k in vpart])
    if keep.any():
        add('grip', '', co[keep], 'the grip round the hold, from the front picture')
    else:
        notes.append('grip: nothing of the weapon round the grip origin')
    mag = np.array([k >= 0 and mesh['bones'][k] in props for k in vpart])
    if mag.any():
        add('magazine', '', co[mag], 'the parts on the props\' bones (%s), from the front picture'
            % ', '.join(sorted({mesh['names'][k] for k in range(len(mesh['names'])) if mesh['bones'][k] in props})))
    else:
        notes.append('magazine: the weapon has no prop')
    # marks: each is looked at from the picture straight from the side it is on (else from any that sees its middle with nothing in
    # front of it); `marks` is the largest of all in view, and each side's largest follows (marks_left, marks_right) when it is another
    # one, so that a mark on the left is cropped as well as one on the right
    from mathutils import Vector
    seen_marks = []
    for mname, pts in marks or ():
        if not len(pts):
            continue
        mid = pts.mean(axis=0)
        side = _side_of(pts)
        got = {}
        for sfx in ('_left', '_right', '', '_rear'):
            cam = cams.get(sfx)
            if cam is None:
                continue
            box = _bbox(cam, pts)
            if box is None:
                continue
            eye = np.array(cam['loc'])
            to = mid - eye
            dist = float(np.linalg.norm(to))
            hit = tree.ray_cast(Vector(eye), Vector(to / dist), dist + 1.0)
            if hit[0] is None or abs(hit[3] - dist) > 0.4:
                continue                       # something else is in front of it in this picture
            got[sfx] = (box[2] - box[0]) * (box[3] - box[1])
        if not got:
            continue
        sfx = side if side in got else max(got, key=got.get)
        seen_marks.append((got[sfx], mname, sfx, pts, side))
    if seen_marks:
        best = max(seen_marks, key=lambda m: m[0])
        add('marks', best[2], best[3], 'the largest mark in view (%s), from the %s picture' % (best[1], best[2].strip('_') or 'front'))
        for label, sfx_side, _sign in SIDES:
            there = [m for m in seen_marks if m[4] == sfx_side]
            if there:
                top = max(there, key=lambda m: m[0])
                if top[1] != best[1]:
                    add('marks_%s' % label, top[2], top[3], 'the largest mark on the %s (%s), from the %s picture' % (label, top[1], top[2].strip('_') or 'front'))
    else:
        notes.append('marks: no mark is in view in any picture')

    # the large side walls: for each side, the parts with the most surface looking straight out of it, cut from the picture straight
    # from that side (a wide wall is cut into several crops, side by side). The side outline and the walls are what a change of the
    # silhouette or of the look of a big flat face shows in; the crops above are all of small things
    for label, sfx, sign in SIDES:
        cam = cams.get(sfx)
        if cam is None:
            notes.append('wall_%s: no %s picture' % (label, label))
            continue
        facing = mesh['normal'][:, 1] * sign > WALL_FACING
        wall = np.bincount(mesh['part'][facing], weights=mesh['area'][facing], minlength=len(mesh['names']))
        made = 0
        for k in [int(k) for k in np.argsort(-wall, kind='stable') if wall[k] >= WALL_MIN_CM2][:WALL_PARTS * 3]:
            if made == WALL_PARTS:
                break
            idx = np.nonzero(facing & (mesh['part'] == k))[0]
            idx = _visible_tris(tree, mesh, cam, idx[np.argsort(-mesh['area'][idx], kind='stable')][:400])
            if len(idx) < 3:
                continue                       # its wall is inside, behind another part: the next one's
            box = _bbox(cam, co[mesh['tri'][idx]].reshape(-1, 3))
            if box is None:
                continue
            parts = _pieces(box)
            made += 1
            for i, piece in enumerate(parts):
                add_box('wall_%s_%s%s' % (label, mesh['names'][k].lower(), '_%d' % (i + 1) if len(parts) > 1 else ''), sfx, piece,
                        'the %s wall of %s (%.0f cm2 looking straight out of the %s)%s' % (
                            label, mesh['names'][k], wall[k], label, ', part %d of %d, left to right in the picture' % (i + 1, len(parts))
                            if len(parts) > 1 else ''))
    shot = record.get('shots', {}).get('_outline')
    if shot:
        plan.append({'name': 'side_outline', 'shot': '_outline', 'box': [0, 0, int(shot['res'][0]), int(shot['res'][1])],
                     'what': 'the weapon\'s silhouette from its left, flat grey, the same camera in both builds'})
    else:
        notes.append('side_outline: no outline picture')
    return plan, notes


# ---- pictures: a contact sheet needs a few words on it, and Blender's Python has no font to draw them with
_GLYPHS = {
    'A': '01110100011000111111100011000110001', 'B': '11110100011000111110100011000111110',
    'C': '01110100011000010000100001000101110', 'D': '11110100011000110001100011000111110',
    'E': '11111100001000011110100001000011111', 'F': '11111100001000011110100001000010000',
    'G': '01110100011000010111100011000101111', 'H': '10001100011000111111100011000110001',
    'I': '01110001000010000100001000010001110', 'J': '00111000100001000010000101001001100',
    'K': '10001100101010011000101001001010001', 'L': '10000100001000010000100001000011111',
    'M': '10001110111010110101100011000110001', 'N': '10001100011100110101100111000110001',
    'O': '01110100011000110001100011000101110', 'P': '11110100011000111110100001000010000',
    'Q': '01110100011000110001101011001001101', 'R': '11110100011000111110101001001010001',
    'S': '01111100001000001110000010000111110', 'T': '11111001000010000100001000010000100',
    'U': '10001100011000110001100011000101110', 'V': '10001100011000110001100010101000100',
    'W': '10001100011000110101101011010101010', 'X': '10001100010101000100010101000110001',
    'Y': '10001100010101000100001000010000100', 'Z': '11111000010001000100010001000011111',
    '0': '01110100011001110101110011000101110', '1': '00100011000010000100001000010001110',
    '2': '01110100010000100010001000100011111', '3': '11111000100010000010000011000101110',
    '4': '00010001100101010010111110001000010', '5': '11111100001111000001000011000101110',
    '6': '00110010001000011110100011000101110', '7': '11111000010001000100010000100001000',
    '8': '01110100011000101110100011000101110', '9': '01110100011000101111000010001001100',
    '.': '00000000000000000000000000110001100', ',': '00000000000000000000011000010001000',
    ':': '00000011000110000000011000110000000', '-': '00000000000000011111000000000000000',
    '_': '00000000000000000000000000000011111', '%': '11000110010001000100010001001100011',
    '/': '00000000010001000100010001000000000', '(': '00010001000100001000010000010000010',
    ')': '01000001000001000010000100010001000', '+': '00000001000010011111001000010000000',
    '=': '00000000001111100000111110000000000', '>': '01000001000001000001000100010001000',
    '<': '00010001000100010000010000010000010',
}


def text(img, x, y, words, scale=2, colour=(235, 235, 235)):
    """Draw `words` (capitals, digits and a little punctuation; anything else is a space) at (x, y), 5 x 7 cells of `scale`
    px. Returns the x after it."""
    h, w = img.shape[:2]
    for ch in str(words).upper().replace('\\', '/'):           # a Windows path keeps its separators
        g = _GLYPHS.get(ch)
        if g:
            cell = np.array([int(c) for c in g], dtype=bool).reshape(7, 5).repeat(scale, 0).repeat(scale, 1)
            y1, x1 = min(h, y + cell.shape[0]), min(w, x + cell.shape[1])
            if y1 > y >= 0 and x1 > x >= 0:
                img[y:y1, x:x1][cell[:y1 - y, :x1 - x]] = colour
        x += 6 * scale
    return x


def shrink(img, w, h):
    """img scaled to w x h (down only), each pixel the mean of four samples."""
    H, W = img.shape[:2]
    if (w, h) == (W, H):
        return img
    acc = np.zeros((h, w, img.shape[2]), dtype=np.float32)
    for oy in (0.25, 0.75):
        for ox in (0.25, 0.75):
            ys = np.clip(((np.arange(h) + oy) * H / h).astype(np.int64), 0, H - 1)
            xs = np.clip(((np.arange(w) + ox) * W / w).astype(np.int64), 0, W - 1)
            acc += img[ys][:, xs].astype(np.float32)
    return (acc / 4.0 + 0.5).astype(np.uint8)


def fit_in(img, w, h):
    H, W = img.shape[:2]
    k = min(1.0, w / float(W), h / float(H))
    return shrink(img, max(1, int(W * k)), max(1, int(H * k)))


def _short(path, keep=2):
    """The last `keep` folders of a path, for a picture: a sheet is shared, and the machine's own folders are not its business
    (compare.json keeps the whole path)."""
    parts = [p for p in re.split(r'[\\/]+', str(path)) if p]
    return '/'.join((['...'] if len(parts) > keep else []) + parts[-keep:])


def _sheet(tiles, cols, tile_w, tile_h, title, lines=(), label_h=26, width=2400):
    """A contact sheet: a title, the tiles [(img, label, colour)] in a grid, then lines of text."""
    pad = 12
    rows = (len(tiles) + cols - 1) // cols
    cell_w = (width - pad) // cols
    height = 60 + rows * (tile_h + label_h + pad) + 26 * len(lines) + pad
    sheet = np.full((height, width, 3), 24, dtype=np.uint8)
    text(sheet, pad, 18, title, 3)
    for i, (img, label, colour) in enumerate(tiles):
        r, c = divmod(i, cols)
        x, y = pad + c * cell_w, 60 + r * (tile_h + label_h + pad)
        t = fit_in(img[..., :3], min(tile_w, cell_w - pad), tile_h)
        sheet[y:y + t.shape[0], x:x + t.shape[1]] = t
        text(sheet, x, y + tile_h + 6, label[:max(1, (cell_w - pad) // 12)], 2, colour)
    y = 60 + rows * (tile_h + label_h + pad)
    for line in lines:
        text(sheet, pad, y, line, 2)
        y += 26
    return sheet


def _summary_lines(weapon, figs):
    if not figs or 'error' in figs:
        return ['figures: %s' % (figs or {}).get('error', 'not measured')]
    aim = ('aiming %.0f px/cm, %.0f %%' % (figs['ads_px_cm'], 100 * figs['ads_sharp_share'])
           if figs.get('ads_px_cm') is not None else 'no aiming view (no SightRear and SightFront sockets)')
    out = ['hip view %.0f px/cm, %.0f %% at %.0f or more; %s' % (
        figs.get('fp_px_cm') or 0, 100 * (figs.get('fp_sharp_share') or 0), SHARP_PX_CM, aim),
        'kinds over %.0f %%: hip view %s, front %s; hardware %s pieces (%.2f per 100 cm2); marks %s (%s per 100 cm2)' % (
        KIND_MIN * 100, figs.get('fp_kinds'), figs.get('front_kinds'), figs.get('pieces'), figs.get('pieces_per_100cm2') or 0,
        figs.get('marks', '-'), _fmt(figs.get('marks_per_100cm2'))),
        'no surface kind: %.3f %% of what the views see; largest bare stretch: hip %.1f cm2, front %.1f cm2' % (
        100 * (figs.get('no_kind_seen') or 0), figs.get('fp_bare_cm2') or 0, figs.get('front_bare_cm2') or 0)]
    if getattr(weapon, 'review', None):
        out.append('held (%s): %s' % (weapon.review, ', '.join('%s %s' % (k, 'ok' if ok else 'MISS')
                                                                 for k, ok, _v, _l, _w in held(weapon, figs))))
    return out


def _mark_lines(rows):
    """Lines for the contact sheet: the marks the hip eye sees little of (MARK_SEEN) and how wide the smallest letter is."""
    if not rows:
        return []
    wide = [r['letter_px_w'] for r in rows if r['letter_px_w'] is not None and r['seen'] > 0]
    out = ['marks from the hip: %d, seen %d %% or more: %d; %s' % (
        len(rows), 100 * MARK_SEEN, sum(1 for r in rows if r['seen'] >= MARK_SEEN),
        'narrowest letter %.1f px wide, widest %.1f' % (min(wide), max(wide)) if wide else 'none in view')]
    for r in [r for r in rows if r['seen'] < MARK_SEEN][:5]:
        out.append('  mark %s at %s cm: seen %d %%%s' % (r['mark'], ' '.join('%.0f' % v for v in r['at']), 100 * r['seen'],
                                                        (', behind ' + ', '.join(r['blocked_by'])) if r['blocked_by'] else ''))
    return out


def cut(shots, plan, folder):
    """Cut every crop of the plan out of its picture ({suffix: image}) into folder/<name>.png: {name: image}."""
    out = {}
    for c in plan:
        img = shots.get(c['shot'])
        if img is None:
            continue
        x0, y0, x1, y1 = c['box']
        out[c['name']] = img[y0:y1, x0:x1]
        write_png(os.path.join(folder, c['name'] + '.png'), out[c['name']])
    return out


def difference(a, b):
    """(mean absolute difference of 255, share of pixels with a channel moved by more than DIFF_LEVEL)."""
    if a.shape != b.shape:
        return None, None
    d = np.abs(a[..., :3].astype(np.int16) - b[..., :3].astype(np.int16))
    return float(d.mean()), float((d.max(axis=2) > DIFF_LEVEL).mean())


class _Elsewhere:
    """Another build of the same weapon, for hero.make: its export and textures in place of this one's."""

    def __init__(self, weapon, folder):
        self._weapon, self._folder = weapon, folder

    @property
    def export_dir(self):
        return os.path.join(self._folder, 'export')

    @property
    def tex_dir(self):
        return os.path.join(self._folder, 'textures')

    @property
    def asset_root(self):
        return self._folder

    def __getattr__(self, key):
        return getattr(self._weapon, key)


def png_size(path):
    """(width, height) of a PNG, read from its header without loading it (a 4096 px texture is 60 MB in memory), or None."""
    try:
        with open(path, 'rb') as fh:
            head = fh.read(24)
    except OSError:
        return None
    if len(head) < 24 or head[:8] != b'\x89PNG\r\n\x1a\n' or head[12:16] != b'IHDR':
        return None
    return struct.unpack('>II', head[16:24])


def texture_px(weapon):
    """The width in px of the game textures the weapon (or an _Elsewhere build) has on disk (T_<Name>_BC.png), or None."""
    size = png_size(os.path.join(weapon.tex_dir, '%s_BC.png' % weapon.tex_prefix))
    return size[0] if size else None


def texture_notes(this, other, cap):
    """What two builds' texture sizes (px on disk; None when not known) mean for putting them side by side, when the pictures
    are taken with the textures capped at `cap` px (hero's --size): ({'this', 'against', 'differ' (True, False or None when one is
    not known), 'pictured': {'this', 'against'}}, [warnings, as sentences])."""
    pic = {'this': min(this, cap) if this else None, 'against': min(other, cap) if other else None}
    info = {'this': this, 'against': other, 'differ': None if not (this and other) else this != other, 'pictured': pic}
    out = []
    if info['differ']:
        out.append('the two builds\' textures differ in size: this build %d px, the build compared against %d px. Sharpness, the px/cm '
                   'figures and the pixel differences below include that, and it is no change of the design. %s' % (
                       this, other, 'Both are pictured at %d px (--size), but the px/cm figures count each build\'s own size.' % pic['this']
                       if pic['this'] == pic['against'] else
                       'They are pictured at %d and %d px; give --size %d to picture both at the same size (the figures keep each '
                       'build\'s own).' % (pic['this'], pic['against'], min(this, other))))
    elif info['differ'] is None:
        out.append('the texture size of %s is not known (%s): whether the pictures are at the same sharpness is not known either'
                   % ('this build' if not this else 'the build compared against',
                      'its textures are not on disk' if not this else 'a pack made before the size was recorded, or a build without textures'))
    return info, out


def build_folder(path, weapon):
    """The build folder (holding <id>.blend) a path names: the folder itself, or <path>/<id>/ (an asset root); else None."""
    for f in (path, os.path.join(path, weapon.id)):
        if os.path.isfile(os.path.join(f, weapon.id + '.blend')):
            return f
    return None


def _measure_build(weapon, folder, log):
    """Open a build's .blend (never saved) and measure it: (figures or {'error'}, mesh, tree, marks [(name, points)])."""
    import bpy
    bpy.ops.wm.open_mainfile(filepath=os.path.join(folder, weapon.id + '.blend'))
    coll = bpy.data.collections.get(weapon.coll('LP'))
    objs = sorted((o for o in coll.objects if o.type == 'MESH'), key=lambda o: o.name) if coll else []
    if not objs:
        raise SystemExit('review: %s has no game parts (%s)' % (folder, weapon.coll('LP')))
    mc = bpy.data.collections.get(weapon.coll('MARKS'))
    marks, pieces = [], []
    for o in (mc.objects if mc else ()):
        if o.type == 'MESH' and len(o.data.vertices):
            co = np.empty(len(o.data.vertices) * 3)
            o.data.vertices.foreach_get('co', co)
            m = np.array(o.matrix_world)
            marks.append((o.name, co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]))
            ev = np.empty(len(o.data.edges) * 2, dtype=np.int64)
            o.data.edges.foreach_get('vertices', ev)
            pieces.append(glyph_pieces(len(o.data.vertices), ev.reshape(-1, 2)))
    mesh = _mesh(objs)
    tree = _tree(mesh)
    maps = load_maps(folder, weapon.tag)
    if maps is None:
        figs = {'error': 'no bake in %s (bake/*.npy or textures/work/%s_id.png)' % (folder, weapon.tag.lower())}
    else:
        try:
            figs = figures(weapon, objs, maps, size=texture_px(_Elsewhere(weapon, folder)) or None, marks=[o for o in mc.objects] if mc else None)
        except Exception as err:                 # a figure that cannot be measured must not cost the pictures
            figs = {'error': 'could not be measured: %r' % (err,)}
    log('review: measured %s in %s s' % (folder, figs.get('seconds', '-')))
    return figs, mesh, tree, marks, pieces


def make_pack(weapon, out=None, against=None, samples=None, res=None, size=None, pack_file=None, log=print):
    """`weaponforge <id> review`: write the review pack and return its folder (docs/review.md). samples, res, size: as for
    hero.make (size: the textures the pictures are taken with, not what the figures are counted at)."""
    from . import hero
    out = out or os.path.join(os.path.dirname(weapon.asset_root), '_gallery', 'review', weapon.name)
    if against and os.path.normcase(os.path.abspath(against)) == os.path.normcase(os.path.abspath(out)):
        raise SystemExit('review: --against %s is the pack this run writes: it would be emptied before it is read; '
                         'give the new pack another folder with --out' % against)
    os.makedirs(out, exist_ok=True)
    for sub in ('shots', 'crops', 'pairs', 'against', 'critic'):
        _clear(os.path.join(out, sub))
    for name in ('compare.json', 'pairs.png', 'punchlist.md', 'punchlist.json'):
        if os.path.isfile(os.path.join(out, name)):
            os.remove(os.path.join(out, name))
    other = None
    if against:
        if os.path.isfile(os.path.join(against, 'pack.json')):
            other = {'kind': 'pack', 'path': against, 'pack': load(os.path.join(against, 'pack.json'))}
        else:
            folder = build_folder(against, weapon)
            if folder is None:
                raise SystemExit('review: --against %s is neither a review pack (pack.json) nor a build (%s.blend)' % (against, weapon.id))
            other = {'kind': 'build', 'path': folder}
    figs, mesh, tree, marks, pieces = _measure_build(weapon, weapon.asset_root, log)
    record = {}
    replay = other['pack']['record'] if other and other['kind'] == 'pack' else None
    hero.make(weapon, size=size, samples=samples, res=res, shots=SHOTS, out_dir=os.path.join(out, 'shots'), record=record,
              replay=replay)
    plan, notes = crop_plan(weapon, mesh, tree, record, marks)
    for n in notes:
        log('review: no crop %s' % n)
    shots = {sfx: read_png(os.path.join(out, 'shots', weapon.name + sfx + '.png'))
             for _n, sfx in SHOT_FILES if os.path.isfile(os.path.join(out, 'shots', weapon.name + sfx + '.png'))}
    crops = cut(shots, plan, os.path.join(out, 'crops'))
    rows = held(weapon, figs) if getattr(weapon, 'review', None) and 'error' not in figs else []
    seen_marks = {}
    if marks and 'error' not in figs:
        # each mark as each of the player's eyes sees it: how wide a letter is on the screen, and how much of it is in view
        cams = eye_cameras(weapon, length_m(mesh))
        scale = (res or hero.FP_RES)[0] / float(hero.FP_RES[0])
        seen_marks = {k: mark_figures(mesh, tree, cams[k], marks, pieces, scale) for k in ('fp', 'ads') if k in cams}
        for r in seen_marks.get('fp', []):
            if r['seen'] < MARK_SEEN:
                log('review: mark %s at (%s) cm is seen %.0f %% from the hip%s; its letters %s px wide' % (
                    r['mark'], ', '.join('%.1f' % v for v in r['at']), 100 * r['seen'],
                    (', behind ' + ', '.join('%s (%.0f %%)' % (k, 100 * v) for k, v in r['blocked_by'].items())) if r['blocked_by']
                    else (', %.0f %% of it in the picture' % (100 * r['in_frame'])),
                    '%.1f' % r['letter_px_w'] if r['letter_px_w'] is not None else 'not'))
    dump(os.path.join(out, 'figures.json'), {'weapon': weapon.id, 'build': weapon.asset_root, 'figures': figs, 'marks_seen': seen_marks,
                                             'held': [dict(zip(('figure', 'ok', 'value', 'limit', 'what'), r)) for r in rows],
                                             'limits': {k: list(v) for k, v in limits(weapon).items()}})
    this_px = texture_px(weapon)
    cap = size or hero.SIZE                    # hero.make loads the textures at most this wide
    pack = {'weapon': weapon.id, 'name': weapon.name, 'build': weapon.asset_root, 'made': time.strftime('%Y-%m-%d %H:%M'),
            'textures': {'size': this_px, 'pictured': min(this_px, cap) if this_px else None},
            'shots': {n: 'shots/%s%s.png' % (weapon.name, sfx) for n, sfx in SHOT_FILES if sfx in shots},
            'crops': plan, 'left_out': notes, 'record': record, 'against': other and {'kind': other['kind'], 'path': other['path']}}
    dump(os.path.join(out, 'pack.json'), pack)
    tiles = [(shots[sfx], n, (180, 200, 255)) for n, sfx in SHOT_FILES if sfx in shots]
    tiles += [(crops[c['name']], c['name'], (235, 235, 235)) for c in plan if c['name'] in crops]
    write_png(os.path.join(out, 'contact.png'),
              _sheet(tiles, 5, 460, 300, '%s review  %s' % (weapon.name, pack['made']),
                     _summary_lines(weapon, figs) + _mark_lines(seen_marks.get('fp'))))
    rubric = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'review_rubric.md')
    if os.path.isfile(rubric):
        with open(rubric, 'r', encoding='utf-8') as src, open(os.path.join(out, 'rubric.md'), 'w', encoding='utf-8') as dst:
            dst.write(src.read())
    warnings = _compare(weapon, out, other, plan, crops, figs, samples, res, size, record, log, this_px, cap) if other else []
    if pack_file:
        with open(pack_file, 'w', encoding='utf-8') as fh:
            fh.write(out)
    log('review: %s (%d pictures, %d crops%s)' % (out, len(shots), len(crops), ', compared against %s' % other['path'] if other else ''))
    for w in warnings:                         # last, where the run's summary is read
        log('review: WARNING %s' % w)
    return out


def _clear(folder):
    if os.path.isdir(folder):
        for root, dirs, files in os.walk(folder, topdown=False):
            for f in files:
                os.remove(os.path.join(root, f))
            for d in dirs:
                os.rmdir(os.path.join(root, d))


def _wrap(words, width=190):
    """words as lines of at most `width` characters (the contact sheets' lettering is 12 px a character on a 2400 px sheet)."""
    lines, line = [], ''
    for w in str(words).split():
        if line and len(line) + 1 + len(w) > width:
            lines.append(line)
            line = ''
        line = (line + ' ' + w) if line else w
    return lines + ([line] if line else [])


def silhouette(img, level=130):
    """The pixels of a side outline picture (<Name>_outline.png: flat light grey on near-black) that are the weapon."""
    return img[..., :3].astype(np.int32).mean(axis=2) > level


def _compare(weapon, out, other, plan, crops, figs, samples, res, size, record, log, this_px=None, cap=None):
    """The other build's crops cut with this build's plan, side-by-side pairs, the change in every figure and a pixel
    difference per crop (compare.json, pairs/, pairs.png). Returns the warnings (also in compare.json under 'warnings', with
    the two builds' texture sizes under 'textures')."""
    from . import hero
    there = os.path.join(out, 'against')
    if other['kind'] == 'build':
        ofigs, _m, _t, _k, _p = _measure_build(weapon, other['path'], log)
        hero.make(_Elsewhere(weapon, other['path']), size=size, samples=samples, res=res, shots=SHOTS,
                  out_dir=os.path.join(there, 'shots'), replay=record)
        folder = os.path.join(there, 'shots')
        dump(os.path.join(there, 'figures.json'), {'weapon': weapon.id, 'build': other['path'], 'figures': ofigs})
    else:
        folder = os.path.join(other['path'], 'shots')
        ofigs = load(os.path.join(other['path'], 'figures.json'))['figures']
    oshots = {sfx: read_png(os.path.join(folder, weapon.name + sfx + '.png'))
              for _n, sfx in SHOT_FILES if os.path.isfile(os.path.join(folder, weapon.name + sfx + '.png'))}
    theirs = cut(oshots, plan, os.path.join(there, 'crops'))
    other_px = texture_px(_Elsewhere(weapon, other['path'])) if other['kind'] == 'build' else (other['pack'].get('textures') or {}).get('size')
    textures, warnings = texture_notes(this_px, other_px, cap or 4096)
    result = {'this': weapon.asset_root, 'against': other['path'], 'kind': other['kind'], 'textures': textures, 'warnings': warnings,
              'figures': {}, 'crops': {}}
    for key in sorted(set(figs) | set(ofigs)):
        if key == 'seconds':                     # how long the measuring took, not a figure of the weapon
            continue
        a, b = ofigs.get(key), figs.get(key)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
            result['figures'][key] = {'against': a, 'this': b, 'change': b - a}
    tiles = []
    for c in plan:
        name = c['name']
        a, b = theirs.get(name), crops.get(name)
        if a is None or b is None:
            result['crops'][name] = {'missing': 'against' if a is None else 'this'}
            continue
        if a.shape != b.shape:
            # the two pictures are not the same size (another --res or another build's pack): there is nothing to lay side by side
            result['crops'][name] = {'missing': 'shape', 'against_shape': list(a.shape), 'this_shape': list(b.shape)}
            warnings.append('the crop %s could not be paired: %s px against %s px (give --res and --samples as the pack compared against '
                            'was made with)' % (name, 'x'.join(str(v) for v in a.shape[1::-1]), 'x'.join(str(v) for v in b.shape[1::-1])))
            continue
        mean, share = difference(a, b)
        same = share is not None and share < UNCHANGED
        gap = np.full((a.shape[0], 8, 3), 200, dtype=np.uint8)
        pair = np.concatenate([a[..., :3], gap, b[..., :3]], axis=1)
        write_png(os.path.join(out, 'pairs', name + '.png'), pair)
        result['crops'][name] = {'pair': 'pairs/%s.png' % name, 'against': 'against/crops/%s.png' % name,
                                 'this': 'crops/%s.png' % name, 'diff_mean': mean, 'diff_share': share, 'unchanged': same}
        if name == 'side_outline':
            sa, sb = silhouette(a), silhouette(b)
            result['crops'][name]['silhouette'] = {'against_px': int(sa.sum()), 'this_px': int(sb.sum()), 'differing_px': int((sa ^ sb).sum()),
                                                   'differing_share': float((sa ^ sb).sum()) / max(1, int((sa | sb).sum()))}
        tiles.append((pair, '%s  %s' % (name, 'unchanged' if same else 'changed %.1f %%' % (100 * share)),
                      (150, 150, 150) if same else (255, 220, 120)))
    changed = sorted(tiles, key=lambda t: 'unchanged' in t[1])
    lines = [('WARNING: ' if i == 0 else '    ') + l for w in warnings for i, l in enumerate(_wrap(w, 180))]
    lines += ['left: %s' % _short(other['path']), 'right: %s' % _short(weapon.asset_root)]
    lines += ['%s: %s -> %s' % (k, _fmt(v['against']), _fmt(v['this'])) for k, v in result['figures'].items()
              if k in LIMITS or k in ('fp_px_cm', 'ads_px_cm', 'pieces', 'marks', 'fp_bare_cm2', 'front_bare_cm2')]
    write_png(os.path.join(out, 'pairs.png'), _sheet(changed, 3, 780, 300, '%s pairs: left the build compared against, right this one'
                                                     % weapon.name, lines))
    dump(os.path.join(out, 'compare.json'), result)
    log('review: %d pairs, %d unchanged' % (len(tiles), sum(1 for v in result['crops'].values() if v.get('unchanged'))))
    return warnings
