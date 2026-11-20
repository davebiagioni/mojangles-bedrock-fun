"""Validate both packs. Collects every problem, prints them all, exits 1 if any.

Run standalone:  python tools/validate.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import uuid
from pathlib import Path

from PIL import Image

from common import ROOT, BuildError, coat_name, load_config, load_geometry, rel, tame_name
from gen_json import RC_TEXTURE_EXPR

TEXTURE_EXTS = (".png", ".tga", ".jpg", ".jpeg")
SCRIPT_SERVER_VERSION = "2.11.0"
LASER_ITEM = "mymod:laser_pointer"
LASER_DOT = "mymod:laser_dot"
LASER_FAMILY = "bigcat_laser_dot"
BORED_TAG = "bigcat_bored"


def validate(verbose: bool = True) -> None:
    cfg, paths = load_config()
    errors: list[str] = []
    err = errors.append
    n = cfg["coat_count"]
    ident, prop = cfg["entity"]["identifier"], cfg["entity"]["coat_property"]

    # 1. every JSON file parses ----------------------------------------------------
    parsed: dict[Path, object] = {}
    json_files = [p for pack in (paths.bp, paths.rp) for p in sorted(pack.rglob("*.json"))]
    json_files += sorted((ROOT / "tools").rglob("*.json"))
    for p in json_files:
        try:
            raw = p.read_bytes()
            if raw.startswith(b"\xef\xbb\xbf"):
                err(f"{rel(p)}: has a UTF-8 BOM (Minecraft can reject it)")
            parsed[p] = json.loads(raw.decode("utf-8-sig"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            err(f"{rel(p)}: invalid JSON: {e}")
    if errors:
        _fail(errors)

    # Minecraft rejects unknown top-level keys ("child 'x' not valid here")
    allowed_top = {"format_version", "minecraft:entity", "minecraft:client_entity", "render_controllers",
                   "animation_controllers", "animations", "minecraft:geometry", "header", "modules",
                   "dependencies", "metadata", "capabilities", "entity_sounds", "individual_event_sounds",
                   "block_sounds", "interactive_sounds", "minecraft:item", "minecraft:recipe_shaped",
                   "particle_effect", "resource_pack_name", "texture_name", "texture_data"}
    for p, data in parsed.items():
        if (paths.bp in p.parents or paths.rp in p.parents) and isinstance(data, dict):
            if p.name == "languages.json":
                continue
            bad = sorted(set(data) - allowed_top)
            if bad:
                err(f"{rel(p)}: unexpected top-level key(s) {bad} - Minecraft will reject them")

    def get(p: Path):
        if p not in parsed:
            err(f"{rel(p)}: missing")
            return None
        return parsed[p]

    # 2. manifests ---------------------------------------------------------------
    bpm, rpm = get(paths.bp / "manifest.json"), get(paths.rp / "manifest.json")
    if bpm and rpm:
        seen: dict[str, str] = {}
        for label, m in (("BP", bpm), ("RP", rpm)):
            ids = [("header", m.get("header", {}).get("uuid"))]
            ids += [(f"module {i}", mod.get("uuid")) for i, mod in enumerate(m.get("modules", []))]
            for where, u in ids:
                try:
                    uuid.UUID(str(u))
                except ValueError:
                    err(f"{label} manifest {where}: invalid UUID {u!r}")
                    continue
                if u in seen:
                    err(f"{label} manifest {where}: UUID {u} duplicates {seen[u]}")
                seen[u] = f"{label} {where}"
            hv = m.get("header", {}).get("version")
            if not (isinstance(hv, list) and len(hv) == 3 and all(isinstance(x, int) for x in hv)):
                err(f"{label} manifest: header.version must be [major, minor, patch], got {hv!r}")
        deps = {d.get("uuid"): d.get("version") for d in bpm.get("dependencies", [])}
        rp_uuid, rp_ver = rpm["header"]["uuid"], rpm["header"]["version"]
        if rp_uuid not in deps:
            err("BP manifest: does not depend on the RP header UUID")
        elif deps[rp_uuid] != rp_ver:
            err(f"BP manifest: depends on RP version {deps[rp_uuid]} but RP is {rp_ver}")
        if bpm["header"].get("min_engine_version") != rpm["header"].get("min_engine_version"):
            err("BP and RP manifests have different min_engine_version")
        mev = bpm["header"].get("min_engine_version")
    else:
        mev = None

    # 3. entity files -------------------------------------------------------------
    bp_ent = get(paths.bp / "entities/big_cat.json")
    ce = get(paths.rp / "entity/big_cat.entity.json")
    rcf = get(paths.rp / "render_controllers/big_cat.render_controllers.json")
    geo = load_geometry(paths.geometry, cfg["entity"]["geometry"])

    groups = events = 0
    if bp_ent:
        e = bp_ent["minecraft:entity"]
        if e["description"]["identifier"] != ident:
            err(f"BP entity identifier {e['description']['identifier']} != {ident}")
        fv = bp_ent.get("format_version", "0")
        if mev and tuple(int(x) for x in fv.split(".")) > tuple(mev):
            err(f"BP entity format_version {fv} is newer than min_engine_version {mev}")
        pdef = e["description"].get("properties", {}).get(prop)
        if not pdef:
            err(f"BP entity: property {prop} missing")
        else:
            lo, hi = pdef["range"]
            if hi - lo + 1 != n or lo != 0:
                err(f"BP entity: {prop} range {pdef['range']} does not cover {n} coats")
            if pdef.get("client_sync") is not True:
                err(f"BP entity: {prop} needs client_sync so the render controller can read it")
            if pdef.get("default") != f"math.random_integer(0, {n - 1})":
                err(f"BP entity: {prop} default {pdef.get('default')!r} does not match {n} coats")
        if len(e["description"].get("properties", {})) > 32:
            err("BP entity: more than 32 properties")
        events = sum(1 for k in e.get("events", {}) if re.fullmatch(r"mymod:set_coat_\d+", k))
        if events != n:
            err(f"BP entity: {events} set_coat events, expected {n}")
        for i in range(n):
            if e.get("events", {}).get(f"mymod:set_coat_{i}", {}).get("set_property", {}).get(prop) != i:
                err(f"BP entity: mymod:set_coat_{i} does not set {prop} to {i}")
                break
        # existing behaviour still present (spot-check what must not break)
        cg = e.get("component_groups", {})
        if cg.get("minecraft:cat_adult", {}).get("minecraft:scale", {}).get("value") != 3.0:
            err("BP entity: adult scale is no longer 3.0 (giant cat broken?)")
        for must in ("minecraft:cat_wild", "minecraft:cat_tame", "minecraft:cat_baby"):
            if must not in cg:
                err(f"BP entity: component group {must} missing")
        if "mymod:sound_variant" not in e["description"].get("properties", {}):
            err("BP entity: mymod:sound_variant property missing (sounds.json uses it)")
        groups = len(cg)

    textures: dict[str, str] = {}
    if ce:
        desc = ce["minecraft:client_entity"]["description"]
        if desc["identifier"] != ident:
            err(f"client entity identifier {desc['identifier']} != {ident}")
        textures = desc.get("textures", {})
        for key, tpath in textures.items():
            if not any((paths.rp / (tpath + ext)).is_file() for ext in TEXTURE_EXTS):
                err(f"client entity texture '{key}': {tpath}(.png/.tga) not found in RP")
        coat_keys = [k for k in textures if k.startswith("coat_") and not k.endswith("_tame")]
        tame_keys = [k for k in textures if k.startswith("coat_") and k.endswith("_tame")]
        if len(coat_keys) != n or len(tame_keys) != n:
            err(f"client entity: {len(coat_keys)} coat + {len(tame_keys)} tame textures, expected {n} each")

    if rcf:
        rcs = rcf.get("render_controllers", {})
        rc = rcs.get(cfg["entity"]["render_controller"])
        if not rc:
            err(f"render controller {cfg['entity']['render_controller']} missing")
        else:
            for arr_name, namer in (("Array.coats", coat_name), ("Array.tame", tame_name)):
                arr = rc.get("arrays", {}).get("textures", {}).get(arr_name, [])
                if len(arr) != n:
                    err(f"render controller: {arr_name} has {len(arr)} entries, expected {n}")
                for i, entry in enumerate(arr):
                    if entry != f"Texture.{namer(i)}":
                        err(f"render controller: {arr_name}[{i}] is {entry}, expected Texture.{namer(i)}")
                        break
                    if namer(i) not in textures:
                        err(f"render controller: {entry} is not defined in the client entity")
                        break
            if rc.get("textures") != [RC_TEXTURE_EXPR.format(prop=prop)]:
                err(f"render controller: textures should be {RC_TEXTURE_EXPR.format(prop=prop)}")

    # 3b. laser pointer (hand-written files + generated textures) ----------------------
    laser_textures = validate_laser(paths, parsed, bpm, bp_ent, mev, err)

    # 4. images: all referenced, right size, right alpha ---------------------------
    referenced = {(paths.rp / (t + ext)).resolve() for t in list(textures.values()) + laser_textures
                  for ext in TEXTURE_EXTS}
    pngs = sorted(p for ext in TEXTURE_EXTS for p in (paths.rp / "textures").rglob("*" + ext))
    wild = sorted(paths.coat_dir_abs.glob("coat_*.png"))
    tame = sorted(paths.coat_dir_abs.glob("coat_*_tame.tga"))
    coat_pngs = wild + tame
    if len(wild) != n or len(tame) != n:
        err(f"{rel(paths.coat_dir_abs)}: {len(wild)} coat PNGs + {len(tame)} tame TGAs, expected {n} each")
    # Vanilla tame textures are TGA; the alpha-as-collar-mask is not honoured for PNG.
    stray_tame = sorted(paths.coat_dir_abs.glob("*_tame.png"))
    if stray_tame:
        err(f"{rel(stray_tame[0])}: tame textures must be .tga, not .png")
    # The 'cat' material tints by alpha with the collar colour: wild coats must be fully
    # opaque, tame coats alpha=fur_alpha except the collar (else the whole cat turns red).
    fur_a, collar_a = cfg["tame"]["fur_alpha"], cfg["tame"]["collar_alpha"]
    with Image.open(paths.tame_reference) as ref:
        ref = ref.convert("RGBA")
        collar = {(x, y) for y in range(ref.height) for x in range(ref.width) if ref.getpixel((x, y))[3] == 255}
    for p in coat_pngs:
        with Image.open(p) as im:
            im = im.convert("RGBA")
            px = {(x, y): im.getpixel((x, y))[3] for y in range(im.height) for x in range(im.width)}
        visible = {k: a for k, a in px.items() if a > 0}
        if p.stem.endswith("_tame"):
            bad = sorted(k for k, a in visible.items() if a != (collar_a if k in collar else fur_a))
            if bad:
                err(f"{rel(p)}: {len(bad)} pixels have the wrong alpha (fur must be {fur_a}, only the "
                    f"{len(collar)} collar pixels {collar_a}) - a tamed cat would be tinted the collar colour")
        elif set(visible.values()) != {255}:
            err(f"{rel(p)}: wild coat must be fully opaque, has alpha {sorted(set(visible.values()))}")
    for p in pngs:
        if p.resolve() not in referenced:
            err(f"{rel(p)}: not referenced by any client entity or item_texture.json")
    for p in coat_pngs:
        with Image.open(p) as im:
            if im.size != (geo.width, geo.height):
                err(f"{rel(p)}: {im.size[0]}x{im.size[1]}, geometry expects {geo.width}x{geo.height}")

    # 5. functions only use events that exist ------------------------------------
    ev_names = set(bp_ent["minecraft:entity"].get("events", {})) if bp_ent else set()
    for f in sorted((paths.bp / "functions").rglob("*.mcfunction")):
        for ln, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for evn in re.findall(r"\b(mymod:[a-z_0-9]+)\s*$", line):
                if line.lstrip().startswith("event") and evn not in ev_names:
                    err(f"{rel(f)}:{ln}: unknown event {evn}")

    if errors:
        _fail(errors)
    if verbose:
        print(f"  OK: {len(parsed)} JSON files parse; {n} coats == {len(textures)} textures == "
              f"{n} array entries == {events} set_coat events; {len(wild)} PNG + {len(tame)} TGA "
              f"{geo.width}x{geo.height}; manifests OK ({groups} component groups untouched)")


def validate_laser(paths, parsed, bpm, bp_ent, mev, err) -> list[str]:
    """Cross-checks for the laser pointer feature. Returns the RP texture paths it uses."""
    from gen_laser import DOT_TEXTURE, ITEM_TEXTURE

    bp, rp = paths.bp, paths.rp
    script = bp / "scripts/main.js"

    def need(p: Path):
        if p not in parsed:
            err(f"{rel(p)}: missing (laser pointer)")
            return None
        return parsed[p]

    # manifest: one script module + an exact @minecraft/server dependency
    if bpm:
        scripts = [m for m in bpm.get("modules", []) if m.get("type") == "script"]
        if len(scripts) != 1:
            err(f"BP manifest: expected exactly 1 script module, found {len(scripts)}")
        else:
            m = scripts[0]
            if m.get("language") != "javascript":
                err('BP manifest: script module needs "language": "javascript"')
            if not (bp / str(m.get("entry", ""))).is_file():
                err(f"BP manifest: script entry {m.get('entry')!r} not found in the BP")
        server = [d for d in bpm.get("dependencies", []) if d.get("module_name") == "@minecraft/server"]
        if [d.get("version") for d in server] != [SCRIPT_SERVER_VERSION]:
            err(f"BP manifest: needs exactly one dependency on @minecraft/server {SCRIPT_SERVER_VERSION}")

    item = need(bp / "items/laser_pointer.json")
    dot = need(bp / "entities/laser_dot.json")
    recipe = need(bp / "recipes/laser_pointer.json")
    dot_ce = need(rp / "entity/laser_dot.entity.json")
    atlas = need(rp / "textures/item_texture.json")
    geo = need(rp / "models/entity/laser_dot.geo.json")
    particle = need(rp / "particles/laser_dot.particle.json")

    if item:
        d = item["minecraft:item"]
        if d["description"]["identifier"] != LASER_ITEM:
            err(f"items/laser_pointer.json: identifier should be {LASER_ITEM}")
        icon = d["components"].get("minecraft:icon")
        icon = icon if isinstance(icon, str) else (icon or {}).get("textures", {}).get("default")
        if atlas and icon not in atlas.get("texture_data", {}):
            err(f"items/laser_pointer.json: icon {icon!r} is not a key in textures/item_texture.json")
    if atlas:
        for key, entry in atlas.get("texture_data", {}).items():
            if entry.get("textures") != ITEM_TEXTURE:
                err(f"textures/item_texture.json: {key} -> {entry.get('textures')!r}, expected {ITEM_TEXTURE}")
    if recipe and recipe["minecraft:recipe_shaped"]["result"]["item"] != LASER_ITEM:
        err(f"recipes/laser_pointer.json: result should be {LASER_ITEM}")
    if dot:
        e = dot["minecraft:entity"]
        if e["description"]["identifier"] != LASER_DOT:
            err(f"entities/laser_dot.json: identifier should be {LASER_DOT}")
        fv = dot.get("format_version", "0")
        if mev and tuple(int(x) for x in fv.split(".")) > tuple(mev):
            err(f"entities/laser_dot.json: format_version {fv} is newer than min_engine_version {mev}")
        comps = e.get("components", {})
        if LASER_FAMILY not in comps.get("minecraft:type_family", {}).get("family", []):
            err(f"entities/laser_dot.json: type_family must include {LASER_FAMILY} (the cats target it)")
        ds = comps.get("minecraft:damage_sensor", {}).get("triggers", {})
        if ds.get("cause") != "all" or ds.get("deals_damage") != "no":
            err("entities/laser_dot.json: damage_sensor must block all damage")
        if any("minecraft:loot" in c for c in [comps, *e.get("component_groups", {}).values()]):
            err("entities/laser_dot.json: the dot must not drop loot")
    if dot_ce:
        desc = dot_ce["minecraft:client_entity"]["description"]
        if desc["identifier"] != LASER_DOT:
            err(f"entity/laser_dot.entity.json: identifier should be {LASER_DOT}")
        if desc.get("textures", {}).get("default") != DOT_TEXTURE:
            err(f"entity/laser_dot.entity.json: default texture should be {DOT_TEXTURE}")
        gid = desc.get("geometry", {}).get("default")
        if geo and gid not in [g["description"]["identifier"] for g in geo.get("minecraft:geometry", [])]:
            err(f"entity/laser_dot.entity.json: geometry {gid} not defined in models/entity/laser_dot.geo.json")
    if bp_ent:
        sel = bp_ent["minecraft:entity"].get("components", {}).get(
            "minecraft:behavior.nearest_prioritized_attackable_target", {})
        if LASER_FAMILY not in json.dumps(sel) or BORED_TAG not in json.dumps(sel):
            err(f"BP entity: big cat no longer targets the {LASER_FAMILY} family / checks {BORED_TAG}")

    lang = rp / "texts/en_US.lang"
    lang_text = lang.read_text(encoding="utf-8") if lang.is_file() else ""
    for key in (f"item.{LASER_ITEM}.name", f"entity.{LASER_DOT}.name"):
        if f"{key}=" not in lang_text:
            err(f"{rel(lang)}: missing {key}=...")

    # script: ids it uses exist; imports exist in the API metadata (when bedrock-samples is present)
    if not script.is_file():
        err(f"{rel(script)}: missing (laser pointer)")
        return [ITEM_TEXTURE, DOT_TEXTURE]
    js = script.read_text(encoding="utf-8")
    pid = particle["particle_effect"]["description"]["identifier"] if particle else None
    for needle, what in ((LASER_ITEM, "item"), (LASER_DOT, "dot entity"), (pid, "particle"),
                         (BORED_TAG, "bored tag")):
        if needle and f'"{needle}"' not in js:
            err(f"{rel(script)}: does not use the {what} id {needle!r}")
    for other in re.findall(r'from\s*"([^"]+)"', js):
        if other != "@minecraft/server":
            err(f"{rel(script)}: imports {other!r}; only @minecraft/server is declared in the manifest")
    meta = (Path(os.environ.get("MC_SAMPLES") or ROOT.parent / "bedrock-samples") / "metadata/script_modules/@minecraft"
            / f"server-bindings_{SCRIPT_SERVER_VERSION}.json")
    if meta.is_file():
        api = json.loads(meta.read_text(encoding="utf-8"))
        exported = {x["name"] for k in ("classes", "interfaces", "enums", "objects", "constants",
                                        "functions", "errors", "type_aliases") for x in api.get(k, [])}
        for block in re.findall(r'import\s*\{([^}]*)\}\s*from\s*"@minecraft/server"', js):
            for name in (n.strip().split(" as ")[0] for n in block.split(",") if n.strip()):
                if name not in exported:
                    err(f"{rel(script)}: imports {name!r}, which @minecraft/server "
                        f"{SCRIPT_SERVER_VERSION} does not export")
    return [ITEM_TEXTURE, DOT_TEXTURE]


def _fail(errors):
    raise BuildError("validation failed:\n    - " + "\n    - ".join(errors))


if __name__ == "__main__":
    try:
        validate()
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
