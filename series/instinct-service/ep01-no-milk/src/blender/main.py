"""Blender entry point.

  blender -b --factory-startup -P src/blender/main.py -- <ep> stills  <t1,t2,...|cams> [--pct 50] [--samples 16]
  blender -b --factory-startup -P src/blender/main.py -- <ep> bake                     (writes build/<ep>/scene.blend)
  blender -b build/<ep>/scene.blend -P src/blender/main.py -- <ep> render <start> <end>   (renders PNG frames)

Everything is driven by build/<ep>/timeline.json (one master timeline, fixed fps, frame-exact).
"""
import json
import math
import os
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

import lp  # noqa: E402
import set_bar  # noqa: E402
from characters import Bear, Patrick  # noqa: E402
from perform import Performance  # noqa: E402


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts = {}
    pos = []
    i = 0
    while i < len(a):
        if a[i].startswith("--"):
            opts[a[i][2:]] = a[i + 1]
            i += 2
        else:
            pos.append(a[i])
            i += 1
    return pos, opts


def setup_render(scene, series, pct=100, samples=32):
    v = series["video"]
    r = scene.render
    r.engine = "BLENDER_EEVEE"
    r.resolution_x, r.resolution_y = v["width"], v["height"]
    r.resolution_percentage = pct
    r.fps = v["fps"]
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGB"
    r.image_settings.color_depth = "8"
    r.film_transparent = False
    e = scene.eevee
    e.taa_render_samples = samples
    e.use_shadows = True
    e.shadow_ray_count = 1
    e.shadow_step_count = 6
    e.shadow_pool_size = "1024"
    e.shadow_resolution_scale = 0.5
    # only the lights that shape the characters cast shadows; practicals and fills are shadowless
    casters = ("pendant0", "pendant1", "pendant2", "key_warm", "window_back_light", "window_front_light", "moon_sun", "uv_spot")
    for ob in scene.objects:
        if ob.type == "LIGHT":
            ob.data.use_shadow = ob.name in casters
    try:
        e.use_raytracing = False
    except Exception:
        pass
    vs = scene.view_settings
    vs.view_transform = "AgX"
    for look in ("AgX - Medium High Contrast", "Medium High Contrast", "AgX - Base Contrast"):
        try:
            vs.look = look
            break
        except Exception:
            continue
    vs.exposure = series["look"]["color_management"].get("exposure", 0.0)
    w = scene.world or bpy.data.worlds.new("World")
    scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.035, 0.028, 0.026, 1)
    bg.inputs["Strength"].default_value = 1.0


def build(ep):
    series = load(os.path.join(ROOT, "series", "series.json"))
    chars = load(os.path.join(ROOT, "series", "characters.json"))
    setcfg = load(os.path.join(ROOT, "series", "set_forest_bar.json"))
    bd = os.path.join(ROOT, "build", ep)
    tl = load(os.path.join(bd, "timeline.json"))
    # clean factory scene
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    tex = {s: os.path.join(bd, "tex", f"screen_{s}.png") for s in ("idle", "manager", "fee")}
    S = set_bar.build(setcfg, tex)
    pat = Patrick(chars["patrick"]["look"])
    bear = Bear(chars["bear"]["look"])
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.sensor_fit = "VERTICAL"
    cam_data.sensor_height = 36
    cam_data.dof.use_dof = True
    cam_data.clip_start = 0.03
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    cam.rotation_mode = "QUATERNION"
    perf = Performance(tl, setcfg, S, pat, bear)
    # base energies for multipliers
    base = {name: ob.data.energy for name, ob in S["lights"].items()}
    return dict(series=series, setcfg=setcfg, tl=tl, S=S, perf=perf, cam=cam, base=base, pat=pat, bear=bear, bd=bd)


