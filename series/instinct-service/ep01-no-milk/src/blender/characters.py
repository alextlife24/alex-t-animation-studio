"""Patrick (platypus bartender) and Mr. Bear (black-bear customer).

Each character is a set of rigid low-poly parts bound to bones. pose(ch, hands) returns world matrices for
every part and every bone, so props can be attached to hands without drift. Local frame: +Y forward, +Z up,
+X = the character's right. Arms are 2-bone analytic IK toward world-space hand targets.
"""
import math

import bpy
from mathutils import Matrix, Quaternion, Vector

import lp
from lp import T, box, cyl, hex_rgb, ico, mat, poly_prism

D = math.radians


def Rx(a):
    return Matrix.Rotation(D(a), 4, "X")


def Ry(a):
    return Matrix.Rotation(D(a), 4, "Y")


def Rz(a):
    return Matrix.Rotation(D(a), 4, "Z")


def Tr(*v):
    return Matrix.Translation(v)


def frame_from(origin, y_axis, up_hint):
    y = y_axis.normalized()
    z = (up_hint - y * up_hint.dot(y))
    if z.length < 1e-6:
        z = Vector((0, 0, 1)) - y * y.z
    z.normalize()
    x = y.cross(z)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = origin
    return m


def two_bone(S, Tg, a, b, pole):
    d = Tg - S
    L = max(abs(a - b) + 1e-3, min(d.length, a + b - 1e-4))
    dn = d.normalized()
    Te = S + dn * L
    ca = (a * a + L * L - b * b) / (2 * a * L)
    sa = math.sqrt(max(0.0, 1 - ca * ca))
    pp = pole - S
    pp = pp - dn * pp.dot(dn)
    if pp.length < 1e-6:
        pp = Vector((0, 0, -1))
    pp.normalize()
    E = S + dn * (a * ca) + pp * (a * sa)
    return E, Te


def bill_outline(w_base, w_tip, length, n=7):
    """Platypus bill seen from above: straight-ish sides, broad rounded tip. y from 0 (base) to length."""
    pts = [(-w_base / 2, 0.0)]
    pts.append((-w_tip / 2, length * 0.72))
    for i in range(n + 1):
        a = math.pi * (1 - i / n)
        pts.append((math.cos(a) * w_tip / 2, length * 0.72 + math.sin(a) * length * 0.28))
    pts.append((w_tip / 2, length * 0.72))
    pts.append((w_base / 2, 0.0))
    # dedupe consecutive duplicates
    out = []
    for p in pts:
        if not out or (abs(out[-1][0] - p[0]) > 1e-6 or abs(out[-1][1] - p[1]) > 1e-6):
            out.append(p)
    return out


