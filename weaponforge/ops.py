"""weaponforge: calling Blender operators from anywhere.

A script started from a timer or from the MCP bridge has no area in its context, and `blender -b` has no window at all. run() gives
an operator a 3D viewport when there is one to give, and calls it bare otherwise (every operator used here works that way).
"""
import bpy


def run(op, **kw):
    ctx = bpy.context
    if ctx.area is not None:
        return op(**kw)
    windows = ctx.window_manager.windows
    if not windows:                      # background mode
        return op(**kw)
    win = windows[0]
    area = next((a for a in win.screen.areas if a.type == 'VIEW_3D'), None)
    if area is None:
        return op(**kw)
    region = next(r for r in area.regions if r.type == 'WINDOW')
    with ctx.temp_override(window=win, area=area, region=region):
        return op(**kw)


def only(objs, active=None):
    """Select exactly objs (unhidden), with `active` or the first of them active."""
    bpy.context.view_layer.update()
    for o in bpy.context.view_layer.objects:
        if o is not None:
            o.select_set(False)
    for o in objs:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def background():
    return bpy.app.background
