"""gen_json.py: entity / client entity / render controller / test functions from the templates."""

from __future__ import annotations

import re

import pytest

import common
import gen_evolution
import gen_json
from common import BuildError

PROP = "mymod:coat"


@pytest.mark.parametrize("n", [1, 4, 200])
def test_coat_events(n):
    ev = gen_json.coat_events(PROP, n)
    assert len(ev) == n + 3
    assert ev["mymod:randomize_coat"] == {"set_property": {PROP: f"math.random_integer(0, {n - 1})"}}
    assert ev["mymod:next_coat"]["set_property"][PROP] == f"math.mod(query.property('{PROP}') + 1, {n})"
    assert ev["mymod:prev_coat"]["set_property"][PROP] == f"math.mod(query.property('{PROP}') + {n - 1}, {n})"
    assert [ev[f"mymod:set_coat_{i}"]["set_property"][PROP] for i in range(n)] == list(range(n))


def test_generate_json_outputs(raw_project, capsys):
    gen_json.generate_json()
    n, bp, rp = raw_project.cfg["coat_count"], raw_project.bp, raw_project.rp
    assert "4 coats" in capsys.readouterr().out

    e = common.load_json(bp / gen_json.BP_ENTITY)["minecraft:entity"]
    prop = e["description"]["properties"][PROP]
    assert prop == {
        "type": "int",
        "range": [0, n - 1],
        "default": f"math.random_integer(0, {n - 1})",
        "client_sync": True,
    }
    assert "mymod:set_coat_3" in e["events"]
    assert "mymod:set_coat_4" not in e["events"]
    assert "minecraft:cat_adult" in e["component_groups"]  # template content kept
    assert common.GENERATED_KEY not in common.load_json(bp / gen_json.BP_ENTITY)

    desc = common.load_json(rp / gen_json.RP_ENTITY)["minecraft:client_entity"]["description"]
    assert desc["textures"]["coat_002"] == "textures/entity/coats/coat_002"
    assert desc["textures"]["coat_002_tame"] == "textures/entity/coats/coat_002_tame"
    assert len(desc["textures"]) == 2 * n + 1  # + the stage-8 wings
    assert desc["textures"]["wings"] == gen_evolution.WING_TEXTURE
    # plain strings only: a 1.8.0 client entity rejects {controller: condition} entries
    assert desc["render_controllers"] == ["controller.render.big_cat", gen_json.WING_RC]

    rc = common.load_json(rp / gen_json.RP_RC)["render_controllers"]["controller.render.big_cat"]
    arrays = rc["arrays"]["textures"]
    assert arrays["Array.coats"] == [f"Texture.coat_{i:03d}" for i in range(n)]
    assert arrays["Array.tame"] == [f"Texture.coat_{i:03d}_tame" for i in range(n)]
    assert rc["textures"] == [gen_json.RC_TEXTURE_EXPR.format(prop=PROP)]

    md = (raw_project.root / "GENERATED_FILES.md").read_text(encoding="utf-8")
    assert "coat_003.png" in md
    assert "big_cat_bp/entities/big_cat.json" in md


def test_generate_json_is_stable(raw_project):
    gen_json.generate_json(verbose=False)
    files = [raw_project.bp / gen_json.BP_ENTITY, raw_project.rp / gen_json.RP_ENTITY, raw_project.rp / gen_json.RP_RC]
    first = [f.read_bytes() for f in files]
    gen_json.generate_json(verbose=False)
    assert [f.read_bytes() for f in files] == first


def test_functions(raw_project):
    gen_json.generate_json(verbose=False)
    fdir = raw_project.bp / "functions"
    test_cats = (fdir / "test_cats.mcfunction").read_text(encoding="utf-8")
    assert test_cats.startswith("# GENERATED")
    assert test_cats.count("summon mymod:big_cat ") == 4  # 2 x 2 grid
    assert "summon mymod:big_cat ~3 ~ ~3\n" in test_cats
    assert "kill @e[type=mymod:big_cat]" in (fdir / "clear_cats.mcfunction").read_text(encoding="utf-8")
    pages = sorted(p.name for p in (fdir / "coats").iterdir())
    assert pages == ["page_01.mcfunction", "page_02.mcfunction"]  # 4 coats, 3 per page
    page2 = (fdir / "coats" / "page_02.mcfunction").read_text(encoding="utf-8")
    assert 'name="Coat 003"] mymod:set_coat_3' in page2
    assert "Coat 002" not in page2


