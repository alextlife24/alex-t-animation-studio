"""Reusable set: night-time fine-dining forest bar. Dark wood, brass, amber light, cold blue forest windows.
Props are modelled in their own local frame (origin at the base, front = +Y) so the timeline can move them."""
import math
import random

import bpy
from mathutils import Matrix, Vector

import lp
from lp import T, box, cyl, emissive, hex_rgb, ico, mat, poly_prism

R = random.Random(11)


def M_place(pos, yaw=0.0):
    return Matrix.Translation(pos) @ Matrix.Rotation(math.radians(yaw), 4, "Z")


def materials():
    return dict(
        wood_dark=mat("wood_dark", "#2a1810", rough=0.7),
        wood_mid=mat("wood_mid", "#43271a", rough=0.72),
        wood_panel=mat("wood_panel", "#3a2216", rough=0.78),
        wood_panel2=mat("wood_panel2", "#33200f", rough=0.8),
        bar_top=mat("bar_top", "#3b2014", rough=0.42, spec=0.45, coat=0.25),
        floor=mat("floor", "#24150e", rough=0.6),
        floor2=mat("floor2", "#2c1a11", rough=0.6),
        ceiling=mat("ceiling", "#170e0a", rough=0.9),
        brass=mat("brass", "#c08c3e", rough=0.38, metallic=0.85, spec=0.5),
        brass_dark=mat("brass_dark", "#7d5a2a", rough=0.45, metallic=0.8),
        leather=mat("leather", "#4a1d17", rough=0.55),
        steel=mat("steel", "#3a3d42", rough=0.5, metallic=0.6),
        black=mat("black", "#0e0f12", rough=0.6),
        glass=mat("glass", "#eef7fa", rough=0.04, spec=1.0, alpha=0.42, coat=1.0),
        glass_amber=mat("glass_amber", "#8a4b12", rough=0.15, spec=0.7, alpha=0.8),
        glass_green=mat("glass_green", "#1f3b22", rough=0.15, spec=0.7, alpha=0.85),
        glass_clear=mat("glass_clear", "#b7c7c9", rough=0.12, spec=0.8, alpha=0.35),
        cloth=mat("cloth", "#e7e0d2", rough=0.95),
        shade=mat("shade", "#a8611c", rough=0.5, emit="#ffb35c", emit_strength=1.2, alpha=0.95),
        bulb=emissive("bulb", "#ffd08a", 25.0),
        candle=mat("candle", "#efe6d2", rough=0.9),
        flame=emissive("flame", "#ffb44a", 18.0),
        led_warm=emissive("led_warm", "#ffb766", 8.0),
        tree1=mat("tree1", "#25486e", rough=0.95),
        tree2=mat("tree2", "#2f5a85", rough=0.95),
        tree3=mat("tree3", "#3e6c97", rough=0.95),
        tree_far=mat("tree_far", "#5579a3", rough=0.95, emit="#3b5d88", emit_strength=0.25),
        ground=mat("ground", "#1d3550", rough=1.0),
        moon=emissive("moon", "#dfeaff", 6.0),
        lemon=mat("lemon", "#d9b62e", rough=0.7),
        cheese=mat("cheese", "#e6c565", rough=0.8),
        label_blue=mat("label_blue", "#2f5d8c", rough=0.7),
        paper=mat("paper", "#e9dfc8", rough=0.95),
        menu_cover=mat("menu_cover", "#2b3a2e", rough=0.6),
        fridge_light=emissive("fridge_light", "#e9f4ff", 4.0),
    )


def sky(col):
    """Gradient backdrop behind both windows (emissive, unaffected by interior light)."""
    m = bpy.data.materials.new("sky")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = hex_rgb("#3a5f88")
    ramp.color_ramp.elements[1].position = 0.55
    ramp.color_ramp.elements[1].color = hex_rgb("#081428")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], em.inputs[0])
    em.inputs["Strength"].default_value = 0.55
    nt.links.new(em.outputs[0], out.inputs[0])
    for y, nm in ((26, "sky_back"), (-28, "sky_front")):
        ob = box(nm, (70, 0.2, 30), (0, y, 12), material=m, col=col)
    return m


def forest(col, M, sign, seed):
    """Low-poly conifers outside a window. sign=+1 behind the back wall, -1 beyond the front wall."""
    r = random.Random(seed)
    box(f"ground_{seed}", (40, 24, 0.2), (0, sign * 14, -0.1), material=M["ground"], col=col)
    trees = []
    for i in range(70):
        y = sign * r.uniform(3.2, 22)
        x = r.uniform(-14, 14)
        d = abs(y)
        h = r.uniform(3.5, 7.5) * (1 + d / 30)
        rad = h * r.uniform(0.22, 0.3)
        m = M["tree1"] if d < 7 else M["tree2"] if d < 12 else M["tree3"] if d < 17 else M["tree_far"]
        layers = r.choice((2, 3))
        for k in range(layers):
            z0 = h * (0.18 + 0.24 * k)
            hh = h * (0.55 - 0.08 * k)
            trees.append(cyl(f"tree_{seed}_{i}_{k}", r1=rad * (1 - 0.22 * k), r2=0.0, h=hh, verts=r.choice((5, 6, 7)),
                             loc=(x, y, z0), rot=(0, 0, r.uniform(0, 60)), material=m, col=col, jitter=0.06))
        trees.append(cyl(f"trunk_{seed}_{i}", 0.12 * h / 5, h=h * 0.25, verts=5, loc=(x, y, 0), material=M["tree1"], col=col))
    lp.join(f"forest_{seed}", trees)


