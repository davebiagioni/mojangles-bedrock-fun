"""gen_tame.py and gen_player.py: patching (synthetic) vanilla entity definitions."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

import common
import gen_player
import gen_tame
from common import BuildError

# ------------------------------------------------------------------- comment stripping


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"a": 1}', {"a": 1}),
        ('// top\n{"a": 1} // tail', {"a": 1}),
        ('{\n  "a": 1, // why\n  "b": 2\n}', {"a": 1, "b": 2}),
        ('/* x\n y */ {"a": /* inline */ 1}', {"a": 1}),
        ('{"url": "http://x//y", "c": "/* not a comment */"}', {"url": "http://x//y", "c": "/* not a comment */"}),
        ('{"q": "say \\"hi\\" // still string"}', {"q": 'say "hi" // still string'}),
        ('{"p": "C:\\\\dir\\\\"} // after a backslash-ended string', {"p": "C:\\dir\\"}),
        ('{"a": [1, 2,], "b": {"c": 3,},}', {"a": [1, 2], "b": {"c": 3}}),
        ('{"a": [1, 2 ,\n ]}', {"a": [1, 2]}),
    ],
    ids=["plain", "line", "line-mid", "block", "in-string", "escaped-quote", "escaped-backslash", "trailing", "ws"],
)
def test_strip_comments(text, expected):
    assert json.loads(gen_tame._strip_comments(text)) == expected


@pytest.mark.xfail(
    strict=True,
    reason="BUG: the trailing-comma regex in _strip_comments also runs inside JSON strings, "
    "so a string containing ',]' or ',}' loses its comma",
)
def test_strip_comments_keeps_commas_inside_strings():
    assert json.loads(gen_tame._strip_comments('{"s": ",]"}')) == {"s": ",]"}


@pytest.mark.xfail(
    strict=True,
    raises=pytest.fail.Exception,
    reason="BUG: _strip_comments loops forever on an unterminated /* comment that isn't at index 0 "
    "(text.find returns -1, so i jumps back to 1); a truncated vanilla file would hang the build",
)
def test_strip_comments_unterminated_block_comment_terminates(synth):
    code = "from gen_tame import _strip_comments; _strip_comments('{} /* truncated')"
    try:
        subprocess.run(
            [sys.executable, "-c", code], cwd=synth.BIGCAT / "tools", timeout=1.0, check=True, capture_output=True
        )
    except subprocess.TimeoutExpired:
        pytest.fail("_strip_comments did not terminate")


# --------------------------------------------------------------------- vanilla loading


def test_load_vanilla_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "ROOT", tmp_path)
    monkeypatch.setattr(gen_tame, "VANILLA", tmp_path / "vanilla")
    with pytest.raises(BuildError, match=r"vanilla/zombie\.json missing; run tools/fetch_vanilla\.py"):
        gen_tame._load_vanilla("zombie")


def test_load_vanilla_unparseable(tmp_path, monkeypatch):
    monkeypatch.setattr(gen_tame, "VANILLA", tmp_path)
    (tmp_path / "zombie.json").write_text("{ nope", encoding="utf-8")
    with pytest.raises(BuildError, match=r"zombie\.json: could not parse"):
        gen_tame._load_vanilla("zombie")


def test_load_vanilla_with_bom_and_comments(tmp_path, monkeypatch, synth):
    monkeypatch.setattr(gen_tame, "VANILLA", tmp_path)
    doc = synth.vanilla_mob("minecraft:zombie")
    (tmp_path / "zombie.json").write_text(synth.vanilla_text(doc), encoding="utf-8-sig")
    assert gen_tame._load_vanilla("zombie") == doc


# ------------------------------------------------------------------------------ taming


@pytest.fixture
def vanilla(tmp_path, monkeypatch, synth):
    """Write synthetic vanilla files: vanilla(name, doc)."""
    monkeypatch.setattr(gen_tame, "VANILLA", tmp_path / "vanilla")

    def write(name, doc):
        common.write_text(tmp_path / "vanilla" / f"{name}.json", synth.vanilla_text(doc))

    return write


@pytest.mark.parametrize("name", sorted(gen_tame.MOBS))
def test_patch_adds_taming(vanilla, synth, name):
    vanilla(name, synth.vanilla_mob(f"minecraft:{name}"))
    ent = gen_tame._patch(name, gen_tame.MOBS[name])["minecraft:entity"]
    comps = ent["components"]
    tame = comps["minecraft:tameable"]
    assert tame["probability"] == 0.0
    assert tame["tame_event"] == {"event": gen_tame.TAME_EVENT, "target": "self"}
    assert comps["minecraft:health"] == {"value": 20}  # vanilla content kept
    assert "minecraft:some_group" in ent["component_groups"]
    assert "minecraft:entity_spawned" in ent["events"]
    group = ent["component_groups"][gen_tame.TAMED_GROUP]
    assert "minecraft:is_tamed" in group
    assert "minecraft:behavior.follow_owner" in group
    assert group["minecraft:despawn"]["filters"] == gen_tame.NEVER
    assert ent["events"][gen_tame.TAME_EVENT] == {"add": {"component_groups": [gen_tame.TAMED_GROUP]}}
    assert gen_tame.TRY_EVENT in ent["events"]
    (ours,) = comps["minecraft:interact"]["interactions"]
    assert ours["interact_text"] == gen_tame.MOBS[name]["interact"]["text"]
    assert ours["on_interact"]["event"] == gen_tame.TRY_EVENT


@pytest.mark.parametrize(
    ("existing", "count"),
    [({"interact_text": "old"}, 2), ([{"interact_text": "a"}, {"interact_text": "b"}], 3)],
    ids=["single-dict", "list"],
)
def test_patch_keeps_existing_interactions(vanilla, synth, existing, count):
    vanilla("creeper", synth.vanilla_mob("minecraft:creeper", **{"minecraft:interact": {"interactions": existing}}))
    inter = gen_tame._patch("creeper", gen_tame.MOBS["creeper"])["minecraft:entity"]["components"]["minecraft:interact"]
    assert len(inter["interactions"]) == count
    assert inter["interactions"][0]["interact_text"] in ("old", "a")
    assert inter["interactions"][-1]["interact_text"] == "action.interact.mymod_hug"


def test_patch_creates_missing_component_groups_and_events(vanilla):
    vanilla("zombie", {"minecraft:entity": {"description": {"identifier": "minecraft:zombie"}, "components": {}}})
    ent = gen_tame._patch("zombie", gen_tame.MOBS["zombie"])["minecraft:entity"]
    assert set(ent["component_groups"]) == {gen_tame.TAMED_GROUP}
    assert set(ent["events"]) == {gen_tame.TAME_EVENT, gen_tame.TRY_EVENT}


@pytest.mark.parametrize(
    ("spec", "test"),
    [
        (
            {"text": "t", "item": "cake"},
            {"test": "has_equipment", "subject": "other", "domain": "hand", "value": "cake"},
        ),
        ({"text": "t", "sneaking": True}, {"test": "is_sneaking", "subject": "other"}),
    ],
)
def test_interaction_filters(spec, test):
    conds = gen_tame._interaction(spec)["on_interact"]["filters"]["all_of"]
    assert conds[0] == {"test": "is_family", "subject": "other", "value": "player"}
    assert gen_tame.NOT_TAMED_SELF in conds
    assert conds[-1] == test


@pytest.mark.parametrize("fights", [True, False])
def test_tamed_group_fighting(fights):
    g = gen_tame._tamed_group(fights)
    assert ("minecraft:behavior.owner_hurt_by_target" in g) is fights
    target = json.dumps(g["minecraft:behavior.nearest_attackable_target"])
    assert ("monster" in target) is fights
    assert ("mymod_never" in target) is not fights
    hurt = g["minecraft:behavior.hurt_by_target"]["entity_types"][0]["filters"]
    assert (hurt["operator"], hurt["value"]) == ("!=", "player")  # never fights back against players


def test_lang_keys_cover_mob_interactions():
    assert {spec["interact"]["text"] for spec in gen_tame.MOBS.values()} == set(gen_tame.LANG)


def test_generate_tame_writes_entities_and_lang_once(raw_project):
    lang = raw_project.rp / "texts" / "en_US.lang"
    lang.write_text("item.x.name=X\n", encoding="utf-8")
    gen_tame.generate_tame(verbose=False)
    for name in gen_tame.MOBS:
        doc = common.load_json(raw_project.bp / "entities" / f"{name}.json")
        assert "minecraft:tameable" in doc["minecraft:entity"]["components"]
    text = lang.read_text(encoding="utf-8")
    assert text.startswith("item.x.name=X\n")
    for k, v in gen_tame.LANG.items():
        assert f"{k}={v}\n" in text
    gen_tame.generate_tame(verbose=False)
    assert lang.read_text(encoding="utf-8") == text  # idempotent


def test_generate_tame_needs_vanilla(raw_project):
    (raw_project.root / "vanilla" / "skeleton.json").unlink()
    with pytest.raises(BuildError, match=r"skeleton\.json missing"):
        gen_tame.generate_tame(verbose=False)


# ------------------------------------------------------------------------------ player


def test_player_patch(vanilla, synth):
    vanilla("player", synth.vanilla_mob("minecraft:player"))
    ent = gen_player._patch()["minecraft:entity"]
    groups, events = ent["component_groups"], ent["events"]
    assert "minecraft:some_group" in groups
    for name, scale in gen_player.SIZES.items():
        assert groups[f"mymod:size_{name}"] == {"minecraft:scale": {"value": scale}}
        ev = events[f"mymod:size_{name}"]
        assert ev["add"] == {"component_groups": [f"mymod:size_{name}"]}
        assert f"mymod:size_{name}" not in ev["remove"]["component_groups"]
        assert set(ev["remove"]["component_groups"]) | {f"mymod:size_{name}"} == set(gen_player.GROUPS.values())
    assert events["mymod:size_normal"] == {"remove": {"component_groups": list(gen_player.GROUPS.values())}}
    assert "minecraft:scale" not in ent["components"]


def test_player_patch_refuses_vanilla_scale(vanilla, synth):
    vanilla("player", synth.vanilla_mob("minecraft:player", **{"minecraft:scale": {"value": 1}}))
    with pytest.raises(BuildError, match=r"vanilla player\.json now has minecraft:scale"):
        gen_player._patch()


def test_player_sizes_are_sane():
    assert gen_player.SIZES["mini"] < 1 < gen_player.SIZES["huge"]
    assert set(gen_player.EVENTS) == {*gen_player.SIZES, "normal"}


def test_generate_player_writes_bp_entity(bare_project, capsys):
    gen_player.generate_player()
    doc = common.load_json(bare_project.bp / "entities" / "player.json")
    assert "mymod:size_normal" in doc["minecraft:entity"]["events"]
    assert "big_cat_bp/entities/player.json" in capsys.readouterr().out


def test_sizes_match_wands_script(synth):
    """gen_player.SIZES must match SCALE in the committed scripts/wands.js (validate checks this too)."""
    js_path = synth.BIGCAT / "big_cat_bp" / "scripts" / "wands.js"
    if not js_path.is_file():
        pytest.skip("scripts/wands.js not present")
    js = js_path.read_text(encoding="utf-8")
    for size, scale in gen_player.SIZES.items():
        assert f"{size}: {scale}" in js
