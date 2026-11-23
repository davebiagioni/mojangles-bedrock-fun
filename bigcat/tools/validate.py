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
    allowed_top = {
        "format_version",
        "minecraft:entity",
        "minecraft:client_entity",
        "render_controllers",
        "animation_controllers",
        "animations",
        "minecraft:geometry",
        "header",
        "modules",
        "dependencies",
        "metadata",
        "capabilities",
        "entity_sounds",
        "individual_event_sounds",
        "block_sounds",
        "interactive_sounds",
        "minecraft:item",
        "minecraft:block",
        "minecraft:recipe_shaped",
        "particle_effect",
        "resource_pack_name",
        "texture_name",
        "texture_data",
    }
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
    from gen_orb import ALL_TEXTURES as ORB_TEXTURES
    from gen_wand import ALL_TEXTURES as WAND_TEXTURES

    laser_textures += ORB_TEXTURES + WAND_TEXTURES
    validate_orb(paths, parsed, err)
    validate_wands(paths, parsed, err)
    laser_textures += validate_grapple(paths, parsed, mev, err)
    laser_textures += validate_drowned_trap(paths, parsed, mev, err)
    laser_textures += validate_evolution(paths, parsed, bp_ent, ce, err)
    laser_textures += validate_net_trap(paths, parsed, err)
    laser_textures += validate_morph(paths, parsed, err)
    laser_textures += validate_air_cannon(paths, parsed, err)
    laser_textures += validate_atomic_bomb(paths, parsed, err)
    laser_textures += validate_blaster(paths, parsed, err)
    laser_textures += validate_mountain(paths, parsed, err)
    laser_textures += validate_vortex(paths, parsed, err)
    laser_textures += validate_mooshroom_drill(paths, parsed, mev, err)
    laser_textures += validate_portal(paths, parsed, err)
    validate_blocks(paths, parsed, err)

    # 4. images: all referenced, right size, right alpha ---------------------------
    referenced = {
        (paths.rp / (t + ext)).resolve() for t in list(textures.values()) + laser_textures for ext in TEXTURE_EXTS
    }
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
                err(
                    f"{rel(p)}: {len(bad)} pixels have the wrong alpha (fur must be {fur_a}, only the "
                    f"{len(collar)} collar pixels {collar_a}) - a tamed cat would be tinted the collar colour"
                )
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
        print(
            f"  OK: {len(parsed)} JSON files parse; {n} coats == {len(textures)} textures == "
            f"{n} array entries == {events} set_coat events; {len(wild)} PNG + {len(tame)} TGA "
            f"{geo.width}x{geo.height}; manifests OK ({groups} component groups untouched)"
        )


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
            tex = entry.get("textures")
            if key == "mymod_laser_pointer" and tex != ITEM_TEXTURE:
                err(f"textures/item_texture.json: {key} -> {tex!r}, expected {ITEM_TEXTURE}")
            if not any((rp / (str(tex) + ext)).is_file() for ext in TEXTURE_EXTS):
                err(f"textures/item_texture.json: {key} -> {tex!r}, which is not in the RP")
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
        sel = (
            bp_ent["minecraft:entity"]
            .get("components", {})
            .get("minecraft:behavior.nearest_prioritized_attackable_target", {})
        )
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
    for needle, what in ((LASER_ITEM, "item"), (LASER_DOT, "dot entity"), (pid, "particle"), (BORED_TAG, "bored tag")):
        if needle and f'"{needle}"' not in js:
            err(f"{rel(script)}: does not use the {what} id {needle!r}")
    meta = (
        Path(os.environ.get("MC_SAMPLES") or ROOT.parent / "bedrock-samples")
        / "metadata/script_modules/@minecraft"
        / f"server-bindings_{SCRIPT_SERVER_VERSION}.json"
    )
    exported = None
    if meta.is_file():
        api = json.loads(meta.read_text(encoding="utf-8"))
        exported = {
            x["name"]
            for k in ("classes", "interfaces", "enums", "objects", "constants", "functions", "errors", "type_aliases")
            for x in api.get(k, [])
        }
    # every script in the pack: imports are @minecraft/server or another script file that exists
    for f in sorted((bp / "scripts").rglob("*.js")):
        src = f.read_text(encoding="utf-8")
        for other in re.findall(r'(?:from\s*|import\s+)"([^"]+)"', src):
            if other == "@minecraft/server":
                continue
            if other.startswith("./") or other.startswith("../"):
                if not (f.parent / other).resolve().is_file():
                    err(f"{rel(f)}: imports {other!r}, which does not exist")
                continue
            err(f"{rel(f)}: imports {other!r}; only @minecraft/server is declared in the manifest")
        if exported is not None:
            for block in re.findall(r'import\s*\{([^}]*)\}\s*from\s*"@minecraft/server"', src):
                for name in (n.strip().split(" as ")[0] for n in block.split(",") if n.strip()):
                    if name not in exported:
                        err(
                            f"{rel(f)}: imports {name!r}, which @minecraft/server "
                            f"{SCRIPT_SERVER_VERSION} does not export"
                        )
    return [ITEM_TEXTURE, DOT_TEXTURE]


