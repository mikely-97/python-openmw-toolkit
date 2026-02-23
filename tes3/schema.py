"""tes3.schema — Binary schemas for TES3 subrecords.

Each entry in SUBRECORD_SCHEMAS maps (record_tag, subrecord_tag) → SubrecordSchema.
A SubrecordSchema is a namedtuple with:
  - fmt:    struct format string (always little-endian, prefix '<')
  - fields: list of field names matching the format

For variable-length string subrecords use StringSchema.
For fixed-length string subrecords use FixedStringSchema.

To add a new record type:
  1. Add (RECORD_TAG, SUBREC_TAG): SubrecordSchema(...) entries here.
  2. The reader/writer will automatically parse/serialise them.
  3. If the subrecord is a plain null-terminated string, use StringSchema.
  4. If it is a fixed-width binary blob with named fields, use SubrecordSchema.

Extendability note
------------------
3D meshes (NIF) and textures (DDS/TGA) live in the VFS as separate files and
are referenced by file-path strings inside subrecords (e.g. MODL, ITEX, ICON).
Add entries here for those subrecords to resolve the asset path; the actual
file parsing should live in a future `tes3mesh` / `tes3tex` subpackage.
"""

from __future__ import annotations
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Schema types
# ---------------------------------------------------------------------------

class SubrecordSchema(NamedTuple):
    """Struct-based schema for a fixed-layout binary subrecord."""
    fmt: str          # struct format string (little-endian, with '<')
    fields: list[str]


class StringSchema(NamedTuple):
    """Variable-length null-terminated (or padded) string subrecord."""
    encoding: str = "latin-1"


class FixedStringSchema(NamedTuple):
    """Fixed-width, null-padded string field (e.g. HEDR company/description)."""
    length: int
    encoding: str = "latin-1"


# ---------------------------------------------------------------------------
# Subrecord schemas
# Keyed by (RECORD_TAG_bytes, SUBREC_TAG_bytes).
# Tags are plain str here; reader/writer convert to bytes internally.
# ---------------------------------------------------------------------------

SUBRECORD_SCHEMAS: dict[tuple[str, str], SubrecordSchema | StringSchema | FixedStringSchema] = {}

_S = SUBRECORD_SCHEMAS  # shorthand

# ----- TES3 header ---------------------------------------------------------
# HEDR: 300 bytes — float version, uint file_type, 32-char company,
#                   256-char description, uint num_records
# We handle HEDR with a custom multi-part parser; mark it as a tuple schema.

class HedrSchema(NamedTuple):
    pass  # handled by reader/writer specially

_S["TES3", "HEDR"] = HedrSchema()
_S["TES3", "MAST"] = StringSchema()          # master filename
_S["TES3", "DATA"] = SubrecordSchema("<Q", ["master_size"])  # uint64 file size
_S["TES3", "CNAM"] = StringSchema()           # author/company name

# ----- GMST — Game Setting -------------------------------------------------
_S["GMST", "NAME"] = StringSchema()
_S["GMST", "STRV"] = StringSchema()                        # string value
_S["GMST", "INTV"] = SubrecordSchema("<i", ["value"])      # int value
_S["GMST", "FLTV"] = SubrecordSchema("<f", ["value"])      # float value

# ----- GLOB — Global Variable ----------------------------------------------
_S["GLOB", "NAME"] = StringSchema()
_S["GLOB", "FNAM"] = StringSchema()   # type: 's'=short, 'l'=long, 'f'=float
_S["GLOB", "FLTV"] = SubrecordSchema("<f", ["value"])

# ----- CLAS — Character Class ----------------------------------------------
_S["CLAS", "NAME"] = StringSchema()
_S["CLAS", "FNAM"] = StringSchema()
_S["CLAS", "CLDT"] = SubrecordSchema(
    "<iiIIIIIII",
    ["attribute1", "attribute2", "specialization",
     "minor_skill1", "major_skill1", "minor_skill2", "major_skill2",
     "minor_skill3", "major_skill3"]
)
_S["CLAS", "DESC"] = StringSchema()

