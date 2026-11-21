"""build_coats.py: helpers, anatomy, patterns, coat/tame images, and the full run on a small config."""

from __future__ import annotations

import json
import random

import pytest
from PIL import Image

import build_coats as bc
import common
from common import BuildError

# ------------------------------------------------------------------------ small math


@pytest.mark.parametrize(("x", "expected"), [(-1, 0), (0, 0), (0.25, 0.25), (1, 1), (7, 1)])
def test_clamp01(x, expected):
    assert bc.clamp01(x) == expected


@pytest.mark.parametrize(("x", "expected"), [(-5, 0), (0, 0), (0.5, 0.5), (1, 1), (3, 1)])
def test_smooth(x, expected):
    assert bc.smooth(x) == pytest.approx(expected)


def test_smooth_is_monotonic():
    ys = [bc.smooth(i / 100) for i in range(101)]
    assert ys == sorted(ys)


@pytest.mark.parametrize(
    ("t", "expected"), [(0, (0, 0, 0)), (0.5, (0.5, 1, 1.5)), (1, (1, 2, 3)), (2, (1, 2, 3)), (-1, (0, 0, 0))]
)
def test_lerp_clamps(t, expected):
    assert bc.lerp((0, 0, 0), (1, 2, 3), t) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("h", "rgb"),
    [("#000000", (0, 0, 0)), ("#ffffff", (1, 1, 1)), ("ff0000", (1, 0, 0)), ("#00FF80", (0, 1, 128 / 255))],
)
def test_hex_to_rgb(h, rgb):
    assert bc.hex_to_rgb(h) == pytest.approx(rgb)


@pytest.mark.parametrize("bad", ["#fff", "#1234567", ""])
def test_hex_to_rgb_rejects(bad):
    with pytest.raises(BuildError, match="use #rrggbb"):
        bc.hex_to_rgb(bad)


@pytest.mark.parametrize(("rgb", "lum"), [((0, 0, 0), 0), ((255, 255, 255), 1), ((0, 255, 0, 9), 0.7152)])
def test_luminance(rgb, lum):
    assert bc.luminance(rgb) == pytest.approx(lum)


# ----------------------------------------------------------------------------- noise


def test_noise_is_deterministic_and_in_range():
    a, b = bc.Noise(42), bc.Noise(42)
    pts = [(x * 0.37, y * 0.91, (x - y) * 0.53) for x in range(-5, 5) for y in range(-5, 5)]
    va = [a.value(*p) for p in pts]
    assert va == [b.value(*p) for p in pts]
    assert all(0 <= v < 1 for v in va)
    assert all(0 <= a.fbm(p, 0.5) < 1 for p in pts)
    assert len(set(va)) > 50


def test_noise_seed_matters():
    p = (1.3, 2.7, -0.4)
    assert len({bc.Noise(s).value(*p) for s in range(10)}) == 10


def test_noise_value_is_continuous():
    n = bc.Noise(7)
    assert abs(n.value(1.0, 2.0, 3.0) - n.value(1.0001, 2.0, 3.0)) < 1e-3


def test_noise_spots_distance():
    n = bc.Noise(3)
    assert n.spots((0, 0, 0), 2.0, 0.0) == pytest.approx(1e9**0.5 * 2.0)  # density 0: no spots at all
    d = n.spots((0.3, 0.2, 0.1), 2.0, 1.0)  # density 1: one spot per cell, so one is near
    assert 0 <= d < 2.0 * 3**0.5


# ------------------------------------------------------------------- random helpers


def test_weighted_follows_weights():
    rng = random.Random(1)
    items = [("a", 1), ("b", 3), ("zero", 0)]
    counts = {"a": 0, "b": 0, "zero": 0}
    for _ in range(4000):
        counts[bc.weighted(rng, items)] += 1
    assert counts["zero"] == 0
    assert 0.2 < counts["a"] / 4000 < 0.3


def test_weighted_single_item():
    assert bc.weighted(random.Random(0), [("only", 2)]) == "only"


def test_jitter_zero_is_identity():
    c = (0.2, 0.5, 0.7)
    assert bc.jitter(c, random.Random(0), {"hue": 0, "sat": 0, "val": 0}) == pytest.approx(c)


def test_jitter_stays_in_range():
    rng = random.Random(0)
    for _ in range(200):
        out = bc.jitter((1, 1, 0), rng, {"hue": 0.5, "sat": 0.5, "val": 0.5})
        assert all(0 <= x <= 1 for x in out)


