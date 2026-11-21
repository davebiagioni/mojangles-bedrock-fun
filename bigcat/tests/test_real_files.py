"""Read-only checks on the real project files.

The committed pack/tool JSON is always present. The Mojang files (bigcat/vanilla/, bedrock-samples/)
are gitignored local copies, so tests that need them skip when they're absent (e.g. on CI).
Nothing here writes anything.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

import build_coats
import common
import gen_tame

BIGCAT = Path(__file__).resolve().parent.parent
VANILLA = BIGCAT / "vanilla"
JSON_FILES = sorted(p for d in ("big_cat_bp", "big_cat_rp", "tools") for p in (BIGCAT / d).rglob("*.json"))
needs_vanilla = pytest.mark.skipif(
    not (VANILLA / "cat.geo.json").is_file(), reason="bigcat/vanilla/ not present (run tools/fetch_vanilla.py)"
)


def test_found_pack_json():
    names = {p.relative_to(BIGCAT).as_posix() for p in JSON_FILES}
    assert {"big_cat_bp/manifest.json", "big_cat_rp/manifest.json", "tools/coats_config.json"} <= names


@pytest.mark.parametrize("path", JSON_FILES, ids=[p.relative_to(BIGCAT).as_posix() for p in JSON_FILES])
def test_committed_json_parses_without_bom(path):
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "a UTF-8 BOM can make Minecraft reject the file"
    json.loads(raw.decode("utf-8"))


@pytest.fixture
def real_root(monkeypatch):
    """Point the tools at the real project, for read-only use."""
    monkeypatch.setattr(common, "ROOT", BIGCAT)
    monkeypatch.setattr(common, "CONFIG_PATH", BIGCAT / "tools" / "coats_config.json")


def test_real_config_loads(real_root):
    cfg, paths = common.load_config()
    assert paths.bp == BIGCAT / "big_cat_bp"
    assert paths.bp_template.is_file()
    assert paths.client_template.is_file()
    assert set(cfg["pattern_weights"]) <= set(build_coats.PATTERNS)
    for pal in cfg["palettes"]:
        assert {pal["base"], pal["dark"], pal["light"]} <= set(cfg["colors"])
    for h in cfg["colors"].values():
        build_coats.hex_to_rgb(h)


def test_every_configured_pattern_has_a_palette(real_root):
    cfg, _ = common.load_config()
    for pattern in cfg["pattern_weights"]:
        assert any(pattern in p.get("patterns", [pattern]) for p in cfg["palettes"]), pattern


def test_manifests_agree():
    bp = json.loads((BIGCAT / "big_cat_bp" / "manifest.json").read_text(encoding="utf-8"))
    rp = json.loads((BIGCAT / "big_cat_rp" / "manifest.json").read_text(encoding="utf-8"))
    deps = {d.get("uuid"): d.get("version") for d in bp["dependencies"]}
    assert deps[rp["header"]["uuid"]] == rp["header"]["version"]
    assert bp["header"]["min_engine_version"] == rp["header"]["min_engine_version"]


@needs_vanilla
def test_real_cat_geometry_maps_cleanly(real_root, capsys):
    cfg, paths = common.load_config()
    geo = common.load_geometry(paths.geometry, cfg["entity"]["geometry"], cfg["anatomy"]["rest_pose"])
    assert "warning" not in capsys.readouterr().out
    build_coats.compute_anatomy(geo, cfg)
    assert len(geo.texels) > 500
    for bone in [cfg["anatomy"]["body_bone"], cfg["anatomy"]["head_bone"], *cfg["anatomy"]["leg_bones"]]:
        assert any(t.bone == bone for t in geo.surface)  # left/right legs share UVs, so use surface
    # body rest pose turns the upright body horizontal: its long axis ends up along z
    (_x0, y0, z0), (_x1, y1, z1) = geo.cube_bounds[(cfg["anatomy"]["body_bone"], 0)]
    assert z1 - z0 > y1 - y0


@needs_vanilla
def test_real_base_texture_protects_a_few_pixels(real_root):
    cfg, paths = common.load_config()
    geo = common.load_geometry(paths.geometry, cfg["entity"]["geometry"], cfg["anatomy"]["rest_pose"])
    with Image.open(paths.base_texture) as im:
        base = im.convert("RGBA")
    protect = build_coats.build_protect_mask(base, geo, cfg, paths)
    visible = [k for k in protect if base.getpixel(k)[3] > 0]
    assert 0 < len(visible) <= 0.1 * len(geo.texels)


@needs_vanilla
@pytest.mark.parametrize("name", sorted(gen_tame.MOBS))
def test_real_vanilla_mobs_patch(monkeypatch, name):
    monkeypatch.setattr(gen_tame, "VANILLA", VANILLA)
    if not (VANILLA / f"{name}.json").is_file():
        pytest.skip(f"vanilla/{name}.json not present")
    ent = gen_tame._patch(name, gen_tame.MOBS[name])["minecraft:entity"]
    assert gen_tame.TAMED_GROUP in ent["component_groups"]
    assert ent["components"]["minecraft:tameable"]["probability"] == 0.0