def validate_orb(paths, parsed, err) -> None:
    """Cross-checks for the orbs (hand-written items/recipes/scripts + generated icons)."""
    bp, rp = paths.bp, paths.rp
    atlas = parsed.get(rp / "textures/item_texture.json", {}).get("texture_data", {})
    lang = (rp / "texts/en_US.lang").read_text(encoding="utf-8")
    main_js = (bp / "scripts/main.js").read_text(encoding="utf-8")
    # orb name -> script that implements it
    kinds = {"cat_orb": "orbs.js", "creature_orb": "orbs.js", "trap_orb": "trap_orb.js"}
    for script_name in sorted(set(kinds.values())):
        if f'import "./{script_name}"' not in main_js:
            err(f"scripts/main.js: must import ./{script_name}")
    for name, script_name in kinds.items():
        script = bp / "scripts" / script_name
        js = script.read_text(encoding="utf-8") if script.is_file() else ""
        if not js:
            err(f"{rel(script)}: missing ({name})")
        for fname, stack in ((name, 16), (name + "_full", 1)):
            ident = f"mymod:{fname}"
            item = parsed.get(bp / f"items/{fname}.json")
            if not item:
                err(f"items/{fname}.json: missing ({name})")
                continue
            d = item["minecraft:item"]
            if d["description"]["identifier"] != ident:
                err(f"items/{fname}.json: identifier should be {ident}")
            comps = d.get("components", {})
            if comps.get("minecraft:icon") not in atlas:
                err(f"items/{fname}.json: icon {comps.get('minecraft:icon')!r} not in item_texture.json")
            # full orbs hold dynamic properties, which only work on non-stackable items
            if comps.get("minecraft:max_stack_size") != stack:
                err(f"items/{fname}.json: max_stack_size should be {stack}")
            if f"item.{ident}.name=" not in lang:
                err(f"texts/en_US.lang: missing item.{ident}.name=...")
            if f'"{ident}"' not in js:
                err(f"{rel(script)}: does not use {ident}")
        recipe = parsed.get(bp / f"recipes/{name}.json")
        if not recipe or recipe.get("minecraft:recipe_shaped", {}).get("result", {}).get("item") != f"mymod:{name}":
            err(f"recipes/{name}.json: missing or does not make mymod:{name}")
    for script in sorted((bp / "scripts").glob("*.js")):
        js = script.read_text(encoding="utf-8")
        for tag in re.findall(r'(?:addTag|removeTag|hasTag|DynamicProperty)\(\s*"([^"]+)"', js):
            if not tag.startswith("bigcat_"):
                err(f"{rel(script)}: tag/property {tag!r} must start with bigcat_")
        for prefix in re.findall(r'(?:PROP_[A-Z_]+|RECORD_PREFIX)\s*=\s*"([^"]+)"', js):
            if not prefix.startswith("bigcat_"):
                err(f"{rel(script)}: dynamic property {prefix!r} must start with bigcat_")


def validate_wands(paths, parsed, err) -> None:
    """Cross-checks for the Size Wand and Vapor Wand (scripts/wands.js + generated player.json)."""
    from gen_player import EVENTS, SIZES

    bp, rp = paths.bp, paths.rp
    atlas = parsed.get(rp / "textures/item_texture.json", {}).get("texture_data", {})
    lang = (rp / "texts/en_US.lang").read_text(encoding="utf-8")
    script = bp / "scripts/wands.js"
    js = script.read_text(encoding="utf-8") if script.is_file() else ""
    if 'import "./wands.js"' not in (bp / "scripts/main.js").read_text(encoding="utf-8"):
        err("scripts/main.js: must import ./wands.js")
    for name in ("size_wand", "vapor_wand"):
        ident = f"mymod:{name}"
        item = parsed.get(bp / f"items/{name}.json")
        if not item or item["minecraft:item"]["description"]["identifier"] != ident:
            err(f"items/{name}.json: missing or identifier is not {ident}")
        elif item["minecraft:item"]["components"].get("minecraft:icon") not in atlas:
            err(f"items/{name}.json: icon not in item_texture.json")
        recipe = parsed.get(bp / f"recipes/{name}.json")
        if not recipe or recipe.get("minecraft:recipe_shaped", {}).get("result", {}).get("item") != ident:
            err(f"recipes/{name}.json: missing or does not make {ident}")
        if f"item.{ident}.name=" not in lang:
            err(f"texts/en_US.lang: missing item.{ident}.name=...")
        if f'"{ident}"' not in js:
            err(f"{rel(script)}: does not use {ident}")
    player = parsed.get(bp / "entities/player.json")
    if not player:
        err("entities/player.json: missing (tools/gen_player.py)")
    else:
        events = player["minecraft:entity"].get("events", {})
        for ev in EVENTS.values():
            if ev not in events:
                err(f"entities/player.json: event {ev} missing")
        for size, scale in SIZES.items():
            if not re.search(rf"\b{size}: {re.escape(str(scale))}\b", js):
                err(f"{rel(script)}: SCALE.{size} should be {scale} (tools/gen_player.py SIZES)")
    for pid in re.findall(r'"(mymod:[a-z_]+)"', js):
        if pid.endswith(("_sparkle", "_vapor")):
            pfile = rp / "particles" / f"{pid.split(':')[1]}.particle.json"
            pdata = parsed.get(pfile)
            if not pdata or pdata["particle_effect"]["description"]["identifier"] != pid:
                err(f"{rel(pfile)}: missing or does not define {pid}")


def validate_grapple(paths, parsed, mev, err) -> list[str]:
    """Cross-checks for the Grappling Gun. Returns the RP texture paths it uses."""
    from gen_grapple import ALL_TEXTURES, HOOK_TEXTURE

    bp, rp = paths.bp, paths.rp
    gun, hook = "mymod:grappling_gun", "mymod:grapple_hook"
    atlas = parsed.get(rp / "textures/item_texture.json", {}).get("texture_data", {})
    lang = (rp / "texts/en_US.lang").read_text(encoding="utf-8")
    script = bp / "scripts/grapple.js"
    js = script.read_text(encoding="utf-8") if script.is_file() else ""
    if not js:
        err(f"{rel(script)}: missing (grappling gun)")
    if 'import "./grapple.js"' not in (bp / "scripts/main.js").read_text(encoding="utf-8"):
        err("scripts/main.js: must import ./grapple.js")

    item = parsed.get(bp / "items/grappling_gun.json")
    if not item or item["minecraft:item"]["description"]["identifier"] != gun:
        err(f"items/grappling_gun.json: missing or identifier is not {gun}")
    elif item["minecraft:item"]["components"].get("minecraft:icon") not in atlas:
        err("items/grappling_gun.json: icon not in item_texture.json")
    recipe = parsed.get(bp / "recipes/grappling_gun.json")
    if not recipe or recipe.get("minecraft:recipe_shaped", {}).get("result", {}).get("item") != gun:
        err(f"recipes/grappling_gun.json: missing or does not make {gun}")

    ent = parsed.get(bp / "entities/grapple_hook.json")
    if not ent or ent["minecraft:entity"]["description"]["identifier"] != hook:
        err(f"entities/grapple_hook.json: missing or identifier is not {hook}")
    else:
        fv = ent.get("format_version", "0")
        if mev and tuple(int(x) for x in fv.split(".")) > tuple(mev):
            err(f"entities/grapple_hook.json: format_version {fv} is newer than min_engine_version {mev}")
        comps = ent["minecraft:entity"].get("components", {})
        if "minecraft:projectile" not in comps:
            err("entities/grapple_hook.json: needs minecraft:projectile (the script calls shoot())")
        ds = comps.get("minecraft:damage_sensor", {}).get("triggers", {})
        if ds.get("cause") != "all" or ds.get("deals_damage") != "no":
            err("entities/grapple_hook.json: damage_sensor must block all damage")

    ce = parsed.get(rp / "entity/grapple_hook.entity.json")
    geo = parsed.get(rp / "models/entity/grapple_hook.geo.json")
    if not ce or ce["minecraft:client_entity"]["description"]["identifier"] != hook:
        err(f"entity/grapple_hook.entity.json: missing or identifier is not {hook}")
    else:
        desc = ce["minecraft:client_entity"]["description"]
        if desc.get("textures", {}).get("default") != HOOK_TEXTURE:
            err(f"entity/grapple_hook.entity.json: default texture should be {HOOK_TEXTURE}")
        gid = desc.get("geometry", {}).get("default")
        if not geo or gid not in [g["description"]["identifier"] for g in geo.get("minecraft:geometry", [])]:
            err(f"entity/grapple_hook.entity.json: geometry {gid} not defined in models/entity/grapple_hook.geo.json")

    for key in (f"item.{gun}.name", f"entity.{hook}.name"):
        if f"{key}=" not in lang:
            err(f"texts/en_US.lang: missing {key}=...")
    for pid in re.findall(r'"(mymod:[a-z_]+)"', js):
        if pid in (gun, hook):
            continue
        pfile = rp / "particles" / f"{pid.split(':')[1]}.particle.json"
        pdata = parsed.get(pfile)
        if not pdata or pdata["particle_effect"]["description"]["identifier"] != pid:
            err(f"{rel(pfile)}: missing or does not define {pid}")
    for needle in (gun, hook):
        if js and f'"{needle}"' not in js:
            err(f"{rel(script)}: does not use {needle}")
    return list(ALL_TEXTURES)


