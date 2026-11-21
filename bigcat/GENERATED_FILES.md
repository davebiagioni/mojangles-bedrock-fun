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
| `big_cat_rp/textures/items/{cat,creature,trap}_orb[_full].png` | `tools/gen_orb.py` (pixel art in code) |
| `big_cat_rp/textures/items/{size,vapor}_wand.png` | `tools/gen_wand.py` (pixel art in code) |
| `big_cat_rp/textures/items/grappling_gun.png`, `big_cat_rp/textures/entity/grapple_hook.png` | `tools/gen_grapple.py` (pixel art in code) |
| `big_cat_rp/textures/items/evolution_stone.png`, `big_cat_rp/textures/entity/big_cat_wings.png` | `tools/gen_evolution.py` (pixel art in code) |
| `big_cat_bp/entities/player.json` (gitignored) | `tools/gen_player.py` (vanilla player + Size Wand sizes) |
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
| `big_cat_rp/textures/item_texture.json` | item icon atlas entries for the laser pointer, the three orbs (empty and full), the two wands and the grappling gun |

Orbs (checked by `validate_orb` in `tools/validate.py`):

| File | What it is |
|---|---|
| `big_cat_bp/scripts/orbs.js` | Cat Orb + Creature Orb capture/release, imported by `scripts/main.js` |
| `big_cat_bp/scripts/trap_orb.js` | Player Trap Orb (spectator-mode trap with auto-release), imported by `scripts/main.js` |
| `big_cat_bp/items/{cat,creature,trap}_orb.json`, `..._full.json` | each empty orb (stacks to 16) and its occupied version (holds one, not in the creative menu) |
| `big_cat_bp/recipes/{cat,creature,trap}_orb.json` | crafting: 4 glass in a plus around a raw cod / ender pearl / iron bars |
| `big_cat_rp/texts/en_US.lang` | display names |

Wands (checked by `validate_wands` in `tools/validate.py`):

| File | What it is |
|---|---|
| `big_cat_bp/scripts/wands.js` | Size Wand (normal / mini / huge) and Vapor Wand (rainbow / stinky), imported by `scripts/main.js` |
| `big_cat_bp/items/{size,vapor}_wand.json` | the two wand items |
| `big_cat_bp/recipes/{size,vapor}_wand.json` | crafting: red mushroom / stick / brown mushroom, and glowstone dust / stick / fermented spider eye |
| `big_cat_rp/particles/{rainbow_sparkle,stinky_vapor}.particle.json` | the vapor clouds the script spawns around a player |

Grappling Gun (checked by `validate_grapple` in `tools/validate.py`):

| File | What it is |
|---|---|
| `big_cat_bp/scripts/grapple.js` | fire the hook, reel yourself to blocks or hooked entities to you, draw the rope, imported by `scripts/main.js` |
| `big_cat_bp/items/grappling_gun.json`, `big_cat_bp/recipes/grappling_gun.json` | the `mymod:grappling_gun` item; crafting: tripwire hook / string / iron ingot, stacked vertically |
| `big_cat_bp/entities/grapple_hook.json` | the `mymod:grapple_hook` projectile (sticks in blocks, invulnerable) |
| `big_cat_rp/entity/grapple_hook.entity.json`, `big_cat_rp/models/entity/grapple_hook.geo.json` | the hook's four-pronged steel model |
| `big_cat_rp/particles/grapple_rope.particle.json` | `mymod:grapple_rope`, the rope dots the script draws between you and the hook |

Evolution Stone (checked by `validate_evolution` in `tools/validate.py`; stages, stats and the
stage property/groups/events in `big_cat_bp/entities/big_cat.json` come from `tools/gen_evolution.py`):

| File | What it is |
|---|---|
| `big_cat_bp/scripts/evolution.js` | stones dropping from ores, evolving a cat, stage particles, stage-8 flying while ridden; imported by `scripts/main.js` |
| `big_cat_bp/items/evolution_stone.json` | the `mymod:evolution_stone` item (no recipe: ores drop it) |
| `big_cat_rp/models/entity/big_cat_wings.geo.json` | the wings, a second model drawn on the cat (its `body` bone follows the cat's sit / lie-down poses) |
| `big_cat_rp/render_controllers/big_cat_wings.render_controllers.json` | draws the wings; its `part_visibility` hides them below stage 8 |
| `big_cat_rp/animations/big_cat_wings.animation.json`, `controller.animation.big_cat.wings` in `big_cat_rp/animation_controllers/big_cat.animation_controllers.json` | folded wings on the ground, flapping in the air |

The cats' chase goals (`minecraft:behavior.nearest_prioritized_attackable_target` for the
`bigcat_laser_dot` family and `minecraft:behavior.move_towards_target`) live in
`tools/templates/big_cat.behavior.json`, like the rest of the cat's behavior.
