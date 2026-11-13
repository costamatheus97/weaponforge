#!/usr/bin/env bash
# The review stage's own tests (docs/review.md), about ten seconds, nothing written outside a scratch folder:
#
#   tests/review.sh     test_review.py in Blender (the figures on a synthetic case with known answers); test_review_crops.py (each
#                       crop cut from the picture of the side its thing is on); test_review_textures.py (two builds' texture sizes);
#                       test_critic.py (the critic's round trip with a stub judge); test_review_definition.py (what a definition
#                       may say: Weapon.review, .review_limits); and the launcher, with a stand-in for Blender: a path given as
#                       D:\..., D:/..., \\server\... or (under WSL) /mnt/d/... reaches a Windows Blender as a Windows path and
#                       any other Blender as it was given, the WEAPONFORGE_* variables reach a Windows Blender through WSLENV,
#                       --critic goes only with review and runs on this side once Blender has said where the pack is
set -uo pipefail

. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT
fail() { echo "review tests: FAIL: $*"; exit 1; }

echo "review tests: the figures on a synthetic case (Blender)"
"$BLENDER" -b --factory-startup --python-exit-code 1 --python "$(w "$TOOL/tests/test_review.py")" >"$SCRATCH/figures.log" 2>&1; rc=$?
grep -a "^review: " "$SCRATCH/figures.log"
[ $rc -eq 0 ] && grep -aq "^review: PASS" "$SCRATCH/figures.log" || { tail -20 "$SCRATCH/figures.log"; fail "test_review.py (exit $rc)"; }

echo "review tests: the crops, from the side a thing is on (Blender)"
"$BLENDER" -b --factory-startup --python-exit-code 1 --python "$(w "$TOOL/tests/test_review_crops.py")" >"$SCRATCH/crops.log" 2>&1; rc=$?
grep -a "^crops: " "$SCRATCH/crops.log" | tail -3
[ $rc -eq 0 ] && grep -aq "^crops: PASS" "$SCRATCH/crops.log" || { tail -20 "$SCRATCH/crops.log"; fail "test_review_crops.py (exit $rc)"; }

echo "review tests: two builds' texture sizes"
python3 "$TOOL/tests/test_review_textures.py" >"$SCRATCH/textures.log" 2>&1 || { grep -a "^FAIL\|Error" "$SCRATCH/textures.log"; fail "test_review_textures.py"; }
tail -1 "$SCRATCH/textures.log"

echo "review tests: the critic with a stub judge"
python3 "$TOOL/tests/test_critic.py" >"$SCRATCH/critic.log" 2>&1 || { grep -a "^FAIL\|test_critic" "$SCRATCH/critic.log"; fail "test_critic.py"; }
tail -1 "$SCRATCH/critic.log"

echo "review tests: what a definition may say"
python3 "$TOOL/tests/test_review_definition.py" >"$SCRATCH/definition.log" 2>&1 || { grep -a "^FAIL\|test_review_definition" "$SCRATCH/definition.log"; fail "test_review_definition.py"; }
tail -1 "$SCRATCH/definition.log"

