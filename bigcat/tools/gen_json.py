"""Generate the entity / render-controller JSON and test functions for the coats.

Inputs : tools/templates/*.json (hand-maintained cat behaviour and client entity)
         tools/coats_config.json
Outputs: <bp>/entities/big_cat.json          template + coat property + coat events
         <rp>/entity/big_cat.entity.json      template + one texture per coat
         <rp>/render_controllers/big_cat.render_controllers.json
         <bp>/functions/test_cats.mcfunction, clear_cats.mcfunction, coats/page_##.mcfunction

How a coat is chosen: an int entity property (default "math.random_integer(0, N-1)")
is set the moment any cat is created (natural spawn, spawn egg, /summon, breeding)
and for already-saved cats the first time they load with this pack version.
"""
from __future__ import annotations

import copy
import shutil
import sys

from common import (GENERATED_KEY, GENERATED_NOTE, BuildError, coat_name, load_config, load_json, rel,
                    tame_name, write_json, write_text)

RC_TEXTURE_EXPR = ("query.is_tamed ? Array.tame[query.property('{prop}')] "
                   ": Array.coats[query.property('{prop}')]")
BP_ENTITY = "entities/big_cat.json"
RP_ENTITY = "entity/big_cat.entity.json"
RP_RC = "render_controllers/big_cat.render_controllers.json"


def coat_events(prop: str, n: int) -> dict:
    ev = {
        "mymod:randomize_coat": {"set_property": {prop: f"math.random_integer(0, {n - 1})"}},
        "mymod:next_coat": {"set_property": {prop: f"math.mod(query.property('{prop}') + 1, {n})"}},
        "mymod:prev_coat": {"set_property": {prop: f"math.mod(query.property('{prop}') + {n - 1}, {n})"}},
    }
    for i in range(n):
        ev[f"mymod:set_coat_{i}"] = {"set_property": {prop: i}}
    return ev


def with_note(obj: dict) -> dict:
    # Minecraft rejects unknown keys ("child '__generated__' not valid here"), so the
    # "generated" marker lives in GENERATED_FILES.md instead of inside pack JSON.
    return obj


def write_generated_list(paths, n: int) -> None:
    rp, bp = paths.rp.name, paths.bp.name
    text = f"""# Generated files - do not edit by hand

`python tools/build.py` overwrites everything listed here. Minecraft rejects extra
fields in pack JSON, so this list is the "generated" marker instead.

| File | Edit this instead |
|---|---|
| `{bp}/{BP_ENTITY}` | `tools/templates/big_cat.behavior.json` (+ `tools/coats_config.json` for coats) |
| `{bp}/functions/` (all `.mcfunction` files) | `tools/gen_json.py`, `test_grid` in `tools/coats_config.json` |
| `{rp}/{RP_ENTITY}` | `tools/templates/big_cat.client_entity.json` |
| `{rp}/{RP_RC}` | `tools/gen_json.py` |
| `{rp}/{paths.coat_texture_dir}/coat_000.png` ... `coat_{n - 1:03d}.png` | `tools/coats_config.json`, `art/` |
| `{bp}/manifest.json`, `{rp}/manifest.json` - version only | bumped by `python tools/build.py --package` |
| `{rp}/textures/items/laser_pointer.png`, `{rp}/textures/entity/laser_dot.png` | `tools/gen_laser.py` (pixel art in code) |
| `{rp}/textures/items/cat_orb.png`, `{rp}/textures/items/cat_orb_full.png` | `tools/gen_orb.py` (pixel art in code) |
| `GENERATED_FILES.md` (this file) | `write_generated_list` in `tools/gen_json.py` |

## Hand-written - edit these directly

Laser pointer (checked by `validate_laser` in `tools/validate.py`):

| File | What it is |
|---|---|
| `{bp}/scripts/main.js` | Script API (`@minecraft/server` 2.11.0): item use, raycast, place/move/remove the dot, glow particles, cats losing interest |
| `{bp}/manifest.json` - script module + `@minecraft/server` dependency | keep the UUIDs; only the version is bumped by the build |
| `{bp}/items/laser_pointer.json` | the `mymod:laser_pointer` item |
| `{bp}/recipes/laser_pointer.json` | crafting: glass pane / redstone / iron nugget, stacked vertically |
| `{bp}/entities/laser_dot.json` | the invulnerable, gravity-free `mymod:laser_dot` entity (family `bigcat_laser_dot`) |
| `{rp}/entity/laser_dot.entity.json`, `{rp}/models/entity/laser_dot.geo.json` | the dot's tiny red cube |
| `{rp}/particles/laser_dot.particle.json` | `mymod:laser_dot_glow`, the unlit red glow the script spawns at the dot |
| `{rp}/textures/item_texture.json` | item icon atlas entries `mymod_laser_pointer`, `mymod_cat_orb`, `mymod_cat_orb_full` |

Cat Orb (checked by `validate_orb` in `tools/validate.py`):

| File | What it is |
|---|---|
| `{bp}/scripts/cat_orb.js` | capture/release logic, imported by `scripts/main.js` |
| `{bp}/items/cat_orb.json`, `{bp}/items/cat_orb_full.json` | the empty orb (stacks to 16) and the occupied orb (holds one cat, not in the creative menu) |
| `{bp}/recipes/cat_orb.json` | crafting: 4 glass around a raw cod |
| `{rp}/texts/en_US.lang` | display names |

The cats' chase goals (`minecraft:behavior.nearest_prioritized_attackable_target` for the
`bigcat_laser_dot` family and `minecraft:behavior.move_towards_target`) live in
`tools/templates/big_cat.behavior.json`, like the rest of the cat's behavior.
"""
    write_text(paths.build.parent / "GENERATED_FILES.md", text)


