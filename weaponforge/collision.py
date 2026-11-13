"""weaponforge: simple collision for the world copy, as a few boxes fitted to the mesh.

A box is {'name', 'centre' (Vector, weapon frame), 'size' (Vector, along the box's own X, Y, Z), 'pitch_deg'}. pitch is Unreal's:
positive lifts the box's +X toward +Z (a grip raked 15 degrees back is pitch -15, so the box's Z runs up the grip).

The Unreal import builds them with GeometryScript, since a commandlet has no StaticMeshEditorSubsystem (PLAYBOOK.md, "Unreal import").
"""
import math

from mathutils import Vector


def points(obj):
    return [obj.matrix_world @ v.co for v in obj.data.vertices]


def axes(pitch_deg):
    """The box's X and Z axes in the weapon frame (its Y is the weapon's)."""
    p = math.radians(pitch_deg)
    return Vector((math.cos(p), 0.0, math.sin(p))), Vector((-math.sin(p), 0.0, math.cos(p)))


def aligned(name, pts, z_max=None, z_min=None):
    """The axis-aligned box around pts (z_max / z_min: cut it off there instead)."""
    if not pts:
        raise ValueError('collision box %s: no points' % name)
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts) if z_min is None else z_min))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts) if z_max is None else z_max))
    return {'name': name, 'centre': (lo + hi) / 2, 'size': hi - lo, 'pitch_deg': 0.0}


def pitched(name, pts, pitch_deg):
    """The tightest box around pts whose X axis is pitched by pitch_deg."""
    if not pts:
        raise ValueError('collision box %s: no points' % name)
    ex, ez = axes(pitch_deg)
    xs, ys, zs = [p.dot(ex) for p in pts], [p.y for p in pts], [p.dot(ez) for p in pts]
    mid = [(min(v) + max(v)) / 2 for v in (xs, ys, zs)]
    centre = ex * mid[0] + Vector((0.0, mid[1], 0.0)) + ez * mid[2]
    return {'name': name, 'centre': centre, 'size': Vector((max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))), 'pitch_deg': pitch_deg}


def box(name, centre, size, pitch_deg=0.0):
    return {'name': name, 'centre': Vector(centre), 'size': Vector(size), 'pitch_deg': pitch_deg}


def outside(p, b):
    """How far p is outside box b (0 inside)."""
    d = p - b['centre']
    if b['pitch_deg']:
        ex, ez = axes(b['pitch_deg'])
        d = Vector((d.dot(ex), d.y, d.dot(ez)))
    return math.sqrt(sum(max(0.0, abs(d[i]) - b['size'][i] / 2) ** 2 for i in range(3)))


def report(boxes, pts, slack=0.2):
    """The boxes in Unreal's frame for the spec, with how well they fit: 'cover' is the share of the mesh's vertices inside a box
    (2 mm slack), 'largest_gap_cm' how far the farthest vertex is from the nearest box."""
    if not boxes:                  # a weapon may have none (Weapon.collision returns []): the import then clears the collision
        return {'boxes': [], 'cover': 0.0, 'largest_gap_cm': None}
    gaps = [min(outside(p, b) for b in boxes) for p in pts]
    return {'boxes': [{'name': b['name'], 'centre_ue': [round(b['centre'].x, 4) + 0.0, round(-b['centre'].y, 4) + 0.0, round(b['centre'].z, 4) + 0.0],
                       'size_cm': [round(v, 4) for v in b['size']], 'pitch_deg': b['pitch_deg']} for b in boxes],
            'cover': round(sum(1 for g in gaps if g <= slack) / len(gaps), 4), 'largest_gap_cm': round(max(gaps), 3)}