# ----- FACT — Faction ------------------------------------------------------
_S["FACT", "NAME"] = StringSchema()
_S["FACT", "FNAM"] = StringSchema()
# FADT is a complex 240-byte struct; keep raw for now
_S["FACT", "ANAM"] = StringSchema()   # NPC rank name
_S["FACT", "INTV"] = SubrecordSchema("<I", ["unknown"])

# ----- RACE — Race ---------------------------------------------------------
_S["RACE", "NAME"] = StringSchema()
_S["RACE", "FNAM"] = StringSchema()
# RADT is a 140-byte struct with skill bonuses, stat adjustments, flags
_S["RACE", "DESC"] = StringSchema()

# ----- SOUN — Sound --------------------------------------------------------
_S["SOUN", "NAME"] = StringSchema()
_S["SOUN", "FNAM"] = StringSchema()
_S["SOUN", "DATA"] = SubrecordSchema("<BBB", ["volume", "min_range", "max_range"])

# ----- SKIL — Skill --------------------------------------------------------
_S["SKIL", "INDX"] = SubrecordSchema("<i", ["skill_id"])
_S["SKIL", "SKDT"] = SubrecordSchema("<iiii", ["attribute", "specialization", "use_type0", "use_type1"])
_S["SKIL", "DESC"] = StringSchema()

# ----- MGEF — Magic Effect -------------------------------------------------
_S["MGEF", "INDX"] = SubrecordSchema("<i", ["effect_id"])
_S["MGEF", "MEDT"] = SubrecordSchema(
    "<IffIIff",
    ["school", "base_cost", "flags", "red", "blue", "speed", "size"]
)
_S["MGEF", "ITEX"] = StringSchema()
_S["MGEF", "PTEX"] = StringSchema()
_S["MGEF", "BSND"] = StringSchema()
_S["MGEF", "CSND"] = StringSchema()
_S["MGEF", "HSND"] = StringSchema()
_S["MGEF", "ASND"] = StringSchema()
_S["MGEF", "CVFX"] = StringSchema()
_S["MGEF", "BVFX"] = StringSchema()
_S["MGEF", "HVFX"] = StringSchema()
_S["MGEF", "AVFX"] = StringSchema()
_S["MGEF", "DESC"] = StringSchema()

# ----- SCPT — Script -------------------------------------------------------
_S["SCPT", "SCHD"] = SubrecordSchema(
    "<32sIIII",
    ["name", "num_shorts", "num_longs", "num_floats", "script_data_size"]
)
_S["SCPT", "SCVR"] = StringSchema()  # variable names (null-separated)
_S["SCPT", "SCDT"] = None            # raw bytecode — stored as bytes
_S["SCPT", "SCTX"] = StringSchema()  # source text
_S["SCPT", "INTV"] = SubrecordSchema("<I", ["local_var_size"])

# ----- REGN — Region -------------------------------------------------------
_S["REGN", "NAME"] = StringSchema()
_S["REGN", "FNAM"] = StringSchema()
_S["REGN", "WEAT"] = None           # raw weather bytes
_S["REGN", "BNAM"] = StringSchema()
_S["REGN", "CNAM"] = SubrecordSchema("<BBBB", ["r", "g", "b", "a"])
_S["REGN", "SNAM"] = None           # sound chance records

# ----- BSGN — Birthsign ----------------------------------------------------
_S["BSGN", "NAME"] = StringSchema()
_S["BSGN", "FNAM"] = StringSchema()
_S["BSGN", "TNAM"] = StringSchema()
_S["BSGN", "DESC"] = StringSchema()
_S["BSGN", "NPCS"] = StringSchema()

# ----- LTEX — Land Texture -------------------------------------------------
_S["LTEX", "NAME"] = StringSchema()
_S["LTEX", "INTV"] = SubrecordSchema("<I", ["texture_index"])
_S["LTEX", "DATA"] = StringSchema()  # texture filename

