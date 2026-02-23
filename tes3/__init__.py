"""tes3 — pure-stdlib binary parser/writer for TES3 (OpenMW) files.

Zero external dependencies; uses only the stdlib `struct` module.
"""
from .reader import read_file, read_bytes
from .writer import write_file, write_bytes

__all__ = ["read_file", "read_bytes", "write_file", "write_bytes"]
