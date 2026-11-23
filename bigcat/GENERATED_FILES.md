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
| `big_cat_rp/textures/items/air_cannon.png` | `tools/gen_air_cannon.py` (pixel art in code) |
| `big_cat_rp/textures/blocks/atomic_bomb_side.png`, `..._top.png`, `..._bottom.png` | `tools/gen_atomic_bomb.py` (pixel art in code) |
| `big_cat_rp/textures/items/{laser,flame,water,ice,barf}_blaster.png` | `tools/gen_blaster.py` (pixel art in code) |
| `big_cat_rp/textures/items/mountain_seed.png` | `tools/gen_mountain.py` (pixel art in code) |
| `big_cat_rp/textures/items/vortex_gun.png`, `big_cat_rp/textures/items/animal_vortex_gun.png` | `tools/gen_vortex.py` (pixel art in code) |
| `big_cat_rp/textures/items/drowned_trap.png`, `big_cat_rp/textures/entity/drowned_lure.png` | `tools/gen_drowned_trap.py` (pixel art in code) |
| `big_cat_bp/entities/drowned.json` (gitignored) | `tools/gen_drowned_trap.py` (vanilla drowned + the trap as an attack target) |
| `big_cat_rp/textures/items/evolution_stone.png`, `big_cat_rp/textures/entity/big_cat_wings.png` | `tools/gen_evolution.py` (pixel art in code) |
| `big_cat_rp/textures/blocks/net_trap.png`, `big_cat_rp/textures/items/net_trap.png` | `tools/gen_net.py` (pixel art in code) |
| `big_cat_bp/entities/morph_<form>.json`, `big_cat_bp/scripts/morph_forms.js`, `big_cat_rp/entity/morph_<form>.entity.json`, `big_cat_rp/render_controllers/morph.render_controllers.json`, `big_cat_rp/textures/items/morph_wand.png` | `tools/gen_morph.py` (`FORMS`: the Morph Wand's creatures) |
| `big_cat_rp/models/entity/mooshroom_drill.geo.json`, `big_cat_rp/textures/entity/mooshroom_drill.png`, `big_cat_rp/textures/items/mooshroom_drill.png` | `tools/gen_mooshroom_drill.py` (`CUBES`: the chassis and mushrooms; pixel art in code) |
| `big_cat_bp/blocks/portal_pad.json`, `big_cat_bp/scripts/portal_colors.js`, `big_cat_rp/textures/blocks/portal_pad_<color>.png`, `big_cat_rp/textures/items/portal_pad.png` | `tools/gen_portal.py` (`COLORS`: one pad colour per dye) |
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

Drowned Trap (checked by `validate_drowned_trap` in `tools/validate.py`):

| File | What it is |
|---|---|
| `big_cat_bp/scripts/drowned_trap.js` | place / pick up the trap, blow up drowned that attack it, drop one randomly enchanted weapon, imported by `scripts/main.js` |
| `big_cat_bp/items/drowned_trap.json`, `big_cat_bp/recipes/drowned_trap.json` | the `mymod:drowned_trap` item (stacks to 16); crafting: 4 iron bars in a plus around a raw cod |
| `big_cat_bp/entities/drowned_lure.json` | the placed trap, `mymod:drowned_lure` (family `bigcat_drowned_trap`, invulnerable, never despawns) |
| `big_cat_rp/entity/drowned_lure.entity.json`, `big_cat_rp/models/entity/drowned_lure.geo.json` | the see-through prismarine cage with a fish inside |

Evolution Stone (checked by `validate_evolution` in `tools/validate.py`; stages, stats and the
stage property/groups/events in `big_cat_bp/entities/big_cat.json` come from `tools/gen_evolution.py`):

| File | What it is |
|---|---|
| `big_cat_bp/scripts/evolution.js` | stones dropping from ores, evolving a cat, stage particles, stage-8 flying while ridden; imported by `scripts/main.js` |
| `big_cat_bp/items/evolution_stone.json` | the `mymod:evolution_stone` item (no recipe: ores drop it) |
| `big_cat_rp/models/entity/big_cat_wings.geo.json` | the wings, a second model drawn on the cat (its `body` bone follows the cat's sit / lie-down poses) |
| `big_cat_rp/render_controllers/big_cat_wings.render_controllers.json` | draws the wings; its `part_visibility` hides them below stage 8 |
| `big_cat_rp/animations/big_cat_wings.animation.json`, `controller.animation.big_cat.wings` in `big_cat_rp/animation_controllers/big_cat.animation_controllers.json` | folded wings on the ground, flapping in the air |

Net Trap (checked by `validate_net_trap` in `tools/validate.py`):

| File | What it is |
|---|---|
| `big_cat_bp/scripts/net_trap.js` | the `mymod:net_trap` custom block component (step on it: caught), holding, releasing; imported by `scripts/main.js` |
| `big_cat_bp/blocks/net_trap.json` | the flat net block (thin collision box, so stepping on it fires `onStepOn`) |
| `big_cat_bp/items/net_trap.json`, `big_cat_bp/recipes/net_trap.json` | the item that places it (`block_placer`, replaces the block's own item); crafting: 4 string in the corners around a slime ball, makes 2 |
| `big_cat_rp/models/blocks/net_trap.geo.json` | a 16x16 plate a quarter pixel thick |
| `big_cat_rp/textures/terrain_texture.json` | block texture atlas entry `mymod_net_trap` |

Morph Wand (checked by `validate_morph` in `tools/validate.py`; the creatures are generated, see above):

| File | What it is |
|---|---|
| `big_cat_bp/scripts/morph.js` | use the wand: next creature (sneak: back to yourself); the costume follows the invisible player; perks; imported by `scripts/main.js` |
| `big_cat_bp/items/morph_wand.json`, `big_cat_bp/recipes/morph_wand.json` | the wand; crafting: feather / stick / leather |

Air Cannon (checked by `validate_air_cannon` in `tools/validate.py`):

| File | What it is |
|---|---|
| `big_cat_bp/scripts/air_cannon.js` | blast everything in a cone in front of you super far (look down: rocket jump), imported by `scripts/main.js` |
| `big_cat_bp/items/air_cannon.json`, `big_cat_bp/recipes/air_cannon.json` | the `mymod:air_cannon` item; crafting: 3 iron ingots over a feather and a piston |

Atomic Bomb (checked by `validate_atomic_bomb` in `tools/validate.py`):

| File | What it is |
|---|---|
| `big_cat_bp/scripts/atomic_bomb.js` | light it (flint and steel, fire charge, redstone, another explosion), countdown, crater, mushroom cloud, kill mobs / fling and protect players; imported by `scripts/main.js` |
| `big_cat_bp/blocks/atomic_bomb.json`, `big_cat_bp/recipes/atomic_bomb.json` | the `mymod:atomic_bomb` block; crafting: 8 TNT around a glowstone block |
| `big_cat_rp/textures/terrain_texture.json` | block texture atlas entries `mymod_atomic_bomb_side/top/bottom` |

Laser Blaster (checked by `validate_blaster` in `tools/validate.py`):

| File | What it is |
|---|---|
| `big_cat_bp/scripts/blaster.js` | hold use to fire: burns through up to 4 blocks per pulse (skips containers and unbreakables), hurts and ignites what's in the beam; imported by `scripts/main.js` |
| `big_cat_bp/items/laser_blaster.json`, `big_cat_bp/recipes/laser_blaster.json` | the blaster (long `use_duration`, so holding the button keeps it firing); crafting: diamond, 2 redstone blocks, laser pointer, glowstone |
| `big_cat_bp/items/flame_blaster.json`, `big_cat_bp/recipes/flame_blaster.json` | the Flame Blaster (same hold-to-fire `use_duration`); crafting: blaze rod, 2 fire charges, laser pointer, glowstone |
| `big_cat_rp/particles/laser_glow.particle.json`, `big_cat_rp/particles/fire_beam.particle.json` | `mymod:laser_glow` (the Laser Blaster's wide beacon glow) and `mymod:fire_beam` (the Flame Blaster's orange beam) |
| `big_cat_bp/items/water_blaster.json`, `big_cat_bp/items/ice_blaster.json` (+ recipes) | the Water and Ice Blasters (same hold-to-fire `use_duration`); crafting: water bucket + 2 lapis / blue ice + 2 snowballs, laser pointer, glowstone |
| `big_cat_rp/particles/water_beam.particle.json`, `big_cat_rp/particles/ice_beam.particle.json` | `mymod:water_beam` and `mymod:ice_beam`, their beams |
| `big_cat_bp/items/barf_blaster.json`, `big_cat_bp/recipes/barf_blaster.json` | the Barf Blaster (same hold-to-fire `use_duration`): makes whoever it hits throw up; crafting: spider eye + 2 slime balls, laser pointer, glowstone |
| `big_cat_rp/particles/barf_beam.particle.json`, `big_cat_rp/particles/barf_spew.particle.json` | `mymod:barf_beam` (its green beam) and `mymod:barf_spew` (the chunks thrown up, aimed with `variable.direction`) |

Mountain Seed (checked by `validate_mountain` in `tools/validate.py`):

| File | What it is |
|---|---|
| `big_cat_bp/scripts/mountain.js` | plant the seed; a diamond-square fractal mountain grows layer by layer (snow peaks, terracotta bands, ores inside); imported by `scripts/main.js` |
| `big_cat_bp/items/mountain_seed.json`, `big_cat_bp/recipes/mountain_seed.json` | the `mymod:mountain_seed` item (stacks to 16); crafting: 4 stone in a plus around wheat seeds |

Vortex Guns (checked by `validate_vortex` in `tools/validate.py`):

| File | What it is |
|---|---|
| `big_cat_bp/scripts/vortex.js` | use: for 5 s creatures within 256 blocks are pulled to you (Monster Vortex: hostile mobs; Animal Vortex: everything else alive; never players), nearest 100 first; imported by `scripts/main.js` |
| `big_cat_bp/items/vortex_gun.json`, `big_cat_bp/recipes/vortex_gun.json` | Monster Vortex (`mymod:vortex_gun`); crafting: iron / ender pearl / iron over iron / redstone block / iron |
| `big_cat_bp/items/animal_vortex_gun.json`, `big_cat_bp/recipes/animal_vortex_gun.json` | Animal Vortex (`mymod:animal_vortex_gun`); same, with wheat instead of the ender pearl |
| `big_cat_rp/particles/laser_beam.particle.json` | `mymod:laser_beam`, the glowing cyan dots the beam is drawn with |

Mooshroom Drill (checked by `validate_mooshroom_drill` in `tools/validate.py`; the chassis model and textures are generated, see above):

| File | What it is |
|---|---|
| `big_cat_bp/scripts/drill.js` | place / pick up (sneak + hit) the drill; while the driver holds forward: spin the mooshroom and carve a 5x5 tunnel (look up / down: stairs, straight down: shaft), ores into the driver's inventory, driver perks; imported by `scripts/main.js` |
| `big_cat_bp/entities/mooshroom_drill_vehicle.json` | the rideable, driveable, invulnerable vehicle; the client-synced `mymod:drilling` property starts the spin |
| `big_cat_bp/items/mooshroom_drill.json`, `big_cat_bp/recipes/mooshroom_drill.json` | the `mymod:mooshroom_drill` item; crafting: red mushroom / diamond pickaxe / brown mushroom over iron block / minecart / iron block |
| `big_cat_rp/entity/mooshroom_drill_vehicle.entity.json`, `big_cat_rp/render_controllers/mooshroom_drill.render_controllers.json` | draws the chassis model plus Minecraft's own mooshroom model and texture (not copied into this repo) |
| `big_cat_rp/animations/mooshroom_drill.animation.json` | spin (the `body` and `head` bones of both models turn around the cow's long axis) and a gentle idle wobble |

Portal Pads (checked by `validate_portal` in `tools/validate.py`; the block and its textures are generated, see above):

| File | What it is |
|---|---|
| `big_cat_bp/scripts/portal.js` | remembers every pad (world dynamic properties), teleports players and creatures to the next pad of the same colour, dyeing, swirl particles; imported by `scripts/main.js` |
| `big_cat_bp/items/portal_pad.json`, `big_cat_bp/recipes/portal_pad.json` | the item that places it (`block_placer`); crafting: obsidian / ender pearl / obsidian, makes 2 |
| `big_cat_rp/models/blocks/portal_pad.geo.json` | a 16x16 plate one pixel thick |
| `big_cat_rp/particles/portal_swirl.particle.json` | `mymod:portal_swirl`, tinted with the pad's colour (`variable.pr/pg/pb` from the script) |
| `big_cat_rp/textures/terrain_texture.json` | block texture atlas entries `mymod_portal_pad_<color>` |

The cats' chase goals (`minecraft:behavior.nearest_prioritized_attackable_target` for the
`bigcat_laser_dot` family and `minecraft:behavior.move_towards_target`) live in
`tools/templates/big_cat.behavior.json`, like the rest of the cat's behavior.