# ----- STAT — Static Object ------------------------------------------------
_S["STAT", "NAME"] = StringSchema()
_S["STAT", "MODL"] = StringSchema()  # mesh path in VFS (NIF file)

# ----- DOOR — Door ---------------------------------------------------------
_S["DOOR", "NAME"] = StringSchema()
_S["DOOR", "MODL"] = StringSchema()
_S["DOOR", "FNAM"] = StringSchema()
_S["DOOR", "SCRI"] = StringSchema()
_S["DOOR", "SNAM"] = StringSchema()
_S["DOOR", "ANAM"] = StringSchema()

# ----- MISC — Misc. Item ---------------------------------------------------
_S["MISC", "NAME"] = StringSchema()
_S["MISC", "MODL"] = StringSchema()
_S["MISC", "FNAM"] = StringSchema()
_S["MISC", "MCDT"] = SubrecordSchema("<fIH", ["weight", "value", "unknown"])
_S["MISC", "SCRI"] = StringSchema()
_S["MISC", "ITEX"] = StringSchema()  # icon texture path

# ----- WEAP — Weapon -------------------------------------------------------
_S["WEAP", "NAME"] = StringSchema()
_S["WEAP", "MODL"] = StringSchema()
_S["WEAP", "FNAM"] = StringSchema()
_S["WEAP", "WPDT"] = SubrecordSchema(
    "<fIHHHHHbbbh",
    ["weight", "value", "type", "health", "speed_x100", "reach_x100",
     "enchant_pts", "chop_min", "chop_max", "slash_min", "slash_max"]
)
_S["WEAP", "ITEX"] = StringSchema()
_S["WEAP", "ENAM"] = StringSchema()
_S["WEAP", "SCRI"] = StringSchema()

# ----- CONT — Container ----------------------------------------------------
_S["CONT", "NAME"] = StringSchema()
_S["CONT", "MODL"] = StringSchema()
_S["CONT", "FNAM"] = StringSchema()
_S["CONT", "CNDT"] = SubrecordSchema("<f", ["capacity"])
_S["CONT", "FLAG"] = SubrecordSchema("<I", ["flags"])
_S["CONT", "SCRI"] = StringSchema()
_S["CONT", "NPCO"] = SubrecordSchema("<i32s", ["count", "item_id"])

# ----- SPEL — Spell --------------------------------------------------------
_S["SPEL", "NAME"] = StringSchema()
_S["SPEL", "FNAM"] = StringSchema()
_S["SPEL", "SPDT"] = SubrecordSchema("<iii", ["type", "cost", "flags"])
_S["SPEL", "ENAM"] = SubrecordSchema(
    "<HHBBBBHHf",
    ["effect_id", "skill", "attribute", "range", "area", "duration",
     "magnitude_min", "magnitude_max", "unknown"]
)

# ----- CREA — Creature -----------------------------------------------------
_S["CREA", "NAME"] = StringSchema()
_S["CREA", "MODL"] = StringSchema()
_S["CREA", "CNAM"] = StringSchema()
_S["CREA", "FNAM"] = StringSchema()
_S["CREA", "SCRI"] = StringSchema()
_S["CREA", "NPCS"] = StringSchema()
# NPDT for creatures is 96 bytes
_S["CREA", "AIDT"] = SubrecordSchema("<BBBBI", ["hello", "unknown", "fight", "flee", "services"])
_S["CREA", "NPCO"] = SubrecordSchema("<i32s", ["count", "item_id"])
_S["CREA", "DODT"] = SubrecordSchema("<ffffff", ["x", "y", "z", "rot_x", "rot_y", "rot_z"])
_S["CREA", "DNAM"] = StringSchema()  # destination cell name

# ----- BODY — Body Part ----------------------------------------------------
_S["BODY", "NAME"] = StringSchema()
_S["BODY", "MODL"] = StringSchema()
_S["BODY", "FNAM"] = StringSchema()
_S["BODY", "BYDT"] = SubrecordSchema("<BBBB", ["part", "vampire", "flags", "part_type"])

