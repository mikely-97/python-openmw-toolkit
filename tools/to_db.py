"""omw-to-db — Ingest TES3 files into a SQLite workspace database.

Usage
-----
    omw-to-db template.omwgame my_addon.omwaddon [--db workspace.db] [--reset]

Files should be given in load order: masters first, your addon last.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tes3.db import open_db, ingest_file


def main() -> None:
    p = argparse.ArgumentParser(
        prog="omw-to-db",
        description=(
            "Parse OpenMW addon/game files into a SQLite database.\n"
            "Pass files in load order: masters first, your addon last."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "files",
        nargs="+",
        metavar="FILE",
        help="TES3 files to ingest (in load order)",
    )
    p.add_argument(
        "--db",
        default="openmw.db",
        metavar="PATH",
        help="SQLite database path (default: openmw.db)",
    )
    p.add_argument(
        "--reset",
        action="store_true",
        help="Delete and recreate the database before ingesting",
    )
    args = p.parse_args()

    db_path = args.db
    if args.reset and Path(db_path).exists():
        Path(db_path).unlink()
        print(f"Removed {db_path!r}")

    conn = open_db(db_path)
    errors = 0

    for i, fpath in enumerate(args.files):
        try:
            fid = ingest_file(conn, fpath, load_order=i)
            size = Path(fpath).stat().st_size
            print(f"  [{fid}] {Path(fpath).name}  ({size:,} bytes)")
        except FileExistsError as exc:
            print(f"  SKIP  {Path(fpath).name}  — {exc}", file=sys.stderr)
        except Exception as exc:
            print(f"  ERROR {fpath}: {exc}", file=sys.stderr)
            errors += 1

    print()
    print(f"Database : {db_path}")
    print(f"Tables   : files, records, subrecords, masters")
    print(f"Views    : v_globals, v_npcs, v_cells, v_statics, v_scripts, v_dialogs")

    conn.close()
    if errors:
        sys.exit(1)
