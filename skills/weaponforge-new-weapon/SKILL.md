---
name: weaponforge-new-weapon
description: Use when asked to create, model, texture, rig, export or import a first-person game weapon (pistol, revolver, rifle, shotgun, SMG or similar) with weaponforge, or to change or re-export one that was built with it. Use it before opening Blender, before writing any Blender script, and before starting an engine import.
---

# New weapon (weaponforge)

A pipeline for this already exists: **weaponforge**, the repo this file is in. You design the weapon and judge it; the pipeline
builds, bakes, rigs, checks and exports it from a definition in Python, and it carries what earlier weapons taught. Do not start
from an empty Blender file and do not write new modelling, baking, export or import scripts.

Every weapon is its own design. Nothing is copied from another weapon: not its parts, not its colours. What carries over is
craft (how to make something well), and that is in `CRAFT.md`.

**Read long files in parts.** A file read in one go can be cut off silently, and you may not notice. `PLAYBOOK.md` (about
1,400 lines) and `weapons/assault_g3/weapon.py` (about 700) must be read in parts, by section or by line range, and checked
that the last part was reached. The README is a short front page; the reference is in `docs/`, one subject per file, each
short enough to read whole (the README's "The reference" lists them).

## The order of work

The same order as the README, `CRAFT.md` and the text `bin/weaponforge new` prints.

1. **Read `CRAFT.md` whole.** It is short. It is what earlier weapons got wrong and what fixed it, put before the step where it
   matters. Reading it first is the difference between a first build worth showing and five hours of rework.
2. **Ask the person.** `CRAFT.md` section 1 has the questions (role, feel, the one thing to remember, how it works, materials
   and condition, what goes on it, how it is seen, what must stay the same as a weapon it replaces, the id, name and tag, which
   side the controls are on). Ask them on every weapon, with concrete options and your recommendation, before anything is
   modelled. Do not guess a style and do not reuse the last weapon's.
3. **Start the weapon:** `bin/weaponforge new <id> <Name> <TAG>`. It copies the template to `weapons/<id>/`. **The template is
   a small pistol.** A long gun replaces `parts.py` and most of `weapon.py`; read `weapons/assault_g3` for how a long gun's rig,
   poses and sockets are set up (`docs/rig.md`), not for its parts.
4. **Write `weapons/<id>/BRIEF.md`:** outline, assemblies, hardware, marks, wear story, what the eye is near.
5. **Show the concept** (`docs/concept.md`): the brief, two or three to-scale side outlines that differ in kind (saved in
   `<asset root>/<id>/ref/`), your recommendation, and what each differs in. **Wait for the person's approval 1.**
6. **Build**, following `docs/building.md`: the outline and assemblies first, then hardware, then the parts near the eye, then
   UVs and texel density, then the look, small machining last. Read `docs/stages.md` ("Costs and order") first: the triangle
   count is measured only after `uv`; any game-mesh change means `uv` again (about 4 minutes), so collect model changes;
   `check` straight after `model` still shows the later stages' old results; and `review --against` needs a kept copy of the
   earlier build's folder, so copy `<asset root>/<id>/` before a round of changes.
7. **Judge each pass by comparing, not scoring.** `bin/weaponforge <id> review --against <the build before>` puts the same crops
   of both builds side by side. Keep a change only if its pair is better; otherwise put it back and write down why. Retries are
   expected.
8. **Record what the weapon taught** (`CRAFT.md` section 6) before calling it done: technique into the shared code, standards
   and mistakes into `CRAFT.md`, the full story into `PLAYBOOK.md`, the design itself nowhere but the weapon's folder.

`PLAYBOOK.md` is the long record, by stage: go to it when something fails or looks wrong. `weapons/assault_g3/` is the worked
example of the standard and its `BRIEF.md` gives the reasoning pass by pass; read it for how, not for what. `weapons/_template/`
is the file set a new weapon starts from.

## Quick reference

**Where to run it.** `bin/weaponforge` finds the repository from its own path, so it works from any folder; the commands below
are written as typed from the repository's root. From another folder, call it by its path. A relative path in an option or
in a `WEAPONFORGE_*` variable is read from the folder you are in. Everything is headless: do not model by hand in an
interactive Blender session (a live Blender is only for looking at a model, `docs/stages.md`, "In a live Blender").

| To | Run |
|---|---|
| see what exists | `bin/weaponforge list` |
| start a weapon | `bin/weaponforge new <id> <Name> <TAG>` |
| start a variant of one (a scope, a suppressor) | a definition that extends the other's: `docs/variants.md` |
| build and look | `bin/weaponforge <id> model render --what grey`, then Read the PNG in `renders/` under the weapon's folder |
| run every check | `bin/weaponforge <id> check` |
| everything, small and fast | `bin/weaponforge <id> all --size 512` |
| pictures as the player sees it | `bin/weaponforge <id> hero --shots fp,ads,beauty` |
| compare with the build before | `bin/weaponforge <id> review --against <folder of the other build>`, then Read `pairs.png` |
| try without touching real files | add `--root <scratch folder>` |
| prove the tool still works | `tests/smoke.sh` |

The stages, their order and every option are in `docs/stages.md`; `bin/weaponforge --help` lists them. Where the weapons' files
go (the asset root) is set up in the README, "Configure".

## Rules that are not negotiable

- **The person approves four things: the concept, the high-detail model, the textures, the look in the engine.** Show the review
  renders and wait at each. Everything else is yours to do without asking.
- **Report check misses as misses**, with the numbers. Never loosen a check to make it pass.
- **The weapon is an original design**: no real maker's name, logo or markings.

## Common mistakes

- Modelling before asking. A weapon built on a guessed style is rework, however good it is.
- Starting from another weapon's parts or look. Each weapon is designed from its own brief.
- One outline with rounded edges and the detail in the normal map. It reads as a CAD blockout (`CRAFT.md`, "Form").
- Scoring a build out of ten. Scores drift between reviewers; pairs of the same crop do not.
- Modelling by hand in an interactive Blender session. The pipeline is headless and the definition is the weapon; a live session
  is only for looking around.
- Tuning the look at 512 px and calling it approved. Wear masks depend on resolution: approve at full size.
- Calling a weapon "done" after `export`. Done is `verify` passing, the engine check (for Unreal, `unreal-check`) ending in
  `RESULT all facts match the spec`, the person having seen it in a game run, and what it taught written down.
- Solving a new problem privately. Put the lesson where the next weapon meets it (`CRAFT.md` section 6).
