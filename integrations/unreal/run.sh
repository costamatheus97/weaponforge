#!/usr/bin/env bash
# Run one of the Unreal scripts of this folder headless in an Unreal editor, on the project the settings name:
#
#   integrations/unreal/run.sh import --weapon <id> [options]      weapon_import.py   (bin/weaponforge <id> unreal-import)
#   integrations/unreal/run.sh check  --weapon <id> [options]      weapon_check.py    (bin/weaponforge <id> unreal-check)
#   integrations/unreal/run.sh import --spec <path> --dest <base>/_Scratch/<Name>     a spec from a --root build: trial only
#
# Options go to the script as they are: --reimport | --reimport-meshes | --reimport-static, --replace-referenced,
# --dest <base>/_Scratch/<Name>, --remove (weapon_import.py's docstring says what each does). The runner adds
#   --base <unreal.content>   and   --specs <spec_dir, else the asset root>
# from the settings (weaponforge.toml or WEAPONFORGE_*; `bin/weaponforge settings` shows them). It needs
#   unreal.editor    UnrealEditor-Cmd (Linux, macOS: .../Engine/Binaries/<Platform>/UnrealEditor-Cmd), or from WSL the
#                    Windows UnrealEditor-Cmd.exe (it is then run through cmd.exe, with every path in Windows form)
#   unreal.project   the .uproject
# and stops with a message when either is not set. It runs
#   <editor> <project> -run=pythonscript -script="<script> <args>" -unattended -nullrhi -nosplash -NoSound -stdout -abslog=<log>
# writes the log to build/logs/unreal-<import|check>-<time>.log, prints the script's own lines, and fails when the editor's
# exit code is not 0 or the log has a Python error, a traceback or a crash (the scripts report a failure by raising).
#
# UNTESTED since the scripts were taken out of the project they were written in (docs/unreal.md). It does not stop a second
# Unreal process from starting on the same project: run one at a time.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOL="$(cd "$HERE/../.." && pwd)"
die() { echo "unreal run: $*" >&2; exit 2; }
usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "${BASH_SOURCE[0]}"; }

[ $# -ge 1 ] || { usage; exit 2; }
case "$1" in
    import) script="$HERE/weapon_import.py" ;;
    check) script="$HERE/weapon_check.py" ;;
    -h|--help|help) usage; exit 0 ;;
    *) die "first say import or check (got '$1')" ;;
esac
shift

command -v python3 >/dev/null 2>&1 || die "python3 is needed to read the settings"
setting() { python3 "$TOOL/weaponforge/settings.py" get "$1" || exit 2; }
EDITOR_BIN="$(setting unreal.editor)"
UPROJECT="$(setting unreal.project)"
BASE="$(setting unreal.content)"
SPECS="$(setting spec_dir)"
[ -n "$SPECS" ] || SPECS="$(setting assets)"            # no spec folder: each spec is beside its weapon's files
[ -n "$EDITOR_BIN" ] || die "unreal.editor is not set: put editor = \"/path/to/UnrealEditor-Cmd\" under [unreal] in weaponforge.toml, or set WEAPONFORGE_UNREAL_EDITOR"
[ -n "$UPROJECT" ] || die "unreal.project is not set: put project = \"/path/to/Game.uproject\" under [unreal] in weaponforge.toml, or set WEAPONFORGE_UNREAL_PROJECT"
[ -f "$EDITOR_BIN" ] || die "no Unreal editor at $EDITOR_BIN (unreal.editor)"
[ -f "$UPROJECT" ] || die "no project at $UPROJECT (unreal.project)"
[ -n "$BASE" ] || die "unreal.content is empty"

windows=0
case "$EDITOR_BIN" in *.exe|*.EXE) windows=1 ;; esac
[ $windows = 0 ] || command -v wslpath >/dev/null 2>&1 || die "a Windows editor ($EDITOR_BIN) is run from WSL here, and wslpath is missing"
ed() {  # a path in the editor's form
    if [ $windows = 1 ]; then case "$1" in [A-Za-z]:[\\/]*|\\\\*) printf '%s' "$1" ;; *) wslpath -w "$1" ;; esac; else printf '%s' "$1"; fi
}

# the script's arguments: never an empty one (joined into one -script="..." string it would vanish, and a lost value must
# stop the run, not shift the next option into its place: weapon_spec.py refuses that too), never a character the
# command line cannot carry
args=()
while [ $# -gt 0 ]; do
    a="$1"; shift
    [ -n "$a" ] || die "an empty argument (a value that was lost?): nothing was run"
    case "$a" in *'"'*|*'%'*|*'^'*|*'&'*|*'|'*|*'<'*|*'>'*) die "argument not allowed through the command line: $a" ;; esac
    case "$a" in
        --spec) [ $# -ge 1 ] || die "--spec needs a path"; args+=("$a" "$(ed "$1")"); shift ;;
        --base|--specs) die "$a comes from the settings (unreal.content; spec_dir or assets), not the command line" ;;
        *) args+=("$a") ;;
    esac
done
case " ${args[*]-} " in *" --weapon "*|*" --spec "*) ;; *) die "give --weapon <id> or --spec <path>" ;; esac

if [ $windows = 1 ]; then script_e="$(wslpath -m "$script")"; else script_e="$script"; fi    # forward slashes: no escapes
line="$script_e"
for a in ${args[@]+"${args[@]}"} --base "$BASE" --specs "$(ed "$SPECS")"; do line+=" $a"; done

mkdir -p "$TOOL/build/logs"
log="$TOOL/build/logs/unreal-$(basename "$script" .py | sed 's/^weapon_//')-$(date +%Y%m%d-%H%M%S).log"
rm -f "$log"
rc=0
if [ $windows = 1 ]; then
    bat="$TOOL/build/logs/run_unreal.bat"           # cmd.exe keeps -script="..." as one argument, quotes and all
    printf '@echo off\r\n"%s" "%s" -run=pythonscript -script="%s" -unattended -nullrhi -nosplash -NoSound -stdout -abslog="%s"\r\n' \
        "$(ed "$EDITOR_BIN")" "$(ed "$UPROJECT")" "$line" "$(ed "$log")" >"$bat"
    echo "+ $(tr -d '\r' <"$bat" | tail -1)" >&2
    (cd "$(dirname "$bat")" && cmd.exe /d /c "$(wslpath -w "$bat")") >/dev/null 2>&1 || rc=$?
else
    echo "+ $EDITOR_BIN $UPROJECT -run=pythonscript -script=\"$line\" ..." >&2
    "$EDITOR_BIN" "$UPROJECT" -run=pythonscript "-script=$line" -unattended -nullrhi -nosplash -NoSound -stdout "-abslog=$log" >/dev/null 2>&1 || rc=$?
fi
echo "unreal run: editor exit code $rc; log: $log" >&2
[ -f "$log" ] || die "the editor wrote no log at $log"
grep -aE "weapon_(import|check): " "$log" | sed -E 's/^\[[^]]*\]\[[^]]*\]//' | tr -d '\r' >&2 || true
if grep -aqE "LogPython: Error|Traceback \(most recent|=== Critical error" "$log"; then
    grep -aE "LogPython: Error|Traceback \(most recent|=== Critical error" "$log" | head -20 | tr -d '\r' >&2
    echo "unreal run: FAIL: the script reported an error (see the log)" >&2
    exit 1
fi
[ $rc -eq 0 ] || { echo "unreal run: FAIL: editor exit code $rc" >&2; exit 1; }
echo "unreal run: OK" >&2
