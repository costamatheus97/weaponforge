# Building a weapon, step by step

The order of work in detail: what to run, what to look at, where to stop. `CRAFT.md` is what to know and what to ask first;
the README's [order of work](../README.md#the-order-of-work-for-a-new-weapon) is the short version of this page. What the stages cost is in [stages.md](stages.md): read
that first, because it decides how to group changes. Commands are written as typed from the repository's root (the README,
"Install", says what to do from elsewhere).

The person who asked for the weapon approves four things: **the concept, the high-detail model, the textures, and the final
look in the game**. Everything else is left to whoever builds it. Do not go past an approval without it: each one is cheap to change before
the next stage and expensive after.

The order, and the step numbers other files refer to:

| Step | What | Stops at |
|---|---|---|
| 0 | read `CRAFT.md`, whole | |
| 1 | ask the person; `weaponforge new`; write `BRIEF.md`; show the concept | **approval 1: the concept** |
| 2 | start the definition: `params.py`, `parts.py`, `weapon.py` | |
| 3 | blockout, then detail; the high-detail model | **approval 2: the model** |
| 4 | UVs, bake, textures; the look | **approval 3: the textures** |
| 5 | checks and export | |
| 6 | into Unreal (optional) | |
| 7 | into the game | **approval 4: the look in the game** |

**0. Read `CRAFT.md`, whole.** It is short: what earlier weapons got wrong and what fixed it, put before the step where it
matters, and the questions to ask. Every weapon is its own design; what carries over from one to the next is craft, not parts.

**1. Ask, start the weapon, write the brief, show the concept.** In this order, on every weapon:

1. **Ask the person** `CRAFT.md`'s questions (section 1: role, feel, the one thing to remember, how it works, materials and
   condition, what goes on it, how it is seen, what must stay the same as a weapon it replaces, the id, name and tag, which
   side the controls are on and which marks must be readable at the hip). Nothing is modelled, and nothing is written down
   as a decision, before the answers are in.
2. **Start the weapon:** `bin/weaponforge new <id> <Name> <TAG>` (for example `new shotgun_g1 ShotgunG1 SG1`). It copies
   `weapons/_template/` to `weapons/<id>/` and renames what has to be renamed, and it refuses an id, a name or a tag that
   anything already uses (a definition, an asset folder, a spec, an Unreal folder), so a clash is found now, before the person
   has seen anything. It is `new` that makes the folder the brief lives in; that is why it comes before the brief.

   **The template is a pistol.** `weapons/_template` is a small blocky pistol (a slide, a frame, a raked magazine), made to
   show every hook of a definition. A pistol is edited from it. A long gun (a rifle, a shotgun, a submachine gun) **replaces
   `parts.py` and most of `weapon.py`**: its parts, bones, sockets, props, what moves, poses, budget and look are not the
   pistol's, and only the layout of the three files and `params.py`'s habit of deriving every number from a few datums carry
   over. For how a long gun's rig, poses and sockets are set up, read `weapons/assault_g3/weapon.py` (a long file: read it
   in parts; [rig.md](rig.md) says what to look for) and its `BRIEF.md`. Read it for how, not for what: its parts are its own
   design and are not yours.
3. **Write `weapons/<id>/BRIEF.md`**: what the weapon is, in words and centimetres: the outline, the assemblies it is made of,
   its hardware, marks and wear story, its overall size, what moves (slide, bolt, magazine, trigger, ...), what the game
   needs to find on it (sockets), and the triangle and texture budget. A first-person weapon here is 15,000 to 30,000
   triangles at LOD0 with one 4096 px texture set. The weapon is its own design: no real maker's name, logo or markings.
4. **Show the concept**: the brief, two or three to-scale side outlines that differ in kind, a recommendation, and what each
   differs in, as defined in [concept.md](concept.md). The pictures go in `<asset root>/<id>/ref/`. **Approval 1: the
   concept.**

**2. Write the definition.** The three files are the whole weapon (the template's `weapon.py` has every block commented, and
the base class in `weaponforge/weapon.py` has a default for each hook except `builders()` and `surface()`):

- `params.py`: every dimension, in centimetres, pure Python. Fix the datums first (bore height, muzzle, grip), derive the rest
  from them.
- `parts.py`: one builder per part. `fn(coll, hp=False)` leaves its mesh object(s) in `coll`, each tagged with
  `K.tag(obj, bone, mat=kind)`, and deletes every helper. The same code makes the game part and, with `hp=True`, the bake
  source: more segments, plus the small cuts (grooves, pins, markings) the game mesh only gets through its normal map.
