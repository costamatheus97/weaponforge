# What the tool does not prove, tests, and what is not known to work

## What the tool does not prove

- **Anything rendered in Unreal.** The import and check are headless. The textures have only been seen in Blender's renders,
  and the Unreal adapter is untested since extraction. The normal map is written OpenGL-style and flipped at import; if a weapon's bevels look inverted in the engine, that flag is the first suspect.
- **How the weapon sits in the hands, the sights, the reload.** That is the game side.
- **Taste.** The checks say the mesh is closed, in budget, in its brief and collision-free when it moves. They do not say it
  looks good; the review sheets and the four approvals do.

## Changing the tool

    tests/smoke.sh                  the template through every stage; then `export` must refuse a stale chain and an
                                    incomplete one; then the guards: another rig in the file, a definition's typos, the
                                    Unreal arguments (about 4 min)
    tests/kit_builders.sh           the shared builders on a weapon defined from scratch in tests/kit_builders.py (about a minute)
    tests/finishes.sh               the named finishes on a small template bake (under 2 min)
    tests/review.sh                 the review: the figures on a synthetic case, the critic with a stub judge, review and
                                    review_limits in a definition, the launcher's paths (10 s): run after touching review.py,
                                    critic.py, hero.py or bin/weaponforge
    python3 tests/test_definition.py     what a weapon definition may say, without Blender
    python3 tests/test_unreal_args.py    the rules that keep an Unreal import in its own folder (no Unreal needed): run after
                                         touching integrations/unreal/weapon_*.py
    python3 tests/check_viewer_copy.py <the .glb> <the weapon's textures folder> <Name>
                                    the viewer copy's textures are the game's own

Run them after any change under `weaponforge/` or `weapons/`. A regression test against a kept reference build is not
included; `tests/compare_spec.py` and `tests/compare_textures.py` are the tools to write one. After a change to the two Unreal
scripts, also do a trial import of the template ([unreal.md](unreal.md): `--root`, then `run.sh import --spec ...`) and read the check's result: nothing else exercises them.
The shell tests write only under a scratch root (`build/_test`, or `WEAPONFORGE_TEST_ROOT`) and delete it
when they pass. Put what a second weapon needs into the shared code when it is general (a new surface recipe, a new check) and
into the weapon's own folder when it is not; then add the wall you hit, and the way past it, to `PLAYBOOK.md`, and the lesson
in a line or two to `CRAFT.md` at the step where the next weapon will meet it (`CRAFT.md`, section 6).

## Not known to work

- **The Unreal adapter**, since extraction (above). Paths with spaces in them inside the `-script="..."` string have never
  been tried.
- **macOS.** The launcher, the tests and the runner avoid GNU-only options where they can, but nothing has been run on a Mac
  (Blender's Metal backend is in the device list, untried). `tests/*.sh` use `find -printf` and are Linux-only.
- **Native Windows** (without WSL): `bin/weaponforge` is bash. Git Bash or MSYS2 may run it; untried. Blender can always be
  started by hand: `blender -b --factory-startup --python-exit-code 1 --python weaponforge/cli.py -- <id> <stage> ...`.
- **A WSL-only repository or asset root with a Windows Blender** (`\\wsl.localhost\...`): untested.
- **Regenerated painted sets** come out different from the ones the pictures in the README were made with ([examples-and-layout.md](examples-and-layout.md)).
- **Anything rendered in Unreal**, and how the weapon sits in the hands: see "What the tool does not prove", above.
