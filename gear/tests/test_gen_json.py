"""gen_json: the pure builders and generate_json() on a minimal config in tmp_path."""

from __future__ import annotations

import json

import pytest

import common
import gen_json
from gen_json import attachables, item_json, recipe_json


@pytest.fixture
def cfg_paths(gear_root):
    return common.load_config()


def test_item_json_shape(cfg_paths):
    cfg, _ = cfg_paths
    helmet = cfg["pieces"][0]
    item = item_json(cfg, helmet)
    assert item["format_version"] == "1.26.50"
    body = item["minecraft:item"]
    assert body["description"] == {
        "identifier": "gear:test_helmet",
        "menu_category": {"category": "equipment", "group": "minecraft:itemGroup.name.helmet"},
    }
    c = body["components"]
    assert c["minecraft:icon"] == {"textures": {"default": "gear_test_helmet"}}
    assert c["minecraft:max_stack_size"] == 1
    assert c["minecraft:wearable"] == {"slot": "slot.armor.head", "protection": 5}
    assert c["minecraft:durability"] == {"max_durability": 400}
    assert c["minecraft:enchantable"] == {"slot": "armor_head", "value": 30}
    repair = c["minecraft:repairable"]["repair_items"]
    assert [r["items"] for r in repair] == [["gear:test_helmet"], ["minecraft:amethyst_shard"]]
    assert repair[1]["repair_amount"] == "query.max_durability * 0.25"
    assert c["minecraft:tags"] == {"tags": ["minecraft:is_armor"]}


def test_item_json_does_not_alias_config(cfg_paths):
    cfg, _ = cfg_paths
    item_json(cfg, cfg["pieces"][0])["minecraft:item"]["components"]["minecraft:tags"]["tags"].append("x")
    assert cfg["material"]["tags"] == ["minecraft:is_armor"]


def test_recipe_json_shape(cfg_paths):
    cfg, _ = cfg_paths
    r = recipe_json(cfg, cfg["pieces"][1])
    assert r == {
        "format_version": "1.20.10",
        "minecraft:recipe_shaped": {
            "description": {"identifier": "gear:test_boots"},
            "tags": ["crafting_table"],
            "pattern": ["I I", "S S"],
            "key": {"S": {"item": "minecraft:amethyst_shard"}, "I": {"item": "minecraft:iron_ingot"}},
            "unlock": [{"item": "minecraft:amethyst_shard"}],
            "result": {"item": "gear:test_boots"},
        },
    }


@pytest.mark.parametrize(("index", "kind"), [(0, "helmet"), (1, "boots")])
def test_attachables_pair(cfg_paths, index, kind):
    cfg, paths = cfg_paths
    piece = cfg["pieces"][index]
    out = attachables(cfg, paths, piece)
    assert set(out) == {f"{piece['id']}.json", f"{piece['id']}.player.json"}
    generic = out[f"{piece['id']}.json"]["minecraft:attachable"]["description"]
    player = out[f"{piece['id']}.player.json"]["minecraft:attachable"]["description"]
    assert generic["identifier"] == piece["identifier"]
    assert player["identifier"] == piece["identifier"] + ".player"
    assert player["item"] == {piece["identifier"]: "query.owner_identifier == 'minecraft:player'"}
    assert "item" not in generic
    assert generic["geometry"] == {"default": f"geometry.humanoid.armor.{kind}"}
    assert player["geometry"] == {"default": f"geometry.player.armor.{kind}"}
    assert player["animations"] == {"offset": f"animation.armor.{kind}.offset"}
    assert player["scripts"]["animate"] == ["offset"]
    for d in (generic, player):
        assert d["textures"] == {
            "default": "textures/gear/armor/test_1",
            "enchanted": "textures/misc/enchanted_actor_glint",
        }
        assert d["materials"] == {"default": "armor", "enchanted": "armor_enchanted"}
        assert d["scripts"]["parent_setup"] == cfg["kinds"][kind]["parent_setup"]
        assert d["render_controllers"] == ["controller.render.armor"]