def window_wall(name, col, M, y, x_range, z_range, x_span=(-3.3, 3.3), facing=1):
    """Wall along X at depth y with a rectangular window opening + brass/wood frame and mullions."""
    t = 0.12
    H = 3.4
    (wx0, wx1), (wz0, wz1) = x_range, z_range
    parts = []
    parts.append(box(f"{name}_L", (wx0 - x_span[0], t, H), ((x_span[0] + wx0) / 2, y, H / 2), material=M["wood_panel"], col=col))
    parts.append(box(f"{name}_R", (x_span[1] - wx1, t, H), ((wx1 + x_span[1]) / 2, y, H / 2), material=M["wood_panel"], col=col))
    parts.append(box(f"{name}_B", (wx1 - wx0, t, wz0), ((wx0 + wx1) / 2, y, wz0 / 2), material=M["wood_panel"], col=col))
    parts.append(box(f"{name}_T", (wx1 - wx0, t, H - wz1), ((wx0 + wx1) / 2, y, (wz1 + H) / 2), material=M["wood_panel"], col=col))
    wall = lp.join(name, parts)
    # vertical panel seams (faceted board look)
    seams = []
    x = x_span[0] + 0.25
    while x < x_span[1]:
        if not (wx0 - 0.05 < x < wx1 + 0.05):
            seams.append(box(f"{name}_seam{x:.2f}", (0.035, 0.02, 3.4), (x, y - facing * 0.07, 1.7),
                             material=M["wood_panel2"], col=col))
        x += 0.5 + R.uniform(-0.05, 0.05)
    seams.append(box(f"{name}_rail", (x_span[1] - x_span[0], 0.03, 0.04), (0, y - facing * 0.075, 0.95), material=M["brass_dark"], col=col))
    seams.append(box(f"{name}_base", (x_span[1] - x_span[0], 0.04, 0.16), (0, y - facing * 0.08, 0.08), material=M["wood_dark"], col=col))
    lp.join(f"{name}_trim", seams)
    # frame + mullions
    fr = []
    fw = 0.06
    fr.append(box(f"{name}_f1", (wx1 - wx0 + 2 * fw, 0.16, fw), ((wx0 + wx1) / 2, y, wz0 - fw / 2), material=M["wood_dark"], col=col))
    fr.append(box(f"{name}_f2", (wx1 - wx0 + 2 * fw, 0.16, fw), ((wx0 + wx1) / 2, y, wz1 + fw / 2), material=M["wood_dark"], col=col))
    fr.append(box(f"{name}_f3", (fw, 0.16, wz1 - wz0), (wx0 - fw / 2, y, (wz0 + wz1) / 2), material=M["wood_dark"], col=col))
    fr.append(box(f"{name}_f4", (fw, 0.16, wz1 - wz0), (wx1 + fw / 2, y, (wz0 + wz1) / 2), material=M["wood_dark"], col=col))
    n = 3
    for i in range(1, n):
        xx = wx0 + (wx1 - wx0) * i / n
        fr.append(box(f"{name}_m{i}", (0.03, 0.05, wz1 - wz0), (xx, y, (wz0 + wz1) / 2), material=M["brass_dark"], col=col))
    zz = wz0 + (wz1 - wz0) * 0.62
    fr.append(box(f"{name}_mh", (wx1 - wx0, 0.05, 0.03), ((wx0 + wx1) / 2, y, zz), material=M["brass_dark"], col=col))
    fr.append(box(f"{name}_sill", (wx1 - wx0 + 0.2, 0.26, 0.05), ((wx0 + wx1) / 2, y - facing * 0.08, wz0 - 0.02), material=M["wood_mid"], col=col))
    lp.join(f"{name}_frame", fr)
    return wall


def wine_glass(name, loc, col, M, s=1.0):
    p = [
        cyl(name + "_foot", 0.032 * s, h=0.004, verts=8, loc=loc, material=M["glass_clear"], col=col),
        cyl(name + "_stem", 0.004 * s, h=0.07 * s, verts=5, loc=loc, material=M["glass_clear"], col=col),
        cyl(name + "_bowl", 0.012 * s, 0.038 * s, h=0.075 * s, verts=8, loc=(loc[0], loc[1], loc[2] + 0.07 * s), material=M["glass_clear"], col=col, caps=False),
    ]
    return p


def tumbler(name, loc, col, M, s=1.0):
    return [cyl(name, 0.032 * s, 0.036 * s, h=0.085 * s, verts=8, loc=loc, material=M["glass_clear"], col=col, caps=False),
            cyl(name + "_b", 0.032 * s, h=0.012, verts=8, loc=loc, material=M["glass_clear"], col=col)]


def bottle(name, loc, col, m, h=0.30, r=0.038):
    return [cyl(name, r, h=h * 0.62, verts=8, loc=loc, material=m, col=col),
            cyl(name + "_sh", r, r * 0.35, h=h * 0.14, verts=8, loc=(loc[0], loc[1], loc[2] + h * 0.62), material=m, col=col),
            cyl(name + "_nk", r * 0.33, h=h * 0.22, verts=6, loc=(loc[0], loc[1], loc[2] + h * 0.76), material=m, col=col)]


# ----------------------------------------------------------------- props (local frames)
def prop_glass(col, M):
    parts = [cyl("pg_wall", 0.034, 0.040, h=0.135, verts=9, material=M["glass"], col=col, caps=False),
             cyl("pg_base", 0.034, h=0.014, verts=9, material=mat("glass_base", "#dbe9ee", rough=0.1, spec=0.9, alpha=0.4), col=col),
             cyl("pg_rim", 0.0405, 0.0405, h=0.004, verts=9, loc=(0, 0, 0.133), material=M["glass_clear"], col=col, caps=False)]
    return lp.join("prop_glass", parts)


def prop_bottle(col, M):
    g = mat("bottle_glass", "#a9c4cc", rough=0.05, spec=1.0, alpha=0.13, coat=0.8)
    parts = [cyl("pb_body", 0.042, h=0.13, verts=9, material=g, col=col),
             cyl("pb_sh", 0.042, 0.022, h=0.05, verts=9, loc=(0, 0, 0.13), material=g, col=col),
             cyl("pb_nk", 0.022, h=0.035, verts=8, loc=(0, 0, 0.18), material=g, col=col),
             cyl("pb_cap", 0.025, h=0.012, verts=8, loc=(0, 0, 0.212), material=M["label_blue"], col=col),
             cyl("pb_lbl", 0.0435, h=0.045, verts=9, loc=(0, 0, 0.045), material=M["label_blue"], col=col, caps=False)]
    return lp.join("prop_bottle", parts)


def prop_uvlamp(col, M):
    """Small desk UV banknote checker: base tray, two brass posts, hood with a violet tube underneath.
    Beam leaves the tube along local -Z (down onto the tray), or toward whatever the hood is pointed at."""
    tube = emissive("uv_tube", "#8a55ff", 0.4)
    tube.node_tree.nodes["emit"].name = "uv_tube_emit"
    body = mat("uv_body", "#e8e3da", rough=0.6)
    parts = [box("pu_base", (0.17, 0.11, 0.022), (0, 0, 0.011), material=body, col=col, bevel=0.004),
             box("pu_tray", (0.14, 0.08, 0.004), (0, 0.0, 0.023), material=M["black"], col=col),
             box("pu_post1", (0.012, 0.02, 0.085), (-0.075, -0.04, 0.06), material=M["brass"], col=col),
             box("pu_post2", (0.012, 0.02, 0.085), (0.075, -0.04, 0.06), material=M["brass"], col=col),
             box("pu_hood", (0.175, 0.085, 0.02), (0, -0.006, 0.105), rot=(-6, 0, 0), material=body, col=col, bevel=0.004),
             box("pu_btn", (0.022, 0.01, 0.01), (0.055, 0.056, 0.012), material=mat("uv_btn", "#7a2fd0", rough=0.5), col=col)]
    tb = cyl("pu_tube", 0.008, h=0.14, verts=6, loc=(-0.07, 0.0, 0.088), rot=(0, 90, 0), material=tube, col=col)
    parts.append(tb)
    return lp.join("prop_uvlamp", parts)


