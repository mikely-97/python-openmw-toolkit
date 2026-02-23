"""tes3.reader — Parse TES3 binary files into Python dicts.

Zero external dependencies; uses only stdlib `struct`.

Output format
-------------
A list of record dicts:

    [
        {
            "tag": "TES3",
            "flags": 0,
            "subrecords": [
                {"tag": "HEDR", "raw": b"...", "parsed": {
                    "version": 1.3,
                    "file_type": 0,
                    "company": "",
                    "description": "",
                    "num_records": 227,
                }},
                {"tag": "MAST", "raw": b"template.omwgame\\x00", "parsed": "template.omwgame"},
                ...
            ]
        },
        {
            "tag": "NPC_",
            "flags": 0,
            "subrecords": [
                {"tag": "NAME", "raw": b"ra'virr\\x00", "parsed": "ra'virr"},
                ...
            ]
        },
        ...
    ]

Rules:
- "raw" is always present (the verbatim bytes from the file).
- "parsed" is present when a schema is known; it is a Python object
  (dict for struct schemas, str for string schemas, None for raw-only).
- Unknown subrecords have only "raw"; no "parsed" key.
- Round-trip fidelity: write_bytes(read_bytes(data)) == data.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

from .schema import (
    SUBRECORD_SCHEMAS,
    HedrSchema,
    SubrecordSchema,
    StringSchema,
)

# ---- constants ------------------------------------------------------------

RECORD_HEADER_SIZE = 16   # tag(4) + size(4) + hdr1(4) + flags(4)
SUBREC_HEADER_SIZE = 8    # tag(4) + size(4)
RECORD_STRUCT = struct.Struct("<4sIII")
SUBREC_STRUCT = struct.Struct("<4sI")


# ---- public API -----------------------------------------------------------

def read_file(path: str | Path) -> list[dict]:
    """Parse a TES3 binary file and return a list of record dicts."""
    data = Path(path).read_bytes()
    return read_bytes(data)


def read_bytes(data: bytes | memoryview) -> list[dict]:
    """Parse TES3 binary data from a bytes buffer."""
    if isinstance(data, memoryview):
        data = bytes(data)
    records: list[dict] = []
    offset = 0
    length = len(data)

    while offset + RECORD_HEADER_SIZE <= length:
        tag_b, size, hdr1, flags = RECORD_STRUCT.unpack_from(data, offset)
        tag = tag_b.decode("ascii", errors="replace").rstrip("\x00")
        offset += RECORD_HEADER_SIZE

        payload_end = offset + size
        if payload_end > length:
            # Truncated file — store what we have
            payload_end = length

        subrecords = _parse_subrecords(data, offset, payload_end, tag)
        records.append({"tag": tag, "flags": flags, "hdr1": hdr1, "subrecords": subrecords})
        offset = payload_end

    return records


# ---- internal helpers -----------------------------------------------------

def _parse_subrecords(
    data: bytes,
    offset: int,
    end: int,
    record_tag: str,
) -> list[dict]:
    subrecords: list[dict] = []
    while offset + SUBREC_HEADER_SIZE <= end:
        sr_tag_b, sr_size = SUBREC_STRUCT.unpack_from(data, offset)
        sr_tag = sr_tag_b.decode("ascii", errors="replace").rstrip("\x00")
        offset += SUBREC_HEADER_SIZE

        sr_end = offset + sr_size
        raw = data[offset:sr_end]

        entry: dict[str, Any] = {"tag": sr_tag, "raw": raw}

        parsed = _parse_subrecord(record_tag, sr_tag, raw)
        if parsed is not None:
            entry["parsed"] = parsed

        subrecords.append(entry)
        offset = sr_end

    return subrecords


def _parse_subrecord(record_tag: str, sr_tag: str, raw: bytes) -> Any:
    """Return a parsed value for the subrecord, or None if unknown/raw-only."""
    # CELL/DATA is overloaded: 12 bytes = cell header (flags, grid_x, grid_y),
    # 24 bytes = object reference position (x, y, z, rot_x, rot_y, rot_z).
    if record_tag == "CELL" and sr_tag == "DATA":
        if len(raw) == 24:
            try:
                x, y, z, rx, ry, rz = struct.unpack_from("<ffffff", raw)
                return {"x": x, "y": y, "z": z, "rot_x": rx, "rot_y": ry, "rot_z": rz}
            except struct.error:
                return None
        elif len(raw) <= 16:
            # cell header: flags(I) grid_x(i) grid_y(i) — 12 bytes standard
            try:
                flags, gx, gy = struct.unpack_from("<Iii", raw[:12])
                return {"flags": flags, "grid_x": gx, "grid_y": gy}
            except struct.error:
                return None

    schema = SUBRECORD_SCHEMAS.get((record_tag, sr_tag))

    if schema is None:
        # Try a generic fallback for common string-only tags
        if sr_tag in _GENERIC_STRING_TAGS:
            return _decode_string(raw)
        return None

    if isinstance(schema, HedrSchema):
        return _parse_hedr(raw)

    if isinstance(schema, StringSchema):
        return _decode_string(raw, schema.encoding)

    if isinstance(schema, SubrecordSchema):
        return _parse_struct(schema, raw)

    # schema is None (marked as raw-only in schema.py)
    return None


def _parse_hedr(raw: bytes) -> dict:
    """Parse the 300-byte HEDR subrecord of a TES3 record."""
    if len(raw) < 300:
        raw = raw.ljust(300, b"\x00")
    version, file_type = struct.unpack_from("<fI", raw, 0)
    company = raw[8:40].rstrip(b"\x00").decode("latin-1")
    description = raw[40:296].rstrip(b"\x00").decode("latin-1")
    num_records = struct.unpack_from("<I", raw, 296)[0]
    return {
        "version": round(version, 6),
        "file_type": file_type,
        "company": company,
        "description": description,
        "num_records": num_records,
    }


def _parse_struct(schema: SubrecordSchema, raw: bytes) -> dict:
    """Unpack a fixed-layout struct subrecord into a dict."""
    try:
        size = struct.calcsize(schema.fmt)
        if len(raw) < size:
            raw = raw.ljust(size, b"\x00")
        values = struct.unpack_from(schema.fmt, raw)
        result = {}
        for field, val in zip(schema.fields, values):
            # Decode byte-string fields (32s, etc.)
            if isinstance(val, bytes):
                val = val.rstrip(b"\x00").decode("latin-1")
            result[field] = val
        return result
    except struct.error:
        return {}


def _decode_string(raw: bytes, encoding: str = "latin-1") -> str:
    """Strip null terminator and decode bytes to str."""
    null_pos = raw.find(b"\x00")
    if null_pos >= 0:
        raw = raw[:null_pos]
    return raw.decode(encoding, errors="replace")


# Tags that are string-valued in most record types (fallback when no schema)
_GENERIC_STRING_TAGS = frozenset([
    "NAME", "FNAM", "MODL", "ITEX", "ICON", "SCRI", "SNAM", "BNAM",
    "CNAM", "ANAM", "RNAM", "KNAM", "DNAM", "TNAM", "ENAM", "DESC",
    "TEXT", "PTEX", "NNAM", "PNAM", "INAM", "ONAM", "QNAM", "MNAM",
])
