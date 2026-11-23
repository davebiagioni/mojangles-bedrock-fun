"""gen_portal.py (the Portal Pad block and textures) and validate_portal."""

from __future__ import annotations

import json

import pytest
from PIL import Image

import gen_portal
import validate
from common import BuildError


def test_purple_is_the_default_colour():
    """Block states default to their first value: new pads must all be purple so any two link."""
    assert gen_portal.COLORS[0].key == "purple"
    states = gen_portal.block()["minecraft:block"]["description"]["states"][gen_portal.STATE]
    assert states == {"values": {"min": 0, "max": len(gen_portal.COLORS) - 1}}


def test_one_permutation_per_colour():
    perms = gen_portal.block()["minecraft:block"]["permutations"]
    assert len(perms) == len(gen_portal.COLORS)
    for i, (perm, c) in enumerate(zip(perms, gen_portal.COLORS, strict=True)):
        assert perm["condition"] == f"q.block_state('mymod:color') == {i}"
        assert perm["components"]["minecraft:material_instances"]["*"]["texture"] == gen_portal.atlas_key(c)


def test_every_dye_picks_one_colour():
    dyes = [d for c in gen_portal.COLORS for d in c.dyes]
    assert len(dyes) == len(set(dyes))
    assert all(d.startswith("minecraft:") for d in dyes)
    assert len(gen_portal.COLORS) == 16


def test_colors_js_matches():
    js = gen_portal.colors_js()
    rows = json.loads("[" + js.split("export const COLORS = [")[1].rsplit("];", 1)[0].rstrip().rstrip(",") + "]")
    assert [r["key"] for r in rows] == [c.key for c in gen_portal.COLORS]
    assert all(0 <= v <= 1 for r in rows for v in r["rgb"])


def test_textures_differ_by_colour():
    images = [gen_portal.pad_texture(c).tobytes() for c in gen_portal.COLORS]
    assert len(set(images)) == len(images)
    icon = gen_portal.icon()
    assert icon.size == (16, 16)
    assert icon.getpixel((0, 0))[3] == 0  # transparent background


def test_generate_writes_everything(raw_project):
    gen_portal.generate_portal(verbose=False)
    assert json.loads((raw_project.bp / "blocks/portal_pad.json").read_text(encoding="utf-8")) == gen_portal.block()
    assert (raw_project.bp / "scripts/portal_colors.js").read_text(encoding="utf-8") == gen_portal.colors_js()
    for tex in gen_portal.ALL_TEXTURES:
        with Image.open(raw_project.rp / (tex + ".png")) as im:
            assert im.size == (16, 16)


def not_imported(p):
    f = p.bp / "scripts" / "main.js"
    f.write_text(f.read_text(encoding="utf-8").replace('import "./portal.js";', ""), encoding="utf-8")


def stale_block(p):
    f = p.bp / "blocks" / "portal_pad.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    d["minecraft:block"]["permutations"].pop()
    f.write_text(json.dumps(d), encoding="utf-8")


def stale_colors(p):
    f = p.bp / "scripts" / "portal_colors.js"
    f.write_text(f.read_text(encoding="utf-8").replace("Purple", "Violet"), encoding="utf-8")


def atlas_missing(p):
    f = p.rp / "textures" / "terrain_texture.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    del d["texture_data"]["mymod_portal_pad_red"]
    f.write_text(json.dumps(d), encoding="utf-8")


def recipe_missing(p):
    (p.bp / "recipes" / "portal_pad.json").unlink()


BREAKAGES = [
    (not_imported, "scripts/main.js: must import ./portal.js"),
    (stale_block, "blocks/portal_pad.json: missing or stale"),
    (stale_colors, "portal_colors.js: missing or stale"),
    (atlas_missing, "mymod_portal_pad_red should map to textures/blocks/portal_pad_red"),
    (recipe_missing, "recipes/portal_pad.json: missing or does not make mymod:portal_pad"),
]


@pytest.mark.parametrize(("breakage", "message"), BREAKAGES, ids=[b.__name__ for b, _ in BREAKAGES])
def test_validate_catches(project, breakage, message):
    breakage(project)
    with pytest.raises(BuildError, match="validation failed") as exc:
        validate.validate(verbose=False)
    assert message in str(exc.value)
