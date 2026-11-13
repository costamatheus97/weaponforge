"""Named finishes: a whole material in one call, with its painted set, its wear and its grime, for surface() to lay on by kind.

Each finish is what AssaultG3's look pass tuned, lifted out of that weapon so the next one
starts from it: the base recipe (surface.polymer / surface.worn_steel) with its arguments, the texforge set and how it is laid
on, and the wear on top of the recipe (hand polish in patches, scuffs in the material's own colour, grime gathered round the
controls, a top-to-bottom fade, bright thin wear on the top corners of black metal, dust in its slots, carbon at the muzzle).

    from weaponforge import finish as F
    def images(self):
        return S.texforge_sets(self, *F.sets('moulded_polymer', 'rubber', 'anodised_alloy', 'phosphate_parts'))
    def surface(self, s):
        return F.look(s, [('steel', 'phosphate_parts'),                               # the first row is the base
                          ('polymer', 'moulded_polymer', {'colour': (0.05, 0.05, 0.055)}),
                          ('rubber', 'rubber')])

Every argument of every finish can be overridden; the defaults are AssaultG3's values. A finish never reads a weapon's own
constants: where a mask needs a place it takes it from what the weapon declares (`handled`, `smooth`, `textured`,
`rubber_textured`, `grime`, its bones and sockets, its game mesh's bounds) or from a generic rule, as each docstring says.
FINISHES lists them by name; docs/look.md, "Named finishes", lists their arguments.
"""
import zlib

import bpy

from . import surface as S
from .weapon import Zone

OLIVE = (0.052, 0.062, 0.024)
OLIVE_WORN = (0.062, 0.074, 0.028)


# ------------------------------------------------------------------------------------------------------------ helpers
def _painted(s, name, world_cm=None, tone=0.0, relief=1.0, rough=0.0, grain=False):
    """A texforge set as a recipe's detail keywords, or {} when it is not on disk (the recipe keeps its procedural pattern)."""
    if not name:
        return {}
    d = S.detail(s, name, world_cm=world_cm)
    if d is None:
        return {}
    out = dict(detail=d, detail_tone=tone, detail_relief=relief, detail_rough=rough)
    if grain:
        out['grain'] = 0.0
    return out


class _Default:
    def __repr__(self):
        return 'DEFAULT'


DEFAULT = _Default()          # "take it from the weapon" (its zones, bones, sockets, bounds), as each finish's docstring says


def _zones(s, value, key):
    """A mask from a list of Zones, or the socket itself, or None. Cached under key and the zones' own numbers, so two rows of
    one finish with different places (a black grip, an olive body) never share a mask."""
    if value is None or isinstance(value, bpy.types.NodeSocket):
        return value
    value = list(value)
    sig = repr([(z.lo, z.hi, z.strength, z.soft, z.tilt) for z in value]).encode()
    return S.zones(s, value, '%s_%08x' % (key, zlib.crc32(sig)))


def _up(s):
    """1 on faces that look up (the generic place for corner wear on black metal)."""
    g = s.g
    return s.shared('finish_up', lambda: g.step(g.xyz(g.new('ShaderNodeNewGeometry').outputs['True Normal'])[2], 0.50, 0.80))


def _down(s):
    """1 on faces that look down (the generic place a magazine is set down on)."""
    g = s.g
    return s.shared('finish_down', lambda: g.step(g.xyz(g.new('ShaderNodeNewGeometry').outputs['True Normal'])[2], -0.50, -0.80))


def _lp_objects(weapon):
    coll = next((c for c in bpy.data.collections if c.name == weapon.tag + '_LP'), None)
    return [o for o in (coll.all_objects if coll else ()) if o.type == 'MESH']


def kind_z_range(weapon, kind):
    """(lowest, highest) z of the game parts of one kind (their 'mat'), from the game mesh in the file; None without one."""
    zs = []
    for o in _lp_objects(weapon):
        if str(o.get('mat', 'steel')) == kind:
            zs += [(o.matrix_world @ v.co).z for v in o.data.vertices]
    return (min(zs), max(zs)) if zs else None


