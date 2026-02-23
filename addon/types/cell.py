"""addon.types.cell — CellBuilder: place objects into CELL records."""

from __future__ import annotations

import struct


def _ref_sr(tag: str, data: bytes) -> dict:
    return {"tag": tag, "raw": data}


def _str_sr(tag: str, value: str) -> dict:
    return {"tag": tag, "raw": value.encode("latin-1") + b"\x00", "parsed": value}


# Static counter for FRMR (reference frame number) — monotonically increasing
_frmr_counter = 1


def _next_frmr() -> int:
    global _frmr_counter
    val = _frmr_counter
    _frmr_counter += 1
    return val


class CellBuilder:
    """Fluent builder for placing objects into a CELL record.

    Returned by AddonBuilder.add_interior_cell() and add_exterior_cell().
    Modifies the cell record dict in-place.
    """

    def __init__(self, cell_record: dict) -> None:
        self._record = cell_record

    def _place(
        self,
        base_id: str,
        x: float,
        y: float,
        z: float,
        rot_x: float = 0.0,
        rot_y: float = 0.0,
        rot_z: float = 0.0,
        scale: float = 1.0,
    ) -> "CellBuilder":
        """Internal: append FRMR + NAME + DATA subrecords for a placed object."""
        frmr = _next_frmr()
        srs = self._record["subrecords"]
        srs.append(_ref_sr("FRMR", struct.pack("<I", frmr)))
        srs.append(_str_sr("NAME", base_id))
        # DATA for an object reference: 24 bytes — x, y, z, rot_x, rot_y, rot_z
        srs.append(_ref_sr("DATA", struct.pack("<ffffff", x, y, z, rot_x, rot_y, rot_z)))
        if scale != 1.0:
            srs.append(_ref_sr("XSCL", struct.pack("<f", scale)))
        return self

    def place_npc(
        self,
        npc_id: str,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        rotation: float = 0.0,
        scale: float = 1.0,
    ) -> "CellBuilder":
        """Place an NPC reference into the cell."""
        return self._place(npc_id, x, y, z, rot_z=rotation, scale=scale)

    def place_static(
        self,
        stat_id: str,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        rot_x: float = 0.0,
        rot_y: float = 0.0,
        rot_z: float = 0.0,
        scale: float = 1.0,
    ) -> "CellBuilder":
        """Place a static object reference into the cell."""
        return self._place(stat_id, x, y, z, rot_x, rot_y, rot_z, scale)

    def place_door(
        self,
        door_id: str,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        rot_z: float = 0.0,
        destination_cell: str = "",
        destination_pos: tuple[float, float, float] = (0.0, 0.0, 0.0),
        destination_rot: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> "CellBuilder":
        """Place a door and optionally wire its teleport destination."""
        self._place(door_id, x, y, z, rot_z=rot_z)
        if destination_cell:
            dx, dy, dz = destination_pos
            drx, dry, drz = destination_rot
            srs = self._record["subrecords"]
            srs.append({
                "tag": "DODT",
                "raw": struct.pack("<ffffff", dx, dy, dz, drx, dry, drz),
            })
            srs.append(_str_sr("DNAM", destination_cell))
        return self

    def place_container(
        self,
        cont_id: str,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        rot_z: float = 0.0,
    ) -> "CellBuilder":
        """Place a container reference."""
        return self._place(cont_id, x, y, z, rot_z=rot_z)

    def place_light(
        self,
        light_id: str,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        rot_z: float = 0.0,
    ) -> "CellBuilder":
        """Place a light source."""
        return self._place(light_id, x, y, z, rot_z=rot_z)

    def place_item(
        self,
        item_id: str,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        rot_z: float = 0.0,
        count: int = 1,
    ) -> "CellBuilder":
        """Place a misc/inventory item on the ground."""
        self._place(item_id, x, y, z, rot_z=rot_z)
        if count != 1:
            srs = self._record["subrecords"]
            srs.append({"tag": "FLTV", "raw": struct.pack("<I", count)})
        return self
