"""common.py: JSON I/O, config loading, naming, and box-UV geometry parsing."""

from __future__ import annotations

import json
import math

import pytest

import common
from common import BuildError

# ------------------------------------------------------------------------------ rel


def test_rel_inside_root_is_relative_posix(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "ROOT", tmp_path)
    assert common.rel(tmp_path / "a" / "b.json") == "a/b.json"


def test_rel_outside_root_is_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "ROOT", tmp_path / "project")
    other = tmp_path / "elsewhere" / "x.json"
    assert common.rel(other) == str(other)


# ------------------------------------------------------------------------- load_json


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig"])
def test_load_json_reads_with_or_without_bom(tmp_path, encoding):
    p = tmp_path / "x.json"
    p.write_text('{"a": [1, 2], "b": "é"}', encoding=encoding)
    assert common.load_json(p) == {"a": [1, 2], "b": "é"}


def test_load_json_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "ROOT", tmp_path)
    with pytest.raises(BuildError, match=r"^sub/nope\.json: file not found$"):
        common.load_json(tmp_path / "sub" / "nope.json")


def test_load_json_invalid_json_names_file_and_position(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "ROOT", tmp_path)
    p = tmp_path / "bad.json"
    p.write_text('{"a": 1,\n "b": }', encoding="utf-8")
    with pytest.raises(BuildError, match=r"^bad\.json: invalid JSON: .*line 2") as exc:
        common.load_json(p)
    assert exc.value.__cause__ is None  # `from None`: a clean message, no chained traceback


def test_load_json_directory_is_not_a_file(tmp_path):
    with pytest.raises(BuildError, match="file not found"):
        common.load_json(tmp_path)


# ----------------------------------------------------------------------------- dumps


@pytest.mark.parametrize(
    ("obj", "expected"),
    [
        ({}, "{}\n"),
        ([], "[]\n"),
        ({"a": []}, '{\n  "a": []\n}\n'),
        ({"v": [1, 0, 3]}, '{\n  "v": [1, 0, 3]\n}\n'),
        ({"a": {"b": "c"}}, '{\n  "a": {\n    "b": "c"\n  }\n}\n'),
        ([{"x": 1}], '[\n  {\n    "x": 1\n  }\n]\n'),
        ({"s": "é", "n": None, "t": True}, '{\n  "s": "\\u00e9",\n  "n": null,\n  "t": true\n}\n'),
    ],
)
def test_dumps_layout(obj, expected):
    assert common.dumps(obj) == expected


def test_dumps_breaks_long_scalar_lists():
    long = list(range(60))
    text = common.dumps({"k": long}, inline_width=40)
    assert "[0, 1" not in text
    assert text.count("\n") > 60


def test_dumps_nested_list_is_never_inline():
    assert common.dumps([[1, 2]]) == "[\n  [1, 2]\n]\n"


@pytest.mark.parametrize(
    "obj",
    [
        {"a": [1, 2, {"b": [3, "x" * 200]}], "c": {"d": {}}, "e": [[], [1.5, -2]]},
        [{"format_version": "1.8.0"}, None, 0, "", [True, False]],
        {"unicode": "§6HUGE ✓", "quote": 'say "hi"\\'},
    ],
)
def test_dumps_round_trips(obj):
    assert json.loads(common.dumps(obj)) == obj


# ------------------------------------------------------------------------- write_text


def test_write_text_lf_no_bom_and_creates_parents(tmp_path):
    p = tmp_path / "deep" / "er" / "f.txt"
    common.write_text(p, "a\nb\n§\n")
    raw = p.read_bytes()
    assert raw == "a\nb\n§\n".encode()
    assert b"\r" not in raw
    assert not raw.startswith(b"\xef\xbb\xbf")


def test_write_json_round_trips(tmp_path):
    obj = {"header": {"version": [1, 2, 3]}, "modules": [{"uuid": "x"}]}
    p = tmp_path / "m.json"
    common.write_json(p, obj)
    assert common.load_json(p) == obj
    assert p.read_text(encoding="utf-8").endswith("}\n")


