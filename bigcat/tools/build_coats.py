"""Generate random cat coat textures from tools/coats_config.json.

Patterns are evaluated in 3D on the model surface (every texture pixel is mapped
to its spot on the cat via the geometry's box UVs). That makes stripes, spots and
patches follow the body across face seams instead of smearing across the atlas.
Eyes, nose and inner ears are protected and copied unchanged from the original.

Outputs:
  <rp>/textures/entity/coats/coat_###.png   one per coat
  build/coat_preview.png                    contact sheet (side/front/top views + atlas)
  build/coats_manifest.json                 what each coat is (pattern, palette, ...)
  build/uv_template.png                     big labelled UV map for painting layers

Run standalone:  python tools/build_coats.py
"""
from __future__ import annotations

import colorsys
import math
import random
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from common import (BuildError, Geometry, Texel, coat_name, load_config, load_geometry, rel, tame_name,
                    write_json)

Color = tuple[float, float, float]

# --------------------------------------------------------------------- small math


def clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def smooth(x: float) -> float:
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def lerp(a: Color, b: Color, t: float) -> Color:
    t = clamp01(t)
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def hex_to_rgb(h: str) -> Color:
    h = h.lstrip("#")
    if len(h) != 6:
        raise BuildError(f"bad color '{h}' in config (use #rrggbb)")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def luminance(rgb) -> float:
    r, g, b = rgb[:3]
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255


class Noise:
    """Deterministic 3D value noise + jittered-grid spots (no numpy needed)."""

    def __init__(self, seed: int):
        self.seed = seed & 0xFFFFFFFF

    def _hash(self, x: int, y: int, z: int, k: int = 0) -> float:
        h = (x * 374761393 + y * 668265263 + z * 1274126177 + (self.seed + k * 977) * 2246822519) & 0xFFFFFFFF
        h = ((h ^ (h >> 13)) * 3266489917) & 0xFFFFFFFF
        h ^= h >> 16
        return h / 4294967296.0

    def value(self, x: float, y: float, z: float) -> float:
        ix, iy, iz = math.floor(x), math.floor(y), math.floor(z)
        fx, fy, fz = x - ix, y - iy, z - iz
        ux, uy, uz = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy), fz * fz * (3 - 2 * fz)
        h = self._hash

        def l(a, b, t):
            return a + (b - a) * t

        x00 = l(h(ix, iy, iz), h(ix + 1, iy, iz), ux)
        x10 = l(h(ix, iy + 1, iz), h(ix + 1, iy + 1, iz), ux)
        x01 = l(h(ix, iy, iz + 1), h(ix + 1, iy, iz + 1), ux)
        x11 = l(h(ix, iy + 1, iz + 1), h(ix + 1, iy + 1, iz + 1), ux)
        return l(l(x00, x10, uy), l(x01, x11, uy), uz)

    def fbm(self, p, freq: float, octaves: int = 3) -> float:
        total, amp, norm = 0.0, 1.0, 0.0
        for o in range(octaves):
            f = freq * (2 ** o)
            total += amp * self.value(p[0] * f + o * 17.1, p[1] * f + o * 3.7, p[2] * f + o * 9.3)
            norm += amp
            amp *= 0.5
        return total / norm

    def spots(self, p, cell: float, density: float) -> float:
        """Distance (in model units) to the nearest spot centre."""
        q = (p[0] / cell, p[1] / cell, p[2] / cell)
        bx, by, bz = math.floor(q[0]), math.floor(q[1]), math.floor(q[2])
        best = 1e9
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    cx, cy, cz = bx + dx, by + dy, bz + dz
                    if self._hash(cx, cy, cz, 7) > density:
                        continue
                    fx = cx + self._hash(cx, cy, cz, 1)
                    fy = cy + self._hash(cx, cy, cz, 2)
                    fz = cz + self._hash(cx, cy, cz, 3)
                    d = (fx - q[0]) ** 2 + (fy - q[1]) ** 2 + (fz - q[2]) ** 2
                    best = min(best, d)
        return math.sqrt(best) * cell