def validate_evolution(paths, parsed, bp_ent, ce, err) -> list[str]:
    """Cross-checks for the Evolution Stone and the stage-8 wings. Returns the item icon textures."""
    from gen_evolution import ALL_TEXTURES, EVENT, GROUP, MAX_STAGE, PROPERTY, STAGES, STONE_ID, WING_TEXTURE
    from gen_json import WING_RC, wing_condition

    bp, rp = paths.bp, paths.rp
    atlas = parsed.get(rp / "textures/item_texture.json", {}).get("texture_data", {})
    lang = (rp / "texts/en_US.lang").read_text(encoding="utf-8")
    script = bp / "scripts/evolution.js"
    js = script.read_text(encoding="utf-8") if script.is_file() else ""
    if not js:
        err(f"{rel(script)}: missing (evolution stone)")
    if 'import "./evolution.js"' not in (bp / "scripts/main.js").read_text(encoding="utf-8"):
        err("scripts/main.js: must import ./evolution.js")
    if js and f'"{STONE_ID}"' not in js:
        err(f"{rel(script)}: does not use {STONE_ID}")
    if js and f'"{PROPERTY}"' not in js:
        err(f"{rel(script)}: does not read {PROPERTY}")

    # the script's stage list must match tools/gen_evolution.py STAGES
    js_stages = re.findall(r'\{ name: "([^"]+)", color: "[^"]*", particle: "([^"]+)" \}', js)
    want = [(s[0], s[1]) for s in STAGES]
    if js and js_stages != want:
        err(f"{rel(script)}: STAGES {js_stages} do not match tools/gen_evolution.py {want}")

    item = parsed.get(bp / "items/evolution_stone.json")
    if not item or item["minecraft:item"]["description"]["identifier"] != STONE_ID:
        err(f"items/evolution_stone.json: missing or identifier is not {STONE_ID}")
    elif item["minecraft:item"]["components"].get("minecraft:icon") not in atlas:
        err("items/evolution_stone.json: icon not in item_texture.json")
    if f"item.{STONE_ID}.name=" not in lang:
        err(f"texts/en_US.lang: missing item.{STONE_ID}.name=...")

    if bp_ent:
        e = bp_ent["minecraft:entity"]
        pdef = e["description"].get("properties", {}).get(PROPERTY, {})
        if pdef.get("range") != [0, MAX_STAGE] or pdef.get("client_sync") is not True:
            err(f"BP entity: {PROPERTY} must be an int 0..{MAX_STAGE} with client_sync (wings read it)")
        cg, events = e.get("component_groups", {}), e.get("events", {})
        for n in range(1, MAX_STAGE + 1):
            if "minecraft:health" not in cg.get(GROUP.format(n=n), {}):
                err(f"BP entity: component group {GROUP.format(n=n)} missing or has no health")
            ev = events.get(EVENT.format(n=n), {})
            if {PROPERTY: n} not in [step.get("set_property") for step in ev.get("sequence", [])]:
                err(f"BP entity: {EVENT.format(n=n)} does not set {PROPERTY} to {n}")

    if ce:
        desc = ce["minecraft:client_entity"]["description"]
        if desc.get("textures", {}).get("wings") != WING_TEXTURE:
            err(f"client entity: texture 'wings' should be {WING_TEXTURE}")
        rcl = desc.get("render_controllers", [])
        if WING_RC not in rcl:
            err(f"client entity: render controller {WING_RC} missing")
        if mismatch := [r for r in rcl if not isinstance(r, str)]:
            err(f"client entity: render_controllers must be plain strings in format 1.8.0, got {mismatch}")
        geo_id = desc.get("geometry", {}).get("wings")
        geo = parsed.get(rp / "models/entity/big_cat_wings.geo.json", {})
        if geo_id not in [g["description"]["identifier"] for g in geo.get("minecraft:geometry", [])]:
            err(f"client entity: geometry 'wings' ({geo_id}) not defined in models/entity/big_cat_wings.geo.json")
        if "wings" not in desc.get("materials", {}):
            err("client entity: material 'wings' missing")
        anim_id = desc.get("animations", {}).get("wings")
        anims = parsed.get(rp / "animations/big_cat_wings.animation.json", {}).get("animations", {})
        if anim_id not in anims:
            err(f"client entity: animation 'wings' ({anim_id}) not in animations/big_cat_wings.animation.json")
    rcs = parsed.get(rp / "render_controllers/big_cat_wings.render_controllers.json", {})
    if WING_RC not in rcs.get("render_controllers", {}):
        err(f"render_controllers/big_cat_wings.render_controllers.json: {WING_RC} missing")
    elif rcs["render_controllers"][WING_RC].get("part_visibility") != [{"*": wing_condition()}]:
        err(
            "render_controllers/big_cat_wings.render_controllers.json: part_visibility should be "
            f'[{{"*": "{wing_condition()}"}}] so the wings only show at the last stage'
        )
    return list(ALL_TEXTURES)


