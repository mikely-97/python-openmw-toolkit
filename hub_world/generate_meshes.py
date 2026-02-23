"""hub_world/generate_meshes.py — Generate placeholder 3-D assets with Blender.

Run from INSIDE Blender's Python environment:

    blender --background --python generate_meshes.py

Or open Blender → Scripting tab → paste and run.

Prerequisites
-------------
* Blender 3.x / 4.x
* The built-in "Import-Export: Collada (Better Collada)" add-on, OR the
  official "BetterColladaExporter" from:
      https://github.com/godotengine/collada-exporter
  For simple static geometry the built-in exporter works too.

Output
------
All .dae files are written to  <this script's directory>/data/meshes/hub_world/
Each file is a single named mesh with a flat-colored material.
No armatures, no animations — purely static geometry for OpenMW.

OpenMW COLLADA notes
--------------------
* Use the Flatpak build (org.openmw.OpenMW) — the system package on Void
  Linux has a DAE loader that rejects some files.
* The Better Collada exporter produces cleaner output and is preferred.
* Scale: 1 Blender unit = 1 OpenMW unit ≈ 1 cm.
  Objects here are sized in game units (character ≈ 128 units tall).

After generation
----------------
    1. Move / copy the hub_world/data/ folder so it is reachable as a
       data= entry in openmw.cfg.
    2. Run build.py to regenerate hub_world.omwaddon (mesh paths are
       already set to meshes/hub_world/*.dae in the addon).
    3. Add to openmw.cfg:
           data="<path_to>/hub_world/data"
           content=hub_world.omwaddon
           content=hub_world.omwscripts
"""

import os
import math
import sys

# ---------------------------------------------------------------------------
# Blender import guard
# ---------------------------------------------------------------------------
try:
    import bpy  # noqa: F401  (Blender-only; not resolvable by static analysers)
except ImportError:
    print("ERROR: This script must be run inside Blender (bpy not available).")
    print("Run: blender --background --python generate_meshes.py")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR    = os.path.join(SCRIPT_DIR, "data", "meshes", "hub_world")
os.makedirs(OUT_DIR, exist_ok=True)

