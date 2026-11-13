#!/usr/bin/env bash
# The named finishes (weaponforge/finish.py) on a small template bake: every finish builds alone and in one table, rows with
# different places keep their own masks, and the per-cm edge masks (maps.edge_masks) give the bake back at scale 1.
#
#   tests/finishes.sh         a 256 px template under $WEAPONFORGE_TEST_ROOT (default build/_test in the repository)
#   KEEP=1 tests/finishes.sh  leave the files
set -uo pipefail

. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
WF="$TOOL/bin/weaponforge"
ROOT="$TEST_ROOT/finishes_$$"
LOG="$ROOT/finishes.log"
mkdir -p "$ROOT"
win() { w "$1"; }
finish() { if [ "${KEEP:-0}" = 1 ]; then echo "finishes: kept $ROOT"; else rm -rf "$ROOT"; fi; }

echo "finishes: a small template bake (log: $LOG)"
"$WF" _template model uv bake --root "$ROOT" --size 256 >"$LOG" 2>&1 || { tail -20 "$LOG"; echo "finishes: FAIL: the bake"; exit 1; }
"$BLENDER" -b --factory-startup "$(win "$ROOT/_template/_template.blend")" --python-exit-code 1 \
    --python "$(win "$TOOL/tests/test_finishes.py")" -- "$(win "$TOOL")" "$(win "$ROOT")" >>"$LOG" 2>&1; rc=$?
grep -a "^finishes:" "$LOG"
[ $rc -eq 0 ] || { grep -a "Error\|Traceback" "$LOG" | tail -8; echo "finishes: FAIL (log $LOG)"; exit 1; }
finish
