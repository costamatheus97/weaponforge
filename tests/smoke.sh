#!/usr/bin/env bash
# The whole pipeline on the template weapon, from an empty file, in about a minute and a half:
#
#   tests/smoke.sh            model, uv, bake, texture, rig, check, export, render, verify at 512 px, every check must pass;
#                             the viewer copy (`view`) and the presentation pictures (`hero`) of what was exported, which
#                             must leave the weapon's own files alone;
#                             then the rules that stop a bad export: rebuild the parts and `export` must refuse (stale), leave
#                             the bake and the textures out and it must refuse (incomplete); then the guards
#                             (tests/guards_blender.py, test_definition.py, test_unreal_args.py)
#   KEEP=1 tests/smoke.sh     leave the files for a look (the folder is printed)
#
# Everything is written under a scratch asset root ($WEAPONFORGE_TEST_ROOT, default build/_test in the repository), the spec
# included: no weapon's real files and nothing in Unreal is touched. With a Windows Blender run from WSL the root has to be a path
# that Blender can reach (a drive under /mnt/), not a WSL-only one such as /tmp.
set -uo pipefail

. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
WF="$TOOL/bin/weaponforge"
ROOT="$TEST_ROOT/smoke_$$"
OUT="$ROOT/_template"
LOG="$ROOT/smoke.log"
mkdir -p "$ROOT"
fail() { echo "smoke: FAIL: $*"; echo "smoke: log $LOG, files $ROOT"; exit 1; }
finish() { if [ "${KEEP:-0}" = 1 ]; then echo "smoke: kept $ROOT"; else rm -rf "$ROOT"; fi; }

echo "smoke: the template through every stage (log: $LOG)"
"$WF" _template all --root "$ROOT" --size 512 --strict >"$LOG" 2>&1; rc=$?
[ $rc -eq 0 ] || { grep -a "weaponforge\] *MISS\|Error\|FAILED" "$LOG" | tail -20; fail "the pipeline exited $rc"; }
grep -a "\[weaponforge\] .*checks\|verify" "$LOG" | tail -4
grep -a "\[bake\] lettering: " "$LOG" | tail -1
[ -s "$OUT/bake/marks.npy" ] || fail "the bake kept no lettering mask (bake/marks.npy) for the template's engraved text"
grep -a "note look: bare faces" "$LOG" | tail -1 | cut -c1-200
grep -aq "note look: bare faces" "$LOG" || fail "check did not print its note about bare faces"
grep -a "note look: bare faces" "$LOG" | grep -aq "could not be measured" && fail "the note about bare faces could not be measured"
for f in _template.blend _template.json export/SKM_TemplateGun.fbx export/SKM_TemplateGun_LOD1.fbx export/SM_TemplateGun.fbx export/SM_TemplateGun_Mag.fbx \
         textures/T_TemplateGun_BC.png textures/T_TemplateGun_N.png textures/T_TemplateGun_ORM.png textures/work/uv_layout.png \
         renders/grey_game_parts.png renders/grey_game_parts_eyes.png renders/grey_high_detail_eyes.png renders/look_authoring.png renders/final_views.png renders/pose_reload.png; do
    [ -s "$OUT/$f" ] || fail "missing $f"
done
python3 - "$OUT/_template.json" <<'EOF' || fail "the spec is not what the Unreal scripts need"
import json, sys
spec = json.load(open(sys.argv[1], encoding='utf-8'))
u = spec['unreal']
assert u['skeletal']['name'] == 'SKM_TemplateGun' and len(u['skeletal']['lods']) == 2, u['skeletal']
assert [s['name'] for s in u['statics']] == ['SM_TemplateGun', 'SM_TemplateGun_Mag'], u['statics']
assert len(u['textures']) == 3 and len(spec['sockets']) == 3 and len(spec['bones']) == 6
missed = [c['check'] for c in spec['checks'] if not c['ok']]
assert not missed, missed
print('smoke: spec ok (%d checks, %d sockets, LOD0 %d triangles)' % (len(spec['checks']), len(spec['sockets']), spec['meshes']['SKM_TemplateGun']['triangles']))
EOF

echo "smoke: the viewer copy"
before="$(cd "$OUT" && find . -type f -printf '%p %s %T@\n' | sort)"
"$WF" _template view --root "$ROOT" >"$ROOT/view.log" 2>&1; rc=$?
[ $rc -eq 0 ] || { tail -5 "$ROOT/view.log"; fail "view exited $rc"; }
[ -s "$ROOT/_gallery/3d/TemplateGun.glb" ] || fail "view wrote no _gallery/3d/TemplateGun.glb"
[ "$(head -c 4 "$ROOT/_gallery/3d/TemplateGun.glb")" = "glTF" ] || fail "the viewer copy is not a .glb"
python3 "$(dirname "$0")/check_viewer_copy.py" "$ROOT/_gallery/3d/TemplateGun.glb" "$OUT/textures" TemplateGun \
    || fail "the viewer copy does not carry the game textures unchanged (smaller or lossy textures blur it and grain the lettering)"