# ----------------------------------------------------------------------- anatomy


def compute_anatomy(geo: Geometry, cfg: dict) -> None:
    """Fill texel.w with 0..1 weights for body regions used by the patterns."""
    an = cfg["anatomy"]
    body, head = an["body_bone"], an["head_bone"]
    legs, tails = set(an["leg_bones"]), list(an["tail_bones"])
    ears = {tuple(c) for c in an["ear_cubes"]}
    muzzle = {tuple(c) for c in an["muzzle_cubes"]}
    belly_frac, paw_h = an["belly_height"], an["paw_height"]

    allP = [t.P for t in geo.surface]
    zmin, zmax = min(p[2] for p in allP), max(p[2] for p in allP)
    (bx0, by0, bz0), (bx1, by1, bz1) = geo.cube_bounds[(body, 0)]
    (hx0, hy0, hz0), (hx1, hy1, hz1) = geo.cube_bounds[(head, 0)]
    nose = next(iter(muzzle))
    (nx0, ny0, nz0), (nx1, ny1, nz1) = geo.cube_bounds[nose]
    nose_c = ((nx0 + nx1) / 2, (ny0 + ny1) / 2, nz0)
    head_cx = (hx0 + hx1) / 2

    for t in list(geo.texels.values()):
        x, y, z = t.P
        nx, ny, nz = t.N
        w = {k: 0.0 for k in ("ventral", "chest", "paw", "leg_low", "legs", "face", "lower_face",
                              "muzzle", "ears", "tail", "tail_tip", "blaze", "dorsal", "nose_dist")}
        w["length"] = (z - zmin) / (zmax - zmin)
        cube = (t.bone, t.cube)
        w["nose_dist"] = math.dist(t.P, nose_c)
        if t.bone == body:
            ry = (y - by0) / (by1 - by0)
            w["dorsal"] = ry
            w["ventral"] = smooth((belly_frac - ry) / 0.3 + 0.5)
            front = 1 - (z - bz0) / (bz1 - bz0)
            w["chest"] = smooth((front - 0.72) / 0.2) * smooth((0.8 - ry) / 0.4)
            if nz < -0.5:  # front end cap
                w["chest"] = max(w["chest"], smooth((0.75 - ry) / 0.3))
        elif cube in muzzle:
            w.update(muzzle=1.0, face=1.0, lower_face=1.0, dorsal=0.3, ventral=0.3)
        elif cube in ears:
            w.update(ears=1.0, dorsal=1.0)
        elif t.bone == head:
            ry = (y - hy0) / (hy1 - hy0)
            w["dorsal"] = ry
            if nz < -0.5:
                w["face"] = 1.0
                w["lower_face"] = smooth((0.45 - ry) / 0.25)
            if ny < -0.5:  # chin
                w.update(ventral=1.0, lower_face=1.0)
            near_front = nz < -0.5 or (ny > 0.5 and z < hz0 + 2.5)
            if near_front:
                w["blaze"] = smooth((0.9 - abs(x - head_cx)) / 0.4) * (1 if ny > 0.5 or ry > 0.4 else 0)
        elif t.bone in legs:
            (lx0, ly0, lz0), (lx1, ly1, lz1) = geo.cube_bounds[cube]
            above = y - ly0
            w["legs"] = 1.0
            w["leg_low"] = clamp01(1 - above / (ly1 - ly0))
            w["paw"] = 1.0 if (ny < -0.5 or above < paw_h) else 0.0
            w["dorsal"] = 0.5 * (1 - w["leg_low"])
        elif t.bone in tails:
            (tx0, ty0, tz0), (tx1, ty1, tz1) = geo.cube_bounds[cube]
            seg = tails.index(t.bone)
            along = clamp01((ty1 - y) / (ty1 - ty0)) if ny > -0.5 else 1.0
            w["tail"] = 1.0
            w["tail_tip"] = (seg + along) / len(tails)
            w["dorsal"] = 0.8
        t.w = w


