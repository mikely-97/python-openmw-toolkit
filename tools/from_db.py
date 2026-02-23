"""omw-from-db — Export TES3 files from a SQLite workspace database.

Usage
-----
    omw-from-db [--db workspace.db] --list
    omw-from-db [--db workspace.db] --export FILE_ID [--out PATH]
    omw-from-db [--db workspace.db] --deploy FILE_ID
    omw-from-db [--db workspace.db] --deploy-all
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tes3.db import open_db, list_files, export_file, deploy_file

_FILE_TYPES = {0: "addon", 1: "master", 32: "save"}


def main() -> None:
    p = argparse.ArgumentParser(
        prog="omw-from-db",
        description="Export OpenMW addon/game files from a SQLite database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--db",
        default="openmw.db",
        metavar="PATH",
        help="SQLite database path (default: openmw.db)",
    )

    action = p.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "--list",
        action="store_true",
        help="List all files stored in the database",
    )
    action.add_argument(
        "--export",
        metavar="FILE_ID",
        type=int,
        help="Reconstruct binary for FILE_ID and write it to disk",
    )
    action.add_argument(
        "--deploy",
        metavar="FILE_ID",
        type=int,
        help="Reconstruct binary for FILE_ID and overwrite its source path",
    )
    action.add_argument(
        "--deploy-all",
        action="store_true",
        help="Deploy all addon files (file_type=0) back to their source paths",
    )

    p.add_argument(
        "--out",
        metavar="PATH",
        help="Output path for --export (default: original source path)",
    )

    args = p.parse_args()

    if not Path(args.db).exists():
        print(f"Database not found: {args.db!r}", file=sys.stderr)
        print("Run  omw-to-db <files...>  first.", file=sys.stderr)
        sys.exit(1)

    conn = open_db(args.db)

    # ── --list ────────────────────────────────────────────────────────────────
    if args.list:
        files = list_files(conn)
        if not files:
            print("No files in database.")
        else:
            print(f"{'ID':>4}  {'Type':>6}  {'Order':>5}  Filename")
            print("─" * 72)
            for f in files:
                ftype = _FILE_TYPES.get(f["file_type"], f"type{f['file_type']}")
                print(f"  {f['id']:>4}  {ftype:>6}  {f['load_order']:>5}  {f['filename']}")
                print(f"              {f['source_path']}")
        conn.close()
        return

    # ── --export FILE_ID ──────────────────────────────────────────────────────
    if args.export is not None:
        try:
            data = export_file(conn, args.export)
        except KeyError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            conn.close()
            sys.exit(1)

        out = args.out
        if out is None:
            row = conn.execute(
                "SELECT source_path FROM files WHERE id = ?", (args.export,)
            ).fetchone()
            out = row["source_path"]

        Path(out).write_bytes(data)
        print(f"Exported {len(data):,} bytes → {out}")
        conn.close()
        return

    # ── --deploy FILE_ID ──────────────────────────────────────────────────────
    if args.deploy is not None:
        try:
            path = deploy_file(conn, args.deploy)
            print(f"Deployed → {path}")
        except KeyError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            conn.close()
            sys.exit(1)
        conn.close()
        return

    # ── --deploy-all ──────────────────────────────────────────────────────────
    if args.deploy_all:
        files = list_files(conn)
        addons = [f for f in files if f["file_type"] == 0]
        if not addons:
            print(
                "No addon files (file_type=0) in the database. "
                "Use --export or --deploy for master files.",
                file=sys.stderr,
            )
            conn.close()
            sys.exit(1)

        errors = 0
        for f in addons:
            try:
                path = deploy_file(conn, f["id"])
                print(f"Deployed → {path}")
            except Exception as exc:
                print(f"Error deploying [{f['id']}] {f['filename']}: {exc}", file=sys.stderr)
                errors += 1

        conn.close()
        if errors:
            sys.exit(1)