echo "review tests: the launcher's paths and --critic (a stand-in for Blender)"
FAKE="$SCRATCH/fake_blender.exe"          # named as the Windows Blender is: the launcher converts paths only for a .exe
cat >"$FAKE" <<'EOF'
#!/usr/bin/env bash
# says what it was given, one argument a line; for review, writes the pack it was told to into --pack-file
printf '%s\n' "$@" >"$FAKE_LOG"
printf '%s\n' "${WSLENV:-}" >"$FAKE_LOG.env"
while [ $# -gt 0 ]; do
    if [ "$1" = --pack-file ]; then f="$2"; command -v wslpath >/dev/null && f="$(wslpath -u "$2")"; printf '%s' "$FAKE_PACK" >"$f"; fi
    shift
done
EOF
chmod +x "$FAKE"
export FAKE_LOG="$SCRATCH/args.txt" FAKE_PACK
FAKE_PACK="$(w "$SCRATCH/pack")"
WF="$TOOL/bin/weaponforge"
given() { grep -qxF -- "$1" "$FAKE_LOG" || fail "$2: Blender was not given '$1' ($(tr '\n' ' ' <"$FAKE_LOG"))"; }

WEAPONFORGE_BLENDER="$FAKE" "$WF" _template check --root 'D:\builds\trial' >/dev/null || fail "check, D:\\ root"
given 'D:\builds\trial' 'a D:\ root passes as it is'
WEAPONFORGE_BLENDER="$FAKE" "$WF" _template check --root 'D:/builds/x' >/dev/null || fail "check, D:/ root"
given 'D:/builds/x' 'a D:/ root passes as it is'
WEAPONFORGE_BLENDER="$FAKE" "$WF" _template check --root '\\server\share\x' >/dev/null || fail "check, UNC root"
given '\\server\share\x' 'a \\server root passes as it is'
if command -v wslpath >/dev/null 2>&1; then
    WEAPONFORGE_BLENDER="$FAKE" "$WF" _template check --root=/mnt/d/builds/x >/dev/null || fail "check, --root=/mnt/d"
    given 'D:\builds\x' 'a /mnt/d root given as --root= becomes D:\'
    WEAPONFORGE_BLENDER="$FAKE" "$WF" _template review --root /mnt/d/a --against /mnt/d/b --out /mnt/d/c >/dev/null || fail "review"
    given 'D:\a' 'review --root'; given 'D:\b' 'review --against'; given 'D:\c' 'review --out'; given '--pack-file' 'review --pack-file'
fi
cp "$FAKE" "$SCRATCH/fake_blender"                 # a Linux or macOS Blender: every path reaches it as it was given
WEAPONFORGE_BLENDER="$SCRATCH/fake_blender" "$WF" _template check --root /mnt/d/builds/x >/dev/null || fail "check, a Blender that is not a .exe"
given '/mnt/d/builds/x' 'a /mnt/d root reaches a Blender that is not a .exe as it is'
echo "ok   paths reach Blender in its own form"
WEAPONFORGE_ASSETS=/mnt/d/builds WEAPONFORGE_BLENDER="$FAKE" "$WF" _template check >/dev/null || fail "check, with a setting in the environment"
for name in WEAPONFORGE_ASSETS WEAPONFORGE_BLENDER; do
    tr ':' '\n' <"$FAKE_LOG.env" | grep -qx "$name" || fail "$name is not in the WSLENV a Windows Blender gets ($(cat "$FAKE_LOG.env"))"
done
echo "ok   the WEAPONFORGE_* variables reach a Windows Blender (WSLENV)"
WEAPONFORGE_BLENDER="$FAKE" "$WF" _template check --critic 'true' >"$SCRATCH/out.txt" 2>&1; rc=$?
[ $rc -eq 2 ] && grep -q "goes with review" "$SCRATCH/out.txt" || fail "--critic without review exited $rc: $(cat "$SCRATCH/out.txt")"
echo "ok   --critic without review is refused"
mkdir -p "$SCRATCH/pack"
WEAPONFORGE_BLENDER="$FAKE" "$WF" _template review --critic 'true {a}' >"$SCRATCH/out.txt" 2>&1; rc=$?
grep -q "review pack: $SCRATCH/pack" "$SCRATCH/out.txt" || fail "the launcher did not say where the pack is: $(cat "$SCRATCH/out.txt")"
grep -qx -- '--critic' "$FAKE_LOG" && fail "--critic reached Blender"
[ $rc -eq 2 ] && grep -q "has no compare.json" "$SCRATCH/out.txt" || fail "the critic did not run on the pack (exit $rc): $(cat "$SCRATCH/out.txt")"
echo "ok   --critic stays on this side and runs on the pack Blender wrote (here one with no pairs: refused, exit 2)"
printf '{"warnings": ["the textures of the two builds differ in size: this build 4096 px, the build compared against 1024 px."], "crops": {}}' >"$SCRATCH/pack/compare.json"
WEAPONFORGE_BLENDER="$FAKE" "$WF" _template review >"$SCRATCH/out.txt" 2>&1
grep -q "review WARNING: the textures of the two builds differ in size: this build 4096 px" "$SCRATCH/out.txt" || fail "the launcher did not print compare.json's warning: $(cat "$SCRATCH/out.txt")"
echo "ok   the launcher prints what compare.json warns of"

echo "review tests: PASS"