# ----- LIGH — Light --------------------------------------------------------
_S["LIGH", "NAME"] = StringSchema()
_S["LIGH", "MODL"] = StringSchema()
_S["LIGH", "FNAM"] = StringSchema()
_S["LIGH", "ITEX"] = StringSchema()
_S["LIGH", "LHDT"] = SubrecordSchema("<fIiiBBBB", ["weight", "value", "time", "radius", "r", "g", "b", "flags"])
_S["LIGH", "SCRI"] = StringSchema()
_S["LIGH", "SNAM"] = StringSchema()

# ----- ENCH — Enchantment --------------------------------------------------
_S["ENCH", "NAME"] = StringSchema()
_S["ENCH", "ENDT"] = SubrecordSchema("<iiii", ["type", "cost", "charge", "flags"])
_S["ENCH", "ENAM"] = SubrecordSchema(
    "<HHBBBBHHf",
    ["effect_id", "skill", "attribute", "range", "area", "duration",
     "magnitude_min", "magnitude_max", "unknown"]
)

# ----- NPC_ — NPC ----------------------------------------------------------
_S["NPC_", "NAME"] = StringSchema()
_S["NPC_", "MODL"] = StringSchema()
_S["NPC_", "FNAM"] = StringSchema()   # display name
_S["NPC_", "RNAM"] = StringSchema()   # race
_S["NPC_", "CNAM"] = StringSchema()   # class
_S["NPC_", "ANAM"] = StringSchema()   # faction
_S["NPC_", "BNAM"] = StringSchema()   # head mesh
_S["NPC_", "KNAM"] = StringSchema()   # hair mesh
_S["NPC_", "SCRI"] = StringSchema()   # attached script
_S["NPC_", "NPDT"] = None             # variable-size; 52 or 12 bytes
_S["NPC_", "FLAG"] = SubrecordSchema("<I", ["flags"])
_S["NPC_", "NPCO"] = SubrecordSchema("<i32s", ["count", "item_id"])
_S["NPC_", "NPCS"] = StringSchema()   # spell ID (32 bytes, null-padded)
_S["NPC_", "AIDT"] = SubrecordSchema("<BBBBI", ["hello", "unknown", "fight", "flee", "services"])
_S["NPC_", "DODT"] = SubrecordSchema("<ffffff", ["x", "y", "z", "rot_x", "rot_y", "rot_z"])
_S["NPC_", "DNAM"] = StringSchema()   # destination cell name
_S["NPC_", "XSCL"] = SubrecordSchema("<f", ["scale"])
_S["NPC_", "TNAM"] = StringSchema()

# ----- ARMO — Armour -------------------------------------------------------
_S["ARMO", "NAME"] = StringSchema()
_S["ARMO", "MODL"] = StringSchema()
_S["ARMO", "FNAM"] = StringSchema()
_S["ARMO", "SCRI"] = StringSchema()
_S["ARMO", "AODT"] = SubrecordSchema(
    "<IffIIH",
    ["type", "weight", "value", "health", "enchant_pts", "armor_rating"]
)
_S["ARMO", "ITEX"] = StringSchema()
_S["ARMO", "INDX"] = SubrecordSchema("<B", ["body_part_index"])
_S["ARMO", "BNAM"] = StringSchema()
_S["ARMO", "CNAM"] = StringSchema()
_S["ARMO", "ENAM"] = StringSchema()

# ----- CLOT — Clothing -----------------------------------------------------
_S["CLOT", "NAME"] = StringSchema()
_S["CLOT", "MODL"] = StringSchema()
_S["CLOT", "FNAM"] = StringSchema()
_S["CLOT", "SCRI"] = StringSchema()
_S["CLOT", "CTDT"] = SubrecordSchema("<IfIH", ["type", "weight", "value", "enchant_pts"])
_S["CLOT", "ITEX"] = StringSchema()
_S["CLOT", "INDX"] = SubrecordSchema("<B", ["body_part_index"])
_S["CLOT", "BNAM"] = StringSchema()
_S["CLOT", "CNAM"] = StringSchema()
_S["CLOT", "ENAM"] = StringSchema()