def grime_places(weapon, radius=0.9, half_width=5.0):
    """Where grime gathers on a moulding, when the weapon names no `grime` zones: a box round every bone's head but the root
    and the grip's (the controls' pivots: safety, release, trigger, charging handle, magazine catch) and round the ejection
    socket, through the whole width (both sides). The weapon's own `grime` list wins when it has one."""
    out = []
    for name, _parent, head in getattr(weapon, 'bones', ()):
        if name in ('Root_Bone1', 'Root_Bone', 'Grip_Bone') or name.startswith('Clip') or name in ('Ammo', 'MagAmmo_Bone'):
            continue
        x, _y, z = head
        out.append(Zone((x - radius, -half_width, z - radius), (x + radius, half_width, z + radius), 1.0, 0.5, note='round ' + name))
    for sk in getattr(weapon, 'sockets', ()):
        if sk[0] == 'AmmoEject':
            x, _y, z = sk[2]
            out.append(Zone((x - 1.5, -half_width, z - 1.0), (x + 1.5, half_width, z + 1.0), 0.8, 0.5, note='round the port'))
    return out


def part_zone(s, *builders, pad=0.3, soft=0.04):
    """A mask over the game parts of these builders (their bounds in the weapon frame, `pad` cm wider), for a row's `where`:
    the generic way to tell a barrel or a magazine from the rest of the steel by the parts the weapon already has. None when
    no such part is in the file."""
    lo, hi = [1e9] * 3, [-1e9] * 3
    for o in _lp_objects(s.weapon):
        if o.get('builder', '') in builders:
            for v in o.data.vertices:
                p = o.matrix_world @ v.co
                lo, hi = [min(a, b) for a, b in zip(lo, p)], [max(a, b) for a, b in zip(hi, p)]
    if lo[0] > hi[0]:
        return None
    return _zones(s, [Zone([a - pad for a in lo], [b + pad for b in hi], 1.0, soft, note='the parts of ' + ', '.join(builders))], 'part')


def _socket_x(weapon, name):
    for sk in getattr(weapon, 'sockets', ()):
        if sk[0] == name:
            return float(sk[2][0])
    return None


def _lines(s, key, along_x=0.05, across=26.0, lo=0.700, hi=0.713, loc=(3.3, 1.1, 0.4)):
    """Long fine scratches along +X (the way a charging handle and an optic slide), about a texel wide."""
    g = s.g
    return s.shared('tex_lines_' + key, lambda: g.step(g.noise(g.mapping(s.pos, scale=(along_x, across, across), rot=(0.0, 0.0, 1.2), loc=loc),
                                                                 1.0, 2.0, 0.5), lo, hi))


SERRATED_COLOUR = ((0.014, 0.015, 0.017), (0.004, 0.004, 0.005))     # a serrated face's ridges, its grooves: the black dye, a little worn
SERRATED_ROUGH = (0.60, 0.84)                                        # roughness of its ridges, of its grooves (drier)


def _serrated(s, lay, serrated, ends, colour, rough, metal):
    """lay with the serrated zones laid over it: no dust and no corner wear (the dust and the bright line the finish put on every
    groove floor and every top corner are replaced), black and dry in the grooves, the ridges the black dye (`colour`, `rough`,
    `metal`: (ridge, groove) pairs, metal one number for the ridge, a list of numbers one for each zone of `serrated`, or a
    mask). `ends`: zones of ridge ends, where a sparse few keep the finish's own wear (a thin worn line on the metal)."""
    g = s.g
    serr = _zones(s, serrated, 'tex_serrated')
    groove = g.maxf(g.step(S.hollows(s), 0.25, 0.70), g.step(s.cavity, 0.08, 0.40))
    quiet = serr
    if ends is not None:
        sparse = g.step(g.noise(g.mapping(s.pos, loc=(4.2, 9.1, 1.3)), 2.5, 2.0, 0.5), 0.56, 0.66)
        worn = g.mul(g.mul(_zones(s, ends, 'tex_serrated_ends'), sparse), g.inv(groove))
        quiet = g.mul(serr, g.inv(worn))
    ridge_metal = metal
    if isinstance(metal, (tuple, list)):
        if isinstance(serrated, bpy.types.NodeSocket):
            raise ValueError('finish: serrated_metal as a list needs `serrated` as a list of Zones (one number for each)')
        zones = list(serrated)
        if len(metal) != len(zones):
            raise ValueError('finish: serrated_metal has %d numbers for %d serrated zones (one number for each, or one number for all)'
                             % (len(metal), len(zones)))
        ridge_metal = float(metal[0])
        for i in range(1, len(zones)):
            if float(metal[i]) != float(metal[0]):
                ridge_metal = g.mixf(_zones(s, [zones[i]], 'tex_serrated_%d' % i), ridge_metal, float(metal[i]))
    return S.Layer(g.mix(quiet, lay.colour, g.mix(groove, colour[0], colour[1])),
                   g.mixf(quiet, lay.rough, g.mixf(groove, rough[0], rough[1])),
                   g.mixf(quiet, lay.metal, g.mixf(groove, ridge_metal, 1.0)), lay.height)


