"""Round-trip tests: parse → serialize → compare to original bytes."""
import sys
from pathlib import Path

# Make sure the repo root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from tes3.reader import read_bytes
from tes3.writer import write_bytes

EXAMPLE_SUITE = Path("/home/mike/Documents/Games/Morrowind_OpenMW_Linux/game/example-suite")

TEST_FILES = [
    EXAMPLE_SUITE / "the_hub/data/the_hub.omwaddon",
    EXAMPLE_SUITE / "game_template/data/template.omwgame",
    EXAMPLE_SUITE / "example_animated_creature/data/landracer.omwaddon",
    EXAMPLE_SUITE / "integration_tests/data/mwscript.omwaddon",
]


@pytest.mark.parametrize("path", [p for p in TEST_FILES if p.exists()])
def test_round_trip(path: Path) -> None:
    """Parse and re-serialize should produce bit-identical output."""
    original = path.read_bytes()
    records = read_bytes(original)
    result = write_bytes(records)
    assert result == original, (
        f"Round-trip failed for {path.name}: "
        f"original={len(original)} bytes, result={len(result)} bytes"
    )


@pytest.mark.parametrize("path", [p for p in TEST_FILES if p.exists()])
def test_parse_structure(path: Path) -> None:
    """Parsed output should have expected structure."""
    records = read_bytes(path.read_bytes())
    assert len(records) > 0
    assert records[0]["tag"] == "TES3"
    tes3 = records[0]
    hedr = next((sr for sr in tes3["subrecords"] if sr["tag"] == "HEDR"), None)
    assert hedr is not None
    assert "parsed" in hedr
    assert hedr["parsed"]["version"] == pytest.approx(1.3, abs=0.01)


def test_builder_creates_valid_tes3() -> None:
    """AddonBuilder should produce a parseable TES3 binary."""
    from addon import AddonBuilder

    addon = AddonBuilder(description="Test addon", masters=[("template.omwgame", 0)])
    addon.add_global("test_var", type="short", value=42)
    data = addon.to_bytes()

    records = read_bytes(data)
    assert records[0]["tag"] == "TES3"
    glob = next((r for r in records if r["tag"] == "GLOB"), None)
    assert glob is not None
    name_sr = next(sr for sr in glob["subrecords"] if sr["tag"] == "NAME")
    assert name_sr["parsed"] == "test_var"
