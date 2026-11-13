# What the definition says: its hooks

A weapon is a class in `weapon.py` (a subclass of `Weapon` in `weaponforge/weapon.py`) that declares names, budget, rig,
look, collision and checks, and a `params.py` and `parts.py` beside it. Only `builders()` and `surface()` must be written;
everything else has a default. This page is the hooks that have no page of their own: the builders and the kit are in
[kit.md](kit.md), bones, sockets, props, moves and poses in [rig.md](rig.md), the look in [look.md](look.md), the texel layout
and seams in [texels.md](texels.md), review figures in [review.md](review.md).

**Review sheets.** A weapon over three times as long as it is high gets wide tiles in one column, and the angled views on a
sheet of their own (`<sheet>_angles.png`). `closeups = {name: ((x0, y0, z0), (x1, y1, z1))}` adds a sheet framed on that box
(cm, weapon frame) to every kind of render, `<sheet>_<name>.png`: on a metre-long gun the action is a hand's width, and
nothing about it can be judged from the full-length views. A third entry, a list of view names, replaces the default
`left, right, q_rear_r, fp`. `pose_closeup = name` frames the pose sheets on one of those boxes, and `pose_views` says which
two views they show (the side the moving parts are on first, for example `('right', 'q_rear_r')`).

**What can be left out.** `props`, `moves`, `ao_friends`, `density`, `uv_pack`, `texel_zones`, `texel_hidden`, `texel_view`, `player_eyes`, `review`, `review_limits`, `closeups`, `seams`, `brief` with `measure`, `socket_targets`, `checks`,
`collision`, `images`, `hp_kinds` and `spec_extra` all have defaults: a weapon with no magazine and no separate prop mesh
simply has `props = []`. Only `builders()` and `surface()` must be written.

**Budget, LODs.** `budget = (low, high)` triangles for LOD0, `lods = ((1, 0.5), (2, 0.25))` (or `()` for none),
`texture_size` (a power of two).

**The brief.** `brief = {label: (low, high)}` in cm and `measure(parts)` returning the same labels measured on the mesh. The
checks measure meshes, never the numbers in `params.py`: a builder that ignores a parameter is caught.

**Collision.** `collision(static, C)` returns boxes for the world copy; `C.aligned` and `C.pitched` fit one to a set of
points (the template uses two: the upper and the raked grip). The default is one box.

**Extra spec keys.** `spec_extra(game)` adds what the game side wants to read (the template: `dimensions_cm`,
`reload_targets`).
