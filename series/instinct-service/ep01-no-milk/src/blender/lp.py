"""Low-poly mesh + material helpers (Blender 5.x). Meshes are baked in their bone/pivot space so the
object transform alone carries the animation. Every polygon is flat shaded: visible facets are the look."""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

_rng = random.Random(7)


def hex_rgb(h, a=1.0):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (*lin, a)


def collection(name, parent=None):
    col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    p = parent or bpy.context.scene.collection
    if col.name not in [c.name for c in p.children]:
        p.children.link(col)
    return col


# ----------------------------------------------------------------- materials
_mats = {}


def mat(name, color, rough=0.82, spec=0.25, metallic=0.0, emit=None, emit_strength=0.0, alpha=1.0, coat=0.0):
    if name in _mats:
        return _mats[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = hex_rgb(color) if isinstance(color, str) else color
    b.inputs["Roughness"].default_value = rough
    b.inputs["Specular IOR Level"].default_value = spec
    b.inputs["Metallic"].default_value = metallic
    if coat:
        b.inputs["Coat Weight"].default_value = coat
    if emit:
        b.inputs["Emission Color"].default_value = hex_rgb(emit) if isinstance(emit, str) else emit
        b.inputs["Emission Strength"].default_value = emit_strength
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
        m.surface_render_method = "BLENDED"
    m.diffuse_color = hex_rgb(color) if isinstance(color, str) else color
    _mats[name] = m
    return m


def emissive(name, color, strength):
    if name in _mats:
        return _mats[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.name = "emit"
    em.inputs["Color"].default_value = hex_rgb(color) if isinstance(color, str) else color
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], out.inputs[0])
    _mats[name] = m
    return m


# ----------------------------------------------------------------- meshes
def _finish(name, bm, material, col, xform=None, jitter=0.0, seed=None):
    if xform is not None:
        bmesh.ops.transform(bm, matrix=xform, verts=bm.verts)
    if jitter:
        r = random.Random(seed if seed is not None else hash(name) & 0xFFFF)
        for v in bm.verts:
            v.co += Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-1, 1))) * jitter
    for f in bm.faces:
        f.smooth = False
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if material is not None:
        mats = material if isinstance(material, (list, tuple)) else [material]
        for m in mats:
            me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    (col or bpy.context.scene.collection).objects.link(ob)
    return ob


def T(loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    """loc, rot in degrees (XYZ euler), non-uniform scale -> 4x4 matrix."""
    from mathutils import Euler
    S = Matrix.Diagonal((*scale, 1.0))
    R = Euler([math.radians(a) for a in rot], "XYZ").to_matrix().to_4x4()
    return Matrix.Translation(loc) @ R @ S


def ico(name, r=1.0, sub=2, scale=(1, 1, 1), loc=(0, 0, 0), rot=(0, 0, 0), material=None, col=None, jitter=0.0, cut=None):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r)
    if cut:  # keep one half: cut = ('z', +1) keeps z >= 0
        axis, sign = cut
        i = "xyz".index(axis)
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        n = [0, 0, 0]
        n[i] = 1
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, 0), plane_no=n,
                               clear_inner=sign > 0, clear_outer=sign < 0)
    return _finish(name, bm, material, col, T(loc, rot, scale), jitter)


def cyl(name, r1=1.0, r2=None, h=1.0, verts=8, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), material=None, col=None,
        jitter=0.0, base=True, caps=True):
    """Cylinder/cone along +Z; base at z=0 when base=True else centered."""
    r2 = r1 if r2 is None else r2
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=caps, segments=verts, radius1=r1, radius2=r2, depth=h)
    if base:
        bmesh.ops.translate(bm, vec=(0, 0, h / 2), verts=bm.verts)
    return _finish(name, bm, material, col, T(loc, rot, scale), jitter)


def box(name, size=(1, 1, 1), loc=(0, 0, 0), rot=(0, 0, 0), material=None, col=None, bevel=0.0, jitter=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    if bevel:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=1, affect="EDGES")
    return _finish(name, bm, material, col, T(loc, rot), jitter)


def poly_prism(name, pts2d, depth, loc=(0, 0, 0), rot=(0, 0, 0), material=None, col=None, axis="z", jitter=0.0, bevel=0.0):
    """Extrude a 2D outline (in its XY plane) by depth along +Z, then orient."""
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, -depth / 2)) for x, y in pts2d]
    f = bm.faces.new(vs)
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [e for e in r["geom"] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, 0, depth), verts=top)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bevel:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=1, affect="EDGES", clamp_overlap=True)
    return _finish(name, bm, material, col, T(loc, rot), jitter)


def join(name, objs, col=None):
    """Join several static objects into one mesh (keeps per-object materials)."""
    if not objs:
        return None
    bm = bmesh.new()
    mats = []
    for o in objs:
        remap = []
        for m in o.data.materials:
            if m not in mats:
                mats.append(m)
            remap.append(mats.index(m))
        n0 = len(bm.faces)
        o.data.transform(o.matrix_world)
        bm.from_mesh(o.data)
        bm.faces.ensure_lookup_table()
        for f in bm.faces[n0:]:
            f.material_index = remap[f.material_index] if remap else 0
    target = col or objs[0].users_collection[0]
    for o in objs:
        me = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    target.objects.link(ob)
    return ob


def bake_matrix(ob, M):
    """Push a matrix into mesh data (used to place static set pieces in world space)."""
    ob.data.transform(M)
