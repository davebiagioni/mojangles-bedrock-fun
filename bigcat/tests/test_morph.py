"""gen_morph.py (the Morph Wand costume) and validate_morph."""

from __future__ import annotations

import json

import pytest
from PIL import Image

import gen_morph
import validate
from common import BuildError


def test_every_form_has_a_render_controller_and_condition():
    ce = gen_morph.client_entity()["minecraft:client_entity"]["description"]
    rcs = gen_morph.render_controllers()["render_controllers"]
    for n, f in enumerate(gen_morph.FORMS, start=1):
        name = gen_morph.RC.format(key=f.key)
        assert {name: gen_morph.form_condition(n)} in ce["render_controllers"]
        assert rcs[name]["geometry"] == f"Geometry.{f.key}"
        assert ce["geometry"][f.key] == f.geometry
        assert ce["textures"][f.key] == f.texture
        for short in f.animations:
            assert any(
                f"{f.key}_{short}" in e and e[f"{f.key}_{short}"].startswith(gen_morph.form_condition(n))
                for e in ce["scripts"]["animate"]
            )


def test_keys_unique_and_property_range():
    keys = [f.key for f in gen_morph.FORMS]
    assert len(keys) == len(set(keys))
    props = gen_morph.behavior_entity()["minecraft:entity"]["description"]["properties"]
    assert props[gen_morph.PROPERTY]["range"] == [0, len(gen_morph.FORMS)]


def test_scale_expression():
    scale = gen_morph.client_entity()["minecraft:client_entity"]["description"]["scripts"]["scale"]
    big = next(n for n, f in enumerate(gen_morph.FORMS, start=1) if f.key == "big_cat")
    assert f"{gen_morph.form_condition(big)} ? 2.0" in scale
    assert scale.endswith(": 1.0")


def test_forms_js_lists_human_first():
    js = gen_morph.forms_js()
    rows = [json.loads(line.strip().rstrip(",")) for line in js.splitlines() if line.strip().startswith("{")]
    assert [r["key"] for r in rows] == ["human"] + [f.key for f in gen_morph.FORMS]


def test_generate_writes_files(raw_project):
    gen_morph.generate_morph(verbose=False)
    assert (raw_project.bp / "entities/morph.json").is_file()
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


BREAKAGES = [
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
