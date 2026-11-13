# The stages, options and the spec

What each stage does, writes, takes and costs, the options, and how to try something without touching a weapon's real files.
The commands themselves are listed in the [README](../README.md#commands).

## Costs and order: read this before the first round of changes

Times below were measured at 4096 px on a mid-range GPU. They decide how a round of
work is best ordered.

| Stage or command | At 4096 px | At 1024 px |
|---|---|---|
| `model` | 14 to 18 s | |
| `uv` (tight pack) | about 4 minutes | |
| `bake` | 6.5 to 7 minutes | 37 s |
| `texture` | about 3 minutes | 22 s |
| `rig` | under 1 s | |
| `check` | about 15 s | |
| `export` | about 13 s | |
| `hero`, three shots | about 45 s | |
| `render`, every sheet | about 3.2 minutes (the grey sheets alone: about 6 s) | |
| `review --against` | about 3.5 minutes | |
| `verify` | about 1.5 s | |

From that:

- **The triangle count is measured only after `uv`.** Before it, `check` has a rough count from before the cleanup (the clean-up
  welds, triangulates and removes slivers). Do not judge the budget from a `model` run; run `uv` and read `mesh: triangles`.
- **Every change to the game mesh means `uv` again** (about 4 minutes with the tight pack), and then the bake, the textures and
  the rig after it. Collect model changes and make them together; do not run the chain after each one. A change to the
  high-detail parts only (`model --hp-only`) skips `uv` and goes from `bake` on. A change to the look only is `texture rig
  render`.
- **`check` straight after `model` measures the model only.** The stages that are older than the model (UV, bake, texture,
  rig) are named at the end of the result (`stale, not measured: uv, bake, ... (re-run from "uv")`) and their lines are left
  out of the count, so nothing from the build before the change is reported as a pass or a miss. A stage that is current and
  fails still fails. `export` still refuses a stale chain.
- **Look from the player's eyes before the bake.** `render --what grey` (6 s, straight after `model`) also writes
  `grey_game_parts_eyes.png` and `grey_high_detail_eyes.png`: the grey model from the hip and aiming cameras the hero pictures
  use (`hero.player_eyes`). What the player sees of a form, a control or a mark is decided there, before any stage that costs
  minutes; `--what eyes` makes only those two sheets.
- **`review --against` needs the earlier build's folder to exist.** Copy the whole `<asset root>/<id>/` folder (the `.blend`,
  `bake/`, `textures/`, `export/`) to somewhere else *before* a round of changes that will be shown, or keep a pack made with
  `review --out <folder>`. A copy at another texture size is compared as it is. The tool never keeps an earlier build for you.
- **Iterate at 1024, approve at 4096.** `--size 1024` makes `bake` and `texture` roughly ten times faster, and wear masks depend
  on resolution, so the look is judged at full size ([look.md](look.md)).

## The stages

Each stage works on the weapon's `.blend` and saves it. A stage needs the ones before it, and re-running one makes the later
ones stale: change a part and the UVs, bakes, textures and rig all have to follow (change only the high-detail parts,
`model --hp-only`, and it is the bakes onward). `export` refuses a stale chain, and an incomplete one: a stage that never
ran, parts without UVs, textures that are not on disk.

