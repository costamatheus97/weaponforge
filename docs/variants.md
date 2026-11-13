# A variant of a weapon

A weapon that is another one with parts added (a scoped rifle, a pistol with a suppressor) is a definition that **extends**
the other's, so the weapon underneath stays one piece of code and one set of numbers. No shipped weapon is a variant yet.

- `params.py`: `from weapons.<base>.params import *`, then only the numbers the new parts need.
- `parts.py`: only the new builders, then `BUILDERS = dict(base.BUILDERS)` and `BUILDERS.update({...})`. Use the base's
  helpers (its `seg`, `screw_cuts`, `on_bore`) so the two agree on segment counts and detail.
- `weapon.py`: `class Scoped(Base)` with its own `id`, `name` and `tag`. Lists and tables are the base's plus the new rows
  (`bones = Base.bones + [...]`, `closeups = dict(Base.closeups, scope=...)`); hooks call `super()` and add to what it
  returns (`surface`, `checks`, `socket_targets`, `collision`, `spec_extra`, `seams`). End with `WEAPON = Scoped()`.
- `BRIEF.md`: what it adds, and what means something else now.

It is a separate asset from there on: its own folder under the asset root, its own bake and textures, every stage run for
it, its own four approvals. A change to the base's definition reaches the variant the next time the variant is built, so
rebuild both.

When the variant has to **change one of the base's parts** (a suppressed variant's barrel is longer and threaded), do not
copy the base's builder. Give the base a hook with a default that leaves it exactly as it was, and use the hook: an optional
argument on the builder (`barrel(coll, hp, muzzle_x=None, turn=None)`), a class attribute a check reads
(`barrel_end_x`), a method that takes the points (`boxes(pts, C)` under `collision`). Then prove the base did not move: build
it under `--root` and compare the part's triangle counts with the real file's, and, if the base has a kept reference build, compare against it. A regression test against a kept reference build is not
included; `tests/compare_spec.py` and `tests/compare_textures.py` are the tools to write one. The base's real files are never rebuilt for this. A part the game can take off (the suppressor) is not made an
`ao_friend` of what it covers, or the bare barrel carries its shadow. When the part can go on over what is there (a
suppressor that slips over a flash hider), the base needs no hook in its parts at all: the variant only adds a builder, and
the one hook it needs is `boxes(pts, C)`.

When the variant has to **change the base's dimensions** (a sawn-off's muzzle is further back, and with it the rib's
end, the sockets, the checks and the spec), neither of the above works: the base's `params.py` works its derived numbers out
when it is imported, and the base's `parts.py` and `weapon.py` read that one module. Use `weaponforge.variant.rerun`, which
runs one of the base's three files again inside the variant's module of the same name. No shipped weapon uses it yet; the rules, with an
example, are in the docstring of `weaponforge/variant.py`.

- `params.py`: `rerun('<base>', 'params', globals(), MUZZLE_X=45.0, ...)`, then the variant's own numbers. Only names the
  base's file assigns once at its top level can be pinned; a name it does not have stops the run. A value that should stay
  the base's where the two guns are the same metal (the barrel's radius at the cut) is read from the base's module, which
  may be imported for that.
- `parts.py`: `rerun('<base>', 'parts', globals())`, then define the builders that differ and put them into `BUILDERS`
  (and delete the ones the variant has no part for). The base's builders now read the variant's numbers.
- `weapon.py`: `rerun('<base>', 'weapon', globals())` gives the base's class again, built on the variant's numbers: its
  sockets, checks and spec are already right. Subclass it for what a number does not say: `id`, `name`, `tag`, `design`,
  `brief`, `budget`, `closeups`, `ao_friends`, and whatever hook mentions a part the variant no longer has.
- Nothing in the base's folder changes, so there is nothing to prove about the base. Check the variant like a new weapon.

What a variant has to look at, because the new parts change it:

- **A bone for the new parts** (`Scope_Bone`). The game can hide them by scaling it to zero, and a `Prop` on that bone
  writes them out as a static mesh of their own.
- **Sockets whose meaning changes.** With a scope on, `SightFront` and `SightRear` are the ends of the scope's axis, not the
  iron sights. Say so in the socket's meaning, and give `socket_targets` the new places to measure. A number in the spec
  that describes the same thing changes with them (`sight_line_z` is the scope's axis; the irons keep `iron_sight_line_z`).
- **The brief.** A range the new parts move (a scoped variant's height) needs its own numbers.
- **Clearances.** The base's `moves` are tested against the new parts without being asked: a bolt knob that lifts into a new
  eyepiece shows up as a miss. Do that sum on paper before modelling all the same.
- **Collision.** Take the new parts' points out before calling the base's boxes and give them a box of their own.
- **`ao_friends`**: the new builders, and the base builder they sit on.
- **Pictures the base uses** (a wood plank, a painted set): a variant looks in its own `textures/`, not the base's, so
  keep pictures both use in a `_materials/` folder ([examples-and-layout.md](examples-and-layout.md) says where sets are looked for).

A look the surface kinds cannot say is in `PLAYBOOK.md`, "Textures and look" (the scope's glass and its second black).
