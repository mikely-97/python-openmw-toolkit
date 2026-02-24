"""hub_world/generate_meshes.py — Generate placeholder 3-D assets for the Hub World addon.

Pure Python (stdlib only) — no Blender required.  Writes COLLADA 1.4.1
(.dae) files with <blinn> materials directly, which OpenMW's COLLADA loader
reads correctly.

Run:
    python generate_meshes.py          # from hub_world/ or any working dir

Output:
    hub_world/data/meshes/hub_world/*.dae

Room dimensions used here are 60 % of the original design (perimeter scale).
Any change here must be reflected in build.py cell placements.

Key dimensions (game units, 1 GU = 1 cm):
    Hub floor          : 2880 × 2880 GU
    Hub walls placed at: ±1320 GU from centre
    Door activators at : ±1290 GU (10 units inside wall)
    Pillars            : ±900 GU
"""

import math
import os

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR    = os.path.join(SCRIPT_DIR, "data", "meshes", "hub_world")
os.makedirs(OUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Vector helpers
# ---------------------------------------------------------------------------

def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

def _normalize(v):
    m = (v[0]**2 + v[1]**2 + v[2]**2) ** 0.5
    return (v[0]/m, v[1]/m, v[2]/m) if m > 1e-10 else (0.0, 0.0, 1.0)

def _tri_normal(v0, v1, v2):
    e1 = (v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2])
    e2 = (v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2])
    return _normalize(_cross(e1, e2))


# ---------------------------------------------------------------------------
# SubMesh — geometry + single flat-colour material
# ---------------------------------------------------------------------------

class SubMesh:
    """A mesh part with a single blinn flat-colour material."""

    def __init__(self, name: str, r: float, g: float, b: float):
        self.name = name
        self.r, self.g, self.b = r, g, b
        self.triangles: list = []   # list of ((x,y,z),(x,y,z),(x,y,z))

    # ---- low-level primitives ----

    def _tri(self, v0, v1, v2):
        self.triangles.append((v0, v1, v2))

    def _quad(self, v0, v1, v2, v3):
        """Quad assumed CCW from outside so cross-product gives outward normal."""
        self._tri(v0, v1, v2)
        self._tri(v0, v2, v3)

    # ---- shape builders (all return self for chaining) ----

    def box(self, sx, sy, sz, ox=0.0, oy=0.0, oz=0.0):
        """Axis-aligned box.  Bottom-centre at (ox, oy, oz), size (sx, sy, sz)."""
        hx, hy = sx / 2, sy / 2
        x0, x1 = ox - hx, ox + hx
        y0, y1 = oy - hy, oy + hy
        z0, z1 = oz, oz + sz
        # bottom  (normal -Z)
        self._quad((x0,y1,z0),(x1,y1,z0),(x1,y0,z0),(x0,y0,z0))
        # top     (normal +Z)
        self._quad((x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1))
        # south   (normal -Y)
        self._quad((x0,y0,z0),(x1,y0,z0),(x1,y0,z1),(x0,y0,z1))
        # north   (normal +Y)
        self._quad((x1,y1,z0),(x0,y1,z0),(x0,y1,z1),(x1,y1,z1))
        # west    (normal -X)
        self._quad((x0,y0,z0),(x0,y0,z1),(x0,y1,z1),(x0,y1,z0))
        # east    (normal +X)
        self._quad((x1,y1,z0),(x1,y1,z1),(x1,y0,z1),(x1,y0,z0))
        return self

    def cylinder(self, radius, height, segments=12, ox=0.0, oy=0.0, oz=0.0):
        """Vertical cylinder.  Bottom-centre at (ox, oy, oz)."""
        pb = [(ox + math.cos(2*math.pi*i/segments)*radius,
               oy + math.sin(2*math.pi*i/segments)*radius, oz)
              for i in range(segments)]
        pt = [(x, y, oz + height) for x, y, _ in pb]
        cb = (ox, oy, oz)
        ct = (ox, oy, oz + height)
        for i in range(segments):
            n = (i + 1) % segments
            self._quad(pb[i], pb[n], pt[n], pt[i])  # side (outward normal)
            self._tri(cb, pb[n], pb[i])              # bottom cap (normal -Z)
            self._tri(ct, pt[i], pt[n])              # top cap    (normal +Z)
        return self

    def cone(self, radius, height, segments=12, ox=0.0, oy=0.0, oz=0.0):
        """Cone with apex at (ox, oy, oz+height)."""
        pb = [(ox + math.cos(2*math.pi*i/segments)*radius,
               oy + math.sin(2*math.pi*i/segments)*radius, oz)
              for i in range(segments)]
        apex = (ox, oy, oz + height)
        cb   = (ox, oy, oz)
        for i in range(segments):
            n = (i + 1) % segments
            self._tri(pb[i], pb[n], apex)   # side (outward-up normal)
            self._tri(cb, pb[n], pb[i])     # bottom cap (normal -Z)
        return self


