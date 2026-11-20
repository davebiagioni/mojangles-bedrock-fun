# Generated files - do not edit by hand

`python tools/build.py` overwrites everything listed here. Minecraft rejects extra
fields in pack JSON, so this list is the "generated" marker instead.

| File | Edit this instead |
|---|---|
| `big_cat_bp/entities/big_cat.json` | `tools/templates/big_cat.behavior.json` (+ `tools/coats_config.json` for coats) |
| `big_cat_bp/functions/` (all `.mcfunction` files) | `tools/gen_json.py`, `test_grid` in `tools/coats_config.json` |
| `big_cat_rp/entity/big_cat.entity.json` | `tools/templates/big_cat.client_entity.json` |
| `big_cat_rp/render_controllers/big_cat.render_controllers.json` | `tools/gen_json.py` |
| `big_cat_rp/textures/entity/coats/coat_000.png` ... `coat_199.png` | `tools/coats_config.json`, `art/` |
| `big_cat_bp/manifest.json`, `big_cat_rp/manifest.json` - version only | bumped by `python tools/build.py --package` |
| `big_cat_rp/textures/items/laser_pointer.png`, `big_cat_rp/textures/entity/laser_dot.png` | `tools/gen_laser.py` (pixel art in code) |
| `big_cat_rp/textures/items/cat_orb.png`, `big_cat_rp/textures/items/cat_orb_full.png` | `tools/gen_orb.py` (pixel art in code) |
| `GENERATED_FILES.md` (this file) | `write_generated_list` in `tools/gen_json.py` |

## Hand-written - edit these directly

Laser pointer (checked by `validate_laser` in `tools/validate.py`):

| File | What it is |
|---|---|
| `big_cat_bp/scripts/main.js` | Script API (`@minecraft/server` 2.11.0): item use, raycast, place/move/remove the dot, glow particles, cats losing interest |
| `big_cat_bp/manifest.json` - script module + `@minecraft/server` dependency | keep the UUIDs; only the version is bumped by the build |
| `big_cat_bp/items/laser_pointer.json` | the `mymod:laser_pointer` item |
| `big_cat_bp/recipes/laser_pointer.json` | crafting: glass pane / redstone / iron nugget, stacked vertically |
| `big_cat_bp/entities/laser_dot.json` | the invulnerable, gravity-free `mymod:laser_dot` entity (family `bigcat_laser_dot`) |
| `big_cat_rp/entity/laser_dot.entity.json`, `big_cat_rp/models/entity/laser_dot.geo.json` | the dot's tiny red cube |
| `big_cat_rp/particles/laser_dot.particle.json` | `mymod:laser_dot_glow`, the unlit red glow the script spawns at the dot |
| `big_cat_rp/textures/item_texture.json` | item icon atlas entries `mymod_laser_pointer`, `mymod_cat_orb`, `mymod_cat_orb_full` |

Cat Orb (checked by `validate_orb` in `tools/validate.py`):

| File | What it is |
|---|---|
| `big_cat_bp/scripts/cat_orb.js` | capture/release logic, imported by `scripts/main.js` |
| `big_cat_bp/items/cat_orb.json`, `big_cat_bp/items/cat_orb_full.json` | the empty orb (stacks to 16) and the occupied orb (holds one cat, not in the creative menu) |
| `big_cat_bp/recipes/cat_orb.json` | crafting: 4 glass around a raw cod |
| `big_cat_rp/texts/en_US.lang` | display names |

The cats' chase goals (`minecraft:behavior.nearest_prioritized_attackable_target` for the
`bigcat_laser_dot` family and `minecraft:behavior.move_towards_target`) live in
`tools/templates/big_cat.behavior.json`, like the rest of the cat's behavior.