# ----- REPA — Repair Item --------------------------------------------------
_S["REPA", "NAME"] = StringSchema()
_S["REPA", "MODL"] = StringSchema()
_S["REPA", "FNAM"] = StringSchema()
_S["REPA", "RIDT"] = SubrecordSchema("<fIHH", ["weight", "value", "uses", "quality_x100"])
_S["REPA", "ITEX"] = StringSchema()
_S["REPA", "SCRI"] = StringSchema()

# ----- ACTI — Activator ----------------------------------------------------
_S["ACTI", "NAME"] = StringSchema()
_S["ACTI", "MODL"] = StringSchema()
_S["ACTI", "FNAM"] = StringSchema()
_S["ACTI", "SCRI"] = StringSchema()

# ----- APPA — Apparatus ----------------------------------------------------
_S["APPA", "NAME"] = StringSchema()
_S["APPA", "MODL"] = StringSchema()
_S["APPA", "FNAM"] = StringSchema()
_S["APPA", "AADT"] = SubrecordSchema("<IfIf", ["type", "quality", "value", "weight"])
_S["APPA", "ITEX"] = StringSchema()
_S["APPA", "SCRI"] = StringSchema()

# ----- LOCK — Lockpick -----------------------------------------------------
_S["LOCK", "NAME"] = StringSchema()
_S["LOCK", "MODL"] = StringSchema()
_S["LOCK", "FNAM"] = StringSchema()
_S["LOCK", "LKDT"] = SubrecordSchema("<fIfI", ["weight", "value", "quality", "uses"])
_S["LOCK", "ITEX"] = StringSchema()
_S["LOCK", "SCRI"] = StringSchema()

# ----- PROB — Probe --------------------------------------------------------
_S["PROB", "NAME"] = StringSchema()
_S["PROB", "MODL"] = StringSchema()
_S["PROB", "FNAM"] = StringSchema()
_S["PROB", "PBDT"] = SubrecordSchema("<fIfI", ["weight", "value", "quality", "uses"])
_S["PROB", "ITEX"] = StringSchema()
_S["PROB", "SCRI"] = StringSchema()

# ----- INGR — Ingredient ---------------------------------------------------
_S["INGR", "NAME"] = StringSchema()
_S["INGR", "MODL"] = StringSchema()
_S["INGR", "FNAM"] = StringSchema()
_S["INGR", "IRDT"] = SubrecordSchema(
    "<fIiiiiBBBB",
    ["weight", "value",
     "effect1", "effect2", "effect3", "effect4",
     "skill1", "skill2", "skill3", "skill4"]
)
_S["INGR", "ITEX"] = StringSchema()
_S["INGR", "SCRI"] = StringSchema()

# ----- BOOK — Book / Scroll ------------------------------------------------
_S["BOOK", "NAME"] = StringSchema()
_S["BOOK", "MODL"] = StringSchema()
_S["BOOK", "FNAM"] = StringSchema()
_S["BOOK", "BKDT"] = SubrecordSchema("<fIiIf", ["weight", "value", "scroll", "skill_id", "enchant_pts"])
_S["BOOK", "SCRI"] = StringSchema()
_S["BOOK", "ITEX"] = StringSchema()
_S["BOOK", "ENAM"] = StringSchema()
_S["BOOK", "TEXT"] = StringSchema()   # book body text (HTML-ish)

# ----- ALCH — Potion -------------------------------------------------------
_S["ALCH", "NAME"] = StringSchema()
_S["ALCH", "MODL"] = StringSchema()
_S["ALCH", "FNAM"] = StringSchema()
_S["ALCH", "ALDT"] = SubrecordSchema("<fIf", ["weight", "value", "auto_calc"])
_S["ALCH", "SCRI"] = StringSchema()
_S["ALCH", "ITEX"] = StringSchema()
_S["ALCH", "ENAM"] = SubrecordSchema(
    "<HHBBBBHHf",
    ["effect_id", "skill", "attribute", "range", "area", "duration",
     "magnitude_min", "magnitude_max", "unknown"]
)