# ---------------------------------------------------------------------------
# White 1×1 DDS texture (shared by all materials for diffuse slot)
# ---------------------------------------------------------------------------
# OpenMW's COLLADA loader requires a *texture* on the diffuse slot to render
# material colours correctly.  Colour-only diffuse causes a red fallback.
# We create a single 1×1 white DDS and use UV (0,0) on every vertex so that
# each material's blinn diffuse samples a white pixel while the per-mesh
# colour lives in the *ambient* channel (which accepts plain colours fine).
# ---------------------------------------------------------------------------

import struct as _struct

_WHITE_DDS_VFS  = "textures/hw_white.dds"   # absolute VFS path used in DAE <init_from>
# OpenMW resolves COLLADA <init_from> as an absolute VFS path.
# The file must therefore live at <DATA_DIR>/textures/hw_white.dds.

_BRICK_DDS_VFS  = "textures/hw_brick.dds"   # 64×64 light-gray brick tile


def _make_white_dds() -> bytes:
    """Return the raw bytes of a 1×1 uncompressed RGBA white DDS file."""
    # DDS_PIXELFORMAT (32 bytes)
    pf = _struct.pack(
        "<IIIIIIII",
        32,           # dwSize
        0x41,         # dwFlags: DDPF_RGB(0x40) | DDPF_ALPHAPIXELS(0x01)
        0,            # dwFourCC: uncompressed
        32,           # dwRGBBitCount
        0x00FF0000,   # dwRBitMask
        0x0000FF00,   # dwGBitMask
        0x000000FF,   # dwBBitMask
        0xFF000000,   # dwABitMask
    )
    # DDS_HEADER (124 bytes)
    header = _struct.pack(
        "<IIIIIII",
        124,    # dwSize
        0x100F, # dwFlags: CAPS|HEIGHT|WIDTH|PIXELFORMAT|PITCH
        1,      # dwHeight
        1,      # dwWidth
        4,      # dwPitchOrLinearSize (4 bytes/row for 32-bit RGBA)
        0,      # dwDepth
        0,      # dwMipMapCount
    )
    header += _struct.pack("<11I", *([0] * 11))  # dwReserved1[11]
    header += pf
    header += _struct.pack("<IIIII", 0x1000, 0, 0, 0, 0)  # dwCaps…dwReserved2
    assert len(header) == 124
    pixel = _struct.pack("<BBBB", 255, 255, 255, 255)   # BGRA white
    return b"DDS " + header + pixel


def write_white_dds(out_dir: str):
    """Write hw_white.dds into <out_dir>/textures/ (creates dir if absent).

    OpenMW resolves COLLADA <init_from> as an absolute VFS path, so the file
    must live at <DATA_DIR>/textures/hw_white.dds.
    """
    tex_dir = os.path.join(out_dir, "textures")
    os.makedirs(tex_dir, exist_ok=True)
    path = os.path.join(tex_dir, "hw_white.dds")
    with open(path, "wb") as f:
        f.write(_make_white_dds())
    return path


def _make_icon_dds(r: int, g: int, b: int, size: int = 32) -> bytes:
    """Return a solid-colour size×size uncompressed RGBA DDS for use as an icon."""
    pf = _struct.pack(
        "<IIIIIIII",
        32, 0x41, 0, 32,
        0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000,
    )
    header = _struct.pack("<IIIIIII", 124, 0x100F, size, size, size * 4, 0, 0)
    header += _struct.pack("<11I", *([0] * 11))
    header += pf
    header += _struct.pack("<IIIII", 0x1000, 0, 0, 0, 0)
    assert len(header) == 124
    pixel = bytes([b, g, r, 255])   # BGRA byte order
    return b"DDS " + header + pixel * (size * size)


def write_herb_icons(out_dir: str):
    """Write solid-colour DDS icon files to <out_dir>/icons/hub_world/."""
    icon_dir = os.path.join(out_dir, "icons", "hub_world")
    os.makedirs(icon_dir, exist_ok=True)
    icons = {
        "herb_basil.dds": _make_icon_dds(30, 120, 40),    # dark green
        "herb_mint.dds":  _make_icon_dds(40, 170, 130),   # cyan-green
    }
    for name, data in icons.items():
        path = os.path.join(icon_dir, name)
        with open(path, "wb") as f:
            f.write(data)
        print(f"[HubWorld] Icon : {path}")
    return icon_dir