def black_metal_life(s, lay, kind, tops=DEFAULT, slides=DEFAULT, bare=None, sparkle=0.34, dust=1.0, corners=1.0, dust_off=None,
                     corners_off=None, serrated=None, serrated_ends=None, serrated_metal=0.4, serrated_colour=SERRATED_COLOUR,
                     serrated_rough=SERRATED_ROUGH):
    """What the eye finds on black metal in the first-person view, over a recipe's finished layer. kind 'alloy': long fine
    scratches where `slides` (a hand, a charging handle, an optic) run, and a bead-blast sparkle (a per-texel swing of roughness
    and brightness, `sparkle` its roughness swing); both kinds: bright thin wear on the top corners in `tops`, pale dust in slots
    and round screws. tops: [Zone] or a mask; DEFAULT: the faces that look up. slides: [Zone] or a mask; DEFAULT: the weapon's
    `handled` zones (none when it names none). bare: (colour, roughness) of the metal under the finish.
    Turning the wear down, in general or in a place (0 is off, 1 is as the finish has always been):
      dust, corners            how much of the pale dust in slots and the bright line on the top corners is kept, everywhere
      dust_off, corners_off    [Zone] or a mask: there the dust / the corner line is multiplied by 1 - the mask (a zone's strength
                               is how much of it goes: 1.0 all, 0.5 half)
    Serrated faces (anti-glare ramps, a sight leaf: faces that are nothing but grooves and corners, where the finish above
    would make bright silver bars):
      serrated          [Zone] or a mask: no dust and no corner wear there, black and dry in the grooves, the ridges the black
                        dye. Laid over everything else, whatever `dust` and `corners` say
      serrated_ends     [Zone] or a mask: ridge ends, where a sparse few keep the finish's own wear (a thin worn line)
      serrated_metal    how much of the ridge is metal: a number for all, or a list with one for each zone of `serrated`. As a coat
                        (0) a dry black reads pale grey on a face seen at a grazing angle; as all metal (1) a face the eye looks
                        into is a black hole with no grooves. About 0.6 for the first, 0.15 for the second; 0.4 between
      serrated_colour   ((ridge), (groove)) colours;  serrated_rough: (ridge, groove) roughness"""
    g = s.g
    if bare is None:
        bare = ((0.50, 0.50, 0.52), 0.26) if kind == 'alloy' else ((0.42, 0.42, 0.41), 0.30)     # aluminium / steel under the finish
    bare, bare_rough = bare
    colour, rough, metal = lay.colour, lay.rough, lay.metal
    top = _up(s) if tops is DEFAULT else _zones(s, tops, 'tex_tops')
    if kind == 'alloy':
        path = s.handled if slides is DEFAULT else _zones(s, slides, 'tex_path')
        if path is not None:
            lines = g.maxf(_lines(s, 'a'), g.mul(_lines(s, 'b', 0.08, 19.0, 0.705, 0.716, (7.1, 2.6, 5.2)), 0.6))
            sc = g.mul(g.mul(lines, path), g.step(g.noise(g.mapping(s.pos, loc=(2.2, 8.1, 4.4)), 0.9, 2.0, 0.5), 0.40, 0.58), True)
            colour = g.mix(g.mul(sc, 0.85, True), colour, bare)
            rough = g.mixf(sc, rough, bare_rough)
            metal = g.mixf(sc, metal, 1.0)
        if sparkle:
            # the bead-blast's sparkle: grains about a texel across, each a little glossier or drier, lighter or darker
            spark = s.shared('tex_spark', lambda: g.noise(g.mapping(s.pos, loc=(5.1, 7.7, 2.9)), 60.0, 1.0, 0.5))
            rough = g.add(rough, g.mul(g.sub(spark, 0.5), sparkle))
            colour = g.times(colour, g.add(1.0, g.mul(g.sub(spark, 0.5), -0.6)))
    if top is not None and corners:
        # the top corners: a hair of bright metal in rubbed stretches
        line = g.mul(g.mul(g.step(s.convex, 0.40, 0.75), top), g.mixf(S.stretches(s), 0.30, 1.0), True)
        if corners != 1.0:
            line = g.mul(line, corners, True)
        if corners_off is not None:
            line = g.mul(line, g.inv(_zones(s, corners_off, 'tex_corners_off')))
        colour = g.mix(g.mul(line, 0.95, True), colour, bare)
        rough = g.mixf(line, rough, bare_rough)
        metal = g.mixf(line, metal, 1.0)
    # dust: pale and dry in the slots and round the screws (dark grime is invisible on black). The floors of grooves and slots
    # and the crease round a screw's counterbore; not surface.recesses, whose occlusion term filled a cover's whole top with dust
    if dust:
        film = g.maxf(g.step(S.hollows(s), 0.30, 0.80), g.mul(g.step(s.cavity, 0.10, 0.45), 0.8))
        film = g.mul(film, g.add(0.35, g.mul(g.step(s.n_med, 0.35, 0.70), 0.65)), True)
        if dust != 1.0:
            film = g.mul(film, dust, True)
        if dust_off is not None:
            film = g.mul(film, g.inv(_zones(s, dust_off, 'tex_dust_off')))
        colour = g.mix(g.mul(film, 0.70, True), colour, (0.105, 0.098, 0.086))
        rough = g.mixf(g.mul(film, 0.8, True), rough, 0.90)
        metal = g.mixf(g.mul(film, 0.8, True), metal, 0.0)
    out = S.Layer(colour, rough, metal, lay.height)
    if serrated is not None:
        out = _serrated(s, out, serrated, serrated_ends, serrated_colour, serrated_rough, serrated_metal)
    return out


