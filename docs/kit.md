# The kit: builders and what is shared

What the modelling helpers are, and what the shared builders are and are not. A weapon is its own design; the kit is
technique. `PLAYBOOK.md`, "Modelling", is the record of why each helper is the way it is.

## Builders and the kit

**Builders.** Register them in `builders()` as `{name: fn}`. A builder may leave several parts (the template's `sights`); each
needs its own object name and tag. `K.tag(obj, bone, mat='steel')` says which bone moves the part and what it is made of. A
part that moves on its own in the game is its own part on its own bone. A part made of two materials sets its faces'
`material_index` and names both kinds in the `hp_kinds()` hook (a cartridge: brass case, copper bullet).
`weaponforge/kit.py` is the toolbox (`from weaponforge import kit as K`):

| Call | Makes |
|---|---|
| `K.round_poly(pts, seg90=6)` | a 2D outline with filleted corners: `pts` is `[(a, b)]` or `[(a, b, radius)]`, `seg90` segments per quarter turn |
| `K.prism(name, pts, plane, lo, hi, coll)` | the outline extruded: `plane` is `'XZ'`, `'YZ'` or `'XY'`, from `lo` to `hi` along the third axis |
| `K.prism_m(name, pts, matrix, lo, hi, coll)` | the same in a local frame (outline in local XY, extruded along local Z), placed by `matrix`: for anything raked |
| `K.box(name, lo, hi, coll)` | a box between two corners |
| `K.cylinder(name, p0, p1, r, seg, coll, r1=None)` | a capped cylinder between two points (`r1`: a cone) |
| `K.tube(name, p0, p1, r_out, r_in, seg, coll)` | a pipe wall between two points |
| `K.lathe(name, profile, origin, axis, seg, coll)` | `[(along, radius)]` spun about `axis` through `origin`. `start=(0, 0, -1)` (also on `cylinder` and `tube`) puts a line of vertices underneath: the part is then the same on both sides and has edges for a UV seam |
| `K.text_solid(name, text, size, origin, x_dir, up_dir, depth, coll, wide=1.0)` | extruded lettering, as a cutter for markings. `wide=1.6` makes an extended face (the letters and their spacing wider along the line, height and depth unchanged): a mark on a side wall is seen from the hip at about 10 degrees, so it is short of width along the gun, not of height |
| `K.boolean(target, cutters, op='DIFFERENCE')` | cuts (`'UNION'`, `'INTERSECT'` also) and deletes the cutters. If the solid vanishes or comes back with open edges it redoes the cuts that went wrong with the other solver and says so in the log, with the usual causes; when a cutter face lies in the plane of a face of the target it names the cut and both faces |
| `K.hatch(outline, angle_deg, pitch, islands=())` | parallel lines across a closed 2D outline, cut off at it: two calls at `+a` and `-a` are a checkering's two line sets. `islands=[((a, b), radius)]` leaves round flats in the field, for a screw head |
| `K.grooves_on(obj, lines, frame, coll)` | one cutter of V grooves that follow `obj`'s surface along 2D lines drawn in `frame`'s plane: checkering on a curved stock, a border round it |
| `K.cut_grooves(target, cutters, coll)` | cuts `grooves_on` cutters (ones that do not cross each other) and then looks for every groove in the result; stops if any stretch was left uncut. Always this for grooves, never `K.boolean` |
| `K.loft(name, rings, coll)` | a closed solid skinned over rings of 3D points (same count in each; a one-point ring is a tip): stocks, grips, anything organic |
| `K.section(hw, lo, hi, n, widest=0.5, top=2.0, bottom=2.0)` | one ring for a loft: an oval `2*hw` wide from `lo` to `hi`, exponent 2 round, higher squarer, set apart for the top and bottom halves |
| `K.span(outline, a)` | `(lowest, highest)` where a closed 2D outline crosses `a`: the height of a loft's ring at that station (also at the outline's very ends) |
| `K.curve([(x, y), ...])` | a smooth function through the points that never overshoots them: widths and squareness along a loft |
| `K.stations(marks, lo, hi, max_gap, min_gap)` | where a loft's rings go: at every mark, with long gaps divided evenly |
| `K.bevel(obj, pred, width, seg=2, clamp=True)` | bevels the edges `pred(edge, mid, direction)` picks. Prints a `[kit] bevel:` note when Blender's overlap clamp shrank it; `clamp=False` turns the clamp off (only where the bevel ends on a wall or a stop edge) |
| `K.fillet_cutter(name, stations, coll, seg=3)` | a cutter that rounds the corner between two faces along a path, for `K.boolean`: cannot be clamped, may change radius, may run out through an end face or fade to nothing. For a rounding that ends part-way along an edge (a grip strap), where a bevel tears |
| `K.edge_stations(path, y, radius, solid, fade_in=0, fade_out=0)` | the stations for `fillet_cutter` along the edge an `'XZ'` prism's outline makes with its side at `y`; `path` is that stretch of the outline, `solid` the side of travel the part lies on |
| `K.in_plane(point, normal)` | such a `pred`: the edges lying in that plane (`K.in_plane((0, 0, 0), (0, 1, 0))` is the weapon's centre plane) |
| `K.cleanup(obj, dissolve_deg=0.5, keep=None)` | welds and merges the coplanar faces booleans leave; `keep=pred` protects edges a UV seam will follow |
| `K.mend(obj, sides=8)` | closes the pinholes a fine cut plus `cleanup` can leave in a bake source and deletes stray edges; prints a `[kit] mend:` note when it did anything (`stocks.checker` calls it) |
| `K.mirror_y(obj, name, coll)` | a copy on the weapon's other side |
| `K.transform(obj, matrix)`, `K.join(name, objs, coll)`, `K.copy(obj, name, coll)` | move, merge, duplicate |
| `K.rot_y(pivot_xz, degrees)` | a matrix: rotation about the lateral axis through `(x, z)`. **Positive tips +Z toward -X** (a hammer cocking back) |
| `K.shade(obj, angle=30, flats=False)` | smooth shading with hard edges over `angle` degrees: last, just before the tag. `flats=True` on a bake source with large flat walls keeps them from shading in streaks |
| `K.tag(obj, bone, mat='steel')` | which bone carries the part and what it is made of |

**Sign of `K.rot_y` and of a pose's `rot`.** They are opposite: `K.rot_y` turns positive toward -X for +Z, a pose's `rot`
follows the right-hand rule. [rig.md](rig.md), "Sign conventions", has an example with both.

Three rules keep the meshes clean, and each was learned the hard way (`PLAYBOOK.md`, "Modelling"):

- big rounded shapes are real geometry; the fine edge break comes from the bake, not from more triangles
- a cutter's face never lies in a face of its target, and two parts are never modelled into the same surface: offset 0.02 cm
- one closed solid per part

## Organic parts

A stock is a loft: draw its side outline with `K.round_poly`, read each ring's bottom and top from it with
`K.span`, take the half-width and the squareness of the top and bottom from `(x, value)` tables through `K.curve`, make the
rings with `K.section` at `K.stations(...)`, and skin them with `K.loft`. Then cut the inlets (barrel channel, action,
magazine well) out of it. A part of another material that continues the shape (a recoil pad, a grip cap) is an `INTERSECT`
slice of the same solid, and the wood loses the same slab. AssaultG3's grip, in `weapons/assault_g3/parts.py`, is built with `K.span`,
`K.curve` and `K.stations`. `weaponforge/stocks.py` does the pad, the cap and the checkering for any stock whose `params.py`
has the names its header lists; no shipped weapon uses it yet. A second wooden part on the stock, a band round both and a
curved magazine: `PLAYBOOK.md`, "Modelling", items 22 and 23.

## Shared builders: what they are, and what they are not

**Technique, for any design.** `weaponforge/sections.py` and `forms.py` (a faceted section and the loft, pocket and boss built
on it, marks placed on a surface by a ray) and `weaponforge/fittings.py` (screws, pins, rivets, a data plate, a sling loop,
selector and moulding marks, the hardware every real object has) are parametrised builders that a design of any shape can use.
The template uses the loft and the fittings.

**One weapon's designs, with their sizes as arguments.** `weapons/assault_g3/sights.py` and `weapons/assault_g3/barrels.py`
are AssaultG3's own files, not part of the shared package: an example of how a weapon keeps its designs in its folder. Each
builds one fixed form:

- `sights.py`: a rear aperture sight clamped to a rail (a base with a clamp bar and a cross-bolt each side, two wings, a
  pivoting aperture arm with two apertures, a windage screw and knob, an elevation scale) and a front post sight on the
  same clamp. Every dimension is an argument; every default is AssaultG3's proportion; the form is not an argument.
- `barrels.py`: a barrel nut with notches (castellated), a gas block with a two-position regulator and cross pins, and a
  slotted flash hider with a recessed crown, on the bore line.

Another weapon may copy them as a starting point for a brief that asks for that design (a rifle with a rail and clamped iron
sights). **A brief that asks for any other sight or muzzle device is not served by them**: a leaf, a tangent or a hooded post
fixed to the barrel, a suppressor, a different hider are designed in the weapon's own folder, as SmgG2 does (it uses neither
module). Called with their defaults they give AssaultG3's sights and AssaultG3's barrel furniture, and two weapons built that
way share a design, which `CRAFT.md` says must not happen.

