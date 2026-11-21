"""Shared fixtures for the Big Cat build tool tests.

Safety: every test runs with the tools' ROOT (and every path derived from it) pointed at a
throwaway folder under tmp_path, and with the environment variables that locate Minecraft and
bedrock-samples removed or redirected. A test that wants a working project uses the `project`
(or `raw_project`) fixture, which builds a small synthetic one (tiny cat geometry, 4 coats) in
tmp_path from copies of the committed pack files. Nothing ever writes into the repo or into
Minecraft's folders.

The tools are imported lazily (tool() below): this file is loaded before the root conftest has
put bigcat/tools on sys.path.
"""

from __future__ import annotations

import copy
import importlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

BIGCAT = Path(__file__).resolve().parent.parent  # the real project folder (read only!)
REAL_CONFIG = BIGCAT / "tools" / "coats_config.json"
COAT_COUNT = 4
TEX = 32  # synthetic texture is TEX x TEX
GEO_ID = "geometry.testcat"

FUR = (180, 120, 60, 255)
FUR_DARK = (150, 100, 50, 255)
EYE = (40, 220, 60, 255)
EYE_PIXELS = [(4, 14), (6, 14)]  # on the head's north (face) side
COLLAR_PIXELS = [(3, 16), (4, 16), (5, 16), (6, 16)]  # bottom row of the face


def tool(name: str):
    """bigcat/tools/<name>.py (the root conftest makes sure it's this project's)."""
    return importlib.import_module(name)


def use_root(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    """Point every module-level path the tools use at `root` (a project folder)."""
    common = tool("common")
    monkeypatch.setattr(common, "ROOT", root)
    monkeypatch.setattr(common, "CONFIG_PATH", root / "tools" / "coats_config.json")
    monkeypatch.setattr(tool("validate"), "ROOT", root)
    monkeypatch.setattr(tool("gen_tame"), "VANILLA", root / "vanilla")
    fetch = tool("fetch_vanilla")
    monkeypatch.setattr(fetch, "LIST", root / "tools" / "vanilla_files.json")
    monkeypatch.setattr(fetch, "DEST", root / "vanilla")


@pytest.fixture(scope="session")
def _nowhere(tmp_path_factory) -> Path:
    """A folder that is never created (cheaper than a tmp_path per test). Tests that write use tmp_path."""
    return tmp_path_factory.getbasetemp() / "_nowhere"


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, _nowhere):
    """Default for every test: no real ROOT, no real Minecraft, no real bedrock-samples."""
    use_root(monkeypatch, _nowhere / "project")
    for var in ("APPDATA", "LOCALAPPDATA", "BIGCAT_COM_MOJANG"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MC_SAMPLES", str(_nowhere / "bedrock-samples"))
    yield
    assert not _nowhere.exists(), "a test wrote into the default ROOT; give it its own tmp_path"


# --------------------------------------------------------------------------- synthetic data


def _cube(origin, size, uv):
    return {"origin": origin, "size": size, "uv": uv}


def tiny_geometry() -> dict:
    """A blocky 'cat' with every bone the anatomy code needs, in a 32x32 box-UV texture.

    uv rects (x0..x1, y0..y1): body 0..19,0..9  head 0..13,10..16  muzzle 14..19,10..11
    ear 14..17,12..13  leg 20..23,0..3  tail 24..27,0..4
    """
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": [
            {
                "description": {"identifier": GEO_ID, "texture_width": TEX, "texture_height": TEX},
                "bones": [
                    {"name": "body", "pivot": [0, 6, 0], "cubes": [_cube([-2, 4, -3], [4, 4, 6], [0, 0])]},
                    {
                        "name": "head",
                        "pivot": [0, 8, -4],
                        "cubes": [
                            _cube([-2, 6, -6], [4, 4, 3], [0, 10]),
                            _cube([-1, 6, -7], [2, 1, 1], [14, 10]),
                            _cube([-2, 10, -5], [1, 1, 1], [14, 12]),
                        ],
                    },
                    {"name": "leg", "parent": "body", "cubes": [_cube([-2, 0, -3], [1, 3, 1], [20, 0])]},
                    {"name": "tail", "parent": "body", "cubes": [_cube([-0.5, 5, 3], [1, 4, 1], [24, 0])]},
                ],
            }
        ],
    }


