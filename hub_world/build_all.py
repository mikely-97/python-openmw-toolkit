"""hub_world/build_all.py — One-command build pipeline.

Steps
-----
1. Generate mesh .dae files (pure-Python COLLADA writer, no Blender needed).
   Skipped automatically when generate_meshes.py hasn't changed since the last
   run (stamp file: .mesh_gen_stamp).  Use --force / -f to regenerate anyway.
2. Build hub_world.omwaddon via build.py.

Usage
-----
    cd hub_world/
    python build_all.py              # incremental
    python build_all.py --force      # always regenerate meshes
    python build_all.py --meshes-only
    python build_all.py --addon-only

openmw.cfg setup (one-time)
---------------------------
Point openmw.cfg directly at this project directory so OpenMW picks up
changes immediately — no deploy step needed:

    data="/path/to/hub_world"
    data="/path/to/hub_world/data"
    content=hub_world.omwaddon
    content=hub_world.omwscripts
"""

import argparse
import configparser
import os
import subprocess
import sys

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
GENERATE_PY   = os.path.join(SCRIPT_DIR, "generate_meshes.py")
BUILD_PY      = os.path.join(SCRIPT_DIR, "build.py")
MESH_DIR      = os.path.join(SCRIPT_DIR, "data", "meshes", "hub_world")
STAMP_FILE    = os.path.join(SCRIPT_DIR, ".mesh_gen_stamp")
SETTINGS_FILE = os.path.join(SCRIPT_DIR, "settings.ini")
MIN_DAE_COUNT = 30   # sanity check: expect at least this many .dae files


def _needs_regen() -> bool:
    """True when meshes are missing or generate_meshes.py is newer than stamp."""
    if not os.path.isfile(STAMP_FILE):
        return True
    stamp_mtime  = os.path.getmtime(STAMP_FILE)
    gen_mtime    = os.path.getmtime(GENERATE_PY)
    if gen_mtime > stamp_mtime:
        return True
    if not os.path.isdir(MESH_DIR):
        return True
    dae_files = [f for f in os.listdir(MESH_DIR) if f.endswith(".dae")]
    if len(dae_files) < MIN_DAE_COUNT:
        return True
    return False


def _run(script: str, label: str):
    """Run a Python script; exit on failure."""
    print(f"\n[build_all] {label}…")
    result = subprocess.run(
        [sys.executable, script],
        capture_output=False,   # stream output directly
    )
    if result.returncode != 0:
        print(f"[build_all] ERROR: {label} failed (exit {result.returncode})")
        sys.exit(result.returncode)


def _read_settings() -> dict:
    """Read settings.ini; return dict of values (empty dict if file absent)."""
    ini = configparser.ConfigParser()
    ini.read(SETTINGS_FILE)
    return {
        "openmw_cfg": ini.get("openmw", "cfg", fallback=None),
    }


def configure_openmw():
    """Patch openmw.cfg to add this project's data= entries (one-time setup)."""
    settings = _read_settings()
    cfg_path = settings.get("openmw_cfg")
    if not cfg_path:
        print(f"[build_all] Edit {SETTINGS_FILE} and set openmw.cfg = <path>")
        sys.exit(1)
    cfg_path = os.path.expanduser(cfg_path)
    if not os.path.isfile(cfg_path):
        print(f"[build_all] openmw.cfg not found: {cfg_path}")
        sys.exit(1)

    data1 = SCRIPT_DIR                         # hub_world/
    data2 = os.path.join(SCRIPT_DIR, "data")   # hub_world/data/

    with open(cfg_path) as f:
        lines = f.readlines()

    # Already configured?
    for line in lines:
        if line.strip() == f'data="{data1}"':
            print("[build_all] openmw.cfg already contains this project's data= entries.")
            return

    # Insert before the first content= line (or append at end)
    insert_idx = len(lines)
    for i, line in enumerate(lines):
        if line.strip().startswith("content="):
            insert_idx = i
            break

    lines[insert_idx:insert_idx] = [
        f'data="{data1}"\n',
        f'data="{data2}"\n',
    ]

    with open(cfg_path, "w") as f:
        f.writelines(lines)

    print(f"[build_all] Patched {cfg_path}")
    print(f'  + data="{data1}"')
    print(f'  + data="{data2}"')


def generate_meshes():
    _run(GENERATE_PY, "Generating meshes")
    with open(STAMP_FILE, "w") as f:
        f.write("ok\n")


def build_addon():
    _run(BUILD_PY, "Building addon")


def main():
    parser = argparse.ArgumentParser(description="Hub World build pipeline")
    parser.add_argument("--force",       "-f",  action="store_true",
                        help="Force mesh regeneration even if up-to-date")
    parser.add_argument("--meshes-only", action="store_true",
                        help="Only regenerate meshes, skip addon build")
    parser.add_argument("--addon-only",  action="store_true",
                        help="Only build addon, skip mesh generation")
    parser.add_argument("--configure",   action="store_true",
                        help="Patch openmw.cfg with this project's data= paths "
                             "(one-time setup; reads cfg path from settings.ini)")
    args = parser.parse_args()

    if args.configure:
        configure_openmw()
        return

    if not args.addon_only:
        if args.force or _needs_regen():
            generate_meshes()
        else:
            dae_count = len([f for f in os.listdir(MESH_DIR) if f.endswith(".dae")])
            print(f"[build_all] Meshes up-to-date ({dae_count} .dae files). "
                  "Pass --force to regenerate.")

    if not args.meshes_only:
        build_addon()

    print("\n[build_all] All done.")


if __name__ == "__main__":
    main()