**Method, not yet proven here.** `weaponforge/stocks.py` is the shared way to finish a wooden long-gun stock: a recoil pad,
a grip cap and checkering, cut as slices of one lofted solid. It reads fixed names from the weapon's `params.py` (its header
lists them). It is general (it fixes no outline), but no shipped weapon uses it and `tests/kit_builders.sh` does not build it;
it was used on weapons that are not in this repository (`PLAYBOOK.md`, "Modelling"). Expect to debug it on the first wooden
stock.

`tests/kit_builders.sh` (it runs `tests/kit_builders.py`) builds a small rifle from the loft and the fittings, with AssaultG3's
sights and barrel builders (imported from `weapons/assault_g3/`) on it, with their defaults. Where a builder takes `seg`, it is
the weapon's segment dial bound to `hp` (`lambda lo, hi: seg(hp, lo, hi)`). Whole parts come back untagged and unshaded: the weapon tags and shades them. The calls:

- `weaponforge/sections.py` (`S`, plain Python, for `params.py`): a faceted section. `S.lin(points)` a width or height in
  ramps; `S.knots(*tables)` where those ramps need rings; `S.facet_ring(corners, lo, top, k=2)` the ring from the left
  half's sharp corners `[(y, z, radius)]`; `S.facet_y(corners, lo, top, z)` how far out the surface is at height z;
  `S.rrect(hw, lo, hi, r, k)` a rounded rectangle of fixed count; `S.boss_top(surface_y, x, z, r, h)`; `S.rect`,
  `S.densify`, `S.hex_pts`, `S.disc_pts`.