# ------------------------------------------------------------------------------------------------------------ finishes
def moulded_polymer(s, colour=OLIVE, worn=None, matt=(0.72, 0.62), mottle=0.7, edge=0.75, fade=0.5, handled=DEFAULT, smooth=DEFAULT,
                    textured=DEFAULT, exposure=1.0, recess=1.0, vary=1.0, vary_broad=None, patches=(0.30, 0.70),
                    texture='poly_mould', texture_cm=(9.0, 9.0), texture_tone=0.08, texture_relief=1.3, texture_rough=0.07,
                    polish=(0.60, 0.40), polish_darken=0.80, polish_amount=0.70, polish_rough=0.30,
                    fade_z=DEFAULT, fade_range=(0.88, 1.06), fade_rough=0.06,
                    grime=DEFAULT, grime_tint=(0.50, 0.48, 0.38), grime_amount=0.80, grime_rough=0.12):
    """Moulded polymer of any colour (olive by default; a black shell: colour=(0.020, 0.020, 0.022)): surface.polymer under
    the wear, the `poly_mould` grain in the sheen and the normal map (not in the colour: a tone swing paled it into a chalky
    film), then:
      handled polish   where the weapon's `handled` zones are, in patches (`polish`: the floor and the swing of a smudge noise
                       a cm or two across): `polish_darken` times the colour and roughness `polish_rough`, glossy, not satin
                       (a satin polish caught a broad pale sheen on grazing faces and read as bleached paint). The recipe's
                       own handled wear is fed the zones in patches too (`patches`), so its rub and scuffs are not one sheet
      scuffs / edges   the recipe's, in `worn` (by default 1.19 times `colour`: lighter, the same hue), never a grey
      fade             faces that look up a hair paler (`fade`, the recipe's), and a slow darkening from the top of the
                       moulding to its bottom (`fade_z`: (low, high) z, cm; DEFAULT: the polymer game parts' own z range)
      grime            gathered round the controls, darkest in their recesses (`grime`: [Zone]; DEFAULT: the weapon's `grime`
                       list, else grime_places(): a box round every control bone's pivot and the ejection port)
    handled / smooth / textured: [Zone], a mask or None; DEFAULT: the weapon's own lists.
    vary_broad: how much of `vary`'s broad, low-frequency part (a drift, greasy smudges a few cm across) is kept; None is the
    same as `vary`. vary=1, vary_broad=0.3 keeps the fine variation and the scuffs and turns the mottling down (surface.polymer)."""
    g = s.g
    w = s.weapon
    if worn is None:
        worn = OLIVE_WORN if tuple(colour) == OLIVE else tuple(min(1.0, c * 1.19) for c in colour)
    handled = s.handled if handled is DEFAULT else _zones(s, handled, 'finish_poly_handled')
    smooth = s.smooth if smooth is DEFAULT else _zones(s, smooth, 'finish_poly_smooth')
    textured = s.textured if textured is DEFAULT else _zones(s, textured, 'finish_poly_textured')
    patched = None
    if handled is not None:
        patched = g.mul(handled, g.add(patches[0], g.mul(g.step(S.smudges(s), 0.0, 0.6), patches[1])), True) if patches else handled
    tex = _painted(s, texture, texture_cm, texture_tone, texture_relief, texture_rough, grain=True)
    lay = S.polymer(s, colour=colour, worn=worn, matt=matt, mottle=mottle, edge=edge, smooth=smooth, textured=textured, fade=fade,
                    handled=patched, exposure=exposure, recess=recess, vary=vary, vary_broad=vary_broad, **tex)
    colour_, rough = lay.colour, lay.rough
    if fade_z is DEFAULT:
        fade_z = kind_z_range(w, 'polymer')
    if fade_z is not None:
        _x, _y, z = g.xyz(s.pos)
        t = g.step(z, fade_z[0], fade_z[1])
        colour_ = g.times(colour_, g.mixf(g.add(g.mul(t, 0.85), g.mul(g.sub(s.n_large, 0.5), 0.3)), fade_range[0], fade_range[1]))
        rough = g.add(rough, g.mul(g.sub(t, 0.5), fade_rough))
    if grime is DEFAULT:
        grime = getattr(w, 'grime', None)
        grime = grime_places(w) if not isinstance(grime, (list, tuple)) or not grime else grime
    near = _zones(s, grime, 'olive_grime')
    if handled is not None and polish:
        hands = g.mul(handled, g.add(polish[0], g.mul(g.step(S.smudges(s), 0.0, 0.5), polish[1])), True)
        hands = g.mul(hands, g.inv(g.step(S.hollows(s), 0.30, 0.80)), True)
        colour_ = g.mix(g.mul(hands, polish_amount, True), colour_, g.times(colour_, polish_darken))
        rough = g.mixf(hands, rough, g.add(polish_rough, g.mul(g.sub(s.n_med, 0.5), 0.10)))
    if near is not None:
        rec = g.maxf(g.maxf(g.step(s.cavity, 0.05, 0.35), g.step(s.ao, 0.95, 0.60)), g.mul(g.step(S.hollows(s), 0.30, 0.80), 0.8))
        dirt = g.mul(g.mul(near, g.add(0.30, g.mul(rec, 0.70))), g.add(0.55, g.mul(s.n_med, 0.8)), True)
        colour_ = g.mix(g.mul(dirt, grime_amount, True), colour_, g.times(colour_, grime_tint))
        rough = g.add(rough, g.mul(dirt, grime_rough))
    return S.Layer(colour_, rough, lay.metal, lay.height)