def stripe_coord(t: Texel, cfg: dict) -> float:
    """Coordinate that tabby stripes are bands of, per body part."""
    an = cfg["anatomy"]
    if t.bone == an["body_bone"]:
        return t.P[2]  # bands across the back
    if t.bone == an["head_bone"] and t.cube == 0:
        return t.P[0] * 1.6 if t.N[1] > 0.5 else t.P[1] * 1.3  # forehead lines / cheek bars
    return t.P[1]  # rings on legs, tail, ears


# ---------------------------------------------------------------------- patterns


class Pal:
    def __init__(self, base, dark, light, white):
        self.base, self.dark, self.light, self.white = base, dark, light, white


def pat_solid(rng, pal, s, cfg):
    return lambda t: pal.base


def pat_tabby(rng, pal, s, cfg):
    period = rng.uniform(*s["period"])
    duty = rng.uniform(*s["duty"])
    wobble = rng.uniform(*s["wobble"])
    phase = rng.random()
    broken = rng.random() < s["broken_chance"]
    n = Noise(rng.getrandbits(32))
    belly = lerp(pal.base, pal.light, rng.uniform(0.4, 0.9))

    def f(t):
        c = stripe_coord(t, cfg) / period + phase + wobble * (n.fbm(t.P, 0.35) - 0.5) * 2
        on = (c - math.floor(c)) < duty
        if broken and n.fbm(t.P, 0.7, 2) > 0.55:
            on = False
        col = pal.dark if on else pal.base
        return lerp(col, belly, t.w["ventral"] * 0.85)
    return f


def pat_spots(rng, pal, s, cfg):
    cell = rng.uniform(*s["cell"])
    radius = rng.uniform(*s["radius"]) * cell
    density = rng.uniform(*s["density"])
    rosette = rng.random() < s["rosette_chance"]
    n = Noise(rng.getrandbits(32))
    belly = lerp(pal.base, pal.light, rng.uniform(0.5, 0.9))

    def f(t):
        d = n.spots(t.P, cell, density)
        col = pal.base
        if d < radius:
            col = pal.dark
            if rosette and d < radius * 0.45:
                col = lerp(pal.base, pal.dark, 0.35)
        return lerp(col, belly, t.w["ventral"] * 0.9)
    return f


def pat_calico(rng, pal, s, cfg):
    white_amt = rng.uniform(*s["white_amount"])
    freq = rng.uniform(*s["patch_freq"])
    n1, n2 = Noise(rng.getrandbits(32)), Noise(rng.getrandbits(32))
    cut = rng.uniform(0.42, 0.58)

    def f(t):
        w = t.w
        under = max(w["ventral"], w["paw"], w["lower_face"], w["chest"])
        score = under * 0.75 + (n1.fbm(t.P, 0.22) - 0.5) * 1.4 + white_amt
        if score > 0.5:
            return pal.white
        return pal.base if n2.fbm(t.P, freq) > cut else pal.dark
    return f


def pat_tortie(rng, pal, s, cfg):
    freq = rng.uniform(*s["freq"])
    cut = rng.uniform(0.45, 0.55)
    flecks = rng.uniform(*s["fleck_amount"])
    n1, n2 = Noise(rng.getrandbits(32)), Noise(rng.getrandbits(32))

    def f(t):
        col = pal.dark if n1.fbm(t.P, freq) > cut else pal.base
        if n2.value(t.P[0] * 1.3, t.P[1] * 1.3, t.P[2] * 1.3) < flecks:
            col = lerp(col, pal.light, 0.6)
        return col
    return f


def pat_tuxedo(rng, pal, s, cfg):
    jag = rng.uniform(*s["edge_noise"])
    amount = rng.uniform(*s["white_amount"])
    coat = pal.dark if rng.random() < 0.6 else pal.base
    n = Noise(rng.getrandbits(32))

    def f(t):
        w = t.w
        white = max(w["ventral"], w["chest"], w["paw"], w["lower_face"], w["blaze"] * 0.9)
        if white + (n.fbm(t.P, 0.6) - 0.5) * jag + amount > 0.55:
            return pal.white
        return coat
    return f


