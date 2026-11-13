"""weaponforge: clean up the raw bakes and derive the masks the surface material needs (numpy only).

In:  normal / ao / id / cover arrays from bake.bake_all (row 0 at v = 0).
Out: normal (padded, misses flattened), masks (R occlusion, G convex edges, B cavities, A broad wear zone), id (padded).
"""
import numpy as np


def _shift(a, dy, dx):
    return np.roll(np.roll(a, dy, axis=0), dx, axis=1)


def dilate(arrays, valid, steps=24):
    """Grow every array outward from `valid` by `steps` texels (padding against mip bleed). Returns the grown mask."""
    filled = valid.copy()
    for _ in range(steps):
        todo = ~filled
        if not todo.any():
            break
        new_filled = filled.copy()
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            src = _shift(filled, dy, dx)
            take = todo & src & ~new_filled
            if take.any():
                for arr in arrays:
                    arr[take] = _shift(arr, dy, dx)[take]
                new_filled |= take
        filled = new_filled
    return filled


def _box(a, r):
    """Box blur of radius r along both axes (running sums)."""
    for axis in (0, 1):
        pad = [(0, 0)] * a.ndim
        pad[axis] = (r + 1, r)
        c = np.cumsum(np.pad(a, pad, mode='edge'), axis=axis, dtype=np.float64)
        n = a.shape[axis]
        hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
        lo = np.take(c, np.arange(0, n), axis=axis)
        a = ((hi - lo) / (2 * r + 1)).astype(np.float32)
    return a


def masked_blur(a, mask, r, passes=2):
    m = mask.astype(np.float32)
    num = a * m
    den = m.copy()
    for _ in range(passes):
        num = _box(num, r)
        den = _box(den, r)
    return np.where(mask, num / np.maximum(den, 1.0e-4), 0.0).astype(np.float32)


def curvature(normal, mask):
    """Divergence of the tangent-space normal inside the islands: > 0 on convex edges, < 0 in grooves."""
    nx = normal[..., 0] * 2.0 - 1.0
    ny = normal[..., 1] * 2.0 - 1.0

    def diff(a, axis):
        f, b = np.roll(a, -1, axis), np.roll(a, 1, axis)
        mf, mb = np.roll(mask, -1, axis), np.roll(mask, 1, axis)
        d = np.where(mf & mb, (f - b) * 0.5, np.where(mf, f - a, np.where(mb, a - b, 0.0)))
        return np.where(mask, d, 0.0)

    return (diff(nx, 1) + diff(ny, 0)).astype(np.float32)


def process(raw, pad=24, log=print):
    cover = raw['cover'][..., 0] > 0.5
    idm = raw['id'][..., :3].astype(np.float32)
    hit = cover & (idm.max(axis=2) > 0.2)
    missed = cover & ~hit
    log('covered %.1f%% of the sheet, rays that found no detail: %.2f%% of it' % (100.0 * cover.mean(), 100.0 * (cover & ~hit).sum() / max(1, cover.sum())))
    normal = raw['normal'][..., :3].astype(np.float32)
    ao = raw['ao'][..., 0].astype(np.float32)
    # a texel whose ray missed takes its neighbours' values
    arrays = [normal, ao, idm]
    dilate(arrays, hit, steps=6)
    still = cover & ~dilate([], hit, steps=6)
    normal[still] = (0.5, 0.5, 1.0)
    ao[still] = 1.0
    # renormalise
    n = normal * 2.0 - 1.0
    n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1.0e-6)
    normal = n * 0.5 + 0.5

    # the edge masks are tuned at 4K: a smaller sheet turns the normal more per texel, and its wear zone is fewer texels wide
    rel = normal.shape[0] / 4096.0
    curv = masked_blur(curvature(normal, cover), cover, 1, passes=1)
    convex = np.clip(curv * 4.0 * rel, 0.0, 1.0)
    concave = np.clip(-curv * 4.0 * rel, 0.0, 1.0)
    wide = masked_blur(convex, cover, max(1, int(7 * rel + 0.5)), passes=3)
    wide = np.clip(wide * 3.0, 0.0, 1.0)

    masks = np.stack([ao, convex, concave, wide], axis=2).astype(np.float32)
    dilate([normal, masks, idm], cover, steps=pad)
    masks[~cover & (masks[..., 0] == 0.0), 0] = 1.0
    return {'normal': normal.astype(np.float32), 'masks': masks, 'id': idm.astype(np.float32), 'cover': cover, 'missed': missed}