def rubber(s, colour=(0.010, 0.010, 0.011), worn=(0.024, 0.024, 0.026), matt=(0.90, 0.84), mottle=0.45, textured=DEFAULT,
           exposure=1.0, recess=1.0, vary=0.4, vary_broad=None, texture='rubber', texture_cm=None, texture_tone=0.12, texture_relief=1.1, texture_rough=0.0):
    """Black rubber (butt pads, cheek pads, overmoulded grip inserts): matt, the driest thing on the gun, never polished (no
    `handled`: hands made a pad's top glossy and pale, an insert duct-tape grey), the `rubber` set with no glossier high
    spots. vary_broad: as moulded_polymer's. textured: where it is stippled, [Zone] or a mask; DEFAULT: the weapon's `rubber_textured` list (its own, so the
    polymer's `textured` stipple stays off the rubber)."""
    if textured is DEFAULT:
        textured = getattr(s.weapon, 'rubber_textured', None) or None
    textured = _zones(s, textured, 'rubber_textured')
    tex = _painted(s, texture, texture_cm, texture_tone, texture_relief, texture_rough, grain=True)
    return S.polymer(s, colour=colour, worn=worn, matt=matt, mottle=mottle, textured=textured, exposure=exposure, recess=recess,
                     vary=vary, vary_broad=vary_broad, **tex)


