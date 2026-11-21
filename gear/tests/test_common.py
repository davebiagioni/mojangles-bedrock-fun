"""common.py: JSON-with-comments, load/write/dumps, rel, texture_key and config loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import common
from common import BuildError, dumps, load_json, strip_json_comments, texture_key, write_json, write_text

# --------------------------------------------------------------------------- strip_json_comments


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param('{"a": 1} // trailing', '{"a": 1} ', id="line-comment"),
        pytest.param('{"a": /* inline */ 1}', '{"a":  1}', id="block-comment"),
        pytest.param('/* multi\nline\n*/{"a": 1}', '{"a": 1}', id="multiline-block"),
        pytest.param('{"url": "http://x.y/z"}', '{"url": "http://x.y/z"}', id="slashes-in-string"),
        pytest.param('{"s": "/* not a comment */"}', '{"s": "/* not a comment */"}', id="block-in-string"),
        pytest.param(r'{"s": "quote \" // still string"}', r'{"s": "quote \" // still string"}', id="escaped-quote"),
        pytest.param('{"s": "a\\\\"} // c', '{"s": "a\\\\"} ', id="escaped-backslash-before-quote"),
        pytest.param("[1, 2]", "[1, 2]", id="no-comments"),
    ],
)
def test_strip_json_comments(text, expected):
    assert strip_json_comments(text) == expected


def test_strip_json_comments_result_parses():
    text = """
    // header comment
    {
      "format_version": "1.10.0", // trailing
      /* block */ "path": "textures/a//b",
      "list": [1, /* two */ 3]
    }
    """
    assert json.loads(strip_json_comments(text)) == {
        "format_version": "1.10.0",
        "path": "textures/a//b",
        "list": [1, 3],
    }


# --------------------------------------------------------------------------- load_json


def test_load_json_reads_plain_and_bom(tmp_path):
    plain, bom = tmp_path / "plain.json", tmp_path / "bom.json"
    plain.write_text('{"a": [1, 2]}', encoding="utf-8")
    bom.write_bytes(b'\xef\xbb\xbf{"a": [1, 2]}')
    assert load_json(plain) == load_json(bom) == {"a": [1, 2]}


def test_load_json_accepts_str_path(tmp_path):
    p = tmp_path / "x.json"
    p.write_text("[]", encoding="utf-8")
    assert load_json(str(p)) == []


def test_load_json_comments_only_when_allowed(tmp_path):
    p = tmp_path / "c.json"
    p.write_text('// hi\n{"a": 1}', encoding="utf-8")
    assert load_json(p, allow_comments=True) == {"a": 1}
    with pytest.raises(BuildError, match="invalid JSON"):
        load_json(p)


def test_load_json_missing_file(tmp_path):
    with pytest.raises(BuildError, match="file not found"):
        load_json(tmp_path / "nope.json")


def test_load_json_directory_is_not_a_file(tmp_path):
    with pytest.raises(BuildError, match="file not found"):
        load_json(tmp_path)


@pytest.mark.parametrize("text", ['{"a": 1,}', "{", "", "{'a': 1}"])
def test_load_json_invalid(tmp_path, text):
    p = tmp_path / "bad.json"
    p.write_text(text, encoding="utf-8")
    with pytest.raises(BuildError, match=r"bad\.json: invalid JSON"):
        load_json(p)


# --------------------------------------------------------------------------- dumps / write


@pytest.mark.parametrize(
    ("obj", "expected"),
    [
        pytest.param({}, "{}\n", id="empty-dict"),
        pytest.param([], "[]\n", id="empty-list"),
        pytest.param({"a": []}, '{\n  "a": []\n}\n', id="nested-empty"),
        pytest.param({"v": [1, 0, 1]}, '{\n  "v": [1, 0, 1]\n}\n', id="short-list-inline"),
        pytest.param({"a": {"b": True}}, '{\n  "a": {\n    "b": true\n  }\n}\n', id="nested-dict"),
        pytest.param([{"a": 1}], '[\n  {\n    "a": 1\n  }\n]\n', id="list-of-dicts"),
        pytest.param("§d", '"\\u00a7d"\n', id="non-ascii-escaped"),
    ],
)
def test_dumps_format(obj, expected):
    assert dumps(obj) == expected


def test_dumps_breaks_long_scalar_lists():
    obj = {"k": ["x" * 30, "y" * 30, "z" * 30]}
    out = dumps(obj)
    assert out == '{\n  "k": [\n    "' + "x" * 30 + '",\n    "' + "y" * 30 + '",\n    "' + "z" * 30 + '"\n  ]\n}\n'
    assert dumps(obj, inline_width=200).count("\n") == 3


def test_dumps_inline_width_counts_indent():
    # the list is exactly `width` chars; at level 1 the indent pushes it over
    lst = list(range(10))
    one = json.dumps(lst)
    assert dumps(lst, inline_width=len(one)) == one + "\n"
    assert "\n    0," in dumps({"k": lst}, inline_width=len(one))


@pytest.mark.parametrize(
    "obj",
    [
        {"format_version": "1.26.50", "x": [1, 2.5, None, "s"], "n": {"deep": [{"a": [True, False]}]}},
        [[], {}, [[1]], "", 0],
        {"unicode": "Amethyst §d ✨", "list": ["a"] * 40},
    ],
)
def test_dumps_round_trips(obj):
    assert json.loads(dumps(obj)) == obj


def test_write_text_no_bom_lf_and_creates_dirs(tmp_path):
    p = tmp_path / "a" / "b" / "c.txt"
    write_text(p, "one\ntwo\n§\n")
    raw = p.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in raw
    assert raw == "one\ntwo\n§\n".encode()


def test_write_json_round_trips_through_load_json(tmp_path):
    obj = {"a": [1, 2], "b": {"c": "d"}}
    p = tmp_path / "sub" / "o.json"
    write_json(p, obj)
    assert load_json(p) == obj
    assert p.read_text(encoding="utf-8") == dumps(obj)


# --------------------------------------------------------------------------- rel / texture_key


def test_rel_inside_root():
    assert common.rel(common.ROOT / "gear_bp" / "manifest.json") == "gear_bp/manifest.json"


def test_rel_outside_root_returns_path_unchanged(tmp_path):
    p = tmp_path / "elsewhere.json"
    assert common.rel(p) == str(p)


@pytest.mark.parametrize(
    ("ns", "pid", "expected"),
    [("gear", "amethyst_helmet", "gear_amethyst_helmet"), ("x", "y", "x_y")],
)
def test_texture_key(ns, pid, expected):
    assert texture_key({"namespace": ns}, {"id": pid}) == expected


# --------------------------------------------------------------------------- load_config


def test_load_config_ok(gear_root):
    cfg, paths = common.load_config()
    root = gear_root.root
    assert [p["identifier"] for p in cfg["pieces"]] == ["gear:test_helmet", "gear:test_boots"]
    assert paths.bp == root / "gear_bp"
    assert paths.rp == root / "gear_rp"
    assert paths.vanilla_art == root / "vanilla"
    assert paths.build == root / "build"
    assert paths.dist == root / "dist"
    assert paths.item_texture_dir == "textures/gear/items"
    assert paths.armor_texture_dir == "textures/gear/armor"
    assert paths.samples == (root / "../bedrock-samples").resolve()


def test_load_config_strips_slashes_from_texture_dirs(gear_root, base_config):
    base_config["paths"]["item_texture_dir"] = "/textures/gear/items/"
    gear_root.write_config(base_config)
    _cfg, paths = common.load_config()
    assert paths.item_texture_dir == "textures/gear/items"


@pytest.mark.parametrize(
    ("env", "expected_name"),
    [
        pytest.param({"GEAR_SAMPLES": "g"}, "g", id="gear-samples"),
        pytest.param({"MC_SAMPLES": "m"}, "m", id="mc-samples"),
        pytest.param({"MC_SAMPLES": "m", "GEAR_SAMPLES": "g"}, "m", id="mc-wins"),
    ],
)
def test_load_config_samples_env(gear_root, monkeypatch, tmp_path, env, expected_name):
    for k, v in env.items():
        monkeypatch.setenv(k, str(tmp_path / v))
    _cfg, paths = common.load_config()
    assert paths.samples == (tmp_path / expected_name).resolve()


def _drop_top(cfg):
    del cfg["kinds"]


def _drop_piece_key(cfg):
    del cfg["pieces"][1]["durability"]


def _bad_id(cfg):
    cfg["pieces"][0]["id"] = "Bad-Id"


def _unknown_kind(cfg):
    cfg["pieces"][0]["kind"] = "gauntlets"


def _unknown_layer(cfg):
    cfg["pieces"][0]["layer"] = "nope"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        pytest.param(_drop_top, r"missing keys \['kinds'\]", id="missing-top-key"),
        pytest.param(_drop_piece_key, "piece test_boots is missing 'durability'", id="piece-missing-key"),
        pytest.param(_bad_id, "bad piece id 'Bad-Id'", id="bad-id"),
        pytest.param(_unknown_kind, "unknown kind 'gauntlets'", id="unknown-kind"),
        pytest.param(_unknown_layer, "unknown layer 'nope'", id="unknown-layer"),
    ],
)
def test_load_config_errors(gear_root, base_config, mutate, message):
    mutate(base_config)
    gear_root.write_config(base_config)
    with pytest.raises(BuildError, match=message):
        common.load_config()


def test_load_config_missing_file(gear_root):
    gear_root.config_path.unlink()
    with pytest.raises(BuildError, match="file not found"):
        common.load_config()


def test_load_config_invalid_json(gear_root):
    gear_root.config_path.write_text("{ nope", encoding="utf-8")
    with pytest.raises(BuildError, match="invalid JSON"):
        common.load_config()


def test_real_config_loads():
    """Read-only: the committed gear_config.json is valid (common.ROOT is the real gear folder here)."""
    cfg, paths = common.load_config()
    assert Path(common.ROOT).name == "gear"
    assert paths.bp.name == "gear_bp"
    assert all(p["identifier"].startswith(cfg["namespace"] + ":") for p in cfg["pieces"])
    assert len({p["id"] for p in cfg["pieces"]}) == len(cfg["pieces"])
