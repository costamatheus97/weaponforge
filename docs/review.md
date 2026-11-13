# Review

How a pass is judged: measured figures, and the same crops of two builds side by side. The habit that goes with it (compare,
do not score; keep a change only if its pair is better) is in `CRAFT.md`, section 5.

Judging a weapon by eye went wrong in one way on AssaultG3: marks out of ten did not hold (two reviewers gave the same build
6.5 and 8.5), while "is B better than A in this crop?" did. Part of the rest was measurement nobody had computed. The review
does both: it measures, and it lays the same crops of two builds side by side.

    weaponforge assault_g3 review                                    a pack of this build
    weaponforge assault_g3 review --against <pack or build> --out <new pack folder>
    weaponforge assault_g3 review --against <...> --out <...> --critic '<command>'

Run it after `export`; it reads the `.blend` (never saved), the bake (`bake/*.npy`, or `textures/work/<tag>_*.png` for a
build that kept only those) and the exported meshes and textures (for the pictures, as `hero` does). Against another build
it takes about 3.5 minutes at 4096 px on a mid-range GPU (both are rendered); a pack of one build alone is shorter (not re-timed). `--samples`, `--res` and `--size` work as for `hero`;
against a pack, give the ones that pack was made with (the pixel difference counts noise as change).

**The pack** (`<asset root>/_gallery/review/<Name>/`, or `--out`):

| File | What it is |
|---|---|
| `shots/` | the hero pictures: front, rear, beauty, fp (the hip view), ads (down the sights), left, right and outline |
| `crops/` | native crops of those pictures (cut, never scaled), chosen from the weapon's own sockets and parts: `ads_rear_sight` and `fp_rear_sight` (the `SightRear` socket's part), `fp_near` (the nearest 30 % of the hip view: what fills the player's screen), `muzzle` (the `Muzzle` socket), `control_<part>` for every small part on a moving bone (trigger, safety, release, handle; each from the picture of the side the control is on), `grip` (round the grip origin), `magazine` (the props' parts), `marks` (the largest lettering the pictures see) with `marks_left` and `marks_right` when a side's largest lettering is another, `wall_<side>_<part>` (the large side walls, from the left and right pictures) and `side_outline` (the silhouette). A crop that cannot be had is left out and named in the log and in `pack.json` |
| `figures.json` | the figures below, and for a weapon that holds them, each one held as ok or a miss; under `marks_seen`, for every mark, how much of it the hip eye sees (a mark hidden behind a lever is found here, not in the final picture) |
| `pack.json` | the crop plan (shot and box of each crop) and the record of every camera, light and exposure, so that a later pack can be taken from exactly the same place |
| `contact.png` | one page: the pictures, every crop, and the figures in three lines |
| `rubric.md` | what the critic is given (below) |

With `--against`: `against/` (the other build's crops, cut with this build's plan, and for a build its pictures and figures),
`pairs/<crop>.png` (left the build compared against, right this one), `pairs.png` (every pair on one page, the changed ones
first), and `compare.json`: every figure before and after, and per crop the mean pixel difference and the share of pixels
with a channel moved by more than 12 of 255. When the two builds' textures differ in size, the log says so prominently and
`compare.json` has the sizes under `textures` and the warning under `warnings`: every crop then differs in sharpness, whatever
else changed. A crop under `UNCHANGED` (review.py: 0.2 %) of changed pixels is marked unchanged
and is not judged. That is 100 times the noise: AssaultG3 reviewed against its own pack moved no figure at all and at most
0.002 % of a crop's pixels (mean difference 0.04 of 255); against its middle build its crops changed by 2 to 25 %. **Against a pack**, this build is pictured from the pack's recorded cameras, lights and exposure; **against a
build**, this one is pictured as `hero` would, and then the other from this one's record. Either way the pairs differ in the
asset only. The record replays the camera in the weapon's frame, so a build whose mesh moved is still pictured on the same
part; a build whose overall length changed is framed as the new one was.

**The figures.** Measured on the game parts at rest, in the weapon frame, from the hero eyes (`hero.player_eyes`: the hip
view `fp` and the aiming view `ads`) and the front picture, by casting a ray every third pixel (800 x 450 rays an eye, about
4 seconds in all). `check` says them for every weapon as `note review: figures` (three lines, never a miss), and the spec
gets them under `review`.

