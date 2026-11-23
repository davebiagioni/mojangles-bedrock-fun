"""gen_mooshroom_drill.py (the Mooshroom Drill's chassis model and textures) and validate_mooshroom_drill."""

from __future__ import annotations

import json

import pytest
from PIL import Image

import gen_mooshroom_drill as gen
import validate
from common import BuildError


def test_uv_patches_fit_and_do_not_overlap():
    taken = set()
    for (size, _), (u, v) in gen.layout().items():
        pw, ph = gen._patch_size(size)
        assert u + pw <= gen.TEX_W
        assert v + ph <= gen.TEX_H
        cells = {(x, y) for x in range(u, u + pw) for y in range(v, v + ph)}
        assert not cells & taken
        taken |= cells


def test_spinning_bones_match_the_vanilla_mooshroom():
    """Our mushrooms turn with the cow only if our body/head bones share its pivots."""
    bones = {b["name"]: b for b in gen.geometry()["minecraft:geometry"][0]["bones"]}
    assert set(bones) == {"chassis", "body", "head"}
    assert bones["body"]["pivot"] == [0, 19, 2]
    assert bones["head"]["pivot"] == [0, 20, -8]
    assert len(bones["head"]["cubes"]) == 3  # one mushroom on the head
    assert len(bones["body"]["cubes"]) == 7  # two mushrooms and the axle


def test_chassis_stays_behind_the_cow():
    """The cow spins between z -15 and 10; the chassis must not cut into it."""
    for c in gen.CUBES:
        if c.bone == "chassis":
            assert c.origin[2] >= 9, c


def test_generate_writes_model_and_textures(raw_project):
    gen.generate_mooshroom_drill(verbose=False)
    geo = json.loads((raw_project.rp / gen.GEO_FILE).read_text(encoding="utf-8"))
    assert geo["minecraft:geometry"][0]["description"]["identifier"] == gen.GEOMETRY_ID
    with Image.open(raw_project.rp / (gen.ENTITY_TEXTURE + ".png")) as im:
        assert im.size == (gen.TEX_W, gen.TEX_H)
    with Image.open(raw_project.rp / (gen.ICON_TEXTURE + ".png")) as im:
        assert im.size == (16, 16)
        assert im.getbbox() is not None


def test_texture_is_deterministic():
    assert gen.texture().tobytes() == gen.texture().tobytes()


def not_imported(p):
    f = p.bp / "scripts" / "main.js"
    f.write_text(f.read_text(encoding="utf-8").replace('import "./drill.js";', ""), encoding="utf-8")


def _edit_entity(p, fn):
    f = p.bp / "entities" / "mooshroom_drill_vehicle.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    fn(d["minecraft:entity"])
    f.write_text(json.dumps(d), encoding="utf-8")


def can_be_hurt(p):
    _edit_entity(p, lambda e: e["components"].pop("minecraft:damage_sensor"))


def not_synced(p):
    _edit_entity(p, lambda e: e["description"]["properties"]["mymod:drilling"].pop("client_sync"))


def not_driveable(p):
    _edit_entity(p, lambda e: e["components"].pop("minecraft:input_ground_controlled"))


def no_spin(p):
    f = p.rp / "animations" / "mooshroom_drill.animation.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    d["animations"]["animation.mymod.mooshroom_drill.spin"]["bones"].pop("head")
    f.write_text(json.dumps(d), encoding="utf-8")


def old_pushable(p):
    _edit_entity(p, lambda e: e["components"].update({"minecraft:pushable": {"is_pushable": False}}))


def recipe_missing(p):
    (p.bp / "recipes" / "mooshroom_drill.json").unlink()


BREAKAGES = [
    (not_imported, "scripts/main.js: must import ./drill.js"),
    (can_be_hurt, "damage_sensor must block all damage"),
    (not_synced, "mymod:drilling must be a client_sync bool"),
    (not_driveable, "minecraft:input_ground_controlled missing"),
    (no_spin, "spin must turn the body and head bones"),
    (old_pushable, "minecraft:pushable no longer exists"),
    (recipe_missing, "recipes/mooshroom_drill.json: missing or does not make mymod:mooshroom_drill"),
]


@pytest.mark.parametrize(("breakage", "message"), BREAKAGES, ids=[b.__name__ for b, _ in BREAKAGES])
def test_validate_catches(project, breakage, message):
    breakage(project)
    with pytest.raises(BuildError, match="validation failed") as exc:
        validate.validate(verbose=False)
    assert message in str(exc.value)
