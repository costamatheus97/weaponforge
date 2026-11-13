# Texels and UVs

Where the sheet's pixels go. A weapon that sets none of this gets Blender's packer and an even density. The first-person
standard (about 80 px/cm or more at 4096 where the player looks) and the order of work are in `CRAFT.md`, section 3; the walls
met are in `PLAYBOOK.md`, "UVs". The cost of the tight pack is in [stages.md](stages.md): about four minutes at 4096 where
Blender's packer takes seconds, and every change to the game mesh pays it again.

## Texels by place

Opt-in, with a tighter pack. A weapon that sets none of these gets the same UVs as before, to the byte.
`uv_pack = 'tight'` packs with the tool's own packer (`uv.pack_tight`) instead of Blender's: it lays each island's real
outline, biggest first, at the lowest place it fits in any of four quarter turns, so the small islands fill the hollows of the
curved and L-shaped ones. AssaultG3 went from 46.5 % of the sheet to 55 % at the same `uv_margin`, and to 63 % at 0.0017.
`uv_margin` is the space round EACH island (0.0024 is 10 px at 4096: 20 px between two islands, 10 to the edge). Below 0.0017
(14 px between islands) mip 2 starts to take the neighbour's colour. `texel_hidden = 0.45` gives every face that nobody sees in
any of the weapon's poses that weight: faces covered by another part within 0.3 cm, and faces shut in, where none of 48 rays
leaves the weapon, at the centre and at three quarters of the way to every corner (`uv.hidden_faces`: a big face whose middle
is under a lip but whose ends show is not hidden). `texel_zones = [TexelZone(weight, lo, hi, facing='+Y', builders=(...), note=...)]`
gives the faces in a box, facing a side, or of some builders, their weight; where zones overlap, the last one listed wins.
With either set, the islands are cut where the weight changes, each island is scaled by its weight, and the check
`uv: texel density` holds each part to 10 % of what its faces ask for. A second check, `uv: texel zones`, holds every island
to its weight, misses a zone that matches no face, and lists the parts that are dense or sparse by intent with their px/cm.
The tight pack takes about four minutes at 4096 px where Blender's takes seconds. `weapons/assault_g3/weapon.py`, between the
`UV DENSITY` markers, is the worked example (`PLAYBOOK.md`, "UVs", item 8).

## Texels by view

Opt-in: the start for a new weapon. `texel_view = True` weighs every face by what the player sees of it,
with no boxes to draw: the two eyes are the ones the `hero` pictures `fp` and `ads` are taken from (`hero.player_eyes`: the
hip eye by the weapon's length, the aiming eye behind the SightRear socket on the line to SightFront), each looking through a
frame 60 degrees across. A face either eye sees in any pose gets 1.4, 1.75 or 2.2, by how many screen pixels a cm of it
covers (close and square-on most); a face neither eye sees gets 0.9; a seen part with less than 90 cm2 not hidden takes
one step for all of it, so a sight is not cut into slivers, when a quarter of that is seen or less than 20 cm2 of it is
not (a barrel glimpsed close in one pose keeps its steps by face: `weighed whole` names it). `texel_hidden` still wins over all of it, and a `TexelZone`
wins over the view where it applies: add one on top when the eyes cannot know (a grip under the hand, a part the player
looks at in an animation the poses do not show). `player_eyes = {'fp': (x, y, z), 'ads': (x, y, z)}` (cm) moves either eye,
for the pictures and the weights alike. For a new weapon start with `uv_pack = 'tight'`, `texel_view = True` and
`texel_hidden = 0.45`; look at the `hero --shots fp,ads` pictures, and add a zone only for what they show is wrong. The
`uv` log says what it did: `texels: eyes: ...` (where the eyes are, and the cm2 each sees), `seen x1.40 (under 25 screen
px/cm)` and the next steps (the cm2 on each step once the zones and the hidden faces took theirs), `weighed whole` (the
small parts that took one step), and `seam edges where the texel weight changes` per part. The check `uv: texel zones`
lists the same classes with their px/cm.

## Seams

**Seams.** Every hard edge is a UV seam already. `seams(obj)` returns a `pred(edge, mid, direction)` for more, per game part:
a closed smooth surface (a barrel, a receiver, a stock) cannot be laid flat without one, and is otherwise cut up by angle into
strips that end wherever they end. Cut where nobody looks: `lambda e, mid, d: K.in_plane((0, 0, 0), (0, 1, 0))(e) and
mid.z < BORE_Z and abs(d.x) > 0.5` is one line along the underside of a part built with `start=(0, 0, -1)`. The `uv` stage
prints how many edges each part's test picked and a `recut:` line for every patch it still had to cut up by angle. `PLAYBOOK.md`, "UVs", items 5 to 7 cover an organic part (a stock).