def light_values(ctx, vals, door_angle):
    """-> {light_name: energy}, {material/node: value}"""
    S, base = ctx["S"], ctx["base"]
    L = vals["lights"]
    en = {}
    for name in S["lights"]:
        m = 1.0
        for key, mult in L.items():
            if name == key or name.startswith(key + "_") or (key == "pendant1" and name == "pendant_glow1"):
                m *= mult
        en[name] = base[name] * m
    uv = vals["uv"]
    en["uv_spot"] = 2.2 * uv
    en["fridge"] = 1.5 + 9.0 * min(1.0, door_angle / 40.0)
    mats = {("uv_tube", "uv_tube_emit", "Strength"): 0.4 + 14.0 * uv,
            ("bulb1", "emit", "Strength"): 25.0 * L.get("pendant1", 1.0)}
    for fur in ("pat_fur", "pat_belly"):
        mats[(fur, "uv_on", None)] = uv
        for i, c in enumerate("xyz"):
            mats[(fur, f"lamp_{c}", None)] = vals["beam_o"][i]
            mats[(fur, f"dir_{c}", None)] = vals["beam_d"][i]
    return en, mats


def apply_frame(ctx, f):
    out, vals, cam = ctx["perf"].evaluate(f)
    for ob, M in out.items():
        ob.matrix_world = M
    en, mats = light_values(ctx, vals, ctx["perf"].door_angle)
    for name, e in en.items():
        ctx["S"]["lights"][name].data.energy = e
    for (mname, node, inp), v in mats.items():
        n = bpy.data.materials[mname].node_tree.nodes[node]
        (n.outputs[0] if inp is None else n.inputs[inp]).default_value = v
    c = ctx["cam"]
    c.matrix_world = cam["M"]
    c.data.lens = cam["lens"]
    c.data.dof.focus_distance = cam["focus"]
    c.data.dof.aperture_fstop = cam["fstop"]
    return cam


def stills(ep, which, pct, samples):
    ctx = build(ep)
    sc = bpy.context.scene
    setup_render(sc, ctx["series"], pct, samples)
    outdir = os.path.join(ctx["bd"], "stills")
    os.makedirs(outdir, exist_ok=True)
    fps = ctx["tl"]["fps"]
    if which == "cams":
        apply_frame(ctx, 0)
        for name, p in ctx["setcfg"]["cameras"].items():
            ctx["tl"]["shots"] = [[0.0, name, {"push": 0}]]
            cam = ctx["perf"].camera(0.0)
            c = ctx["cam"]
            c.matrix_world, c.data.lens = cam["M"], cam["lens"]
            c.data.dof.focus_distance, c.data.dof.aperture_fstop = cam["focus"], cam["fstop"]
            sc.render.filepath = os.path.join(outdir, f"cam_{name}.png")
            bpy.ops.render.render(write_still=True)
        return
    times = sorted(float(x) for x in which.split(","))
    targets = {int(round(t * fps)) for t in times}
    for f in range(0, max(targets) + 1):
        cam = apply_frame(ctx, f)
        if f in targets:
            sc.frame_current = f
            sc.render.filepath = os.path.join(outdir, f"t{f / fps:05.2f}_{cam['shot']}.png")
            t0 = time.time()
            bpy.ops.render.render(write_still=True)
            print(f"still f{f} {cam['shot']} {time.time() - t0:.1f}s")


# ------------------------------------------------------------------ baking to keyframes
from bpy_extras import anim_utils  # noqa: E402


def write_fcurves(id_data, id_type, channels, n):
    """channels: {(data_path, index): [values per frame]}; constant channels are set without keys."""
    animated = {k: v for k, v in channels.items() if max(v) - min(v) > 1e-7}
    for (path, idx), v in channels.items():
        if (path, idx) not in animated:
            try:
                obj, prop = id_data.path_resolve(path.rsplit(".", 1)[0]) if "." in path else id_data, path.rsplit(".", 1)[-1]
                cur = getattr(obj, prop)
                if idx >= 0:
                    cur[idx] = v[0]
                else:
                    setattr(obj, prop, v[0])
            except Exception:
                animated[(path, idx)] = v
    if not animated:
        return
    ad = id_data.animation_data_create()
    act = bpy.data.actions.new(f"{id_data.name}_act")
    slot = act.slots.new(id_type=id_type, name=id_data.name)
    ad.action = act
    ad.action_slot = slot
    cb = anim_utils.action_ensure_channelbag_for_slot(act, slot)
    frames = list(range(n))
    for (path, idx), v in animated.items():
        fc = cb.fcurves.new(path, index=max(idx, 0))
        fc.keyframe_points.add(n)
        co = [x for pair in zip(frames, v) for x in pair]
        fc.keyframe_points.foreach_set("co", co)
        fc.keyframe_points.foreach_set("interpolation", [0] * n if path.endswith("hide_render") else [1] * n)
        fc.update()


