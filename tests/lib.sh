# Sourced by the tests/*.sh scripts: the Blender they run, how a path reaches it, and where they write.
#
#   BLENDER         $WEAPONFORGE_BLENDER, else `blender` in the settings (weaponforge.toml), else `blender` on PATH
#   w PATH          PATH in that Blender's form (a Windows Blender run from WSL gets a Windows path)
#   TEST_ROOT       $WEAPONFORGE_TEST_ROOT, else build/_test in the repository (git-ignored). A Windows Blender run from WSL
#                   must be able to reach it: keep the repository on a Windows drive (/mnt/...) or set WEAPONFORGE_TEST_ROOT.
TOOL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BLENDER="${WEAPONFORGE_BLENDER:-}"
[ -n "$BLENDER" ] || BLENDER="$(python3 "$TOOL/weaponforge/settings.py" get blender 2>/dev/null || true)"
[ -n "$BLENDER" ] || BLENDER="$(command -v blender 2>/dev/null || true)"
[ -n "$BLENDER" ] || { echo "tests: no Blender (set WEAPONFORGE_BLENDER, or blender in weaponforge.toml, or put blender on PATH)" >&2; exit 2; }
TEST_ROOT="${WEAPONFORGE_TEST_ROOT:-$TOOL/build/_test}"
w() { case "$BLENDER" in *.exe) wslpath -w "$1" 2>/dev/null && return ;; esac; printf '%s' "$1"; }