def anodised_alloy(s, finish='anodized', blue=((0.013, 0.014, 0.014), (0.026, 0.027, 0.027)), gloss=((0.40, 0.50), (0.22, 0.32), (0.40, 0.48)),
                   thin=((0.24, 0.245, 0.25), 0.0, 0.34), edges=1.15, rust=0.0, cloud=0.0, handled=DEFAULT, exposure=1.0, recess=1.0,
                   vary=0.45, texture='anodised', texture_cm=(2.0, 2.0), texture_tone=0.10, texture_relief=0.6, texture_rough=0.03,
                   tops=DEFAULT, slides=DEFAULT, sparkle=0.34, bare=None, dust=1.0, corners=1.0, dust_off=None, corners_off=None, serrated=None, serrated_ends=None, serrated_metal=0.4, serrated_colour=SERRATED_COLOUR, serrated_rough=SERRATED_ROUGH, **over):
    """Satin black hard-anodised alloy (a top cover, a rail, a receiver): worn to thin bright lines on its corners and round
    what is handled, satin smudges along its long faces (`vary`), the `anodised` bead-blast at 2 cm a tile (at its own 4 cm it
    read as woven cloth), then black_metal_life: scratches where `slides` run, the bead-blast's sparkle, bright wear on the
    corners of `tops`, dust in its slots. Any other worn_steel argument passes through (**over).
    dust, corners, dust_off, corners_off, serrated, serrated_ends, serrated_metal, serrated_colour, serrated_rough: black_metal_life's (turn the dust and the corner
    line down or off in general or in a zone; anti-glare serrated faces)."""
    handled = s.handled if handled is DEFAULT else _zones(s, handled, 'finish_alloy_handled')
    tex = _painted(s, texture, texture_cm, texture_tone, texture_relief, texture_rough)
    lay = S.steel(s, finish, blue=blue, gloss=gloss, thin=thin, edges=edges, rust=rust, cloud=cloud, handled=handled, exposure=exposure,
                  recess=recess, vary=vary, **dict(tex, **over))
    return black_metal_life(s, lay, 'alloy', tops=tops, slides=slides, bare=bare, sparkle=sparkle, dust=dust, corners=corners, dust_off=dust_off, corners_off=corners_off, serrated=serrated, serrated_ends=serrated_ends,
                           serrated_metal=serrated_metal, serrated_colour=serrated_colour, serrated_rough=serrated_rough)


def phosphate_parts(s, finish='parkerized', bright=DEFAULT, dark=DEFAULT, gloss=((0.46, 0.56), (0.22, 0.32), (0.40, 0.50)),
                    thin=((0.150, 0.152, 0.140), 0.70, 0.40), handled=DEFAULT, exposure=1.0, recess=1.0, vary=1.0,
                    texture='phosphate', texture_cm=None, texture_tone=0.12, texture_relief=0.8, texture_rough=0.04,
                    tops=DEFAULT, bare=None, dust=1.0, corners=1.0, dust_off=None, corners_off=None, serrated=None, serrated_ends=None, serrated_metal=0.4, serrated_colour=SERRATED_COLOUR, serrated_rough=SERRATED_ROUGH, **over):
    """Oiled manganese phosphate on the small steel parts (hardware, trigger, controls, sights), with the `bright` kind left
    bare polished and the `dark` kind black (DEFAULT: the weapon's kinds of those names, when it has them): the sheen steel
    hardware has, not a dry grey, the `phosphate` crystals under the wear, then black_metal_life's bright wear on the top
    corners of `tops` (sight ears, rail lands; DEFAULT: faces that look up) and dust in the slots. finish: the named
    surface.STEEL set under it; **over: any other worn_steel argument. dust, corners, dust_off, corners_off, serrated,
    serrated_ends, serrated_metal, serrated_colour, serrated_rough: black_metal_life's (the dust and the corner line down or off, serrated faces)."""
    kinds = S.B.kinds_of(s.weapon)
    bright = (s.mask('bright') if 'bright' in kinds else None) if bright is DEFAULT else bright
    dark = (s.mask('dark') if 'dark' in kinds else None) if dark is DEFAULT else dark
    handled = s.handled if handled is DEFAULT else _zones(s, handled, 'finish_parts_handled')
    tex = _painted(s, texture, texture_cm, texture_tone, texture_relief, texture_rough)
    lay = S.steel(s, finish, bright=bright, dark=dark, gloss=gloss, thin=thin, handled=handled, exposure=exposure, recess=recess,
                  vary=vary, **dict(tex, **over))
    return black_metal_life(s, lay, 'sights', tops=tops, bare=bare, dust=dust, corners=corners, dust_off=dust_off, corners_off=corners_off, serrated=serrated, serrated_ends=serrated_ends,
                           serrated_metal=serrated_metal, serrated_colour=serrated_colour, serrated_rough=serrated_rough)


