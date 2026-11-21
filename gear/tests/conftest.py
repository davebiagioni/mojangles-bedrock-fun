"""Shared fixtures for the gear build-tool tests.

Everything that writes goes into tmp_path: `gear_root` points common.ROOT / CONFIG_PATH (and the
copies other modules imported by name) at a throwaway project folder, `samples` builds a tiny fake
Mojang bedrock-samples checkout, and `project` combines them into a complete, valid synthetic add-on
(generated with the real gen_json / gen_textures code) that validate.py accepts.

The tool modules are imported inside the fixtures, not at the top of this file: pytest may load this
conftest before the root conftest has put gear/tools on sys.path.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from PIL import Image

REPO_GEAR = Path(__file__).resolve().parent.parent

RP_UUID = "f7a1e4cb-0000-4f36-a5fc-2668ee8d778a"

BASE_CONFIG = {
    "namespace": "gear",
    "addon_name": "gear",
    "paths": {
        "behavior_pack": "gear_bp",
        "resource_pack": "gear_rp",
        "vanilla_art": "vanilla",
        "build_dir": "build",
        "dist_dir": "dist",
        "item_texture_dir": "textures/gear/items",
        "armor_texture_dir": "textures/gear/armor",
        "bedrock_samples_default": "../bedrock-samples",
    },
    "item_format_version": "1.26.50",
    "recipe_format_version": "1.20.10",
    "attachable_format_version": "1.10.0",
    "material": {
        "enchantability": 30,
        "repair_item": "minecraft:amethyst_shard",
        "repair_fraction": 0.25,
        "tags": ["minecraft:is_armor"],
    },
    "palette": {
        "stops": [[0.0, [0, 0, 0]], [0.5, [100, 50, 200]], [1.0, [250, 250, 250]]],
        "armor_range": [0.25, 1.0],
        "icon_range": [0.0, 1.0],
        "sparkle_every": 7,
        "sparkle_strength": 0.5,
    },
    "layers": {"test_1": {"source": "diamond_1.png"}},
    "pieces": [
        {
            "id": "test_helmet",
            "name": "Test Helmet",
            "set_piece": True,
            "slot": "slot.armor.head",
            "script_slot": "Head",
            "enchant_slot": "armor_head",
            "protection": 5,
            "durability": 400,
            "kind": "helmet",
            "layer": "test_1",
            "icon_source": "diamond_helmet.png",
            "group": "minecraft:itemGroup.name.helmet",
            "recipe": {
                "pattern": ["SIS", "S S"],
                "key": {"S": "minecraft:amethyst_shard", "I": "minecraft:iron_ingot"},
            },
        },
        {
            "id": "test_boots",
            "name": "Test Boots",
            "set_piece": False,
            "slot": "slot.armor.feet",
            "script_slot": "Feet",
            "enchant_slot": "armor_feet",
            "protection": 3,
            "durability": 300,
            "kind": "boots",
            "layer": "test_1",
            "icon_source": "diamond_boots.png",
            "group": "minecraft:itemGroup.name.boots",
            "recipe": {
                "pattern": ["I I", "S S"],
                "key": {"S": "minecraft:amethyst_shard", "I": "minecraft:iron_ingot"},
            },
        },
    ],
    "kinds": {
        "helmet": {
            "parent_setup": "variable.helmet_layer_visible = 0.0;",
            "animation": "animation.armor.helmet.offset",
        },
        "boots": {"parent_setup": "variable.boot_layer_visible = 0.0;", "animation": "animation.armor.boots.offset"},
    },
}

MAIN_JS = """\
// synthetic test script
import { world, system, EquipmentSlot } from "@minecraft/server";

const HELMET = "gear:test_helmet";
const SET_TAG = "gear_set";

