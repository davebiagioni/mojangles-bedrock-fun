"""Generate every texture in gear_rp from the vanilla diamond textures in art/vanilla/.

The diamond armor is recolored by luminance onto an amethyst gradient (tools/gear_config.json
"palette"), so the shading and silhouette stay exactly vanilla. A sparse, deterministic set of
bright pixels is pushed toward the pale-pink highlight colour for a subtle crystalline glint.
The Geode Goggles get a goggle band painted over the helmet part of the layer and icon.

Also writes build/armor_preview.png and both pack_icon.png files.

Run standalone:  python tools/gen_textures.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

from common import BuildError, load_config, rel

# goggle colours
FRAME = (40, 22, 66, 255)
STRAP = (66, 40, 60, 255)
LENS = (178, 128, 250, 255)
LENS_HI = (250, 232, 255, 255)
LENS_DARK = (112, 72, 182, 255)


def _lum(c) -> float:
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def _gradient(stops, t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            f = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            return tuple(round(a + (b - a) * f) for a, b in zip(c0, c1))
    return tuple(stops[-1][1])


def recolor(src: Image.Image, palette: dict, out_range: list[float]) -> Image.Image:
    im = src.convert("RGBA")
    px = im.load()
    w, h = im.size
    opaque = [(x, y) for y in range(h) for x in range(w) if px[x, y][3] > 0]
    if not opaque:
        raise BuildError("source texture is fully transparent")
    lums = [_lum(px[x, y]) for x, y in opaque]
    lo, hi = min(lums), max(lums)
    r0, r1 = out_range
    stops = [(float(t), tuple(c)) for t, c in palette["stops"]]
    highlight = stops[-1][1]
    every, strength = int(palette["sparkle_every"]), float(palette["sparkle_strength"])
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    opx = out.load()
    for (x, y), l in zip(opaque, lums):
        t = 0.0 if hi == lo else (l - lo) / (hi - lo)
        t = r0 + t * (r1 - r0)
        c = _gradient(stops, t)
        # crystalline glint: a sparse diagonal lattice of mid/bright pixels gets lifted toward the highlight
        if every > 0 and t >= 0.6 and (x * 3 + y * 5) % every == 0:
            c = tuple(round(a + (b - a) * strength) for a, b in zip(c, highlight))
        opx[x, y] = (*c, px[x, y][3])
    return out


def paint_goggles_layer(im: Image.Image) -> None:
    """Goggle band on the helmet cube of a 64x32 armor layer (head box uv 0,0 size 8x8x8)."""
    if im.size != (64, 32):
        raise BuildError(f"goggles layer must be 64x32, got {im.size}")
    px = im.load()
    # front (north) face spans x 8..15, y 8..15; vanilla eye holes are on rows 11-12
    front = {
        10: [FRAME] * 8,
        11: [FRAME, LENS_HI, LENS, FRAME, FRAME, LENS_HI, LENS, FRAME],
        12: [FRAME, LENS, LENS_DARK, FRAME, FRAME, LENS, LENS_DARK, FRAME],
        13: [None, FRAME, FRAME, None, None, FRAME, FRAME, None],
    }
    for y, row in front.items():
        for i, c in enumerate(row):
            if c:
                px[8 + i, y] = c
    # strap around the west (x 0..7), east (16..23) and back (24..31) faces
    for y in (11, 12):
        for x in list(range(0, 8)) + list(range(16, 32)):
            px[x, y] = STRAP


def paint_goggles_icon(im: Image.Image) -> None:
    """Goggle band across a 16x16 helmet icon (helmet body spans x 3..12, y 3..11)."""
    px = im.load()
    for x in range(3, 13):
        px[x, 7] = FRAME
    row8 = [FRAME, LENS_HI, LENS, LENS, FRAME, FRAME, LENS_HI, LENS, LENS, FRAME]
    row9 = [FRAME, LENS, LENS, LENS_DARK, FRAME, FRAME, LENS, LENS, LENS_DARK, FRAME]
    for i in range(10):
        px[3 + i, 8] = row8[i]
        px[3 + i, 9] = row9[i]
    for x in (4, 5, 6, 9, 10, 11):
        px[x, 10] = FRAME


def build_textures() -> dict[str, Path]:
    cfg, paths = load_config()
    pal = cfg["palette"]
    out: dict[str, Path] = {}

    def src(name: str) -> Image.Image:
        p = paths.vanilla_art / name
        if not p.is_file():
            raise BuildError(f"{rel(p)}: source texture missing (run tools/fetch_vanilla.py)")
        with Image.open(p) as im:
            return im.convert("RGBA")

    armor_dir = paths.rp / paths.armor_texture_dir
    item_dir = paths.rp / paths.item_texture_dir
    for d in (armor_dir, item_dir):
        if d.exists():
            for old in d.glob("*.png"):
                old.unlink()

    layers: dict[str, Image.Image] = {}
    for name, spec in cfg["layers"].items():
        im = recolor(src(spec["source"]), pal, pal["armor_range"])
        if spec.get("goggles"):
            paint_goggles_layer(im)
        p = armor_dir / f"{name}.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        im.save(p)
        layers[name] = im
        out[f"layer:{name}"] = p

    icons: dict[str, Image.Image] = {}
    for piece in cfg["pieces"]:
        im = recolor(src(piece["icon_source"]), pal, pal["icon_range"])
        if piece.get("icon_goggles"):
            paint_goggles_icon(im)
        p = item_dir / f"{piece['id']}.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        im.save(p)
        icons[piece["id"]] = im
        out[f"icon:{piece['id']}"] = p

    # pack icons: chestplate icon, nearest-neighbour upscaled on a dark amethyst tile
    chest = icons.get("amethyst_chestplate") or next(iter(icons.values()))
    icon = Image.new("RGBA", (128, 128), (34, 20, 54, 255))
    big = chest.resize((112, 112), Image.NEAREST)
    icon.alpha_composite(big, (8, 8))
    for pack in (paths.bp, paths.rp):
        icon.save(pack / "pack_icon.png")

    write_preview(cfg, paths, layers, icons)
    print(f"  {len(layers)} armor layers -> {rel(armor_dir)}, {len(icons)} icons -> {rel(item_dir)}, "
          f"preview -> {rel(paths.build / 'armor_preview.png')}")
    return out


def _checker(size: tuple[int, int], cell: int = 8) -> Image.Image:
    im = Image.new("RGBA", size, (200, 200, 200, 255))
    d = ImageDraw.Draw(im)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                d.rectangle([x, y, x + cell - 1, y + cell - 1], fill=(170, 170, 170, 255))
    return im


def write_preview(cfg, paths, layers, icons) -> None:
    icon_scale, layer_scale, pad = 8, 6, 16
    label_h = 18
    icon_w = 16 * icon_scale
    row1_w = len(icons) * (icon_w + pad) + pad
    lw, lh = 64 * layer_scale, 32 * layer_scale
    row2_w = len(layers) * (lw + pad) + pad
    width = max(row1_w, row2_w)
    height = pad + label_h + icon_w + pad + label_h + lh + pad + 20
    sheet = Image.new("RGBA", (width, height), (24, 18, 32, 255))
    d = ImageDraw.Draw(sheet)
    x = pad
    for pid, im in icons.items():
        d.text((x, pad), pid, fill=(235, 220, 255, 255))
        tile = _checker((icon_w, icon_w))
        tile.alpha_composite(im.resize((icon_w, icon_w), Image.NEAREST))
        sheet.alpha_composite(tile, (x, pad + label_h))
        x += icon_w + pad
    y2 = pad + label_h + icon_w + pad
    x = pad
    for name, im in layers.items():
        d.text((x, y2), f"{name}.png (64x32)", fill=(235, 220, 255, 255))
        tile = _checker((lw, lh), cell=layer_scale * 4)
        tile.alpha_composite(im.resize((lw, lh), Image.NEAREST))
        sheet.alpha_composite(tile, (x, y2 + label_h))
        x += lw + pad
    d.text((pad, height - 18), "gear: amethyst armor - generated by tools/gen_textures.py", fill=(160, 140, 190, 255))
    paths.build.mkdir(parents=True, exist_ok=True)
    sheet.convert("RGB").save(paths.build / "armor_preview.png")


if __name__ == "__main__":
    try:
        build_textures()
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