# ---------------------------------------------------------------------------- config


@pytest.fixture
def write_config(synth, tmp_path, monkeypatch):
    """write_config(drop=key, **changes): write a (modified) small config into a tmp project root."""
    synth.use_root(monkeypatch, tmp_path)

    def write(drop=None, **changes):
        cfg = synth.small_config()
        cfg.update(changes)
        if drop:
            cfg.pop(drop)
        common.write_json(common.CONFIG_PATH, cfg)
        return cfg

    return write


def test_load_config_resolves_paths_against_root(write_config):
    write_config()
    cfg, paths = common.load_config()
    root = common.ROOT
    assert cfg["coat_count"] == 4
    assert paths.geometry == root / "vanilla" / "cat.geo.json"
    assert paths.bp == root / "big_cat_bp"
    assert paths.rp == root / "big_cat_rp"
    assert paths.build == root / "build"
    assert paths.dist == root / "dist"
    assert paths.coat_texture_dir == "textures/entity/coats"
    assert paths.coat_dir_abs == root / "big_cat_rp" / "textures" / "entity" / "coats"


def test_load_config_strips_slashes_from_coat_dir(write_config, synth):
    cfg = synth.small_config()
    write_config(paths={**cfg["paths"], "coat_texture_dir": "/textures/coats/"})
    _, paths = common.load_config()
    assert paths.coat_texture_dir == "textures/coats"


@pytest.mark.parametrize("key", ["coat_count", "seed", "entity", "paths", "colors", "palettes", "pattern_weights"])
def test_load_config_missing_key(write_config, key):
    write_config(drop=key)
    with pytest.raises(BuildError, match=rf"missing keys \['{key}'\]"):
        common.load_config()


@pytest.mark.parametrize("count", [0, -1, 1001, "5", 2.5, None])
def test_load_config_rejects_bad_coat_count(write_config, count):
    write_config(coat_count=count)
    with pytest.raises(BuildError, match=r"coat_count must be an int in 1\.\.1000"):
        common.load_config()


@pytest.mark.parametrize("count", [1, 1000])
def test_load_config_coat_count_bounds(write_config, count):
    write_config(coat_count=count)
    assert common.load_config()[0]["coat_count"] == count


def test_load_config_missing_file():
    with pytest.raises(BuildError, match=r"coats_config\.json: file not found"):
        common.load_config()


# ---------------------------------------------------------------------------- naming


@pytest.mark.parametrize(
    ("i", "coat", "tame"),
    [(0, "coat_000", "coat_000_tame"), (7, "coat_007", "coat_007_tame"), (199, "coat_199", "coat_199_tame")],
)
def test_coat_and_tame_names(i, coat, tame):
    assert common.coat_name(i) == coat
    assert common.tame_name(i) == tame


def test_names_sort_in_index_order():
    names = [common.coat_name(i) for i in range(1000)]
    assert names == sorted(names)
    assert len(set(names)) == 1000


# -------------------------------------------------------------------------- rotation


def _close(a, b):
    return all(math.isclose(x, y, abs_tol=1e-9) for x, y in zip(a, b, strict=True))


@pytest.mark.parametrize(
    ("v", "deg", "pivot", "expected"),
    [
        ((1, 2, 3), (0, 0, 0), (0, 0, 0), (1, 2, 3)),
        ((0, 1, 0), (90, 0, 0), (0, 0, 0), (0, 0, 1)),
        ((0, 0, 1), (0, 90, 0), (0, 0, 0), (1, 0, 0)),
        ((1, 0, 0), (0, 0, 90), (0, 0, 0), (0, 1, 0)),
        ((0, 0, -1), (0, 90, 0), (0, 0, 0), (-1, 0, 0)),
        ((1, 0, 0), (0, 0, 180), (0, 0, 0), (-1, 0, 0)),
        ((2, 1, 0), (0, 0, 90), (1, 1, 0), (1, 2, 0)),  # about a pivot
        ((0, 1, 0), (90, 90, 0), (0, 0, 0), (1, 0, 0)),  # X first, then Y
    ],
)
def test_rot(v, deg, pivot, expected):
    assert _close(common._rot(v, deg, pivot), expected)


