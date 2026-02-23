"""tes3.db — SQLite persistence layer for TES3 binary files.

Workflow
--------
  omw-to-db  : parse TES3 binaries → store records + subrecords in SQLite
  (edit)     : query / modify the DB with SQL or Python
  omw-from-db: read DB → reconstruct TES3 binary → write to original path

Design
------
- The TES3 header record is *not* stored in ``records``; its metadata lives in
  the ``files`` and ``masters`` tables.
- ``subrecords.parsed`` is a JSON-encoded copy of ``sr["parsed"]`` for easy SQL
  queries.  It is read-only — the export always uses the ``raw`` blob column.
- HEDR is rebuilt on export with ``num_records=0`` so ``write_bytes`` patches it.
- Each ``ingest_file`` call is one atomic transaction.
"""

from __future__ import annotations

import json
import sqlite3
import struct
from pathlib import Path
from typing import Any

from .reader import read_file
from .writer import write_bytes


# ── Schema ────────────────────────────────────────────────────────────────────

_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS _meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT    NOT NULL,
    source_path TEXT    NOT NULL UNIQUE,
    file_type   INTEGER NOT NULL DEFAULT 0,
    description TEXT    NOT NULL DEFAULT '',
    company     TEXT    NOT NULL DEFAULT '',
    version     REAL    NOT NULL DEFAULT 1.3,
    load_order  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS masters (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id     INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    master_name TEXT    NOT NULL,
    master_size INTEGER NOT NULL DEFAULT 0,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS records (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id    INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    tag        TEXT    NOT NULL,
    sort_order INTEGER NOT NULL,
    flags      INTEGER NOT NULL DEFAULT 0,
    hdr1       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS subrecords (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id  INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    tag        TEXT    NOT NULL,
    sort_order INTEGER NOT NULL,
    raw        BLOB    NOT NULL,
    parsed     TEXT    DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_records_file ON records(file_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_records_tag  ON records(file_id, tag);
CREATE INDEX IF NOT EXISTS idx_subs_rec     ON subrecords(record_id, sort_order);
"""

# Views are recreated every time open_db is called so they stay in sync with
# schema changes across toolkit upgrades.
_VIEWS_SQL = """\
DROP VIEW IF EXISTS v_globals;
CREATE VIEW v_globals AS
SELECT
    r.id          AS record_id,
    f.id          AS file_id,
    f.filename,
    json_extract(s_name.parsed, '$') AS id,
    CAST(s_fnam.raw AS TEXT)         AS type_char,
    s_val.tag                        AS value_tag,
    s_val.parsed                     AS value
FROM records r
JOIN files f ON r.file_id = f.id
LEFT JOIN subrecords s_name ON s_name.record_id = r.id AND s_name.tag = 'NAME'
LEFT JOIN subrecords s_fnam ON s_fnam.record_id = r.id AND s_fnam.tag = 'FNAM'
LEFT JOIN subrecords s_val  ON s_val.record_id  = r.id AND s_val.tag IN ('FLTV', 'INTV', 'STRV')
WHERE r.tag = 'GLOB';

DROP VIEW IF EXISTS v_npcs;
CREATE VIEW v_npcs AS
SELECT
    r.id          AS record_id,
    f.id          AS file_id,
    f.filename,
    json_extract(s_name.parsed, '$') AS id,
    json_extract(s_fnam.parsed, '$') AS full_name,
    json_extract(s_rnam.parsed, '$') AS race,
    json_extract(s_cnam.parsed, '$') AS npc_class,
    json_extract(s_anam.parsed, '$') AS faction
FROM records r
JOIN files f ON r.file_id = f.id
LEFT JOIN subrecords s_name ON s_name.record_id = r.id AND s_name.tag = 'NAME'
LEFT JOIN subrecords s_fnam ON s_fnam.record_id = r.id AND s_fnam.tag = 'FNAM'
LEFT JOIN subrecords s_rnam ON s_rnam.record_id = r.id AND s_rnam.tag = 'RNAM'
LEFT JOIN subrecords s_cnam ON s_cnam.record_id = r.id AND s_cnam.tag = 'CNAM'
LEFT JOIN subrecords s_anam ON s_anam.record_id = r.id AND s_anam.tag = 'ANAM'
WHERE r.tag = 'NPC_';

DROP VIEW IF EXISTS v_cells;
CREATE VIEW v_cells AS
SELECT
    r.id          AS record_id,
    f.id          AS file_id,
    f.filename,
    json_extract(s_name.parsed, '$')        AS name,
    json_extract(s_data.parsed, '$.flags')  AS flags,
    json_extract(s_data.parsed, '$.grid_x') AS grid_x,
    json_extract(s_data.parsed, '$.grid_y') AS grid_y
FROM records r
JOIN files f ON r.file_id = f.id
LEFT JOIN subrecords s_name ON s_name.record_id = r.id AND s_name.tag = 'NAME'
LEFT JOIN subrecords s_data ON s_data.record_id = r.id
                           AND s_data.tag = 'DATA'
                           AND length(s_data.raw) = 12
WHERE r.tag = 'CELL';

DROP VIEW IF EXISTS v_statics;
CREATE VIEW v_statics AS
SELECT
    r.id          AS record_id,
    f.id          AS file_id,
    f.filename,
    json_extract(s_name.parsed, '$') AS id,
    json_extract(s_modl.parsed, '$') AS mesh
FROM records r
JOIN files f ON r.file_id = f.id
LEFT JOIN subrecords s_name ON s_name.record_id = r.id AND s_name.tag = 'NAME'
LEFT JOIN subrecords s_modl ON s_modl.record_id = r.id AND s_modl.tag = 'MODL'
WHERE r.tag = 'STAT';

DROP VIEW IF EXISTS v_scripts;
CREATE VIEW v_scripts AS
SELECT
    r.id          AS record_id,
    f.id          AS file_id,
    f.filename,
    json_extract(s_schd.parsed, '$.name') AS id,
    json_extract(s_sctx.parsed, '$')      AS source
FROM records r
JOIN files f ON r.file_id = f.id
LEFT JOIN subrecords s_schd ON s_schd.record_id = r.id AND s_schd.tag = 'SCHD'
LEFT JOIN subrecords s_sctx ON s_sctx.record_id = r.id AND s_sctx.tag = 'SCTX'
WHERE r.tag = 'SCPT';

DROP VIEW IF EXISTS v_dialogs;
CREATE VIEW v_dialogs AS
SELECT
    r.id          AS record_id,
    f.id          AS file_id,
    f.filename,
    json_extract(s_name.parsed, '$')      AS topic,
    json_extract(s_data.parsed, '$.type') AS dialog_type
FROM records r
JOIN files f ON r.file_id = f.id
LEFT JOIN subrecords s_name ON s_name.record_id = r.id AND s_name.tag = 'NAME'
LEFT JOIN subrecords s_data ON s_data.record_id = r.id AND s_data.tag = 'DATA'
WHERE r.tag = 'DIAL';
"""


# ── Public API ────────────────────────────────────────────────────────────────

def open_db(path: str) -> sqlite3.Connection:
    """Open (or create) a toolkit database and apply the schema.

    The database is suitable for further calls to :func:`ingest_file`,
    :func:`export_file`, and :func:`deploy_file`.
    """
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(_SCHEMA_SQL)
    conn.executescript(_VIEWS_SQL)
    conn.commit()
    return conn


def ingest_file(conn: sqlite3.Connection, path: str, load_order: int = 0) -> int:
    """Parse one TES3 file and store its content in *conn*.

    Parameters
    ----------
    conn:
        An open database connection (from :func:`open_db`).
    path:
        Path to a ``.omwaddon`` or ``.omwgame`` file.
    load_order:
        Position in the load order (0 = first master, higher = later).

    Returns
    -------
    int
        The ``file_id`` of the inserted row in the ``files`` table.

    Raises
    ------
    FileExistsError
        If *path* (resolved) has already been ingested into this database.
    """
    resolved = str(Path(path).resolve())

    existing = conn.execute(
        "SELECT id FROM files WHERE source_path = ?", (resolved,)
    ).fetchone()
    if existing:
        raise FileExistsError(
            f"{resolved!r} is already in the database (file_id={existing['id']}). "
            "Use --reset to rebuild from scratch."
        )

    all_records = read_file(resolved)

    # ── Extract TES3 header metadata ──────────────────────────────────────────
    tes3_rec = all_records[0]
    hedr_sr = next((sr for sr in tes3_rec["subrecords"] if sr["tag"] == "HEDR"), None)
    hedr = hedr_sr.get("parsed", {}) if hedr_sr else {}

    version     = hedr.get("version", 1.3)
    file_type   = hedr.get("file_type", 0)
    company     = hedr.get("company", "")
    description = hedr.get("description", "")

    master_pairs: list[tuple[str, int]] = []
    pending_mast: str | None = None
    for sr in tes3_rec["subrecords"]:
        if sr["tag"] == "MAST":
            pending_mast = sr.get("parsed", "")
        elif sr["tag"] == "DATA" and pending_mast is not None:
            msize = struct.unpack_from("<Q", sr["raw"])[0] if len(sr["raw"]) >= 8 else 0
            master_pairs.append((pending_mast, msize))
            pending_mast = None

    filename = Path(resolved).name

    with conn:
        cur = conn.execute(
            """INSERT INTO files
                   (filename, source_path, file_type, description, company, version, load_order)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (filename, resolved, file_type, description, company, version, load_order),
        )
        file_id = cur.lastrowid

        for i, (mname, msize) in enumerate(master_pairs):
            conn.execute(
                "INSERT INTO masters (file_id, master_name, master_size, sort_order)"
                " VALUES (?, ?, ?, ?)",
                (file_id, mname, msize, i),
            )

        # Insert content records — skip the TES3 header (index 0)
        for sort_order, rec in enumerate(all_records[1:]):
            cur = conn.execute(
                "INSERT INTO records (file_id, tag, sort_order, flags, hdr1)"
                " VALUES (?, ?, ?, ?, ?)",
                (file_id, rec["tag"], sort_order,
                 rec.get("flags", 0), rec.get("hdr1", 0)),
            )
            record_id = cur.lastrowid

            for sr_order, sr in enumerate(rec["subrecords"]):
                conn.execute(
                    "INSERT INTO subrecords (record_id, tag, sort_order, raw, parsed)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (record_id, sr["tag"], sr_order,
                     sr["raw"], _to_json(sr.get("parsed"))),
                )

    return file_id


def ingest_files(conn: sqlite3.Connection, paths: list[str]) -> list[int]:
    """Ingest multiple files in load order (index 0 = first master).

    Returns a list of ``file_id`` values in the same order as *paths*.
    """
    return [ingest_file(conn, p, load_order=i) for i, p in enumerate(paths)]


def export_file(conn: sqlite3.Connection, file_id: int) -> bytes:
    """Reconstruct a TES3 binary from the database for *file_id*.

    The resulting bytes are bit-identical to the original file, assuming
    no subrecord ``raw`` columns have been modified.
    """
    row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    if row is None:
        raise KeyError(f"No file with id={file_id} in the database.")

    # ── Rebuild TES3 header ───────────────────────────────────────────────────
    company_b     = (row["company"] or "").encode("latin-1")[:32].ljust(32, b"\x00")
    description_b = (row["description"] or "").encode("latin-1")[:256].ljust(256, b"\x00")
    # num_records = 0 → write_bytes(..., update_num_records=True) will patch this
    hedr_raw = (
        struct.pack("<fI", row["version"], row["file_type"])
        + company_b
        + description_b
        + struct.pack("<I", 0)
    )

    masters = conn.execute(
        "SELECT master_name, master_size FROM masters"
        " WHERE file_id = ? ORDER BY sort_order",
        (file_id,),
    ).fetchall()

    tes3_subs: list[dict] = [
        {"tag": "HEDR", "raw": hedr_raw, "parsed": {"num_records": 0}},
    ]
    for m in masters:
        tes3_subs.append({"tag": "MAST", "raw": m["master_name"].encode("latin-1") + b"\x00"})
        tes3_subs.append({"tag": "DATA", "raw": struct.pack("<Q", m["master_size"])})

    records: list[dict] = [
        {"tag": "TES3", "flags": 0, "hdr1": 0, "subrecords": tes3_subs}
    ]

    # ── Content records ───────────────────────────────────────────────────────
    rec_rows = conn.execute(
        "SELECT id, tag, sort_order, flags, hdr1 FROM records"
        " WHERE file_id = ? ORDER BY sort_order",
        (file_id,),
    ).fetchall()

    for rec_row in rec_rows:
        sr_rows = conn.execute(
            "SELECT tag, raw FROM subrecords WHERE record_id = ? ORDER BY sort_order",
            (rec_row["id"],),
        ).fetchall()
        records.append({
            "tag":        rec_row["tag"],
            "flags":      rec_row["flags"],
            "hdr1":       rec_row["hdr1"],
            "subrecords": [{"tag": sr["tag"], "raw": bytes(sr["raw"])} for sr in sr_rows],
        })

    return write_bytes(records, update_num_records=True)


def deploy_file(conn: sqlite3.Connection, file_id: int) -> str:
    """Export *file_id* and write it back to its original ``source_path``.

    Returns the path written.
    """
    row = conn.execute(
        "SELECT source_path FROM files WHERE id = ?", (file_id,)
    ).fetchone()
    if row is None:
        raise KeyError(f"No file with id={file_id} in the database.")
    path = row["source_path"]
    Path(path).write_bytes(export_file(conn, file_id))
    return path


def list_files(conn: sqlite3.Connection) -> list[dict]:
    """Return metadata rows for all files, ordered by ``load_order``."""
    rows = conn.execute(
        "SELECT id, filename, source_path, file_type, load_order"
        " FROM files ORDER BY load_order"
    ).fetchall()
    return [dict(r) for r in rows]


# ── Internal helpers ──────────────────────────────────────────────────────────

def _to_json(value: Any) -> str | None:
    """JSON-encode a parsed subrecord value, or return None."""
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return None