# ---------------------------------------------------------- tiny geometry & anatomy


@pytest.fixture
def setup(bare_project):
    """(cfg, paths, geo with anatomy, base image, protect set, shade map) for the tiny cat."""
    cfg, paths = bare_project.cfg, bare_project.paths
    geo = common.load_geometry(paths.geometry, cfg["entity"]["geometry"], cfg["anatomy"]["rest_pose"])
    bc.compute_anatomy(geo, cfg)
    base = Image.open(paths.base_texture).convert("RGBA")
    protect = bc.build_protect_mask(base, geo, cfg, paths)
    shade = bc.shading_map(base, geo, protect, cfg)
    return cfg, paths, geo, base, protect, shade


WEIGHTS = ("ventral", "chest", "paw", "leg_low", "legs", "face", "lower_face", "muzzle", "ears", "tail")


def test_anatomy_weights_are_filled_and_bounded(setup):
    _cfg, _paths, geo, *_ = setup
    for t in geo.texels.values():
        assert set(WEIGHTS) <= set(t.w)
        for k in (*WEIGHTS, "tail_tip", "blaze", "dorsal", "length"):
            assert 0 <= t.w[k] <= 1, (k, t)
        assert t.w["nose_dist"] >= 0


@pytest.mark.parametrize(
    ("bone", "cube", "weight"),
    [("head", 2, "ears"), ("head", 1, "muzzle"), ("leg", 0, "legs"), ("tail", 0, "tail")],
)
def test_anatomy_marks_body_parts(setup, bone, cube, weight):
    _cfg, _paths, geo, *_ = setup
    texels = [t for t in geo.texels.values() if (t.bone, t.cube) == (bone, cube)]
    assert texels
    assert all(t.w[weight] == 1.0 for t in texels)
    others = [t for t in geo.texels.values() if (t.bone, t.cube) != (bone, cube)]
    assert all(t.w[weight] == 0.0 for t in others)


def test_anatomy_face_and_belly(setup):
    _cfg, _paths, geo, *_ = setup
    face = [t for t in geo.texels.values() if t.bone == "head" and t.cube == 0 and t.face == "north"]
    assert all(t.w["face"] == 1.0 for t in face)
    belly = [t for t in geo.texels.values() if t.bone == "body" and t.face == "down"]
    back = [t for t in geo.texels.values() if t.bone == "body" and t.face == "up"]
    assert min(t.w["ventral"] for t in belly) > max(t.w["ventral"] for t in back)
    paws = [t for t in geo.texels.values() if t.bone == "leg" and t.face == "down"]
    assert all(t.w["paw"] == 1.0 for t in paws)


def test_stripe_coord_by_part(setup):
    cfg, _paths, geo, *_ = setup
    body = next(t for t in geo.texels.values() if t.bone == "body")
    leg = next(t for t in geo.texels.values() if t.bone == "leg")
    forehead = next(t for t in geo.texels.values() if t.bone == "head" and t.cube == 0 and t.face == "up")
    assert bc.stripe_coord(body, cfg) == body.P[2]
    assert bc.stripe_coord(leg, cfg) == leg.P[1]
    assert bc.stripe_coord(forehead, cfg) == pytest.approx(forehead.P[0] * 1.6)


# -------------------------------------------------------------------------- patterns


@pytest.mark.parametrize("name", sorted(bc.PATTERNS))
def test_pattern_gives_valid_deterministic_colours(setup, name):
    cfg, _paths, geo, *_ = setup
    pal = bc.Pal((0.6, 0.4, 0.2), (0.2, 0.1, 0.05), (0.9, 0.8, 0.7), (1, 1, 1))
    settings = cfg["pattern_settings"].get(name, {})
    f1 = bc.PATTERNS[name](random.Random(5), pal, settings, cfg)
    f2 = bc.PATTERNS[name](random.Random(5), pal, settings, cfg)
    cols = [f1(t) for t in geo.texels.values()]
    assert cols == [f2(t) for t in geo.texels.values()]
    assert all(len(c) == 3 and all(0 <= x <= 1 for x in c) for c in cols)


