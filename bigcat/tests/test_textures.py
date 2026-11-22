"""The pixel-art item/entity textures drawn in code: gen_laser, gen_orb, gen_wand, gen_grapple."""

from __future__ import annotations

import pytest
from PIL import Image

import gen_air_cannon
import gen_drowned_trap
import gen_grapple
import gen_laser
import gen_orb
import gen_wand
from common import BuildError

MAKERS = {
    "laser_icon": gen_laser._icon,
    "laser_dot": gen_laser._dot,
    "cat_orb": gen_orb._empty,
    "cat_orb_full": gen_orb._full,
    "creature_orb": gen_orb._creature_empty,
    "creature_orb_full": gen_orb._creature_full,
    "trap_orb": gen_orb._trap_empty,
    "trap_orb_full": gen_orb._trap_full,
    "size_wand": lambda: gen_wand._wand(gen_wand.SIZE_TIP),
    "vapor_wand": lambda: gen_wand._wand(gen_wand.VAPOR_TIP),
    "grappling_gun": gen_grapple._icon,
    "grapple_hook": gen_grapple._hook,
    "drowned_trap": gen_drowned_trap._icon,
    "air_cannon": gen_air_cannon._icon,
}
ICONS = [k for k in MAKERS if k not in ("laser_dot", "grapple_hook")]  # item icons have transparent backgrounds


def pixels(im: Image.Image) -> list[tuple]:
    return [im.getpixel((x, y)) for y in range(im.height) for x in range(im.width)]


@pytest.mark.parametrize("name", MAKERS)
def test_texture_is_16x16_rgba_and_not_empty(name):
    im = MAKERS[name]()
    assert im.size == (16, 16)
    assert im.mode == "RGBA"
    assert im.getbbox() is not None
    assert len(set(pixels(im))) >= 2


@pytest.mark.parametrize("name", MAKERS)
def test_texture_is_deterministic(name):
    assert MAKERS[name]().tobytes() == MAKERS[name]().tobytes()


@pytest.mark.parametrize("name", ICONS)
def test_icon_has_transparent_corners(name):
    im = MAKERS[name]()
    for corner in ((0, 0), (15, 0), (0, 15), (15, 15)):
        assert im.getpixel(corner)[3] == 0
    assert any(px[3] == 0 for px in pixels(im))


def test_all_textures_are_distinct():
    blobs = [make().tobytes() for make in MAKERS.values()]
    assert len(set(blobs)) == len(blobs)


def test_laser_dot_is_fully_opaque_red():
    im = gen_laser._dot()
    assert {px[3] for px in pixels(im)} == {255}
    assert all(r > 200 for r, _g, _b, _a in pixels(im))


@pytest.mark.parametrize(
    ("grid", "palette"),
    [
        (gen_laser.ICON, gen_laser.COLORS),
        (gen_orb.CAT, {"C", "E"}),
        (gen_orb.PAW, {"P"}),
        (gen_orb.FIGURE, {"H", "B"}),
        (gen_wand.SIZE_TIP, gen_wand.TIP_COLORS),
        (gen_wand.VAPOR_TIP, gen_wand.TIP_COLORS),
        (gen_grapple.ICON, gen_grapple.COLORS),
        (gen_air_cannon.ICON, gen_air_cannon.COLORS),
    ],
    ids=["laser", "cat", "paw", "figure", "size_tip", "vapor_tip", "grapple", "air_cannon"],
)
def test_pixel_grids_are_well_formed(grid, palette):
    assert all(len(row) == 16 for row in grid)
    assert len(grid) <= 16
    used = {ch for row in grid for ch in row} - {"."}
    assert used <= set(palette)


def test_laser_icon_rejects_bad_grid(monkeypatch):
    monkeypatch.setattr(gen_laser, "ICON", gen_laser.ICON[:-1])
    with pytest.raises(BuildError, match="16 rows of 16 characters"):
        gen_laser._icon()


@pytest.mark.parametrize(
    ("full", "plain"),
    [
        (gen_orb._full, lambda: gen_orb._orb((150, 70, 20), (255, 196, 96), 255)),
        (gen_orb._creature_full, lambda: gen_orb._orb((24, 110, 56), (140, 236, 150), 255, gen_orb.SILVER)),
        (gen_orb._trap_full, lambda: gen_orb._orb((120, 16, 26), (255, 120, 104), 255, gen_orb.RED)),
    ],
    ids=["cat", "creature", "trap"],
)
def test_full_orbs_draw_occupant_behind_band(full, plain):
    """The occupant changes the orb, but never the band (rows 8-9) in front of it."""
    f, p = full(), plain()
    assert f.tobytes() != p.tobytes()
    for x in range(16):
        for y in (8, 9):
            assert f.getpixel((x, y)) == p.getpixel((x, y))