def barrel_phosphate(s, finish='phosphate_black', blue=((0.022, 0.023, 0.022), (0.035, 0.036, 0.034)), gloss=((0.40, 0.50), (0.24, 0.32), (0.40, 0.50)),
                     coat=0.0, thin=((0.080, 0.081, 0.078), 0.55, 0.46), edges=0.7, rust=0.3, handled=DEFAULT, exposure=1.0, recess=1.0,
                     vary=1.0, texture='phosphate', texture_cm=None, texture_tone=0.12, texture_relief=0.8, texture_rough=0.04,
                     muzzle_x=DEFAULT, fouling_from=DEFAULT, device_len=4.4, soot=(0.009, 0.0085, 0.008), soot_rough=0.72, **over):
    """Dark manganese phosphate for a barrel and its muzzle device: a little drier than a blued barrel (a glossy procedural
    black read as plastic), as metal (coat 0), with the phosphate crystals, and carbon fouling in the device's slots and
    pockets (occlusion, cavities, groove floors) and on its crown. The fouled stretch runs along +X from `fouling_from` to
    `muzzle_x` (cm); DEFAULT: the weapon's Muzzle socket, and `device_len` cm behind it. No soot film over the outside (a matt
    film read paler in the studio light) and no heat tint (it read as a ring of rust)."""
    g = s.g
    handled = s.handled if handled is DEFAULT else _zones(s, handled, 'finish_barrel_handled')
    tex = _painted(s, texture, texture_cm, texture_tone, texture_relief, texture_rough)
    lay = S.steel(s, finish, blue=blue, gloss=gloss, coat=coat, thin=thin, edges=edges, rust=rust, handled=handled, exposure=exposure,
                  recess=recess, vary=vary, **dict(tex, **over))
    if muzzle_x is DEFAULT:
        muzzle_x = _socket_x(s.weapon, 'Muzzle')
    if muzzle_x is None:
        return lay
    if fouling_from is DEFAULT:
        fouling_from = muzzle_x - device_len
    colour, rough, metal = lay.colour, lay.rough, lay.metal
    x, _y, _z = g.xyz(s.pos)
    nx = g.xyz(g.new('ShaderNodeNewGeometry').outputs['True Normal'])[0]
    device = g.step(x, fouling_from - 0.05, fouling_from + 0.15)
    pocket = g.maxf(g.maxf(g.step(s.ao, 0.92, 0.55), g.step(s.cavity, 0.05, 0.35)), g.step(S.hollows(s), 0.25, 0.70))
    crown = g.mul(g.step(x, muzzle_x - 0.35, muzzle_x - 0.02), g.step(nx, 0.3, 0.7))
    dirt = g.mul(g.mul(device, g.maxf(pocket, crown)), g.add(0.55, g.mul(s.n_med, 0.7)), True)
    colour = g.mix(g.mul(dirt, 0.90, True), colour, soot)
    rough = g.mixf(dirt, rough, soot_rough)
    metal = g.mixf(g.mul(dirt, 0.7, True), metal, 0.0)
    return S.Layer(colour, rough, metal, lay.height)


def sheet_magazine(s, finish='phosphate_black', blue=((0.018, 0.018, 0.019), (0.032, 0.032, 0.033)), black=((0.012, 0.012, 0.013), (0.024, 0.024, 0.025)),
                   gloss=((0.50, 0.60), (0.22, 0.32), (0.44, 0.54)), coat=0.0, thin=((0.050, 0.051, 0.050), 0.55, 0.50), edges=0.8,
                   handled=DEFAULT, exposure=1.0, recess=1.0, vary=0.3, texture='phosphate', texture_cm=None, texture_tone=0.12,
                   texture_relief=0.8, texture_rough=0.04, **over):
    """A dark sheet-steel magazine: black satin METAL (coat 0: as a dielectric its 4 % sheen read mid-grey on the broad sides
    in the studio light; a base this dark is under the physical range for a metal and may read as a hole in Unreal), worn only
    where it is set down and on its edges. handled: where it is set down, [Zone] or a mask; DEFAULT: the faces that look down
    (its floor plate), not the weapon's `handled` zones (two of those covering a whole magazine made it grey)."""
    handled = _down(s) if handled is DEFAULT else _zones(s, handled, 'mag_floor')
    tex = _painted(s, texture, texture_cm, texture_tone, texture_relief, texture_rough)
    return S.steel(s, finish, blue=blue, black=black, gloss=gloss, coat=coat, thin=thin, edges=edges, handled=handled, exposure=exposure,
                   recess=recess, vary=vary, **dict(tex, **over))


