# TES3 Binary Format

`.omwgame` / `.omwaddon` are the **TES3 binary format** (same as Morrowind `.esm`/`.esp`).
All integers are **little-endian**.

## Record header — 16 bytes

| Offset | Size | Field  | Description                               |
|--------|------|--------|-------------------------------------------|
| 0      | 4    | tag    | ASCII, e.g. `TES3`, `NPC_`, `CELL`       |
| 4      | 4    | size   | uint32 — byte count of payload only       |
| 8      | 4    | hdr1   | uint32 — flags (usually 0)                |
| 12     | 4    | flags  | uint32 — 0x400=Persistent, 0x2000=Blocked |

## Subrecord header — 8 bytes

| Offset | Size | Field | Description                        |
|--------|------|-------|------------------------------------|
| 0      | 4    | tag   | ASCII, e.g. `NAME`, `DATA`, `FNAM` |
| 4      | 4    | size  | uint32 — byte count of data        |

## TES3 header record

Always the first record. Contains:
- `HEDR` (300 bytes): `float version` (1.3), `uint file_type` (0=esp/omwaddon, 1=esm/omwgame, 32=save), `char[32] company`, `char[256] description`, `uint num_records`.
- Zero or more `MAST`/`DATA` pairs: master filename + uint64 file size.

## String encoding

Most strings are **null-terminated**, encoding **latin-1** (ISO-8859-1).
Fixed-width fields (HEDR company/description) are null-padded to their width.
IDs are **case-insensitive** in the engine — use lowercase consistently.

## All 42 record types

Tags marked `*` have full schema coverage in `tes3/schema.py`; others store unknown subrecords as raw bytes (transparent round-trip).

| Tag    | Represents           | Key subrecords                                    |
|--------|----------------------|---------------------------------------------------|
| `TES3` | File header          | HEDR, MAST/DATA pairs                             |
| `GMST` | Game setting         | NAME (id), STRV/INTV/FLTV (value)                 |
| `GLOB` | Global variable      | NAME, FNAM (type char), FLTV (value)              |
| `CLAS` | Character class      | NAME, FNAM, CLDT (struct), DESC                   |
| `FACT` | Faction              | NAME, FNAM, FADT (struct), ANAM (ranks)           |
| `RACE` | Race                 | NAME, FNAM, RADT (struct), DESC                   |
| `SOUN` | Sound                | NAME, FNAM (wav path), DATA (vol/range)            |
| `SKIL` | Skill                | INDX, SKDT, DESC                                  |
| `MGEF` | Magic effect         | INDX, MEDT, ITEX, PTEX, sounds, CVFXs             |
| `SCPT` | MWScript             | SCHD, SCVR, SCDT (bytecode), SCTX (source)        |
| `REGN` | Region               | NAME, FNAM, WEAT, BNAM, CNAM, SNAM                |
| `BSGN` | Birthsign            | NAME, FNAM, TNAM, DESC, NPCS                      |
| `LTEX` | Land texture         | NAME, INTV (index), DATA (tex path)               |
| `STAT` | Static object        | NAME, MODL (mesh path)                            |
| `DOOR` | Door                 | NAME, MODL, FNAM, SCRI, SNAM, ANAM                |
| `MISC` | Misc. item           | NAME, MODL, FNAM, MCDT, SCRI, ITEX                |
| `WEAP` | Weapon               | NAME, MODL, FNAM, WPDT, ITEX, ENAM, SCRI          |
| `CONT` | Container            | NAME, MODL, FNAM, CNDT, FLAG, SCRI, NPCO×         |
| `SPEL` | Spell                | NAME, FNAM, SPDT, ENAM×                           |
| `CREA` | Creature             | NAME, MODL, FNAM, SCRI, NPDT, AIDT, NPCO×         |
| `BODY` | Body part            | NAME, MODL, FNAM, BYDT                            |
| `LIGH` | Light                | NAME, MODL, FNAM, LHDT, ITEX, SCRI, SNAM          |
| `ENCH` | Enchantment          | NAME, ENDT, ENAM×                                 |
| `NPC_` | NPC                  | NAME, FNAM, RNAM, CNAM, ANAM, BNAM, KNAM, NPDT, FLAG, AIDT, NPCO×, NPCS× |
| `ARMO` | Armour               | NAME, MODL, FNAM, AODT, ITEX, INDX/BNAM/CNAM×    |
| `CLOT` | Clothing             | NAME, MODL, FNAM, CTDT, ITEX, INDX/BNAM/CNAM×    |
| `REPA` | Repair tool          | NAME, MODL, FNAM, RIDT, ITEX, SCRI                |
| `ACTI` | Activator            | NAME, MODL, FNAM, SCRI                            |
| `APPA` | Apparatus            | NAME, MODL, FNAM, AADT, ITEX, SCRI                |
| `LOCK` | Lockpick             | NAME, MODL, FNAM, LKDT, ITEX, SCRI                |
| `PROB` | Probe                | NAME, MODL, FNAM, PBDT, ITEX, SCRI                |
| `INGR` | Ingredient           | NAME, MODL, FNAM, IRDT, ITEX, SCRI                |
| `BOOK` | Book / scroll        | NAME, MODL, FNAM, BKDT, SCRI, ITEX, ENAM, TEXT    |
| `ALCH` | Potion               | NAME, MODL, FNAM, ALDT, SCRI, ITEX, ENAM×         |
| `LEVI` | Levelled item list   | NAME, DATA, NNAM, INDX, INAM×/INTV× pairs         |
| `LEVC` | Levelled creature    | NAME, DATA, NNAM, INDX, CNAM×/INTV× pairs         |
| `CELL` | Cell (int/ext)       | NAME, DATA, AMBI, WHGT, RGNN; then FRMR/NAME/DATA× |
| `LAND` | Landscape            | INTV (grid), DATA, VNML, VHGT, VCLR, VTEX         |
| `PGRD` | Pathgrid             | DATA, NAME, PGRP, PGRC                            |
| `SNDG` | Sound generator      | NAME, DATA, SNAM, CNAM                            |
| `DIAL` | Dialogue topic       | NAME, DATA (type)                                 |
| `INFO` | Dialogue response    | INAM, PNAM, NNAM, DATA, speaker filters, NAME (text), BNAM (script) |

## CELL flags (DATA subrecord, uint32)

| Bit | Hex    | Meaning               |
|-----|--------|-----------------------|
| 0   | 0x0001 | Interior cell         |
| 1   | 0x0002 | Has water             |
| 2   | 0x0004 | Illegal to sleep      |
| 7   | 0x0080 | Behave like exterior  |

## NPC_ flags (FLAG subrecord, uint32)

| Bit | Hex    | Meaning          |
|-----|--------|------------------|
| 0   | 0x0001 | Female           |
| 1   | 0x0002 | Essential        |
| 2   | 0x0004 | Respawn          |
| 3   | 0x0008 | Autocalc stats   |
| 10  | 0x0400 | Skeleton blood   |
| 11  | 0x0800 | Metal blood      |

## NPC_ NPDT — two layouts

- **Autocalc (12 bytes):** `struct.pack("<HBBBxxxI", level, disposition, faction_rank, reputation, gold)` — that is: level(H=2) + disposition(B=1) + faction_rank(B=1) + reputation(B=1) + 3 padding bytes + gold(I=4) = 12.
- **Full (52 bytes):** level, all 8 attributes, 27 skill values, reputation, health, max_magicka, fatigue, disposition, faction_id, rank, unknown, gold.

Use autocalc when you don't need exact stats.
