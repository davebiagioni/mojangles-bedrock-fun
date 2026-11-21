"""Read-only checks on the committed gear_bp / gear_rp files (no bedrock-samples needed)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from PIL import Image

GEAR = Path(__file__).resolve().parent.parent
PACKS = (GEAR / "gear_bp", GEAR / "gear_rp")
JSON_FILES = sorted(p for pack in PACKS for p in pack.rglob("*.json")) + sorted((GEAR / "tools").glob("*.json"))


def _id(p: Path) -> str:
    return p.relative_to(GEAR).as_posix()


def _load(name: str):
    return json.loads((GEAR / name).read_text(encoding="utf-8"))


def test_found_pack_files():
    assert len(JSON_FILES) > 10


@pytest.mark.parametrize("path", JSON_FILES, ids=_id)
def test_json_parses_strictly_without_bom(path):
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "a BOM breaks Bedrock"
    json.loads(raw.decode("utf-8"))  # strict: no comments, no trailing commas


def test_manifests_link_up():
    bp, rp = _load("gear_bp/manifest.json"), _load("gear_rp/manifest.json")
    ids = [m["header"]["uuid"] for m in (bp, rp)] + [mod["uuid"] for m in (bp, rp) for mod in m["modules"]]
    for u in ids:
        uuid.UUID(u)
    assert len(set(ids)) == len(ids), "UUIDs must be unique"
    assert bp["header"]["version"] == rp["header"]["version"]
    assert all(mod["version"] == bp["header"]["version"] for m in (bp, rp) for mod in m["modules"])
    dep = {d["uuid"]: d["version"] for d in bp["dependencies"] if "uuid" in d}
    assert dep == {rp["header"]["uuid"]: rp["header"]["version"]}
    script = next(mod for mod in bp["modules"] if mod["type"] == "script")
    assert (GEAR / "gear_bp" / script["entry"]).is_file()


def test_item_texture_entries_point_at_files():
    data = _load("gear_rp/textures/item_texture.json")["texture_data"]
    assert data
    for key, v in data.items():
        assert key.startswith("gear_")
        assert (GEAR / "gear_rp" / (v["textures"] + ".png")).is_file(), key


@pytest.mark.parametrize("path", sorted((GEAR / "gear_rp" / "textures").rglob("*.png")), ids=_id)
def test_textures_are_rgba_with_expected_size(path):
    with Image.open(path) as im:
        assert im.mode == "RGBA"
        assert im.size == ((64, 32) if "armor" in path.parts else (16, 16))