# ----- LEVI — Levelled Item List -------------------------------------------
_S["LEVI", "NAME"] = StringSchema()
_S["LEVI", "DATA"] = SubrecordSchema("<I", ["flags"])
_S["LEVI", "NNAM"] = SubrecordSchema("<B", ["chance_none"])
_S["LEVI", "INDX"] = SubrecordSchema("<I", ["count"])
_S["LEVI", "INAM"] = StringSchema()   # item ID
_S["LEVI", "INTV"] = SubrecordSchema("<H", ["pc_level"])

# ----- LEVC — Levelled Creature List ---------------------------------------
_S["LEVC", "NAME"] = StringSchema()
_S["LEVC", "DATA"] = SubrecordSchema("<I", ["flags"])
_S["LEVC", "NNAM"] = SubrecordSchema("<B", ["chance_none"])
_S["LEVC", "INDX"] = SubrecordSchema("<I", ["count"])
_S["LEVC", "CNAM"] = StringSchema()   # creature ID
_S["LEVC", "INTV"] = SubrecordSchema("<H", ["pc_level"])

# ----- CELL — Cell (interior or exterior) ----------------------------------
# NOTE: CELL/DATA is context-sensitive and handled in reader.py by raw byte size:
#   12 bytes → cell header: flags(I), grid_x(i), grid_y(i)
#   24 bytes → object reference: x(f), y(f), z(f), rot_x(f), rot_y(f), rot_z(f)
# The schema entry below is the fallback for any other size.
_S["CELL", "NAME"] = StringSchema()   # cell name (empty = exterior)
_S["CELL", "DATA"] = SubrecordSchema("<Iii", ["flags", "grid_x", "grid_y"])
_S["CELL", "RGNN"] = StringSchema()   # region name
_S["CELL", "NAM0"] = SubrecordSchema("<I", ["num_objects"])
_S["CELL", "WHGT"] = SubrecordSchema("<f", ["water_height"])
_S["CELL", "AMBI"] = SubrecordSchema(
    "<IIII",
    ["ambient_color", "sunlight_color", "fog_color", "fog_density"]
)
# Per-object reference subrecords
_S["CELL", "FRMR"] = SubrecordSchema("<I", ["ref_num"])
_S["CELL", "UNAM"] = SubrecordSchema("<B", ["blocked"])
_S["CELL", "XSCL"] = SubrecordSchema("<f", ["scale"])
_S["CELL", "XSOL"] = StringSchema()   # soul
_S["CELL", "XCHG"] = SubrecordSchema("<f", ["charge_enchant"])
_S["CELL", "XHLT"] = SubrecordSchema("<i", ["health_left"])
_S["CELL", "XPCI"] = SubrecordSchema("<I", ["unknown"])
_S["CELL", "LNAM"] = SubrecordSchema("<I", ["unknown"])
_S["CELL", "FLTV"] = SubrecordSchema("<I", ["lock_level"])
_S["CELL", "KNAM"] = StringSchema()   # key
_S["CELL", "TNAM"] = StringSchema()   # trap
_S["CELL", "CNAM"] = StringSchema()   # owner
_S["CELL", "INDX"] = SubrecordSchema("<I", ["unknown"])
_S["CELL", "ZNAM"] = SubrecordSchema("<B", ["blocked_door"])
_S["CELL", "NAM9"] = SubrecordSchema("<I", ["ref_count"])
_S["CELL", "DODT"] = SubrecordSchema("<ffffff", ["x", "y", "z", "rot_x", "rot_y", "rot_z"])
_S["CELL", "DNAM"] = StringSchema()
_S["CELL", "INTV"] = SubrecordSchema("<i", ["map_color"])
_S["CELL", "NAM5"] = SubrecordSchema("<i", ["map_color"])
_S["CELL", "DELE"] = SubrecordSchema("<I", ["flags"])

