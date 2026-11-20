"""Validate both packs. Collects every problem, prints them all, raises BuildError if any.

Checks JSON syntax, Mojang JSON schemas (items; from bedrock-samples/metadata/json_schemas),
manifests, recipes, attachables (geometry/animation/render controller ids exist in vanilla),
textures, lang, and that scripts/main.js only uses @minecraft/server 2.11.0 API names that
exist in bedrock-samples/metadata/script_modules.

Run standalone:  python tools/validate.py
"""
from __future__ import annotations

import json
import re
import sys
import uuid
from pathlib import Path

from PIL import Image

from common import ROOT, BuildError, load_config, load_json, rel, texture_key
from schema_check import SchemaStore

SCRIPT_MODULE = "@minecraft/server"
SCRIPT_VERSION = "2.11.0"
MIN_ENGINE = [1, 26, 60]
TEXTURE_EXTS = (".png", ".tga")
ARMOR_MATERIALS = {"armor", "armor_enchanted", "armor_leather", "armor_leather_enchanted"}
ENCHANT_FOR_SLOT = {"slot.armor.head": "armor_head", "slot.armor.chest": "armor_torso",
                    "slot.armor.legs": "armor_legs", "slot.armor.feet": "armor_feet"}
ALLOWED_TOP = {
    "manifest.json": {"format_version", "header", "modules", "dependencies", "metadata", "capabilities"},
    "items": {"format_version", "minecraft:item"},
    "recipes": {"format_version", "minecraft:recipe_shaped"},
    "attachables": {"format_version", "minecraft:attachable"},
}
# JS names that are not @minecraft/server API calls
JS_BUILTIN_CALLS = {"every", "some", "map", "filter", "forEach", "find", "includes", "push", "cos", "sin",
                    "floor", "round", "random", "max", "min", "abs", "PI", "warn", "log", "error", "toString",
                    "keys", "values", "entries", "has", "get", "set", "add", "delete", "join", "slice"}