system.runInterval(() => {
  for (const player of world.getAllPlayers()) {
    if (!player.hasTag(SET_TAG)) player.addTag(SET_TAG);
    const slot = EquipmentSlot.Head;
  }
}, 20);
"""

BINDINGS = {
    "classes": [
        {"name": "World", "functions": [{"name": "getAllPlayers"}], "properties": []},
        {"name": "System", "functions": [{"name": "runInterval"}], "properties": []},
        {"name": "Entity", "functions": [{"name": "addTag"}, {"name": "hasTag"}], "properties": [{"name": "name"}]},
    ],
    "enums": [{"name": "EquipmentSlot", "constants": [{"name": "Head"}, {"name": "Feet"}]}],
    "objects": [{"name": "world"}, {"name": "system"}],
    "interfaces": [],
}

ITEM_COMPONENTS = [
    "minecraft:icon",
    "minecraft:max_stack_size",
    "minecraft:wearable",
    "minecraft:durability",
    "minecraft:enchantable",
    "minecraft:repairable",
    "minecraft:tags",
]


def write_json_file(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8", newline="\n")


def read_json_file(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def gradient_image(size: tuple[int, int], transparent_every: int = 5) -> Image.Image:
    """Deterministic RGBA image: grey ramp with varying alpha and a few fully transparent pixels."""
    w, h = size
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    px = im.load()
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if i % transparent_every == 0:
                continue
            g = (x * 255) // max(1, w - 1)
            px[x, y] = (g, (g + y * 7) % 256, 255 - g, 128 + (i % 128))
    return im


def manifests() -> tuple[dict, dict]:
    bp = {
        "format_version": 2,
        "header": {
            "description": "test",
            "name": "Test Gear",
            "uuid": "611531e8-0000-4d97-9ed1-2fb86dc7ca3a",
            "version": [1, 0, 1],
            "min_engine_version": [1, 26, 60],
        },
        "modules": [
            {"type": "data", "uuid": "864aadb2-0000-455e-a2e2-a1c9f5ac6c11", "version": [1, 0, 1]},
            {
                "type": "script",
                "language": "javascript",
                "entry": "scripts/main.js",
                "uuid": "f1db76b9-0000-477a-8872-7a58da455f36",
                "version": [1, 0, 1],
            },
        ],
        "dependencies": [
            {"uuid": RP_UUID, "version": [1, 0, 1]},
            {"module_name": "@minecraft/server", "version": "2.11.0"},
        ],
    }
    rp = {
        "format_version": 2,
        "header": {
            "description": "test",
            "name": "Test Gear Resources",
            "uuid": RP_UUID,
            "version": [1, 0, 1],
            "min_engine_version": [1, 26, 60],
        },
        "modules": [{"type": "resources", "uuid": "72f5a18c-0000-4890-b931-2c47f7f00720", "version": [1, 0, 1]}],
    }
    return bp, rp


@dataclass
class Project:
    root: Path

    @property
    def config_path(self) -> Path:
        return self.root / "tools" / "gear_config.json"

    @property
    def bp(self) -> Path:
        return self.root / "gear_bp"

    @property
    def rp(self) -> Path:
        return self.root / "gear_rp"

    def write_config(self, cfg: dict) -> None:
        write_json_file(self.config_path, cfg)

    def write_manifests(self, bp: dict | None = None, rp: dict | None = None) -> None:
        dbp, drp = manifests()
        write_json_file(self.bp / "manifest.json", bp if bp is not None else dbp)
        write_json_file(self.rp / "manifest.json", rp if rp is not None else drp)


@pytest.fixture
def base_config() -> dict:
    """A fresh, mutable copy of the minimal two-piece config."""
    return copy.deepcopy(BASE_CONFIG)


@pytest.fixture
def gear_root(tmp_path, monkeypatch, base_config) -> Project:
    """An empty project folder that common.ROOT / CONFIG_PATH point at, with the base config written."""
    import common
    import validate

    root = tmp_path / "gear"
    (root / "tools").mkdir(parents=True)
    monkeypatch.setattr(common, "ROOT", root)
    monkeypatch.setattr(common, "CONFIG_PATH", root / "tools" / "gear_config.json")
    monkeypatch.setattr(validate, "ROOT", root)
    for var in ("MC_SAMPLES", "GEAR_SAMPLES", "GEAR_COM_MOJANG"):
        monkeypatch.delenv(var, raising=False)
    proj = Project(root)
    proj.write_config(base_config)
    return proj


@pytest.fixture
def samples(tmp_path, monkeypatch) -> Path:
    """A tiny fake bedrock-samples checkout with just what validate.py reads; MC_SAMPLES points at it."""
    s = tmp_path / "bedrock-samples"
    md = s / "metadata"
    vd = md / "vanilladata_modules"
    write_json_file(
        vd / "mojang-items.json",
        {"data_items": [{"name": n} for n in ("minecraft:amethyst_shard", "minecraft:iron_ingot")]},
    )
    write_json_file(vd / "mojang-effects.json", {"data_items": [{"name": "minecraft:night_vision"}]})
    write_json_file(vd / "mojang-enchantments.json", {"data_items": [{"name": "minecraft:protection"}]})

    sm = md / "script_modules" / "@minecraft"
    write_json_file(sm / "server_2.11.0.json", {})
    write_json_file(sm / "server-bindings_2.11.0.json", BINDINGS)

    item_dir = md / "json_schemas" / "server" / "item" / "1.26.50"
    write_json_file(
        item_dir / "ItemDocument.json",
        {
            "$id": "/server/item/1.26.50/ItemDocument.json",
            "type": "object",
            "required": ["components", "description"],
            "additionalProperties": False,
            "properties": {
                "components": {"$ref": "./Item%20Components.json", "minProperties": 1},
                "description": {
                    "type": "object",
                    "required": ["identifier"],
                    "properties": {
                        "identifier": {"type": "string", "pattern": "^[a-z0-9_]+:[a-z0-9_]+$"},
                        "menu_category": {"type": "object"},
                    },
                    "additionalProperties": False,
                },
            },
        },
    )
    props = {c: {"type": "object"} for c in ITEM_COMPONENTS}
    props["minecraft:max_stack_size"] = {"type": "integer", "minimum": 1, "maximum": 64}
    write_json_file(
        item_dir / "Item Components.json",
        {"$id": "/server/item/1.26.50/Item%20Components.json", "type": "object", "properties": props},
    )

    vrp = s / "resource_pack"
    geo = vrp / "models" / "entity" / "armor.geo.json"
    geo.parent.mkdir(parents=True)
    geo.write_text(
        "// vanilla files carry comments\n"
        + json.dumps(
            {
                "format_version": "1.12.0",
                "minecraft:geometry": [
                    {"description": {"identifier": f"geometry.{who}.armor.{kind}"}}
                    for who in ("humanoid", "player")
                    for kind in ("helmet", "boots")
                ],
            }
        ),
        encoding="utf-8",
    )
    write_json_file(
        vrp / "animations" / "armor.animation.json",
        {"animations": {"animation.armor.helmet.offset": {}, "animation.armor.boots.offset": {}}},
    )
    write_json_file(
        vrp / "render_controllers" / "armor.render_controllers.json",
        {"render_controllers": {"controller.render.armor": {}}},
    )
    write_json_file(vrp / "sounds" / "sound_definitions.json", {"sound_definitions": {"random.orb": {}}})
    glint = vrp / "textures" / "misc" / "enchanted_actor_glint.png"
    glint.parent.mkdir(parents=True)
    Image.new("RGBA", (4, 4), (128, 0, 255, 255)).save(glint)

    monkeypatch.setenv("MC_SAMPLES", str(s))
    return s


@pytest.fixture
def project(gear_root, samples) -> Project:
    """A complete synthetic add-on: source art, manifests, script, then the real generators run on it."""
    import gen_json
    import gen_textures

    art = gear_root.root / "vanilla"
    art.mkdir()
    gradient_image((64, 32)).save(art / "diamond_1.png")
    gradient_image((16, 16), transparent_every=3).save(art / "diamond_helmet.png")
    gradient_image((16, 16), transparent_every=4).save(art / "diamond_boots.png")
    gear_root.write_manifests()
    js = gear_root.bp / "scripts" / "main.js"
    js.parent.mkdir(parents=True)
    js.write_text(MAIN_JS, encoding="utf-8", newline="\n")
    gen_json.generate_json()
    gen_textures.build_textures()
    return gear_root
