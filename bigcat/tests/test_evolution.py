"""gen_evolution.py (stages, entity groups/events, textures) and validate_evolution."""

from __future__ import annotations

import copy
import json

import pytest
from PIL import Image

import common
import gen_evolution as evo
import gen_json
import validate
from common import BuildError


def _entity() -> dict:
    return {"description": {"identifier": "mymod:big_cat"}, "component_groups": {}, "events": {}}


def test_eight_stages_get_steadily_stronger():
    assert evo.MAX_STAGE == 8 == evo.WING_STAGE
    for field in (2, 3, 4, 5):  # health, attack, speed, knockback
        values = [s[field] for s in evo.STAGES]
        assert values == sorted(values), field
        assert len(set(values)) == len(values), field
    # stronger than an unevolved tamed cat (20 health, 4 attack, 0.3 speed) from stage 1 on
    assert evo.STAGES[0][2] > 20
    assert evo.STAGES[0][3] > 4
    assert evo.STAGES[0][4] > 0.3
    assert len({s[1] for s in evo.STAGES}) == 8  # a different particle per stage


def test_add_evolution():
    e = _entity()
    evo.add_evolution(e)
    assert e["description"]["properties"][evo.PROPERTY] == {
        "type": "int",
        "range": [0, 8],
        "default": 0,
        "client_sync": True,
    }
    g8 = e["component_groups"]["mymod:evolution_8"]
    assert g8["minecraft:health"] == {"value": 100, "max": 100}
    assert "minecraft:fire_immune" in g8
    assert "minecraft:fire_immune" not in e["component_groups"]["mymod:evolution_1"]

    ev3 = e["events"]["mymod:evolve_3"]["sequence"]
    removed = ev3[0]["remove"]["component_groups"]
    assert "mymod:evolution_3" not in removed
    assert len(removed) == 7
    assert ev3[1] == {"add": {"component_groups": ["mymod:evolution_3"]}, "set_property": {evo.PROPERTY: 3}}
    reset = e["events"]["mymod:evolve_0"]["sequence"]
    assert len(reset[0]["remove"]["component_groups"]) == 8
    assert reset[0]["set_property"] == {evo.PROPERTY: 0}


@pytest.mark.parametrize(
    "clash",
    [
        lambda e: e["description"].setdefault("properties", {}).update({evo.PROPERTY: {}}),
        lambda e: e["component_groups"].update({"mymod:evolution_2": {}}),
        lambda e: e["events"].update({"mymod:evolve_5": {}}),
    ],
)
def test_add_evolution_refuses_hand_written_copies(clash):
    e = _entity()
    clash(e)
    before = copy.deepcopy(e)
    with pytest.raises(BuildError, match=r"gen_evolution|the build adds it"):
        evo.add_evolution(e)
    assert e == before


def test_textures(raw_project):
    evo.generate_evolution_textures(verbose=False)
    with Image.open(raw_project.rp / (evo.STONE_TEXTURE + ".png")) as im:
        assert im.size == (16, 16)
        assert im.convert("RGBA").getpixel((0, 0))[3] == 0  # transparent background
    with Image.open(raw_project.rp / (evo.WING_TEXTURE + ".png")) as im:
        im = im.convert("RGBA")
        assert im.size == (32, 32)
        # both wing parts (inner 7x6 at 0,0 and tip 7x8 at 0,8) are drawn, with a gold leading edge
        assert im.getpixel((0, 0)) == evo.GOLD
        assert im.getpixel((0, 8)) == evo.GOLD
        assert im.getpixel((20, 20))[3] == 0


def test_generated_entity_has_the_stages(raw_project):
    gen_json.generate_json(verbose=False)
    e = common.load_json(raw_project.bp / gen_json.BP_ENTITY)["minecraft:entity"]
    assert evo.PROPERTY in e["description"]["properties"]
    assert "mymod:coat" in e["description"]["properties"]
    assert all(f"mymod:evolution_{n}" in e["component_groups"] for n in range(1, 9))
    assert "minecraft:cat_tame" in e["component_groups"]  # template groups kept


# --------------------------------------------------------------------------- validate_evolution


def _edit_json(path, fn):
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    common.write_json(path, data)


def _edit_text(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


def script_stage_renamed(p):
    _edit_text(p.bp / "scripts" / "evolution.js", '{ name: "Frost"', '{ name: "Chilly"')


def script_particle_changed(p):
    _edit_text(p.bp / "scripts" / "evolution.js", "minecraft:endrod", "minecraft:heart_particle")


def not_imported(p):
    _edit_text(p.bp / "scripts" / "main.js", 'import "./evolution.js";', "")


def wing_geometry_missing(p):
    (p.rp / "models" / "entity" / "big_cat_wings.geo.json").unlink()


def wing_animation_missing(p):
    (p.rp / "animations" / "big_cat_wings.animation.json").unlink()


def stage_group_dropped(p):
    _edit_json(
        p.bp / "entities" / "big_cat.json",
        lambda d: d["minecraft:entity"]["component_groups"].pop("mymod:evolution_4"),
    )


def stone_name_missing(p):
    f = p.rp / "texts" / "en_US.lang"
    text = f.read_text(encoding="utf-8")
    f.write_text("\n".join(ln for ln in text.splitlines() if "evolution_stone" not in ln), encoding="utf-8")


BREAKAGES = [
    (script_stage_renamed, "do not match tools/gen_evolution.py"),
    (script_particle_changed, "do not match tools/gen_evolution.py"),
    (not_imported, "scripts/main.js: must import ./evolution.js"),
    (wing_geometry_missing, "geometry 'wings' (geometry.mymod.big_cat_wings) not defined"),
    (wing_animation_missing, "animation 'wings' (animation.big_cat.wings) not in"),
    (stage_group_dropped, "component group mymod:evolution_4 missing"),
    (stone_name_missing, "missing item.mymod:evolution_stone.name"),
]


@pytest.mark.parametrize(("breakage", "message"), BREAKAGES, ids=[b.__name__ for b, _ in BREAKAGES])
def test_validate_catches(project, breakage, message):
    breakage(project)
    with pytest.raises(BuildError, match="validation failed") as exc:
        validate.validate(verbose=False)
    assert message in str(exc.value)
