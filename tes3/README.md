# tes3/ — Low-level TES3 binary layer

This package handles the raw TES3 binary format used by `.omwaddon` and
`.omwgame` files (identical to Morrowind `.esp` / `.esm`).

| Module | Purpose |
|--------|---------|
| `reader.py` | Parse binary → list of record dicts |
| `writer.py` | Serialize record dicts → binary |
| `schema.py` | Subrecord format definitions for all 42 record types |
| `db.py` | SQLite persistence layer (ingest → edit → deploy) |

---

## reader / writer

```python
from tes3.reader import read_file
from tes3.writer import write_file, write_bytes

records = read_file("my_addon.omwaddon")
# records is a list of dicts:
# [
#   {"tag": "TES3", "flags": 0, "hdr1": 0, "subrecords": [
#       {"tag": "HEDR", "raw": b"...", "parsed": {"version": 1.3, ...}},
#       {"tag": "MAST", "raw": b"template.omwgame\x00", "parsed": "template.omwgame"},
#   ]},
#   {"tag": "GLOB", "flags": 0, "hdr1": 0, "subrecords": [
#       {"tag": "NAME", "raw": b"MyVar\x00", "parsed": "MyVar"},
#       {"tag": "FLTV", "raw": b"\x00\x00\x80?", "parsed": 1.0},
#   ]},
#   ...
# ]

# Modify raw bytes directly, then round-trip
import struct
for rec in records:
    for sr in rec["subrecords"]:
        if rec["tag"] == "GLOB" and sr["tag"] == "FLTV":
            sr["raw"] = struct.pack("<f", 99.0)

write_file(records, "modified.omwaddon")          # write to file
data: bytes = write_bytes(records)                 # or get bytes
```

The writer always uses `raw` bytes. `parsed` is informational only.
Round-trip output is bit-identical to the original.

---

## db — SQLite workflow

`db.py` adds an intermediate SQLite layer so you can inspect and edit
records with SQL instead of raw bytes.

```
TES3 binary  ──ingest──▶  SQLite DB  ──export──▶  TES3 binary
                                ▲
                           SQL / Python edits
```

### CLI

```bash
# Ingest (pass files in load order: masters first, addon last)
omw-to-db template.omwgame my_addon.omwaddon --db workspace.db

# Rebuild DB from scratch
omw-to-db template.omwgame my_addon.omwaddon --db workspace.db --reset

# List files stored in the DB
omw-from-db --db workspace.db --list

# Export one file (by file_id) to disk
omw-from-db --db workspace.db --export 2 --out /tmp/preview.omwaddon

# Write one file back to its original source path
omw-from-db --db workspace.db --deploy 2

# Write all addon files (file_type=0) back to their source paths
omw-from-db --db workspace.db --deploy-all
```

### Python API

```python
from tes3.db import open_db, ingest_files, ingest_file, \
                    export_file, deploy_file, list_files

conn = open_db("workspace.db")          # create or open

# Ingest
ids = ingest_files(conn, ["template.omwgame", "my_addon.omwaddon"])
# or one at a time:
fid = ingest_file(conn, "my_addon.omwaddon", load_order=1)

# Inspect
for f in list_files(conn):
    print(f["id"], f["filename"], f["file_type"])

# Export
data: bytes = export_file(conn, fid)    # → bytes
path: str   = deploy_file(conn, fid)    # → write to source_path, return path

conn.close()
```

### Database schema

```
files        id, filename, source_path, file_type, description,
             company, version, load_order

masters      file_id → files, master_name, master_size, sort_order

records      file_id → files, tag, sort_order, flags, hdr1

subrecords   record_id → records, tag, sort_order,
             raw   BLOB   — verbatim bytes from the file (used on export)
             parsed TEXT  — JSON of the parsed value, for queries only
```

The TES3 header record is **not** stored in `records`; its metadata
goes into `files` and `masters`.

### Convenience views

| View | Key columns |
|------|-------------|
| `v_npcs` | `id`, `full_name`, `race`, `npc_class`, `faction` |
| `v_cells` | `name`, `flags`, `grid_x`, `grid_y` |
| `v_globals` | `id`, `type_char`, `value_tag`, `value` |
| `v_statics` | `id`, `mesh` |
| `v_scripts` | `id`, `source` |
| `v_dialogs` | `topic`, `dialog_type` |

```bash
sqlite3 workspace.db "SELECT * FROM v_npcs;"
sqlite3 workspace.db "SELECT * FROM v_cells WHERE flags & 1;"   -- interiors
sqlite3 workspace.db "SELECT * FROM v_scripts WHERE id = 'EnableMenus';"

# JSON fields via json_extract
sqlite3 workspace.db "
  SELECT json_extract(s.parsed, '$.disposition')
  FROM subrecords s JOIN records r ON s.record_id = r.id
  WHERE r.tag = 'NPC_' AND s.tag = 'AIDT';"
```

### Editing

`parsed` is read-only. Edits go through the `raw` column.

```python
import struct
from tes3.db import open_db

conn = open_db("workspace.db")

# Find the AIDT subrecord for a specific NPC
row = conn.execute("""
    SELECT s.id, s.raw
    FROM subrecords s
    JOIN records r      ON s.record_id = r.id
    JOIN subrecords s_n ON s_n.record_id = r.id AND s_n.tag = 'NAME'
    WHERE r.tag = 'NPC_' AND s.tag = 'AIDT'
      AND json_extract(s_n.parsed, '$') = 'hw_vendor'
""").fetchone()

# Unpack the 12-byte AIDT struct, change disposition, repack
hello, fight, flee, alarm, u1, u2, u3, u4, services = \
    struct.unpack("<BBBBBBBBI", row["raw"])

conn.execute("UPDATE subrecords SET raw = ? WHERE id = ?",
             (struct.pack("<BBBBBBBBI",
                          80, fight, flee, alarm, u1, u2, u3, u4, services),
              row["id"]))
conn.commit()

# Write back to disk
from tes3.db import deploy_file
deploy_file(conn, file_id=1)
conn.close()
```

> **Remember:** struct sizes are fixed — pack the exact byte count the
> engine expects (see CLAUDE.md §11) or OpenMW will refuse to load the file.
> String subrecords need a `\x00` null terminator (`SCTX` is the exception).
> After any edit run `omw-validate` before launching OpenMW.
