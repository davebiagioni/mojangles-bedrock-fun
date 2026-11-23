"""gen_morph.py (the Morph Wand costume) and validate_morph."""

from __future__ import annotations

import json

import pytest
from PIL import Image

import gen_morph
import validate
from common import BuildError


def test_one_entity_per_form_with_one_model():
    rcs = gen_morph.render_controllers()["render_controllers"]
    for f in gen_morph.FORMS:
        ident = gen_morph.MORPH_PREFIX + f.key
        assert gen_morph.behavior_entity(f)["minecraft:entity"]["description"]["identifier"] == ident
        ce = gen_morph.client_entity(f)["minecraft:client_entity"]["description"]
        assert ce["identifier"] == ident
        # one model per client entity, or the game logs "model already has a locator ..." errors
        assert ce["geometry"] == {"default": f.geometry}
        assert ce["textures"] == {"default": f.texture}
        assert ce["render_controllers"] == [gen_morph.RC.format(key=f.key)]
        assert rcs[gen_morph.RC.format(key=f.key)]["geometry"] == "Geometry.default"
        assert set(ce["animations"]) == set(f.animations)


def test_keys_unique():
    keys = [f.key for f in gen_morph.FORMS]
    assert len(keys) == len(set(keys))


def test_scale():
    for f in gen_morph.FORMS:
        scale = gen_morph.client_entity(f)["minecraft:client_entity"]["description"]["scripts"]["scale"]
        assert scale == ("2.0" if f.key == "big_cat" else "1.0")


def test_forms_js_lists_human_first():
    js = gen_morph.forms_js()
    rows = [json.loads(line.strip().rstrip(",")) for line in js.splitlines() if line.strip().startswith("{")]
    assert [r["key"] for r in rows] == ["human"] + [f.key for f in gen_morph.FORMS]
    assert [r["entity"] for r in rows] == [None] + [gen_morph.MORPH_PREFIX + f.key for f in gen_morph.FORMS]


def test_generate_writes_files(raw_project):
    gen_morph.generate_morph(verbose=False)
    for f in gen_morph.FORMS:
        assert (raw_project.bp / f"entities/morph_{f.key}.json").is_file()
        assert (raw_project.rp / f"entity/morph_{f.key}.entity.json").is_file()
    assert not (raw_project.bp / "entities/morph.json").exists()
    assert (raw_project.bp / "scripts/morph_forms.js").read_text(encoding="utf-8") == gen_morph.forms_js()
    with Image.open(raw_project.rp / (gen_morph.ICON_TEXTURE + ".png")) as im:
        assert im.size == (16, 16)
        assert im.convert("RGBA").getpixel((10, 0)) == gen_morph.TIP_COLORS["P"]


def not_imported(p):
    f = p.bp / "scripts" / "main.js"
    f.write_text(f.read_text(encoding="utf-8").replace('import "./morph.js";', ""), encoding="utf-8")


def stale_forms(p):
    f = p.bp / "scripts" / "morph_forms.js"
    f.write_text(f.read_text(encoding="utf-8").replace("a Pig", "a Cow"), encoding="utf-8")


def perk_missing(p):
    f = p.bp / "scripts" / "morph.js"
    f.write_text(f.read_text(encoding="utf-8").replace("  frog: { jump_boost: 2 },\n", ""), encoding="utf-8")


def recipe_missing(p):
    (p.bp / "recipes" / "morph_wand.json").unlink()


def old_id_in_script(p):
    f = p.bp / "scripts" / "blaster.js"
    f.write_text(f.read_text(encoding="utf-8") + '\nconst X = "mymod:morph";\n', encoding="utf-8")


def two_models(p):
    f = p.rp / "entity" / "morph_pig.entity.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    d["minecraft:client_entity"]["description"]["geometry"]["extra"] = "geometry.cat"
    f.write_text(json.dumps(d), encoding="utf-8")


BREAKAGES = [
    (old_id_in_script, "uses the old id mymod:morph"),
    (two_models, "entity/morph_pig.entity.json: exactly one geometry"),
    (not_imported, "scripts/main.js: must import ./morph.js"),
    (stale_forms, "missing or stale; run tools/gen_morph.py"),
    (perk_missing, "need an entry for frog"),
    (recipe_missing, "recipes/morph_wand.json: missing or does not make mymod:morph_wand"),
]


@pytest.mark.parametrize(("breakage", "message"), BREAKAGES, ids=[b.__name__ for b, _ in BREAKAGES])
def test_validate_catches(project, breakage, message):
    breakage(project)
    with pytest.raises(BuildError, match="validation failed") as exc:
        validate.validate(verbose=False)
    assert message in str(exc.value)