# ---------------------------------------------------------------------------------------------- edge masks by the centimetre
def raster(tris, values, size):
    """Each triangle's value painted where its UVs put it on a size x size sheet (row 0 at v = 0, as the bakes are), 0 where no
    triangle is. tris: (n, 3, 2) UVs in 0..1; values: (n,). A texel takes the triangle its centre is in (the last one listed
    when two overlap)."""
    out = np.zeros((size, size), np.float32)
    px = np.asarray(tris, np.float64) * size - 0.5                 # texel centres at integer coordinates
    for (a, b, c), v in zip(px, np.asarray(values, np.float32)):
        x0, y0 = int(max(0, np.floor(min(a[0], b[0], c[0])))), int(max(0, np.floor(min(a[1], b[1], c[1]))))
        x1, y1 = int(min(size - 1, np.ceil(max(a[0], b[0], c[0])))), int(min(size - 1, np.ceil(max(a[1], b[1], c[1]))))
        if x1 < x0 or y1 < y0:
            continue
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1.0e-12:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        l1 = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / den
        l2 = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / den
        inside = (l1 >= -1.0e-6) & (l2 >= -1.0e-6) & (1.0 - l1 - l2 >= -1.0e-6)
        out[ys[inside], xs[inside]] = v
    return out


EDGE_BANDS = 1.25            # edge_masks: the wide zone's blur radius is rounded to steps of this ratio (one blur per step)


def edge_masks(normal, cover, scale):
    """The convex, concave and wide-zone masks of process(), worked out by the centimetre instead of by the texel: `scale` is
    each texel's density over the density the masks are tuned at (1 where it is that, 2 where an island has twice the texels
    per cm). A bevel then gives its mask the same width in cm at any density: the curvature (the normal's turn per texel,
    which falls as the texels get denser) is multiplied by it, and the radii of its smoothing and of the wide zone's blur
    (texels) grow with it. Where
    scale is 1 everywhere this is process()'s own sum (but for the float16 / 8-bit rounding of the saved maps).
    Returns (convex, concave, wide), each size x size float32."""
    rel = normal.shape[0] / 4096.0
    scale = np.where(cover, np.maximum(scale, 1.0e-3), 1.0).astype(np.float32)
    # the curvature's own one-texel smoothing is a fixed width in cm too: one texel at the tuned density, two at twice it
    raw = curvature(normal, cover)
    r1 = np.maximum(1, (scale + 0.5).astype(np.int32))
    curv = np.zeros_like(raw)
    for r in np.unique(r1[cover]) if cover.any() else (1,):
        sel = cover & (r1 == r)
        curv[sel] = masked_blur(raw, cover, int(r), passes=1)[sel]
    convex = np.clip(curv * 4.0 * rel * scale, 0.0, 1.0)
    concave = np.clip(-curv * 4.0 * rel * scale, 0.0, 1.0)
    radius = np.maximum(1, (7 * rel * scale + 0.5).astype(np.int32))
    bands, r = [], 1                    # one blur per band of radii (EDGE_BANDS apart), each texel taking its own band's
    top = int(radius[cover].max()) if cover.any() else 1
    while r <= top:
        bands.append(r)
        r = max(r + 1, int(r * EDGE_BANDS + 0.5))
    wide = np.zeros_like(convex)
    for i, r in enumerate(bands):
        sel = cover & (radius >= r) & ((radius < bands[i + 1]) if i + 1 < len(bands) else True)
        if sel.any():
            wide[sel] = masked_blur(convex, cover, r, passes=3)[sel]
    wide = np.clip(wide * 3.0, 0.0, 1.0)
    return convex.astype(np.float32), concave.astype(np.float32), wide.astype(np.float32)