TINY_ANATOMY = {
    "body_bone": "body",
    "head_bone": "head",
    "leg_bones": ["leg"],
    "tail_bones": ["tail"],
    "ear_cubes": [["head", 2]],
    "muzzle_cubes": [["head", 1]],
    "belly_height": 0.35,
    "paw_height": 1.0,
    "rest_pose": {},
}


def base_texture() -> Image.Image:
    """Fur with a little shading, plus two eye pixels in a colour the body never uses."""
    im = Image.new("RGBA", (TEX, TEX), (0, 0, 0, 0))
    for y in range(TEX):
        for x in range(28):
            im.putpixel((x, y), FUR if (x + y) % 3 else FUR_DARK)
    for p in EYE_PIXELS:
        im.putpixel(p, EYE)
    return im


def tame_reference() -> Image.Image:
    """Like vanilla's tame TGA: alpha 4 everywhere, 255 on the collar ring."""
    im = Image.new("RGBA", (TEX, TEX), (90, 90, 90, 4))
    for p in COLLAR_PIXELS:
        im.putpixel(p, (200, 30, 30, 255))
    return im


def vanilla_mob(identifier: str, **components) -> dict:
    return {
        "format_version": "1.21.0",
        "minecraft:entity": {
            "description": {"identifier": identifier, "is_spawnable": True},
            "component_groups": {"minecraft:some_group": {"minecraft:scale": {"value": 1}}},
            "components": {"minecraft:health": {"value": 20}, **components},
            "events": {"minecraft:entity_spawned": {"add": {"component_groups": ["minecraft:some_group"]}}},
        },
    }


def vanilla_text(doc: dict) -> str:
    """Mojang-style JSON: a // comment, a /* */ comment and a trailing comma."""
    body = json.dumps(doc, indent=2)
    return "// Mojang header comment\n/* block\n comment */\n" + body[:-2] + ",\n}\n"


CREEPER_INTERACT = {"interact_text": "action.interact.creeper", "on_interact": {"event": "minecraft:start_exploding"}}
VANILLA_MOBS = {
    "zombie": vanilla_mob("minecraft:zombie"),
    "skeleton": vanilla_mob("minecraft:skeleton"),
    "creeper": vanilla_mob("minecraft:creeper", **{"minecraft:interact": {"interactions": CREEPER_INTERACT}}),
    "player": vanilla_mob("minecraft:player"),
}


def small_config(coat_count: int = COAT_COUNT) -> dict:
    """The real coats_config.json, shrunk to a few coats on the tiny geometry."""
    cfg = json.loads(REAL_CONFIG.read_text(encoding="utf-8-sig"))
    cfg["coat_count"] = coat_count
    cfg["entity"]["geometry"] = GEO_ID
    cfg["anatomy"] = copy.deepcopy(TINY_ANATOMY)
    cfg["test_grid"] = {"columns": 2, "rows": 2, "spacing": 3, "page_size": 3}
    return cfg


def _ignore_generated(src, names):
    # coat textures are regenerated anyway; generated mob files come from the synthetic vanilla
    skip = {"coats", "zombie.json", "skeleton.json", "creeper.json", "player.json", "__pycache__"}
    return [n for n in names if n in skip]