def prop_menu(col, M):
    """Two hinged leather boards; hinge along local Y at x=0. Left half spans -x."""
    l = lp.join("menu_L", [box("ml_c", (0.24, 0.33, 0.008), (-0.12, 0, 0.004), material=M["menu_cover"], col=col),
                           box("ml_p", (0.22, 0.31, 0.003), (-0.12, 0, 0.0095), material=M["paper"], col=col)])
    r = lp.join("menu_R", [box("mr_c", (0.24, 0.33, 0.008), (0.12, 0, 0.004), material=M["menu_cover"], col=col),
                           box("mr_p", (0.22, 0.31, 0.003), (0.12, 0, 0.0095), material=M["paper"], col=col),
                           box("mr_crest", (0.05, 0.05, 0.002), (0.12, 0.08, 0.0005), material=M["brass"], col=col)])
    return l, r


def prop_register(col, M, tex):
    """POS terminal: brass stand + tablet. Screens are separate planes (one per state) toggled by scale."""
    parts = [cyl("rg_foot", 0.07, 0.06, h=0.015, verts=8, material=M["brass"], col=col),
             box("rg_neck", (0.025, 0.025, 0.14), (0, -0.03, 0.08), rot=(-12, 0, 0), material=M["brass"], col=col),
             box("rg_tab", (0.27, 0.018, 0.19), (0, 0.0, 0.2), rot=(30, 0, 0), material=M["black"], col=col, bevel=0.006)]
    body = lp.join("register_body", parts)
    screens = {}
    for name, path in tex.items():
        img = bpy.data.images.load(str(path))
        m = bpy.data.materials.new(f"screen_{name}")
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        em = nt.nodes.new("ShaderNodeEmission")
        ti = nt.nodes.new("ShaderNodeTexImage")
        ti.image = img
        nt.links.new(ti.outputs[0], em.inputs[0])
        em.inputs["Strength"].default_value = 1.6
        nt.links.new(em.outputs[0], out.inputs[0])
        me = bpy.data.meshes.new(f"screen_{name}")
        w, h = 0.245, 0.165
        me.from_pydata([(w / 2, 0, -h / 2), (-w / 2, 0, -h / 2), (-w / 2, 0, h / 2), (w / 2, 0, h / 2)], [], [(0, 1, 2, 3)])
        me.uv_layers.new()
        for i, uv in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
            me.uv_layers[0].data[i].uv = uv
        me.materials.append(m)
        ob = bpy.data.objects.new(f"screen_{name}", me)
        col.objects.link(ob)
        # sits just in front of the tablet face (tablet front faces local +Y, tilted back)
        ob["local"] = [0, 0.0105, 0.2]
        screens[name] = ob
    return body, screens


def prop_fridge(col, M):
    """Back-bar glass-door fridge. Body is static; the door hinges on its left edge (local x=-0.28)."""
    w, d, h = 0.56, 0.42, 0.60
    body = [box("fr_back", (w, 0.02, h), (0, d / 2, h / 2), material=M["steel"], col=col),
            box("fr_l", (0.03, d, h), (-w / 2, 0, h / 2), material=M["steel"], col=col),
            box("fr_r", (0.03, d, h), (w / 2, 0, h / 2), material=M["steel"], col=col),
            box("fr_t", (w, d, 0.04), (0, 0, h - 0.02), material=M["steel"], col=col),
            box("fr_b", (w, d, 0.03), (0, 0, 0.015), material=M["steel"], col=col),
            box("fr_in", (w - 0.04, d - 0.04, 0.005), (0, 0, 0.035), material=mat("fr_white", "#d9dee2", rough=0.6), col=col),
            box("fr_shelf", (w - 0.05, d - 0.06, 0.008), (0, 0.01, 0.3), material=M["glass_clear"], col=col),
            box("fr_lamp", (w - 0.1, 0.03, 0.012), (0, -0.05, h - 0.045), material=M["fridge_light"], col=col),
            box("fr_trim", (w + 0.02, 0.02, 0.02), (0, -d / 2, h + 0.0), material=M["brass"], col=col)]
    # sparse contents: a lemon pair, a cheese wedge, a jar - and no milk
    body += [ico("fr_lemon1", 0.03, 1, scale=(1, 1, 0.8), loc=(0.16, 0.05, 0.335), material=M["lemon"], col=col),
             ico("fr_lemon2", 0.03, 1, scale=(1, 1, 0.8), loc=(0.2, 0.1, 0.335), material=M["lemon"], col=col),
             poly_prism("fr_cheese", [(0, 0), (0.09, 0.0), (0.0, 0.05)], 0.04, loc=(-0.18, 0.05, 0.33), rot=(0, 0, 20), material=M["cheese"], col=col),
             cyl("fr_jar", 0.03, h=0.07, verts=8, loc=(0.18, 0.06, 0.04), material=M["glass_amber"], col=col)]
    fr = lp.join("fridge_body", body)
    door = [box("fd_top", (w, 0.03, 0.05), (-w / 2, 0, h - 0.025), material=M["steel"], col=col),
            box("fd_bot", (w, 0.03, 0.06), (-w / 2, 0, 0.03), material=M["steel"], col=col),
            box("fd_l", (0.04, 0.03, h), (-w + 0.02, 0, h / 2), material=M["steel"], col=col),
            box("fd_r", (0.04, 0.03, h), (-0.02, 0, h / 2), material=M["steel"], col=col),
            box("fd_glass", (w - 0.08, 0.008, h - 0.11), (-w / 2, 0, h / 2), material=mat("fd_glass", "#cfe6f0", rough=0.1, spec=0.9, alpha=0.22), col=col),
            box("fd_handle", (0.02, 0.03, 0.28), (-w + 0.05, -0.035, h / 2), material=M["brass"], col=col),
            box("fd_rack", (w - 0.1, 0.012, 0.012), (-w / 2, 0.115, 0.13), material=M["brass"], col=col),
            box("fd_rack_b", (w - 0.1, 0.1, 0.008), (-w / 2, 0.065, 0.03), material=M["brass_dark"], col=col)]
    dr = lp.join("fridge_door", door)
    return fr, dr, dict(w=w, d=d, h=h)