def bake(ep):
    ctx = build(ep)
    sc = bpy.context.scene
    setup_render(sc, ctx["series"], 100, int(ctx["series"].get("render_samples", 32)))
    n = ctx["tl"]["frames"]
    sc.frame_start, sc.frame_end = 0, n - 1
    obj_ch, light_ch, mat_ch, cam_ch = {}, {}, {}, {}
    prevq = {}
    t0 = time.time()
    for f in range(n):
        out, vals, cam = ctx["perf"].evaluate(f)
        for ob, M in out.items():
            loc, q, s = M.decompose()
            pq = prevq.get(ob)
            if pq is not None and pq.dot(q) < 0:
                q = -q
            prevq[ob] = q
            d = obj_ch.setdefault(ob, {})
            for i in range(3):
                d.setdefault(("location", i), []).append(loc[i])
                d.setdefault(("scale", i), []).append(s[i])
            for i in range(4):
                d.setdefault(("rotation_quaternion", i), []).append(q[i])
        en, mats = light_values(ctx, vals, ctx["perf"].door_angle)
        for name, e in en.items():
            light_ch.setdefault(name, []).append(e)
        for key, v in mats.items():
            mat_ch.setdefault(key, []).append(v)
        loc, q, _ = cam["M"].decompose()
        pq = prevq.get("cam")
        if pq is not None and pq.dot(q) < 0:
            q = -q
        prevq["cam"] = q
        for i in range(3):
            cam_ch.setdefault(("location", i), []).append(loc[i])
        for i in range(4):
            cam_ch.setdefault(("rotation_quaternion", i), []).append(q[i])
        for k, v in (("lens", cam["lens"]), ("dof.focus_distance", cam["focus"]), ("dof.aperture_fstop", cam["fstop"])):
            cam_ch.setdefault(k, []).append(v)
    print(f"evaluated {n} frames in {time.time() - t0:.1f}s")
    for ob, d in obj_ch.items():
        ob.rotation_mode = "QUATERNION"
        write_fcurves(ob, "OBJECT", d, n)
    for name, v in light_ch.items():
        write_fcurves(ctx["S"]["lights"][name].data, "LIGHT", {("energy", -1): v}, n)
    by_mat = {}
    for (mname, node, inp), v in mat_ch.items():
        path = f'nodes["{node}"].outputs[0].default_value' if inp is None else f'nodes["{node}"].inputs["{inp}"].default_value'
        by_mat.setdefault(mname, {})[(path, -1)] = v
    for mname, ch in by_mat.items():
        write_fcurves(bpy.data.materials[mname].node_tree, "NODETREE", ch, n)
    cam = ctx["cam"]
    write_fcurves(cam, "OBJECT", {k: v for k, v in cam_ch.items() if isinstance(k, tuple)}, n)
    write_fcurves(cam.data, "CAMERA", {(k, -1): v for k, v in cam_ch.items() if isinstance(k, str)}, n)
    path = os.path.join(ctx["bd"], "scene.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    print(f"baked -> {path} ({time.time() - t0:.1f}s)")


def render(ep, start, end):
    sc = bpy.context.scene
    bd = os.path.join(ROOT, "build", ep)
    out = os.path.join(bd, "frames")
    os.makedirs(out, exist_ok=True)
    for f in range(start, end + 1):
        p = os.path.join(out, f"f_{f:04d}.png")
        if os.path.exists(p) and os.path.getsize(p) > 0:
            continue
        sc.frame_set(f)
        sc.render.filepath = p
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"frame {f} {time.time() - t0:.2f}s", flush=True)


if __name__ == "__main__":
    pos, opts = args()
    ep, mode = pos[0], pos[1]
    if mode == "stills":
        stills(ep, pos[2], int(opts.get("pct", 50)), int(opts.get("samples", 16)))
    elif mode == "bake":
        bake(ep)
    elif mode == "render":
        render(ep, int(pos[2]), int(pos[3]))