[ "$before" = "$(cd "$OUT" && find . -type f -printf '%p %s %T@\n' | sort)" ] || fail "view changed the weapon's own files"
if "$WF" _template view render --root "$ROOT" >"$ROOT/view2.log" 2>&1; then fail "view ran together with a stage"; fi
grep -a "\[weaponforge\] view: " "$ROOT/view.log" | cut -c1-200

echo "smoke: the presentation pictures"
"$WF" _template hero --res 480x300 --samples 8 --root "$ROOT" >"$ROOT/hero.log" 2>&1; rc=$?
[ $rc -eq 0 ] || { tail -5 "$ROOT/hero.log"; fail "hero exited $rc"; }
for f in TemplateGun.png TemplateGun_rear.png; do
    [ -s "$ROOT/_gallery/hero/$f" ] || fail "hero wrote no _gallery/hero/$f"
done
[ "$before" = "$(cd "$OUT" && find . -type f -printf '%p %s %T@\n' | sort)" ] || fail "hero changed the weapon's own files"

echo "smoke: the hero pictures from the sides, the silhouette, the eye, and a pose"
"$WF" _template hero --shots default,fp,left,right,outline --res 480x270 --samples 8 --root "$ROOT" >"$ROOT/hero2.log" 2>&1; rc=$?
[ $rc -eq 0 ] || { tail -5 "$ROOT/hero2.log"; fail "hero --shots default,fp,left,right,outline exited $rc"; }
for f in TemplateGun_fp.png TemplateGun_left.png TemplateGun_right.png TemplateGun_outline.png; do
    [ -s "$ROOT/_gallery/hero/$f" ] || fail "hero wrote no _gallery/hero/$f"
done
POSE=reload                                  # one of the template's poses (weapons/_template/weapon.py)
"$WF" _template hero --pose "$POSE" --res 480x270 --samples 8 --root "$ROOT" >"$ROOT/hero3.log" 2>&1; rc=$?
[ $rc -eq 0 ] || { tail -5 "$ROOT/hero3.log"; fail "hero --pose $POSE exited $rc"; }
[ -s "$ROOT/_gallery/hero/TemplateGun_pose_$POSE.png" ] || fail "hero --pose wrote no TemplateGun_pose_$POSE.png"
"$WF" _template hero --pose no_such_pose --root "$ROOT" >"$ROOT/hero4.log" 2>&1 && fail "hero --pose took a pose the weapon does not have"
python3 "$TOOL/tests/png_diff.py" "$ROOT/_gallery/hero/TemplateGun.png" "$ROOT/_gallery/hero/TemplateGun_pose_$POSE.png" 0.001 \
    || fail "the weapon in its pose '$POSE' is not a different picture from the rest pose"
[ "$before" = "$(cd "$OUT" && find . -type f -printf '%p %s %T@\n' | sort)" ] || fail "hero --pose changed the weapon's own files"
echo "smoke: pose $POSE differs from the rest pose"

echo "smoke: the review pack (crops from the sides, the silhouette), against its own pack (texture sizes)"
"$WF" _template review --res 480x270 --samples 8 --size 512 --root "$ROOT" >"$ROOT/review.log" 2>&1; rc=$?
[ $rc -eq 0 ] || { tail -8 "$ROOT/review.log"; fail "review exited $rc"; }
PACK="$ROOT/_gallery/review/TemplateGun"
for f in shots/TemplateGun_left.png shots/TemplateGun_right.png shots/TemplateGun_outline.png crops/side_outline.png pack.json contact.png; do
    [ -s "$PACK/$f" ] || fail "the review pack has no $f"
done
ls "$PACK/crops" | tr '\n' ' ' | cut -c1-300; echo
"$WF" _template review --against "$PACK" --out "$ROOT/review_pair" --res 480x270 --samples 8 --size 512 --root "$ROOT" >"$ROOT/review2.log" 2>&1; rc=$?
[ $rc -eq 0 ] || { tail -8 "$ROOT/review2.log"; fail "review --against exited $rc"; }
python3 - "$ROOT/review_pair/compare.json" <<'EOF' || fail "compare.json is not what a build against its own pack should give"
import json, sys
c = json.load(open(sys.argv[1], encoding='utf-8'))
assert c['textures']['differ'] is False and c['textures']['this'] == 512, c['textures']
assert c['warnings'] == [], c['warnings']
assert 'side_outline' in c['crops'] and c['crops']['side_outline']['unchanged'], c['crops'].get('side_outline')
assert not [k for k, v in c['crops'].items() if v.get('missing')], [k for k, v in c['crops'].items() if v.get('missing')]
print('smoke: review pair ok (%d crops, textures %s px both)' % (len(c['crops']), c['textures']['this']))
EOF
python3 - "$PACK/pack.json" "$ROOT/review_pair/pack.json" <<'EOF'
import json, sys                  # a pack that says its textures were 1024 px, compared against: the sizes differ and it is said
d = json.load(open(sys.argv[1], encoding='utf-8')); d['textures'] = {'size': 1024, 'pictured': 512}
json.dump(d, open(sys.argv[2], 'w'))
EOF
"$WF" _template review --against "$ROOT/review_pair" --out "$ROOT/review_warn" --res 480x270 --samples 8 --size 512 --root "$ROOT" >"$ROOT/review3.log" 2>&1; rc=$?
[ $rc -eq 0 ] || { tail -8 "$ROOT/review3.log"; fail "review --against (another texture size) exited $rc"; }
grep -aq "review WARNING: the two builds' textures differ in size: this build 512 px, the build compared against 1024 px" "$ROOT/review3.log" \
    || { tail -5 "$ROOT/review3.log"; fail "the launcher's summary does not say the texture sizes differ"; }
