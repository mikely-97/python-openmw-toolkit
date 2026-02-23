"""addon.builder — AddonBuilder: high-level API for creating TES3 addons.

All methods return `self` or a sub-builder so they can be chained.
The internal representation is a list of record dicts compatible with
tes3.reader / tes3.writer.

Extendability
-------------
New record types can be added by:
  1. Creating a helper method add_<type>() here.
  2. Optionally creating a subbuilder in addon/types/<type>.py.
  3. Adding subrecord schemas in tes3/schema.py.

For 3D assets (meshes/textures), the MODL/ITEX subrecords in the records
produced here already carry VFS-relative file paths.  A future tes3mesh or
tes3tex module can read/write those files independently.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import TYPE_CHECKING

from tes3.writer import write_file

if TYPE_CHECKING:
    from addon.types.cell import CellBuilder


# ---- helpers ---------------------------------------------------------------

def _str_sr(tag: str, value: str, encoding: str = "latin-1") -> dict:
    """Create a string subrecord."""
    raw = value.encode(encoding) + b"\x00"
    return {"tag": tag, "raw": raw, "parsed": value}


def _struct_sr(tag: str, fmt: str, fields: list[str], values: dict) -> dict:
    """Create a struct subrecord."""
    vals = [values.get(f, 0) for f in fields]
    # Encode bytes-typed values
    packed_vals = []
    import re
    fmt_parts = re.findall(r"\d*[xcbBhHiIlLqQfdspP]", fmt.lstrip("<>!=@"))
    for part, v in zip(fmt_parts, vals):
        if "s" in part and isinstance(v, str):
            width = int(part.replace("s", "")) if part != "s" else 1
            v = v.encode("latin-1").ljust(width, b"\x00")[:width]
        packed_vals.append(v)
    raw = struct.pack(fmt, *packed_vals)
    return {"tag": tag, "raw": raw, "parsed": values}


def _raw_sr(tag: str, data: bytes) -> dict:
    """Create a raw (opaque) subrecord."""
    return {"tag": tag, "raw": data}


# ---- TES3 header -----------------------------------------------------------

def _make_tes3_header(
    description: str = "",
    company: str = "",
    masters: list[tuple[str, int]] | None = None,
    file_type: int = 0,
) -> dict:
    """Build the TES3 header record."""
    # HEDR: 300 bytes
    buf = bytearray(300)
    struct.pack_into("<fI", buf, 0, 1.3, file_type)
    c_bytes = company.encode("latin-1")[:32]
    buf[8:8 + len(c_bytes)] = c_bytes
    d_bytes = description.encode("latin-1")[:256]
    buf[40:40 + len(d_bytes)] = d_bytes
    # num_records patched at write time
    struct.pack_into("<I", buf, 296, 0)
    hedr_sr = {"tag": "HEDR", "raw": bytes(buf), "parsed": {
        "version": 1.3,
        "file_type": file_type,
        "company": company,
        "description": description,
        "num_records": 0,
    }}

    subrecords = [hedr_sr]
    for master_name, master_size in (masters or []):
        subrecords.append(_str_sr("MAST", master_name))
        data_raw = struct.pack("<Q", master_size)
        subrecords.append({"tag": "DATA", "raw": data_raw, "parsed": {"master_size": master_size}})

    return {"tag": "TES3", "flags": 0, "hdr1": 0, "subrecords": subrecords}


# ---- AddonBuilder ----------------------------------------------------------

class AddonBuilder:
    """High-level builder for .omwaddon / .omwgame files.

    Parameters
    ----------
    description:
        Human-readable description embedded in the file header.
    company:
        Author/company name (up to 32 chars).
    masters:
        List of (master_filename, master_filesize) tuples.
        If you don't know the file size, pass 0 — OpenMW only warns.
    file_type:
        0 = plugin (.omwaddon/.esp), 1 = master (.omwgame/.esm), 32 = save.
    """

    def __init__(
        self,
        description: str = "",
        company: str = "",
        masters: list[str | tuple[str, int]] | None = None,
        file_type: int = 0,
    ) -> None:
        # Normalise masters to (name, size) tuples
        master_pairs: list[tuple[str, int]] = []
        for m in (masters or []):
            if isinstance(m, str):
                master_pairs.append((m, 0))
            else:
                master_pairs.append(tuple(m))  # type: ignore[arg-type]

        self._records: list[dict] = [
            _make_tes3_header(description, company, master_pairs, file_type)
        ]

    # ---- raw access --------------------------------------------------------

    @property
    def records(self) -> list[dict]:
        """Direct access to the underlying list of record dicts."""
        return self._records

    # ---- serialization -----------------------------------------------------

    def save(self, path: str | Path) -> None:
        """Write the addon to a binary file."""
        write_file(self._records, path)

    def to_bytes(self) -> bytes:
        """Return the addon as bytes."""
        from tes3.writer import write_bytes
        return write_bytes(self._records)

    # ---- low-level append --------------------------------------------------

    def _append(self, record: dict) -> None:
        self._records.append(record)

    # ---- GLOB — Global Variable --------------------------------------------

    def add_global(
        self,
        id: str,
        type: str = "short",
        value: float = 0.0,
    ) -> "AddonBuilder":
        """Add a GLOB (global variable) record.

        Parameters
        ----------
        id:   Unique ID (case-insensitive in engine; use lowercase).
        type: 's'=short, 'l'=long, 'f'=float  (or full names).
        value: Initial value.
        """
        type_char = {"short": "s", "long": "l", "float": "f"}.get(type, type)
        self._append({
            "tag": "GLOB",
            "flags": 0,
            "hdr1": 0,
            "subrecords": [
                _str_sr("NAME", id),
                _str_sr("FNAM", type_char),
                _raw_sr("FLTV", struct.pack("<f", float(value))),
            ],
        })
        return self

    # ---- NPC_ --------------------------------------------------------------

    def add_npc(
        self,
        id: str,
        name: str = "",
        race: str = "",
        npc_class: str = "",
        faction: str = "",
        head: str = "",
        hair: str = "",
        script: str = "",
        disposition: int = 50,
        level: int = 1,
        gold: int = 0,
        flags: list[str] | None = None,
        services: int = 0,
        inventory: list[tuple[str, int]] | None = None,
        spells: list[str] | None = None,
        mesh: str = "",
    ) -> "AddonBuilder":
        """Add an NPC_ record.

        flags: list of flag names — 'female', 'essential', 'respawn',
               'autocalc', 'skeleton_blood', 'metal_blood'.
        inventory: list of (item_id, count) tuples.
        spells: list of spell IDs.
        mesh: VFS path to body mesh (.nif).  Usually left blank to use the
              race/gender default resolved by OpenMW.
        """
        flag_map = {
            "female": 0x0001, "essential": 0x0002, "respawn": 0x0004,
            "autocalc": 0x0008, "skeleton_blood": 0x0400, "metal_blood": 0x0800,
        }
        flag_val = 0
        for f in (flags or []):
            flag_val |= flag_map.get(f, 0)

        autocalc = bool(flag_val & 0x0008)
        subrecords = [_str_sr("NAME", id)]
        if mesh:
            subrecords.append(_str_sr("MODL", mesh))
        subrecords.append(_str_sr("FNAM", name))
        subrecords.append(_str_sr("RNAM", race))
        subrecords.append(_str_sr("CNAM", npc_class))
        subrecords.append(_str_sr("ANAM", faction))
        if head:
            subrecords.append(_str_sr("BNAM", head))
        if hair:
            subrecords.append(_str_sr("KNAM", hair))
        if script:
            subrecords.append(_str_sr("SCRI", script))

        if autocalc:
            # 12-byte short NPDT: level(H), disposition(B), faction_rank(B),
            # unknown(6B), gold(I) -- simplified autocalc form
            npdt = struct.pack("<HBB6sI", level, disposition, 0, b"\x00" * 6, gold)
        else:
            # 52-byte full NPDT
            npdt = struct.pack(
                "<HBBBBBBBBB27sBBhhHHBBhH",
                level,
                50, 50, 50, 50, 50, 50, 50, 50,  # attributes (strength..luck)
                b"\x00" * 27,   # skills
                disposition,
                0,              # faction id
                0,              # rank
                gold,           # health
                gold,           # max magicka
                gold,           # fatigue
                0, 0,           # disposition/faction_id duplicates
                gold,           # gold
                0,              # unknown
            )
        subrecords.append(_raw_sr("NPDT", npdt))
        subrecords.append(_struct_sr("FLAG", "<I", ["flags"], {"flags": flag_val}))
        subrecords.append(_struct_sr("AIDT", "<BBBBI", ["hello", "unknown", "fight", "flee", "services"],
                                     {"hello": 30, "unknown": 0, "fight": 30, "flee": 30, "services": services}))

        for item_id, count in (inventory or []):
            item_id_raw = item_id.encode("latin-1").ljust(32, b"\x00")[:32]
            subrecords.append(_raw_sr("NPCO", struct.pack("<i32s", count, item_id_raw)))

        for spell_id in (spells or []):
            subrecords.append(_str_sr("NPCS", spell_id))

        self._append({"tag": "NPC_", "flags": 0, "hdr1": 0, "subrecords": subrecords})
        return self

    # ---- CELL --------------------------------------------------------------

    def add_interior_cell(
        self,
        name: str,
        flags: list[str] | None = None,
        water_height: float = 0.0,
        ambient: int = 0x404040FF,
        sunlight: int = 0x000000FF,
        fog_color: int = 0x000000FF,
        fog_density: float = 0.5,
        region: str = "",
    ) -> "CellBuilder":
        """Add an interior CELL and return a CellBuilder for placing objects."""
        from addon.types.cell import CellBuilder

        flag_map = {"water": 0x02, "illegal_to_sleep": 0x04, "behave_like_exterior": 0x80}
        cell_flags = 0x01  # interior
        for f in (flags or []):
            cell_flags |= flag_map.get(f, 0)

        subrecords: list[dict] = [
            _str_sr("NAME", name),
            _raw_sr("DATA", struct.pack("<Iii", cell_flags, 0, 0)),
            _raw_sr("AMBI", struct.pack("<IIII",
                                        ambient, sunlight, fog_color,
                                        int(fog_density * 1000))),
        ]
        if water_height != 0.0:
            subrecords.append(_raw_sr("WHGT", struct.pack("<f", water_height)))
        if region:
            subrecords.append(_str_sr("RGNN", region))

        cell_record: dict = {"tag": "CELL", "flags": 0, "hdr1": 0, "subrecords": subrecords}
        self._append(cell_record)
        return CellBuilder(cell_record)

    def add_exterior_cell(
        self,
        grid_x: int,
        grid_y: int,
        region: str = "",
    ) -> "CellBuilder":
        """Add an exterior CELL."""
        from addon.types.cell import CellBuilder

        subrecords: list[dict] = [
            _str_sr("NAME", ""),  # exterior cells have empty name
            _raw_sr("DATA", struct.pack("<Iii", 0, grid_x, grid_y)),
        ]
        if region:
            subrecords.append(_str_sr("RGNN", region))

        cell_record: dict = {"tag": "CELL", "flags": 0, "hdr1": 0, "subrecords": subrecords}
        self._append(cell_record)
        return CellBuilder(cell_record)

    # ---- SPEL — Spell ------------------------------------------------------

    def add_spell(
        self,
        id: str,
        name: str = "",
        spell_type: int = 0,
        cost: int = 0,
        auto_calc: bool = False,
        always_succeeds: bool = False,
        effects: list[dict] | None = None,
    ) -> "AddonBuilder":
        """Add a SPEL record.

        spell_type: 0=spell, 1=ability, 2=blight, 3=disease, 4=curse, 5=power.
        effects: list of dicts with keys:
          effect_id, skill, attribute, range, area, duration,
          magnitude_min, magnitude_max.
        """
        flags = 0
        if auto_calc:
            flags |= 0x01
        if always_succeeds:
            flags |= 0x04

        subrecords = [
            _str_sr("NAME", id),
            _str_sr("FNAM", name),
            _raw_sr("SPDT", struct.pack("<iii", spell_type, cost, flags)),
        ]
        for eff in (effects or []):
            subrecords.append(_raw_sr("ENAM", struct.pack(
                "<HHBBBBHHf",
                eff.get("effect_id", 0),
                eff.get("skill", 255),
                eff.get("attribute", 255),
                eff.get("range", 0),
                eff.get("area", 0),
                eff.get("duration", 1),
                eff.get("magnitude_min", 1),
                eff.get("magnitude_max", 1),
                0.0,  # unknown
            )))

        self._append({"tag": "SPEL", "flags": 0, "hdr1": 0, "subrecords": subrecords})
        return self

    # ---- SCPT — MWScript ---------------------------------------------------

    def add_script(
        self,
        id: str,
        source: str,
        num_shorts: int = 0,
        num_longs: int = 0,
        num_floats: int = 0,
        variables: list[str] | None = None,
    ) -> "AddonBuilder":
        """Add a SCPT record with MWScript source text.

        OpenMW will compile the source (SCTX) on load if no bytecode (SCDT)
        is present.
        """
        name_bytes = id.encode("latin-1").ljust(32, b"\x00")[:32]
        schd_data = struct.pack(
            "<32sIIII",
            name_bytes, num_shorts, num_longs, num_floats, 0
        )

        subrecords = [_raw_sr("SCHD", schd_data)]
        if variables:
            var_str = "\x00".join(variables) + "\x00"
            subrecords.append(_raw_sr("SCVR", var_str.encode("latin-1")))
        subrecords.append(_str_sr("SCTX", source))

        self._append({"tag": "SCPT", "flags": 0, "hdr1": 0, "subrecords": subrecords})
        return self

    # ---- BOOK --------------------------------------------------------------

    def add_book(
        self,
        id: str,
        name: str = "",
        mesh: str = "",
        icon: str = "",
        text: str = "",
        weight: float = 1.0,
        value: int = 10,
        scroll: bool = False,
        skill_id: int = -1,
        enchant_pts: float = 0.0,
        script: str = "",
        enchantment: str = "",
    ) -> "AddonBuilder":
        """Add a BOOK record."""
        subrecords = [
            _str_sr("NAME", id),
            _str_sr("MODL", mesh),
            _str_sr("FNAM", name),
            _raw_sr("BKDT", struct.pack("<fIiif",
                                        weight, int(value), int(scroll),
                                        int(skill_id), float(enchant_pts))),
        ]
        if script:
            subrecords.append(_str_sr("SCRI", script))
        if icon:
            subrecords.append(_str_sr("ITEX", icon))
        if enchantment:
            subrecords.append(_str_sr("ENAM", enchantment))
        if text:
            subrecords.append(_str_sr("TEXT", text))
        self._append({"tag": "BOOK", "flags": 0, "hdr1": 0, "subrecords": subrecords})
        return self

    # ---- STAT — Static Object ----------------------------------------------

    def add_static(
        self,
        id: str,
        mesh: str,
    ) -> "AddonBuilder":
        """Add a STAT record (a non-interactive static mesh).

        mesh: VFS-relative path to the .nif file, e.g. 'meshes/x/myobj.nif'.
        """
        self._append({
            "tag": "STAT",
            "flags": 0,
            "hdr1": 0,
            "subrecords": [
                _str_sr("NAME", id),
                _str_sr("MODL", mesh),
            ],
        })
        return self

    # ---- LIGH — Light ------------------------------------------------------

    def add_light(
        self,
        id: str,
        name: str = "",
        mesh: str = "",
        icon: str = "",
        radius: int = 128,
        color: tuple[int, int, int] = (255, 255, 255),
        duration: int = -1,
        weight: float = 1.0,
        value: int = 10,
        flags: list[str] | None = None,
        script: str = "",
        sound: str = "",
    ) -> "AddonBuilder":
        """Add a LIGH record."""
        flag_map = {
            "dynamic": 0x001, "can_carry": 0x002, "negative": 0x004,
            "flicker": 0x008, "fire": 0x010, "off_by_default": 0x020,
            "flicker_slow": 0x040, "pulse": 0x080, "pulse_slow": 0x100,
        }
        flag_val = 0
        for f in (flags or []):
            flag_val |= flag_map.get(f, 0)

        r, g, b = color
        subrecords = [
            _str_sr("NAME", id),
            _str_sr("MODL", mesh) if mesh else _str_sr("MODL", ""),
            _str_sr("FNAM", name),
            _raw_sr("LHDT", struct.pack("<fIiiBBBB",
                                        weight, value, duration, radius,
                                        r, g, b, flag_val)),
        ]
        if icon:
            subrecords.append(_str_sr("ITEX", icon))
        if script:
            subrecords.append(_str_sr("SCRI", script))
        if sound:
            subrecords.append(_str_sr("SNAM", sound))
        self._append({"tag": "LIGH", "flags": 0, "hdr1": 0, "subrecords": subrecords})
        return self

    # ---- CONT — Container --------------------------------------------------

    def add_container(
        self,
        id: str,
        name: str = "",
        mesh: str = "",
        capacity: float = 100.0,
        flags: list[str] | None = None,
        inventory: list[tuple[str, int]] | None = None,
        script: str = "",
    ) -> "AddonBuilder":
        """Add a CONT record."""
        flag_map = {"organic": 0x01, "respawn": 0x02, "default_anim": 0x08}
        flag_val = 0x08  # bit 3 must always be set (required by OpenMW loader)
        for f in (flags or []):
            flag_val |= flag_map.get(f, 0)

        subrecords = [
            _str_sr("NAME", id),
            _str_sr("MODL", mesh),
            _str_sr("FNAM", name),
            _raw_sr("CNDT", struct.pack("<f", capacity)),
            _raw_sr("FLAG", struct.pack("<I", flag_val)),
        ]
        if script:
            subrecords.append(_str_sr("SCRI", script))
        for item_id, count in (inventory or []):
            item_id_raw = item_id.encode("latin-1").ljust(32, b"\x00")[:32]
            subrecords.append(_raw_sr("NPCO", struct.pack("<i32s", count, item_id_raw)))
        self._append({"tag": "CONT", "flags": 0, "hdr1": 0, "subrecords": subrecords})
        return self

    # ---- MISC — Miscellaneous Item -----------------------------------------

    def add_misc_item(
        self,
        id: str,
        name: str = "",
        mesh: str = "",
        icon: str = "",
        weight: float = 1.0,
        value: int = 1,
        script: str = "",
    ) -> "AddonBuilder":
        """Add a MISC record (miscellaneous item)."""
        subrecords = [
            _str_sr("NAME", id),
            _str_sr("MODL", mesh),
            _str_sr("FNAM", name),
            _raw_sr("MCDT", struct.pack("<fIH", weight, value, 0)),
        ]
        if script:
            subrecords.append(_str_sr("SCRI", script))
        if icon:
            subrecords.append(_str_sr("ITEX", icon))
        self._append({"tag": "MISC", "flags": 0, "hdr1": 0, "subrecords": subrecords})
        return self

    # ---- DIAL / INFO — Dialogue --------------------------------------------

    def add_dialogue_topic(
        self,
        name: str,
        topic_type: int = 0,
        responses: list[dict] | None = None,
    ) -> "AddonBuilder":
        """Add a DIAL record and its INFO responses.

        topic_type: 0=topic, 1=voice, 2=greeting, 3=persuasion, 4=journal.
        responses: list of dicts with keys:
          id, prev_id, next_id, text, speaker_id, speaker_race,
          speaker_class, speaker_faction, cell, result_script.
        """
        self._append({
            "tag": "DIAL",
            "flags": 0,
            "hdr1": 0,
            "subrecords": [
                _str_sr("NAME", name),
                _raw_sr("DATA", struct.pack("<B", topic_type)),
            ],
        })
        for resp in (responses or []):
            self._add_info(resp)
        return self

    def _add_info(self, resp: dict) -> None:
        subrecords = [
            _str_sr("INAM", resp.get("id", "")),
            _str_sr("PNAM", resp.get("prev_id", "")),
            _str_sr("NNAM", resp.get("next_id", "")),
        ]
        subrecords.append(_raw_sr("DATA", struct.pack("<BBBI",
            0, resp.get("disposition", 0), 0, 0)))
        if resp.get("speaker_id"):
            subrecords.append(_str_sr("ONAM", resp["speaker_id"]))
        if resp.get("speaker_race"):
            subrecords.append(_str_sr("RNAM", resp["speaker_race"]))
        if resp.get("speaker_class"):
            subrecords.append(_str_sr("CNAM", resp["speaker_class"]))
        if resp.get("speaker_faction"):
            subrecords.append(_str_sr("FNAM", resp["speaker_faction"]))
        if resp.get("cell"):
            subrecords.append(_str_sr("ANAM", resp["cell"]))
        if resp.get("text"):
            subrecords.append(_str_sr("NAME", resp["text"]))
        if resp.get("result_script"):
            subrecords.append(_str_sr("BNAM", resp["result_script"]))
        self._append({"tag": "INFO", "flags": 0, "hdr1": 0, "subrecords": subrecords})

    # ---- GMST — Game Setting -----------------------------------------------

    def add_game_setting(
        self,
        id: str,
        value: str | int | float,
    ) -> "AddonBuilder":
        """Override a game setting (GMST)."""
        subrecords = [_str_sr("NAME", id)]
        if isinstance(value, str):
            subrecords.append(_str_sr("STRV", value))
        elif isinstance(value, float):
            subrecords.append(_raw_sr("FLTV", struct.pack("<f", value)))
        else:
            subrecords.append(_raw_sr("INTV", struct.pack("<i", int(value))))
        self._append({"tag": "GMST", "flags": 0, "hdr1": 0, "subrecords": subrecords})
        return self

    # ---- LEVI — Levelled Item List -----------------------------------------

    def add_levelled_list(
        self,
        id: str,
        items: list[tuple[str, int]],
        chance_none: int = 0,
        flags: int = 0,
    ) -> "AddonBuilder":
        """Add a LEVI record.

        items: list of (item_id, min_pc_level) tuples.
        chance_none: 0-100 probability of no item.
        flags: 0x01=calc from all levels, 0x02=calc for each item.
        """
        subrecords = [
            _str_sr("NAME", id),
            _raw_sr("DATA", struct.pack("<I", flags)),
            _raw_sr("NNAM", struct.pack("<B", chance_none)),
            _raw_sr("INDX", struct.pack("<I", len(items))),
        ]
        for item_id, level in items:
            subrecords.append(_str_sr("INAM", item_id))
            subrecords.append(_raw_sr("INTV", struct.pack("<H", level)))
        self._append({"tag": "LEVI", "flags": 0, "hdr1": 0, "subrecords": subrecords})
        return self

    # ---- Append raw record -------------------------------------------------

    def append_raw_record(self, record: dict) -> "AddonBuilder":
        """Append a pre-built record dict directly (escape hatch for unsupported types)."""
        self._append(record)
        return self