| Figure | What it measures |
|---|---|
| `fp_px_cm`, `ads_px_cm` | texture pixels per cm of surface under the weapon's pixels in the hip and aiming views, at the weapon's texture size (root mean square) |
| `fp_sharp_share`, `ads_sharp_share` | the share of those pixels at 80 px/cm or more: what reads sharp in the hero frames |
| `fp_kind_shares`, `front_kind_shares` | each surface kind's share of the weapon's pixels (`none`: no kind under them) |
| `fp_kinds`, `front_kinds` | how many kinds have 2 % or more of them: materials that read apart |
| `pieces`, `pieces_by_part`, `pieces_per_100cm2` | placed hardware: separate pieces of the game mesh under 3 cm across, counted in parts made of more than one piece (a screw, a pin, a rivet; not a trigger that is a part on its own) |
| `marks`, `marks_per_100cm2` | lettering and pictograms (the bake's mark objects) |
| `fp_bare_cm2`, `front_bare_cm2`, `*_bare_part` | the largest stretch the eye sees with nothing modelled or marked within 1 cm of it (the eye-weighted form of `note look: bare faces`) |
| `no_kind_seen`, `no_kind_tris`, `no_kind_by_part` | what the views see with no surface kind; game triangles with no kind under their middle, by part |
| `surface_cm2` | the game mesh's area |

They were chosen on AssaultG3, on three builds (none of them ships): an early one rated 6.5, a middle one and the last. A figure was kept when it separated them in the direction the passes were judged:

| Figure | early (6.5) | middle | last | held at |
|---|---|---|---|---|
| `fp_px_cm` | 53.1 | 56.8 | 95.2 | (said) |
| `fp_sharp_share` | 0.00 | 0.0025 | 0.911 | 0.60 or more |
| `ads_px_cm` | 53.5 | 66.8 | 119.3 | (said) |
| `ads_sharp_share` | 0.00 | 0.00 | 0.988 | 0.75 or more |
| `fp_kinds` | 2 | 3 | 4 | 3 or more |
| `front_kinds` | 3 | 4 | 5 | 4 or more |
| `pieces` | 0 | 12 | 15 | (said) |
| `pieces_per_100cm2` | 0.00 | 0.367 | 0.455 | 0.25 or more |
| `marks` | 5 | 39 | 35 | (said) |
| `marks_per_100cm2` | 0.165 | 1.19 | 1.06 | 0.60 or more |
| `fp_bare_cm2` | 1.93 | 0.65 | 0.42 | (said) |
| `front_bare_cm2` | 6.44 | 2.55 | 3.05 | (said) |
| `no_kind_seen` | 0 | 0.00003 | 0.00003 | (said) |
| `no_kind_tris` | 97 | 71 | 54 | (said) |

The kinds, hardware and marks limits lie between the early build and the middle one: they hold the modelling passes. The
sharpness limits lie between the middle build and the last: they hold the texel pass (`uv_pack = 'tight'`, texel zones,
`texel_view`), which both earlier builds lack. **Said but not held:** the bare stretch (all three are far under the 12 cm2
of `note look: bare faces`, and the early build already had facet creases that break every face, so it does not separate them);
faces with no kind (nearly none on all three; `no_kind_by_part` is still worth reading: in the middle build it named the safety
lever, 54 triangles with no kind). **Dropped:** how many flat sides a round part near the eye shows against its size on screen
(it rose from 1.45 to 2.82 px over the passes, because there was more round detail, not worse); the largest kind's share
(0.51 against 0.53: no signal).


## Holding the figures: `review = 'first_person'`

**Held for a weapon that asks.** `Weapon.review = 'first_person'` makes each held figure a check, `review: <figure>`, counted
with the others ("N of N checks pass"), in the spec's report, and stopping `export --strict` like any miss.
`review_limits = {'fp_sharp_share': 0.5}` moves a limit for that weapon. Without `review` (the default) nothing
changes: the check results are the same as before, and the figures are only said. A weapon with no bake yet is not measured.

**When a weapon should set it.** Set `review = 'first_person'` on a weapon that is meant to be seen from the player's own
eyes, when the brief wants those standards held: texels sharp at the hip and aiming views, materials that read apart,
hardware and lettering where the eye is. Leave it unset on a weapon that is mostly seen on the ground or in other hands, while
the model is still being found, and on a weapon without the `SightRear` and `SightFront` sockets (it has no aiming view, and a
figure that cannot be measured counts as a miss once the limits are held). No shipped weapon sets it: the table above was
measured on three builds of AssaultG3, and nothing in this repository holds a build to it yet.

**The limits are one weapon's, and are meant to be set per weapon.** The six held limits are in `review.LIMITS`
(`fp_sharp_share` 0.60, `ads_sharp_share` 0.75, `fp_kinds` 3, `front_kinds` 4, `pieces_per_100cm2` 0.25,
`marks_per_100cm2` 0.60), and they were set between AssaultG3's builds (its last has 35 marks and 15 pieces of hardware). They are not a standard of quality. A weapon whose brief asks for less has a different number: a gun
with four engraved marks has about 0.17 marks per 100 cm2, which misses 0.60 and is not wrong, because four marks is what its
brief promised. Such a weapon moves the limit to what its brief promises (`review_limits = {'marks_per_100cm2': 0.15}`) or
leaves `review` unset and reads the figure. Take a limit from the brief, never from what the build happens to give, and
never to turn a miss into a pass. `review_limits` takes the names in `review.LIMITS` and numbers only; the weapon is refused
when it is loaded with an unknown name or a value that is not a number.

**The critic** (`--critic`, off by default). The launcher, once Blender has made the pack, runs `weaponforge/critic.py` on this
side of the launcher, never inside Blender, and calls the command once per pair that changed, with these fields, each quoted for the
shell:

    {a} {b}     the two crops, copied to critic/<crop>/A.png and B.png; which is the new build is drawn per crop (seeded,
                kept in critic/order.json), so the judge is never told
    {name}      the crop's name
    {rubric}    the pack's rubric.md: what was kept and what was turned back on AssaultG3 (weaponforge/review_rubric.md)
    {out}       where to write the answer, critic/<crop>/answer.json

The command writes `{"better": "a" | "b" | "same", "confidence": 0 to 1, "why": "one sentence"}` to `{out}` (or prints it as
its last line). Anything else, a non-zero exit or a time-out (300 s) is recorded as invalid and the run goes on. The answers
are mapped back to before and after into `punchlist.json` and `punchlist.md`: first the crops where the build compared
against is better (to fix or turn back), then those judged the same (a change the pictures do not show as better), then the
invalid ones, then the better ones, the surest first in each. The tool calls no model itself; the command can be anything
(a script that calls a vision model, a person's own viewer). `python3 weaponforge/critic.py <pack> '<command>'` reruns the
judge on a pack that already has its pairs.

    tests/review.sh     the figures on a synthetic case with known answers (Blender), the critic's round trip with a stub
                        judge, the definition's rules for review and review_limits, the launcher's paths (10 s)