def _make_brick_dds() -> bytes:
    """Return a 64×64 light-gray brick-pattern DDS (uncompressed BGRA).

    Layout — 32-row tile repeated twice (two brick courses per tile):
      rows  0-1  : mortar
      rows  2-13 : course A — two bricks (cols 2-31, 34-63), 1-px dark edge
      rows 14-17 : mortar
      rows 18-29 : course B — three half-bricks (offset by half), same edges
      rows 30-31 : mortar
    """
    W, H = 64, 64
    MORTAR = (190, 190, 190, 255)   # light gray
    BRICK  = (152, 152, 162, 255)   # slightly cooler gray
    EDGE   = (118, 118, 128, 255)   # dark 1-px outline for depth

    def cell(row, col):
        r = row % 32    # tile repeats every 32 rows

        if r <= 1 or 14 <= r <= 17 or r >= 30:
            return MORTAR

        if 2 <= r <= 13:                          # course A
            if col < 2 or 32 <= col < 34:
                return MORTAR
            if 2 <= col <= 31:
                if col in (2, 31) or r in (2, 13):
                    return EDGE
                return BRICK
            if 34 <= col <= 63:
                if col in (34, 63) or r in (2, 13):
                    return EDGE
                return BRICK
            return MORTAR

        if 18 <= r <= 29:                         # course B (half-offset)
            if 16 <= col < 18 or 48 <= col < 50:
                return MORTAR
            if col <= 15:
                if col in (0, 15) or r in (18, 29):
                    return EDGE
                return BRICK
            if 18 <= col <= 47:
                if col in (18, 47) or r in (18, 29):
                    return EDGE
                return BRICK
            if col >= 50:
                if col in (50, 63) or r in (18, 29):
                    return EDGE
                return BRICK
            return MORTAR

        return MORTAR

    pixels = bytearray()
    for row in range(H):
        for col in range(W):
            ri, gi, bi, ai = cell(row, col)
            pixels += bytes([bi, gi, ri, ai])   # BGRA byte order

    pf = _struct.pack(
        "<IIIIIIII",
        32, 0x41, 0, 32,
        0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000,
    )
    header = _struct.pack("<IIIIIII", 124, 0x100F, H, W, W * 4, 0, 0)
    header += _struct.pack("<11I", *([0] * 11))
    header += pf
    header += _struct.pack("<IIIII", 0x1000, 0, 0, 0, 0)
    assert len(header) == 124
    return b"DDS " + header + bytes(pixels)


def write_brick_dds(out_dir: str):
    """Write hw_brick.dds into <out_dir>/textures/."""
    tex_dir = os.path.join(out_dir, "textures")
    os.makedirs(tex_dir, exist_ok=True)
    path = os.path.join(tex_dir, "hw_brick.dds")
    with open(path, "wb") as f:
        f.write(_make_brick_dds())
    return path


# ---------------------------------------------------------------------------
# COLLADA writer
# ---------------------------------------------------------------------------

def _f(v):
    """Format a float compactly."""
    return f"{v:.6g}"


def _uv_for_vertex(pos, nrm, tile_size: float):
    """World-space tri-planar UV projection.

    Projects *pos* onto the axis plane most aligned with *nrm*, scaled so
    that *tile_size* game units = 1 UV repeat.
    """
    ax, ay, az = abs(nrm[0]), abs(nrm[1]), abs(nrm[2])
    if az >= ax and az >= ay:   # floor / ceiling (normal ≈ ±Z)
        return pos[0] / tile_size, pos[1] / tile_size
    elif ax >= ay:              # east / west face (normal ≈ ±X)
        return pos[1] / tile_size, pos[2] / tile_size
    else:                       # north / south face (normal ≈ ±Y)
        return pos[0] / tile_size, pos[2] / tile_size


