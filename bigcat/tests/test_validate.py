"""validate.py on a generated synthetic project: passes as built, and catches each kind of breakage."""

from __future__ import annotations

import json
import shutil

import pytest
from PIL import Image

import common
import validate
from common import BuildError


def test_generated_project_validates(project, capsys):
    validate.validate()
    out = capsys.readouterr().out
    assert "OK:" in out
    assert f"{project.cfg['coat_count']} coats" in out


def test_validate_quiet(project, capsys):
    validate.validate(verbose=False)
    assert capsys.readouterr().out == ""


# ---------------------------------------------------------------- breakages, one per test


def _edit_json(path, fn):
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    common.write_json(path, data)


def bump_rp_only(p):
    _edit_json(p.rp / "manifest.json", lambda m: m["header"].update(version=[9, 9, 9]))


def add_bom(p):
    f = p.rp / "texts" / "languages.json"
    f.write_bytes(b"\xef\xbb\xbf" + f.read_bytes())


def break_json(p):
    (p.bp / "items" / "laser_pointer.json").write_text("{ not json", encoding="utf-8")


def unknown_top_key(p):
    _edit_json(p.bp / "items" / "cat_orb.json", lambda d: d.update(__generated__="nope"))


def delete_coat(p):
    (p.paths.coat_dir_abs / "coat_001.png").unlink()


def tame_as_png(p):
    Image.new("RGBA", (32, 32)).save(p.paths.coat_dir_abs / "coat_000_tame.png")


def unreferenced_png(p):
    Image.new("RGBA", (16, 16), (1, 2, 3, 255)).save(p.rp / "textures" / "items" / "orphan.png")


def transparent_wild_coat(p):
    f = p.paths.coat_dir_abs / "coat_002.png"
    im = Image.open(f).convert("RGBA")
    x, y = next((x, y) for y in range(im.height) for x in range(im.width) if im.getpixel((x, y))[3] == 255)
    im.putpixel((x, y), (*im.getpixel((x, y))[:3], 128))
    im.save(f)


def opaque_tame_coat(p):
    f = p.paths.coat_dir_abs / "coat_000_tame.tga"
    im = Image.open(f).convert("RGBA")
    im.putalpha(255)
    im.save(f)


def wrong_coat_size(p):
    f = p.paths.coat_dir_abs / "coat_003.png"
    Image.open(f).convert("RGBA").resize((64, 64)).save(f)


def drop_set_coat_event(p):
    _edit_json(p.bp / "entities" / "big_cat.json", lambda d: d["minecraft:entity"]["events"].pop("mymod:set_coat_2"))


def unknown_event_in_function(p):
    f = p.bp / "functions" / "test_cats.mcfunction"
    f.write_text(f.read_text(encoding="utf-8") + "event entity @s mymod:no_such_event\n", encoding="utf-8")


def drop_wand_event(p):
    _edit_json(p.bp / "entities" / "player.json", lambda d: d["minecraft:entity"]["events"].pop("mymod:size_huge"))


def drop_render_array_entry(p):
    def fn(d):
        rc = next(iter(d["render_controllers"].values()))
        rc["arrays"]["textures"]["Array.tame"].pop()

    _edit_json(p.rp / "render_controllers" / "big_cat.render_controllers.json", fn)


def missing_lang_key(p):
    f = p.rp / "texts" / "en_US.lang"
    text = f.read_text(encoding="utf-8")
    f.write_text("\n".join(ln for ln in text.splitlines() if "mymod:size_wand" not in ln), encoding="utf-8")


def bad_uuid(p):
    _edit_json(p.bp / "manifest.json", lambda m: m["header"].update(uuid="not-a-uuid"))


def bad_tag_prefix(p):
    f = p.bp / "scripts" / "wands.js"
    f.write_text(f.read_text(encoding="utf-8") + '\nplayer.addTag("oops_tag");\n', encoding="utf-8")


def missing_script_import(p):
    f = p.bp / "scripts" / "main.js"
    f.write_text(f.read_text(encoding="utf-8") + '\nimport "./nowhere.js";\n', encoding="utf-8")


def remove_atlas_entry(p):
    _edit_json(p.rp / "textures" / "item_texture.json", lambda d: d["texture_data"].pop("mymod_size_wand"))


def adult_scale_changed(p):
    def fn(d):
        d["minecraft:entity"]["component_groups"]["minecraft:cat_adult"]["minecraft:scale"]["value"] = 1.0

    _edit_json(p.bp / "entities" / "big_cat.json", fn)


def drop_orb_recipe(p):
    (p.bp / "recipes" / "trap_orb.json").unlink()


def hook_not_a_projectile(p):
    _edit_json(
        p.bp / "entities" / "grapple_hook.json",
        lambda d: d["minecraft:entity"]["components"].pop("minecraft:projectile"),
    )


def grapple_not_imported(p):
    f = p.bp / "scripts" / "main.js"
    f.write_text(f.read_text(encoding="utf-8").replace('import "./grapple.js";', ""), encoding="utf-8")


def drop_rope_particle(p):
    (p.rp / "particles" / "grapple_rope.particle.json").unlink()


def drowned_ignores_trap(p):
    def fn(d):
        goal = d["minecraft:entity"]["components"]["minecraft:behavior.nearest_attackable_target"]
        goal["entity_types"] = goal["entity_types"][1:]

    _edit_json(p.bp / "entities" / "drowned.json", fn)