# ----------------------------------------------------------------- EP02 extras (built only when an episode asks)
def prop_shrimp(name, col, body_m, dark_m, s=1.0):
    """Small freshwater shrimp, ~6 cm. Local frame: +Y = head, origin at the belly. No face, no expression."""
    parts = []
    segs = [(0.0, 0.0115, 0.010), (-0.011, 0.0105, 0.0095), (-0.021, 0.009, 0.0085), (-0.03, 0.0075, 0.007), (-0.038, 0.006, 0.0058)]
    for i, (y, r, h) in enumerate(segs):
        parts.append(ico(f"{name}_seg{i}", 1, 1, scale=(r * 0.85 * s, 0.0075 * s, h * s), loc=(0, y * s, 0.002 * s - i * 0.0012 * s),
                         material=body_m, col=col))
    parts.append(ico(f"{name}_cara", 1, 1, scale=(0.0105 * s, 0.017 * s, 0.0095 * s), loc=(0, 0.016 * s, 0.002 * s), material=body_m, col=col))
    parts.append(cyl(f"{name}_rost", 0.0022 * s, 0.0, h=0.014 * s, verts=4, loc=(0, 0.031 * s, 0.004 * s), rot=(-80, 0, 0), material=body_m, col=col))
    parts.append(poly_prism(f"{name}_fan", [(0, 0), (-0.008 * s, -0.012 * s), (0.008 * s, -0.012 * s)], 0.002 * s,
                            loc=(0, -0.042 * s, -0.004 * s), material=body_m, col=col))
    for sd in (-1, 1):
        parts.append(ico(f"{name}_eye{sd}", 0.0022 * s, 1, loc=(0.006 * sd * s, 0.028 * s, 0.006 * s), material=dark_m, col=col))
        parts.append(cyl(f"{name}_ant{sd}", 0.0006 * s, h=0.05 * s, verts=3, loc=(0.003 * sd * s, 0.03 * s, 0.004 * s),
                         rot=(-75, 0, -18 * sd), material=dark_m, col=col))
        for k in range(4):
            parts.append(cyl(f"{name}_leg{sd}{k}", 0.0007 * s, h=0.011 * s, verts=3, loc=(0.004 * sd * s, (0.02 - k * 0.006) * s, -0.004 * s),
                             rot=(180 + 20, 25 * sd, 0), material=dark_m, col=col))
    return lp.join(name, parts)


def ring_mesh(name, col, material, r_in=0.85, r_out=1.0, seg=14):
    import bmesh
    bm = bmesh.new()
    vi, vo = [], []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        vi.append(bm.verts.new((r_in * math.cos(a), r_in * math.sin(a), 0)))
        vo.append(bm.verts.new((r_out * math.cos(a), r_out * math.sin(a), 0)))
    for i in range(seg):
        j = (i + 1) % seg
        bm.faces.new((vi[i], vo[i], vo[j], vi[j]))
    return lp._finish(name, bm, material, col)