| Stage | What it does | Writes | Time on the template at 512 px (at 4096 px: "Costs and order", above) |
|---|---|---|---|
| `model` | runs every builder twice: the game parts into `<TAG>_LP`, the bake source into `<TAG>_HP` | the .blend | 1 s |
| `uv` | welds, triangulates, removes the slivers Unreal would drop, sets hard edges and normals, unwraps, packs one sheet | `textures/work/uv_layout.png` | 1 to 35 s (the packer's time varies a lot) |
| `bake` | high detail onto the game parts: normal, occlusion, material ID, then curvature and wear masks. The log lists the texels whose ray found no detail by part, worst first; `bake/preview_missed.png` shows them coloured by part (the legend is in the log) and `bake.json` has them as `missed_by_part` | `bake/` | 8 s |
| `texture` | the weapon's `surface()` over the bakes, baked down to the game's three textures. The log has one `[texture] decal ...` line per decal: its picture found, applied (with its box and the game triangles it reaches), skipped (with the reason), or applied but reaching no face | `textures/T_<Name>_*.png` | 3 s |
| `rig` | pivots on the bones, the armature with its socket joints, the skinned mesh, the world copy, props, LODs | `<TAG>_GAME` in the .blend | seconds |
| `check` | every automatic check, measured on the meshes | a report in the log | seconds |
| `export` | the checks again, the FBX files, the spec | `export/`, the spec `<id>.json` ("The spec", below) | seconds |
| `render` | review sheets: `grey_game_parts`, `grey_high_detail` (each with `_angles` for a long gun, `_<closeup>`, `_pose_<pose>` and `_eyes`: the hip and aiming views), `look_authoring` and `final_views` (each with `_<closeup>`), `final_prop_*`, `pose_*` | `renders/` | 10 s |
| `verify` | reads every FBX back into an empty scene and compares it with the spec: bones, socket joints (place, parent, rotation), sizes, triangle counts, LOD order, one UV map, one material slot, skinning | nothing | seconds |

`all` is every stage in that order. `verify` empties the scene, so it must come last (the command line refuses any other
order).

**`view` is not a stage.** `weaponforge <id> view` runs alone, after `export`: it reads `export/SM_<Name>.fbx` and the three
game textures and writes `<asset root>/_gallery/3d/<Name>.glb`, one file with the textures inside: the game's own PNG
files at their own size, unchanged (20 to 35 MB at 4096 px; `--size N` makes a smaller copy, still without loss). It must
never look worse than the weapon: a copy with half-size JPEG textures looks blurry and granulated where the
game's textures are clean (`tests/check_viewer_copy.py` holds it to them). That is the file to drag into an online 3D viewer or to send to someone: the FBX files carry no
textures (Unreal gets them as separate PNGs), so a viewer shows them grey. It opens and saves no `.blend` and writes nothing
in the weapon's own folder, so it is safe on a weapon that is in use. Unreal never reads the copy.

**`hero` is not a stage either.** `weaponforge <id> hero` runs alone, after `export`, reads the same files as `view` and
writes `<asset root>/_gallery/hero/<Name>.png` (from the front) and `<Name>_rear.png` (from behind and above, near a
player's eye): the exported game mesh with its game textures, under a soft key light on the camera's side of the weapon and a rim
light behind its far side, mirroring an outdoor image, on a plain grey backdrop with a soft shadow under it (2400 x 1500, 160 samples;
`--res WxH`, `--samples N`, `--size N` for the textures). It meters the weapon and exposes a bright one down, so black
steel and stainless steel both come out right under the same lights; the log says by how much. The review sheets are for judging the asset and make a good
weapon look plain; this is the picture to show someone, and the honest one: nothing is in it that the game does not get.
It opens and saves no `.blend` and writes nothing in the weapon's own folder.
`--shots default,beauty,fp,ads,left,right,outline` (any of them, comma separated; without it, `default`: the two above) adds
`<Name>_beauty.png` (the front view on a near-black backdrop with harder light and a kicker under the far side),
`<Name>_fp.png` (from the player's eye at the hip, 60 degrees across, 2400 x 1350), `<Name>_ads.png` (down the sights, from
the `SightRear` and `SightFront` sockets; skipped without them), `<Name>_left.png` and `<Name>_right.png` (straight from each
side, lit as the front picture) and `<Name>_outline.png` (the silhouette from the left, flat grey on near-black, for putting
two builds' outlines side by side). Which end is the front is taken from the weapon's frame (the muzzle is at +X).
`--pose NAME` takes every picture with the weapon in one of its poses (a name from the weapon's `poses`: a bolt held back, a
stock folded) and saves it as `<Name><shot>_pose_<pose>.png`, framed and lit as the rest pose is. It goes with `hero` only and
needs a chain that is complete and not stale.

**`review` is not a stage either.** `weaponforge <id> review [--against DIR] [--critic '<command>']` runs alone, after
`export`, and writes a review pack to `<asset root>/_gallery/review/<Name>/` (or `--out DIR`): the hero shots, a fixed set of
native crops, the figures, a contact sheet; with `--against`, side-by-side pairs with another build. It opens the `.blend`
without saving it and writes nothing in the weapon's folder. See [review.md](review.md).

Options (anywhere after the weapon's id):

| Option | For | Meaning |
|---|---|---|
| `--size N` | bake, texture | texture size in pixels instead of the weapon's `texture_size`. Use 512 or 1024 while iterating. (`view`: the size of the textures in the copy.) |
| `--only a,b` | model | rebuild only these builders |
| `--lp-only`, `--hp-only` | model | only the game parts, or only the bake source |
| `--what grey,look,game,poses,eyes` | render | which sheets (default: all the file has got as far as). `grey` includes `eyes`; `eyes` alone makes only the hip and aiming sheets |
| `--shots a,b`, `--pose NAME` | hero | which pictures, and the pose the weapon is in (above) |
| `--samples N`, `--res WxH` | render | Cycles samples (64) and tile size (1400x900) |
| `--cpu` | bake, texture | no GPU |
| `--strict` | check, export | exit 1 when any check misses |
| `--force` | export | write even when the chain is stale or incomplete (never a deliverable) |
| `--root DIR` | all | another asset root: everything, the spec included, goes under `DIR/<id>/`. For trials and tests. The spec written there names a trial folder in Unreal (`<content>/_Scratch/<Name>`, with the default content folder `/Game/Weapons/_Scratch/<Name>`), so a test copy cannot be imported over the real weapon. |
| `--blend PATH`, `--no-save` | all | another working file; do not save |
| `--against DIR` | review | another build to pair with: a review pack (a folder with `pack.json`) or a build (a folder with `<id>.blend`, or an asset root holding `<id>/`) |
| `--out DIR` | review | where the pack goes (default `<asset root>/_gallery/review/<Name>/`); it must not be the `--against` folder |
| `--critic '<command>'` | review | a judge run on each changed pair, on this side of the launcher, never inside Blender ([review.md](review.md)) |

A path (`--root`, `--blend`, `--against`, `--out`) can be given as the OS gives it. Under WSL with a Windows Blender (`.exe`)
the launcher converts a WSL drive path to the Windows form and leaves a Windows path as it is.

The first line of a run says which `.blend` it opened; every stage prints `[weaponforge] ---- <stage> done in N s`. A failed
stage exits 1 with the Python error above it. `render` prints `wrote <path>` for every sheet: read the path from there, because
a sheet that is open in a viewer cannot be replaced on Windows and is then written beside it as `<name>_new.png`.

## In a live Blender

The pipeline is headless: every stage that makes something runs with `bin/weaponforge`, and bakes and exports belong there.
Do not model a weapon by hand in an interactive Blender session, and do not start the work there: the definition is the weapon,
and a part made by hand is not in the definition, so no stage builds it. An interactive session (Blender's Python console or a script) is only for
looking: turning the model around and trying a call. Open the weapon's `.blend` there and:

    import sys; sys.path.insert(0, '/path/to/weaponforge')
    from weaponforge import stages, weapon
    w = weapon.load('_template', reload=True)       # reload=True re-reads the definition after an edit
    stages.model(w, only=['slide'])
    stages.render(w, what=['grey'])

Never call `stages.verify` there (it empties the scene), and do not leave the file open in the live session while a headless
run is writing it.

## The spec

`<asset root>/<id>/<id>.json` is what everything after Blender reads: the Unreal import and check, other tools,
and people. It is written beside the weapon's files unless the setting `spec_dir` names a folder (then `<spec_dir>/<id>.json`);
under `--root DIR` it is always `DIR/<id>/<id>.json`. It holds the names, bounds, bones, sockets (positions in Unreal's frame), meshes with triangle counts, LODs,
collision boxes, the UV and texture facts, an `unreal` block (asset folder, material, texture settings, which FBX is which),
whatever `spec_extra(game)` added, and the check report. `export` rewrites it but keeps the `status` line, which belongs to
whoever imported or wired the weapon.

**A run without `--root` rewrites the weapon's real files and its spec.** Running `bin/weaponforge <id> export` (without
`--root`) rewrites the FBX files and the spec other tools read. Do that only when a change to that weapon is wanted; to try
something, use `--root`.