- `weapon.py`: names, budget, bones, sockets, the magazine or other props, what moves, poses, the look, collision, checks.
  Every block in the template's file is commented; the base class in `weaponforge/weapon.py` has a default for each hook
  except `builders()` and `surface()`. The new file starts with a first-person weapon's numbers (`texture_size = 4096`,
  `budget = (15000, 30000)`), marked TODO: set them for your weapon. Until the real parts exist the copied blocks have a few
  hundred triangles, so `mesh: triangles` misses; that is the check doing its job, not something to tune away. A typo in the
  file (a parent bone that does not exist, a socket on a missing bone, a pose for a bone that is not there) stops the first
  stage with a list of everything wrong.

The frame, everywhere: origin in the grip, **+X toward the muzzle, +Z up, +Y the weapon's LEFT** (Blender's view of the game's
weapon frame; Unreal reads `(x, -y, z)`, so the right-hand side is `-Y` here). One Blender unit is one centimetre.

The hooks are described in [definition.md](definition.md), the kit builders in [kit.md](kit.md), the rig in [rig.md](rig.md).

**3. Blockout, then detail.** Iterate on the game parts first; it takes seconds:

    bin/weaponforge shotgun_g1 model render --what grey --lp-only
    bin/weaponforge shotgun_g1 check

Look at `renders/grey_game_parts.png` (under the weapon's folder in the asset root; Read the PNG), and at `grey_game_parts_pose_<pose>.png`:
the parts in each of the weapon's poses, which needs no rig, so the action is seen open from the first blockout. A long gun
also gets `grey_game_parts_angles.png`, and every box in `closeups` its own sheet ([definition.md](definition.md), "Review
sheets"). From the first `model` on, `check` measures the brief, the frame, the travel of every moving part and the sockets.
What needs a later stage is printed as `--` and "not measured yet" (the triangle count, closed meshes and UVs after `uv`;
pivots and the rig after `rig`) and is not counted. When the silhouette and the moving parts are right, add the `hp=True`
detail and render both (`--what grey`). **Approval 2: the model**, shown as `grey_game_parts.png` and `grey_high_detail.png`
(add close-ups of anything that was argued about).

Bring LOD0 into the budget with the one dial in `parts.py`, `LP_Q`, which scales every game-resolution segment count. The
triangle count is only measured after `uv`, so read it there, and collect game-mesh changes before running `uv` again
([stages.md](stages.md), "Costs and order").

**4. UVs, bake, textures.** At low resolution until it looks right, then once at full size:

    bin/weaponforge shotgun_g1 uv bake texture rig render --size 1024
    bin/weaponforge shotgun_g1 bake texture rig check export render verify      # full size, when it is right

The look is `surface()` in `weapon.py`: see [look.md](look.md) for the surface kinds, the steel finish and the timber, the
named finishes, wear that follows use, lettering filled with paint, and painted texture sets and decals. The texel layout
is in [texels.md](texels.md).

**Look at the note `check` prints about bare faces.** After a bake, `check` ends its mesh and UV lines with
`note look: bare faces`: the flat steel or polymer faces that have more than 12 cm2 with nothing modelled within 1 cm
(covered faces, curved faces and wood are left out). It is not a check and never a miss; it is the to-do list of the
detail pass. Big plain faces are the main thing that makes a weapon read as a block, and detail there goes into the
detail model only, so it costs no triangles (PLAYBOOK "Modelling" item 64).

**Make the presentation pictures before showing a weapon:** `weaponforge <id> hero`, after `export`. The review sheets
are flat and dark on purpose; the hero pictures are what the weapon looks like well lit, and they are of the exported
game mesh and textures, so they do not flatter (item 14).
**Approval 3: the textures**, shown as `final_views.png`, the prop sheet, the pose sheets and the two hero pictures.

**5. Checks and export.** `export` prints every check as `ok` or `MISS`, then writes the FBX files and the spec. A miss does
not stop the export; it is for you to fix or to report plainly. `verify` then proves the files on disk say what the spec says. Never call a
weapon exported without `verify` passing. Then record where every picture and texture that went into the weapon came from, with its licence.

**6. Into Unreal.** This is the optional adapter: `unreal-import` and `unreal-check`, what they make and the rules that keep an
import in its own folder are in [unreal.md](unreal.md). Both are headless: they prove names, counts, sizes and settings, not the look.

**7. Into the game.** Pointing the game at the new meshes is code and data work outside this tool, and it has its own list of
things that bite: `PLAYBOOK.md`, "Putting the weapon into the game". Until that is done and the person has seen it in a game
run, the old weapon's asset paths stay as they are. **Approval 4: the look in the game.**