def validate(verbose: bool = True) -> None:
    cfg, paths = load_config()
    errors: list[str] = []
    err = errors.append
    ns = cfg["namespace"]
    bp, rp, samples = paths.bp, paths.rp, paths.samples
    pieces = {p["identifier"]: p for p in cfg["pieces"]}

    if not samples.is_dir():
        raise BuildError(f"bedrock-samples not found at {samples} (set MC_SAMPLES to a checkout of "
                         f"Mojang/bedrock-samples); it is needed for schemas and API metadata")

    # 1. every JSON parses, no BOM, no unexpected top-level keys -----------------------
    parsed: dict[Path, object] = {}
    for p in [p for pack in (bp, rp) for p in sorted(pack.rglob("*.json"))] + sorted((ROOT / "tools").glob("*.json")):
        raw = p.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            err(f"{rel(p)}: has a UTF-8 BOM (Minecraft can reject it)")
        try:
            parsed[p] = json.loads(raw.decode("utf-8-sig"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            err(f"{rel(p)}: invalid JSON: {e}")
    if errors:
        _fail(errors)
    for p, data in parsed.items():
        kind = "manifest.json" if p.name == "manifest.json" else p.parent.name
        if kind in ALLOWED_TOP and isinstance(data, dict):
            bad = sorted(set(data) - ALLOWED_TOP[kind])
            if bad:
                err(f"{rel(p)}: unexpected top-level key(s) {bad}")

    # 2. manifests -------------------------------------------------------------------
    bpm, rpm = parsed.get(bp / "manifest.json"), parsed.get(rp / "manifest.json")
    if not bpm or not rpm:
        _fail(errors + ["gear_bp/manifest.json or gear_rp/manifest.json missing"])
    seen: dict[str, str] = {}
    for label, m in (("BP", bpm), ("RP", rpm)):
        if m.get("format_version") != 2:
            err(f"{label} manifest: format_version must be 2 (array versions)")
        h = m.get("header", {})
        if h.get("min_engine_version") != MIN_ENGINE:
            err(f"{label} manifest: min_engine_version must be {MIN_ENGINE}, got {h.get('min_engine_version')}")
        if not h.get("name"):
            err(f"{label} manifest: header.name missing")
        ids = [("header", h.get("uuid"))] + [(f"module {i}", mod.get("uuid")) for i, mod in enumerate(m.get("modules", []))]
        for where, u in ids:
            try:
                uuid.UUID(str(u))
            except ValueError:
                err(f"{label} manifest {where}: invalid UUID {u!r}")
                continue
            if u in seen:
                err(f"{label} manifest {where}: UUID {u} duplicates {seen[u]}")
            seen[u] = f"{label} {where}"
        for v in [h.get("version")] + [mod.get("version") for mod in m.get("modules", [])]:
            if not (isinstance(v, list) and len(v) == 3 and all(isinstance(x, int) for x in v)):
                err(f"{label} manifest: versions must be [major, minor, patch], got {v!r}")
        if not m.get("modules"):
            err(f"{label} manifest: no modules")
    rp_types = [mod.get("type") for mod in rpm.get("modules", [])]
    if rp_types != ["resources"]:
        err(f"RP manifest: expected one 'resources' module, got {rp_types}")
    bp_types = sorted(mod.get("type") for mod in bpm.get("modules", []))
    if bp_types != ["data", "script"]:
        err(f"BP manifest: expected 'data' + 'script' modules, got {bp_types}")
    for mod in bpm.get("modules", []):
        if mod.get("type") == "script":
            if mod.get("language") != "javascript":
                err("BP manifest: script module language must be 'javascript'")
            if not (bp / str(mod.get("entry", ""))).is_file():
                err(f"BP manifest: script entry {mod.get('entry')!r} not found in gear_bp")
    deps = bpm.get("dependencies", [])
    rp_uuid, rp_ver = rpm["header"]["uuid"], rpm["header"]["version"]
    pack_deps = {d.get("uuid"): d.get("version") for d in deps if "uuid" in d}
    if rp_uuid not in pack_deps:
        err("BP manifest: does not depend on the RP header UUID")
    elif pack_deps[rp_uuid] != rp_ver:
        err(f"BP manifest: depends on RP version {pack_deps[rp_uuid]} but RP is {rp_ver}")
    mod_deps = {d.get("module_name"): d.get("version") for d in deps if "module_name" in d}
    if mod_deps.get(SCRIPT_MODULE) != SCRIPT_VERSION:
        err(f"BP manifest: needs dependency {SCRIPT_MODULE} {SCRIPT_VERSION}, got {mod_deps}")
    sm = samples / "metadata" / "script_modules" / "@minecraft" / f"server_{SCRIPT_VERSION}.json"
    if not sm.is_file():
        err(f"{SCRIPT_MODULE} {SCRIPT_VERSION} not found in bedrock-samples ({sm})")

    # 3. vanilla reference data ------------------------------------------------------
    vd = samples / "metadata" / "vanilladata_modules"
    vanilla_items = {d["name"] for d in load_json(vd / "mojang-items.json")["data_items"]}
    vanilla_effects = {d["name"] for d in load_json(vd / "mojang-effects.json")["data_items"]}
    vrp = samples / "resource_pack"
    geometries: set[str] = set()
    for f in (vrp / "models").rglob("*.json"):
        try:
            data = load_json(f, allow_comments=True)
        except BuildError:
            continue
        for k in data:
            if k.startswith("geometry."):
                geometries.add(k.split(":")[0])
        for g in data.get("minecraft:geometry", []) if isinstance(data.get("minecraft:geometry"), list) else []:
            geometries.add(g.get("description", {}).get("identifier", ""))
    animations: set[str] = set()
    for f in (vrp / "animations").glob("*.json"):
        animations |= set(load_json(f, allow_comments=True).get("animations", {}))
    render_controllers: set[str] = set()
    for f in (vrp / "render_controllers").glob("*.json"):
        render_controllers |= set(load_json(f, allow_comments=True).get("render_controllers", {}))
    sound_defs = set(load_json(vrp / "sounds" / "sound_definitions.json", allow_comments=True)["sound_definitions"])
    particles = set()
    for f in [*(vrp / "particles").glob("*.json"), *(rp / "particles").glob("*.json")]:
        pe = load_json(f, allow_comments=True).get("particle_effect", {})
        particles.add(pe.get("description", {}).get("identifier"))

    # 4. items (schema + strict component names + config consistency) ---------------
    store = SchemaStore(samples / "metadata" / "json_schemas")
    item_files = sorted((bp / "items").glob("*.json"))
    item_texture = parsed.get(rp / "textures" / "item_texture.json", {})
    tex_data = item_texture.get("texture_data", {}) if isinstance(item_texture, dict) else {}
    found_items = set()
    schema_dirs = sorted((d.name for d in (samples / "metadata/json_schemas/server/item").iterdir()
                          if d.is_dir() and re.fullmatch(r"\d+\.\d+\.\d+", d.name)), key=_ver)
    for f in item_files:
        data = parsed[f]
        fv = data.get("format_version", "0")
        usable = [d for d in schema_dirs if _ver(d) <= _ver(fv) and (samples / "metadata/json_schemas/server/item" / d / "ItemDocument.json").is_file()]
        if not usable:
            err(f"{rel(f)}: no item schema for format_version {fv}")
            continue
        if _ver(fv) > tuple(MIN_ENGINE):
            err(f"{rel(f)}: format_version {fv} is newer than min_engine_version {MIN_ENGINE}")
        doc_schema = store.get(f"server/item/{usable[-1]}/ItemDocument.json")
        item = data.get("minecraft:item", {})
        for e in store.validate(item, doc_schema):
            err(f"{rel(f)} [schema {usable[-1]}/ItemDocument]: {e}")
        comp_schema = store.get(f"server/item/{usable[-1]}/Item Components.json")
        unknown = sorted(set(item.get("components", {})) - set(comp_schema.get("properties", {})))
        if unknown:
            err(f"{rel(f)}: unknown component(s) {unknown} (not in item schema {usable[-1]})")
        ident = item.get("description", {}).get("identifier", "")
        found_items.add(ident)
        piece = pieces.get(ident)
        if not ident.startswith(f"{ns}:"):
            err(f"{rel(f)}: identifier {ident!r} not in namespace {ns}:")
        if piece is None:
            err(f"{rel(f)}: {ident} is not in tools/gear_config.json")
            continue
        comps = item.get("components", {})
        slot = comps.get("minecraft:wearable", {}).get("slot")
        if slot != piece["slot"]:
            err(f"{rel(f)}: wearable slot {slot} != config {piece['slot']}")
        if comps.get("minecraft:enchantable", {}).get("slot") != ENCHANT_FOR_SLOT.get(slot):
            err(f"{rel(f)}: enchantable slot should be {ENCHANT_FOR_SLOT.get(slot)} for {slot}")
        repair = [i for r in comps.get("minecraft:repairable", {}).get("repair_items", []) for i in r.get("items", [])]
        if cfg["material"]["repair_item"] not in repair:
            err(f"{rel(f)}: not repairable with {cfg['material']['repair_item']}")
        for i in repair:
            if i not in vanilla_items and i not in pieces:
                err(f"{rel(f)}: repair item {i} is not a known item")
        key = comps.get("minecraft:icon", {}).get("textures", {}).get("default")
        if key not in tex_data:
            err(f"{rel(f)}: icon '{key}' not defined in gear_rp/textures/item_texture.json")
    for ident in pieces:
        if ident not in found_items:
            err(f"gear_bp/items: no item file for {ident}")

    # 5. recipes ----------------------------------------------------------------------
    signatures: dict[str, Path] = {}
    recipe_results = set()
    for f in sorted((bp / "recipes").glob("*.json")):
        r = parsed[f].get("minecraft:recipe_shaped")
        if not r:
            err(f"{rel(f)}: not a minecraft:recipe_shaped")
            continue
        rid = r.get("description", {}).get("identifier", "")
        if not rid.startswith(f"{ns}:"):
            err(f"{rel(f)}: recipe identifier {rid!r} not in namespace {ns}:")
        pat, key = r.get("pattern", []), r.get("key", {})
        if not (1 <= len(pat) <= 3) or len({len(row) for row in pat}) != 1 or len(pat[0]) > 3:
            err(f"{rel(f)}: pattern must be 1-3 rows of equal length <= 3: {pat}")
        used = {c for row in pat for c in row if c != " "}
        if used != set(key):
            err(f"{rel(f)}: pattern symbols {sorted(used)} != key symbols {sorted(key)}")
        for sym, v in key.items():
            if v.get("item") not in vanilla_items:
                err(f"{rel(f)}: key {sym} item {v.get('item')} is not a vanilla item")
        if r.get("tags") != ["crafting_table"]:
            err(f"{rel(f)}: tags should be ['crafting_table']")
        if not r.get("unlock"):
            err(f"{rel(f)}: missing 'unlock' (recipe would never appear in the recipe book)")
        res = r.get("result", {}).get("item")
        if res not in pieces:
            err(f"{rel(f)}: result {res} is not a gear item")
        recipe_results.add(res)
        sig = json.dumps([pat, {k: v.get("item") for k, v in key.items()}], sort_keys=True)
        if sig in signatures:
            err(f"{rel(f)}: same pattern and ingredients as {rel(signatures[sig])}")
        signatures[sig] = f
    for ident in pieces:
        if ident not in recipe_results:
            err(f"gear_bp/recipes: no recipe for {ident}")

    # 6. attachables ------------------------------------------------------------------
    referenced_tex: set[Path] = set()

    def tex_exists(tpath: str, where: str) -> None:
        hits = [rp / (tpath + ext) for ext in TEXTURE_EXTS if (rp / (tpath + ext)).is_file()]
        if not hits and not (vrp / (tpath + ".png")).is_file():
            err(f"{where}: texture {tpath} not found in gear_rp (or vanilla)")
        referenced_tex.update(h.resolve() for h in hits)

    att_for: dict[str, set[str]] = {i: set() for i in pieces}
    for f in sorted((rp / "attachables").glob("*.json")):
        d = parsed[f].get("minecraft:attachable", {}).get("description", {})
        aid = d.get("identifier", "")
        base = aid[:-len(".player")] if aid.endswith(".player") else aid
        if base not in pieces:
            err(f"{rel(f)}: attachable {aid} does not match a gear item")
            continue
        piece = pieces[base]
        kind = cfg["kinds"][piece["kind"]]
        if aid.endswith(".player"):
            att_for[base].add("player")
            if d.get("item") != {base: "query.owner_identifier == 'minecraft:player'"}:
                err(f"{rel(f)}: player attachable must map item {base} on query.owner_identifier == 'minecraft:player'")
            want_geo = f"geometry.player.armor.{piece['kind']}"
            for a in d.get("animations", {}).values():
                if a not in animations:
                    err(f"{rel(f)}: animation {a} not in vanilla")
            if d.get("animations", {}).get("offset") != kind["animation"]:
                err(f"{rel(f)}: offset animation should be {kind['animation']}")
        else:
            att_for[base].add("generic")
            want_geo = f"geometry.humanoid.armor.{piece['kind']}"
        geo = d.get("geometry", {}).get("default")
        if geo != want_geo:
            err(f"{rel(f)}: geometry {geo} should be {want_geo}")
        if geo not in geometries:
            err(f"{rel(f)}: geometry {geo} does not exist in vanilla models")
        for m in d.get("materials", {}).values():
            if m not in ARMOR_MATERIALS:
                err(f"{rel(f)}: unexpected material {m}")
        for rc in d.get("render_controllers", []):
            if rc not in render_controllers:
                err(f"{rel(f)}: render controller {rc} not in vanilla")
        if d.get("scripts", {}).get("parent_setup") != kind["parent_setup"]:
            err(f"{rel(f)}: parent_setup should be {kind['parent_setup']!r} (hides the vanilla layer)")
        for k, t in d.get("textures", {}).items():
            tex_exists(t, f"{rel(f)} texture '{k}'")
        if d.get("textures", {}).get("default") != f"{paths.armor_texture_dir}/{piece['layer']}":
            err(f"{rel(f)}: default texture should be the {piece['layer']} layer")
    for ident, kinds in att_for.items():
        if kinds != {"generic", "player"}:
            err(f"gear_rp/attachables: {ident} needs both a generic and a .player attachable (has {sorted(kinds)})")

    # 7. textures --------------------------------------------------------------------
    for k, v in tex_data.items():
        if not k.startswith(f"{ns}_"):
            err(f"item_texture.json: key {k} should be prefixed {ns}_")
        tex_exists(v.get("textures", ""), f"item_texture.json '{k}'")
    for piece in cfg["pieces"]:
        if texture_key(cfg, piece) not in tex_data:
            err(f"item_texture.json: missing {texture_key(cfg, piece)}")
    for p in sorted((rp / "textures").rglob("*")):
        if p.suffix.lower() in TEXTURE_EXTS:
            if p.resolve() not in referenced_tex:
                err(f"{rel(p)}: not referenced by any item or attachable")
            with Image.open(p) as im:
                if im.mode != "RGBA":
                    err(f"{rel(p)}: mode {im.mode}, expected RGBA")
                want = (64, 32) if paths.armor_texture_dir in p.as_posix() else (16, 16)
                if im.size != want:
                    err(f"{rel(p)}: {im.size[0]}x{im.size[1]}, expected {want[0]}x{want[1]}")
    for pack in (bp, rp):
        if not (pack / "pack_icon.png").is_file():
            err(f"{rel(pack)}/pack_icon.png missing")

    # 8. lang --------------------------------------------------------------------------
    lang_path = rp / "texts" / "en_US.lang"
    lang = {}
    if lang_path.is_file():
        for ln in lang_path.read_text(encoding="utf-8").splitlines():
            if ln and not ln.startswith("##") and "=" in ln:
                k, v = ln.split("=", 1)
                lang[k] = v
    else:
        err("gear_rp/texts/en_US.lang missing")
    for ident, piece in pieces.items():
        if lang.get(f"item.{ident}.name") != piece["name"]:
            err(f"en_US.lang: item.{ident}.name should be {piece['name']!r}")

    # 9. script ------------------------------------------------------------------------
    js_path = bp / "scripts" / "main.js"
    js = js_path.read_text(encoding="utf-8") if js_path.is_file() else ""
    api_names = _check_script(js, samples, pieces, cfg, lang, vanilla_effects, sound_defs, particles, err)

    if errors:
        _fail(errors)
    if verbose:
        print(f"  OK: {len(parsed)} JSON files; {len(item_files)} items schema-valid "
              f"(server/item/{schema_dirs[-1] if schema_dirs else '?'}); {len(signatures)} recipes; "
              f"{sum(len(v) for v in att_for.values())} attachables use vanilla geometry; "
              f"{len(referenced_tex)} textures; manifests OK; main.js uses {api_names} known "
              f"{SCRIPT_MODULE} {SCRIPT_VERSION} names")


def _check_script(js, samples, pieces, cfg, lang, vanilla_effects, sound_defs, particles, err) -> int:
    rel_js = "gear_bp/scripts/main.js"
    if not js:
        err(f"{rel_js}: missing or empty")
        return 0
    bindings = load_json(samples / "metadata/script_modules/@minecraft" / f"server-bindings_{SCRIPT_VERSION}.json")
    classes = {c["name"]: c for c in bindings["classes"]}
    enums = {e["name"]: {k["name"] for k in e["constants"]} for e in bindings["enums"]}
    exported = set(classes) | set(enums) | {o["name"] for o in bindings["objects"]} | \
        {i["name"] for i in bindings["interfaces"]}
    functions = {f["name"] for c in bindings["classes"] for f in c.get("functions", [])}
    props = {p["name"] for c in bindings["classes"] for p in c.get("properties", [])}

    imports = re.findall(r'import\s*\{([^}]*)\}\s*from\s*"([^"]+)"', js)
    if not imports:
        err(f"{rel_js}: no imports from {SCRIPT_MODULE}")
    count = 0
    for names, mod in imports:
        if mod != SCRIPT_MODULE:
            err(f"{rel_js}: imports from {mod}, but the manifest only depends on {SCRIPT_MODULE}")
        for n in (x.strip() for x in names.split(",") if x.strip()):
            count += 1
            if n not in exported:
                err(f"{rel_js}: {n} is not exported by {SCRIPT_MODULE} {SCRIPT_VERSION}")
    for enum_name, member in re.findall(r"\b(EquipmentSlot|EntityComponentTypes)\.(\w+)", js):
        count += 1
        if member not in enums.get(enum_name, set()):
            err(f"{rel_js}: {enum_name}.{member} does not exist in {SCRIPT_VERSION}")
    code = re.sub(r"//[^\n]*", "", js)
    code = re.sub(r'"(?:\\.|[^"\\])*"|`(?:\\.|[^`\\])*`', '""', code)
    local_fns = set(re.findall(r"function\s+(\w+)", code))
    for name in sorted(set(re.findall(r"\.(\w+)\s*\(", code))):
        if name in JS_BUILTIN_CALLS or name in local_fns:
            continue
        count += 1
        if name not in functions:
            err(f"{rel_js}: .{name}() is not a method of any {SCRIPT_MODULE} {SCRIPT_VERSION} class")
    for name in sorted(set(re.findall(r"\b(?:player|item|current|equippable)\.(\w+)\b(?!\s*\()", code))):
        count += 1
        if name not in props:
            err(f"{rel_js}: property .{name} not found on any {SCRIPT_MODULE} {SCRIPT_VERSION} class")
    # content referenced by the script
    strings = set(re.findall(r'"([^"]*)"', re.sub(r"//[^\n]*", "", js)))
    for s in strings:
        if s.startswith(f"{cfg['namespace']}:") and s not in pieces and s not in particles:
            err(f"{rel_js}: references unknown item {s}")
    for ident, piece in pieces.items():
        if piece.get("set_piece") and ident not in strings:
            err(f"{rel_js}: set piece {ident} not checked by the script")
    for tag in re.findall(r'_TAG\s*=\s*"([^"]+)"', js):
        if not tag.startswith(f"{cfg['namespace']}_"):
            err(f"{rel_js}: tag {tag!r} must be prefixed {cfg['namespace']}_")
    for call in re.findall(r'(?:addTag|removeTag|hasTag|setDynamicProperty|getDynamicProperty)\(\s*"([^"]+)"', js):
        if not call.startswith(f"{cfg['namespace']}_"):
            err(f"{rel_js}: tag/property {call!r} must be prefixed {cfg['namespace']}_")
    for eff in re.findall(r'(?:=|id:)\s*"(minecraft:[a-z_]+)"', js):
        if eff not in vanilla_effects:
            err(f"{rel_js}: effect {eff} not in vanilla effect list")
    for snd in re.findall(r'playSound\(\s*"([^"]+)"', js):
        if snd not in sound_defs:
            err(f"{rel_js}: sound {snd} not in vanilla sound_definitions.json")
    for part in re.findall(r'spawnParticle\(\s*"([^"]+)"', js):
        if part not in particles:
            err(f"{rel_js}: particle {part} not in vanilla particles or gear_rp/particles")
    for key in re.findall(r'translate:\s*"([^"]+)"', js):
        if key not in lang:
            err(f"{rel_js}: translation key {key} missing from en_US.lang")
    return count


def _ver(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:3])


def _fail(errors):
    raise BuildError("validation failed:\n    - " + "\n    - ".join(errors))


if __name__ == "__main__":
    try:
        validate()
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