def write_dae(filepath: str, submeshes: list,
              texture_vfs: str | None = None,
              tile_size: float = 0.0):
    """Write a COLLADA 1.4.1 file.

    Parameters
    ----------
    texture_vfs:
        Absolute VFS path to the diffuse texture.  Defaults to the shared
        1×1 white DDS (hw_white.dds).
    tile_size:
        When > 0, compute per-vertex world-space tiling UVs scaled so that
        *tile_size* game units = 1 UV repeat.  When 0 all vertices use (0,0).

    Notes
    -----
    * Each submesh colour lives in the COLLADA ambient channel.
    * Normals are per-triangle (flat shading; no vertex sharing).
    * <bind_vertex_input semantic="CHANNEL1"> is required — using *symbol*
      instead causes a COLLADA DOM schema violation and a SIGSEGV in OpenMW.
    """
    img_vfs = texture_vfs or _WHITE_DDS_VFS
    # Derive a stable XML ID from the VFS path
    img_id  = "img_" + img_vfs.replace("/", "_").replace(".", "_")

    L = []
    A = L.append

    A('<?xml version="1.0" encoding="utf-8"?>')
    A('<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">')
    A('  <asset>')
    A('    <created>2026-01-01</created>')
    A('    <modified>2026-01-01</modified>')
    A('    <unit name="centimeter" meter="0.01"/>')
    A('    <up_axis>Z_UP</up_axis>')
    A('  </asset>')

    # ---- library_images ----
    A('  <library_images>')
    A(f'    <image id="{img_id}" name="{img_id}">')
    A(f'      <init_from>{img_vfs}</init_from>')
    A('    </image>')
    A('  </library_images>')

    # ---- library_effects ----
    A('  <library_effects>')
    for sm in submeshes:
        r, g, b = _f(sm.r), _f(sm.g), _f(sm.b)
        suf = sm.name
        A(f'    <effect id="Effect_{suf}">')
        A('      <profile_COMMON>')
        A(f'        <newparam sid="surf_{suf}">')
        A('          <surface type="2D">')
        A(f'            <init_from>{img_id}</init_from>')
        A('          </surface>')
        A('        </newparam>')
        A(f'        <newparam sid="samp_{suf}">')
        A('          <sampler2D>')
        A(f'            <source>surf_{suf}</source>')
        A('          </sampler2D>')
        A('        </newparam>')
        A('        <technique sid="common">')
        A('          <blinn>')
        A(f'            <emission><color sid="emission">0 0 0 1</color></emission>')
        A(f'            <ambient><color sid="ambient">{r} {g} {b} 1</color></ambient>')
        A(f'            <diffuse><texture texture="samp_{suf}" texcoord="CHANNEL1"/></diffuse>')
        A(f'            <specular><color sid="specular">0.1 0.1 0.1 1</color></specular>')
        A(f'            <shininess><float sid="shininess">20</float></shininess>')
        A('          </blinn>')
        A('        </technique>')
        A('      </profile_COMMON>')
        A('    </effect>')
    A('  </library_effects>')

    # ---- library_materials ----
    A('  <library_materials>')
    for sm in submeshes:
        A(f'    <material id="Mat_{sm.name}" name="{sm.name}">')
        A(f'      <instance_effect url="#Effect_{sm.name}"/>')
        A('    </material>')
    A('  </library_materials>')

    # ---- library_geometries ----
    A('  <library_geometries>')
    for sm in submeshes:
        tris = sm.triangles
        nt   = len(tris)
        nv   = nt * 3   # unique vertices (flat shading — no vertex sharing)

        pos_floats = []
        nrm_floats = []
        uv_floats  = []
        p_ints     = []

        for i, tri in enumerate(tris):
            for v in tri:
                pos_floats += [v[0], v[1], v[2]]
            n = _tri_normal(*tri)
            nrm_floats += [n[0], n[1], n[2]]
            base = i * 3
            if tile_size > 0.0:
                # Per-vertex world-space tiling UV; UV index == vertex index
                for v in tri:
                    u, tv = _uv_for_vertex(v, n, tile_size)
                    uv_floats += [u, tv]
                p_ints += [base,   i, base,
                           base+1, i, base+1,
                           base+2, i, base+2]
            else:
                # All vertices share a single (0,0) UV — samples white pixel
                p_ints += [base, i, 0, base+1, i, 0, base+2, i, 0]

        if tile_size <= 0.0:
            uv_floats = [0.0, 0.0]
        uv_count = nv if tile_size > 0.0 else 1

        gid   = f'Geom_{sm.name}'
        pos_s = ' '.join(_f(x) for x in pos_floats)
        nrm_s = ' '.join(_f(x) for x in nrm_floats)
        uv_s  = ' '.join(_f(x) for x in uv_floats)
        p_s   = ' '.join(str(x) for x in p_ints)

        A(f'    <geometry id="{gid}" name="{sm.name}">')
        A('      <mesh>')

        A(f'        <source id="{gid}-positions">')
        A(f'          <float_array id="{gid}-positions-array" count="{len(pos_floats)}">{pos_s}</float_array>')
        A('          <technique_common>')
        A(f'            <accessor source="#{gid}-positions-array" count="{nv}" stride="3">')
        A('              <param name="X" type="float"/>')
        A('              <param name="Y" type="float"/>')
        A('              <param name="Z" type="float"/>')
        A('            </accessor>')
        A('          </technique_common>')
        A('        </source>')

        A(f'        <source id="{gid}-normals">')
        A(f'          <float_array id="{gid}-normals-array" count="{len(nrm_floats)}">{nrm_s}</float_array>')
        A('          <technique_common>')
        A(f'            <accessor source="#{gid}-normals-array" count="{nt}" stride="3">')
        A('              <param name="X" type="float"/>')
        A('              <param name="Y" type="float"/>')
        A('              <param name="Z" type="float"/>')
        A('            </accessor>')
        A('          </technique_common>')
        A('        </source>')

        A(f'        <source id="{gid}-texcoords">')
        A(f'          <float_array id="{gid}-texcoords-array" count="{len(uv_floats)}">{uv_s}</float_array>')
        A('          <technique_common>')
        A(f'            <accessor source="#{gid}-texcoords-array" count="{uv_count}" stride="2">')
        A('              <param name="S" type="float"/>')
        A('              <param name="T" type="float"/>')
        A('            </accessor>')
        A('          </technique_common>')
        A('        </source>')

        A(f'        <vertices id="{gid}-vertices">')
        A(f'          <input semantic="POSITION" source="#{gid}-positions"/>')
        A('        </vertices>')

        A(f'        <triangles count="{nt}" material="{sm.name}">')
        A(f'          <input semantic="VERTEX"   source="#{gid}-vertices"  offset="0"/>')
        A(f'          <input semantic="NORMAL"   source="#{gid}-normals"   offset="1"/>')
        A(f'          <input semantic="TEXCOORD" source="#{gid}-texcoords" offset="2" set="0"/>')
        A(f'          <p>{p_s}</p>')
        A('        </triangles>')

        A('      </mesh>')
        A(f'    </geometry>')
    A('  </library_geometries>')

    # ---- library_visual_scenes ----
    A('  <library_visual_scenes>')
    A('    <visual_scene id="Scene" name="Scene">')
    for sm in submeshes:
        gid = f'Geom_{sm.name}'
        A(f'      <node id="Node_{sm.name}" name="{sm.name}" type="NODE">')
        A(f'        <instance_geometry url="#{gid}">')
        A('          <bind_material>')
        A('            <technique_common>')
        A(f'              <instance_material symbol="{sm.name}" target="#Mat_{sm.name}">')
        A(f'                <bind_vertex_input semantic="CHANNEL1" input_semantic="TEXCOORD" input_set="0"/>')
        A(f'              </instance_material>')
        A('            </technique_common>')
        A('          </bind_material>')
        A('        </instance_geometry>')
        A('      </node>')
    A('    </visual_scene>')
    A('  </library_visual_scenes>')

    A('  <scene>')
    A('    <instance_visual_scene url="#Scene"/>')
    A('  </scene>')
    A('</COLLADA>')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')


