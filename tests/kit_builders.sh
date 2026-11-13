#!/usr/bin/env bash
# The shared builders (weaponforge/sections.py, forms.py, fittings.py), with AssaultG3's own sights.py and barrels.py (weapons/assault_g3/)
# on it, on a weapon defined from scratch in tests/kit_builders.py: the stages "model" and "uv" and every check they make
# measurable (under a minute). Writes only under a scratch root ($WEAPONFORGE_TEST_ROOT, default build/_test in the repository) and deletes it when it passes.
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
ROOT="$TEST_ROOT/kit_$$"
LOG="$ROOT/kit.log"
mkdir -p "$ROOT"
"$BLENDER" -b --factory-startup --python-exit-code 1 --python "$(w "$TOOL/tests/kit_builders.py")" -- "$(w "$ROOT")" >"$LOG" 2>&1; rc=$?
grep -a "^kit: \|\[kit\] boolean" "$LOG"
if [ $rc -eq 0 ] && grep -aq "^kit: PASS" "$LOG"; then
    [ "${KEEP:-0}" = 1 ] && echo "kit: kept $ROOT" || rm -rf "$ROOT"
    exit 0
fi
echo "kit: FAIL (exit $rc): log $LOG"; exit 1
