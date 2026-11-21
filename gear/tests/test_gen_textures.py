"""gen_textures: luminance gradient, recolor and goggle painting on tiny synthetic images."""

from __future__ import annotations

import pytest
from PIL import Image

import gen_textures
from common import BuildError
from gen_textures import _gradient, _lum, paint_goggles_icon, paint_goggles_layer, recolor

STOPS = [(0.0, (0, 0, 0)), (0.5, (100, 50, 200)), (1.0, (250, 250, 250))]
NO_SPARKLE = {"stops": [[t, list(c)] for t, c in STOPS], "sparkle_every": 0, "sparkle_strength": 0.0}


@pytest.mark.parametrize(
    ("color", "expected"),
    [((0, 0, 0), 0.0), ((255, 255, 255), 255.0), ((255, 0, 0), 0.299 * 255), ((0, 255, 0, 7), 0.587 * 255)],
)
def test_lum(color, expected):
    assert _lum(color) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("t", "expected"),
    [
        pytest.param(0.0, (0, 0, 0), id="start"),
        pytest.param(0.25, (50, 25, 100), id="first-segment-mid"),
        pytest.param(0.5, (100, 50, 200), id="exact-stop"),
        pytest.param(0.75, (175, 150, 225), id="second-segment-mid"),
        pytest.param(1.0, (250, 250, 250), id="end"),
        pytest.param(-3.0, (0, 0, 0), id="clamped-low"),
        pytest.param(7.0, (250, 250, 250), id="clamped-high"),
    ],
)
def test_gradient(t, expected):
    assert _gradient(STOPS, t) == expected


def test_gradient_duplicate_stop_does_not_divide_by_zero():
    stops = [(0.0, (0, 0, 0)), (0.5, (10, 10, 10)), (0.5, (200, 200, 200)), (1.0, (255, 255, 255))]
    assert _gradient(stops, 0.5) == (10, 10, 10)
    assert _gradient(stops, 0.75) == (228, 228, 228)


def _ramp(width: int = 8, alpha=lambda x: 255) -> Image.Image:
    im = Image.new("RGBA", (width, 1))
    for x in range(width):
        g = x * 255 // (width - 1)
        im.putpixel((x, 0), (g, g, g, alpha(x)))
    return im


def test_recolor_maps_luminance_range_onto_output_range():
    out = recolor(_ramp(), NO_SPARKLE, [0.0, 1.0])
    assert out.getpixel((0, 0)) == (0, 0, 0, 255)
    assert out.getpixel((7, 0)) == (250, 250, 250, 255)
    out = recolor(_ramp(), NO_SPARKLE, [0.5, 1.0])
    assert out.getpixel((0, 0)) == (100, 50, 200, 255)


def test_recolor_is_monotonic_in_luminance():
    out = recolor(_ramp(16), NO_SPARKLE, [0.0, 1.0])
    lums = [_lum(out.getpixel((x, 0))) for x in range(16)]
    assert lums == sorted(lums)


def test_recolor_preserves_alpha_and_transparency():
    src = _ramp(8, alpha=lambda x: 0 if x % 3 == 0 else 40 * x)
    out = recolor(src, NO_SPARKLE, [0.0, 1.0])
    assert out.mode == "RGBA"
    assert out.size == src.size
    for x in range(8):
        a = src.getpixel((x, 0))[3]
        assert out.getpixel((x, 0))[3] == a
        if a == 0:
            assert out.getpixel((x, 0)) == (0, 0, 0, 0)


def test_recolor_ignores_transparent_pixels_for_range():
    # a white but fully transparent pixel must not stretch the luminance range
    src = Image.new("RGBA", (3, 1))
    src.putpixel((0, 0), (10, 10, 10, 255))
    src.putpixel((1, 0), (20, 20, 20, 255))
    src.putpixel((2, 0), (255, 255, 255, 0))
    out = recolor(src, NO_SPARKLE, [0.0, 1.0])
    assert out.getpixel((1, 0)) == (250, 250, 250, 255)


def test_recolor_uniform_image_uses_range_start():
    src = Image.new("RGBA", (4, 4), (90, 90, 90, 200))
    out = recolor(src, NO_SPARKLE, [0.5, 1.0])
    assert {out.getpixel((x, y)) for x in range(4) for y in range(4)} == {(100, 50, 200, 200)}


def test_recolor_converts_non_rgba_input():
    src = Image.new("L", (2, 1))
    src.putpixel((1, 0), 255)
    out = recolor(src, NO_SPARKLE, [0.0, 1.0])
    assert out.mode == "RGBA"
    assert out.getpixel((1, 0)) == (250, 250, 250, 255)


def test_recolor_fully_transparent_raises():
    with pytest.raises(BuildError, match="fully transparent"):
        recolor(Image.new("RGBA", (4, 4), (255, 255, 255, 0)), NO_SPARKLE, [0.0, 1.0])