def test_rot_dir_ignores_pivot_and_keeps_length():
    n = common._rot_dir((0.6, 0.0, 0.8), (33, -71, 12))
    assert math.isclose(math.hypot(*n), 1.0)


# -------------------------------------------------------------------------- geometry

ONE_CUBE_GEO = "geometry.one"


def one_cube(**bone_extra) -> dict:
    """One 2x3x4 (w x h x d) cube at uv [0,0] on a 16x8 texture (the box UV needs 12x7)."""
    bone = {"name": "b", "pivot": [0, 0, 0], "cubes": [{"origin": [0, 0, 0], "size": [2, 3, 4], "uv": [0, 0]}]}
    bone.update(bone_extra)
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": [
            {"description": {"identifier": "geometry.other", "texture_width": 1, "texture_height": 1}, "bones": []},
            {"description": {"identifier": ONE_CUBE_GEO, "texture_width": 16, "texture_height": 8}, "bones": [bone]},
        ],
    }


@pytest.fixture
def geo_file(tmp_path):
    def write(doc) -> object:
        p = tmp_path / "g.geo.json"
        common.write_json(p, doc)
        return p

    return write


def test_geometry_basics(geo_file):
    g = common.load_geometry(geo_file(one_cube()), ONE_CUBE_GEO)
    assert (g.identifier, g.width, g.height) == (ONE_CUBE_GEO, 16, 8)
    # 2 * (w*d + d*h + w*h) = 2 * (8 + 12 + 6)
    assert len(g.texels) == len(g.surface) == 52
    assert g.cube_bounds[("b", 0)] == ((0, 0, 0), (2, 3, 4))
    assert {t.face for t in g.surface} == {"up", "down", "west", "north", "east", "south"}
    # unused atlas corners are not mapped
    assert (0, 0) not in g.texels
    assert (12, 4) not in g.texels


@pytest.mark.parametrize(
    ("pixel", "face", "normal", "point"),
    [
        ((4, 0), "up", (0, 1, 0), (0.5, 3, 3.5)),
        ((6, 0), "down", (0, -1, 0), (0.5, 0, 0.5)),
        ((0, 4), "west", (-1, 0, 0), (0, 2.5, 3.5)),
        ((4, 4), "north", (0, 0, -1), (0.5, 2.5, 0)),
        ((6, 4), "east", (1, 0, 0), (2, 2.5, 0.5)),
        ((10, 4), "south", (0, 0, 1), (1.5, 2.5, 4)),
        ((5, 6), "north", (0, 0, -1), (1.5, 0.5, 0)),
    ],
)
def test_geometry_box_uv_faces(geo_file, pixel, face, normal, point):
    t = common.load_geometry(geo_file(one_cube()), ONE_CUBE_GEO).texels[pixel]
    assert (t.bone, t.cube, t.face) == ("b", 0, face)
    assert t.face_key == f"b/0/{face}"
    assert _close(t.N, normal)
    assert _close(t.P, point)


def test_geometry_surface_points_lie_on_their_face(geo_file):
    g = common.load_geometry(geo_file(one_cube()), ONE_CUBE_GEO)
    for t in g.surface:
        axis = next(i for i in range(3) if t.N[i])
        expected = (2, 3, 4)[axis] if t.N[axis] > 0 else 0
        assert math.isclose(t.P[axis], expected)


def test_geometry_bone_rotation_turns_points_and_normals(geo_file):
    g = common.load_geometry(geo_file(one_cube(rotation=[0, 90, 0])), ONE_CUBE_GEO)
    t = g.texels[(4, 4)]  # north face
    assert _close(t.N, (-1, 0, 0))