def validate_net_trap(paths, parsed, err) -> list[str]:
    """Cross-checks for the Net Trap block, its item and script. Returns the textures it uses."""
    from gen_net import ALL_TEXTURES, BLOCK_TEXTURE, ICON_TEXTURE, NET_ID

    bp, rp = paths.bp, paths.rp
    lang = (rp / "texts/en_US.lang").read_text(encoding="utf-8")
    script = bp / "scripts/net_trap.js"
    js = script.read_text(encoding="utf-8") if script.is_file() else ""
    if not js:
        err(f"{rel(script)}: missing (net trap)")
    elif f'"{NET_ID}"' not in js or "registerCustomComponent(NET_ID" not in js:
        err(f"{rel(script)}: must register the custom block component {NET_ID}")
    if 'import "./net_trap.js"' not in (bp / "scripts/main.js").read_text(encoding="utf-8"):
        err("scripts/main.js: must import ./net_trap.js")

    block = parsed.get(bp / "blocks/net_trap.json")
    if not block or block["minecraft:block"]["description"]["identifier"] != NET_ID:
        err(f"blocks/net_trap.json: missing or identifier is not {NET_ID}")
    else:
        comps = block["minecraft:block"]["components"]
        if NET_ID not in comps:
            err(f"blocks/net_trap.json: needs the custom component {NET_ID} (the script's step-on trigger)")
        box = comps.get("minecraft:collision_box")
        if not isinstance(box, dict) or not box.get("size", [0, 0, 0])[1] > 0:
            err("blocks/net_trap.json: needs a collision_box with some height, or onStepOn never fires")
        gid = comps.get("minecraft:geometry")
        geo = parsed.get(rp / "models/blocks/net_trap.geo.json", {})
        if gid not in [g["description"]["identifier"] for g in geo.get("minecraft:geometry", [])]:
            err(f"blocks/net_trap.json: geometry {gid} not defined in models/blocks/net_trap.geo.json")
        terrain = parsed.get(rp / "textures/terrain_texture.json", {}).get("texture_data", {})
        tex = comps.get("minecraft:material_instances", {}).get("*", {}).get("texture")
        if terrain.get(tex, {}).get("textures") != BLOCK_TEXTURE:
            err(f"blocks/net_trap.json: texture {tex!r} should map to {BLOCK_TEXTURE} in terrain_texture.json")

    item = parsed.get(bp / "items/net_trap.json")
    atlas = parsed.get(rp / "textures/item_texture.json", {}).get("texture_data", {})
    if not item or item["minecraft:item"]["description"]["identifier"] != NET_ID:
        err(f"items/net_trap.json: missing or identifier is not {NET_ID}")
    else:
        comps = item["minecraft:item"]["components"]
        placer = comps.get("minecraft:block_placer", {})
        if placer.get("block") != NET_ID or placer.get("replace_block_item") is not True:
            err(f"items/net_trap.json: block_placer must place {NET_ID} with replace_block_item")
        if atlas.get(comps.get("minecraft:icon"), {}).get("textures") != ICON_TEXTURE:
            err(f"items/net_trap.json: icon should map to {ICON_TEXTURE} in item_texture.json")
    recipe = parsed.get(bp / "recipes/net_trap.json")
    if not recipe or recipe.get("minecraft:recipe_shaped", {}).get("result", {}).get("item") != NET_ID:
        err(f"recipes/net_trap.json: missing or does not make {NET_ID}")
    if f"item.{NET_ID}.name=" not in lang:
        err(f"texts/en_US.lang: missing item.{NET_ID}.name=...")
    return list(ALL_TEXTURES)


def validate_morph(paths, parsed, err) -> list[str]:
    """Cross-checks for the Morph Wand (scripts/morph.js + tools/gen_morph.py). Returns its textures."""
    from gen_morph import ALL_TEXTURES, FORMS, ICON_TEXTURE, RC, WAND_ID, entity_id, forms_js

    bp, rp = paths.bp, paths.rp
    if 'import "./morph.js"' not in (bp / "scripts/main.js").read_text(encoding="utf-8"):
        err("scripts/main.js: must import ./morph.js")
    script = bp / "scripts/morph.js"
    js = script.read_text(encoding="utf-8") if script.is_file() else ""
    if f'"{WAND_ID}"' not in js or '"./morph_forms.js"' not in js:
        err(f"{rel(script)}: missing, or does not use {WAND_ID} and ./morph_forms.js")
    for f in FORMS:
        if not re.search(rf"^\s*{f.key}: \{{", js, re.M) or not re.search(rf'^\s*{f.key}: "', js, re.M):
            err(f"{rel(script)}: PERKS and PERK_TEXT need an entry for {f.key} (tools/gen_morph.py FORMS)")
    forms = bp / "scripts/morph_forms.js"
    if not forms.is_file() or forms.read_text(encoding="utf-8") != forms_js():
        err(f"{rel(forms)}: missing or stale; run tools/gen_morph.py")

    rcs = parsed.get(rp / "render_controllers/morph.render_controllers.json", {}).get("render_controllers", {})
    for f in FORMS:
        ident = entity_id(f)
        ent = parsed.get(bp / f"entities/morph_{f.key}.json")
        if not ent or ent["minecraft:entity"]["description"]["identifier"] != ident:
            err(f"entities/morph_{f.key}.json: missing or identifier is not {ident}")
        ce = parsed.get(rp / f"entity/morph_{f.key}.entity.json")
        desc = ce["minecraft:client_entity"]["description"] if ce else {}
        if desc.get("identifier") != ident:
            err(f"entity/morph_{f.key}.entity.json: missing or identifier is not {ident}")
        elif len(desc.get("geometry", {})) != 1:
            err(f"entity/morph_{f.key}.entity.json: exactly one geometry (more log locator errors in game)")
        name = RC.format(key=f.key)
        if desc and (name not in desc.get("render_controllers", []) or name not in rcs):
            err(f"entity/morph_{f.key}.entity.json: render controller {name} missing or not defined")
    for old in ("entities/morph.json",):
        if (bp / old).is_file():
            err(f"{old}: the old single costume entity; delete it (one entity per form now)")
    for js_file in sorted((bp / "scripts").glob("*.js")):
        if '"mymod:morph"' in js_file.read_text(encoding="utf-8"):
            err(f"{rel(js_file)}: uses the old id mymod:morph; costumes are mymod:morph_<form> (check startsWith)")

    atlas = parsed.get(rp / "textures/item_texture.json", {}).get("texture_data", {})
    item = parsed.get(bp / "items/morph_wand.json")
    if not item or item["minecraft:item"]["description"]["identifier"] != WAND_ID:
        err(f"items/morph_wand.json: missing or identifier is not {WAND_ID}")
    elif atlas.get(item["minecraft:item"]["components"].get("minecraft:icon"), {}).get("textures") != ICON_TEXTURE:
        err(f"items/morph_wand.json: icon should map to {ICON_TEXTURE} in item_texture.json")
    recipe = parsed.get(bp / "recipes/morph_wand.json")
    if not recipe or recipe.get("minecraft:recipe_shaped", {}).get("result", {}).get("item") != WAND_ID:
        err(f"recipes/morph_wand.json: missing or does not make {WAND_ID}")
    if f"item.{WAND_ID}.name=" not in (rp / "texts/en_US.lang").read_text(encoding="utf-8"):
        err(f"texts/en_US.lang: missing item.{WAND_ID}.name=...")
    return list(ALL_TEXTURES)


