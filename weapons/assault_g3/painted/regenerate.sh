#!/usr/bin/env bash
# regenerate.sh: rebuild the 12 painted texture sets made for AssaultG3 (sets.json says where each came from and where it goes).
#
#   regenerate.sh <texforge launcher> <output folder> [--gen-only | --no-gen | --handmade-only]
#
#   <texforge launcher>  texforge's bin/texforge (it runs texforge from its own folder's .venv)
#   <output folder>      made if missing. The working folders go in <out>/texforge/<name>/, the kept sets in
#                        <out>/_materials/<name>/: <name>_BaseColor.png, <name>_Height.png, <name>.texforge.json, and
#                        <name>_Opacity.png for a decal: the layout weaponforge finds under an asset root's _materials/.
#   (no flag)            everything, in order: gen, pick, make, hand-made pictures, soften, decal, keep
#   --gen-only           only the `texforge gen` runs (each one is skipped when its candidates are already there), then
#                        stop, so the candidates can be looked at and the PICK_* below set before the rest
#   --no-gen             never calls `texforge gen`: the candidates must already be in <out>/texforge/<name>/
#   --handmade-only      only the three hand-made decals (stencil_07, label_14, witness): no AI pictures needed
#
# Environment:
#   FONTS    a folder holding arialbd.ttf and Inkfree.ttf (a Windows Fonts folder has both), the fonts the original hand-made
#            decals were drawn with. Optional: BOLD_FONT and HAND_FONT name other font files, and with none of the three
#            make_decals.py uses a free font it finds (the stencil's and the label's lettering then differ a little)
#   PYTHON   the python for make_decals.py and soften.py (numpy and Pillow). Default: the launcher's own .venv python
#            when there is one, else python3
#   PICK_POLY_MOULD PICK_RUBBER PICK_ANODISED PICK_PHOSPHATE PICK_TURNED PICK_LEAK PICK_SCRAPE
#            which candidate (1, 2, 3) each set is made from. The defaults are the ones the published sets were made
#            from, but `texforge gen` does not give the same picture twice: after a new gen, look at the candidates and
#            choose by the reasons in sets.json ("source.chosen_because").
#
# `texforge gen` calls an image generator once per candidate (texforge: TEXFORGE_GENERATOR, default its codex backend), and
# never gives the same picture twice: regenerated tiling sets and the leak and scrape decals differ from the originals.
# Everything else here runs offline; the three hand-made decals come out the same (with the original fonts).
set -euo pipefail

if [ $# -lt 2 ]; then
    awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"
    exit 2
fi
TF=$1
OUT=$2
MODE=${3:-all}
case $MODE in all|--gen-only|--no-gen|--handmade-only) ;; *) echo "regenerate.sh: unknown option $MODE" >&2; exit 2 ;; esac
[ -x "$TF" ] || { echo "regenerate.sh: $TF is not an executable texforge launcher" >&2; exit 2; }
HERE=$(cd "$(dirname "$0")" && pwd)
TF_ROOT=$(cd "$(dirname "$TF")/.." && pwd)                 # the launcher is <texforge>/bin/texforge
if [ -z "${PYTHON:-}" ]; then
    if [ -x "$TF_ROOT/.venv/bin/python" ]; then PYTHON=$TF_ROOT/.venv/bin/python; else PYTHON=python3; fi
fi
W=$OUT/texforge
M=$OUT/_materials
mkdir -p "$W" "$M"

tf() { "$TF" --out "$W" "$@"; }

# ---- 1. texforge gen: the AI candidates (exact prompts; the plain ones are wrapped by texforge's material template, the
#         --kind decal one by its decal template, the --raw one is sent as it is)
gen() {   # gen <name> <prompt> <args...>: skipped when <name> already has candidates
    local name=$1 prompt=$2; shift 2
    if ls "$W/$name/${name}_src_"*.png >/dev/null 2>&1; then
        echo "[gen] $name: candidates already there, not generating again"
    else
        tf gen "$prompt" --name "$name" "$@"
    fi
}
if [ "$MODE" = all ] || [ "$MODE" = --gen-only ]; then
    gen poly_mould "moulded glass-filled nylon polymer surface in a neutral medium grey, a fine spark-eroded mould finish like very fine leather grain, irregular sub-millimetre pebbled micro-relief, a few very faint long soft flow marks, matte, even" --n 3 --parallel 3
    gen rubber "dry matte moulded rubber surface in a dark neutral grey, slightly porous, a very fine moulded stipple with tiny pores, a little dust in the pores, even" --n 2 --parallel 2
    gen anodised "hard-anodised aluminium surface in a dark charcoal grey, a fine even bead-blasted matte grain, very faint straight parallel machining passes running horizontally, even" --n 2 --parallel 2
    gen phosphate "manganese phosphate coated steel surface in a dark neutral grey, a dry crystalline matte grain with fine glinting crystals, even" --n 2 --parallel 2
    gen turned "lathe-turned steel surface in a dark blue-grey, very fine straight parallel tool marks running perfectly horizontally across the whole frame, satin, even" --n 2 --parallel 2
    gen leak_src "dark brown-black oily grime streaks running straight down from a short horizontal line at the top: thin dirty drips of gun oil mixed with dust, narrow and dense at the top, thinning and fading out lower down, vertical" --kind decal --n 2 --parallel 1
    gen scrape_src "A single pale grey scuffed scrape patch on a perfectly plain, uniform, flat pure black background: an irregular ragged abraded area made of many fine straight parallel scratches running diagonally, denser in the middle, fading at its edges. Straight-on orthographic view, flat lighting, no perspective, no shadows, no text, no border. The mark is centred with generous empty black margin all around it. Photoreal, high resolution." --raw --n 2 --parallel 1