print(f"[HubWorld] Writing meshes to: {OUT_DIR}")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def reset_scene():
    """Remove all objects, meshes, materials from the scene."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)
    for mat in list(bpy.data.materials):
        bpy.data.materials.remove(mat)


def make_material(name, r, g, b, a=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (r, g, b, a)
        bsdf.inputs["Roughness"].default_value  = 0.8
        bsdf.inputs["Metallic"].default_value   = 0.0
    return mat


def add_mesh_object(name, verts, faces, mat):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return ob


def primitive_box(name, mat, sx=1, sy=1, sz=1, ox=0, oy=0, oz=0):
    """Create a box scaled to (sx,sy,sz) with bottom-center at origin."""
    hx, hy = sx / 2, sy / 2
    v = [
        (-hx+ox, -hy+oy, oz),   ( hx+ox, -hy+oy, oz),
        ( hx+ox,  hy+oy, oz),   (-hx+ox,  hy+oy, oz),
        (-hx+ox, -hy+oy, sz+oz),( hx+ox, -hy+oy, sz+oz),
        ( hx+ox,  hy+oy, sz+oz),(-hx+ox,  hy+oy, sz+oz),
    ]
    f = [
        (0,1,2,3), (4,7,6,5),   # bottom, top
        (0,4,5,1), (1,5,6,2),   # south, east
        (2,6,7,3), (3,7,4,0),   # north, west
    ]
    return add_mesh_object(name, v, f, mat)


def primitive_cylinder(name, mat, radius=1, height=2, segments=12, oz=0):
    """Create a vertical cylinder with bottom at (0,0,oz)."""
    verts, faces = [], []
    for i in range(segments):
        a = 2 * math.pi * i / segments
        verts.append((math.cos(a) * radius, math.sin(a) * radius, oz))
    for i in range(segments):
        a = 2 * math.pi * i / segments
        verts.append((math.cos(a) * radius, math.sin(a) * radius, oz + height))
    # Bottom cap (flat fan)
    verts.append((0, 0, oz))
    verts.append((0, 0, oz + height))
    bot_c = 2 * segments
    top_c = 2 * segments + 1
    for i in range(segments):
        n = (i + 1) % segments
        faces.append((i, n, bot_c))                      # bottom
        faces.append((segments+i, top_c, segments+n))    # top
        faces.append((i, segments+i, segments+n, n))     # side quad
    return add_mesh_object(name, verts, faces, mat)


def primitive_cone(name, mat, radius=1, height=2, segments=12, oz=0):
    verts, faces = [], []
    for i in range(segments):
        a = 2 * math.pi * i / segments
        verts.append((math.cos(a) * radius, math.sin(a) * radius, oz))
    apex = len(verts)
    verts.append((0, 0, oz + height))
    bot_c = len(verts)
    verts.append((0, 0, oz))
    for i in range(segments):
        n = (i + 1) % segments
        faces.append((i, n, apex))         # side
        faces.append((n, i, bot_c))        # bottom
    return add_mesh_object(name, verts, faces, mat)


def export_dae(filename):
    """Export scene to Collada (built-in exporter)."""
    path = os.path.join(OUT_DIR, filename)
    bpy.ops.object.select_all(action='SELECT')

    bpy.ops.wm.collada_export(
        filepath=path,
        selected=True,
        apply_modifiers=True,
        triangulate=True,
        use_texture_copies=False,
    )
    print(f"  -> {filename}")


# ===========================================================================
# Mesh definitions
# Each entry: (filename, build_function)
# All dimensions are in OpenMW game units (GU).
# Reference: character height ≈ 128 GU, doorway ≈ 150 GU tall × 60 GU wide.
# ===========================================================================

def build_plant_herb():
    """Simple stem + leaf cluster for herbs/basil/mint."""
    mat_stem = make_material("stem", 0.3, 0.5, 0.1)
    mat_leaf = make_material("leaf", 0.2, 0.7, 0.2)
    primitive_cylinder("stem", mat_stem, radius=3, height=30)
    primitive_cylinder("leaves", mat_leaf, radius=18, height=12, oz=22)


def build_plant_mushroom():
    """Mushroom: thin stem + wide cap."""
    mat_s = make_material("mstem", 0.8, 0.75, 0.6)
    mat_c = make_material("mcap",  0.7, 0.25, 0.1)
    primitive_cylinder("mstem", mat_s, radius=5, height=20)
    primitive_cylinder("mcap",  mat_c, radius=30, height=10, oz=18)


def build_tree():
    """Tree: thick trunk + cone canopy."""
    mat_t = make_material("trunk",  0.4, 0.25, 0.1)
    mat_c = make_material("canopy", 0.15, 0.45, 0.1)
    primitive_cylinder("trunk",  mat_t, radius=12, height=100)
    primitive_cone("canopy", mat_c, radius=70, height=130, oz=80)


def build_log():
    """Horizontal log for inventory/ground item."""
    mat = make_material("log", 0.5, 0.3, 0.1)
    primitive_cylinder("log", mat, radius=10, height=60)


def build_branch():
    mat = make_material("branch", 0.45, 0.28, 0.08)
    primitive_cylinder("branch", mat, radius=4, height=40)


def build_mineral_iron():
    """Iron ore deposit: dark grey irregular box."""
    mat = make_material("iron", 0.35, 0.35, 0.4)
    primitive_box("ore", mat, sx=60, sy=50, sz=30)


def build_mineral_stone():
    mat = make_material("stone", 0.5, 0.48, 0.45)
    primitive_box("stone", mat, sx=55, sy=45, sz=25)


def build_ingot():
    mat = make_material("ingot", 0.6, 0.6, 0.65)
    primitive_box("ingot", mat, sx=20, sy=8, sz=5)


def build_bed():
    """Simple bed: mattress + headboard."""
    mat_b = make_material("bedframe", 0.4, 0.25, 0.1)
    mat_m = make_material("mattress", 0.8, 0.75, 0.65)
    primitive_box("bedframe",  mat_b, sx=80, sy=160, sz=20)
    primitive_box("mattress",  mat_m, sx=75, sy=155, sz=15, oz=20)
    primitive_box("headboard", mat_b, sx=80, sy=10,  sz=60, oy=75)


def build_anvil():
    """T-shaped anvil: thick base + narrower top."""
    mat = make_material("anvil", 0.3, 0.3, 0.35)
    primitive_box("base", mat,  sx=60, sy=40, sz=25)
    primitive_box("neck", mat,  sx=20, sy=30, sz=20, oz=25, ox=0, oy=0)
    primitive_box("horn", mat,  sx=70, sy=20, sz=15, oz=45, ox=0, oy=0)


def build_forge():
    """Forge: wide box body + chimney cylinder."""
    mat_b = make_material("forgebrick", 0.45, 0.30, 0.20)
    mat_c = make_material("chimney",    0.3,  0.25, 0.2)
    mat_f = make_material("fire",       0.9,  0.4,  0.0)
    primitive_box("body",    mat_b, sx=80, sy=60, sz=60)
    primitive_cylinder("chimney", mat_c, radius=10, height=80, oz=60)
    primitive_box("glow",    mat_f, sx=40, sy=40, sz=5,  oz=58, ox=0, oy=0)


def build_pillar():
    mat = make_material("pillar", 0.65, 0.60, 0.55)
    primitive_cylinder("pillar", mat, radius=20, height=400, segments=8)


def build_pass_token():
    mat = make_material("token", 0.85, 0.75, 0.1)
    primitive_cylinder("token", mat, radius=10, height=3)


def build_apparatus_mortar():
    mat_b = make_material("bowl",   0.55, 0.50, 0.45)
    mat_p = make_material("pestle", 0.50, 0.45, 0.4)
    primitive_cylinder("bowl",   mat_b, radius=18, height=12)
    primitive_cylinder("pestle", mat_p, radius=5,  height=35, oz=12)


def build_apparatus_alembic():
    mat = make_material("alembic", 0.4, 0.55, 0.7)
    primitive_cylinder("body", mat, radius=18, height=30)
    primitive_cone("top",    mat, radius=12, height=25, oz=30)
    primitive_cylinder("spout", mat, radius=3, height=20, oz=55)


def build_apparatus_calcinator():
    mat = make_material("calc", 0.6, 0.55, 0.3)
    primitive_box("box",  mat, sx=40, sy=40, sz=30)
    primitive_cylinder("lid", mat, radius=22, height=8, oz=30)


def build_apparatus_retort():
    mat = make_material("retort", 0.5, 0.3, 0.5)
    primitive_cylinder("bulb", mat, radius=20, height=35)
    primitive_cylinder("neck", mat, radius=5,  height=25, oz=35)
    primitive_cylinder("arm",  mat, radius=3,  height=20, oz=45)


def build_axe(name, color=(0.5, 0.35, 0.15), head_color=(0.6,0.6,0.65)):
    mat_h = make_material(name+"_handle", *color)
    mat_b = make_material(name+"_blade",  *head_color)
    primitive_cylinder(name+"_handle", mat_h, radius=4, height=80)
    primitive_box(name+"_blade", mat_b, sx=40, sy=10, sz=30, oz=65)


def build_pickaxe(name, head_color=(0.6,0.6,0.65)):
    mat_h = make_material(name+"_handle", 0.5, 0.35, 0.15)
    mat_b = make_material(name+"_head",   *head_color)
    primitive_cylinder(name+"_handle", mat_h, radius=4, height=90)
    primitive_box(name+"_head", mat_b, sx=60, sy=8, sz=10, oz=82)


def build_mine_refresh():
    mat = make_material("board", 0.45, 0.35, 0.2)
    primitive_box("board", mat, sx=60, sy=5, sz=80)
    primitive_box("sign",  mat, sx=50, sy=4, sz=40, oz=30)


def build_instrument():
    mat = make_material("instr", 0.55, 0.40, 0.2)
    primitive_box("body",  mat, sx=30, sy=10, sz=50)
    primitive_cylinder("neck", mat, radius=4, height=40, oz=50)


def build_door_frame(color_mat_name, r, g, b):
    """Door-shaped frame — flat rectangle with a coloured border."""
    mat_f = make_material("frame_" + color_mat_name, r, g, b)
    mat_d = make_material("door_"  + color_mat_name,
                           r * 0.7, g * 0.7, b * 0.7)
    # outer frame
    primitive_box("frame_l", mat_f, sx=8,  sy=6, sz=150)
    primitive_box("frame_r", mat_f, sx=8,  sy=6, sz=150, ox=72)
    primitive_box("lintel",  mat_f, sx=88, sy=6, sz=10,  oz=140)
    # door panel
    primitive_box("panel",   mat_d, sx=72, sy=4, sz=140, ox=8)


def build_floor(name, sx=4800, sy=4800, color=(0.4, 0.38, 0.35)):
    mat = make_material(name, *color)
    primitive_box(name, mat, sx=sx, sy=sy, sz=10)


def build_wall(name, sx=4400, sz=500, color=(0.45, 0.42, 0.38)):
    mat = make_material(name, *color)
    primitive_box(name, mat, sx=sx, sy=20, sz=sz)


# ===========================================================================
# Build and export all meshes
# ===========================================================================

MESHES = [
    # (output filename,  build function,              build kwargs)
    ("plant_herb.dae",          build_plant_herb,        {}),
    ("plant_mushroom.dae",      build_plant_mushroom,    {}),
    ("tree.dae",                build_tree,              {}),
    ("log.dae",                 build_log,               {}),
    ("branch.dae",              build_branch,            {}),
    ("mineral_iron.dae",        build_mineral_iron,      {}),
    ("mineral_stone.dae",       build_mineral_stone,     {}),
    ("ingot.dae",               build_ingot,             {}),
    ("bed.dae",                 build_bed,               {}),
    ("anvil.dae",               build_anvil,             {}),
    ("forge.dae",               build_forge,             {}),
    ("pillar.dae",              build_pillar,            {}),
    ("pass_token.dae",          build_pass_token,        {}),
    ("apparatus_mortar.dae",    build_apparatus_mortar,  {}),
    ("apparatus_alembic.dae",   build_apparatus_alembic, {}),
    ("apparatus_calcinator.dae",build_apparatus_calcinator,{}),
    ("apparatus_retort.dae",    build_apparatus_retort,  {}),
    ("mine_refresh.dae",        build_mine_refresh,      {}),
    ("instrument.dae",          build_instrument,        {}),
    # Doors (colored frames)
    ("door_green.dae",          build_door_frame,        {"color_mat_name":"green","r":0.2,"g":0.75,"b":0.2}),
    ("door_brown.dae",          build_door_frame,        {"color_mat_name":"brown","r":0.5,"g":0.3,"b":0.1}),
    ("door_gray.dae",           build_door_frame,        {"color_mat_name":"gray", "r":0.5,"g":0.5,"b":0.55}),
    # Floors + walls
    ("floor_hub.dae",           build_floor,             {"name":"floor_hub","sx":4800,"sy":4800}),
    ("floor_garden.dae",        build_floor,             {"name":"floor_garden","sx":2200,"sy":2200,"color":(0.35,0.55,0.25)}),
    ("floor_forest.dae",        build_floor,             {"name":"floor_forest","sx":3000,"sy":3000,"color":(0.25,0.40,0.18)}),
    ("floor_mine.dae",          build_floor,             {"name":"floor_mine","sx":2200,"sy":1800,"color":(0.30,0.28,0.26)}),
    ("wall_hub.dae",            build_wall,              {"name":"wall_hub","sx":4400,"sz":500}),
    ("wall_small.dae",          build_wall,              {"name":"wall_small","sx":2200,"sz":500}),
    # Weapons
    ("axe_wooden.dae",          build_axe,               {"name":"axe_wooden","color":(0.5,0.35,0.15),"head_color":(0.7,0.6,0.4)}),
    ("axe_iron.dae",            build_axe,               {"name":"axe_iron","color":(0.45,0.30,0.10),"head_color":(0.55,0.55,0.6)}),
    ("pickaxe_basic.dae",       build_pickaxe,           {"name":"pick_basic","head_color":(0.55,0.50,0.40)}),
    ("pickaxe_iron.dae",        build_pickaxe,           {"name":"pick_iron","head_color":(0.55,0.55,0.60)}),
]

print(f"\n[HubWorld] Generating {len(MESHES)} mesh(es)...")
for filename, builder, kwargs in MESHES:
    reset_scene()
    builder(**kwargs)
    export_dae(filename)

print("\n[HubWorld] Done.")
print("Next: add the data/ directory to openmw.cfg and run build.py.")