def validate_drowned_trap(paths, parsed, mev, err) -> list[str]:
    """Cross-checks for the Drowned Trap. Returns the RP texture paths it uses."""
    from gen_drowned_trap import ALL_TEXTURES, LURE_TEXTURE, TARGET_GOAL, TRAP_FAMILY

    bp, rp = paths.bp, paths.rp
    item_id, lure_id = "mymod:drowned_trap", "mymod:drowned_lure"
    atlas = parsed.get(rp / "textures/item_texture.json", {}).get("texture_data", {})
    lang = (rp / "texts/en_US.lang").read_text(encoding="utf-8")
    script = bp / "scripts/drowned_trap.js"
    js = script.read_text(encoding="utf-8") if script.is_file() else ""
    if not js:
        err(f"{rel(script)}: missing (drowned trap)")
    if 'import "./drowned_trap.js"' not in (bp / "scripts/main.js").read_text(encoding="utf-8"):
        err("scripts/main.js: must import ./drowned_trap.js")

    item = parsed.get(bp / "items/drowned_trap.json")
    if not item or item["minecraft:item"]["description"]["identifier"] != item_id:
        err(f"items/drowned_trap.json: missing or identifier is not {item_id}")
    elif item["minecraft:item"]["components"].get("minecraft:icon") not in atlas:
        err("items/drowned_trap.json: icon not in item_texture.json")
    recipe = parsed.get(bp / "recipes/drowned_trap.json")
    if not recipe or recipe.get("minecraft:recipe_shaped", {}).get("result", {}).get("item") != item_id:
        err(f"recipes/drowned_trap.json: missing or does not make {item_id}")

    lure = parsed.get(bp / "entities/drowned_lure.json")
    if not lure or lure["minecraft:entity"]["description"]["identifier"] != lure_id:
        err(f"entities/drowned_lure.json: missing or identifier is not {lure_id}")
    else:
        fv = lure.get("format_version", "0")
        if mev and tuple(int(x) for x in fv.split(".")) > tuple(mev):
            err(f"entities/drowned_lure.json: format_version {fv} is newer than min_engine_version {mev}")
        comps = lure["minecraft:entity"].get("components", {})
        if TRAP_FAMILY not in comps.get("minecraft:type_family", {}).get("family", []):
            err(f"entities/drowned_lure.json: type_family must include {TRAP_FAMILY} (drowned target it)")
        ds = comps.get("minecraft:damage_sensor", {}).get("triggers", {})
        if ds.get("cause") != "all" or ds.get("deals_damage") != "no":
            err("entities/drowned_lure.json: damage_sensor must block all damage")

    drowned = parsed.get(bp / "entities/drowned.json")
    if not drowned:
        err("entities/drowned.json: missing (tools/gen_drowned_trap.py)")
    else:
        goal = drowned["minecraft:entity"].get("components", {}).get(TARGET_GOAL, {})
        if TRAP_FAMILY not in json.dumps(goal.get("entity_types", [])):
            err(f"entities/drowned.json: {TARGET_GOAL} does not target the {TRAP_FAMILY} family")

    ce = parsed.get(rp / "entity/drowned_lure.entity.json")
    geo = parsed.get(rp / "models/entity/drowned_lure.geo.json")
    if not ce or ce["minecraft:client_entity"]["description"]["identifier"] != lure_id:
        err(f"entity/drowned_lure.entity.json: missing or identifier is not {lure_id}")
    else:
        desc = ce["minecraft:client_entity"]["description"]
        if desc.get("textures", {}).get("default") != LURE_TEXTURE:
            err(f"entity/drowned_lure.entity.json: default texture should be {LURE_TEXTURE}")
        gid = desc.get("geometry", {}).get("default")
        if not geo or gid not in [g["description"]["identifier"] for g in geo.get("minecraft:geometry", [])]:
            err(f"entity/drowned_lure.entity.json: geometry {gid} not defined in models/entity/drowned_lure.geo.json")

    for key in (f"item.{item_id}.name", f"entity.{lure_id}.name"):
        if f"{key}=" not in lang:
            err(f"texts/en_US.lang: missing {key}=...")
    for needle in (item_id, lure_id):
        if js and f'"{needle}"' not in js:
            err(f"{rel(script)}: does not use {needle}")
    return list(ALL_TEXTURES)