def test_functions_shrink_removes_stale_pages(raw_project, synth):
    (raw_project.bp / "functions" / "coats").mkdir(parents=True, exist_ok=True)
    (raw_project.bp / "functions" / "coats" / "page_09.mcfunction").write_text("old", encoding="utf-8")
    common.write_json(common.CONFIG_PATH, synth.small_config(coat_count=2))
    gen_json.generate_json(verbose=False)
    assert sorted(p.name for p in (raw_project.bp / "functions" / "coats").iterdir()) == ["page_01.mcfunction"]


def test_functions_only_use_generated_events(raw_project):
    gen_json.generate_json(verbose=False)
    events = set(common.load_json(raw_project.bp / gen_json.BP_ENTITY)["minecraft:entity"]["events"])
    for f in (raw_project.bp / "functions").rglob("*.mcfunction"):
        for ev in re.findall(r"\b(mymod:[a-z_0-9]+)\s*$", f.read_text(encoding="utf-8"), re.MULTILINE):
            assert ev in events


# ------------------------------------------------------------------ template mistakes


def _bp_template(p):
    return p.paths.bp_template


def _ce_template(p):
    return p.paths.client_template


def _edit(path, fn):
    data = common.load_json(path)
    fn(data)
    common.write_json(path, data)


TEMPLATE_ERRORS = [
    (
        _bp_template,
        lambda d: d["minecraft:entity"]["description"].update(identifier="x:y"),
        "expected minecraft:entity 'mymod:big_cat'",
    ),
    (_bp_template, lambda d: d.pop("minecraft:entity"), "expected minecraft:entity"),
    (
        _bp_template,
        lambda d: d["minecraft:entity"]["description"].setdefault("properties", {}).update({PROP: {}}),
        "remove 'mymod:coat' from the template",
    ),
    (
        _bp_template,
        lambda d: d["minecraft:entity"].setdefault("events", {}).update({"mymod:set_coat_0": {}}),
        r"events \['mymod:set_coat_0'\] are generated",
    ),
    (
        _ce_template,
        lambda d: d["minecraft:client_entity"]["description"].update(identifier="x:y"),
        "expected minecraft:client_entity 'mymod:big_cat'",
    ),
    (
        _ce_template,
        lambda d: d["minecraft:client_entity"]["description"].update(textures={"default": "a"}),
        "remove 'textures' from the template",
    ),
    (
        _ce_template,
        lambda d: d["minecraft:client_entity"]["description"].update(render_controllers=["controller.render.other"]),
        r'render_controllers must be \["controller.render.big_cat"\]',
    ),
]


@pytest.mark.parametrize(
    ("which", "edit", "message"),
    TEMPLATE_ERRORS,
    ids=["bp-id", "bp-no-entity", "bp-has-prop", "bp-event-clash", "ce-id", "ce-textures", "ce-rc"],
)
def test_template_errors(raw_project, which, edit, message):
    _edit(which(raw_project), edit)
    with pytest.raises(BuildError, match=message):
        gen_json.generate_json(verbose=False)


def test_generated_marker_is_dropped_from_templates(raw_project):
    _edit(raw_project.paths.bp_template, lambda d: d.update({common.GENERATED_KEY: "note"}))
    _edit(raw_project.paths.client_template, lambda d: d.update({common.GENERATED_KEY: "note"}))
    gen_json.generate_json(verbose=False)
    assert common.GENERATED_KEY not in common.load_json(raw_project.bp / gen_json.BP_ENTITY)
    assert common.GENERATED_KEY not in common.load_json(raw_project.rp / gen_json.RP_ENTITY)