def make_project(root: Path, cfg: dict | None = None, packs: bool = True) -> Path:
    """A buildable Big Cat project in `root`: real hand-written pack files + synthetic Mojang files.

    packs=False skips copying the pack folders (faster, for tests that only need the coat inputs).
    """
    common = tool("common")
    (root / "tools").mkdir(parents=True)
    common.write_json(root / "tools" / "coats_config.json", cfg or small_config())
    shutil.copytree(BIGCAT / "tools" / "templates", root / "tools" / "templates")
    for pack in ("big_cat_bp", "big_cat_rp") if packs else ():
        shutil.copytree(BIGCAT / pack, root / pack, ignore=_ignore_generated)
    van = root / "vanilla"
    van.mkdir()
    common.write_json(van / "cat.geo.json", tiny_geometry())
    base_texture().save(van / "cat_base.png")
    tame_reference().save(van / "cat_tame.tga")
    for name, doc in VANILLA_MOBS.items():
        common.write_text(van / f"{name}.json", vanilla_text(doc))
    return root


def run_generators() -> None:
    """Everything build.py does except fetching, validating, deploying and packaging."""
    tool("build_coats").build_coats(verbose=False)
    tool("gen_json").generate_json(verbose=False)
    tool("gen_laser").generate_laser_textures(verbose=False)
    tool("gen_orb").generate_orb_textures(verbose=False)
    tool("gen_tame").generate_tame(verbose=False)
    tool("gen_wand").generate_wand_textures(verbose=False)
    tool("gen_grapple").generate_grapple_textures(verbose=False)
    tool("gen_evolution").generate_evolution_textures(verbose=False)
    tool("gen_player").generate_player(verbose=False)


@pytest.fixture
def synth() -> SimpleNamespace:
    """The synthetic-data helpers and constants above, for tests that need them directly."""
    return SimpleNamespace(
        TEX=TEX,
        GEO_ID=GEO_ID,
        COAT_COUNT=COAT_COUNT,
        EYE_PIXELS=EYE_PIXELS,
        COLLAR_PIXELS=COLLAR_PIXELS,
        BIGCAT=BIGCAT,
        tiny_geometry=tiny_geometry,
        base_texture=base_texture,
        tame_reference=tame_reference,
        vanilla_mob=vanilla_mob,
        vanilla_text=vanilla_text,
        small_config=small_config,
        make_project=make_project,
        run_generators=run_generators,
        use_root=use_root,
    )


@dataclass
class Project:
    root: Path
    cfg: dict
    paths: object  # common.Paths

    @property
    def bp(self) -> Path:
        return self.paths.bp

    @property
    def rp(self) -> Path:
        return self.paths.rp


@pytest.fixture(scope="session")
def _built_cache(tmp_path_factory) -> dict:
    return {"root": None, "base": tmp_path_factory.mktemp("built")}


@pytest.fixture
def raw_project(tmp_path, monkeypatch) -> Project:
    """A synthetic project with sources only (nothing generated yet), ROOT pointed at it."""
    root = make_project(tmp_path / "proj")
    use_root(monkeypatch, root)
    cfg, paths = tool("common").load_config()
    return Project(root, cfg, paths)


@pytest.fixture
def bare_project(tmp_path, monkeypatch) -> Project:
    """Like raw_project but without the pack folders: config, templates and vanilla inputs only."""
    root = make_project(tmp_path / "proj", packs=False)
    use_root(monkeypatch, root)
    cfg, paths = tool("common").load_config()
    return Project(root, cfg, paths)


@pytest.fixture
def project(tmp_path, monkeypatch, _built_cache) -> Project:
    """A fully generated synthetic project (fresh copy per test), ROOT pointed at it.

    Generation runs once per session; each test gets its own copy so it can break things.
    """
    if _built_cache["root"] is None:
        golden = make_project(_built_cache["base"] / "golden")
        with monkeypatch.context() as m:
            use_root(m, golden)
            run_generators()
        _built_cache["root"] = golden
    root = tmp_path / "proj"
    shutil.copytree(_built_cache["root"], root)
    use_root(monkeypatch, root)
    cfg, paths = tool("common").load_config()
    return Project(root, cfg, paths)
