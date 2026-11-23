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

from common import (
    GENERATED_KEY,
    BuildError,
    coat_name,
    load_config,
    load_json,
    rel,
    tame_name,
    write_json,
    write_text,
)
from gen_evolution import PROPERTY as EVO_PROPERTY
from gen_evolution import WING_STAGE, WING_TEXTURE, add_evolution

RC_TEXTURE_EXPR = "query.is_tamed ? Array.tame[query.property('{prop}')] : Array.coats[query.property('{prop}')]"
BP_ENTITY = "entities/big_cat.json"
RP_ENTITY = "entity/big_cat.entity.json"
RP_RC = "render_controllers/big_cat.render_controllers.json"
WING_RC = "controller.render.big_cat_wings"  # render_controllers/big_cat_wings.render_controllers.json


def wing_condition() -> str:
    return f"query.property('{EVO_PROPERTY}') >= {WING_STAGE}"


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
| `{rp}/textures/items/{{cat,creature,trap}}_orb[_full].png` | `tools/gen_orb.py` (pixel art in code) |
| `{rp}/textures/items/{{size,vapor}}_wand.png` | `tools/gen_wand.py` (pixel art in code) |
| `{rp}/textures/items/grappling_gun.png`, `{rp}/textures/entity/grapple_hook.png` | `tools/gen_grapple.py` (pixel art in code) |
| `{rp}/textures/items/air_cannon.png` | `tools/gen_air_cannon.py` (pixel art in code) |
| `{rp}/textures/blocks/atomic_bomb_side.png`, `..._top.png`, `..._bottom.png` | `tools/gen_atomic_bomb.py` (pixel art in code) |
| `{rp}/textures/items/{{laser,flame,water,ice,barf}}_blaster.png` | `tools/gen_blaster.py` (pixel art in code) |
| `{rp}/textures/items/mountain_seed.png` | `tools/gen_mountain.py` (pixel art in code) |
| `{rp}/textures/items/vortex_gun.png`, `{rp}/textures/items/animal_vortex_gun.png` | `tools/gen_vortex.py` (pixel art in code) |
| `{rp}/textures/items/drowned_trap.png`, `{rp}/textures/entity/drowned_lure.png` | `tools/gen_drowned_trap.py` (pixel art in code) |
| `{bp}/entities/drowned.json` (gitignored) | `tools/gen_drowned_trap.py` (vanilla drowned + the trap as an attack target) |
| `{rp}/textures/items/evolution_stone.png`, `{rp}/textures/entity/big_cat_wings.png` | `tools/gen_evolution.py` (pixel art in code) |
| `{rp}/textures/blocks/net_trap.png`, `{rp}/textures/items/net_trap.png` | `tools/gen_net.py` (pixel art in code) |
| `{bp}/entities/morph_<form>.json`, `{bp}/scripts/morph_forms.js`, `{rp}/entity/morph_<form>.entity.json`, `{rp}/render_controllers/morph.render_controllers.json`, `{rp}/textures/items/morph_wand.png` | `tools/gen_morph.py` (`FORMS`: the Morph Wand's creatures) |
| `{rp}/models/entity/mooshroom_drill.geo.json`, `{rp}/textures/entity/mooshroom_drill.png`, `{rp}/textures/items/mooshroom_drill.png` | `tools/gen_mooshroom_drill.py` (`CUBES`: the chassis and mushrooms; pixel art in code) |
| `{bp}/blocks/portal_pad.json`, `{bp}/scripts/portal_colors.js`, `{rp}/textures/blocks/portal_pad_<color>.png`, `{rp}/textures/items/portal_pad.png` | `tools/gen_portal.py` (`COLORS`: one pad colour per dye) |
| `{bp}/entities/player.json` (gitignored) | `tools/gen_player.py` (vanilla player + Size Wand sizes) |
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
| `{rp}/textures/item_texture.json` | item icon atlas entries for the laser pointer, the three orbs (empty and full), the two wands and the grappling gun |

Orbs (checked by `validate_orb` in `tools/validate.py`):

| File | What it is |
|---|---|
| `{bp}/scripts/orbs.js` | Cat Orb + Creature Orb capture/release, imported by `scripts/main.js` |
| `{bp}/scripts/trap_orb.js` | Player Trap Orb (spectator-mode trap with auto-release), imported by `scripts/main.js` |
| `{bp}/items/{{cat,creature,trap}}_orb.json`, `..._full.json` | each empty orb (stacks to 16) and its occupied version (holds one, not in the creative menu) |
| `{bp}/recipes/{{cat,creature,trap}}_orb.json` | crafting: 4 glass in a plus around a raw cod / ender pearl / iron bars |
| `{rp}/texts/en_US.lang` | display names |

Wands (checked by `validate_wands` in `tools/validate.py`):

| File | What it is |
|---|---|
| `{bp}/scripts/wands.js` | Size Wand (normal / mini / huge) and Vapor Wand (rainbow / stinky), imported by `scripts/main.js` |
| `{bp}/items/{{size,vapor}}_wand.json` | the two wand items |
| `{bp}/recipes/{{size,vapor}}_wand.json` | crafting: red mushroom / stick / brown mushroom, and glowstone dust / stick / fermented spider eye |
| `{rp}/particles/{{rainbow_sparkle,stinky_vapor}}.particle.json` | the vapor clouds the script spawns around a player |

Grappling Gun (checked by `validate_grapple` in `tools/validate.py`):

| File | What it is |
|---|---|
| `{bp}/scripts/grapple.js` | fire the hook, reel yourself to blocks or hooked entities to you, draw the rope, imported by `scripts/main.js` |
| `{bp}/items/grappling_gun.json`, `{bp}/recipes/grappling_gun.json` | the `mymod:grappling_gun` item; crafting: tripwire hook / string / iron ingot, stacked vertically |
| `{bp}/entities/grapple_hook.json` | the `mymod:grapple_hook` projectile (sticks in blocks, invulnerable) |
| `{rp}/entity/grapple_hook.entity.json`, `{rp}/models/entity/grapple_hook.geo.json` | the hook's four-pronged steel model |
| `{rp}/particles/grapple_rope.particle.json` | `mymod:grapple_rope`, the rope dots the script draws between you and the hook |

Drowned Trap (checked by `validate_drowned_trap` in `tools/validate.py`):

| File | What it is |
|---|---|
| `{bp}/scripts/drowned_trap.js` | place / pick up the trap, blow up drowned that attack it, drop one randomly enchanted weapon, imported by `scripts/main.js` |
| `{bp}/items/drowned_trap.json`, `{bp}/recipes/drowned_trap.json` | the `mymod:drowned_trap` item (stacks to 16); crafting: 4 iron bars in a plus around a raw cod |
| `{bp}/entities/drowned_lure.json` | the placed trap, `mymod:drowned_lure` (family `bigcat_drowned_trap`, invulnerable, never despawns) |
| `{rp}/entity/drowned_lure.entity.json`, `{rp}/models/entity/drowned_lure.geo.json` | the see-through prismarine cage with a fish inside |

Evolution Stone (checked by `validate_evolution` in `tools/validate.py`; stages, stats and the
stage property/groups/events in `{bp}/{BP_ENTITY}` come from `tools/gen_evolution.py`):

| File | What it is |
|---|---|
| `{bp}/scripts/evolution.js` | stones dropping from ores, evolving a cat, stage particles, stage-8 flying while ridden; imported by `scripts/main.js` |
| `{bp}/items/evolution_stone.json` | the `mymod:evolution_stone` item (no recipe: ores drop it) |
| `{rp}/models/entity/big_cat_wings.geo.json` | the wings, a second model drawn on the cat (its `body` bone follows the cat's sit / lie-down poses) |
| `{rp}/render_controllers/big_cat_wings.render_controllers.json` | draws the wings; its `part_visibility` hides them below stage 8 |
| `{rp}/animations/big_cat_wings.animation.json`, `controller.animation.big_cat.wings` in `{rp}/animation_controllers/big_cat.animation_controllers.json` | folded wings on the ground, flapping in the air |

Net Trap (checked by `validate_net_trap` in `tools/validate.py`):

| File | What it is |
|---|---|
| `{bp}/scripts/net_trap.js` | the `mymod:net_trap` custom block component (step on it: caught), holding, releasing; imported by `scripts/main.js` |
| `{bp}/blocks/net_trap.json` | the flat net block (thin collision box, so stepping on it fires `onStepOn`) |
| `{bp}/items/net_trap.json`, `{bp}/recipes/net_trap.json` | the item that places it (`block_placer`, replaces the block's own item); crafting: 4 string in the corners around a slime ball, makes 2 |
| `{rp}/models/blocks/net_trap.geo.json` | a 16x16 plate a quarter pixel thick |
| `{rp}/textures/terrain_texture.json` | block texture atlas entry `mymod_net_trap` |

Morph Wand (checked by `validate_morph` in `tools/validate.py`; the creatures are generated, see above):

| File | What it is |
|---|---|
| `{bp}/scripts/morph.js` | use the wand: next creature (sneak: back to yourself); the costume follows the invisible player; perks; imported by `scripts/main.js` |
| `{bp}/items/morph_wand.json`, `{bp}/recipes/morph_wand.json` | the wand; crafting: feather / stick / leather |

Air Cannon (checked by `validate_air_cannon` in `tools/validate.py`):

| File | What it is |
|---|---|
| `{bp}/scripts/air_cannon.js` | blast everything in a cone in front of you super far (look down: rocket jump), imported by `scripts/main.js` |
| `{bp}/items/air_cannon.json`, `{bp}/recipes/air_cannon.json` | the `mymod:air_cannon` item; crafting: 3 iron ingots over a feather and a piston |

Atomic Bomb (checked by `validate_atomic_bomb` in `tools/validate.py`):

| File | What it is |
|---|---|
| `{bp}/scripts/atomic_bomb.js` | light it (flint and steel, fire charge, redstone, another explosion), countdown, crater, mushroom cloud, kill mobs / fling and protect players; imported by `scripts/main.js` |
| `{bp}/blocks/atomic_bomb.json`, `{bp}/recipes/atomic_bomb.json` | the `mymod:atomic_bomb` block; crafting: 8 TNT around a glowstone block |
| `{rp}/textures/terrain_texture.json` | block texture atlas entries `mymod_atomic_bomb_side/top/bottom` |

Laser Blaster (checked by `validate_blaster` in `tools/validate.py`):

| File | What it is |
|---|---|
| `{bp}/scripts/blaster.js` | hold use to fire: burns through up to 4 blocks per pulse (skips containers and unbreakables), hurts and ignites what's in the beam; imported by `scripts/main.js` |
| `{bp}/items/laser_blaster.json`, `{bp}/recipes/laser_blaster.json` | the blaster (long `use_duration`, so holding the button keeps it firing); crafting: diamond, 2 redstone blocks, laser pointer, glowstone |
| `{bp}/items/flame_blaster.json`, `{bp}/recipes/flame_blaster.json` | the Flame Blaster (same hold-to-fire `use_duration`); crafting: blaze rod, 2 fire charges, laser pointer, glowstone |
| `{rp}/particles/laser_glow.particle.json`, `{rp}/particles/fire_beam.particle.json` | `mymod:laser_glow` (the Laser Blaster's wide beacon glow) and `mymod:fire_beam` (the Flame Blaster's orange beam) |
| `{bp}/items/water_blaster.json`, `{bp}/items/ice_blaster.json` (+ recipes) | the Water and Ice Blasters (same hold-to-fire `use_duration`); crafting: water bucket + 2 lapis / blue ice + 2 snowballs, laser pointer, glowstone |
| `{rp}/particles/water_beam.particle.json`, `{rp}/particles/ice_beam.particle.json` | `mymod:water_beam` and `mymod:ice_beam`, their beams |
| `{bp}/items/barf_blaster.json`, `{bp}/recipes/barf_blaster.json` | the Barf Blaster (same hold-to-fire `use_duration`): makes whoever it hits throw up; crafting: spider eye + 2 slime balls, laser pointer, glowstone |
| `{rp}/particles/barf_beam.particle.json`, `{rp}/particles/barf_spew.particle.json` | `mymod:barf_beam` (its green beam) and `mymod:barf_spew` (the chunks thrown up, aimed with `variable.direction`) |

Mountain Seed (checked by `validate_mountain` in `tools/validate.py`):

| File | What it is |
|---|---|
| `{bp}/scripts/mountain.js` | plant the seed; a diamond-square fractal mountain grows layer by layer (snow peaks, terracotta bands, ores inside); imported by `scripts/main.js` |
| `{bp}/items/mountain_seed.json`, `{bp}/recipes/mountain_seed.json` | the `mymod:mountain_seed` item (stacks to 16); crafting: 4 stone in a plus around wheat seeds |

Vortex Guns (checked by `validate_vortex` in `tools/validate.py`):

| File | What it is |
|---|---|
| `{bp}/scripts/vortex.js` | use: for 5 s creatures within 256 blocks are pulled to you (Monster Vortex: hostile mobs; Animal Vortex: everything else alive; never players), nearest 100 first; imported by `scripts/main.js` |
| `{bp}/items/vortex_gun.json`, `{bp}/recipes/vortex_gun.json` | Monster Vortex (`mymod:vortex_gun`); crafting: iron / ender pearl / iron over iron / redstone block / iron |
| `{bp}/items/animal_vortex_gun.json`, `{bp}/recipes/animal_vortex_gun.json` | Animal Vortex (`mymod:animal_vortex_gun`); same, with wheat instead of the ender pearl |
| `{rp}/particles/laser_beam.particle.json` | `mymod:laser_beam`, the glowing cyan dots the beam is drawn with |

Mooshroom Drill (checked by `validate_mooshroom_drill` in `tools/validate.py`; the chassis model and textures are generated, see above):

| File | What it is |
|---|---|
| `{bp}/scripts/drill.js` | place / pick up (sneak + hit) the drill; while the driver holds forward: spin the mooshroom and carve a 5x5 tunnel (look up / down: stairs, straight down: shaft), ores into the driver's inventory, driver perks; imported by `scripts/main.js` |
| `{bp}/entities/mooshroom_drill_vehicle.json` | the rideable, driveable, invulnerable vehicle; the client-synced `mymod:drilling` property starts the spin |
| `{bp}/items/mooshroom_drill.json`, `{bp}/recipes/mooshroom_drill.json` | the `mymod:mooshroom_drill` item; crafting: red mushroom / diamond pickaxe / brown mushroom over iron block / minecart / iron block |
| `{rp}/entity/mooshroom_drill_vehicle.entity.json`, `{rp}/render_controllers/mooshroom_drill.render_controllers.json` | draws the chassis model plus Minecraft's own mooshroom model and texture (not copied into this repo) |
| `{rp}/animations/mooshroom_drill.animation.json` | spin (the `body` and `head` bones of both models turn around the cow's long axis) and a gentle idle wobble |

Portal Pads (checked by `validate_portal` in `tools/validate.py`; the block and its textures are generated, see above):

| File | What it is |
|---|---|
| `{bp}/scripts/portal.js` | remembers every pad (world dynamic properties), teleports players and creatures to the next pad of the same colour, dyeing, swirl particles; imported by `scripts/main.js` |
| `{bp}/items/portal_pad.json`, `{bp}/recipes/portal_pad.json` | the item that places it (`block_placer`); crafting: obsidian / ender pearl / obsidian, makes 2 |
| `{rp}/models/blocks/portal_pad.geo.json` | a 16x16 plate one pixel thick |
| `{rp}/particles/portal_swirl.particle.json` | `mymod:portal_swirl`, tinted with the pad's colour (`variable.pr/pg/pb` from the script) |
| `{rp}/textures/terrain_texture.json` | block texture atlas entries `mymod_portal_pad_<color>` |

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
    add_evolution(e, rel(paths.bp_template))  # Evolution Stone stages (tools/gen_evolution.py)
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
        raise BuildError(f'{rel(paths.client_template)}: render_controllers must be ["{rc_id}"]')
    # Stage-8 wings: a second model drawn on top of the cat (geometry, material and flap animation
    # are in the template; the geometry is models/entity/big_cat_wings.geo.json).
    desc["textures"]["wings"] = WING_TEXTURE
    # A 1.8.0 client entity only accepts plain strings here (a {controller: condition} entry
    # fails to load), so the wing controller always runs and hides the wings itself with
    # part_visibility below stage 8.
    desc["render_controllers"].append(WING_RC)
    write_json(paths.rp / RP_ENTITY, with_note(ce))

    # ---- render controller
    rc = {
        "format_version": "1.8.0",
        "render_controllers": {
            rc_id: {
                "arrays": {
                    "textures": {
                        "Array.coats": [f"Texture.{coat_name(i)}" for i in range(n)],
                        # tame versions carry the collar alpha mask the 'cat' material tints
                        "Array.tame": [f"Texture.{tame_name(i)}" for i in range(n)],
                    }
                },
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

    write_text(
        fdir / "clear_cats.mcfunction",
        head + f"# Removes every Big Cat in the world (handy between test batches).\nkill @e[type={ident}]\n",
    )

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