def pat_colorpoint(rng, pal, s, cfg):
    reach = rng.uniform(*s["mask_size"])
    body = lerp(pal.light, pal.base, rng.uniform(0.0, 0.35))

    def f(t):
        w = t.w
        face = w["face"] * smooth(1 - w["nose_dist"] / reach)
        pts = max(w["ears"], w["muzzle"], face, w["leg_low"] ** 1.3 * w["legs"], w["tail_tip"] ** 0.8 * w["tail"])
        return lerp(body, pal.dark, smooth(pts))
    return f


def pat_gradient(rng, pal, s, cfg):
    mode = rng.choice(s["modes"])
    flip = rng.random() < 0.5

    def f(t):
        w = t.w
        if mode == "dorsal":
            return lerp(pal.light, pal.dark, smooth(w["dorsal"]))
        if mode == "length":
            k = 1 - w["length"] if flip else w["length"]
            return lerp(pal.base, pal.dark, smooth(k))
        # radial: darker the further from the nose
        return lerp(pal.light, pal.dark, smooth(w["nose_dist"] / 22))
    return f


PATTERNS = {
    "solid": pat_solid, "tabby": pat_tabby, "spots": pat_spots, "calico": pat_calico,
    "tortie": pat_tortie, "tuxedo": pat_tuxedo, "colorpoint": pat_colorpoint, "gradient": pat_gradient,
}


def apply_modifiers(rng, name, pal, cfg):
    """Optional extras layered on top of the main pattern."""
    mods = []
    mc = cfg.get("modifiers", {})
    skip = {"tuxedo": {"white_paws", "white_blaze", "light_belly"}, "calico": {"white_paws", "light_belly"},
            "colorpoint": {"white_blaze"}}
    for mod in sorted(mc):
        if mod in skip.get(name, ()):
            continue
        if rng.random() < mc[mod]:
            mods.append(mod)

    def f(t, col):
        w = t.w
        if "light_belly" in mods:
            col = lerp(col, pal.light, w["ventral"] * 0.8)
        if "white_paws" in mods and w["paw"] > 0.5:
            col = pal.white
        if "white_blaze" in mods and w["blaze"] > 0.5:
            col = pal.white
        if "white_tail_tip" in mods and w["tail_tip"] > 0.8:
            col = pal.white
        return col
    return mods, f


# -------------------------------------------------------------------- generation


def jitter(c: Color, rng: random.Random, j: dict) -> Color:
    h, s, v = colorsys.rgb_to_hsv(*c)
    h = (h + rng.uniform(-j["hue"], j["hue"])) % 1.0
    s = clamp01(s + rng.uniform(-j["sat"], j["sat"]))
    v = clamp01(v + rng.uniform(-j["val"], j["val"]))
    return colorsys.hsv_to_rgb(h, s, v)


def weighted(rng: random.Random, items: list[tuple[str, float]]):
    total = sum(w for _, w in items)
    r = rng.uniform(0, total)
    for name, w in items:
        r -= w
        if r <= 0:
            return name
    return items[-1][0]


def build_protect_mask(base: Image.Image, geo: Geometry, cfg: dict, paths) -> set[tuple[int, int]]:
    """Pixels that keep the original colour: anything whose colour never appears on
    the plain-fur reference cube (eyes, nose, inner ears), plus art/protect_mask.png."""
    ref_bone = cfg["anatomy"]["body_bone"]
    fur = {base.getpixel((t.px, t.py)) for t in geo.texels.values() if t.bone == ref_bone}
    protect = {k for k in geo.texels if base.getpixel(k) not in fur and base.getpixel(k)[3] > 0}
    for k in geo.texels:  # transparent covered pixels stay transparent
        if base.getpixel(k)[3] == 0:
            protect.add(k)
    if paths.protect_mask.is_file():
        m = Image.open(paths.protect_mask).convert("L")
        if m.size != base.size:
            raise BuildError(f"{rel(paths.protect_mask)} is {m.size}, expected {base.size}")
        protect |= {(x, y) for y in range(m.height) for x in range(m.width) if m.getpixel((x, y)) > 127}
    return protect