def test_modifiers_skip_conflicting_ones():
    cfg = {"modifiers": {"white_paws": 1.0, "white_blaze": 1.0, "light_belly": 1.0, "white_tail_tip": 1.0}}
    pal = bc.Pal((0.5,) * 3, (0.1,) * 3, (0.9,) * 3, (1, 1, 1))
    mods, _ = bc.apply_modifiers(random.Random(0), "tuxedo", pal, cfg)
    assert mods == ["white_tail_tip"]
    mods, _ = bc.apply_modifiers(random.Random(0), "tabby", pal, cfg)
    assert mods == sorted(cfg["modifiers"])


def test_modifier_white_paws(setup):
    _cfg, _paths, geo, *_ = setup
    pal = bc.Pal((0.5,) * 3, (0.1,) * 3, (0.9,) * 3, (1, 1, 1))
    _, f = bc.apply_modifiers(random.Random(0), "solid", pal, {"modifiers": {"white_paws": 1.0}})
    paw = next(t for t in geo.texels.values() if t.w["paw"] > 0.5)
    back = next(t for t in geo.texels.values() if t.bone == "body" and t.face == "up")
    assert f(paw, (0, 0, 0)) == (1, 1, 1)
    assert f(back, (0, 0, 0)) == (0, 0, 0)


# ----------------------------------------------------------------------- protection


def test_protect_mask_finds_eyes(setup, synth):
    _cfg, _paths, _geo, base, protect, _shade = setup
    visible = {k for k in protect if base.getpixel(k)[3] > 0}
    assert visible == set(synth.EYE_PIXELS)


def test_protect_mask_adds_transparent_model_pixels(setup):
    cfg, paths, geo, base, *_ = setup
    hole = next(k for k, t in geo.texels.items() if t.bone == "body")
    base = base.copy()
    base.putpixel(hole, (0, 0, 0, 0))
    assert hole in bc.build_protect_mask(base, geo, cfg, paths)


def test_protect_mask_file_is_added(setup, synth):
    cfg, paths, geo, base, *_ = setup
    mask = Image.new("L", base.size, 0)
    mask.putpixel((10, 5), 255)
    paths.protect_mask.parent.mkdir(parents=True, exist_ok=True)
    mask.save(paths.protect_mask)
    assert bc.build_protect_mask(base, geo, cfg, paths) == {*synth.EYE_PIXELS, (10, 5)}


def test_protect_mask_file_wrong_size(setup):
    cfg, paths, geo, base, *_ = setup
    paths.protect_mask.parent.mkdir(parents=True, exist_ok=True)
    Image.new("L", (8, 8)).save(paths.protect_mask)
    with pytest.raises(BuildError, match=r"protect_mask\.png is \(8, 8\), expected \(32, 32\)"):
        bc.build_protect_mask(base, geo, cfg, paths)


def test_shading_map_bounds(setup):
    cfg, _paths, geo, _base, _protect, shade = setup
    sc = cfg["shading"]
    assert set(shade) == set(geo.texels)
    assert all(sc["min"] <= v <= sc["max"] for v in shade.values())
    assert len(set(shade.values())) > 1  # the base texture's light/dark fur shows through


# -------------------------------------------------------------------- collar & tame


def test_load_collar(setup, synth):
    _cfg, paths, geo, *_ = setup
    collar = bc.load_collar(paths, geo)
    assert set(collar) == set(synth.COLLAR_PIXELS)
    assert all(c == (200, 30, 30) for c in collar.values())


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda im: im.resize((16, 16)), r"is \(16, 16\), expected \(32, 32\)"),
        (lambda im: Image.new("RGBA", im.size, (0, 0, 0, 4)), "no collar pixels"),
        (
            lambda im: (im.putpixel((31, 31), (1, 1, 1, 255)), im)[1],
            r"collar pixels \[\(31, 31\)\] are not on the model",
        ),
    ],
    ids=["wrong-size", "no-collar", "collar-off-model"],
)
def test_load_collar_errors(setup, edit, message):
    _cfg, paths, geo, *_ = setup
    edit(Image.open(paths.tame_reference).convert("RGBA")).save(paths.tame_reference)
    with pytest.raises(BuildError, match=message):
        bc.load_collar(paths, geo)


def test_make_tame_sets_alpha_mask():
    coat = Image.new("RGBA", (4, 4), (10, 20, 30, 255))
    coat.putpixel((3, 3), (0, 0, 0, 0))
    collar = {(0, 0): (200, 0, 0), (1, 0): (201, 0, 0)}
    tame = bc.make_tame(coat, collar, {"tame": {"fur_alpha": 4, "collar_alpha": 255}})
    assert tame.getpixel((0, 0)) == (200, 0, 0, 255)
    assert tame.getpixel((1, 0)) == (201, 0, 0, 255)
    assert tame.getpixel((2, 2)) == (10, 20, 30, 4)
    assert tame.getpixel((3, 3)) == (0, 0, 0, 0)  # uncovered stays transparent
    assert coat.getpixel((0, 0)) == (10, 20, 30, 255)  # input untouched