# ----- LAND — Landscape ----------------------------------------------------
_S["LAND", "INTV"] = SubrecordSchema("<ii", ["grid_x", "grid_y"])
_S["LAND", "DATA"] = SubrecordSchema("<i", ["flags"])
# VNML, VHGT, VCLR, VTEX are large raw blobs; keep as bytes

# ----- PGRD — Pathgrid -----------------------------------------------------
_S["PGRD", "DATA"] = SubrecordSchema("<iiHH", ["grid_x", "grid_y", "granularity", "num_points"])
_S["PGRD", "NAME"] = StringSchema()

# ----- SNDG — Sound Generator ----------------------------------------------
_S["SNDG", "NAME"] = StringSchema()
_S["SNDG", "DATA"] = SubrecordSchema("<I", ["type"])
_S["SNDG", "SNAM"] = StringSchema()
_S["SNDG", "CNAM"] = StringSchema()

# ----- DIAL — Dialogue Topic -----------------------------------------------
_S["DIAL", "NAME"] = StringSchema()
_S["DIAL", "DATA"] = SubrecordSchema("<B", ["type"])

# ----- INFO — Dialogue Response --------------------------------------------
_S["INFO", "INAM"] = StringSchema()   # this info ID
_S["INFO", "PNAM"] = StringSchema()   # previous info ID (linked list)
_S["INFO", "NNAM"] = StringSchema()   # next info ID
_S["INFO", "DATA"] = SubrecordSchema(
    "<BBBI",
    ["type", "disposition", "rank", "gender_race_class_flags"]
)
_S["INFO", "ONAM"] = StringSchema()   # actor ID
_S["INFO", "RNAM"] = StringSchema()   # race ID
_S["INFO", "CNAM"] = StringSchema()   # class ID
_S["INFO", "FNAM"] = StringSchema()   # faction ID
_S["INFO", "ANAM"] = StringSchema()   # cell name
_S["INFO", "DNAM"] = StringSchema()   # PC faction ID
_S["INFO", "SNAM"] = StringSchema()   # sound file
_S["INFO", "NAME"] = StringSchema()   # response text
_S["INFO", "SCVR"] = StringSchema()   # condition
_S["INFO", "INTV"] = SubrecordSchema("<i", ["value"])
_S["INFO", "FLTV"] = SubrecordSchema("<f", ["value"])
_S["INFO", "BNAM"] = StringSchema()   # result script
_S["INFO", "QSTN"] = SubrecordSchema("<B", ["quest_name"])
_S["INFO", "QSTF"] = SubrecordSchema("<B", ["quest_finish"])
_S["INFO", "QSTR"] = SubrecordSchema("<B", ["quest_restart"])

# ---------------------------------------------------------------------------
# Convenience lookup helpers
# ---------------------------------------------------------------------------

def get_schema(record_tag: str, subrec_tag: str):
    """Return the schema for (record_tag, subrec_tag), or None if unknown."""
    return _S.get((record_tag, subrec_tag))


# Asset-path subrecord tags (mesh/texture references).
# These contain VFS paths to 3D or image files and are the extension points
# for future tes3mesh / tes3tex modules.
ASSET_PATH_SUBRECORDS: dict[str, str] = {
    "MODL": "mesh",   # .nif 3D mesh path
    "ITEX": "texture",  # icon texture path
    "PTEX": "texture",  # particle texture
    "ICON": "texture",  # alternate icon tag used in some records
    "TNAM": "texture",  # terrain texture
}

# Record tags that represent placeable objects (have MODL + placement refs)
PLACEABLE_RECORD_TAGS = frozenset([
    "STAT", "DOOR", "MISC", "WEAP", "CONT", "CREA", "BODY",
    "LIGH", "NPC_", "ARMO", "CLOT", "REPA", "ACTI", "APPA",
    "LOCK", "PROB", "INGR", "BOOK", "ALCH",
])