def load_collar(paths, geo: Geometry) -> dict[tuple[int, int], tuple]:
    """Collar pixels from vanilla's tame cat texture.

    The 'cat' material uses texture ALPHA as a tint mask for the collar colour
    (minecraft:color): alpha 255 = fully tinted, ~4 = untouched. Vanilla tame
    textures are alpha 4 everywhere except the collar ring. A fully opaque coat
    therefore turns the whole cat collar-coloured once it is tamed."""
    ref = Image.open(paths.tame_reference).convert("RGBA")
    if ref.size != (geo.width, geo.height):
        raise BuildError(f"{rel(paths.tame_reference)} is {ref.size}, expected {(geo.width, geo.height)}")
    collar = {(x, y): ref.getpixel((x, y))[:3] for y in range(ref.height) for x in range(ref.width)
              if ref.getpixel((x, y))[3] == 255}
    if not collar:
        raise BuildError(f"{rel(paths.tame_reference)}: no collar pixels (alpha 255) found")
    stray = [k for k in collar if k not in geo.texels]
    if stray:
        raise BuildError(f"{rel(paths.tame_reference)}: collar pixels {stray[:4]} are not on the model")
    return collar


def make_tame(coat: Image.Image, collar: dict, cfg: dict) -> Image.Image:
    fur_a, collar_a = cfg["tame"]["fur_alpha"], cfg["tame"]["collar_alpha"]
    tame = coat.copy()
    px = tame.load()
    for y in range(tame.height):
        for x in range(tame.width):
            r, g, b, a = px[x, y]
            if (x, y) in collar:
                px[x, y] = (*collar[(x, y)], collar_a)
            elif a > 0:
                px[x, y] = (r, g, b, fur_a)
    return tame


def load_layers(paths, size) -> list[tuple[str, Image.Image]]:
    """Hand-painted overlays. Any integer multiple of the texture size is accepted
    (paint at 16x, it gets shrunk). Files starting with '_' are ignored."""
    layers = []
    if not paths.coat_layers.is_dir():
        return layers
    for p in sorted(paths.coat_layers.glob("*.png")):
        if p.name.startswith("_"):
            continue
        im = Image.open(p).convert("RGBA")
        sx, sy = im.width / size[0], im.height / size[1]
        if sx != sy or sx < 1 or sx != int(sx):
            raise BuildError(f"{rel(p)} is {im.width}x{im.height}; layers must be {size[0]}x{size[1]} "
                             f"or an exact multiple of it (e.g. {size[0]*16}x{size[1]*16})")
        if sx > 1:
            im = im.resize(size, Image.Resampling.NEAREST)
        layers.append((p.name, im))
    return layers