def test_recolor_is_deterministic_and_does_not_touch_source():
    src = _ramp(16)
    before = src.tobytes()
    pal = {**NO_SPARKLE, "sparkle_every": 3, "sparkle_strength": 0.5}
    assert recolor(src, pal, [0.0, 1.0]).tobytes() == recolor(src, pal, [0.0, 1.0]).tobytes()
    assert src.tobytes() == before


def test_sparkle_lifts_only_bright_lattice_pixels():
    w, h, every = 12, 12, 5
    src = Image.new("RGBA", (w, h))
    for y in range(h):
        for x in range(w):
            g = (x + y) * 255 // (w + h - 2)
            src.putpixel((x, y), (g, g, g, 255))
    plain = recolor(src, NO_SPARKLE, [0.0, 1.0])
    sparkly = recolor(src, {**NO_SPARKLE, "sparkle_every": every, "sparkle_strength": 1.0}, [0.0, 1.0])
    changed = {(x, y) for y in range(h) for x in range(w) if plain.getpixel((x, y)) != sparkly.getpixel((x, y))}
    assert changed, "expected some glint pixels"
    for x, y in changed:
        assert (x * 3 + y * 5) % every == 0
        t = (x + y) / (w + h - 2)
        assert t >= 0.59
        # strength 1.0 -> exactly the highlight (last stop), alpha untouched
        assert sparkly.getpixel((x, y)) == (250, 250, 250, 255)


# --------------------------------------------------------------------------- goggles


def test_paint_goggles_layer_paints_front_and_strap_only():
    im = Image.new("RGBA", (64, 32), (1, 2, 3, 255))
    paint_goggles_layer(im)
    assert im.getpixel((8, 10)) == gen_textures.FRAME
    assert im.getpixel((9, 11)) == gen_textures.LENS_HI
    assert im.getpixel((10, 12)) == gen_textures.LENS_DARK
    assert im.getpixel((8, 13)) == (1, 2, 3, 255)  # None entries leave the source pixel
    for x in (0, 7, 16, 31):
        assert im.getpixel((x, 11)) == gen_textures.STRAP
    # outside the head box nothing changes
    for xy in ((40, 11), (8, 9), (8, 14), (0, 0), (63, 31)):
        assert im.getpixel(xy) == (1, 2, 3, 255)


@pytest.mark.parametrize("size", [(16, 16), (64, 64), (128, 64)])
def test_paint_goggles_layer_rejects_wrong_size(size):
    with pytest.raises(BuildError, match="64x32"):
        paint_goggles_layer(Image.new("RGBA", size))


def test_paint_goggles_icon():
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    paint_goggles_icon(im)
    assert all(im.getpixel((x, 7)) == gen_textures.FRAME for x in range(3, 13))
    assert im.getpixel((4, 8)) == gen_textures.LENS_HI
    assert im.getpixel((6, 9)) == gen_textures.LENS_DARK
    painted = {(x, y) for y in range(16) for x in range(16) if im.getpixel((x, y))[3]}
    assert {y for _, y in painted} == {7, 8, 9, 10}
    assert {x for x, _ in painted} == set(range(3, 13))


# --------------------------------------------------------------------------- build_textures (tmp project)


def test_build_textures_outputs(project):
    rp = project.rp
    layer = rp / "textures/gear/armor/test_1.png"
    icons = [rp / "textures/gear/items/test_helmet.png", rp / "textures/gear/items/test_boots.png"]
    with Image.open(layer) as im:
        assert (im.mode, im.size) == ("RGBA", (64, 32))
    for p in icons:
        with Image.open(p) as im:
            assert (im.mode, im.size) == ("RGBA", (16, 16))
    for pack in (project.bp, project.rp):
        with Image.open(pack / "pack_icon.png") as im:
            assert im.size == (128, 128)
    assert (project.root / "build" / "armor_preview.png").is_file()


def test_build_textures_removes_stale_pngs_and_is_reproducible(project):
    stale = project.rp / "textures/gear/items/old_piece.png"
    Image.new("RGBA", (16, 16)).save(stale)
    icon = project.rp / "textures/gear/items/test_helmet.png"
    before = icon.read_bytes()
    gen_textures.build_textures()
    assert not stale.exists()
    assert icon.read_bytes() == before


def test_build_textures_goggles_variants(project, base_config):
    base_config["layers"]["goggles"] = {"source": "diamond_1.png", "goggles": True}
    base_config["pieces"][0]["layer"] = "goggles"
    base_config["pieces"][0]["icon_goggles"] = True
    project.write_config(base_config)
    out = gen_textures.build_textures()
    assert set(out) == {"layer:test_1", "layer:goggles", "icon:test_helmet", "icon:test_boots"}
    with Image.open(out["layer:goggles"]) as im:
        assert im.getpixel((8, 10)) == gen_textures.FRAME
    with Image.open(out["icon:test_helmet"]) as im:
        assert im.getpixel((3, 7)) == gen_textures.FRAME


def test_build_textures_missing_source(project):
    (project.root / "vanilla" / "diamond_boots.png").unlink()
    with pytest.raises(BuildError, match=r"diamond_boots\.png: source texture missing"):
        gen_textures.build_textures()
