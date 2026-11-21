"""gen_net.py (textures) and validate_net_trap."""

from __future__ import annotations

import json

import pytest
from PIL import Image

import common
import gen_net
import validate
from common import BuildError


def test_textures(raw_project):
    gen_net.generate_net_textures(verbose=False)
    with Image.open(raw_project.rp / (gen_net.BLOCK_TEXTURE + ".png")) as im:
        im = im.convert("RGBA")
        assert im.size == (16, 16)
        assert im.getpixel((1, 1)) == gen_net.KNOT  # ropes cross here
        assert im.getpixel((2, 2))[3] == 0  # holes are see-through
        assert im.getpixel((14, 14))[3] == 0
    with Image.open(raw_project.rp / (gen_net.ICON_TEXTURE + ".png")) as im:
        im = im.convert("RGBA")
        assert im.size == (16, 16)
        assert im.getpixel((0, 0))[3] == 0  # outside the bundle
        assert im.getpixel((8, 8)) == gen_net.KNOT


def _edit_json(path, fn):
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    common.write_json(path, data)


def no_custom_component(p):
    _edit_json(p.bp / "blocks" / "net_trap.json", lambda d: d["minecraft:block"]["components"].pop("mymod:net_trap"))


def no_collision(p):
    def fn(d):
        d["minecraft:block"]["components"]["minecraft:collision_box"] = False

    _edit_json(p.bp / "blocks" / "net_trap.json", fn)


def geometry_missing(p):
    (p.rp / "models" / "blocks" / "net_trap.geo.json").unlink()


def terrain_entry_missing(p):
    _edit_json(p.rp / "textures" / "terrain_texture.json", lambda d: d["texture_data"].pop("mymod_net_trap"))


def placer_not_replacing(p):
    def fn(d):
        d["minecraft:item"]["components"]["minecraft:block_placer"]["replace_block_item"] = False

    _edit_json(p.bp / "items" / "net_trap.json", fn)


def not_imported(p):
    f = p.bp / "scripts" / "main.js"
    f.write_text(f.read_text(encoding="utf-8").replace('import "./net_trap.js";', ""), encoding="utf-8")


def recipe_missing(p):
    (p.bp / "recipes" / "net_trap.json").unlink()


BREAKAGES = [
    (no_custom_component, "needs the custom component mymod:net_trap"),
    (no_collision, "needs a collision_box with some height"),
    (geometry_missing, "geometry geometry.mymod.net_trap not defined"),
    (terrain_entry_missing, "should map to textures/blocks/net_trap in terrain_texture.json"),
    (placer_not_replacing, "block_placer must place mymod:net_trap with replace_block_item"),
    (not_imported, "scripts/main.js: must import ./net_trap.js"),
    (recipe_missing, "recipes/net_trap.json: missing or does not make mymod:net_trap"),
]


@pytest.mark.parametrize(("breakage", "message"), BREAKAGES, ids=[b.__name__ for b, _ in BREAKAGES])
def test_validate_catches(project, breakage, message):
    breakage(project)
    with pytest.raises(BuildError, match="validation failed") as exc:
        validate.validate(verbose=False)
    assert message in str(exc.value)