def lure_wrong_family(p):
    _edit_json(
        p.bp / "entities" / "drowned_lure.json",
        lambda d: d["minecraft:entity"]["components"]["minecraft:type_family"].update(family=["inanimate"]),
    )


def air_cannon_not_imported(p):
    f = p.bp / "scripts" / "main.js"
    f.write_text(f.read_text(encoding="utf-8").replace('import "./air_cannon.js";', ""), encoding="utf-8")


BREAKAGES = [
    (bump_rp_only, "depends on RP version"),
    (add_bom, "UTF-8 BOM"),
    (break_json, "invalid JSON"),
    (unknown_top_key, "unexpected top-level key(s) ['__generated__']"),
    (delete_coat, "3 coat PNGs + 4 tame TGAs, expected 4 each"),
    (tame_as_png, "tame textures must be .tga"),
    (unreferenced_png, "orphan.png: not referenced"),
    (transparent_wild_coat, "wild coat must be fully opaque"),
    (opaque_tame_coat, "have the wrong alpha"),
    (wrong_coat_size, "64x64, geometry expects 32x32"),
    (drop_set_coat_event, "3 set_coat events, expected 4"),
    (unknown_event_in_function, "unknown event mymod:no_such_event"),
    (drop_wand_event, "event mymod:size_huge missing"),
    (drop_render_array_entry, "Array.tame has 3 entries, expected 4"),
    (missing_lang_key, "missing item.mymod:size_wand.name"),
    (bad_uuid, "invalid UUID 'not-a-uuid'"),
    (bad_tag_prefix, "'oops_tag' must start with bigcat_"),
    (missing_script_import, "imports './nowhere.js', which does not exist"),
    (remove_atlas_entry, "items/size_wand.json: icon not in item_texture.json"),
    (adult_scale_changed, "adult scale is no longer 3.0"),
    (drop_orb_recipe, "recipes/trap_orb.json: missing or does not make mymod:trap_orb"),
    (drowned_ignores_trap, "drowned.json: minecraft:behavior.nearest_attackable_target does not target"),
    (lure_wrong_family, "drowned_lure.json: type_family must include bigcat_drowned_trap"),
    (air_cannon_not_imported, "scripts/main.js: must import ./air_cannon.js"),
    (hook_not_a_projectile, "grapple_hook.json: needs minecraft:projectile"),
    (grapple_not_imported, "scripts/main.js: must import ./grapple.js"),
    (drop_rope_particle, "grapple_rope.particle.json: missing or does not define mymod:grapple_rope"),
]


@pytest.mark.parametrize(("breakage", "message"), BREAKAGES, ids=[b.__name__ for b, _ in BREAKAGES])
def test_validate_catches(project, breakage, message):
    breakage(project)
    with pytest.raises(BuildError, match="validation failed") as exc:
        validate.validate(verbose=False)
    assert message in str(exc.value)


def test_validate_reports_every_problem_at_once(project):
    delete_coat(project)
    bad_uuid(project)
    unreferenced_png(project)
    with pytest.raises(BuildError) as exc:
        validate.validate(verbose=False)
    msg = str(exc.value)
    assert "invalid UUID" in msg
    assert "not referenced" in msg
    assert "expected 4 each" in msg


def test_missing_pack_file_is_reported(project):
    (project.rp / "entity" / "big_cat.entity.json").unlink()
    with pytest.raises(BuildError, match=r"entity/big_cat\.entity\.json: missing"):
        validate.validate(verbose=False)


@pytest.mark.xfail(
    strict=True,
    raises=FileNotFoundError,
    reason="BUG: validate_orb / validate_wands read scripts/main.js and texts/en_US.lang without checking "
    "they exist, so a missing file crashes validate with a traceback instead of being reported",
)
@pytest.mark.parametrize("missing", ["big_cat_bp/scripts/main.js", "big_cat_rp/texts/en_US.lang"])
def test_missing_hand_written_file_is_reported(project, missing):
    (project.root / missing).unlink()
    with pytest.raises(BuildError, match="missing"):
        validate.validate(verbose=False)


def test_missing_coat_dir_is_reported(project):
    shutil.rmtree(project.paths.coat_dir_abs)
    with pytest.raises(BuildError, match="0 coat PNGs"):
        validate.validate(verbose=False)


def test_script_imports_checked_against_api_metadata(project, tmp_path, monkeypatch):
    """With bedrock-samples' API metadata present, importing a name it doesn't export fails."""
    meta = tmp_path / "samples" / "metadata" / "script_modules" / "@minecraft"
    meta.mkdir(parents=True)
    exported = ["world", "system", "EquipmentSlot", "GameMode", "ItemStack", "Player", "EntityComponentTypes"]
    (meta / f"server-bindings_{validate.SCRIPT_SERVER_VERSION}.json").write_text(
        json.dumps({"classes": [{"name": n} for n in exported]}), encoding="utf-8"
    )
    monkeypatch.setenv("MC_SAMPLES", str(tmp_path / "samples"))
    f = project.bp / "scripts" / "wands.js"
    f.write_text('import { NoSuchThing } from "@minecraft/server";\n' + f.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(BuildError, match="imports 'NoSuchThing', which @minecraft/server"):
        validate.validate(verbose=False)