def test_orb_specular_highlight():
    for make in (gen_orb._empty, gen_orb._full, gen_orb._trap_full):
        assert make().getpixel((4, 4)) == (255, 255, 255, 255)


# ----------------------------------------------------------- writing into a pack folder

GENERATORS = [
    (gen_laser.generate_laser_textures, [gen_laser.ITEM_TEXTURE, gen_laser.DOT_TEXTURE]),
    (gen_orb.generate_orb_textures, gen_orb.ALL_TEXTURES),
    (gen_wand.generate_wand_textures, gen_wand.ALL_TEXTURES),
    (gen_grapple.generate_grapple_textures, gen_grapple.ALL_TEXTURES),
    (gen_air_cannon.generate_air_cannon_textures, gen_air_cannon.ALL_TEXTURES),
]


@pytest.mark.parametrize(("generate", "textures"), GENERATORS, ids=["laser", "orb", "wand", "grapple", "air_cannon"])
def test_generators_write_pngs_into_rp(bare_project, capsys, generate, textures):
    generate()
    out = capsys.readouterr().out
    for tex in textures:
        p = bare_project.rp / (tex + ".png")
        with Image.open(p) as im:
            assert im.size == (16, 16)
        assert f"big_cat_rp/{tex}.png" in out


@pytest.mark.parametrize(("generate", "textures"), GENERATORS, ids=["laser", "orb", "wand", "grapple", "air_cannon"])
def test_generators_are_byte_stable(bare_project, generate, textures):
    generate(verbose=False)
    first = [(bare_project.rp / (t + ".png")).read_bytes() for t in textures]
    generate(verbose=False)
    assert [(bare_project.rp / (t + ".png")).read_bytes() for t in textures] == first


def test_orb_texture_list_matches_names():
    assert gen_orb.ALL_TEXTURES[:2] == [gen_orb.EMPTY_TEXTURE, gen_orb.FULL_TEXTURE]
    assert len(set(gen_orb.ALL_TEXTURES)) == 6


def test_grapple_icon_rejects_bad_grid(monkeypatch):
    monkeypatch.setattr(gen_grapple, "ICON", gen_grapple.ICON[:-1])
    with pytest.raises(BuildError, match="16 rows of 16 characters"):
        gen_grapple._icon()


def test_grapple_hook_texture_is_opaque():
    assert {px[3] for px in pixels(gen_grapple._hook())} == {255}


def test_drowned_trap_icon_grid_is_well_formed():
    grid = gen_drowned_trap.ICON
    assert len(grid) == 16
    assert all(len(row) == 16 for row in grid)
    assert {ch for row in grid for ch in row} - {"."} <= set(gen_drowned_trap.COLORS)


def test_drowned_lure_texture_is_32x32_with_see_through_cage():
    im = gen_drowned_trap._lure()
    assert im.size == (32, 32)
    assert im.getpixel((11, 3))[3] == 0  # gap between bars
    assert im.getpixel((8, 0))[3] == 255  # frame
    assert im.getpixel((1, 17))[3] == 255  # bait fish


def test_generate_drowned_trap_writes_textures_and_patched_drowned(project):
    import common

    gen_drowned_trap.generate_drowned_trap(verbose=False)
    for tex in gen_drowned_trap.ALL_TEXTURES:
        assert (project.rp / (tex + ".png")).is_file()
    doc = common.load_json(project.bp / "entities" / "drowned.json")
    types = doc["minecraft:entity"]["components"][gen_drowned_trap.TARGET_GOAL]["entity_types"]
    assert types[0] == gen_drowned_trap.TRAP_TARGET
    assert len(types) == 2  # the vanilla target is kept


def test_patch_drowned_requires_target_goal(project):
    from common import BuildError

    (project.root / "vanilla" / "drowned.json").write_text('{"minecraft:entity": {"components": {}}}', encoding="utf-8")
    with pytest.raises(BuildError, match=r"has no minecraft:behavior\.nearest_attackable_target"):
        gen_drowned_trap.patch_drowned()