def test_geometry_parent_rotation_applies_to_children(geo_file):
    doc = one_cube(rotation=[0, 0, 90])
    bones = doc["minecraft:geometry"][1]["bones"]
    bones[0]["cubes"] = []
    bones.append({"name": "child", "parent": "b", "cubes": [{"origin": [0, 0, 0], "size": [2, 3, 4], "uv": [0, 0]}]})
    t = common.load_geometry(geo_file(doc), ONE_CUBE_GEO).texels[(4, 0)]  # child's up face
    assert t.bone == "child"
    assert _close(t.N, (-1, 0, 0))


def test_geometry_rest_rotation_only_affects_own_cubes(geo_file):
    doc = one_cube()
    doc["minecraft:geometry"][1]["bones"].append(
        {"name": "child", "parent": "b", "cubes": [{"origin": [4, 0, 0], "size": [2, 3, 4], "uv": [0, 0]}]}
    )
    rest = {"b": {"rotation": [90, 0, 0], "offset": [0, 10, 0]}}
    g = common.load_geometry(geo_file(doc), ONE_CUBE_GEO, rest)
    own = next(t for t in g.surface if t.bone == "b" and t.face == "up")
    child = next(t for t in g.surface if t.bone == "child" and t.face == "up")
    assert _close(own.N, (0, 0, 1))
    assert own.P[1] > 5  # offset applied
    assert _close(child.N, (0, 1, 0))


def test_geometry_identical_cubes_share_uv_silently(geo_file, capsys):
    doc = one_cube()
    doc["minecraft:geometry"][1]["bones"].append(
        {"name": "twin", "cubes": [{"origin": [5, 0, 0], "size": [2, 3, 4], "uv": [0, 0]}]}
    )
    g = common.load_geometry(geo_file(doc), ONE_CUBE_GEO)
    assert len(g.texels) == 52
    assert len(g.surface) == 104
    assert g.texels[(4, 4)].bone == "b"  # first one wins
    assert "warning" not in capsys.readouterr().out


def test_geometry_warns_on_uv_overlap(geo_file, capsys):
    doc = one_cube()
    doc["minecraft:geometry"][1]["bones"].append(
        {"name": "other", "cubes": [{"origin": [5, 0, 0], "size": [1, 1, 1], "uv": [4, 0]}]}
    )
    common.load_geometry(geo_file(doc), ONE_CUBE_GEO)
    assert "warning: UV overlap at pixel" in capsys.readouterr().out


def _mutate(doc_fn):
    doc = one_cube()
    doc_fn(doc)
    return doc


def _cube0(doc):
    return doc["minecraft:geometry"][1]["bones"][0]["cubes"][0]


@pytest.mark.parametrize(
    ("doc", "identifier", "message"),
    [
        ({"format_version": "1.8.0", "geometry.one": {}}, ONE_CUBE_GEO, "no 'minecraft:geometry' list"),
        (one_cube(), "geometry.missing", "geometry 'geometry.missing' not found"),
        (_mutate(lambda d: _cube0(d).update(mirror=True)), ONE_CUBE_GEO, "bone 'b' uses mirror"),
        (one_cube(mirror=True), ONE_CUBE_GEO, "bone 'b' uses mirror"),
        (_mutate(lambda d: _cube0(d).update(uv={"north": {"uv": [0, 0]}})), ONE_CUBE_GEO, "only box UV"),
        (
            _mutate(lambda d: d["minecraft:geometry"][1]["description"].update(texture_width=8)),
            ONE_CUBE_GEO,
            r"face \w+ leaves the 8x8 texture at pixel \(8,",
        ),
    ],
    ids=["old-format", "unknown-id", "cube-mirror", "bone-mirror", "per-face-uv", "outside-texture"],
)
def test_geometry_errors(geo_file, doc, identifier, message):
    with pytest.raises(BuildError, match=message):
        common.load_geometry(geo_file(doc), identifier)