def generate_json(verbose: bool = True) -> None:
    cfg, paths = load_config()
    n = cfg["coat_count"]
    ent = cfg["entity"]
    ident, prop, rc_id = ent["identifier"], ent["coat_property"], ent["render_controller"]

    # ---- behavior entity
    bp = copy.deepcopy(load_json(paths.bp_template))
    bp.pop(GENERATED_KEY, None)
    e = bp.get("minecraft:entity")
    if not e or e.get("description", {}).get("identifier") != ident:
        raise BuildError(f"{rel(paths.bp_template)}: expected minecraft:entity '{ident}'")
    props = e["description"].setdefault("properties", {})
    if prop in props:
        raise BuildError(f"{rel(paths.bp_template)}: remove '{prop}' from the template, the build adds it")
    props[prop] = {
        "type": "int",
        "range": [0, n - 1],
        "default": f"math.random_integer(0, {n - 1})",
        "client_sync": True,
    }
    events = e.setdefault("events", {})
    new_events = coat_events(prop, n)
    clash = sorted(set(events) & set(new_events))
    if clash:
        raise BuildError(f"{rel(paths.bp_template)}: events {clash[:3]} are generated; remove them from the template")
    events.update(new_events)
    write_json(paths.bp / BP_ENTITY, with_note(bp))

    # ---- client entity
    ce = copy.deepcopy(load_json(paths.client_template))
    ce.pop(GENERATED_KEY, None)
    desc = ce.get("minecraft:client_entity", {}).get("description")
    if not desc or desc.get("identifier") != ident:
        raise BuildError(f"{rel(paths.client_template)}: expected minecraft:client_entity '{ident}'")
    if desc.get("textures"):
        raise BuildError(f"{rel(paths.client_template)}: remove 'textures' from the template, the build adds them")
    desc["textures"] = {coat_name(i): f"{paths.coat_texture_dir}/{coat_name(i)}" for i in range(n)}
    desc["textures"].update({tame_name(i): f"{paths.coat_texture_dir}/{tame_name(i)}" for i in range(n)})
    if desc.get("render_controllers") != [rc_id]:
        raise BuildError(f"{rel(paths.client_template)}: render_controllers must be [\"{rc_id}\"]")
    write_json(paths.rp / RP_ENTITY, with_note(ce))

    # ---- render controller
    rc = {
        "format_version": "1.8.0",
        "render_controllers": {
            rc_id: {
                "arrays": {"textures": {
                    "Array.coats": [f"Texture.{coat_name(i)}" for i in range(n)],
                    # tame versions carry the collar alpha mask the 'cat' material tints
                    "Array.tame": [f"Texture.{tame_name(i)}" for i in range(n)],
                }},
                "geometry": "Geometry.default",
                "materials": [{"*": "Material.default"}],
                "textures": [RC_TEXTURE_EXPR.format(prop=prop)],
            }
        },
    }
    write_json(paths.rp / RP_RC, with_note(rc))

    # ---- test functions
    write_functions(cfg, paths, ident, n)
    write_generated_list(paths, n)
    if verbose:
        print(f"  wrote {BP_ENTITY}, {RP_ENTITY}, {RP_RC} and functions ({n} coats, property {prop})")


def write_functions(cfg, paths, ident, n):
    g = cfg["test_grid"]
    cols, rows, sp, page = g["columns"], g["rows"], g["spacing"], g["page_size"]
    fdir = paths.bp / "functions"
    head = "# GENERATED by tools/build.py - do not edit by hand.\n"
    if (fdir / "coats").exists():
        shutil.rmtree(fdir / "coats")

    def grid(k):
        return (k % cols) * sp + sp, (k // cols) * sp + sp

    lines = [head, f"# Summons {cols * rows} cats with random coats in a grid in front of (+x/+z of) you.\n"]
    for k in range(cols * rows):
        x, z = grid(k)
        lines.append(f"summon {ident} ~{x} ~ ~{z}\n")
    write_text(fdir / "test_cats.mcfunction", "".join(lines))

    write_text(fdir / "clear_cats.mcfunction",
               head + "# Removes every Big Cat in the world (handy between test batches).\n"
               f"kill @e[type={ident}]\n")

    pages = (n + page - 1) // page
    for p in range(pages):
        lo, hi = p * page, min(n, (p + 1) * page)
        lines = [head, f"# Coats {lo}-{hi - 1}: named cats with a forced coat, in a grid.\n"]
        for k, i in enumerate(range(lo, hi)):
            x, z = grid(k)
            name = f"Coat {i:03d}"
            lines.append(f'summon {ident} ~{x} ~ ~{z} 0 0 minecraft:entity_spawned "{name}"\n')
            lines.append(f'event entity @e[type={ident},name="{name}"] mymod:set_coat_{i}\n')
        write_text(fdir / "coats" / f"page_{p + 1:02d}.mcfunction", "".join(lines))


if __name__ == "__main__":
    try:
        generate_json()
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