# -------------------------------------------------------------------------- layers


def test_load_layers_none(bare_project):
    assert bc.load_layers(bare_project.paths, (32, 32)) == []


def test_load_layers_sizes_and_ignores(bare_project):
    d = bare_project.paths.coat_layers
    d.mkdir(parents=True)
    Image.new("RGBA", (32, 32), (1, 0, 0, 255)).save(d / "b_exact.png")
    big = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    for p in ((2, 2), (3, 2), (2, 3), (3, 3)):  # one 2x2 block = one texture pixel
        big.putpixel(p, (255, 0, 0, 255))
    big.save(d / "a_double.png")
    Image.new("RGBA", (5, 5)).save(d / "_ignored.png")
    (d / "notes.txt").write_text("x", encoding="utf-8")
    layers = bc.load_layers(bare_project.paths, (32, 32))
    assert [n for n, _ in layers] == ["a_double.png", "b_exact.png"]
    assert all(im.size == (32, 32) for _, im in layers)
    assert layers[0][1].getpixel((1, 1)) == (255, 0, 0, 255)  # nearest-neighbour shrink


@pytest.mark.parametrize("size", [(48, 48), (64, 32), (16, 16)])
def test_load_layers_rejects_bad_sizes(bare_project, size):
    d = bare_project.paths.coat_layers
    d.mkdir(parents=True)
    Image.new("RGBA", size).save(d / "bad.png")
    with pytest.raises(BuildError, match="layers must be 32x32 or an exact multiple"):
        bc.load_layers(bare_project.paths, (32, 32))


# ------------------------------------------------------------------------ make_coat


def _coat(setup, i, layers=(), **cfg_changes):
    cfg, _paths, geo, base, protect, shade = setup
    cfg = {**cfg, **cfg_changes}
    return bc.make_coat(i, cfg, geo, base, protect, shade, list(layers))


def test_make_coat_is_deterministic(setup):
    a, ma = _coat(setup, 2)
    b, mb = _coat(setup, 2)
    assert a.tobytes() == b.tobytes()
    assert ma == mb
    assert ma["index"] == 2
    assert ma["name"] == "coat_002"


def test_make_coat_differs_by_index_and_seed(setup):
    imgs = {_coat(setup, i)[0].tobytes() for i in range(6)}
    assert len(imgs) == 6
    assert _coat(setup, 0)[0].tobytes() != _coat(setup, 0, seed=12345)[0].tobytes()


def test_make_coat_keeps_protected_and_uncovered_pixels(setup):
    _cfg, _paths, geo, base, protect, _shade = setup
    img, _ = _coat(setup, 1)
    assert img.size == base.size
    for k in protect:
        assert img.getpixel(k) == base.getpixel(k)
    for y in range(base.height):
        for x in range(base.width):
            if (x, y) not in geo.texels:
                assert img.getpixel((x, y)) == base.getpixel((x, y))
    assert all(img.getpixel(k)[3] == 255 for k in geo.texels if k not in protect)


@pytest.mark.parametrize("pattern", sorted(bc.PATTERNS))
def test_make_coat_each_pattern(setup, pattern):
    cfg = setup[0]
    img, meta = _coat(setup, 0, pattern_weights={pattern: 1})
    assert img.size == (32, 32)
    assert meta["pattern"] == pattern
    pal = next(p for p in cfg["palettes"] if p["name"] == meta["palette"])
    assert pattern in pal.get("patterns", [pattern])


def test_make_coat_unknown_pattern(setup):
    with pytest.raises(BuildError, match="unknown pattern 'plaid'"):
        _coat(setup, 0, pattern_weights={"plaid": 1})


def test_make_coat_no_palette_for_pattern(setup):
    pal = {"name": "only_calico", "base": "brown", "dark": "black", "light": "cream", "patterns": ["calico"]}
    with pytest.raises(BuildError, match="no palette allows pattern 'solid'"):
        _coat(setup, 0, pattern_weights={"solid": 1}, palettes=[pal])