- `weaponforge/forms.py` (`FM`): `FM.section_loft(name, side, section, coll, x0, x1, max_gap, min_gap, knots=(), must=(),
  warp=None)` a body skinned over `section(x, lo, hi)` at the stations of its side outline (it prints `[kit] warning` for a
  four-sided facet between two rings whose corners are more than `twist_tol`, 0.03 cm, from one plane, naming the facet, its
  place, the rings and the amount: a later boolean may turn such a facet's diagonal; make its two edges parallel or accept
  it); `FM.pocket(surface_y, outline,
  side, depth, inset, coll)` a sunk panel open to the outside; `FM.boss(surface_y, x, z, r, h, side, coll, seg)`;
  `FM.slab(quad, normal, depth, coll)`; and what places a mark on a surface: `FM.hit(body, origin, direction)`,
  `FM.surface_frame(loc, nrm, up)`, `FM.engrave(pts, frame, depth, coll, ink=None)`, `FM.ring_cut(frame, r, w, depth, coll)`.
  On the bore: `FM.about_bore(deg, bz)`, `FM.turned(obj, deg, centre)`, `FM.bore_seam(bz)`.
- `weaponforge/fittings.py` (`F`), besides `screw_cuts`, `pin_cuts` and `stud`: placed by a ray (`F.side_ray(x, z, side)`,
  or any other origin and direction), each `[]` on a miss: `F.fastener(body, origin, direction, coll, groove=(0.34, 0.27),
  hex_r=0.17, up=(0, 0, 1))`, `F.witness`, `F.date_clock`, `F.qd_cup_marks`, `F.parting_line(body, x0, x1, top, coll)`,
  and the marks `F.safe_mark` (ink 0), `F.fire_mark` (ink 1), `F.lock_mark`, `F.arrow_mark`. Hardware to `K.join` into a
  part: `F.takedown_pin(x, z, face, coll, seg, side=1.0)`, `F.pin_head`, `F.rivet(base, axis, coll, seg_n, r=0.11)` (`r` is the
  head's radius, the head a scaled copy: 0.11 cm is about a pixel and a half on a 1024 sheet, 0.16 to 0.20 reads from the
  hip), `F.data_plate(x0, x1, z0, z1, floor, coll, seg, side=1.0, rivet_r=0.11)` (it returns the plate, its rivets and its
  face; join the rivets after the plate's cuts),
  `F.sling_loop(x0, x1, z0, z1, coll, seg)`. Cutters: `F.plate_recess`, `F.plate_text(face, text, coll, wide=1.0)`, `F.qd_cup`,
  `F.takedown_pin_cuts`.
- `weapons/assault_g3/sights.py` (`SI`, AssaultG3's own), for a rail: `SI.Mount(rail_z, rail_hw, base_hw, jaw_z, seat)`;
  `SI.front_post(name, x0, x1, coll, seg, hp, mount, sight_z, ...)` and `SI.rear_aperture(name, x0, x1, coll, seg, hp,
  mount, sight_z, ...)`, every other dimension defaulted from those. The aperture's countersunk rim gets 10 x LP_Q sides in
  the game mesh, the serrations stop at a flat land round the apertures, and the countersinks are cut once more last.
- `weapons/assault_g3/barrels.py` (`BR`, AssaultG3's own), on the bore line `y = 0, z = bz`: `BR.gas_ring(x0, x1, r)` four points for the barrel's
  lathe profile; `BR.gas_block(obj, x0, x1, r, bz, coll, seg)` the regulator, flats and cross pins on it, and its bake-source
  cuts as lists (`BR.gas_block_cuts`, or one by one to put the barrel's own between them);
  `BR.castellate(obj, x1, r, bz, coll, count=8)`; `BR.flash_hider(name, x0, x1, bz, coll, seg, hp, r=1.08, ...)`.

**Measuring in a weapon's `checks()`.** Ask the solid, not its vertices: a check that picks vertices by position breaks
the day the part is built another way. `weaponforge/check.py` (`CHK`) has `CHK.ray(part, origin, direction)` (the first skin a
ray meets: distance, point, normal), `CHK.reach(part, point)` (how far the skin is in each of six directions, met from inside,
or None), `CHK.inside(part, point, within=None)` (the point is inside the closed solid, and optionally within so many cm of
its skin every way), `CHK.pieces(part)` and `CHK.piece_bounds(part, near)` (the bounds of the connected piece nearest a point:
a button on a plate) and `CHK.parts_bounds(c.by_name, 'A', 'B')` (the bounds of named parts, with a clear error for a name
that is not there). SmgG2's "origin in the grip" check was the first use (SmgG2 is not in this repository).

What stays a weapon's own: its section's corners and tables, its composition (which cuts, in what order), and anything only
that gun has.

**Parts that swing or turn about the bore's direction** (a revolving cylinder and its crane): no shipped weapon does this; the clearances
are worked out in `PLAYBOOK.md`, "Modelling", item 27.