def validate_air_cannon(paths, parsed, err) -> list[str]:
    """Cross-checks for the Air Cannon. Returns the RP texture paths it uses."""
    from gen_air_cannon import ALL_TEXTURES

    bp, rp = paths.bp, paths.rp
    item_id = "mymod:air_cannon"
    atlas = parsed.get(rp / "textures/item_texture.json", {}).get("texture_data", {})
    script = bp / "scripts/air_cannon.js"
    js = script.read_text(encoding="utf-8") if script.is_file() else ""
    if f'"{item_id}"' not in js:
        err(f"{rel(script)}: missing, or does not use {item_id}")
    if 'import "./air_cannon.js"' not in (bp / "scripts/main.js").read_text(encoding="utf-8"):
        err("scripts/main.js: must import ./air_cannon.js")
    item = parsed.get(bp / "items/air_cannon.json")
    if not item or item["minecraft:item"]["description"]["identifier"] != item_id:
        err(f"items/air_cannon.json: missing or identifier is not {item_id}")
    elif item["minecraft:item"]["components"].get("minecraft:icon") not in atlas:
        err("items/air_cannon.json: icon not in item_texture.json")
    recipe = parsed.get(bp / "recipes/air_cannon.json")
    if not recipe or recipe.get("minecraft:recipe_shaped", {}).get("result", {}).get("item") != item_id:
        err(f"recipes/air_cannon.json: missing or does not make {item_id}")
    if f"item.{item_id}.name=" not in (rp / "texts/en_US.lang").read_text(encoding="utf-8"):
        err(f"texts/en_US.lang: missing item.{item_id}.name=...")
    return list(ALL_TEXTURES)


def validate_blocks(paths, parsed, err) -> None:
    """Minecraft refuses a block (and every recipe for it) that has textures but no geometry."""
    for f in sorted((paths.bp / "blocks").glob("*.json")):
        comps = parsed.get(f, {}).get("minecraft:block", {}).get("components", {})
        if "minecraft:material_instances" in comps and "minecraft:geometry" not in comps:
            err(
                f"blocks/{f.name}: has material_instances but no minecraft:geometry (use minecraft:geometry.full_block)"
            )


def validate_blaster(paths, parsed, err) -> list[str]:
    """Cross-checks for the Laser, Flame, Water, Ice and Barf Blasters (scripts/blaster.js). Returns their textures."""
    from gen_blaster import (
        ALL_TEXTURES,
        BARF_ID,
        BARF_TEXTURE,
        BLASTER_ID,
        FLAME_ID,
        FLAME_TEXTURE,
        ICE_ID,
        ICE_TEXTURE,
        ICON_TEXTURE,
        WATER_ID,
        WATER_TEXTURE,
    )

    bp, rp = paths.bp, paths.rp
    if 'import "./blaster.js"' not in (bp / "scripts/main.js").read_text(encoding="utf-8"):
        err("scripts/main.js: must import ./blaster.js")
    script = bp / "scripts/blaster.js"
    js = script.read_text(encoding="utf-8") if script.is_file() else ""
    for name in ("laser_beam", "laser_glow", "fire_beam", "water_beam", "ice_beam", "barf_beam", "barf_spew"):
        pid = f"mymod:{name}"
        particle = parsed.get(rp / f"particles/{name}.particle.json")
        if not particle or particle["particle_effect"]["description"]["identifier"] != pid or f'"{pid}"' not in js:
            err(f"particles/{name}.particle.json: missing or does not define {pid} (used by {rel(script)})")
    atlas = parsed.get(rp / "textures/item_texture.json", {}).get("texture_data", {})
    lang = (rp / "texts/en_US.lang").read_text(encoding="utf-8")
    blasters = (
        (BLASTER_ID, ICON_TEXTURE),
        (FLAME_ID, FLAME_TEXTURE),
        (WATER_ID, WATER_TEXTURE),
        (ICE_ID, ICE_TEXTURE),
        (BARF_ID, BARF_TEXTURE),
    )
    for item_id, texture in blasters:
        name = item_id.split(":")[1]
        if f'"{item_id}"' not in js:
            err(f"{rel(script)}: missing or does not use {item_id}")
        item = parsed.get(bp / f"items/{name}.json")
        if not item or item["minecraft:item"]["description"]["identifier"] != item_id:
            err(f"items/{name}.json: missing or identifier is not {item_id}")
        else:
            comps = item["minecraft:item"]["components"]
            if comps.get("minecraft:use_modifiers", {}).get("use_duration", 0) < 60:
                err(f"items/{name}.json: needs minecraft:use_modifiers with a long use_duration (hold to fire)")
            if atlas.get(comps.get("minecraft:icon"), {}).get("textures") != texture:
                err(f"items/{name}.json: icon should map to {texture} in item_texture.json")
        recipe = parsed.get(bp / f"recipes/{name}.json")
        if not recipe or recipe.get("minecraft:recipe_shaped", {}).get("result", {}).get("item") != item_id:
            err(f"recipes/{name}.json: missing or does not make {item_id}")
        if f"item.{item_id}.name=" not in lang:
            err(f"texts/en_US.lang: missing item.{item_id}.name=...")
    return list(ALL_TEXTURES)


def validate_atomic_bomb(paths, parsed, err) -> list[str]:
    """Cross-checks for the Atomic Bomb block and script. Returns the RP texture paths it uses."""
    from gen_atomic_bomb import ALL_TEXTURES, BOMB_ID, TERRAIN

    bp, rp = paths.bp, paths.rp
    script = bp / "scripts/atomic_bomb.js"
    js = script.read_text(encoding="utf-8") if script.is_file() else ""
    if f'"{BOMB_ID}"' not in js:
        err(f"{rel(script)}: missing, or does not use {BOMB_ID}")
    if 'import "./atomic_bomb.js"' not in (bp / "scripts/main.js").read_text(encoding="utf-8"):
        err("scripts/main.js: must import ./atomic_bomb.js")
    block = parsed.get(bp / "blocks/atomic_bomb.json")
    if not block or block["minecraft:block"]["description"]["identifier"] != BOMB_ID:
        err(f"blocks/atomic_bomb.json: missing or identifier is not {BOMB_ID}")
    else:
        terrain = parsed.get(rp / "textures/terrain_texture.json", {}).get("texture_data", {})
        mats = block["minecraft:block"]["components"].get("minecraft:material_instances", {})
        for face, m in mats.items():
            tex = m.get("texture")
            if tex not in TERRAIN or terrain.get(tex, {}).get("textures") != TERRAIN[tex]:
                err(f"blocks/atomic_bomb.json: {face} texture {tex!r} is not mapped in terrain_texture.json")
    recipe = parsed.get(bp / "recipes/atomic_bomb.json")
    if not recipe or recipe.get("minecraft:recipe_shaped", {}).get("result", {}).get("item") != BOMB_ID:
        err(f"recipes/atomic_bomb.json: missing or does not make {BOMB_ID}")
    if f"tile.{BOMB_ID}.name=" not in (rp / "texts/en_US.lang").read_text(encoding="utf-8"):
        err(f"texts/en_US.lang: missing tile.{BOMB_ID}.name=...")
    return list(ALL_TEXTURES)