def out(filename: str):
    return os.path.join(OUT_DIR, filename)


# ===========================================================================
# Mesh builder functions — return list[SubMesh]
# ===========================================================================

def build_plant_herb():
    """Herb plant — tall enough for the interact raycast to hit reliably.

    Previous mesh (23 GU tall, 4-GU-wide leaves) was invisible to the raycast
    at player eye-level (~130 GU).  This version reaches 90 GU with wide cross
    leaves at two heights, giving a solid click target.
    """
    return [
        SubMesh("stem",    0.22, 0.48, 0.08).cylinder(radius=5, height=90),
        SubMesh("leaf_lo", 0.14, 0.66, 0.10).box(50, 12, 14, oz=30),  # lower fan
        SubMesh("leaf_hi", 0.14, 0.66, 0.10).box(12, 50, 14, oz=60),  # upper fan
    ]


def build_herb_item():
    """Small herb bundle — the inventory/dropped-item mesh.

    Much smaller than the activator plant_herb (90 GU); this is the picked-up
    herb as it appears in the world or in the inventory model slot.
    """
    return [
        SubMesh("stem_i",    0.22, 0.48, 0.08).cylinder(radius=2, height=14),
        SubMesh("leaf_i_lo", 0.14, 0.66, 0.10).box(16, 5, 6, oz=4),
        SubMesh("leaf_i_hi", 0.14, 0.66, 0.10).box(5, 16, 6, oz=9),
    ]


def build_plant_mushroom():
    return [
        SubMesh("mstem", 0.82, 0.78, 0.62).cylinder(radius=5,  height=20),
        SubMesh("mcap",  0.65, 0.18, 0.08).cylinder(radius=30, height=10, oz=18),
    ]


def build_tree():
    return [
        SubMesh("trunk",  0.35, 0.22, 0.08).cylinder(radius=12,  height=100),
        SubMesh("canopy", 0.10, 0.42, 0.08).cone(    radius=70,  height=130, oz=80),
    ]


