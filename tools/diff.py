"""tools.diff — Compare two TES3 addon files record-by-record.

Shows added, removed, and changed records by type+ID.

Usage
-----
    omw-diff original.omwaddon modified.omwaddon
    omw-diff original.omwaddon modified.omwaddon --json
    omw-diff original.omwaddon modified.omwaddon --record NPC_
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HERE))

from tes3.reader import read_file


def _record_key(record: dict) -> tuple[str, str]:
    """Return a (tag, id) tuple that uniquely identifies a record."""
    tag = record["tag"]
    for sr in record["subrecords"]:
        if sr["tag"] in ("NAME", "INAM") and "parsed" in sr:
            return (tag, sr["parsed"].lower())
    return (tag, "")


def _subrecords_equal(a: list[dict], b: list[dict]) -> bool:
    """Compare two subrecord lists by their raw bytes."""
    if len(a) != len(b):
        return False
    for sa, sb in zip(a, b):
        if sa["tag"] != sb["tag"]:
            return False
        if sa.get("raw") != sb.get("raw"):
            return False
    return True


def diff_records(
    orig: list[dict],
    modified: list[dict],
) -> dict[str, list]:
    """
    Return a dict with keys 'added', 'removed', 'changed'.
    Each entry is a list of record dicts (from the appropriate file).
    TES3 header changes are reported separately.
    """
    orig_map: dict[tuple[str, str], dict] = {}
    for rec in orig:
        key = _record_key(rec)
        orig_map[key] = rec

    mod_map: dict[tuple[str, str], dict] = {}
    for rec in modified:
        key = _record_key(rec)
        mod_map[key] = rec

    added = [mod_map[k] for k in mod_map if k not in orig_map]
    removed = [orig_map[k] for k in orig_map if k not in mod_map]
    changed = [
        mod_map[k]
        for k in mod_map
        if k in orig_map and not _subrecords_equal(orig_map[k]["subrecords"], mod_map[k]["subrecords"])
    ]

    return {"added": added, "removed": removed, "changed": changed}


def _record_summary(rec: dict) -> str:
    tag = rec["tag"]
    for sr in rec["subrecords"]:
        if sr["tag"] in ("NAME", "INAM") and "parsed" in sr:
            return f"{tag}[{sr['parsed']}]"
    return f"{tag}"


# ---- main -----------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="omw-diff",
        description="Compare two OpenMW/TES3 addon files.",
    )
    parser.add_argument("original", help="Original file")
    parser.add_argument("modified", help="Modified file")
    parser.add_argument("--record", "-r", metavar="TAG", help="Limit diff to a specific record type")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    args = parser.parse_args(argv)

    def _load(path: str) -> list[dict]:
        try:
            return read_file(path)
        except FileNotFoundError:
            print(f"Error: file not found: {path}", file=sys.stderr)
            sys.exit(1)

    orig_records = _load(args.original)
    mod_records = _load(args.modified)

    if args.record:
        tag_filter = args.record.strip()
        orig_records = [r for r in orig_records if r["tag"] == tag_filter]
        mod_records = [r for r in mod_records if r["tag"] == tag_filter]

    result = diff_records(orig_records, mod_records)

    if args.json:

        def _rec_to_json(rec: dict) -> dict:
            srs = []
            for sr in rec["subrecords"]:
                entry: dict[str, Any] = {"tag": sr["tag"]}
                if "parsed" in sr:
                    entry["parsed"] = sr["parsed"]
                entry["raw"] = sr.get("raw", b"").hex()
                srs.append(entry)
            return {"tag": rec["tag"], "flags": rec["flags"], "subrecords": srs}

        print(json.dumps(
            {k: [_rec_to_json(r) for r in v] for k, v in result.items()},
            indent=2,
        ))
        return

    total = sum(len(v) for v in result.values())
    if total == 0:
        print("Files are identical (for the selected record types).")
        return

    if result["added"]:
        print(f"ADDED ({len(result['added'])}):")
        for rec in result["added"]:
            print(f"  + {_record_summary(rec)}")

    if result["removed"]:
        print(f"\nREMOVED ({len(result['removed'])}):")
        for rec in result["removed"]:
            print(f"  - {_record_summary(rec)}")

    if result["changed"]:
        print(f"\nCHANGED ({len(result['changed'])}):")
        for rec in result["changed"]:
            print(f"  ~ {_record_summary(rec)}")


if __name__ == "__main__":
    main()