def build_extras(X, M, pcol, col, phone_tex=None):
    """X = episodes/<ep>/props.json 'extras'. Returns a dict merged into the set dictionary S."""
    out = dict(props={}, statics={}, ripples=[], ripple_mats=[], lights={})
    if "tank" in X:
        t = X["tank"]
        cx, cy, z0 = t["pos"]
        w, d, h = t["size"]
        wl = t["water"]
        g = t["gravel"]
        gl = mat("tank_glass", "#e3f1f2", rough=0.05, spec=0.35, alpha=0.05)
        gl.use_backface_culling = True
        trim = mat("tank_trim", "#15171a", rough=0.5)
        th = 0.008
        panes = [box("tk_front", (w, th, h), (cx, cy - d / 2, z0 + h / 2), material=gl, col=col),
                 box("tk_back", (w, th, h), (cx, cy + d / 2, z0 + h / 2), material=gl, col=col),
                 box("tk_left", (th, d, h), (cx - w / 2, cy, z0 + h / 2), material=gl, col=col),
                 box("tk_right", (th, d, h), (cx + w / 2, cy, z0 + h / 2), material=gl, col=col)]
        lp.join("tank_glass", panes)
        frame = []
        for zz in (z0 + 0.006, z0 + h - 0.006):
            frame += [box(f"tkf_a{zz:.2f}", (w + 0.016, 0.016, 0.012), (cx, cy - d / 2, zz), material=trim, col=col),
                      box(f"tkf_b{zz:.2f}", (w + 0.016, 0.016, 0.012), (cx, cy + d / 2, zz), material=trim, col=col),
                      box(f"tkf_c{zz:.2f}", (0.016, d, 0.012), (cx - w / 2, cy, zz), material=trim, col=col),
                      box(f"tkf_d{zz:.2f}", (0.016, d, 0.012), (cx + w / 2, cy, zz), material=trim, col=col)]
        frame.append(box("tk_bottom", (w, d, 0.01), (cx, cy, z0 + 0.005), material=trim, col=col))
        lp.join("tank_frame", frame)
        # cabinet stand (dark wood, brass kick) from the floor up to the tank
        lp.join("tank_stand", [box("ts_body", (w + 0.06, d + 0.06, z0 - 0.02), (cx, cy, (z0 - 0.02) / 2), material=M["wood_dark"], col=col),
                               box("ts_top", (w + 0.1, d + 0.1, 0.03), (cx, cy, z0 - 0.015), material=M["bar_top"], col=col, bevel=0.006),
                               box("ts_brass", (w + 0.07, d + 0.07, 0.02), (cx, cy, z0 - 0.05), material=M["brass"], col=col)])
        # gravel, stones, plants
        grv = mat("gravel", "#6b5a44", rough=0.95)
        gm = [box("tk_gravel", (w - 0.02, d - 0.02, g), (cx, cy, z0 + 0.01 + g / 2), material=grv, col=col, jitter=0.002)]
        r = random.Random(5)
        for i in range(26):
            gm.append(ico(f"tk_peb{i}", r.uniform(0.006, 0.012), 1, loc=(cx + r.uniform(-w / 2 + 0.03, w / 2 - 0.03), cy + r.uniform(-d / 2 + 0.03, d / 2 - 0.03), z0 + 0.01 + g),
                          material=mat("pebble", "#857259", rough=0.9), col=col, jitter=0.002))
        lp.join("tank_gravel", gm)
        stone_m = mat("stone", "#5d625f", rough=0.85)
        moss = mat("moss", "#3f6a3a", rough=0.95)
        for i, st in enumerate(t["stones"]):
            p = (cx + st["at"][0], cy + st["at"][1], z0 + 0.01 + g)
            sc = st["size"]
            ob = lp.join(f"tank_stone{i}", [ico(f"tks{i}", 1, 1, scale=(sc[0], sc[1], sc[2]), loc=(p[0], p[1], p[2] + sc[2] * 0.55), rot=(0, 0, st.get("yaw", 0)),
                                                material=stone_m, col=col, jitter=0.12 * min(sc)),
                                            ico(f"tksm{i}", 1, 1, scale=(sc[0] * 0.55, sc[1] * 0.5, sc[2] * 0.25), loc=(p[0] - sc[0] * 0.15, p[1], p[2] + sc[2] * 1.38),
                                                material=moss, col=col, jitter=0.004)])
        leaf = mat("plant", "#3e7d3c", rough=0.8, spec=0.3)
        leaf2 = mat("plant2", "#5a9a45", rough=0.8, spec=0.3)
        pl = []
        for i, pp in enumerate(t["plants"]):
            for k in range(pp.get("n", 5)):
                hh = pp["h"] * r.uniform(0.6, 1.0)
                pl.append(poly_prism(f"tkp{i}_{k}", [(-0.006, 0), (0.006, 0), (0.003, hh * 0.8), (0.0, hh), (-0.003, hh * 0.8)], 0.002,
                                     loc=(cx + pp["at"][0] + r.uniform(-0.025, 0.025), cy + pp["at"][1] + r.uniform(-0.02, 0.02), z0 + 0.01 + g),
                                     rot=(90 + r.uniform(-14, 14), r.uniform(-12, 12), r.uniform(0, 180)), material=leaf if k % 2 else leaf2, col=col))
        lp.join("tank_plants", pl)
        # water: tinted volume shell + a separate surface the ripples sit on
        water = mat("water_body", "#1f6366", rough=0.3, spec=0.15, alpha=0.17)
        water.use_backface_culling = True
        ws = mat("water_surface", "#b4e4e0", rough=0.06, spec=0.6, alpha=0.24)
        top = z0 + wl
        box("tank_water", (w - 0.012, d - 0.012, wl - 0.012), (cx, cy, z0 + 0.006 + (wl - 0.012) / 2), material=water, col=col)
        box("tank_water_top", (w - 0.012, d - 0.012, 0.002), (cx, cy, top - 0.001), material=ws, col=col)
        # slim aquarium light along the back edge
        lp.join("tank_light", [box("tl_bar", (w - 0.04, 0.04, 0.018), (cx, cy + d / 2 - 0.03, z0 + h + 0.015), material=M["black"], col=col),
                               box("tl_led", (w - 0.08, 0.02, 0.003), (cx, cy + d / 2 - 0.03, z0 + h + 0.005), material=emissive("tank_led", "#e8fbff", 6.0), col=col),
                               box("tl_arm1", (0.012, 0.03, 0.03), (cx - w / 2 + 0.05, cy + d / 2 - 0.01, z0 + h), material=M["black"], col=col),
                               box("tl_arm2", (0.012, 0.03, 0.03), (cx + w / 2 - 0.05, cy + d / 2 - 0.01, z0 + h), material=M["black"], col=col)])
        L = bpy.data.lights.new("tank_light", "AREA")
        L.shape = "RECTANGLE"
        L.size, L.size_y = w - 0.1, 0.05
        L.energy = 9
        L.color = (0.82, 0.96, 1.0)
        o = bpy.data.objects.new("tank_light", L)
        o.location = (cx, cy + d / 2 - 0.05, z0 + h - 0.005)
        col.objects.link(o)
        out["lights"]["tank_light"] = o
        out["tank"] = dict(center=(cx, cy), size=(w, d, h), z0=z0, top=top, floor=z0 + 0.01 + g)
        # ripple pool: flat rings on the water surface, scale/alpha driven per frame
        for i in range(X.get("ripple_pool", 6)):
            m = mat(f"ripple{i}", "#e9fbfa", rough=0.05, spec=1.0, alpha=0.0)
            out["ripples"].append(ring_mesh(f"ripple{i}", pcol, m, 0.86, 1.0))
            out["ripple_mats"].append(m.name)
        sm = mat("shrimp_body", "#c0573f", rough=0.45, spec=0.5, alpha=0.92)
        sd = mat("shrimp_dark", "#3a1a14", rough=0.4)
        for name in X.get("shrimp", []):
            out["props"][name] = prop_shrimp(name, pcol, sm, sd)
    if "stool" in X:
        s = X["stool"]
        sx, sy, sz = s["pos"]
        hh = s["h"]
        sw, sdp = s["size"]
        parts = [box("stl_top", (sw, sdp, 0.035), (sx, sy, sz + hh - 0.0175), material=M["wood_mid"], col=col, bevel=0.006),
                 box("stl_tread", (sw * 0.98, sdp * 0.6, 0.004), (sx, sy, sz + hh + 0.001), material=mat("rubber", "#1b1b1d", rough=0.9), col=col)]
        for ix in (-1, 1):
            for iy in (-1, 1):
                parts.append(box(f"stl_leg{ix}{iy}", (0.035, 0.035, hh - 0.035), (sx + ix * (sw / 2 - 0.03), sy + iy * (sdp / 2 - 0.03), sz + (hh - 0.035) / 2),
                                 rot=(iy * -3, ix * 3, 0), material=M["wood_dark"], col=col))
        parts.append(box("stl_brace1", (sw - 0.06, 0.02, 0.03), (sx, sy - sdp / 2 + 0.03, sz + 0.09), material=M["wood_dark"], col=col))
        parts.append(box("stl_brace2", (sw - 0.06, 0.02, 0.03), (sx, sy + sdp / 2 - 0.03, sz + 0.09), material=M["wood_dark"], col=col))
        lp.join("step_stool", parts)
    if "net" in X:
        mesh_m = mat("net_mesh", "#f1f3ee", rough=0.9, alpha=0.55)
        hnd = mat("net_handle", "#2f3a33", rough=0.5)
        # local frame: origin at the ring centre, handle runs along +Y, the bag hangs along -Z
        rw, rd = 0.12, 0.09
        parts = [box("nt_r1", (rw, 0.005, 0.005), (0, rd / 2, 0), material=M["steel"], col=pcol),
                 box("nt_r2", (rw, 0.005, 0.005), (0, -rd / 2, 0), material=M["steel"], col=pcol),
                 box("nt_r3", (0.005, rd, 0.005), (rw / 2, 0, 0), material=M["steel"], col=pcol),
                 box("nt_r4", (0.005, rd, 0.005), (-rw / 2, 0, 0), material=M["steel"], col=pcol),
                 cyl("nt_neck", 0.0035, h=0.06, verts=5, loc=(0, rd / 2, 0), rot=(-90, 0, 0), material=M["steel"], col=pcol),
                 cyl("nt_handle", 0.008, h=0.32, verts=6, loc=(0, rd / 2 + 0.05, 0), rot=(-90, 0, 0), material=hnd, col=pcol)]
        bag = cyl("nt_bag", 0.07, 0.03, h=0.07, verts=8, loc=(0, 0, -0.07), scale=(0.85, 0.65, 1), material=mesh_m, col=pcol, caps=False)
        bot = ico("nt_bot", 0.03, 1, scale=(0.85, 0.65, 0.4), loc=(0, 0, -0.07), material=mesh_m, col=pcol)
        parts += [bag, bot]
        out["props"]["net"] = lp.join("prop_net", parts)
    if "towel" in X:
        tw = mat("towel", "#ece6da", rough=1.0)
        stripe = mat("towel_stripe", "#7a1f28", rough=1.0)
        # local frame: folded towel draped over a rail along X; origin at the fold
        parts = [box("tw_f", (0.16, 0.012, 0.13), (0, -0.012, -0.065), material=tw, col=pcol, bevel=0.003),
                 box("tw_b", (0.16, 0.012, 0.11), (0, 0.012, -0.055), material=tw, col=pcol, bevel=0.003),
                 box("tw_top", (0.16, 0.036, 0.012), (0, 0, 0.0), material=tw, col=pcol, bevel=0.004),
                 box("tw_st", (0.162, 0.013, 0.01), (0, -0.012, -0.11), material=stripe, col=pcol)]
        out["props"]["towel"] = lp.join("prop_towel", parts)
        tp = X["towel"]["post"]
        lp.join("towel_post", [cyl("tp_pole", 0.012, h=tp[2] - 0.62, verts=6, loc=(tp[0], tp[1], 0.62), material=M["brass"], col=col),
                               cyl("tp_foot", 0.07, 0.05, h=0.02, verts=8, loc=(tp[0], tp[1], 0.62), material=M["brass_dark"], col=col),
                               cyl("tp_rail", 0.008, h=0.2, verts=6, loc=(tp[0] - 0.1, tp[1], tp[2]), rot=(0, 90, 0), material=M["brass"], col=col)]
                              + ([cyl("tp_hook_arm", 0.006, h=abs(X["towel"]["hook"][1] - tp[1]) + 0.01, verts=6, loc=(tp[0], tp[1], X["towel"]["hook"][2]),
                                      rot=(-90, 0, 0), material=M["brass"], col=col),
                                  box("tp_hook_tip", (0.04, 0.008, 0.03), (X["towel"]["hook"][0], X["towel"]["hook"][1], X["towel"]["hook"][2] + 0.012),
                                      material=M["brass"], col=col)] if "hook" in X["towel"] else []))
    if "phone" in X:
        body = mat("phone_body", "#1d2026", rough=0.35, spec=0.6, metallic=0.3)
        parts = [box("ph_body", (0.074, 0.152, 0.009), (0, 0, 0.0045), material=body, col=pcol, bevel=0.004)]
        if phone_tex:
            img = bpy.data.images.load(str(phone_tex))
            m = bpy.data.materials.new("phone_screen")
            m.use_nodes = True
            nt = m.node_tree
            nt.nodes.clear()
            o_ = nt.nodes.new("ShaderNodeOutputMaterial")
            em = nt.nodes.new("ShaderNodeEmission")
            ti = nt.nodes.new("ShaderNodeTexImage")
            ti.image = img
            nt.links.new(ti.outputs[0], em.inputs[0])
            em.inputs["Strength"].default_value = 1.4
            nt.links.new(em.outputs[0], o_.inputs[0])
            me = bpy.data.meshes.new("phone_screen")
            sw, sh = 0.066, 0.142
            zz = 0.0092
            me.from_pydata([(-sw / 2, -sh / 2, zz), (sw / 2, -sh / 2, zz), (sw / 2, sh / 2, zz), (-sw / 2, sh / 2, zz)], [], [(0, 1, 2, 3)])
            me.uv_layers.new()
            for i, uv in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
                me.uv_layers[0].data[i].uv = uv
            me.materials.append(m)
            so = bpy.data.objects.new("phone_screen_geo", me)
            pcol.objects.link(so)
            parts.append(so)
        out["props"]["phone"] = lp.join("prop_phone", parts)
    return out