def build_log():
    return [SubMesh("log", 0.50, 0.30, 0.10).cylinder(radius=10, height=60)]


def build_branch():
    return [SubMesh("branch", 0.45, 0.28, 0.08).cylinder(radius=4, height=40)]


def build_mineral_iron():
    return [SubMesh("iron", 0.35, 0.35, 0.40).box(60, 50, 30)]


def build_mineral_stone():
    return [SubMesh("stone", 0.50, 0.48, 0.45).box(55, 45, 25)]


def build_ingot():
    return [SubMesh("ingot", 0.60, 0.60, 0.65).box(20, 8, 5)]


def build_bed():
    return [
        SubMesh("bedframe",  0.42, 0.26, 0.10).box(80,  160, 20),
        SubMesh("mattress",  0.88, 0.82, 0.70).box(75,  155, 15, oz=20),
        SubMesh("headboard", 0.42, 0.26, 0.10).box(80,   10, 60, oy=75),
    ]


def build_anvil():
    # IRL anvils are dark grey/black wrought iron
    return [
        SubMesh("base", 0.08, 0.08, 0.10).box(60, 40, 25),
        SubMesh("neck", 0.08, 0.08, 0.10).box(20, 30, 20, oz=25),
        SubMesh("horn", 0.08, 0.08, 0.10).box(70, 20, 15, oz=45),
    ]


def build_forge():
    # IRL forges are dark clay/stone with an orange fire glow
    return [
        SubMesh("body",    0.32, 0.20, 0.14).box(80, 60, 60),
        SubMesh("chimney", 0.28, 0.22, 0.18).cylinder(radius=10, height=80, oz=60),
        SubMesh("glow",    0.95, 0.45, 0.02).box(40, 40, 5, oz=58),
    ]


def build_pillar():
    return [SubMesh("pillar", 0.58, 0.55, 0.52).cylinder(radius=20, height=400, segments=8)]


def build_pass_token():
    return [SubMesh("token", 0.85, 0.75, 0.10).cylinder(radius=10, height=3)]


def build_apparatus_mortar():
    return [
        SubMesh("bowl",   0.55, 0.50, 0.45).cylinder(radius=18, height=12),
        SubMesh("pestle", 0.50, 0.45, 0.40).cylinder(radius=5,  height=35, oz=12),
    ]


def build_apparatus_alembic():
    return [
        SubMesh("body",  0.40, 0.55, 0.70).cylinder(radius=18, height=30),
        SubMesh("top",   0.40, 0.55, 0.70).cone(    radius=12, height=25, oz=30),
        SubMesh("spout", 0.40, 0.55, 0.70).cylinder(radius=3,  height=20, oz=55),
    ]


def build_apparatus_calcinator():
    return [
        SubMesh("box", 0.60, 0.55, 0.30).box(40, 40, 30),
        SubMesh("lid", 0.60, 0.55, 0.30).cylinder(radius=22, height=8, oz=30),
    ]


def build_apparatus_retort():
    return [
        SubMesh("bulb", 0.50, 0.30, 0.50).cylinder(radius=20, height=35),
        SubMesh("neck", 0.50, 0.30, 0.50).cylinder(radius=5,  height=25, oz=35),
        SubMesh("arm",  0.50, 0.30, 0.50).cylinder(radius=3,  height=20, oz=45),
    ]


def build_mine_refresh():
    return [
        SubMesh("board", 0.45, 0.35, 0.20).box(60, 5, 80),
        SubMesh("sign",  0.55, 0.45, 0.25).box(50, 4, 40, oz=30),
    ]


def build_instrument():
    return [
        SubMesh("body", 0.55, 0.40, 0.20).box(30, 10, 50),
        SubMesh("neck", 0.50, 0.35, 0.15).cylinder(radius=4, height=40, oz=50),
    ]


def build_door_frame(color_name, r, g, b):
    dr, dg, db = r*0.7, g*0.7, b*0.7
    return [
        SubMesh(f"frame_{color_name}", r,  g,  b ).box(8,  6, 150),
        SubMesh(f"framer_{color_name}", r,  g,  b ).box(8,  6, 150, ox=72),
        SubMesh(f"lintel_{color_name}", r,  g,  b ).box(88, 6,  10, oz=140),
        SubMesh(f"panel_{color_name}", dr, dg, db).box(72, 4, 140, ox=8),
    ]


def build_axe(name, r_h, g_h, b_h, r_b, g_b, b_b):
    return [
        SubMesh(name + "_handle", r_h, g_h, b_h).cylinder(radius=4, height=80),
        SubMesh(name + "_blade",  r_b, g_b, b_b).box(40, 10, 30, oz=65),
    ]


