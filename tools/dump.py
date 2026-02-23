"""tools.dump — Inspect TES3 binary files as human-readable text or JSON.

Usage
-----
    omw-dump file.omwaddon
    omw-dump file.omwaddon --record NPC_
    omw-dump file.omwaddon --record NPC_ --id "ra'virr"
    omw-dump file.omwaddon --json
    omw-dump file.omwaddon --json --record CELL > dump.json
    omw-dump file.omwaddon --stats
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Allow running as a standalone script (not installed as package)
_HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HERE))

from tes3.reader import read_file


# ---- JSON serialization helper --------------------------------------------

def _json_default(obj: Any) -> Any:
    if isinstance(obj, bytes):
        # Emit bytes as hex string for JSON portability
        return obj.hex()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _record_id(record: dict) -> str | None:
    """Extract the primary identifier from a record (first NAME or INAM subrecord)."""
    for sr in record["subrecords"]:
        if sr["tag"] in ("NAME", "INAM") and "parsed" in sr:
            return sr["parsed"]
    return None


def _record_to_display(record: dict, verbose: bool = False) -> list[str]:
    """Format a record as human-readable lines."""
    lines = []
    record_id = _record_id(record)
    id_str = f"  [{record_id}]" if record_id else ""
    lines.append(f"{'─' * 60}")
    lines.append(f"  {record['tag']}{id_str}  flags={record['flags']:#010x}")
    for sr in record["subrecords"]:
        tag = sr["tag"]
        raw = sr.get("raw", b"")
        parsed = sr.get("parsed")

        if parsed is not None:
            if isinstance(parsed, dict):
                lines.append(f"    {tag}:")
                for k, v in parsed.items():
                    lines.append(f"      {k} = {v!r}")
            elif isinstance(parsed, str):
                lines.append(f"    {tag} = {parsed!r}")
            else:
                lines.append(f"    {tag} = {parsed!r}")
        else:
            if verbose:
                hex_str = raw[:32].hex()
                suffix = "..." if len(raw) > 32 else ""
                lines.append(f"    {tag} [{len(raw)}B] {hex_str}{suffix}")
            else:
                lines.append(f"    {tag} [{len(raw)}B] (raw)")
    return lines


# ---- stats output ----------------------------------------------------------

def _print_stats(records: list[dict]) -> None:
    from collections import Counter
    counts: Counter[str] = Counter()
    for r in records:
        counts[r["tag"]] += 1
    total = sum(counts.values())
    print(f"Total records: {total}")
    print()
    print(f"{'Tag':<8}  {'Count':>6}")
    print(f"{'─' * 8}  {'─' * 6}")
    for tag, count in counts.most_common():
        print(f"{tag:<8}  {count:>6}")


# ---- main -----------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="omw-dump",
        description="Inspect OpenMW/TES3 binary addon files.",
    )
    parser.add_argument("file", help="Path to .omwaddon/.omwgame/.esm/.esp file")
    parser.add_argument("--record", "-r", metavar="TAG", help="Filter to a specific record type (e.g. NPC_)")
    parser.add_argument("--id", "-i", metavar="ID", help="Filter to a specific record by its NAME/INAM id")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    parser.add_argument("--stats", "-s", action="store_true", help="Print record type counts and exit")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show raw bytes for unknown subrecords")
    args = parser.parse_args(argv)

    try:
        records = read_file(args.file)
    except FileNotFoundError:
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    if args.stats:
        _print_stats(records)
        return

    # Filter by record type
    if args.record:
        tag_filter = args.record.upper().ljust(4)[:4]  # normalise to 4 chars
        records = [r for r in records if r["tag"] == args.record or r["tag"].ljust(4)[:4] == tag_filter]

    # Filter by ID
    if args.id:
        id_lower = args.id.lower()
        records = [r for r in records if (_record_id(r) or "").lower() == id_lower]

    if args.json:
        # Produce JSON — convert bytes to hex
        output: list[dict] = []
        for rec in records:
            srs = []
            for sr in rec["subrecords"]:
                entry: dict[str, Any] = {"tag": sr["tag"]}
                if "parsed" in sr:
                    entry["parsed"] = sr["parsed"]
                # Always include raw as hex
                entry["raw"] = sr.get("raw", b"").hex()
                srs.append(entry)
            output.append({
                "tag": rec["tag"],
                "flags": rec["flags"],
                "hdr1": rec.get("hdr1", 0),
                "subrecords": srs,
            })
        print(json.dumps(output, indent=2, default=_json_default))
    else:
        if not records:
            print("(no matching records)")
            return
        for rec in records:
            lines = _record_to_display(rec, verbose=args.verbose)
            print("\n".join(lines))
        print("─" * 60)


if __name__ == "__main__":
    main()
