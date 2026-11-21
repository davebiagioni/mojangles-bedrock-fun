"""validate.py on a synthetic add-on + fake bedrock-samples (passing and failing cases), and on the real packs."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from PIL import Image

import common
import validate
from common import BuildError


def test_synthetic_project_validates(project, capsys):
    validate.validate()
    out = capsys.readouterr().out
    assert "OK:" in out
    assert "2 items schema-valid (server/item/1.26.50)" in out
    assert "2 recipes" in out
    assert "4 attachables" in out


def test_quiet_mode_prints_nothing(project, capsys):
    validate.validate(verbose=False)
    assert capsys.readouterr().out == ""


def test_missing_samples(project, monkeypatch, tmp_path):
    monkeypatch.setenv("MC_SAMPLES", str(tmp_path / "nowhere"))
    with pytest.raises(BuildError, match="bedrock-samples not found"):
        validate.validate()


@pytest.mark.parametrize(
    ("v", "expected"),
    [("1.26.50", (1, 26, 50)), ("1.20.10", (1, 20, 10)), ("v1.2.3.4", (1, 2, 3)), ("0", (0,)), ("", ())],
)
def test_ver(v, expected):
    assert validate._ver(v) == expected


# --------------------------------------------------------------------------- failing cases
# Each mutation breaks one thing in a valid synthetic project; validate must name it.


def read_json_file(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _edit_json(path: Path, fn) -> None:
    data = read_json_file(path)
    fn(data)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _helmet_item(p):
    return p.bp / "items" / "test_helmet.json"


def bom(p):
    f = _helmet_item(p)
    f.write_bytes(b"\xef\xbb\xbf" + f.read_bytes())


def broken_json(p):
    (p.rp / "attachables" / "test_boots.json").write_text("{", encoding="utf-8")


def extra_top_key(p):
    _edit_json(_helmet_item(p), lambda d: d.update(extra=1))


def bad_uuid(p):
    _edit_json(p.rp / "manifest.json", lambda d: d["modules"][0].update(uuid="not-a-uuid"))


def duplicate_uuid(p):
    bp = read_json_file(p.bp / "manifest.json")
    _edit_json(p.rp / "manifest.json", lambda d: d["modules"][0].update(uuid=bp["header"]["uuid"]))


def dep_version(p):
    _edit_json(p.bp / "manifest.json", lambda d: d["dependencies"][0].update(version=[9, 9, 9]))


def no_rp_dependency(p):
    _edit_json(p.bp / "manifest.json", lambda d: d["dependencies"].pop(0))


def wrong_engine(p):
    _edit_json(p.rp / "manifest.json", lambda d: d["header"].update(min_engine_version=[1, 20, 0]))


def string_version(p):
    _edit_json(p.bp / "manifest.json", lambda d: d["header"].update(version="1.0.1"))


def missing_script_entry(p):
    (p.bp / "scripts" / "main.js").unlink()


def unknown_component(p):
    _edit_json(_helmet_item(p), lambda d: d["minecraft:item"]["components"].update({"minecraft:bogus": {}}))


def schema_violation(p):
    _edit_json(_helmet_item(p), lambda d: d["minecraft:item"]["components"].update({"minecraft:max_stack_size": 99}))


def wrong_slot(p):
    _edit_json(
        _helmet_item(p),
        lambda d: d["minecraft:item"]["components"]["minecraft:wearable"].update(slot="slot.armor.chest"),
    )


def wrong_namespace(p):
    _edit_json(_helmet_item(p), lambda d: d["minecraft:item"]["description"].update(identifier="other:test_helmet"))


def missing_item(p):
    _helmet_item(p).unlink()


def unknown_icon(p):
    _edit_json(
        _helmet_item(p),
        lambda d: d["minecraft:item"]["components"]["minecraft:icon"]["textures"].update(default="gear_nope"),
    )


def recipe_symbol(p):
    _edit_json(
        p.bp / "recipes" / "test_helmet.json", lambda d: d["minecraft:recipe_shaped"].update(pattern=["SXS", "S S"])
    )


def recipe_shape(p):
    _edit_json(
        p.bp / "recipes" / "test_helmet.json", lambda d: d["minecraft:recipe_shaped"].update(pattern=["SIS", "S"])
    )


def recipe_unknown_item(p):
    _edit_json(
        p.bp / "recipes" / "test_helmet.json",
        lambda d: d["minecraft:recipe_shaped"]["key"].update(I={"item": "minecraft:unobtainium"}),
    )


def duplicate_recipe(p):
    helmet = read_json_file(p.bp / "recipes" / "test_helmet.json")["minecraft:recipe_shaped"]
    _edit_json(
        p.bp / "recipes" / "test_boots.json",
        lambda d: d["minecraft:recipe_shaped"].update(pattern=helmet["pattern"], key=helmet["key"]),
    )


def missing_recipe(p):
    (p.bp / "recipes" / "test_boots.json").unlink()


def missing_player_attachable(p):
    (p.rp / "attachables" / "test_boots.player.json").unlink()


def bad_geometry(p):
    _edit_json(
        p.rp / "attachables" / "test_boots.json",
        lambda d: d["minecraft:attachable"]["description"].update(geometry={"default": "geometry.humanoid.armor.hat"}),
    )


def bad_animation(p):
    _edit_json(
        p.rp / "attachables" / "test_helmet.player.json",
        lambda d: d["minecraft:attachable"]["description"].update(animations={"offset": "animation.nope"}),
    )


def bad_material(p):
    _edit_json(
        p.rp / "attachables" / "test_helmet.json",
        lambda d: d["minecraft:attachable"]["description"]["materials"].update(default="entity_alphatest"),
    )


def missing_layer_texture(p):
    (p.rp / "textures" / "gear" / "armor" / "test_1.png").unlink()


def unreferenced_texture(p):
    Image.new("RGBA", (16, 16)).save(p.rp / "textures" / "gear" / "items" / "stray.png")


def rgb_texture(p):
    f = p.rp / "textures" / "gear" / "items" / "test_boots.png"
    with Image.open(f) as im:
        rgb = im.convert("RGB")
    rgb.save(f)


def wrong_icon_size(p):
    Image.new("RGBA", (32, 32)).save(p.rp / "textures" / "gear" / "items" / "test_boots.png")


def missing_pack_icon(p):
    (p.bp / "pack_icon.png").unlink()


def lang_missing_name(p):
    f = p.rp / "texts" / "en_US.lang"
    f.write_text(f.read_text(encoding="utf-8").replace("=Test Helmet", "=Wrong"), encoding="utf-8")


def _js(p, old, new):
    f = p.bp / "scripts" / "main.js"
    text = f.read_text(encoding="utf-8")
    assert old in text
    f.write_text(text.replace(old, new), encoding="utf-8")


def script_unknown_import(p):
    _js(p, "EquipmentSlot }", "EquipmentSlot, Bogus }")


def script_other_module(p):
    _js(p, 'from "@minecraft/server";', 'from "@minecraft/server-ui";')


def script_unknown_enum(p):
    _js(p, "EquipmentSlot.Head", "EquipmentSlot.Tail")


def script_unknown_method(p):
    _js(p, "player.addTag(SET_TAG)", "player.flyAway(SET_TAG)")


def script_unprefixed_tag(p):
    _js(p, 'SET_TAG = "gear_set"', 'SET_TAG = "set"')


def script_unknown_item(p):
    _js(p, '"gear:test_helmet"', '"gear:test_hat"')


def script_unknown_effect(p):
    _js(p, "const slot", 'const fx = "minecraft:flying";\n    const slot')


def script_missing_translation(p):
    _js(p, "const slot", 'const msg = { translate: "gear.nope" };\n    const slot')


FAILURES = [
    (bom, "test_helmet.json: has a UTF-8 BOM"),
    (broken_json, "test_boots.json: invalid JSON"),
    (extra_top_key, r"unexpected top-level key\(s\) \['extra'\]"),
    (bad_uuid, "RP manifest module 0: invalid UUID 'not-a-uuid'"),
    (duplicate_uuid, "RP manifest module 0: UUID .* duplicates BP header"),
    (dep_version, r"depends on RP version \[9, 9, 9\] but RP is \[1, 0, 1\]"),
    (no_rp_dependency, "does not depend on the RP header UUID"),
    (wrong_engine, "RP manifest: min_engine_version must be"),
    (string_version, r"versions must be \[major, minor, patch\]"),
    (missing_script_entry, "script entry 'scripts/main.js' not found"),
    (unknown_component, r"unknown component\(s\) \['minecraft:bogus'\]"),
    (schema_violation, r"\[schema 1.26.50/ItemDocument\]: \$.components.minecraft:max_stack_size: 99 > maximum 64"),
    (wrong_slot, "wearable slot slot.armor.chest != config slot.armor.head"),
    (wrong_namespace, "identifier 'other:test_helmet' not in namespace gear:"),
    (missing_item, "no item file for gear:test_helmet"),
    (unknown_icon, "icon 'gear_nope' not defined"),
    (recipe_symbol, r"pattern symbols \['S', 'X'\] != key symbols \['I', 'S'\]"),
    (recipe_shape, "pattern must be 1-3 rows of equal length"),
    (recipe_unknown_item, "item minecraft:unobtainium is not a vanilla item"),
    (duplicate_recipe, "test_helmet.json: same pattern and ingredients as gear_bp/recipes/test_boots.json"),
    (missing_recipe, "no recipe for gear:test_boots"),
    (missing_player_attachable, r"gear:test_boots needs both a generic and a .player attachable \(has \['generic'\]\)"),
    (bad_geometry, "geometry geometry.humanoid.armor.hat does not exist in vanilla models"),
    (bad_animation, "animation animation.nope not in vanilla"),
    (bad_material, "unexpected material entity_alphatest"),
    (missing_layer_texture, "texture textures/gear/armor/test_1 not found"),
    (unreferenced_texture, "stray.png: not referenced"),
    (rgb_texture, "test_boots.png: mode RGB, expected RGBA"),
    (wrong_icon_size, "test_boots.png: 32x32, expected 16x16"),
    (missing_pack_icon, "gear_bp/pack_icon.png missing"),
    (lang_missing_name, "item.gear:test_helmet.name should be 'Test Helmet'"),
    (script_unknown_import, "Bogus is not exported"),
    (script_other_module, "imports from @minecraft/server-ui"),
    (script_unknown_enum, "EquipmentSlot.Tail does not exist"),
    (script_unknown_method, r"\.flyAway\(\) is not a method"),
    (script_unprefixed_tag, "tag 'set' must be prefixed gear_"),
    (script_unknown_item, "references unknown item gear:test_hat"),
    (script_unknown_effect, "effect minecraft:flying not in vanilla effect list"),
    (script_missing_translation, "translation key gear.nope missing"),
]


@pytest.mark.parametrize(("mutate", "message"), [pytest.param(f, m, id=f.__name__) for f, m in FAILURES])
def test_validation_failure(project, mutate, message):
    mutate(project)
    with pytest.raises(BuildError, match="validation failed") as exc:
        validate.validate(verbose=False)
    assert exc.match(message)


def test_collects_every_error(project):
    bad_uuid(project)
    lang_missing_name(project)
    script_unknown_method(project)
    with pytest.raises(BuildError) as exc:
        validate.validate(verbose=False)
    lines = [ln for ln in str(exc.value).splitlines() if ln.strip().startswith("- ")]
    assert len(lines) == 3


def test_set_piece_must_be_checked_by_script(project, base_config):
    base_config["pieces"][1]["set_piece"] = True
    project.write_config(base_config)
    with pytest.raises(BuildError, match="set piece gear:test_boots not checked by the script"):
        validate.validate(verbose=False)


def test_validate_does_not_write(project):
    before = {p: p.stat().st_mtime_ns for p in project.root.rglob("*") if p.is_file()}
    validate.validate(verbose=False)
    after = {p: p.stat().st_mtime_ns for p in project.root.rglob("*") if p.is_file()}
    assert after == before


# --------------------------------------------------------------------------- real packs (read-only)


def _real_samples() -> Path:
    env = os.environ.get("MC_SAMPLES") or os.environ.get("GEAR_SAMPLES")
    return Path(env) if env else (common.ROOT / "../bedrock-samples").resolve()


@pytest.mark.skipif(
    not (_real_samples() / "metadata" / "json_schemas").is_dir(),
    reason="Mojang bedrock-samples checkout not present (gitignored; clone it to run this)",
)
def test_real_packs_validate(capsys):
    """The committed gear_bp / gear_rp pass the full validator against the real Mojang metadata."""
    validate.validate()
    assert "OK:" in capsys.readouterr().out


def test_real_validate_uses_real_root():
    assert json.loads((validate.ROOT / "tools" / "gear_config.json").read_text(encoding="utf-8"))["namespace"] == "gear"