def make_coat(i, cfg, geo, base, protect, shade, layers):
    seed = cfg["seed"]
    rng = random.Random(f"{seed}:{i}")
    colors = {k: hex_to_rgb(v) for k, v in cfg["colors"].items()}
    pattern = weighted(rng, sorted(cfg["pattern_weights"].items()))
    if pattern not in PATTERNS:
        raise BuildError(f"unknown pattern '{pattern}' in pattern_weights (known: {sorted(PATTERNS)})")
    # a palette may list "patterns" it is limited to (e.g. tri-colour only for calico/tortie)
    pal_cfg = [p for p in cfg["palettes"] if pattern in p.get("patterns", [pattern])]
    if not pal_cfg:
        raise BuildError(f"no palette allows pattern '{pattern}'")
    pal_name = weighted(rng, [(p["name"], p.get("weight", 1)) for p in pal_cfg])
    pc = next(p for p in pal_cfg if p["name"] == pal_name)
    for k in ("base", "dark", "light"):
        if pc[k] not in colors:
            raise BuildError(f"palette '{pal_name}' uses unknown color '{pc[k]}'")
    j = cfg["jitter"]
    pal = Pal(*(jitter(colors[pc[k]], rng, j) for k in ("base", "dark", "light")),
              jitter(colors[cfg.get("white", "white")], rng, {"hue": 0, "sat": 0.03, "val": 0.03}))
    fn = PATTERNS[pattern](rng, pal, cfg["pattern_settings"].get(pattern, {}), cfg)
    mods, modfn = apply_modifiers(rng, pattern, pal, cfg)

    # kid layers use their own random stream so adding a layer doesn't reshuffle every coat
    layer = None
    lrng = random.Random(f"{seed}:{i}:layer")
    if layers and lrng.random() < cfg["coat_layers"]["chance"]:
        layer = layers[lrng.randrange(len(layers))]

    out = base.copy()
    for key, t in geo.texels.items():
        if key in protect:
            continue
        col = modfn(t, fn(t))
        r, g, b = (c * 255 for c in col)
        if layer:
            lr, lg, lb, la = layer[1].getpixel(key)
            a = la / 255
            r, g, b = r + (lr - r) * a, g + (lg - g) * a, b + (lb - b) * a
        k = shade[key]
        out.putpixel(key, (min(255, round(r * k)), min(255, round(g * k)), min(255, round(b * k)),
                           base.getpixel(key)[3]))
    meta = {"index": i, "name": coat_name(i), "pattern": pattern, "palette": pal_name, "modifiers": mods,
            "layer": layer[0] if layer else None}
    return out, meta