def test_make_coat_unknown_palette_colour(setup):
    pal = {"name": "bad", "base": "brown", "dark": "nonexistent", "light": "cream"}
    with pytest.raises(BuildError, match="palette 'bad' uses unknown color 'nonexistent'"):
        _coat(setup, 0, palettes=[pal])


def test_make_coat_applies_layer(setup):
    _cfg, _paths, geo, _base, protect, _shade = setup
    layer = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    spot = next(k for k, t in geo.texels.items() if t.bone == "body" and k not in protect)
    layer.putpixel(spot, (0, 0, 255, 255))
    img, meta = _coat(setup, 0, [("kid.png", layer)], coat_layers={"chance": 1.0})
    assert meta["layer"] == "kid.png"
    r, g, b, _a = img.getpixel(spot)
    assert b > 150
    assert max(r, g) < 30
    _img, meta = _coat(setup, 0, [("kid.png", layer)], coat_layers={"chance": 0.0})
    assert meta["layer"] is None


def test_adding_a_layer_does_not_reshuffle_coats(setup):
    """Layers use their own random stream: the coat's pattern/palette don't change."""
    layer = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    for i in range(5):
        _img, plain = _coat(setup, i)
        _img, layered = _coat(setup, i, [("kid.png", layer)], coat_layers={"chance": 1.0})
        assert {k: v for k, v in plain.items() if k != "layer"} == {k: v for k, v in layered.items() if k != "layer"}


# --------------------------------------------------------------------- full build


def test_build_coats_outputs(project):
    n = project.cfg["coat_count"]
    coat_dir = project.paths.coat_dir_abs
    assert sorted(p.name for p in coat_dir.glob("*.png")) == [common.coat_name(i) + ".png" for i in range(n)]
    assert sorted(p.name for p in coat_dir.glob("*.tga")) == [common.tame_name(i) + ".tga" for i in range(n)]
    manifest = json.loads((project.paths.build / "coats_manifest.json").read_text(encoding="utf-8"))
    assert manifest["seed"] == project.cfg["seed"]
    assert [m["index"] for m in manifest["coats"]] == list(range(n))
    assert all(m["pattern"] in bc.PATTERNS for m in manifest["coats"])
    for name in ("coat_preview.png", "uv_template.png"):
        with Image.open(project.paths.build / name) as im:
            assert im.width > 100


def test_build_coats_tame_files_carry_collar_mask(project, synth):
    with Image.open(project.paths.coat_dir_abs / "coat_000_tame.tga") as im:
        im = im.convert("RGBA")
        alphas = {im.getpixel(p)[3] for p in synth.COLLAR_PIXELS}
        assert alphas == {255}
        assert im.getpixel((10, 5))[3] == project.cfg["tame"]["fur_alpha"]


def test_build_coats_is_deterministic_and_wipes_orphans(bare_project, capsys):
    coat_dir = bare_project.paths.coat_dir_abs
    coat_dir.mkdir(parents=True)
    (coat_dir / "coat_999.png").write_bytes(b"stale")
    metas = bc.build_coats()
    assert not (coat_dir / "coat_999.png").exists()
    out = capsys.readouterr().out
    assert "protected pixels" in out
    assert f"wrote {bare_project.cfg['coat_count']} coats" in out
    first = {p.name: p.read_bytes() for p in coat_dir.iterdir()}
    assert bc.build_coats(verbose=False) == metas
    assert {p.name: p.read_bytes() for p in coat_dir.iterdir()} == first


def test_build_coats_rejects_wrong_base_size(bare_project):
    Image.new("RGBA", (16, 16), (1, 1, 1, 255)).save(bare_project.paths.base_texture)
    with pytest.raises(BuildError, match=r"cat_base\.png is \(16, 16\), geometry expects \(32, 32\)"):
        bc.build_coats(verbose=False)


def test_build_coats_needs_protected_pixels(bare_project):
    Image.new("RGBA", (32, 32), (100, 100, 100, 255)).save(bare_project.paths.base_texture)
    with pytest.raises(BuildError, match="no protected pixels found"):
        bc.build_coats(verbose=False)


def test_build_coats_rejects_too_many_protected_pixels(bare_project):
    im = Image.new("RGBA", (32, 32), (100, 100, 100, 255))
    for x in range(14):
        for y in range(10, 17):
            im.putpixel((x, y), (x * 10, y * 10, 3, 255))  # the head in colours the body never uses
    im.save(bare_project.paths.base_texture)
    with pytest.raises(BuildError, match="suspiciously many"):
        bc.build_coats(verbose=False)