def fur_material(name, base_hex, fluor_hex):
    """Matte fur whose emission is masked by the UV lamp's real cone: position, direction, facing, falloff.
    The mask parameters live in Value nodes that the timeline keys every frame (uv_on, lamp_*, dir_*)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N = nt.nodes
    Ln = nt.links.new
    b = N["Principled BSDF"]
    b.inputs["Base Color"].default_value = hex_rgb(base_hex)
    b.inputs["Roughness"].default_value = 0.9
    b.inputs["Specular IOR Level"].default_value = 0.2
    b.inputs["Emission Color"].default_value = hex_rgb(fluor_hex)

    def val(nm, v):
        n = N.new("ShaderNodeValue")
        n.name = nm
        n.label = nm
        n.outputs[0].default_value = v
        return n

    def vmath(op, a, bb=None):
        n = N.new("ShaderNodeVectorMath")
        n.operation = op
        Ln(a, n.inputs[0])
        if bb is not None:
            Ln(bb, n.inputs[1])
        return n

    def smath(op, a, bb=None, v1=None):
        n = N.new("ShaderNodeMath")
        n.operation = op
        if isinstance(a, float):
            n.inputs[0].default_value = a
        else:
            Ln(a, n.inputs[0])
        if bb is not None:
            if isinstance(bb, float):
                n.inputs[1].default_value = bb
            else:
                Ln(bb, n.inputs[1])
        return n

    uv_on = val("uv_on", 0.0)
    lp_ = [val(f"lamp_{c}", 0.0) for c in "xyz"]
    dr = [val(f"dir_{c}", 0.0) for c in "xyz"]
    lpos = N.new("ShaderNodeCombineXYZ")
    ldir = N.new("ShaderNodeCombineXYZ")
    for i in range(3):
        Ln(lp_[i].outputs[0], lpos.inputs[i])
        Ln(dr[i].outputs[0], ldir.inputs[i])
    geo = N.new("ShaderNodeNewGeometry")
    V = vmath("SUBTRACT", lpos.outputs[0], geo.outputs["Position"])
    dist = vmath("LENGTH", V.outputs[0])
    Vn = vmath("NORMALIZE", V.outputs[0])
    cos_t = vmath("DOT_PRODUCT", Vn.outputs[0], ldir.outputs[0])  # = -cos(angle) since V points to lamp
    cone_in = smath("MULTIPLY", cos_t.outputs["Value"], -1.0)
    cone = N.new("ShaderNodeMapRange")
    cone.interpolation_type = "SMOOTHSTEP"
    Ln(cone_in.outputs[0], cone.inputs["Value"])
    cone.inputs["From Min"].default_value = math.cos(D(34))
    cone.inputs["From Max"].default_value = math.cos(D(16))
    face = vmath("DOT_PRODUCT", geo.outputs["Normal"], Vn.outputs[0])
    facing = smath("MAXIMUM", face.outputs["Value"], 0.0)
    facing2 = smath("POWER", facing.outputs[0], 0.6)
    d2 = smath("DIVIDE", dist.outputs["Value"], 0.42)
    d3 = smath("MULTIPLY", d2.outputs[0], d2.outputs[0])
    d4 = smath("ADD", d3.outputs[0], 1.0)
    fall = smath("DIVIDE", 1.0, d4.outputs[0])
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 60.0
    nr = N.new("ShaderNodeMapRange")
    Ln(noise.outputs["Fac"], nr.inputs["Value"])
    nr.inputs["From Min"].default_value = 0.3
    nr.inputs["From Max"].default_value = 0.7
    nr.inputs["To Min"].default_value = 0.7
    nr.inputs["To Max"].default_value = 1.15
    m1 = smath("MULTIPLY", cone.outputs["Result"], facing2.outputs[0])
    m2 = smath("MULTIPLY", m1.outputs[0], fall.outputs[0])
    m3 = smath("MULTIPLY", m2.outputs[0], uv_on.outputs[0])
    m4 = smath("MULTIPLY", m3.outputs[0], nr.outputs["Result"])
    strength = smath("MULTIPLY", m4.outputs[0], 3.2)
    Ln(strength.outputs[0], b.inputs["Emission Strength"])
    return m


class Rig:
    def __init__(self, name):
        self.name = name
        self.col = lp.collection(name)
        self.parts = []  # (obj, bone)

    def add(self, bone, ob):
        self.parts.append((ob, bone))
        if ob.users_collection and ob.users_collection[0] != self.col:
            for c in ob.users_collection:
                c.objects.unlink(ob)
            self.col.objects.link(ob)
        return ob


# ======================================================================= Patrick
class Patrick(Rig):
    ARM = (0.24, 0.22)

    def __init__(self, look):
        super().__init__("Patrick")
        c = self.col
        self.fur = fur_material("pat_fur", look["fur"], "#0ff2b0")
        self.belly = fur_material("pat_belly", look["belly"], "#16f7c0")
        bill = mat("pat_bill", look["bill"], rough=0.55, spec=0.35)
        bill_dark = mat("pat_bill_dark", "#3a4048", rough=0.6)
        paw = mat("pat_paw", look["paw"], rough=0.75)
        eye = mat("eye_black", "#07070a", rough=0.15, spec=0.8)
        hl = lp.emissive("eye_hl", "#ffffff", 3.0)
        red = mat("pat_bowtie", look["bowtie"], rough=0.55)
        red_dark = mat("pat_bowtie_knot", "#8c1820", rough=0.55)
        brow = mat("pat_brow", "#4b2c18", rough=0.9)
        self.tilt0 = look["bowtie_tilt_deg"]

        A = self.add
        A("body", ico("pat_body", 1, 2, scale=(0.25, 0.22, 0.34), loc=(0, 0, 0.25), material=self.fur, col=c, jitter=0.006))
        A("body", ico("pat_belly", 1, 2, scale=(0.19, 0.11, 0.24), loc=(0, 0.115, 0.2), material=self.belly, col=c, jitter=0.004))
        A("root", ico("pat_tail", 1, 1, scale=(0.15, 0.2, 0.035), loc=(0, -0.3, -0.02), rot=(-12, 0, 0), material=self.fur, col=c, jitter=0.005))
        for s in (-1, 1):
            A("root", cyl(f"pat_leg{s}", 0.05, 0.045, h=0.25, verts=6, loc=(0.1 * s, 0.02, -0.33), material=self.fur, col=c))
            A("root", ico(f"pat_foot{s}", 1, 1, scale=(0.06, 0.09, 0.025), loc=(0.11 * s, 0.07, -0.34), material=paw, col=c))
        # head
        A("head", ico("pat_head", 1, 2, scale=(0.165, 0.17, 0.148), material=self.fur, col=c, jitter=0.005))
        A("head", ico("pat_cheeks", 1, 2, scale=(0.15, 0.1, 0.1), loc=(0, 0.08, -0.04), material=self.fur, col=c, jitter=0.004))
        up = bill_outline(0.18, 0.27, 0.24, n=9)
        A("head", poly_prism("pat_bill_up", up, 0.03, loc=(0, 0.125, -0.035), rot=(-9, 0, 0), material=bill, col=c, jitter=0.002, bevel=0.009))
        A("head", box("pat_shield", (0.2, 0.025, 0.06), (0, 0.13, -0.025), rot=(-9, 0, 0), material=bill_dark, col=c, bevel=0.01))
        for s in (-1, 1):
            A("head", ico(f"pat_nostril{s}", 0.008, 1, scale=(1, 1.4, 0.6), loc=(0.022 * s, 0.33, -0.012), material=bill_dark, col=c))
        lo = bill_outline(0.15, 0.21, 0.19, n=9)
        A("jaw", poly_prism("pat_bill_lo", lo, 0.018, loc=(0, 0.0, -0.012), rot=(-9, 0, 0), material=bill, col=c, jitter=0.002, bevel=0.005))
        for s in (-1, 1):
            side = "R" if s > 0 else "L"
            A(f"eye_{side}", ico(f"pat_eye{side}", 0.022, 2, material=eye, col=c))
            A(f"eye_{side}", ico(f"pat_eyehl{side}", 0.0055, 1, loc=(0.006 * s, 0.017, 0.009), material=hl, col=c))
            A(f"lid_{side}", ico(f"pat_lid{side}", 0.026, 2, cut=("z", 1), material=self.fur, col=c))
            A(f"llid_{side}", ico(f"pat_llid{side}", 0.0255, 2, cut=("z", -1), material=self.fur, col=c))
            A(f"brow_{side}", box(f"pat_brow{side}", (0.05, 0.014, 0.012), (0, 0, 0), material=brow, col=c, bevel=0.003))
        # bow tie (crooked)
        wing = [(0.0, 0.0), (0.075, 0.042), (0.08, -0.04)]
        A("bowtie", poly_prism("pat_bt_R", wing, 0.025, rot=(90, 0, 0), material=red, col=c, jitter=0.002))
        A("bowtie", poly_prism("pat_bt_L", [(-x, y) for x, y in wing][::-1], 0.025, rot=(90, 0, 0), material=red, col=c, jitter=0.002))
        A("bowtie", box("pat_bt_knot", (0.03, 0.03, 0.03), (0, 0.004, 0), material=red_dark, col=c, bevel=0.006))
        # arms
        a, b = self.ARM
        for side in "LR":
            A(f"upper_{side}", cyl(f"pat_up{side}", 0.048, 0.042, h=a, verts=7, rot=(-90, 0, 0), material=self.fur, col=c, jitter=0.003))
            A(f"upper_{side}", ico(f"pat_shoulder{side}", 0.05, 1, material=self.fur, col=c))
            A(f"fore_{side}", cyl(f"pat_fo{side}", 0.042, 0.036, h=b, verts=7, rot=(-90, 0, 0), material=self.fur, col=c, jitter=0.003))
            A(f"fore_{side}", ico(f"pat_elbow{side}", 0.043, 1, material=self.fur, col=c))
            A(f"hand_{side}", ico(f"pat_paw{side}", 1, 1, scale=(0.05, 0.055, 0.024), loc=(0, 0.03, 0), material=paw, col=c, jitter=0.002))
            for k in range(5):
                xx = (k - 2) * 0.019
                A(f"hand_{side}", cyl(f"pat_claw{side}{k}", 0.006, 0.0, h=0.022, verts=4, loc=(xx, 0.075, -0.004), rot=(-90, 0, 0),
                                      material=bill_dark, col=c))

    def pose(self, root_M, ch, hands):
        """ch: channel dict; hands: {'L': (pos Vector, quat|None), 'R': ...} in world space."""
        B = {}
        B["root"] = root_M @ Tr(0, 0, ch.get("dip", 0.0))
        breathe = 1 + 0.008 * ch.get("breath", 0.0)
        B["body"] = B["root"] @ Rx(-ch.get("lean", 0.0)) @ Ry(ch.get("sway", 0.0))
        B["body_s"] = B["body"] @ Matrix.Diagonal((1, 1, breathe, 1))
        hp, hy, hr = ch.get("head", (0, 0, 0))
        B["head"] = B["body"] @ Tr(0, 0.03, 0.66) @ Rz(hy) @ Rx(hp) @ Ry(hr) @ Tr(0, 0, -0.02 * ch.get("swallow", 0.0))
        B["jaw"] = B["head"] @ Tr(0, 0.135, -0.055) @ Rx(-13 * ch.get("mouth", 0.0))
        lx, ly = ch.get("look", (0, 0))
        lid = ch.get("lid", 0.12)
        smile = ch.get("smile", 0.0)
        worry = ch.get("worry", 0.0)
        for s, side in ((-1, "L"), (1, "R")):
            eM = B["head"] @ Tr(0.088 * s, 0.135, 0.04) @ Rz(-12 * s)
            B[f"eye_{side}"] = eM @ Rz(-lx * 25) @ Rx(ly * 20)
            B[f"lid_{side}"] = eM @ Rx(40 - 92 * lid)
            B[f"llid_{side}"] = eM @ Rx(-30 + 40 * smile)
            B[f"brow_{side}"] = B["head"] @ Tr(0.08 * s, 0.125, 0.087 + 0.012 * ch.get("brow", 0.0)) @ Rz(-12 * s) @ Ry(s * (16 * worry - 6 * smile)) @ Rx(-10)
        B["bowtie"] = B["body"] @ Tr(0, 0.17, 0.505) @ Ry(ch.get("bowtie_tilt", self.tilt0)) @ Rx(-12)
        B["root_s"] = B["root"] @ Rz(ch.get("tail", 0.0))
        bodyR = B["body"].to_3x3()
        right, fwd, upv = bodyR.col[0], bodyR.col[1], bodyR.col[2]
        a, b = self.ARM
        for s, side in ((-1, "L"), (1, "R")):
            S = (B["body"] @ Vector((0.19 * s, 0.05, 0.42)))
            tgt, q = hands[side]
            pole = S + right * s * 0.35 - upv * 0.25 - fwd * 0.12
            E, W = two_bone(S, tgt, a, b, pole)
            B[f"upper_{side}"] = frame_from(S, E - S, upv)
            B[f"fore_{side}"] = frame_from(E, W - E, upv)
            if q is None:
                d = (W - E).normalized()
                HM = frame_from(W, d, upv)
            else:
                HM = q.to_matrix().to_4x4()
                HM.translation = W
            B[f"hand_{side}"] = HM
        out = []
        for ob, bone in self.parts:
            bn = {"body": "body_s", "root": "root_s"}.get(bone, bone) if ob.name in ("pat_body", "pat_belly", "pat_tail") else bone
            out.append((ob, B[bn]))
        return out, B


# ======================================================================= Mr. Bear
class Bear(Rig):
    ARM = (0.40, 0.38)

    def __init__(self, look):
        super().__init__("MrBear")
        c = self.col
        fur = mat("bear_fur", look["fur"], rough=0.92, spec=0.2)
        muz = mat("bear_muzzle", look["muzzle"], rough=0.85)
        muz_d = mat("bear_muzzle_d", "#6e533d", rough=0.85)
        brow = mat("bear_brow", look["brow"], rough=0.85)
        jacket = mat("bear_jacket", look["jacket"], rough=0.78, spec=0.25)
        lapel = mat("bear_lapel", look["lapel"], rough=0.55, spec=0.35)
        shirt = mat("bear_shirt", look["shirt"], rough=0.8)
        tie = mat("bear_tie", look["tie"], rough=0.5)
        sq = mat("bear_square", look["pocket_square"], rough=0.6)
        nose = mat("bear_nose", "#0a0a0c", rough=0.25, spec=0.7)
        eye = mat("bear_eye", "#1a0e08", rough=0.12, spec=0.8)
        hl = lp.emissive("eye_hl", "#ffffff", 3.0)
        brass = mat("brass", "#c08c3e", rough=0.38, metallic=0.85, spec=0.5)
        claw = mat("bear_claw", "#3a332c", rough=0.5)
        A = self.add
        A("body", ico("bear_torso", 1, 2, scale=(0.47, 0.38, 0.52), loc=(0, 0, 0.44), material=jacket, col=c, jitter=0.01))
        A("body", ico("bear_shirt", 1, 2, scale=(0.13, 0.06, 0.21), loc=(0, 0.30, 0.68), material=shirt, col=c))
        A("body", box("bear_tie", (0.055, 0.025, 0.24), (0, 0.355, 0.62), rot=(-14, 0, 0), material=tie, col=c, bevel=0.008))
        A("body", box("bear_knot", (0.06, 0.03, 0.045), (0, 0.33, 0.77), rot=(-20, 0, 0), material=tie, col=c, bevel=0.01))
        for s in (-1, 1):
            A("body", box(f"bear_lapel{s}", (0.085, 0.035, 0.36), (0.12 * s, 0.31, 0.62), rot=(-16, -24 * s, 0), material=lapel, col=c, bevel=0.01))
        A("body", poly_prism("bear_square", [(0, 0), (0.07, 0), (0.035, 0.05)], 0.012, loc=(-0.25, 0.33, 0.6), rot=(90, 0, 18), material=sq, col=c))
        for k, z in enumerate((0.36, 0.24)):
            A("body", ico(f"bear_btn{k}", 0.017, 1, loc=(0.0, 0.385 - k * 0.005, z), material=brass, col=c))
        A("body", cyl("bear_collar", 0.17, 0.15, h=0.07, verts=10, loc=(0, 0.05, 0.86), material=shirt, col=c))
        for s in (-1, 1):
            A("root", cyl(f"bear_thigh{s}", 0.16, 0.14, h=0.42, verts=8, loc=(0.2 * s, 0.05, 0.02), rot=(-80, 0, 0), material=jacket, col=c))
            A("root", cyl(f"bear_shin{s}", 0.13, 0.12, h=0.5, verts=8, loc=(0.2 * s, 0.45, -0.5), material=jacket, col=c))
            A("root", ico(f"bear_foot{s}", 1, 1, scale=(0.11, 0.16, 0.07), loc=(0.2 * s, 0.52, -0.56), material=fur, col=c))
        # head
        A("head", ico("bear_head", 1, 2, scale=(0.26, 0.25, 0.235), material=fur, col=c, jitter=0.008))
        A("head", ico("bear_muzzle", 1, 2, scale=(0.125, 0.14, 0.085), loc=(0, 0.215, -0.055), material=muz, col=c, jitter=0.004))
        A("head", ico("bear_nose", 1, 1, scale=(0.05, 0.032, 0.03), loc=(0, 0.345, -0.025), material=nose, col=c))
        A("jaw", ico("bear_jaw", 1, 2, scale=(0.095, 0.11, 0.04), loc=(0, 0.085, -0.01), material=muz_d, col=c))
        for s in (-1, 1):
            side = "R" if s > 0 else "L"
            A("head", ico(f"bear_ear{side}", 1, 2, scale=(0.08, 0.045, 0.075), loc=(0.17 * s, -0.02, 0.19), material=fur, col=c))
            A("head", ico(f"bear_earin{side}", 1, 2, scale=(0.045, 0.02, 0.042), loc=(0.17 * s, 0.015, 0.185), material=muz_d, col=c))
            A(f"eye_{side}", ico(f"bear_eye{side}", 0.022, 2, material=eye, col=c))
            A(f"eye_{side}", ico(f"bear_eyehl{side}", 0.0055, 1, loc=(0.006 * s, 0.017, 0.009), material=hl, col=c))
            A(f"lid_{side}", ico(f"bear_lid{side}", 0.0262, 2, cut=("z", 1), material=fur, col=c))
            A(f"brow_{side}", ico(f"bear_brow{side}", 1, 1, scale=(0.036, 0.016, 0.014), material=brow, col=c))
        # arms
        a, b = self.ARM
        for side in "LR":
            A(f"upper_{side}", cyl(f"bear_up{side}", 0.125, 0.105, h=a, verts=8, rot=(-90, 0, 0), material=jacket, col=c, jitter=0.004))
            A(f"upper_{side}", ico(f"bear_sh{side}", 0.13, 1, material=jacket, col=c))
            A(f"fore_{side}", cyl(f"bear_fo{side}", 0.105, 0.095, h=b - 0.03, verts=8, rot=(-90, 0, 0), material=jacket, col=c, jitter=0.004))
            A(f"fore_{side}", ico(f"bear_el{side}", 0.108, 1, material=jacket, col=c))
            A(f"fore_{side}", cyl(f"bear_cuff{side}", 0.085, h=0.035, verts=8, loc=(0, b - 0.035, 0), rot=(-90, 0, 0), material=shirt, col=c))
            A(f"hand_{side}", ico(f"bear_paw{side}", 1, 1, scale=(0.085, 0.1, 0.05), loc=(0, 0.05, 0), material=fur, col=c, jitter=0.004))
            for k in range(4):
                xx = (k - 1.5) * 0.04
                bone = f"tap_{side}" if (k == 1 and side == "R") or (k == 2 and side == "L") else f"hand_{side}"
                loc = (0, 0, 0) if bone.startswith("tap") else (xx, 0.13, -0.012)
                A(bone, ico(f"bear_dig{side}{k}", 0.026, 1, scale=(1, 1.3, 0.8), loc=loc, material=fur, col=c))
                A(bone, cyl(f"bear_claw{side}{k}", 0.01, 0.0, h=0.035, verts=4, loc=(loc[0], loc[1] + 0.03, loc[2] - 0.006), rot=(-100, 0, 0), material=claw, col=c))

    def pose(self, root_M, ch, hands):
        B = {}
        B["root"] = root_M
        breathe = 1 + 0.006 * ch.get("breath", 0.0)
        B["body"] = B["root"] @ Rx(-ch.get("lean", 0.0)) @ Ry(ch.get("sway", 0.0))
        B["body_s"] = B["body"] @ Matrix.Diagonal((1, 1, breathe, 1))
        hp, hy, hr = ch.get("head", (0, 0, 0))
        B["head"] = B["body"] @ Tr(0, 0.07, 1.13) @ Rz(hy) @ Rx(hp) @ Ry(hr)
        B["jaw"] = B["head"] @ Tr(0, 0.15, -0.105) @ Rx(-10 * ch.get("mouth", 0.0))
        lx, ly = ch.get("look", (0, 0))
        lid = ch.get("lid", 0.3)
        browv = ch.get("brow", 0.0)
        for s, side in ((-1, "L"), (1, "R")):
            eM = B["head"] @ Tr(0.088 * s, 0.225, 0.06) @ Rz(-14 * s)
            B[f"eye_{side}"] = eM @ Rz(-lx * 25) @ Rx(ly * 20)
            B[f"lid_{side}"] = eM @ Rx(40 - 92 * lid)
            B[f"brow_{side}"] = B["head"] @ Tr(0.09 * s, 0.215, 0.105 + 0.022 * browv) @ Ry(-s * 10 * ch.get("frown", 0.0)) @ Rz(-14 * s)
        bodyR = B["body"].to_3x3()
        right, fwd, upv = bodyR.col[0], bodyR.col[1], bodyR.col[2]
        a, b = self.ARM
        for s, side in ((-1, "L"), (1, "R")):
            S = B["body"] @ Vector((0.43 * s, 0.04, 0.74))
            tgt, q = hands[side]
            pole = S + right * s * 0.5 - upv * 0.45 - fwd * 0.15
            E, W = two_bone(S, tgt, a, b, pole)
            B[f"upper_{side}"] = frame_from(S, E - S, upv)
            B[f"fore_{side}"] = frame_from(E, W - E, upv)
            if q is None:
                d = (W - E)
                d.z *= 0.2
                HM = frame_from(W, d, Vector((0, 0, 1)))
            else:
                HM = q.to_matrix().to_4x4()
                HM.translation = W
            B[f"hand_{side}"] = HM
            tap = ch.get(f"tap_{side}", 0.0)
            xx = -0.02 if side == "R" else 0.02
            B[f"tap_{side}"] = HM @ Tr(xx, 0.10, -0.012) @ Rx(28 * tap) @ Tr(0, 0.03, 0)
        out = []
        for ob, bone in self.parts:
            bn = "body_s" if ob.name == "bear_torso" else bone
            out.append((ob, B[bn]))
        return out, B