def bright_steel(s, finish='stainless', handled=DEFAULT, exposure=1.0, recess=1.0, vary=0.6, texture=None, texture_cm=None,
                 texture_tone=0.10, texture_relief=0.6, texture_rough=0.03, **over):
    """Bare bright steel (a bolt, a bolt carrier, pins, a stainless barrel): surface.STEEL's `finish` (stainless: brushed along
    the weapon, light clouds, few scratches, a little grime in the cuts) with the wear by use and exposure. Its colour, gloss,
    brush and so on are the named set's; pass any worn_steel argument to change one (**over). texture: a texforge set to lay
    under it, none by default (a turned set's rings are under a texel on most guns, PLAYBOOK "Textures and look")."""
    handled = s.handled if handled is DEFAULT else _zones(s, handled, 'finish_bright_handled')
    tex = _painted(s, texture, texture_cm, texture_tone, texture_relief, texture_rough)
    return S.steel(s, finish, handled=handled, exposure=exposure, recess=recess, vary=vary, **dict(tex, **over))


FINISHES = {
    'moulded_polymer': moulded_polymer,
    'rubber': rubber,
    'anodised_alloy': anodised_alloy,
    'phosphate_parts': phosphate_parts,
    'barrel_phosphate': barrel_phosphate,
    'sheet_magazine': sheet_magazine,
    'bright_steel': bright_steel,
}

# the texforge set each finish lays on by default (docs/look.md, "Named finishes"); a weapon loads them in images() with sets()
SETS = {'moulded_polymer': 'poly_mould', 'rubber': 'rubber', 'anodised_alloy': 'anodised', 'phosphate_parts': 'phosphate',
        'barrel_phosphate': 'phosphate', 'sheet_magazine': 'phosphate', 'bright_steel': None}


def sets(*names):
    """The texforge sets the named finishes lay on by default, each once, for Weapon.images(): S.texforge_sets(self, *F.sets(...))."""
    out = []
    for n in names:
        if n not in FINISHES:
            raise KeyError('no finish %r (finish.FINISHES: %s)' % (n, ', '.join(sorted(FINISHES))))
        if SETS[n] and SETS[n] not in out:
            out.append(SETS[n])
    return out


def make(s, name, **over):
    """One named finish as a Layer: FINISHES[name](s, **over)."""
    if name not in FINISHES:
        raise KeyError('no finish %r (finish.FINISHES: %s)' % (name, ', '.join(sorted(FINISHES))))
    return FINISHES[name](s, **over)


def look(s, rows):
    """The whole look from a small table, stacked in order (surface.stack): each row (kind, finish[, overrides[, where]]):
    kind a surface kind (Weapon.kinds / bake.KINDS); finish a name in FINISHES or a ready Layer (S.brass(s), your own recipe);
    overrides a dict of that finish's arguments (or None); where (optional) a mask that narrows the kind to a place (a zone,
    part_zone(), a position test). A row whose where is given as None is left out: the place it names is not on this weapon
    (part_zone() of a part it has not got). The FIRST row is the base: it fills everything, whatever its kind (normally the
    steel)."""
    g = s.g
    layers = []
    for row in rows:
        kind, fin = row[0], row[1]
        over = row[2] if len(row) > 2 and row[2] else {}
        if len(row) > 3 and row[3] is None:
            print('[texture] finish.look: %s %s left out, its place is not on this weapon' % (kind, fin if isinstance(fin, str) else 'layer'))
            continue
        where = row[3] if len(row) > 3 else None
        layer = fin if isinstance(fin, S.Layer) else make(s, fin, **over)
        mask = s.mask(kind) if where is None else g.mul(s.mask(kind), where)
        layers.append((mask, layer))
    return S.stack(s, layers[0][1], *layers[1:])