def build_pickaxe(name, r_b, g_b, b_b):
    return [
        SubMesh(name + "_handle", 0.50, 0.35, 0.15).cylinder(radius=4, height=90),
        SubMesh(name + "_head",   r_b,  g_b,  b_b ).box(60, 8, 10, oz=82),
    ]


def build_floor(name, sx, sy, r, g, b):
    return [SubMesh(name, r, g, b).box(sx, sy, 10)]


def build_wall(name, sx, sz, r, g, b):
    return [SubMesh(name, r, g, b).box(sx, 20, sz)]


def build_wall_ew(name, sy, sz, r, g, b):
    """East/west-oriented wall: thin in X (20 GU), length along Y axis.

    Place at (±1320, 0, 0) with *no rotation* — avoids mesh rotation which
    can cause UV-binding failures in OpenMW's COLLADA loader.
    """
    return [SubMesh(name, r, g, b).box(20, sy, sz)]


def build_vending_machine():
    """Boxy vending machine: body + display panel + logo strip + tray + buttons.

    Dimensions (GU):  80 wide × 50 deep × 200 tall
    Front faces -Y (south, toward the player when placed at hub centre).
    The vendor NPC should be placed just in front of this (at slightly lower Y).
    """
    return [
        # Main body — dark blue-grey
        SubMesh("vm_body",    0.15, 0.18, 0.28).box(80, 50, 200),
        # Front display window — light blue, protruding 8 units from front face
        # Body front is at y = -25; panel centre at y = -29 → y: -33 to -25
        SubMesh("vm_panel",   0.35, 0.55, 0.80).box(62, 8, 90, oy=-29, oz=55),
        # Logo / brand strip at top front — bright orange-yellow
        SubMesh("vm_logo",    0.90, 0.55, 0.05).box(70, 6, 22, oy=-28, oz=165),
        # Buttons area — red strip below logo
        SubMesh("vm_buttons", 0.80, 0.15, 0.10).box(55, 5, 18, oy=-28, oz=148),
        # Dispensing tray at bottom front — dark grey, sticks out further
        SubMesh("vm_tray",    0.22, 0.22, 0.30).box(60, 14, 14, oy=-32, oz=5),
        # Side accent strips — slightly lighter than body
        SubMesh("vm_strip_l", 0.25, 0.28, 0.42).box(4, 50, 200, ox=-40),
        SubMesh("vm_strip_r", 0.25, 0.28, 0.42).box(4, 50, 200, ox=36),
    ]


# ===========================================================================
# Master mesh list
# ===========================================================================

