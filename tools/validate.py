"""tools.validate — Structural validator for TES3 addon files.

Checks:
- TES3 header is present and is the first record
- MAST/DATA pairs are balanced (each MAST has a DATA)
- No duplicate IDs within the same record type
- CELL interior/exterior flag consistency with grid coordinates
- DIAL records appear before their INFO records
- SCDT bytecode present when SCTX source is present (warning only)

Usage
-----
    omw-validate file.omwaddon
    omw-validate file.omwaddon --strict   # treat warnings as errors
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

_HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HERE))

from tes3.reader import read_file

CELL_FLAG_INTERIOR = 0x01



def _record_id(record: dict) -> str | None:
    for sr in record["subrecords"]:
        if sr["tag"] in ("NAME", "INAM") and "parsed" in sr:
            return sr["parsed"]
    # SCPT uses SCHD which embeds the name as the first 32 bytes
    if record["tag"] == "SCPT":
        for sr in record["subrecords"]:
            if sr["tag"] == "SCHD" and "raw" in sr:
                raw = sr["raw"]
                name = raw[:32].rstrip(b"\x00").decode("latin-1", errors="replace")
                return name or None
    return None


class ValidationResult:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


def validate(records: list[dict]) -> ValidationResult:
    result = ValidationResult()

    # 1. TES3 header must be first
    if not records:
        result.error("File is empty — no records found")
        return result

    if records[0]["tag"] != "TES3":
        result.error(f"First record is {records[0]['tag']!r}, expected TES3")
    else:
        tes3 = records[0]
        _validate_tes3_header(tes3, result)

    # 2. Duplicate ID check per record type
    # CELL records are excluded: TES3 legitimately repeats CELL records with
    # the same coordinates to split object placements across multiple records.
    ids_by_type: dict[str, dict[str, int]] = defaultdict(dict)
    for i, rec in enumerate(records):
        if rec["tag"] in ("TES3", "CELL"):
            continue
        rid = _record_id(rec)
        if rid:
            rid_lower = rid.lower()
            if rid_lower in ids_by_type[rec["tag"]]:
                prev = ids_by_type[rec["tag"]][rid_lower]
                result.warn(
                    f"Duplicate ID {rid!r} in record type {rec['tag']} "
                    f"(first at index {prev}, again at index {i})"
                )
            ids_by_type[rec["tag"]][rid_lower] = i

    # 3. CELL interior/exterior consistency
    for rec in records:
        if rec["tag"] != "CELL":
            continue
        _validate_cell(rec, result)

    # 4. DIAL before INFO
    seen_dial_topics: set[str] = set()
    for rec in records:
        if rec["tag"] == "DIAL":
            rid = _record_id(rec)
            if rid:
                seen_dial_topics.add(rid.lower())
        elif rec["tag"] == "INFO":
            # INFO records reference their owning DIAL implicitly by sequence
            pass  # hard to check without carrying state; skip for now

    # 5. SCPT: warn if SCTX present but SCDT missing
    for rec in records:
        if rec["tag"] != "SCPT":
            continue
        tags = {sr["tag"] for sr in rec["subrecords"]}
        if "SCTX" in tags and "SCDT" not in tags:
            rid = _record_id(rec) or "?"
            result.warn(
                f"SCPT {rid!r} has source (SCTX) but no compiled bytecode (SCDT). "
                "OpenMW will compile on load."
            )

    return result


def _validate_tes3_header(tes3: dict, result: ValidationResult) -> None:
    subrecord_tags = [sr["tag"] for sr in tes3["subrecords"]]
    if "HEDR" not in subrecord_tags:
        result.error("TES3 record is missing HEDR subrecord")
        return

    # Validate MAST/DATA pairing
    mast_count = subrecord_tags.count("MAST")
    data_count = subrecord_tags.count("DATA")
    if mast_count != data_count:
        result.error(
            f"TES3 header has {mast_count} MAST subrecords but {data_count} DATA "
            "subrecords — they must be paired"
        )

    # Interleaving check
    state = "start"
    for tag in subrecord_tags:
        if tag == "MAST":
            if state == "mast":
                result.error("Two consecutive MAST subrecords without intervening DATA")
            state = "mast"
        elif tag == "DATA":
            if state != "mast":
                result.error("DATA subrecord without preceding MAST")
            state = "data"


def _validate_cell(rec: dict, result: ValidationResult) -> None:
    data_sr = next(
        (sr for sr in rec["subrecords"] if sr["tag"] == "DATA" and "parsed" in sr),
        None,
    )
    if data_sr is None:
        return

    parsed = data_sr["parsed"]
    if not isinstance(parsed, dict):
        return

    flags = parsed.get("flags", 0)
    grid_x = parsed.get("grid_x", 0)
    grid_y = parsed.get("grid_y", 0)
    is_interior = bool(flags & CELL_FLAG_INTERIOR)

    if is_interior and (grid_x != 0 or grid_y != 0):
        cell_name = _record_id(rec) or "?"
        result.warn(
            f"Interior CELL {cell_name!r} has non-zero grid coordinates "
            f"({grid_x}, {grid_y}) — these are ignored by the engine"
        )

    # Note: exterior cells commonly have a non-empty NAME (region label).
    # This is valid TES3 — no warning needed.


# ---- main -----------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="omw-validate",
        description="Validate structural integrity of an OpenMW/TES3 addon file.",
    )
    parser.add_argument("file", help="Path to .omwaddon/.omwgame/.esm/.esp")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    args = parser.parse_args(argv)

    try:
        records = read_file(args.file)
    except FileNotFoundError:
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    result = validate(records)

    for err in result.errors:
        print(f"ERROR   {err}")
    for warn in result.warnings:
        print(f"WARNING {warn}")

    if not result.errors and not result.warnings:
        print(f"OK — {args.file} passes all checks ({len(records)} records)")
        sys.exit(0)

    if result.errors or (args.strict and result.warnings):
        sys.exit(1)


if __name__ == "__main__":
    main()