def shading_map(base, geo, protect, cfg) -> dict:
    """Per-pixel brightness factor from the original texture, relative to its face's
    median, so coats keep the original's depth without inheriting its stripes."""
    sc = cfg["shading"]
    k, lo, hi = sc["strength"], sc["min"], sc["max"]
    faces: dict[str, list] = {}
    for key, t in geo.texels.items():
        if key not in protect:
            faces.setdefault(t.face_key, []).append(luminance(base.getpixel(key)))
    med = {fk: sorted(v)[len(v) // 2] for fk, v in faces.items()}
    out = {}
    for key, t in geo.texels.items():
        L = luminance(base.getpixel(key))
        m = max(med.get(t.face_key, L), 0.05)
        out[key] = max(lo, min(hi, 1 + k * (L - m) / m))
    return out


# ---------------------------------------------------------------------- previews


def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow
        return ImageFont.load_default()


def render_views(img: Image.Image, geo: Geometry, scale: int) -> dict[str, Image.Image]:
    """Orthographic side / front / top views of the cat in its rest pose."""
    P = [t.P for t in geo.surface]
    x0, x1 = min(p[0] for p in P), max(p[0] for p in P)
    y0, y1 = min(p[1] for p in P), max(p[1] for p in P)
    z0, z1 = min(p[2] for p in P), max(p[2] for p in P)
    views = {
        # name: (visible-if, screen x, screen y, depth (draw ascending), size)
        "side": (lambda t: t.N[0] < -0.5, lambda p: p[2] - z0, lambda p: y1 - p[1], lambda p: -p[0], (z1 - z0, y1 - y0)),
        "front": (lambda t: t.N[2] < -0.5, lambda p: x1 - p[0], lambda p: y1 - p[1], lambda p: p[2], (x1 - x0, y1 - y0)),
        "top": (lambda t: t.N[1] > 0.5, lambda p: p[2] - z0, lambda p: p[0] - x0, lambda p: p[1], (z1 - z0, x1 - x0)),
    }
    out = {}
    for name, (vis, sx, sy, depth, (w, h)) in views.items():
        im = Image.new("RGBA", (math.ceil(w * scale) + 1, math.ceil(h * scale) + 1), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for t in sorted((t for t in geo.surface if vis(t)), key=lambda t: depth(t.P)):
            c = img.getpixel((t.px, t.py))
            if c[3] == 0:
                continue
            cx, cy = sx(t.P) * scale, sy(t.P) * scale
            hs = scale / 2
            d.rectangle([round(cx - hs), round(cy - hs), round(cx + hs) - 1, round(cy + hs) - 1], fill=c)
        out[name] = im
    return out


def contact_sheet(coats, metas, geo, path: Path, cols: int = 10):
    scale = 4
    atlas_scale = 2
    sample = render_views(coats[0], geo, scale)
    side, front, top = sample["side"], sample["front"], sample["top"]
    aw, ah = geo.width * atlas_scale, geo.height * atlas_scale
    pad = 6
    tile_w = max(side.width + front.width + pad, top.width, aw) + pad * 2
    tile_h = 14 + side.height + pad + top.height + pad + ah + pad
    rows = math.ceil(len(coats) / cols)
    sheet = Image.new("RGBA", (cols * tile_w, rows * tile_h + 24), (58, 62, 66, 255))
    d = ImageDraw.Draw(sheet)
    font = _font(11)
    d.text((6, 5), f"{len(coats)} coats  -  index / pattern / palette  (+ modifiers)", fill=(235, 235, 235), font=font)
    for n, (img, m) in enumerate(zip(coats, metas)):
        ox, oy = (n % cols) * tile_w + pad, (n // cols) * tile_h + 24
        v = render_views(img, geo, scale)
        label = f"{m['index']:03d} {m['pattern']}/{m['palette']}" + (" +" if m["modifiers"] or m["layer"] else "")
        d.text((ox, oy), label, fill=(240, 240, 240), font=font)
        y = oy + 14
        sheet.alpha_composite(v["side"], (ox, y))
        sheet.alpha_composite(v["front"], (ox + v["side"].width + pad, y))
        y += v["side"].height + pad
        sheet.alpha_composite(v["top"], (ox, y))
        y += v["top"].height + pad
        sheet.alpha_composite(img.resize((aw, ah), Image.Resampling.NEAREST), (ox, y))
    sheet.save(path)


def uv_template(geo: Geometry, base: Image.Image, path: Path, cfg: dict, scale: int = 16):
    """Big labelled UV map. Kids can paint on a copy in a layer above it, hide the
    template, and save the painting (same size) into art/coat_layers/."""
    im = base.resize((geo.width * scale, geo.height * scale), Image.Resampling.NEAREST).convert("RGBA")
    im = Image.blend(Image.new("RGBA", im.size, (255, 255, 255, 255)), im, 0.35)
    d = ImageDraw.Draw(im)
    font = _font(14)
    rects: dict[str, list] = {}
    for t in geo.texels.values():
        r = rects.setdefault(t.face_key, [t.px, t.py, t.px, t.py])
        r[0], r[1] = min(r[0], t.px), min(r[1], t.py)
        r[2], r[3] = max(r[2], t.px), max(r[3], t.py)
    an = cfg["anatomy"]
    ears = {tuple(c) for c in an["ear_cubes"]}
    muzzle = {tuple(c) for c in an["muzzle_cubes"]}

    def part(bone, cube):
        if (bone, cube) in ears:
            return "ear"
        if (bone, cube) in muzzle:
            return "nose"
        if bone in an["leg_bones"]:
            return ("front" if "front" in bone.lower() else "back") + " legs"
        if bone in an["tail_bones"]:
            return "tail"
        return bone

    def facing(n, name):  # label by where the face points on the standing cat
        if n[1] > 0.5:
            return {"body": "back (spine)", "head": "top of head"}.get(name, "top")
        if n[1] < -0.5:
            return {"body": "belly", "head": "chin"}.get(name, "bottom")
        if n[2] < -0.5:
            return {"body": "chest", "head": "FACE"}.get(name, "front")
        if n[2] > 0.5:
            return {"body": "rump", "head": "back of head"}.get(name, "back")
        return "side"

    first = {}
    for t in geo.texels.values():
        first.setdefault(t.face_key, t)
    groups: dict[str, list] = {}
    for fk, (a, b, c, e) in sorted(rects.items()):
        t = first[fk]
        name = part(t.bone, t.cube)
        d.rectangle([a * scale, b * scale, (c + 1) * scale - 1, (e + 1) * scale - 1], outline=(30, 30, 30, 255), width=2)
        g = groups.setdefault(name, [a, b, c, e])
        g[0], g[1], g[2], g[3] = min(g[0], a), min(g[1], b), max(g[2], c), max(g[3], e)
        if name in ("body", "head") and (c - a + 1) * scale >= 60:
            d.multiline_text((a * scale + 3, b * scale + 2), f"{name}\n{facing(t.N, name)}",
                             fill=(20, 20, 20, 255), font=font, spacing=0)
    for name, (a, b, c, e) in groups.items():  # small parts: one label per part, above it
        if name not in ("body", "head"):
            y = b * scale - 16 if b * scale >= 16 else (e + 1) * scale + 2
            d.text((a * scale + 2, y), name, fill=(150, 20, 20, 255), font=font)
    d.text((660, 470), "left & right legs share one picture", fill=(60, 60, 60, 255), font=font)
    im.save(path)


# --------------------------------------------------------------------------- main


def build_coats(verbose: bool = True) -> list[dict]:
    cfg, paths = load_config()
    geo = load_geometry(paths.geometry, cfg["entity"]["geometry"], cfg["anatomy"].get("rest_pose"))
    base = Image.open(paths.base_texture).convert("RGBA")
    if base.size != (geo.width, geo.height):
        raise BuildError(f"{rel(paths.base_texture)} is {base.size}, geometry expects {(geo.width, geo.height)}")
    compute_anatomy(geo, cfg)
    protect = build_protect_mask(base, geo, cfg, paths)
    visible_protect = sorted(k for k in protect if base.getpixel(k)[3] > 0)
    if verbose:
        print(f"  geometry {geo.identifier}: {geo.width}x{geo.height}, {len(geo.texels)} mapped pixels")
        print(f"  protected pixels (eyes/nose/inner ears): {len(visible_protect)} {visible_protect}")
    if not visible_protect:
        raise BuildError("no protected pixels found - eyes/nose would be recoloured. Add art/protect_mask.png")
    if len(visible_protect) > 0.1 * len(geo.texels):
        raise BuildError(f"{len(visible_protect)} protected pixels is suspiciously many; check the base texture")
    shade = shading_map(base, geo, protect, cfg)
    layers = load_layers(paths, base.size)
    if verbose and layers:
        print(f"  kid layers: {[n for n, _ in layers]}")

    n = cfg["coat_count"]
    coats, metas = [], []
    for i in range(n):
        img, meta = make_coat(i, cfg, geo, base, protect, shade, layers)
        coats.append(img)
        metas.append(meta)

    out_dir = paths.coat_dir_abs
    if out_dir.exists():
        shutil.rmtree(out_dir)  # wipe so a smaller coat_count leaves no orphans
    out_dir.mkdir(parents=True)
    collar = load_collar(paths, geo)
    for i, (img, meta) in enumerate(zip(coats, metas)):
        img.save(out_dir / f"{coat_name(i)}.png", optimize=False)
        # TGA like vanilla: Bedrock reads the collar alpha mask from TGA tame textures
        make_tame(img, collar, cfg).save(out_dir / f"{tame_name(i)}.tga")

    paths.build.mkdir(parents=True, exist_ok=True)
    contact_sheet(coats, metas, geo, paths.build / "coat_preview.png")
    uv_template(geo, base, paths.build / "uv_template.png", cfg)
    write_json(paths.build / "coats_manifest.json", {"seed": cfg["seed"], "coats": metas})

    if verbose:
        counts: dict[str, int] = {}
        for m in metas:
            counts[m["pattern"]] = counts.get(m["pattern"], 0) + 1
        print(f"  wrote {n} coats (+ {n} tame versions with collar mask) to {rel(out_dir)}  ({', '.join(f'{k} {v}' for k, v in sorted(counts.items()))})")
        print(f"  preview: {rel(paths.build / 'coat_preview.png')}")
    return metas


if __name__ == "__main__":
    try:
        build_coats()
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