MESHES = [
    # (output filename,          builder,              kwargs)
    ("plant_herb.dae",           build_plant_herb,     {}),
    ("herb_item.dae",            build_herb_item,      {}),
    ("plant_mushroom.dae",       build_plant_mushroom, {}),
    ("tree.dae",                 build_tree,           {}),
    ("log.dae",                  build_log,            {}),
    ("branch.dae",               build_branch,         {}),
    ("mineral_iron.dae",         build_mineral_iron,   {}),
    ("mineral_stone.dae",        build_mineral_stone,  {}),
    ("ingot.dae",                build_ingot,          {}),
    ("bed.dae",                  build_bed,            {}),
    ("anvil.dae",                build_anvil,          {}),
    ("forge.dae",                build_forge,          {}),
    ("pillar.dae",               build_pillar,         {}),
    ("pass_token.dae",           build_pass_token,     {}),
    ("apparatus_mortar.dae",     build_apparatus_mortar,    {}),
    ("apparatus_alembic.dae",    build_apparatus_alembic,   {}),
    ("apparatus_calcinator.dae", build_apparatus_calcinator,{}),
    ("apparatus_retort.dae",     build_apparatus_retort,    {}),
    ("mine_refresh.dae",         build_mine_refresh,   {}),
    ("instrument.dae",           build_instrument,     {}),
    # Doors (coloured archways)
    ("door_green.dae",  build_door_frame, {"color_name":"green","r":0.12,"g":0.72,"b":0.12}),
    ("door_brown.dae",  build_door_frame, {"color_name":"brown","r":0.48,"g":0.28,"b":0.10}),
    ("door_gray.dae",   build_door_frame, {"color_name":"gray", "r":0.45,"g":0.45,"b":0.48}),
    # Floors  (60 % scale from original)
    # hub floor/ceiling use the brick tile; other cells keep plain colour
    ("floor_hub.dae",    build_floor, {"name":"floor_hub",    "sx":2880,"sy":2880,"r":0.45,"g":0.45,"b":0.45}, {"texture_vfs": _BRICK_DDS_VFS, "tile_size": 128.0}),
    ("floor_garden.dae", build_floor, {"name":"floor_garden", "sx":1320,"sy":1320,"r":0.20,"g":0.55,"b":0.14}),
    ("floor_forest.dae", build_floor, {"name":"floor_forest", "sx":1800,"sy":1800,"r":0.14,"g":0.38,"b":0.10}),
    ("floor_mine.dae",   build_floor, {"name":"floor_mine",   "sx":1320,"sy":1080,"r":0.22,"g":0.20,"b":0.18}),
    # Walls  (60 % scale) — brick-textured with tiling UVs
    # N/S walls: long in X, placed with no rotation
    ("wall_hub.dae",      build_wall,    {"name":"wall_hub",      "sx":2640,"sz":500,"r":0.38,"g":0.38,"b":0.40}, {"texture_vfs": _BRICK_DDS_VFS, "tile_size": 128.0}),
    ("wall_small.dae",    build_wall,    {"name":"wall_small",    "sx":1320,"sz":500,"r":0.38,"g":0.38,"b":0.40}, {"texture_vfs": _BRICK_DDS_VFS, "tile_size": 128.0}),
    # E/W walls: long in Y, placed with no rotation — avoids COLLADA UV-binding issue
    ("wall_hub_ew.dae",   build_wall_ew, {"name":"wall_hub_ew",   "sy":2640,"sz":500,"r":0.38,"g":0.38,"b":0.40}, {"texture_vfs": _BRICK_DDS_VFS, "tile_size": 128.0}),
    ("wall_small_ew.dae", build_wall_ew, {"name":"wall_small_ew", "sy":1320,"sz":500,"r":0.38,"g":0.38,"b":0.40}, {"texture_vfs": _BRICK_DDS_VFS, "tile_size": 128.0}),
    # Forest walls (1800 GU) — N/S long in X, E/W long in Y
    ("wall_forest.dae",    build_wall,    {"name":"wall_forest",    "sx":1800,"sz":500,"r":0.38,"g":0.38,"b":0.40}, {"texture_vfs": _BRICK_DDS_VFS, "tile_size": 128.0}),
    ("wall_forest_ew.dae", build_wall_ew, {"name":"wall_forest_ew", "sy":1800,"sz":500,"r":0.38,"g":0.38,"b":0.40}, {"texture_vfs": _BRICK_DDS_VFS, "tile_size": 128.0}),
    # Mine E/W wall (1080 GU long in Y — mine floor is 1320×1080)
    ("wall_mine_ew.dae",   build_wall_ew, {"name":"wall_mine_ew",   "sy":1080,"sz":500,"r":0.38,"g":0.38,"b":0.40}, {"texture_vfs": _BRICK_DDS_VFS, "tile_size": 128.0}),
    # Weapons
    ("axe_wooden.dae",   build_axe,     {"name":"axe_wooden", "r_h":0.50,"g_h":0.35,"b_h":0.15,"r_b":0.70,"g_b":0.60,"b_b":0.40}),
    ("axe_iron.dae",     build_axe,     {"name":"axe_iron",   "r_h":0.45,"g_h":0.30,"b_h":0.10,"r_b":0.55,"g_b":0.55,"b_b":0.60}),
    ("pickaxe_basic.dae",build_pickaxe, {"name":"pick_basic", "r_b":0.55,"g_b":0.50,"b_b":0.40}),
    ("pickaxe_iron.dae", build_pickaxe, {"name":"pick_iron",  "r_b":0.55,"g_b":0.55,"b_b":0.60}),
    # Vending machine (decorative STAT, NPC placed in front)
    ("vending_machine.dae", build_vending_machine, {}),
]


# ===========================================================================
# Main
# ===========================================================================

if __name__ == "__main__":
    DATA_DIR = os.path.join(SCRIPT_DIR, "data")
    white_path = write_white_dds(DATA_DIR)
    print(f"[HubWorld] White texture : {white_path}")
    brick_path = write_brick_dds(DATA_DIR)
    print(f"[HubWorld] Brick texture : {brick_path}")
    write_herb_icons(DATA_DIR)

    print(f"[HubWorld] Writing {len(MESHES)} mesh(es) to: {OUT_DIR}")
    for entry in MESHES:
        filename, builder, kwargs = entry[:3]
        dae_opts = entry[3] if len(entry) > 3 else {}
        submeshes = builder(**kwargs)
        write_dae(out(filename), submeshes, **dae_opts)
        total_tris = sum(len(sm.triangles) for sm in submeshes)
        print(f"  -> {filename}  ({total_tris} tris, {len(submeshes)} part(s))")
    print("[HubWorld] Done.")
    print("Next: run build.py (or build_all.py) to generate hub_world.omwaddon.")