fi
if [ "$MODE" = --gen-only ]; then
    echo "[gen] done. Candidates:"; ls "$W"/*/*_src_*.png
    echo "Look at them, set PICK_* if another candidate is better, then run again with --no-gen."
    exit 0
fi

pick() {  # pick <gen name> <index>: the candidate's path, or stop when it is missing
    local p="$W/$1/$1_src_$2.png"
    [ -f "$p" ] || { echo "regenerate.sh: $p is missing (a timed-out candidate?); set PICK_* to one that exists:" >&2; ls "$W/$1/" >&2 || true; exit 1; }
    echo "$p"
}

# ---- 2. texforge make: the five tiling detail sets (plaster type = min-cut seams; no shadow lift, no material masks)
if [ "$MODE" != --handmade-only ]; then
    tile() {  # tile <name> <candidate> <size> <world cm>
        tf make "$2" --name "$1" --type plaster --size "$3" --world-cm "$4" --no-shadow-lift --no-materials --normal-strength 1.0
    }
    # (each pick is its own assignment so that a missing candidate stops the script under set -e)
    P=$(pick poly_mould "${PICK_POLY_MOULD:-2}"); tile poly_mould "$P" 1024 6
    P=$(pick rubber "${PICK_RUBBER:-2}");         tile rubber     "$P" 1024 5
    P=$(pick anodised "${PICK_ANODISED:-2}");     tile anodised   "$P" 512 4
    P=$(pick phosphate "${PICK_PHOSPHATE:-2}");   tile phosphate  "$P" 512 3
    P=$(pick turned "${PICK_TURNED:-1}");         tile turned     "$P" 1024 6
fi

# ---- 3. the hand-made pictures: stencil 07, label 14, witness mark (make_decals.py, seeded)
fonts=()
[ -z "${FONTS:-}" ] || fonts+=(--fonts "$FONTS")
[ -z "${BOLD_FONT:-}" ] || fonts+=(--bold-font "$BOLD_FONT")
[ -z "${HAND_FONT:-}" ] || fonts+=(--hand-font "$HAND_FONT")
"$PYTHON" "$HERE/make_decals.py" --out "$W/_handmade" ${fonts[@]+"${fonts[@]}"}

# ---- 4. the soft variants of the chosen leak and scrape (soften.py, no randomness)
if [ "$MODE" != --handmade-only ]; then
    LEAK=$(pick leak_src "${PICK_LEAK:-2}")
    SCRAPE=$(pick scrape_src "${PICK_SCRAPE:-2}")
    "$PYTHON" "$HERE/soften.py" --leak "$LEAK" --leak-out "$W/leak_src/leak_soft_src.png" \
        --scrape "$SCRAPE" --scrape-out "$W/scrape_src/scrape_soft_src.png"
fi

# ---- 5. texforge decal --image: the seven decals (the description is only a label when --image is given)
tf decal "hand-made label" --image "$W/_handmade/label_14_src.png" --name label_14 --surface generic --size 1024 --world-cm 3.2
tf decal "hand-made stencil" --image "$W/_handmade/stencil_07_src.png" --name stencil_07 --surface generic --size 1024 --world-cm 4
tf decal "hand-made witness" --image "$W/_handmade/witness_src.png" --name witness --surface generic --size 1024 --world-cm 0.3
if [ "$MODE" != --handmade-only ]; then
    tf decal "oil leak" --image "$LEAK" --name leak --surface dirt --size 1024 --world-cm 1.5
    tf decal "scrape" --image "$SCRAPE" --name scrape --surface generic --size 1024 --world-cm 4
    tf decal "oil leak, softened" --image "$W/leak_src/leak_soft_src.png" --name leak_soft --surface dirt --size 1024 --world-cm 2
    tf decal "scrape, softened" --image "$W/scrape_src/scrape_soft_src.png" --name scrape_soft --surface generic --size 1024 --world-cm 4
fi

# ---- 6. keep: BaseColor, Height (and Opacity for a decal) and the record of each set, in <out>/_materials/<name>/
if [ "$MODE" = --handmade-only ]; then
    SETS="label_14 stencil_07 witness"
else
    SETS="anodised phosphate poly_mould rubber turned leak leak_soft scrape scrape_soft label_14 stencil_07 witness"
fi
for n in $SETS; do
    mkdir -p "$M/$n"
    for f in "${n}_BaseColor.png" "${n}_Height.png" "${n}_Opacity.png" "${n}.texforge.json"; do
        if [ -f "$W/$n/$f" ]; then cp "$W/$n/$f" "$M/$n/"; fi
    done
done
kept=0; for n in $SETS; do if [ -f "$M/$n/${n}_BaseColor.png" ]; then kept=$((kept + 1)); fi; done
echo "[done] $kept of $(echo "$SETS" | wc -w) sets kept in $M"