# ----------------------------------------------------------------- build
def build(cfg, screen_tex):
    col = lp.collection("Set")
    pcol = lp.collection("Props")
    M = materials()
    S = dict(objects={}, lights={}, props={}, mats=M)
    bar = cfg["bar"]
    bx0, bx1 = bar["x"]
    by0, by1 = bar["y"]
    top = bar["top"]

    # floor planks
    planks = []
    for i in range(-14, 15):
        planks.append(box(f"plank{i}", (0.24, 9.0, 0.04), (i * 0.245, -0.8, -0.02), material=M["floor"] if i % 2 else M["floor2"], col=col))
    lp.join("floor", planks)
    box("ceiling", (7.0, 6.2, 0.1), (0, -0.85, 3.4), material=M["ceiling"], col=col)
    beams = [box(f"beam{i}", (0.18, 6.0, 0.18), (-2.6 + i * 1.3, -0.85, 3.27), material=M["wood_dark"], col=col) for i in range(5)]
    lp.join("beams", beams)
    box("side_wall_L", (0.12, 6.0, 3.4), (-3.3, -0.85, 1.7), material=M["wood_panel"], col=col)
    box("side_wall_R", (0.12, 6.0, 3.4), (3.3, -0.85, 1.7), material=M["wood_panel"], col=col)

    window_wall("back_wall", col, M, cfg["back_wall_y"], cfg["window_back"]["x"], cfg["window_back"]["z"], facing=1)
    window_wall("front_wall", col, M, cfg["front_wall_y"], cfg["window_front"]["x"], cfg["window_front"]["z"], facing=-1)
    sky(col)
    forest(col, M, +1, 101)
    forest(col, M, -1, 202)
    ico("moon", 1.1, 2, loc=(9.0, 24.0, 10.5), material=M["moon"], col=col)

    # ---- the bar
    parts = [box("bar_top", (bx1 - bx0, by1 - by0 + 0.06, 0.06), ((bx0 + bx1) / 2, 0, top - 0.03), material=M["bar_top"], col=col, bevel=0.012)]
    x = bx0 + 0.11
    k = 0
    while x < bx1 - 0.05:
        parts.append(box(f"slat{k}", (0.2, 0.05, top - 0.12), (x, by0 + 0.03, (top - 0.12) / 2 + 0.06), rot=(0, 0, R.uniform(-1, 1)),
                         material=M["wood_mid"] if k % 2 else M["wood_dark"], col=col))
        x += 0.22
        k += 1
    parts.append(box("bar_kick", (bx1 - bx0, 0.1, 0.1), ((bx0 + bx1) / 2, by0 + 0.06, 0.05), material=M["black"], col=col))
    parts.append(box("bar_back", (bx1 - bx0, 0.04, top - 0.06), ((bx0 + bx1) / 2, by1 - 0.02, (top - 0.06) / 2), material=M["wood_dark"], col=col))
    lp.join("bar", parts)
    rails = [cyl("rail_top", 0.018, h=bx1 - bx0, verts=8, loc=(bx0, by0 - 0.02, top - 0.075), rot=(0, 90, 0), material=M["brass"], col=col),
             cyl("rail_foot", 0.022, h=bx1 - bx0, verts=8, loc=(bx0, by0 - 0.16, 0.26), rot=(0, 90, 0), material=M["brass"], col=col)]
    for i in range(7):
        xx = bx0 + 0.2 + i * (bx1 - bx0 - 0.4) / 6
        rails.append(cyl(f"rail_post{i}", 0.012, h=0.26, verts=6, loc=(xx, by0 - 0.1, 0.0), rot=(30, 0, 0), material=M["brass"], col=col))
    lp.join("bar_rails", rails)
    # coasters / little bar life
    ob = cyl("coaster", 0.05, h=0.004, verts=10, loc=(0.02, 0.06, top - 0.001), material=mat("coaster", "#6a3a22", rough=0.9), col=col)
    tb = tumbler("bar_tumbler", (1.25, -0.05, top), col, M)
    lp.join("bar_tumbler_j", tb)
    lp.join("bar_bottle_j", bottle("bar_bottle", (1.55, 0.12, top), col, M["glass_amber"], h=0.3))
    lp.join("bar_napkins", [box("napkin", (0.12, 0.12, 0.03), (-1.55, 0.1, top + 0.015), rot=(0, 0, 12), material=M["cloth"], col=col)])
    # hidden step Patrick stands on
    box("pat_step", (1.4, 0.7, 0.62), (-0.2, 0.85, 0.31), material=M["wood_dark"], col=col)

    # ---- back counter, shelves, glassware
    bc = cfg["back_counter"]
    by_0, by_1 = bc["y"]
    lp.join("back_counter", [
        box("bc_top", (5.2, by_1 - by_0, 0.05), (0, (by_0 + by_1) / 2, bc["top"] - 0.025), material=M["bar_top"], col=col),
        box("bc_cab", (5.2, by_1 - by_0 - 0.06, bc["top"] - 0.05), (0, (by_0 + by_1) / 2 + 0.03, (bc["top"] - 0.05) / 2), material=M["wood_mid"], col=col)])
    doors = []
    for i in range(10):
        xx = -2.35 + i * 0.52
        doors.append(box(f"bc_door{i}", (0.48, 0.02, 0.75), (xx, by_0 + 0.02, 0.47), material=M["wood_dark"], col=col))
        doors.append(box(f"bc_knob{i}", (0.02, 0.02, 0.06), (xx + 0.18, by_0 + 0.0, 0.7), material=M["brass"], col=col))
    lp.join("bc_doors", doors)
    shelf_items = []
    for j, z in enumerate((1.35, 1.72, 2.09)):
        shelf_items.append(box(f"shelf{j}", (2.05, 0.26, 0.035), (-1.42, 1.80, z), material=M["wood_mid"], col=col))
        shelf_items.append(box(f"shelf_edge{j}", (2.05, 0.012, 0.012), (-1.42, 1.67, z + 0.0), material=M["brass"], col=col))
        led = box(f"shelf_led{j}", (1.9, 0.02, 0.006), (-1.42, 1.72, z - 0.021), material=M["led_warm"], col=col)
        shelf_items.append(led)
        xx = -2.35
        while xx < -0.55:
            kind = R.random()
            if j == 0 and kind < 0.5:
                shelf_items += wine_glass(f"wg{j}_{xx:.2f}", (xx, 1.80, z + 0.018), col, M, s=1.1)
                xx += 0.1
            elif kind < 0.75:
                m = R.choice([M["glass_amber"], M["glass_green"], M["glass_clear"], M["glass_amber"]])
                shelf_items += bottle(f"bt{j}_{xx:.2f}", (xx, 1.82, z + 0.018), col, m, h=R.uniform(0.24, 0.32), r=R.uniform(0.03, 0.042))
                xx += 0.11
            else:
                shelf_items += tumbler(f"tb{j}_{xx:.2f}", (xx, 1.80, z + 0.018), col, M)
                xx += 0.09
    lp.join("back_shelves", shelf_items)
    for j, z in enumerate((1.35, 1.72, 2.09)):
        L = bpy.data.lights.new(f"shelf_led_light{j}", "AREA")
        L.shape = "RECTANGLE"
        L.size, L.size_y = 1.9, 0.05
        L.energy = 18
        L.color = (1.0, 0.68, 0.38)
        o = bpy.data.objects.new(L.name, L)
        o.location = (-1.42, 1.74, z - 0.03)
        col.objects.link(o)

    # ---- pendants over the bar
    for i, (px, py) in enumerate(cfg["pendants"]):
        zb = 2.15
        parts = [cyl(f"pd_cord{i}", 0.006, h=3.4 - zb - 0.2, verts=5, loc=(px, py, zb + 0.2), material=M["black"], col=col),
                 cyl(f"pd_cap{i}", 0.035, 0.02, h=0.06, verts=8, loc=(px, py, zb + 0.17), material=M["brass"], col=col),
                 cyl(f"pd_shade{i}", 0.16, 0.04, h=0.19, verts=10, loc=(px, py, zb), material=M["shade"], col=col, caps=False),
                 cyl(f"pd_rim{i}", 0.162, h=0.012, verts=10, loc=(px, py, zb - 0.004), material=M["brass"], col=col, caps=False)]
        lp.join(f"pendant{i}", parts)
        bulb = ico(f"pd_bulb{i}", 0.045, 1, loc=(px, py, zb + 0.06), material=bpy.data.materials.new(f"bulb{i}"), col=col)
        bm = bulb.data.materials[0]
        bm.use_nodes = True
        bnt = bm.node_tree
        bnt.nodes.clear()
        bo = bnt.nodes.new("ShaderNodeOutputMaterial")
        be = bnt.nodes.new("ShaderNodeEmission")
        be.name = "emit"
        be.inputs["Color"].default_value = hex_rgb("#ffd08a")
        be.inputs["Strength"].default_value = 25
        bnt.links.new(be.outputs[0], bo.inputs[0])
        L = bpy.data.lights.new(f"pendant_light{i}", "SPOT")
        L.energy = 95
        L.spot_size = math.radians(115)
        L.spot_blend = 0.6
        L.shadow_soft_size = 0.07
        L.color = (1.0, 0.64, 0.33)
        o = bpy.data.objects.new(L.name, L)
        o.location = (px, py, zb + 0.05)
        col.objects.link(o)
        S["lights"][f"pendant{i}"] = o
        S["objects"][f"pd_bulb{i}"] = bulb
        Lp = bpy.data.lights.new(f"pendant_glow{i}", "POINT")
        Lp.energy = 12
        Lp.shadow_soft_size = 0.15
        Lp.color = (1.0, 0.6, 0.3)
        op = bpy.data.objects.new(Lp.name, Lp)
        op.location = (px, py, zb + 0.12)
        col.objects.link(op)
        S["lights"][f"pendant_glow{i}"] = op
    # ---- stools
    for i, sx in enumerate((cfg["characters"]["bear"]["pos"][0], 1.45, -1.25)):
        lp.join(f"stool{i}", [cyl(f"st_seat{i}", 0.21, h=0.08, verts=10, loc=(sx, -0.74, 0.70), material=M["leather"], col=col, jitter=0.004),
                              cyl(f"st_pole{i}", 0.025, h=0.7, verts=6, loc=(sx, -0.74, 0.0), material=M["brass"], col=col),
                              cyl(f"st_foot{i}", 0.2, 0.17, h=0.03, verts=10, loc=(sx, -0.74, 0.0), material=M["brass_dark"], col=col),
                              cyl(f"st_ring{i}", 0.17, h=0.015, verts=10, loc=(sx, -0.74, 0.3), material=M["brass"], col=col, caps=False)])

    # ---- dining room behind the customer
    for i, (tx, ty) in enumerate(((-1.75, -2.35), (1.55, -2.65), (-0.1, -3.05))):
        lp.join(f"table{i}", [cyl(f"tb_cloth{i}", 0.48, 0.46, h=0.72, verts=12, loc=(tx, ty, 0), material=M["cloth"], col=col, jitter=0.01),
                              cyl(f"tb_top{i}", 0.5, h=0.03, verts=12, loc=(tx, ty, 0.72), material=M["cloth"], col=col),
                              cyl(f"tb_candle{i}", 0.02, h=0.12, verts=6, loc=(tx, ty, 0.75), material=M["candle"], col=col)]
                + wine_glass(f"tb_wg{i}", (tx + 0.2, ty + 0.1, 0.75), col, M) + wine_glass(f"tb_wg2{i}", (tx - 0.18, ty - 0.12, 0.75), col, M))
        ico(f"tb_flame{i}", 0.012, 1, scale=(1, 1, 1.8), loc=(tx, ty, 0.89), material=M["flame"], col=col)
        L = bpy.data.lights.new(f"candle{i}", "POINT")
        L.energy = 6
        L.shadow_soft_size = 0.05
        L.color = (1.0, 0.55, 0.22)
        o = bpy.data.objects.new(L.name, L)
        o.location = (tx, ty, 0.95)
        col.objects.link(o)
        for c in range(2):
            a = math.radians(70 + 180 * c + i * 20)
            chx, chy = tx + math.cos(a) * 0.72, ty + math.sin(a) * 0.72
            lp.join(f"chair{i}{c}", [box(f"ch_s{i}{c}", (0.42, 0.42, 0.05), (chx, chy, 0.46), rot=(0, 0, math.degrees(a)), material=M["leather"], col=col),
                                     box(f"ch_b{i}{c}", (0.06, 0.42, 0.5), (chx + math.cos(a) * 0.2, chy + math.sin(a) * 0.2, 0.72), rot=(0, 0, math.degrees(a)), material=M["wood_dark"], col=col),
                                     cyl(f"ch_l{i}{c}", 0.02, h=0.46, verts=5, loc=(chx, chy, 0), material=M["wood_dark"], col=col)])
    # sconces on the front wall
    for i, sx in enumerate((-2.25, 1.6)):
        y = cfg["front_wall_y"] + 0.1
        lp.join(f"sconce{i}", [box(f"sc_plate{i}", (0.1, 0.02, 0.22), (sx, y, 1.9), material=M["brass"], col=col),
                               cyl(f"sc_shade{i}", 0.05, 0.08, h=0.14, verts=8, loc=(sx, y + 0.1, 1.95), material=M["shade"], col=col)])
        L = bpy.data.lights.new(f"sconce{i}", "POINT")
        L.energy = 30
        L.shadow_soft_size = 0.06
        L.color = (1.0, 0.6, 0.3)
        o = bpy.data.objects.new(L.name, L)
        o.location = (sx, y + 0.12, 2.0)
        col.objects.link(o)

    # ---- props
    P = cfg["props"]
    S["props"]["glass"] = prop_glass(pcol, M)
    S["props"]["bottle"] = prop_bottle(pcol, M)
    S["props"]["uvlamp"] = prop_uvlamp(pcol, M)
    S["props"]["menu_L"], S["props"]["menu_R"] = prop_menu(pcol, M)
    body, screens = prop_register(pcol, M, screen_tex)
    rp = P["register"]
    body.matrix_world = M_place(rp["pos"], rp["yaw"])
    S["props"]["register"] = body
    S["screens"] = screens
    S["register_M"] = M_place(rp["pos"], rp["yaw"])
    dp = P["dimmer"]
    lp.join("dimmer_plate", [box("dm_plate", (0.07, 0.07, 0.006), (0, 0, 0.003), material=M["brass"], col=pcol, bevel=0.002)]).matrix_world = M_place(dp["pos"], dp["yaw"])
    S["props"]["dimmer_knob"] = lp.join("dimmer_knob", [cyl("dm_knob", 0.018, 0.015, h=0.022, verts=8, material=M["brass"], col=pcol),
                                                        box("dm_tick", (0.004, 0.014, 0.004), (0, 0.008, 0.022), material=M["black"], col=pcol)])
    S["dimmer_M"] = M_place((dp["pos"][0], dp["pos"][1], dp["pos"][2] + 0.006), dp["yaw"])
    fr, door, fdim = prop_fridge(pcol, M)
    fp = P["fridge"]
    FM = M_place(fp["pos"], fp["yaw"])
    fr.matrix_world = FM
    S["fridge_M"] = FM
    S["fridge_dim"] = fdim
    S["props"]["fridge_door"] = door
    L = bpy.data.lights.new("fridge_light", "POINT")
    L.energy = 2
    L.shadow_soft_size = 0.1
    L.color = (0.85, 0.93, 1.0)
    o = bpy.data.objects.new(L.name, L)
    o.matrix_world = FM @ Matrix.Translation((0, 0.0, fdim["h"] - 0.1))
    col.objects.link(o)
    S["lights"]["fridge"] = o

    # ---- room lighting
    def area(name, loc, rot, size, energy, color, size_y=None):
        L = bpy.data.lights.new(name, "AREA")
        L.shape = "RECTANGLE"
        L.size = size
        L.size_y = size_y or size
        L.energy = energy
        L.color = color
        o = bpy.data.objects.new(name, L)
        o.location = loc
        o.rotation_euler = [math.radians(a) for a in rot]
        col.objects.link(o)
        S["lights"][name] = o
        return o

    area("key_warm", (0.1, -0.2, 3.1), (0, 0, 0), 1.8, 170, (1.0, 0.7, 0.45), size_y=1.2)
    area("window_back_light", (1.5, 1.86, 2.0), (-90, 0, 0), 1.8, 320, (0.45, 0.62, 1.0), size_y=1.6)
    area("window_front_light", (-0.35, -3.5, 1.85), (90, 0, 0), 2.4, 420, (0.45, 0.62, 1.0), size_y=1.6)
    area("fill_front", (0.2, -2.2, 1.7), (78, 0, 0), 2.0, 70, (1.0, 0.78, 0.6), size_y=1.0)
    sun = bpy.data.lights.new("moon_sun", "SUN")
    sun.energy = 0.9
    sun.angle = math.radians(3)
    sun.color = (0.55, 0.7, 1.0)
    so = bpy.data.objects.new("moon_sun", sun)
    so.rotation_euler = (math.radians(-55), 0, math.radians(200))
    col.objects.link(so)
    # violet spot carried by the UV lamp (energy driven by the timeline)
    L = bpy.data.lights.new("uv_spot", "SPOT")
    L.energy = 0
    L.color = (0.55, 0.25, 1.0)
    L.spot_size = math.radians(70)
    L.spot_blend = 0.5
    L.shadow_soft_size = 0.02
    o = bpy.data.objects.new("uv_spot", L)
    col.objects.link(o)
    S["lights"]["uv_spot"] = o
    if cfg.get("extras"):
        E = build_extras(cfg["extras"], M, pcol, col, cfg.get("phone_tex"))
        S["props"].update(E["props"])
        S["lights"].update(E["lights"])
        S["ripples"], S["ripple_mats"], S["tank"] = E["ripples"], E["ripple_mats"], E.get("tank")
    return S