def validate_mountain(paths, parsed, err) -> list[str]:
    """Cross-checks for the Mountain Seed. Returns the RP texture paths it uses."""
    from gen_mountain import ALL_TEXTURES

    bp, rp = paths.bp, paths.rp
    item_id = "mymod:mountain_seed"
    atlas = parsed.get(rp / "textures/item_texture.json", {}).get("texture_data", {})
    script = bp / "scripts/mountain.js"
    js = script.read_text(encoding="utf-8") if script.is_file() else ""
    if f'"{item_id}"' not in js:
        err(f"{rel(script)}: missing, or does not use {item_id}")
    if 'import "./mountain.js"' not in (bp / "scripts/main.js").read_text(encoding="utf-8"):
        err("scripts/main.js: must import ./mountain.js")
    item = parsed.get(bp / "items/mountain_seed.json")
    if not item or item["minecraft:item"]["description"]["identifier"] != item_id:
        err(f"items/mountain_seed.json: missing or identifier is not {item_id}")
    elif item["minecraft:item"]["components"].get("minecraft:icon") not in atlas:
        err("items/mountain_seed.json: icon not in item_texture.json")
    recipe = parsed.get(bp / "recipes/mountain_seed.json")
    if not recipe or recipe.get("minecraft:recipe_shaped", {}).get("result", {}).get("item") != item_id:
        err(f"recipes/mountain_seed.json: missing or does not make {item_id}")
    if f"item.{item_id}.name=" not in (rp / "texts/en_US.lang").read_text(encoding="utf-8"):
        err(f"texts/en_US.lang: missing item.{item_id}.name=...")
    return list(ALL_TEXTURES)


def validate_vortex(paths, parsed, err) -> list[str]:
    """Cross-checks for the two Vortex Guns (monsters / animals). Returns the RP texture paths they use."""
    from gen_vortex import ALL_TEXTURES

    bp, rp = paths.bp, paths.rp
    atlas = parsed.get(rp / "textures/item_texture.json", {}).get("texture_data", {})
    lang = (rp / "texts/en_US.lang").read_text(encoding="utf-8")
    script = bp / "scripts/vortex.js"
    js = script.read_text(encoding="utf-8") if script.is_file() else ""
    if 'import "./vortex.js"' not in (bp / "scripts/main.js").read_text(encoding="utf-8"):
        err("scripts/main.js: must import ./vortex.js")
    for name in ("vortex_gun", "animal_vortex_gun"):
        item_id = f"mymod:{name}"
        if f'"{item_id}"' not in js:
            err(f"{rel(script)}: missing, or does not use {item_id}")
        item = parsed.get(bp / f"items/{name}.json")
        if not item or item["minecraft:item"]["description"]["identifier"] != item_id:
            err(f"items/{name}.json: missing or identifier is not {item_id}")
        elif item["minecraft:item"]["components"].get("minecraft:icon") not in atlas:
            err(f"items/{name}.json: icon not in item_texture.json")
        recipe = parsed.get(bp / f"recipes/{name}.json")
        if not recipe or recipe.get("minecraft:recipe_shaped", {}).get("result", {}).get("item") != item_id:
            err(f"recipes/{name}.json: missing or does not make {item_id}")
        if f"item.{item_id}.name=" not in lang:
            err(f"texts/en_US.lang: missing item.{item_id}.name=...")
    return list(ALL_TEXTURES)


def validate_mooshroom_drill(paths, parsed, mev, err) -> list[str]:
    """Cross-checks for the Mooshroom Drill (scripts/drill.js + tools/gen_mooshroom_drill.py). Returns its textures."""
    from gen_mooshroom_drill import (
        ALL_TEXTURES,
        ENTITY_TEXTURE,
        GEO_FILE,
        GEOMETRY_ID,
        ICON_TEXTURE,
        ITEM_ID,
        VEHICLE_ID,
    )

    bp, rp = paths.bp, paths.rp
    if 'import "./drill.js"' not in (bp / "scripts/main.js").read_text(encoding="utf-8"):
        err("scripts/main.js: must import ./drill.js")
    script = bp / "scripts/drill.js"
    js = script.read_text(encoding="utf-8") if script.is_file() else ""
    for needle in (ITEM_ID, VEHICLE_ID, "mymod:drilling"):
        if f'"{needle}"' not in js:
            err(f"{rel(script)}: missing, or does not use {needle}")

    ent = parsed.get(bp / "entities/mooshroom_drill_vehicle.json")
    if not ent or ent["minecraft:entity"]["description"]["identifier"] != VEHICLE_ID:
        err(f"entities/mooshroom_drill_vehicle.json: missing or identifier is not {VEHICLE_ID}")
    else:
        fv = ent.get("format_version", "0")
        if mev and tuple(int(x) for x in fv.split(".")) > tuple(mev):
            err(f"entities/mooshroom_drill_vehicle.json: format_version {fv} is newer than min_engine_version {mev}")
        prop = ent["minecraft:entity"]["description"].get("properties", {}).get("mymod:drilling", {})
        if prop.get("type") != "bool" or prop.get("client_sync") is not True:
            err("entities/mooshroom_drill_vehicle.json: mymod:drilling must be a client_sync bool (starts the spin)")
        comps = ent["minecraft:entity"].get("components", {})
        ds = comps.get("minecraft:damage_sensor", {}).get("triggers", {})
        if ds.get("cause") != "all" or ds.get("deals_damage") != "no":
            err("entities/mooshroom_drill_vehicle.json: damage_sensor must block all damage (mooshroom never hurt)")
        # 1.26.50 split minecraft:pushable in two; the old name makes the whole entity fail to load
        if "minecraft:pushable" in comps:
            err("entities/mooshroom_drill_vehicle.json: minecraft:pushable no longer exists (use pushable_by_block)")
        for must in ("minecraft:rideable", "minecraft:input_ground_controlled", "minecraft:movement"):
            if must not in comps:
                err(f"entities/mooshroom_drill_vehicle.json: {must} missing (it can't be driven)")

    ce = parsed.get(rp / "entity/mooshroom_drill_vehicle.entity.json")
    rcf = parsed.get(rp / "render_controllers/mooshroom_drill.render_controllers.json", {})
    rcs = rcf.get("render_controllers", {})
    anims = parsed.get(rp / "animations/mooshroom_drill.animation.json", {}).get("animations", {})
    geo = parsed.get(rp / GEO_FILE)
    if not ce or ce["minecraft:client_entity"]["description"]["identifier"] != VEHICLE_ID:
        err(f"entity/mooshroom_drill_vehicle.entity.json: missing or identifier is not {VEHICLE_ID}")
    else:
        desc = ce["minecraft:client_entity"]["description"]
        if desc.get("textures", {}).get("default") != ENTITY_TEXTURE:
            err(f"entity/mooshroom_drill_vehicle.entity.json: default texture should be {ENTITY_TEXTURE}")
        if desc.get("geometry", {}).get("default") != GEOMETRY_ID or not geo:
            err(f"entity/mooshroom_drill_vehicle.entity.json: default geometry should be {GEOMETRY_ID} ({GEO_FILE})")
        for name in desc.get("render_controllers", []):
            if name not in rcs:
                err(f"entity/mooshroom_drill_vehicle.entity.json: render controller {name} not defined")
        for short, anim in desc.get("animations", {}).items():
            if anim not in anims:
                err(f"entity/mooshroom_drill_vehicle.entity.json: animation {short} ({anim}) not defined")
        spin = anims.get(desc.get("animations", {}).get("spin"), {}).get("bones", {})
        if not {"body", "head"} <= set(spin):
            err("animations/mooshroom_drill.animation.json: spin must turn the body and head bones")

    atlas = parsed.get(rp / "textures/item_texture.json", {}).get("texture_data", {})
    item = parsed.get(bp / "items/mooshroom_drill.json")
    if not item or item["minecraft:item"]["description"]["identifier"] != ITEM_ID:
        err(f"items/mooshroom_drill.json: missing or identifier is not {ITEM_ID}")
    elif atlas.get(item["minecraft:item"]["components"].get("minecraft:icon"), {}).get("textures") != ICON_TEXTURE:
        err(f"items/mooshroom_drill.json: icon should map to {ICON_TEXTURE} in item_texture.json")
    recipe = parsed.get(bp / "recipes/mooshroom_drill.json")
    if not recipe or recipe.get("minecraft:recipe_shaped", {}).get("result", {}).get("item") != ITEM_ID:
        err(f"recipes/mooshroom_drill.json: missing or does not make {ITEM_ID}")
    lang = (rp / "texts/en_US.lang").read_text(encoding="utf-8")
    for key in (f"item.{ITEM_ID}.name", f"entity.{VEHICLE_ID}.name"):
        if f"{key}=" not in lang:
            err(f"texts/en_US.lang: missing {key}=...")
    return list(ALL_TEXTURES)


