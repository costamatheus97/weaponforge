"""weaponforge: a variant that changes its base's dimensions (pure Python, no bpy).

A variant that only ADDS to its base imports the base's modules and extends them (a scoped or a suppressed copy). That
stops working the moment the variant has to MOVE one of the base's numbers. params.py works every derived value out as it is
imported, so the base's module has one MUZZLE_X, and everything that follows from it (where the rib ends, where the bead
stands, the sockets, the checks) is already a number; and the base's parts.py and weapon.py read that one module.

`rerun` gives the variant its own copy instead. It runs one of the base's three files again, inside the variant's module of
the same name, with some of the file's top-level values pinned to the variant's. Everything derived from a pinned value
follows, because the file works it out afresh. The `from . import params as P` in the base's parts.py and weapon.py then
finds the VARIANT's params, because the code now runs in the variant's package.

    # weapons/assault_g3_short/params.py
    from weaponforge.variant import rerun
    rerun('assault_g3', 'params', globals(), NOSE_X=17.0)        # the same file with the handguard 4 cm shorter
    STUB_X = 15.5                                                  # then the variant's own numbers

    # weapons/assault_g3_short/parts.py
    rerun('assault_g3', 'parts', globals())                        # every builder, reading the variant's params
    def shell(coll, hp=False): ...                                 # then replace or add builders
    BUILDERS['shell'] = shell

    # weapons/assault_g3_short/weapon.py
    rerun('assault_g3', 'weapon', globals())                       # class AssaultG3 again, built on the variant's params
    class AssaultG3Short(AssaultG3): ...
    WEAPON = AssaultG3Short()

(An illustration: no variant ships. Whether a given pin gives a sound weapon is for the variant's own checks to say.)

Rules:
  * Pin only names the base's file assigns ONCE, at its top level, as `NAME = value` or as one of `A, B = x, y`. Anything
    else stops with an error that names it: a mistyped name would otherwise change nothing and say nothing.
  * Change the base's numbers only by pinning them. A name the variant assigns AFTER the rerun is seen by the files that run
    later (parts.py, weapon.py read the module), but by nothing params.py had already worked out from the old value.
  * A function the variant defines again after the rerun replaces the base's for callers that look it up by name when they
    run (PT.stock_seam() in weapon.py). A table filled before that (BUILDERS) still holds the base's: put the new one in.
  * The base is not touched: its own modules, its .blend and its assets stay what they were. A later change to the base's
    files reaches the variant the next time the variant is built.
"""
import ast
import os

TOOL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ('params', 'parts', 'weapon')


def _literal(name, value):
    try:
        node = ast.parse(repr(value), mode='eval').body
        ast.literal_eval(node)
    except (ValueError, SyntaxError):
        raise ValueError('rerun: %s=%r is not a plain value (a number, a string, a tuple or list of them)' % (name, value))
    return node


def _targets(node):
    """Every name a top-level statement assigns."""
    if isinstance(node, ast.Assign):
        heads = node.targets
    elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
        heads = [node.target]
    else:
        return []
    return [n.id for head in heads for n in ast.walk(head) if isinstance(n, ast.Name)]


def rerun(base_id, name, into, **pins):
    """Run weapons/<base_id>/<name>.py inside the module whose globals() is `into`, with each top-level NAME in pins set to
    the given value instead of the file's own. name: 'params', 'parts' or 'weapon'."""
    if name not in FILES:
        raise ValueError('rerun: %r is not one of %s' % (name, ', '.join(FILES)))
    path = os.path.join(TOOL, 'weapons', base_id, name + '.py')
    with open(path, encoding='utf-8') as f:
        tree = ast.parse(f.read(), path)
    done = dict.fromkeys(pins, 0)
    for node in tree.body:
        hit = [t for t in _targets(node) if t in pins]
        if not hit:
            continue
        target = node.targets[0] if isinstance(node, ast.Assign) and len(node.targets) == 1 else None
        if isinstance(target, ast.Name):
            node.value = ast.copy_location(_literal(target.id, pins[target.id]), node.value)
            done[target.id] += 1
        elif isinstance(target, ast.Tuple) and isinstance(node.value, ast.Tuple) and len(target.elts) == len(node.value.elts) \
                and all(isinstance(e, ast.Name) for e in target.elts):
            for i, elt in enumerate(target.elts):
                if elt.id in pins:
                    node.value.elts[i] = ast.copy_location(_literal(elt.id, pins[elt.id]), node.value.elts[i])
                    done[elt.id] += 1
        else:
            raise ValueError('rerun: %s line %d assigns %s in a way that cannot be pinned (write it as NAME = value there)'
                             % (path, node.lineno, ', '.join(hit)))
    wrong = ['%s (%s)' % (k, 'not assigned at the top level' if n == 0 else 'assigned %d times' % n) for k, n in done.items() if n != 1]
    if wrong:
        raise ValueError('rerun: cannot pin in %s: %s' % (path, '; '.join(wrong)))
    ast.fix_missing_locations(tree)
    doc = into.get('__doc__')
    exec(compile(tree, path, 'exec'), into)
    into['__doc__'] = doc            # the variant's own docstring, not the base file's
    return into
