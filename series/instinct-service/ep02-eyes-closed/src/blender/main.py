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
    ed = os.path.join(ROOT, "episodes", ep)
    script = load(os.path.join(ed, "script.json"))
    # episode-specific props/cameras/grips (e.g. EP02 tank) layered over the reusable set
    pj = os.path.join(ed, "props.json")
    if os.path.exists(pj):
        P = load(pj)
        for k in ("props", "cameras", "grips", "anchors"):
            setcfg.setdefault(k, {}).update(P.get(k, {}))
        setcfg["extras"] = P.get("extras", {})
        if "phone" in setcfg["extras"]:
            setcfg["phone_tex"] = os.path.join(bd, "tex", "phone.png")
    # clean factory scene
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    tex = {s["id"]: os.path.join(bd, "tex", f"screen_{s['id']}.png") for s in script["screens"]}
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
    for name, a in zip(S.get("ripple_mats", []), vals.get("ripple_alpha", [])):
        mats[(name, "Principled BSDF", "Alpha")] = a
    return en, mats


def project(cam, p, W=1080, H=1920):
    """World point -> pixel position for the vertical-fit 36 mm camera (None if behind the camera)."""
    from mathutils import Vector
    q = cam["M"].inverted() @ Vector(p)
    if q.z >= -1e-4:
        return None
    f = cam["lens"]
    x = 0.5 + f * q.x / -q.z / (36.0 * W / H)
    y = 0.5 + f * q.y / -q.z / 36.0
    return [round(x * W, 1), round((1 - y) * H, 1), round(-q.z, 3)]


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
    track = []
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
        track.append({k: project(cam, p) for k, p in vals.get("track", {}).items()})
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
    with open(os.path.join(ctx["bd"], "track.json"), "w", encoding="utf-8") as fh:
        json.dump(track, fh)
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


def render(ep, start, end, out="frames", pct=None, step=1, samples=None):
    sc = bpy.context.scene
    if pct:
        sc.render.resolution_percentage = pct
    if samples:
        sc.eevee.taa_render_samples = samples
    bd = os.path.join(ROOT, "build", ep)
    out = os.path.join(bd, out)
    os.makedirs(out, exist_ok=True)
    for f in range(start, end + 1, step):
        p = os.path.join(out, f"f_{f:04d}.png")
        if os.path.exists(p) and os.path.getsize(p) > 0:
            continue
        sc.frame_set(f)
        sc.render.filepath = p
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"frame {f} {time.time() - t0:.2f}s", flush=True)


def probe(ep, step=0.5):
    """Numeric acceptance for props/contact: every `step` s, report Patrick's eye depth, bill tip vs gravel, and any
    character/prop vertex that crosses a tank wall below the rim or sinks into the bar, stool or tank floor."""
    ctx = build(ep)
    S = ctx["S"]
    tk = S.get("tank")
    fps = ctx["tl"]["fps"]
    n = ctx["tl"]["frames"]
    every = max(1, int(round(step * fps)))
    head_parts = {"pat_head", "pat_cheeks", "pat_bill_up", "pat_shield", "pat_bill_lo", "pat_neck", "pat_nostril-1", "pat_nostril1",
                  "pat_eyeL", "pat_eyeR", "pat_eyehlL", "pat_eyehlR", "pat_lidL", "pat_lidR", "pat_llidL", "pat_llidR", "pat_browL", "pat_browR"}
    may_enter = head_parts | {"prop_net", "s0", "s1", "s2", "s3", "pat_pawL", "pat_pawR", "pat_foL", "pat_foR"} | {f"pat_claw{s}{k}" for s in "LR" for k in range(5)}
    pat = [ob for ob, _ in ctx["pat"].parts]
    bear = [ob for ob, _ in ctx["bear"].parts]
    movers = pat + bear + [S["props"][k] for k in ("net", "towel", "phone", "s0", "s1", "s2", "s3") if k in S["props"]]
    report = []
    for f in range(n):
        out, vals, cam = ctx["perf"].evaluate(f)
        if f % every:
            continue
        t = f / fps
        issues = []
        if tk:
            (cx, cy), (w, d, h), z0 = tk["center"], tk["size"], tk["z0"]
            x0, x1, y0, y1, rim = cx - w / 2, cx + w / 2, cy - d / 2, cy + d / 2, z0 + h
            for ob in movers:
                if ob not in out:
                    continue
                M = out[ob]
                vs = [M @ v.co for v in ob.data.vertices]
                low = [v for v in vs if v.z < rim - 0.002 and x0 - 0.012 < v.x < x1 + 0.012 and y0 - 0.012 < v.y < y1 + 0.012]
                if not low:
                    continue
                inside = [v for v in low if x0 + 0.006 < v.x < x1 - 0.006 and y0 + 0.006 < v.y < y1 - 0.006]
                if ob.name not in may_enter:
                    worst = min(low, key=lambda v: v.z)
                    issues.append(f"{ob.name} below rim at tank ({len(low)} v, deepest {rim - worst.z:.3f} at x{worst.x:.3f} y{worst.y:.3f})")
                elif len(inside) != len(low):
                    bad = [v for v in low if v not in inside]
                    worst = max(bad, key=lambda v: rim - v.z)
                    issues.append(f"{ob.name} crosses tank glass ({len(bad)} v, deepest {rim - worst.z:.3f} below rim at x{worst.x:.3f} y{worst.y:.3f})")
                if any(v.z < tk["floor"] - 0.003 for v in inside):
                    issues.append(f"{ob.name} into gravel")
        tr = vals["track"]
        row = dict(t=round(t, 2), shot=cam["shot"], eye_z=round(tr["eye"][2], 3), bill_z=round(tr["bill"][2], 3), issues=issues)
        if tk:
            row["eye_depth"] = round(tk["top"] - tr["eye"][2], 3)
        report.append(row)
        print(json.dumps(row))
    with open(os.path.join(ctx["bd"], "probe.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=0)


if __name__ == "__main__":
    pos, opts = args()
    if pos[1] == "probe":
        probe(pos[0], float(opts.get("step", 0.5)))
        sys.exit(0)
    ep, mode = pos[0], pos[1]
    if mode == "stills":
        stills(ep, pos[2], int(opts.get("pct", 50)), int(opts.get("samples", 16)))
    elif mode == "bake":
        bake(ep)
    elif mode == "render":
        render(ep, int(pos[2]), int(pos[3]), opts.get("out", "frames"), int(opts["pct"]) if "pct" in opts else None,
               int(opts.get("step", 1)), int(opts["samples"]) if "samples" in opts else None)