def test_generate_json_writes_all_files(gear_root):
    gen_json.generate_json()
    bp, rp = gear_root.bp, gear_root.rp
    assert sorted(p.name for p in (bp / "items").iterdir()) == ["test_boots.json", "test_helmet.json"]
    assert sorted(p.name for p in (bp / "recipes").iterdir()) == ["test_boots.json", "test_helmet.json"]
    assert sorted(p.name for p in (rp / "attachables").iterdir()) == [
        "test_boots.json",
        "test_boots.player.json",
        "test_helmet.json",
        "test_helmet.player.json",
    ]
    tex = json.loads((rp / "textures" / "item_texture.json").read_text(encoding="utf-8"))
    assert tex == {
        "resource_pack_name": "gear",
        "texture_name": "atlas.items",
        "texture_data": {
            "gear_test_helmet": {"textures": "textures/gear/items/test_helmet"},
            "gear_test_boots": {"textures": "textures/gear/items/test_boots"},
        },
    }
    assert json.loads((rp / "texts" / "languages.json").read_text(encoding="utf-8")) == ["en_US"]
    lang = (rp / "texts" / "en_US.lang").read_text(encoding="utf-8").splitlines()
    assert lang[0].startswith("## GENERATED")
    assert "item.gear:test_helmet.name=Test Helmet" in lang
    assert "item.gear:test_boots.name=Test Boots" in lang
    keys = {ln.split("=", 1)[0] for ln in lang if "=" in ln and not ln.startswith("##")}
    assert {"gear.set_bonus.on", "gear.set_bonus.off", "gear.goggles.on", "gear.goggles.off"} <= keys


def test_generate_json_output_is_canonical(gear_root):
    gen_json.generate_json()
    cfg, _ = common.load_config()
    item = gear_root.bp / "items" / "test_helmet.json"
    raw = item.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in raw
    assert raw.decode("utf-8") == common.dumps(item_json(cfg, cfg["pieces"][0]))


def test_generate_json_removes_stale_pieces(gear_root, base_config):
    gen_json.generate_json()
    base_config["pieces"].pop()
    gear_root.write_config(base_config)
    keep = gear_root.bp / "items" / "notes.txt"
    keep.write_text("not json", encoding="utf-8")
    gen_json.generate_json()
    assert sorted(p.name for p in (gear_root.bp / "items").glob("*.json")) == ["test_helmet.json"]
    assert sorted(p.name for p in (gear_root.rp / "attachables").glob("*.json")) == [
        "test_helmet.json",
        "test_helmet.player.json",
    ]
    assert keep.is_file(), "only *.json is cleared"
    lang = (gear_root.rp / "texts" / "en_US.lang").read_text(encoding="utf-8")
    assert "test_boots" not in lang


def test_generate_json_is_idempotent(gear_root):
    gen_json.generate_json()
    files = sorted(p for p in gear_root.root.rglob("*") if p.is_file())
    first = {p: p.read_bytes() for p in files}
    gen_json.generate_json()
    assert {p: p.read_bytes() for p in sorted(p for p in gear_root.root.rglob("*") if p.is_file())} == first


# --------------------------------------------------------------------------- real files (read-only)


def _real_cases():
    cfg, paths = common.load_config()
    for piece in cfg["pieces"]:
        yield pytest.param(paths.bp / "items" / f"{piece['id']}.json", item_json(cfg, piece), id=f"item-{piece['id']}")
        yield pytest.param(
            paths.bp / "recipes" / f"{piece['id']}.json", recipe_json(cfg, piece), id=f"recipe-{piece['id']}"
        )
        for name, data in attachables(cfg, paths, piece).items():
            yield pytest.param(paths.rp / "attachables" / name, data, id=f"attachable-{name}")


@pytest.mark.parametrize(("path", "expected"), list(_real_cases()))
def test_committed_generated_json_is_up_to_date(path, expected):
    """The checked-in pack files equal what gen_json would write from the committed config."""
    assert path.read_text(encoding="utf-8") == common.dumps(expected), f"{path.name} is stale: run tools/build.py"