def validate_portal(paths, parsed, err) -> list[str]:
    """Cross-checks for the Portal Pads (scripts/portal.js + tools/gen_portal.py). Returns their textures."""
    from gen_portal import (
        ALL_TEXTURES,
        COLORS,
        GEOMETRY_ID,
        ICON_TEXTURE,
        PAD_ID,
        atlas_key,
        block,
        colors_js,
        texture_path,
    )

    bp, rp = paths.bp, paths.rp
    if 'import "./portal.js"' not in (bp / "scripts/main.js").read_text(encoding="utf-8"):
        err("scripts/main.js: must import ./portal.js")
    script = bp / "scripts/portal.js"
    js = script.read_text(encoding="utf-8") if script.is_file() else ""
    if f'"{PAD_ID}"' not in js or '"./portal_colors.js"' not in js or '"mymod:portal_swirl"' not in js:
        err(f"{rel(script)}: missing, or does not use {PAD_ID}, ./portal_colors.js and mymod:portal_swirl")
    colors = bp / "scripts/portal_colors.js"
    if not colors.is_file() or colors.read_text(encoding="utf-8") != colors_js():
        err(f"{rel(colors)}: missing or stale; run tools/gen_portal.py")
    if parsed.get(bp / "blocks/portal_pad.json") != block():
        err("blocks/portal_pad.json: missing or stale; run tools/gen_portal.py")

    terrain = parsed.get(rp / "textures/terrain_texture.json", {}).get("texture_data", {})
    for c in COLORS:
        if terrain.get(atlas_key(c), {}).get("textures") != texture_path(c):
            err(f"textures/terrain_texture.json: {atlas_key(c)} should map to {texture_path(c)}")
    geo = parsed.get(rp / "models/blocks/portal_pad.geo.json", {})
    if GEOMETRY_ID not in [g["description"]["identifier"] for g in geo.get("minecraft:geometry", [])]:
        err(f"models/blocks/portal_pad.geo.json: missing or does not define {GEOMETRY_ID}")
    particle = parsed.get(rp / "particles/portal_swirl.particle.json")
    if not particle or particle["particle_effect"]["description"]["identifier"] != "mymod:portal_swirl":
        err("particles/portal_swirl.particle.json: missing or does not define mymod:portal_swirl")

    atlas = parsed.get(rp / "textures/item_texture.json", {}).get("texture_data", {})
    item = parsed.get(bp / "items/portal_pad.json")
    if not item or item["minecraft:item"]["description"]["identifier"] != PAD_ID:
        err(f"items/portal_pad.json: missing or identifier is not {PAD_ID}")
    else:
        comps = item["minecraft:item"]["components"]
        if atlas.get(comps.get("minecraft:icon"), {}).get("textures") != ICON_TEXTURE:
            err(f"items/portal_pad.json: icon should map to {ICON_TEXTURE} in item_texture.json")
        if comps.get("minecraft:block_placer", {}).get("block") != PAD_ID:
            err(f"items/portal_pad.json: minecraft:block_placer must place {PAD_ID}")
    recipe = parsed.get(bp / "recipes/portal_pad.json")
    if not recipe or recipe.get("minecraft:recipe_shaped", {}).get("result", {}).get("item") != PAD_ID:
        err(f"recipes/portal_pad.json: missing or does not make {PAD_ID}")
    lang = (rp / "texts/en_US.lang").read_text(encoding="utf-8")
    for key in (f"item.{PAD_ID}.name", f"tile.{PAD_ID}.name"):
        if f"{key}=" not in lang:
            err(f"texts/en_US.lang: missing {key}=...")
    return list(ALL_TEXTURES)


def _fail(errors):
    raise BuildError("validation failed:\n    - " + "\n    - ".join(errors))


if __name__ == "__main__":
    try:
        validate()
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
