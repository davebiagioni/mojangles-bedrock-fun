"""gen_blaster.py (icon) and validate_blaster."""

from __future__ import annotations

import json

import pytest
from PIL import Image

import common
import gen_blaster
import validate
from common import BuildError


def test_icon(raw_project):
    gen_blaster.generate_blaster_texture(verbose=False)
    with Image.open(raw_project.rp / (gen_blaster.ICON_TEXTURE + ".png")) as im:
        im = im.convert("RGBA")
        assert im.size == (16, 16)
        assert im.getpixel((0, 0))[3] == 0
        assert im.getpixel((13, 2)) == gen_blaster.COLORS["C"]  # glowing barrel
    with Image.open(raw_project.rp / (gen_blaster.FLAME_TEXTURE + ".png")) as im:
        assert im.convert("RGBA").getpixel((13, 2)) == gen_blaster.FLAME_COLORS["C"]  # orange barrel
    for tex, colors in (
        (gen_blaster.WATER_TEXTURE, gen_blaster.WATER_COLORS),
        (gen_blaster.ICE_TEXTURE, gen_blaster.ICE_COLORS),
        (gen_blaster.BARF_TEXTURE, gen_blaster.BARF_COLORS),
    ):
        with Image.open(raw_project.rp / (tex + ".png")) as im:
            assert im.convert("RGBA").getpixel((13, 2)) == colors["C"]


def test_art_rows_are_16_wide_and_use_known_colors():
    assert len(gen_blaster.ART) == 16
    for row in gen_blaster.ART:
        assert len(row) == 16
        assert set(row) <= set(gen_blaster.COLORS) | {"."}


def _edit_json(path, fn):
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    common.write_json(path, data)


def not_imported(p):
    f = p.bp / "scripts" / "main.js"
    f.write_text(f.read_text(encoding="utf-8").replace('import "./blaster.js";', ""), encoding="utf-8")


def no_hold(p):
    _edit_json(
        p.bp / "items" / "laser_blaster.json",
        lambda d: d["minecraft:item"]["components"].pop("minecraft:use_modifiers"),
    )


def particle_missing(p):
    (p.rp / "particles" / "laser_beam.particle.json").unlink()


def recipe_missing(p):
    (p.bp / "recipes" / "laser_blaster.json").unlink()


def flame_no_hold(p):
    _edit_json(
        p.bp / "items" / "flame_blaster.json",
        lambda d: d["minecraft:item"]["components"].pop("minecraft:use_modifiers"),
    )


def glow_missing(p):
    (p.rp / "particles" / "laser_glow.particle.json").unlink()


def fire_beam_missing(p):
    (p.rp / "particles" / "fire_beam.particle.json").unlink()


def ice_recipe_missing(p):
    (p.bp / "recipes" / "ice_blaster.json").unlink()


def water_beam_missing(p):
    (p.rp / "particles" / "water_beam.particle.json").unlink()


def barf_recipe_missing(p):
    (p.bp / "recipes" / "barf_blaster.json").unlink()


def barf_spew_missing(p):
    (p.rp / "particles" / "barf_spew.particle.json").unlink()


def barf_not_named(p):
    f = p.rp / "texts" / "en_US.lang"
    f.write_text(f.read_text(encoding="utf-8").replace("item.mymod:barf_blaster.name=", "x="), encoding="utf-8")


def block_without_geometry(p):
    _edit_json(
        p.bp / "blocks" / "net_trap.json", lambda d: d["minecraft:block"]["components"].pop("minecraft:geometry")
    )


BREAKAGES = [
    (block_without_geometry, "blocks/net_trap.json: has material_instances but no minecraft:geometry"),
    (not_imported, "scripts/main.js: must import ./blaster.js"),
    (no_hold, "needs minecraft:use_modifiers with a long use_duration"),
    (particle_missing, "particles/laser_beam.particle.json: missing or does not define mymod:laser_beam"),
    (recipe_missing, "recipes/laser_blaster.json: missing or does not make mymod:laser_blaster"),
    (flame_no_hold, "flame_blaster.json: needs minecraft:use_modifiers with a long use_duration"),
    (glow_missing, "particles/laser_glow.particle.json: missing or does not define mymod:laser_glow"),
    (fire_beam_missing, "particles/fire_beam.particle.json: missing or does not define mymod:fire_beam"),
    (ice_recipe_missing, "recipes/ice_blaster.json: missing or does not make mymod:ice_blaster"),
    (water_beam_missing, "particles/water_beam.particle.json: missing or does not define mymod:water_beam"),
    (barf_recipe_missing, "recipes/barf_blaster.json: missing or does not make mymod:barf_blaster"),
    (barf_spew_missing, "particles/barf_spew.particle.json: missing or does not define mymod:barf_spew"),
    (barf_not_named, "texts/en_US.lang: missing item.mymod:barf_blaster.name=..."),
]


@pytest.mark.parametrize(("breakage", "message"), BREAKAGES, ids=[b.__name__ for b, _ in BREAKAGES])
def test_validate_catches(project, breakage, message):
    breakage(project)
    with pytest.raises(BuildError, match="validation failed") as exc:
        validate.validate(verbose=False)
    assert message in str(exc.value)