grep -aq '"differ": true' "$ROOT/review_warn/compare.json" || fail "compare.json does not say the texture sizes differ"
echo "smoke: $(grep -a 'review WARNING' "$ROOT/review3.log" | head -1 | cut -c1-160)"

echo "smoke: the stale-chain rule"
"$WF" _template model --root "$ROOT" >>"$LOG" 2>&1; rc=$?
[ $rc -eq 0 ] || fail "the rebuild exited $rc"
if "$WF" _template export --root "$ROOT" >"$ROOT/stale.log" 2>&1; then
    fail "export wrote files although the parts were rebuilt after the UVs, bakes, textures and rig"
fi
grep -aq "RuntimeError: stale: " "$ROOT/stale.log" || { tail -5 "$ROOT/stale.log"; fail "export failed, but not with the stale message"; }
echo "smoke: export refused, as it must: $(grep -a 'RuntimeError: stale: ' "$ROOT/stale.log" | head -1 | cut -c1-200)"

echo "smoke: check after the rebuild names the stale stages and does not count them as misses"
"$WF" _template check --strict --root "$ROOT" >"$ROOT/stale_check.log" 2>&1; rc=$?
[ $rc -eq 0 ] || { grep -a "MISS" "$ROOT/stale_check.log" | head; fail "check --strict after model exited $rc: the old uv and rig were counted as misses"; }
grep -aq "stale, not measured: " "$ROOT/stale_check.log" || fail "check did not say which stages are stale"
grep -a "stale, not measured: " "$ROOT/stale_check.log" | cut -c1-200

echo "smoke: the incomplete-chain rule"
if "$WF" _template model uv rig export --root "$ROOT/skipped" >"$ROOT/skipped.log" 2>&1; then
    fail "export wrote files although the bake and the textures were never made"
fi
grep -aq "RuntimeError: incomplete: " "$ROOT/skipped.log" || { tail -5 "$ROOT/skipped.log"; fail "export failed, but not with the incomplete message"; }
[ ! -e "$ROOT/skipped/_template/export" ] || fail "a refused export still wrote into export/"
echo "smoke: export refused, as it must: $(grep -a 'RuntimeError: incomplete: ' "$ROOT/skipped.log" | head -1 | cut -c1-200)"

echo "smoke: one eye for the grey sheets and hero; a stale stage is not a miss of the model (Blender)"
for t in test_view_eyes:eyes test_stale:stale; do
    name="${t%%:*}"; tag="${t##*:}"
    "$BLENDER" -b --factory-startup --python-exit-code 1 --python "$(w "$TOOL/tests/$name.py")" -- "$(w "$ROOT/$tag")" >"$ROOT/$name.log" 2>&1; rc=$?
    grep -a "^$tag: " "$ROOT/$name.log" | tail -2
    [ $rc -eq 0 ] && grep -aq "^$tag: PASS" "$ROOT/$name.log" || { tail -20 "$ROOT/$name.log"; fail "$name.py (exit $rc)"; }
done

echo "smoke: the guards that need Blender (another rig in the file, a part on a missing bone, an unknown sheet)"
"$BLENDER" -b --factory-startup --python-exit-code 1 --python "$(w "$TOOL/tests/guards_blender.py")" -- "$(w "$ROOT/guards")" >"$ROOT/guards.log" 2>&1; rc=$?
grep -a "^guards: " "$ROOT/guards.log"
[ $rc -eq 0 ] && grep -aq "^guards: PASS" "$ROOT/guards.log" || fail "guards_blender.py (exit $rc)"

echo "smoke: the rules that need no Blender (a definition's typos; the Unreal scripts' arguments)"
python3 "$TOOL/tests/test_definition.py" >"$ROOT/definition.log" 2>&1 || { grep -a "^FAIL\|test_definition" "$ROOT/definition.log"; fail "test_definition.py"; }
tail -1 "$ROOT/definition.log"
python3 "$TOOL/tests/test_unreal_args.py" "$OUT/_template.json" >"$ROOT/args.log" 2>&1 || { grep -a "^FAIL\|test_unreal_args" "$ROOT/args.log"; fail "test_unreal_args.py"; }
tail -1 "$ROOT/args.log"

echo "smoke: PASS"
finish
