# Testing the Big Cat coats

Everything under `big_cat_bp/` and `big_cat_rp/` that relates to coats is **generated**. Don't edit it by hand, because the next build overwrites it. To change:
- **coats** (count, seed, colors, patterns): edit `tools/coats_config.json`.
- **the cat's behavior** (size, AI, taming): edit `tools/templates/big_cat.behavior.json`.
- **the client entity** (animations, geometry): edit `tools/templates/big_cat.client_entity.json`.
- **hand-painted patterns**: drop PNGs into `art/coat_layers/` (see the README there).

Then rebuild.

## One-time setup (Windows)

1. Install Python 3.12+ and Pillow: `pip install pillow`. On this PC both are already installed.
2. In Minecraft, go to **Settings > Creator** and turn on **Content Log File** and **Content Log GUI**, so JSON errors show on screen.
3. Create a test world:
   - **Creative**, **Cheats on**, **Flat** world.
   - **Daylight cycle off** and **Mob spawning off**, so only our cats appear.
4. In the world's settings, open **Behavior Packs** and activate **Big Cat BP**. The resource pack attaches automatically. The pack needs **no experiments**.

## Every iteration

1. Run `python tools/build.py`. It generates the coats and JSON, validates them, and copies the packs into `development_behavior_packs` / `development_resource_packs`. It prints which `com.mojang` folder it used. Any problem stops the build with a list of what's wrong.
   - Look at `build/coat_preview.png` first. It shows every coat with its index, without launching the game.
2. **Fully exit the world to the main menu and reopen it.** Texture and entity JSON changes aren't picked up live, and `/reload` only reloads scripts and functions. If changes still don't appear, restart Minecraft. If the deploy step printed a WARNING about an imported copy, delete that copy under **Settings > Storage**.
3. Summon a batch to see the variety:
   - `/function test_cats` summons 20 random cats in a 5×4 grid in front of you.
   - `/function clear_cats` removes all Big Cats.
   - `/summon mymod:big_cat` summons one at a time.
4. Check:
   - No purple/black checkerboard (that means a missing texture).
   - No Content Log errors.
   - The cats look different from one another.
   - Eyes, nose and inner ears look like the original.
   - Adults are still giant (scale 3), babies are scale 1.5.
5. To check a specific coat:
   - `/function coats/page_01` … `coats/page_10` spawn 20 cats each, named **"Coat 000"** to **"Coat 199"**, each forced to that coat. The indices match `build/coat_preview.png`.
   - To force a coat on an existing cat: `/event entity @e[type=mymod:big_cat,c=1] mymod:set_coat_42`. This targets the nearest cat.
   - To browse coats on one cat: `/event entity @e[type=mymod:big_cat,c=1] mymod:next_coat` (or `prev_coat`, or `randomize_coat`).
   - Don't pass a coat event to `/summon` as its spawn event. That replaces `minecraft:entity_spawned`, so the cat would skip its adult/wild setup and not be giant. Summon first, then use `/event`.

## Things to check once after this change

- **Every way a cat is created gets a coat:** `/summon`, the spawn egg, and breeding two tamed cats (the kitten gets its own random coat).
- **Taming keeps the coat and adds a collar** (red by default; dye the cat to change it). Each coat has a `coat_###_tame.png` twin. The vanilla `cat` material tints by texture *alpha* with the collar color, so the tame twin is alpha 4 except the 16 collar pixels. If a tamed cat turns completely red, that rule is broken (validation checks it).
- **Cats that existed before this version get a coat when the world loads.** Open a world that has big cats from before this update (version 1.0.0). They should show *different* coats.
  - If they all show the **same** coat, the engine didn't evaluate the random default for saved cats. Tell me, and I'll add a one-time fixer that re-randomizes cats.
  - Cats that already show a random coat keep it; that part is expected.
- **Sounds** still vary between the `default` and `royal` variants. The existing `mymod:sound_variant` property is untouched.

## Laser pointer

Hold the **Laser Pointer** and use it (right-click; on touch screens, tap or hold the use button) while looking at a block up to 32 blocks away. A small red dot with a red glow appears on that surface. Big Cats within 24 blocks stalk it and pounce on it, the way they hunt rabbits. Use it again to move the dot. The dot disappears:
- 5 seconds after your last use,
- as soon as you switch away from the pointer, or
- when you point it at the sky or at something more than 32 blocks away.

Every so often a cat that's batting at the dot gets bored and ignores it for 3–8 seconds.

The pointer is crafted from a glass pane, redstone and an iron nugget, stacked vertically in one column. The pack still needs no experiments; the script uses the stable `@minecraft/server` 2.11.0.

The files that make up the pointer are listed in `GENERATED_FILES.md` under "Hand-written". The script is `big_cat_bp/scripts/main.js`. After editing only the script, `/reload` in the world is enough. For JSON or texture changes, exit to the menu and reopen the world, as usual.

### Test steps

1. Run `python tools/build.py`, then exit and reopen the test world (Creative, Cheats on).
2. `/give @s mymod:laser_pointer`. Check that the item shows the pen icon and the name **Laser Pointer** (not `item.mymod:laser_pointer.name`). It's also in the creative inventory under **Equipment**.
3. `/function test_cats` (or `/summon mymod:big_cat` a few times), and step back about 10 blocks.
4. Point at the floor near the cats and use the pointer. Check:
   - A red dot sits on the floor, with a glow you can see at night too, and a soft click plays.
   - Within about a second, cats turn toward it. They sneak toward it, sprint the last few blocks and leap at it.
   - Using the pointer on a wall puts the dot on the wall. The cats jump at it.
   - Moving the dot (use again somewhere else) makes the cats follow it.
   - Holding use while aiming at a block within reach drags the dot along.
5. Wait 5 seconds without using it, or switch hotbar slots. The dot vanishes and the cats go back to normal.
6. Tame a cat (fish), then repeat. Tamed cats should chase too. A **sitting** tamed cat should stay seated; that's intentional.
7. Make sure the dot can't be harmed: hit it with a sword, point it into a lava pool. It should never take damage, move, drop anything, or show a death animation.
8. Save and quit with the dot visible, then reopen the world. No dot should be left behind; the script removes leftovers within a second.
9. Regression: check that the cats are still giant, coats still vary, `/event entity @e[type=mymod:big_cat,c=1] mymod:next_coat` works, and taming still adds the collar.

### What to look for in the Content Log

- **No** lines containing `[bigcat laser]`. The script logs `could not place dot` or `could not remove dot` there only when something fails.
- **No** errors mentioning `scripts/main.js`, `@minecraft/server`, `laser_dot`, `laser_pointer`, `nearest_prioritized_attackable_target` or `move_towards_target`.
- A script error at world load such as `Failed to load module` or `module @minecraft/server version 2.11.0 not found` means the game is older than the API version. Update Minecraft; don't lower the version.

### Likely failure modes

| Symptom | Probable cause / what to try |
|---|---|
| Item does nothing at all, no dot, no click | Script not running. Check the Content Log at world load. Make sure **Big Cat BP** is active (not an old imported copy, see the deploy WARNING). |
| Dot only appears when you aim at nearby blocks, never far ones | `itemUse` does not fire for this item in the air on your platform (only `playerInteractWithBlock` does). Report it; the item may need a `minecraft:use_modifiers` component. |
| Dot appears, but the cats ignore it | The cats aren't accepting the dot as a target. Check the Content Log for `nearest_prioritized_attackable_target` errors. Test with `/summon mymod:laser_dot` right next to a cat. |
| Cats turn toward the dot but don't walk to it from far away | `ocelotattack` only works within 15 blocks; farther away, `move_towards_target` should take over. Get closer to check. |
| Cats never lose interest, or lose it for good | Depends on whether the `has_tag` filter on `self` is checked again while a target is active. `/tag @e[type=mymod:big_cat] list` shows `bigcat_bored`. The script clears stale tags every second. |
| Dot visible but no glow at night | The particle `mymod:laser_dot_glow` failed to load. Look for a particle error in the Content Log. |
| Purple/black checkerboard dot or item icon | `textures/entity/laser_dot.png` or `textures/items/laser_pointer.png` is missing. Rebuild. |
| A dot stays after the player leaves | Should be removed by the sweep once its chunk is loaded. If one persists, `/event entity @e[type=mymod:laser_dot] mymod:laser_dot_despawn` removes it. |

## Packaging for the iPad

1. Run `python tools/build.py --package`. It bumps the patch version in both manifests (and the BP's dependency on the RP), validates again, deploys, and writes `dist/big_cat.mcaddon`. The version bump makes the iPad accept the file as an update rather than "already installed".
2. Get `dist/big_cat.mcaddon` onto the iPad (AirDrop, iCloud Drive or OneDrive), tap it, and choose **Minecraft**. Both packs import together.
3. On the iPad, edit the world: activate **Big Cat BP** under Behavior Packs. If an older version is listed as active, remove it and add the new one.
4. Commit the bumped manifests, so the next package continues from the new number.

## Useful commands

| Command | What it does |
|---|---|
| `python tools/build.py` | Generate, validate and deploy |
| `python tools/build.py --package` | The same, plus a version bump and `dist/big_cat.mcaddon` |
| `python tools/build.py --no-deploy` | Generate and validate only |
| `python tools/build_coats.py` | Coats and preview only (quick look at config changes) |
| `python tools/validate.py` | Validation only |
| `python tools/deploy_dev.py` | Copy the packs into Minecraft only |

Set `BIGCAT_COM_MOJANG` to override the detected `com.mojang` folder.

## Cat Orb

Catch a Big Cat in an orb, carry it around, and let it out again later.

**Get one:** `/give @s mymod:cat_orb`, or craft it: 4 glass in a plus shape around a raw cod.

1. Rebuild, then exit to the menu and reopen the world.
2. Summon a cat and give it a name with a name tag, so you can check it comes back the same.
3. **Catch it:** hold the orb and right-click the cat, or aim at it from up to 8 blocks away and use the orb.
   - The cat vanishes with a portal puff and a "Caught …!" message.
   - The orb in your hand becomes a glowing amber **Cat Orb (occupied)** with the cat's name, coat number and wild/tamed status in its tooltip.
   - If you were holding a stack of empty orbs, one turns into the occupied orb and goes into your inventory.
4. **Let it out:** right-click a block with the occupied orb, or aim at a block up to 8 blocks away and use it.
   - The cat appears next to the face you clicked, with hearts, a meow and "Welcome back, …!".
   - You get the empty orb back.
5. Check it's the **same** cat: same coat, same name, still tamed to you with the same collar colour, still an adult or still a baby.
6. Edge cases:
   - Someone else's tamed cat can't be caught ("That cat belongs to someone else").
   - Save and quit while holding an occupied orb, reopen, and release it. The cat should still come back.
   - Right-clicking a tamed cat with the orb must not make it sit.

**What could go wrong:**

| Symptom | Likely cause |
|---|---|
| "Too crowded: something else is right next to …" | Another mob, a dropped item or an XP orb is in the same block. Wait for it to move, or pick up the item. This stops the orb from copying anything else. |
| "The orb fizzled" | Saving the cat failed. The Content Log shows `[bigcat orb] capture failed: …`. |
| Releasing says "Its cat could not be found" | The saved cat was deleted, for example by `/structure delete`. The orb resets to empty. |
| Nothing happens when right-clicking the cat | The click-on-cat event didn't fire. Aim at the cat and use the orb instead, and tell me. |

## Creature Orb

Works exactly like the Cat Orb, but catches **any mob** except players, bosses (Ender Dragon, Wither, Warden,
Elder Guardian) and objects (armor stands, boats, minecarts). Other people's tamed pets are refused too.

**Get one:** `/give @s mymod:creature_orb`, or craft it: 4 glass in a plus shape around an ender pearl.

1. Catch a few different mobs: a cow, a named villager (check its trades come back), a tamed wolf, a zombie, a Big Cat.
2. Catch some **wild** animals too (goats, rabbits): they must end up in the orb, not vanish.
3. Release each one and check it's the same: name, health, baby/adult, owner, villager trades.
4. Try a boss (`/summon wither`) or an armor stand: you should get a refusal message and nothing happens.
5. Cat Orbs you filled before this update still release normally.

## Player Trap Orb

Needs **two players** in the same world (it can't trap you, and single player has no one else to catch).

**Get one:** `/give @s mymod:trap_orb`, or craft it: 4 glass in a plus shape around iron bars.

1. Aim at another player within 10 blocks and use the orb, or hit them with it.
   - They see "Trapped!", switch to spectator mode high above where they stood, and can't move. Their actionbar shows a countdown.
   - Your orb becomes **Player Trap Orb (occupied)** with their name.
2. Use the occupied orb on a block. They appear there in their old game mode and can move again ("You're free!").
3. Safety checks:
   - Wait 5 minutes without releasing: they're freed where they were caught ("The trap wore off").
   - Trap someone, then leave the world: they're freed within a second.
   - Have the trapped player leave and rejoin: they're still trapped (or freed, if the time ran out or you released them while they were away).
   - Trapping yourself or someone already trapped is refused.

## Taming monsters

Zombies, skeletons and creepers can be tamed, the silly way. `tools/gen_tame.py` builds tameable copies of
their vanilla definitions (gitignored), and `scripts/tame_monsters.js` handles the taming.

| Mob | How to tame | What it says |
|---|---|---|
| Skeleton | Use a **milk bucket** on it | "The skeleton finally got its calcium!" (you keep the empty bucket) |
| Zombie | Use a **cake** on it | "Nobody ever remembered its birthday. Until you." |
| Creeper | **Sneak**, empty hand, and use it (a **hug**) | 35% chance it accepts. Otherwise it **sneezes**: a harmless fake explosion that launches you backwards |

On touch screens (iPad), the mob shows a **Give Milk**, **Give Cake** or **Hug** button when you hold the right thing.

1. Rebuild, exit to the menu and reopen the world. Easiest in Creative, where monsters ignore you.
2. Summon each mob (`/summon skeleton`, `/summon zombie`, `/summon creeper`) and tame it as above.
   - You should see a "Tamed!" title with a funny line, hearts, and a level-up chime.
   - In Survival, the cake is used up and the milk bucket becomes an empty bucket.
3. A tamed monster:
   - follows you around and never attacks you, even if you hit it;
   - doesn't burn in daylight (it gets hidden fire resistance);
   - never despawns;
   - zombies and skeletons attack other, untamed monsters, and anything that hurts you or that you attack;
   - creepers just tag along and never explode on their own.
4. Hugging a creeper without sneaking, or with something in your hand, gives a hint instead.
5. Other zombies, skeletons and creepers still behave normally until you tame them.

**What could go wrong:**

| Symptom | Likely cause |
|---|---|
| Nothing happens when using milk/cake/empty hand on the mob | The interaction didn't reach the script. Check the Content Log for errors in `zombie.json`, `skeleton.json` or `creeper.json`. |
| A tamed creeper still blows up | It got a target anyway. Report which mob it was chasing. |
| Tamed mobs disappear after a while | The despawn override didn't take. Name them with a name tag as a workaround and report it. |

## Size Wand and Vapor Wand

`scripts/wands.js` handles both wands. `tools/gen_player.py` builds a copy of the vanilla player definition (gitignored)
with two extra sizes. Only the look changes: the hitbox, reach and first-person camera stay normal size.

| Wand | Crafting (top to bottom) | Each use moves to the next setting |
|---|---|---|
| Size Wand | red mushroom, stick, brown mushroom | normal → mini (0.4×) → huge (2.5×) → normal |
| Vapor Wand | glowstone dust, stick, fermented spider eye | none → rainbow sparkles → stinky green vapor → none |

Aim at another player within 10 blocks and use the wand, or hit them with it, to change them. Use it anywhere else to
change yourself. **Drinking milk** puts you back to normal size and clears your vapor.

1. Rebuild, exit to the menu and reopen the world. Switch to third person (F5) to see yourself.
2. Use the Size Wand three times: you should go mini, then huge, then normal, with an action-bar message and a sound each time.
3. Use the Vapor Wand: rainbow sparkles around your whole body, then green stinky clouds drifting up from your middle, then nothing.
4. Combine them: the vapor should scale with you when you're mini or huge.
5. With a second player (or the iPad): aim and use, or hit them. Both of you should see the change, and they get a message saying who did it.
6. Leave and rejoin, and die and respawn: your size and vapor should stay.
7. Drink a milk bucket: back to normal, no vapor.

**What could go wrong:**

| Symptom | Likely cause |
|---|---|
| Size never changes, but the message shows | The player override didn't load. Check the Content Log for errors in `player.json`. Another add-on that also replaces `player.json` would also cause this. |
| No particles, but the message shows | Check the Content Log for errors in `rainbow_sparkle` / `stinky_vapor`. |
| Particles are huge or tiny when you're normal size | The `variable.size` value from the script isn't reaching the particle. Report it. |


## Grappling Gun

`scripts/grapple.js` handles the gun. Use it to fire a hook (a real projectile, `mymod:grapple_hook`) up to about 40 blocks:

- **Hook hits a block:** you're reeled in to that spot and land on top if you hooked the top of a block.
- **Hook hits a mob, player, boat, etc.:** it's reeled in to you.
- A rope of small brown dots connects you to the hook.
- It lets go when you arrive, after 5 seconds, if you get stuck, or when you use the gun again, sneak, or switch away from the gun.
- While you're being reeled in, and for 2 seconds after, you have Slow Falling, so you never take fall damage from grappling.

Crafting (top to bottom): tripwire hook, string, iron ingot.

1. Rebuild, exit to the menu and reopen the world. `/give @s mymod:grappling_gun`. Check the icon and the name **Grappling Gun**.
2. Fire at a wall 20 blocks away: the hook flies, sticks, and you zip to the wall along the rope. Fire at the top of a tall pillar: you should land on top.
3. Fire at the sky: the hook flies about 40 blocks, then is retracted with a low click.
4. `/summon pig` 15 blocks away and hook it: the pig is pulled to you and stops in front of you. Try a cow up on a hill, and a pig in water.
5. While being reeled in, sneak or use the gun again: you let go and drift down slowly without damage.
6. With a second player: hooking them pulls them to you, and they see "<name> hooked you!".
7. Save and quit while a hook is out, then reopen: no hook is left behind (the script removes leftovers within a second).

**What could go wrong:**

| Symptom | Likely cause |
|---|---|
| Nothing happens on use, no sound | Check the Content Log for script errors in `grapple.js`. |
| Hook flies but passes through mobs | The projectile isn't registering entity hits. Report it, since the `on_hit` settings in `entities/grapple_hook.json` need adjusting. |
| Hook bounces off blocks instead of sticking | You still get pulled (the script keeps the hook at the hit point), but report it. |
| Hook model is invisible or a purple/black box | Check the Content Log for `grapple_hook` geometry/texture errors. |
| Being pulled feels jerky, especially with friends | Expected for some multiplayer lag; `SELF_SPEED` in `grapple.js` can be lowered. |
| Mobs wearing netherite / players in netherite barely move | Knockback resistance reduces the pull. |

## Evolution Stone

`scripts/evolution.js` handles the stone. The 8 stages and their stats live in `tools/gen_evolution.py`, which adds them to the generated `big_cat.json` (property `mymod:evolution`, component groups `mymod:evolution_1..8`, events `mymod:evolve_0..8`).

- **Finding stones:** breaking any ore (coal, iron, copper, gold, redstone, lapis, diamond, emerald, nether gold, nether quartz, and the deepslate versions) has a 5% chance to drop one. Fortune raises the chance (+50% per level, so 12.5% with Fortune III). Silk Touch and Creative mode never drop one. There is no crafting recipe.
- **Evolving:** use a stone on a **tamed** Big Cat (click it, or aim at it within 8 blocks and use). It moves up one stage, heals fully, and one stone is used up (none in Creative).

| Stage | Name | Particles | Health | Attack | Speed | Knockback resist. | Fire immune |
|---|---|---|---|---|---|---|---|
| 0 | (tamed cat) | none | 20 | 4 | 0.30 | 0 | no |
| 1 | Sprout | green sparkles | 30 | 6 | 0.31 | 0.1 | no |
| 2 | Blossom | cherry petals | 40 | 8 | 0.32 | 0.2 | no |
| 3 | Frost | snowflakes | 50 | 10 | 0.33 | 0.3 | no |
| 4 | Ember | small flames | 60 | 12 | 0.34 | 0.4 | yes |
| 5 | Soulfire | blue flames | 70 | 14 | 0.35 | 0.5 | yes |
| 6 | Firefly | fireflies | 80 | 16 | 0.36 | 0.6 | yes |
| 7 | Arcane | purple glow dust | 90 | 18 | 0.38 | 0.7 | yes |
| 8 | Celestial | end rod sparkles + **wings** | 100 | 20 | 0.40 | 0.8 | yes |

- **Flying (stage 8):** ride the cat and press jump to take off. In the air, hold forward to fly where you look (look up to climb, down to dive), hold back to drift backwards, and hold jump to climb straight up. Let go of everything and it hovers, sinking very slowly. Fly into the ground to land. If you get off mid-air you get Slow Falling for 10 seconds.

### Test steps

1. Rebuild, exit to the menu and reopen the world. `/give @s mymod:evolution_stone 16`. Check the grey-and-violet icon, the enchanted shimmer and the name **Evolution Stone** (Creative inventory: **Items**).
2. Ore drops: switch to Survival (`/gamemode s`) and mine about 40 ores. A stone should drop roughly once in 20, with a green sparkle, a ding and "You found an Evolution Stone!". With a Silk Touch pickaxe: never. Back in Creative: never.
3. Use a stone on a **wild** cat: "Only a tamed Big Cat can evolve" and the stone is kept.
4. Tame a cat (fish), then use stones on it one at a time. Each time: a burst of the new stage's particles, a level-up sound with a rising pitch, and "evolved! Stage n/8: <name>". The cat does not sit down or get mounted when you click it with a stone.
5. Between uses, watch for a few seconds: the cat gives off an occasional particle of its stage. It should be subtle, not a cloud.
6. Check stats on the way: hit it with a sword and see it take longer to kill at higher stages. From stage 4 it doesn't burn in fire.
7. Stage 8: wings appear on its back with a totem burst and a wing-flap sound. Using another stone says it's fully evolved and keeps the stone.
8. Wings on the ground: folded back over the body, gently moving. Make it sit (sneak + use): the wings tilt with the body.
9. Ride it (use with an empty hand). Press jump: it leaps up and starts flapping fast. Hold forward and look around: it flies where you look. Hold jump to climb. Let go: it hovers and sinks slowly. Fly into the ground: it lands and walks normally again.
10. While flying high, sneak to get off: you drift down with Slow Falling and take no damage. The cat falls and takes no fall damage either.
11. Catch a stage-8 cat in a Cat Orb and release it: it still has wings and stage 8. Save and quit, reopen: same.
12. Shortcuts for testing: `/event entity @e[type=mymod:big_cat,c=1] mymod:evolve_8` jumps straight to a stage (0-8; 0 removes all stages). This doesn't heal the cat.

**What could go wrong:**

| Symptom | Likely cause |
|---|---|
| Wings stick out sideways from the cat's side or float above it | The wing model's `body` bone doesn't line up with the vanilla cat's. Adjust the pivots/origins in `models/entity/big_cat_wings.geo.json` (the cat's back is at y=10, z -7..9). |
| Wings droop down instead of folding up, or sweep forward | The rotation signs in `animations/big_cat_wings.animation.json` are flipped. Negate the `query.is_on_ground ? ...` angles. |
| Feathers point forward / gold edge at the back | Swap the texture: flip the `uv` of the up/down faces in the wing geometry. |
| Cat sinks while hovering, or drifts up | Raise or lower `GRAVITY_LIFT` in `evolution.js` (0.08 is vanilla gravity). |
| Flying feels too fast, slow or floaty | `FLY_SPEED`, `CLIMB_SPEED` and `STEERING` in `evolution.js`. |
| Jump does nothing in the air | `player.inputInfo` isn't reporting jump; check the Content Log. |
| Health didn't go up | Look for Content Log errors about `mymod:evolution_*`. |

## Net Trap

`scripts/net_trap.js` handles the net. It's a flat block you place on the ground. The first creature that walks onto it is caught: held on the net for 10 seconds, then the net is used up. Mobs, animals, Big Cats and other players are all caught. The player who placed the net can walk over it safely (`OWNER_IS_SAFE` in the script). Bosses (dragon, wither, warden, elder guardian), items, arrows and players in spectator mode are never caught. Breaking a net frees whatever is in it.

- **Mobs** get Slowness 255 and are put back on the net if they get pushed off it.
- **Players** have movement and jump turned off. They always get their controls back: when the 10 seconds end, when the net breaks, when they rejoin, and after `/reload`.

Crafting: string in the four corners and a slime ball in the middle makes 2 nets.

### Test steps

1. Rebuild, exit to the menu and reopen the world. `/give @s mymod:net_trap 8`. Check the icon, the name **Net Trap** (Creative inventory: **Equipment**), and that it places only on top of blocks as a flat rope mesh you can see the ground through.
2. Walk over your own net: nothing happens.
3. Place a net in a pen and `/summon pig` next to it. Lure or push the pig onto it: a twang, a puff of particles and "Your net caught Pig!". The pig stays put with white specks around it, even if you hit it. After 10 seconds the net disappears and the pig walks off.
4. Try a zombie at night, a Big Cat, a chicken: all caught. A dropped item or an arrow landing on the net: nothing happens.
5. Break a net that's holding something: it's freed right away.
6. With a second player: they walk onto your net and see "You're caught in a net! (10s)". They can look around but can't move or jump, and "You wriggled free" appears when it ends. Have them disconnect while caught and come back: they can move.
7. `/reload` while a player is caught: they can move again right away.

**What could go wrong:**

| Symptom | Likely cause |
|---|---|
| Nothing happens when walking onto it | `onStepOn` isn't firing. Check the Content Log for errors about the `mymod:net_trap` custom component, and that the block has its collision box. |
| Net shows as a purple/black or solid block | Check `terrain_texture.json` and the block geometry in the Content Log. |
| Net item shows as a tiny flat sliver instead of the icon | `block_placer`'s `replace_block_item` didn't take; report it. |
| A player stays frozen after release | Run `/reload` (the script unlocks anyone it isn't holding). Report it. |
| Mobs jitter on the net | Expected a little while they try to walk; raise `SNAP_DISTANCE` in the script to make it calmer. |

## Drowned Trap

`scripts/drowned_trap.js` handles the trap. `tools/gen_drowned_trap.py` builds a copy of the vanilla drowned (gitignored)
that treats the trap as an enemy. No other mob is changed, so zombies, husks and the rest ignore it.

- **Placing:** use the Drowned Trap on a block up to 8 blocks away. Aiming through water at the sea floor works. A
  see-through cage with a fish inside appears there.
- **Catching:** drowned within about 12 blocks that can see the trap go for it. When one hits it, throws a trident at it, or
  gets right up against it, the drowned blows up. The explosion is just for show: nothing else is hurt and no blocks break.
- **The drop:** no normal loot, just **one weapon with 1–3 random enchantments**. That's the drowned's own trident if it
  was holding one, otherwise a random trident, iron or diamond sword, iron or diamond axe, bow or crossbow (tridents are the
  most likely). Players within 32 blocks see "Drowned Trap: caught a drowned!".
- **It keeps working**, drowned after drowned. **Hit it** to pick it back up.

Crafting: 4 iron bars in a plus around a raw cod.

1. Rebuild, exit to the menu and reopen the world. `/give @s mymod:drowned_trap`. Check the icon and the name **Drowned Trap**.
2. Place it on the floor. `/summon drowned` about 6 blocks away: it walks to the trap and hits it, then boom, and a weapon
   with enchantments (check its tooltip) drops where the drowned was.
3. Do it a few times: weapons and enchantments should vary, with no curses and no rotten flesh.
4. Give a drowned a trident (`/summon drowned`, then `/replaceitem entity @e[type=drowned,c=1] slot.weapon.mainhand 0 trident`)
   and step back. It throws at the trap or hits it, and should drop an enchanted **trident**.
5. Underwater: place the trap on the sea floor near drowned, at night or in an ocean. It should catch them there too.
6. `/summon zombie` and `/summon husk` next to the trap: they ignore it and come for you.
7. Hit the trap: it pops back into your inventory.
8. Survival: drowned still attack you normally when the trap isn't around, and killing one yourself still gives normal loot.

**What could go wrong:**

| Symptom | Likely cause |
|---|---|
| Drowned ignore the trap | The patched `drowned.json` didn't load. Check the Content Log, and check that no other add-on replaces the drowned. |
| A drowned that held a trident drops a random weapon instead | This game version doesn't let scripts read a mob's hands. Report it. |
| The trap can't be picked up by hitting it | Report it; picking up may need a different trigger. |
| Nothing happens when placing | Check the Content Log for errors in `drowned_lure.json` or `drowned_trap.js`. |


## Morph Wand

Right-click (or tap) with the wand: you turn into the next creature. The order is Chicken, Pig, Fox, Frog, Bee, Creeper,
Iron Golem, Big Cat, then yourself again. **Sneak + use** takes you straight back to yourself, and so does **milk**.
Aim at another player (up to 10 blocks), or hit them with the wand, to change *them* instead.

How it works: you get Invisibility, and a costume creature with no AI follows you every tick. Invisibility doesn't hide
armour, so your armour moves into your inventory (marked "Morph Wand: worn on ...") and goes back on when you're yourself
again. If your inventory is full, the pieces that don't fit stay on and show. The item in your hand still shows. Each
creature has a perk:

| Form | Perk |
|---|---|
| Chicken | Slow Falling |
| Pig | Saturation (never hungry) |
| Fox | Speed I + Night Vision |
| Frog | Jump Boost III |
| Bee | Slow Falling; **hold jump to fly up** |
| Creeper | sneak for 1.5 s: hiss, then a harmless BOOM (no damage, no broken blocks) |
| Iron Golem | Strength II + Resistance II, but Slowness I |
| Big Cat | Speed II + Jump Boost I, and the costume is twice the size |

Crafting: feather / stick / leather, stacked vertically.

1. Rebuild, exit to the menu and reopen the world. `/give @s mymod:morph_wand`. Check the pig-face icon and the name **Morph Wand**.
2. Press F5 to see yourself. Use the wand 9 times and check each creature appears, walks with its legs moving and
   faces where you look. The action bar names each form and its perk.
3. Walk, sprint and jump in each form: the costume should stay on you with no more than a slight lag.
4. Bee: hold jump and you float up. Let go and you drift down slowly.
5. Creeper: hold sneak and you hear a hiss, then a boom about 1.5 s later. Nothing gets hurt.
6. Sneak + use: you're yourself, no longer invisible, and the perks are gone. Try milk too.
   Wear armour before morphing: it moves into your inventory while you're a creature and goes back on afterwards.
7. Pick a form, then die, respawn, leave the world and come back: you should still be that creature.
8. With a second player: aim at them and use the wand, or hit them with it. They change, and you don't.

**What could go wrong:**

| Symptom | Likely cause |
|---|---|
| You're invisible but there's no creature | Check the Content Log for `morph_<form>.entity.json` or `morph.js` errors. |
| A creature is lying down or upside down (most likely the Fox or the Big Cat) | The vanilla "setup" animation doesn't suit this entity. Report which one. |
| Legs don't move while walking | `query.modified_move_speed` doesn't update for teleported entities. Report it; the fix is a script-driven walk animation. |
| A creature is left behind after `/reload` | It should vanish within 2 s (orphan sweep). If not, report it. |

## Air Cannon

`scripts/air_cannon.js` handles it. Use the Air Cannon and a blast of air shoots out in a cone up to 16 blocks in front of
you. Every player and creature in the cone, plus dropped items and arrows, is launched **super far** the way you're
looking. The closer they are, the harder they go.

- **Look up** to send them up, **straight ahead** to send them far and a bit up.
- **Look straight down at the ground** to rocket-jump yourself into the air.
- Launched players and Big Cats, and you after a rocket jump, get Slow Falling a moment later, so they don't die from
  the fall. Other mobs land however they land.
- Pets in front of you get blasted too, so aim carefully.

Crafting: 3 iron ingots on top, a feather and a piston under them.

1. Rebuild, exit to the menu and reopen the world. `/give @s mymod:air_cannon`. Check the teal cannon icon and the name **Air Cannon**.
2. `/summon cow` about 5 blocks in front and fire: whoosh and white puffs, and the cow flies about 30+ blocks.
3. Fire at a group of mobs: everything in the cone flies. Mobs right next to you go furthest.
4. Look up at a mob close by and fire: it goes straight up.
5. Look down at the ground and fire: you shoot up, then float down slowly.
6. With a second player (or the kids): blast them. They fly far and float down without fall damage.
7. Click a nearby block with it: it still fires.

**What could go wrong:**

| Symptom | Likely cause |
|---|---|
| Mobs move but not far | `PUSH_NEAR` / `PUSH_FAR` in `air_cannon.js` are too low. Turn them up. |
| Players don't move at all | `applyKnockback` failed. Check the Content Log. |
| No whoosh or puffs | A particle or sound name changed in this game version. The push still works. |

## Atomic Bomb

`scripts/atomic_bomb.js` handles it. The Atomic Bomb is a block. **It really destroys your world**: the crater is about
110 blocks across. Make a backup or test in a copy of the world first.

- **Light it:** use flint and steel or a fire charge on it, power it with redstone, or blow it up with TNT or a creeper.
  Another explosion gives a 2-second fuse.
- **Countdown:** 10 seconds of beeps that speed up, smoke, and "ATOMIC BOMB in 10..." for everyone within 240 blocks.
  **Break the bomb to defuse it.**
- **Boom:** a white flash and screen shake, a huge ragged crater with fire and blackstone on the floor, and a mushroom cloud.
  Bedrock is never removed.
- **Mobs** within 90 blocks die. **Players aren't hurt:** everyone within 160 blocks is flung away and gets 20 s of full
  Resistance, Fire Resistance and Slow Falling. **Tamed pets** (Big Cats, dogs) and **name-tagged mobs** are treated like players.

Crafting: 8 TNT around a glowstone block.

1. Rebuild, exit to the menu and reopen the world (**a copy!**). `/give @s mymod:atomic_bomb`. The block should be yellow
   with the radiation symbol and a steel top with a red fuse. The name is **Atomic Bomb**.
2. Place it, light it with flint and steel, and run. Watch for beeps, smoke and the countdown on the action bar.
3. Light another one and break it before it goes off: "Atomic Bomb defused!".
4. Let one go off with you about 20 blocks away: flash, shake and boom. You fly, float down, and take no damage.
   A crater with a mushroom cloud above it.
5. Put cows and zombies near it: they're gone. Put a tamed Big Cat near it: it's flung but alive.
6. A lever or redstone torch next to the bomb should light it. If not, see below.
7. TNT next to the bomb: the bomb goes off 2 s after the TNT.

**What could go wrong:**

| Symptom | Likely cause |
|---|---|
| Redstone doesn't light it | `getRedstonePower()` returns nothing for this block. Use flint and steel; report it. |
| Flint and steel lights a fire on top instead | The before-event didn't catch the click. Report it. |
| The crater is only partly dug | Part of it was outside the loaded chunks. Stand closer (but not too close!). |
| The game stutters for a second | Expected while the crater is dug. Lower `CRATER_RADIUS` in `atomic_bomb.js` if it's bad on the iPads. |
| No flash | The `camera` command isn't allowed (cheats off). Everything else still works. |


## Laser Blaster

**Hold** use (right-click, or hold on touch) and a bright cyan beam fires continuously until you let go. A quick click
gives a short burst. Every 2 ticks the beam reaches up to 64 blocks and burns through up to 4 blocks (no drops), so
about 40 blocks a second. It hurts and sets fire to creatures and players in the beam, but never you, your own tamed pets
or Morph Wand costumes.

The beam **stops at** (never destroys) unbreakable blocks (bedrock, portals, command blocks, barriers, reinforced
deepslate...) and anything that holds items (chests, barrels, furnaces, hoppers, shulker boxes...), so nobody's stuff
gets deleted. It goes straight through water and lava.

Crafting: diamond on top, redstone block / laser pointer / redstone block, glowstone at the bottom.

1. Rebuild, exit to the menu and reopen the world. `/give @s mymod:laser_blaster`. Check the icon, glint and the name **Laser Blaster**.
2. Hold use at a hillside: a beam appears from the gun, and a tunnel forms 4 blocks deeper every pulse. Let go: it stops at once.
3. Click once: a short burst only.
4. Aim at a chest behind some dirt: the dirt burns, the chest stays with its items, and the beam ends on it.
5. `/summon zombie` 20 blocks away and hold the beam on it: it catches fire and dies within a few seconds.
6. Hold the beam on your own tamed Big Cat: nothing happens to it.
7. Switch to another item while firing: the beam stops.

**What could go wrong:**

| Symptom | Likely cause |
|---|---|
| Only one short burst while holding | This game version doesn't send itemStartUse for this item. Report it; the item may need a use animation. |
| The beam keeps firing after you let go | itemStopUse didn't arrive. Switching items stops it; report it. |
| Lag while firing with several players | Lower `PIERCE` or raise `PARTICLE_STEP` at the top of `scripts/blaster.js`. |

## Mountain Seed

`scripts/mountain.js` handles it. Plant the seed and, after a few seconds of rumbling, a mountain rises out of that spot
one layer at a time. Every mountain is different.

- **The shape is a fractal** made with the *diamond-square* algorithm: big bumps, smaller bumps on those, and even
  smaller bumps on those. The outline is a wiggly fractal coastline too. The spot you planted is the highest peak.
- **Blocks:**
  - Outside, from the bottom up: grass and flowers, then moss and coarse dirt, then rock and gravel, then snow and ice
    on top. Steep cliffs are always bare rock.
  - Halfway up, just under the surface: stripes of coloured terracotta like a badlands mesa.
  - Inside: stone, andesite, diorite, granite, tuff and deepslate, with ores (coal, copper, iron, redstone, lapis,
    gold, emerald, and rare diamonds).
- **Size:** up to 65 blocks across and about 30–50 tall, roughly 15–20 thousand blocks. It takes about 15 seconds to grow.
- **It never breaks anything:** it only fills air, water, lava and plants, so houses stay put (they just end up inside
  the mountain). Creatures caught as it rises are lifted on top of it.

Crafting: 4 stone in a plus around wheat seeds.

1. Rebuild, exit to the menu and reopen the world. `/give @s mymod:mountain_seed`. Check the seed-with-a-mountain icon and the name **Mountain Seed**.
2. On flat open ground, step back about 40 blocks, aim at the ground (up to 8 blocks away, so walk up, plant, then run)
   and use it. Watch for rumbling, puffs and a little screen shake, then the mountain rising.
3. When it's done: "A mountain has grown!". Fly around it and check for snow on top, terracotta stripes on the sides
   and a fractal-looking outline.
4. Dig into it: you should find stone variants and some ores.
5. Plant two more: each should look different.
6. Plant one next to a small hut: the hut must not be broken.
7. Stand where it will grow: you get lifted up and don't suffocate.

**What could go wrong:**

| Symptom | Likely cause |
|---|---|
| Part of the mountain is missing (cut off flat) | That part was outside the loaded chunks. Stand closer. |
| It grows too slowly or too fast | Change `TICKS_PER_LAYER` in `mountain.js`. |
| Too big or too small | Change `PEAK` (height) or `GRID_POWER` (6 = 65 wide, 5 = 33 wide). |
| The game stutters while it grows | Increase `TICKS_PER_LAYER`, or set `GRID_POWER` to 5. |

## Vortex Guns

`scripts/vortex.js` handles both guns. They use the same vortex but pull different creatures:

- **Monster Vortex** (red swirl icon): only **hostile mobs**, like zombies, skeletons, creepers, spiders, slimes,
  phantoms and drowned. Tamed monsters count as pets and are left alone.
- **Animal Vortex** (green swirl icon): **everything else alive**: animals, villagers, pets and tamed monsters.
- **Players are never pulled.**

Use one and, for 5 seconds, every matching creature within 256 blocks is sucked towards you. Far-away creatures fly in
fast, near ones slower. Each one gets its own spot on a spiral around you, so they don't pile up. Use it again (or sneak +
use) to let go early.

- Only creatures in **loaded chunks** can be pulled. In practice that's your simulation distance (Settings > Simulation
  Distance), which on iPads is usually much less than 256 blocks.
- At most 100 creatures per shot, nearest first.

Crafting: iron, ender pearl, iron on top; iron, redstone block, iron below (Monster Vortex). Use wheat instead of the
ender pearl for the Animal Vortex.

1. Rebuild, exit to the menu and reopen the world. `/give @s mymod:vortex_gun` and `/give @s mymod:animal_vortex_gun`.
   Check the red and green swirl icons and the names **Monster Vortex** and **Animal Vortex**.
2. `/summon zombie ~30 ~ ~` and `/summon cow ~30 ~ ~5`. Monster Vortex: only the zombie comes. Animal Vortex: only the cow.
3. Near a field of animals, use the Animal Vortex: they spread out around you instead of piling up. No lag.
4. A tamed zombie (fed cake) is pulled by the Animal Vortex, not the Monster Vortex.
5. With a second player nearby: they are NOT pulled by either gun.
6. Use it, then again straight away: "Vortex off" and everything stops.
7. Content Log: no Molang errors about `portal_directional` or `portal_reverse`.

**What could go wrong:**

| Symptom | Likely cause |
|---|---|
| Creatures far away don't come | Their chunks aren't loaded. Raise Simulation Distance, or get closer. |
| Creatures get stuck behind walls | They're pulled in a straight line, with a little lift to hop fences. Tall walls stop them. |
| A hostile mob is pulled by the Animal Vortex | It isn't in the `monster` family. Report which mob. |
| The game lags | Lower `MAX_CREATURES` in `vortex.js`, and check the Content Log for errors repeating every frame. |

## Laser Blaster: beacon beam, and the Flame Blaster

`scripts/blaster.js` handles both blasters.

- **Laser Blaster:** the beam now looks like a beacon beam: a bright core inside a wide soft cyan glow, with sparkles
  spiralling around it. Otherwise it works the same: it burns through blocks and hurts and ignites creatures.
- **Flame Blaster** (new, orange barrel): hold use to fire an orange beam with flames along it. It **doesn't break
  blocks**. Wherever it lands it **sets fire**: in front of the block it hit, on top of it, and a few random spots
  around. Creatures in the beam take a little damage and burn for 10 s. Never you, your own pets or Morph Wand costumes.
  Fire spreads by itself (unless `/gamerule dofiretick false`), so careful near houses!

Crafting (Flame Blaster): blaze rod on top; fire charge, laser pointer, fire charge in the middle; glowstone at the bottom.

1. `/give @s mymod:laser_blaster` and hold use: thick glowing cyan beam with spiralling sparkles, still burning through blocks.
2. `/give @s mymod:flame_blaster` (orange barrel icon, name **Flame Blaster**). Hold use at grass: fire appears where it
   lands and around it. No blocks are broken.
3. Aim at a cow or zombie: it catches fire and keeps burning.
4. Aim at a wooden wall: it catches fire (fire in front of or on top of it) and spreads.
5. Aim at water: no fire, just the beam.
6. Content Log: no errors about `laser_glow` or `fire_beam`.

**What could go wrong:**

| Symptom | Likely cause |
|---|---|
| The Laser Blaster lags | Make `GLOW_STEP` and `SPARKLE_STEP` in `blaster.js` bigger (fewer particles). |
| Fire doesn't appear on walls | Fire needs a solid block under it. Aim at the floor in front of the wall, or at the top of it. |
| Fire goes out at once | Fire on non-flammable blocks (stone, dirt) burns out after a few seconds. That's normal. |

## Water Blaster and Ice Blaster

`scripts/blaster.js` handles them, like the other blasters (hold use to fire). They are the Flame Blaster's counters.

- **Water Blaster** (blue barrel): a blue jet with splashes. Where it lands (3 blocks around), it **puts out fire** and
  **cools lava**: still lava turns to obsidian, flowing lava to cobblestone. Creatures in the jet stop burning and get
  pushed back a little.
- **Ice Blaster** (pale icy barrel): an icy beam with snowflakes. Where it lands it **puts out fire**, **freezes water**
  (the top layer turns to ice), cools lava like the Water Blaster, and **lays snow** on the ground. Creatures in the beam
  stop burning, slow right down for 3 s, and take a small freezing hit.
- Neither one breaks blocks, and neither affects you, your own pets or Morph Wand costumes.

Crafting: like the Laser Blaster, but with a water bucket on top and 2 lapis lazuli at the sides (Water), or blue ice
on top and 2 snowballs at the sides (Ice).

1. `/give @s mymod:water_blaster` and `/give @s mymod:ice_blaster`. Check the blue and icy icons and the names.
2. Start a fire with the Flame Blaster, then hold the Water Blaster on it: the fire goes out with a fizz.
3. Do the same with the Ice Blaster: the fire goes out, and snow appears around the spot.
4. Aim the Ice Blaster at a pond: the surface turns to ice.
5. Aim either at a lava pool: still lava becomes obsidian, flowing lava becomes cobblestone.
6. Set a cow on fire with the Flame Blaster, then spray it: it stops burning. Ice: it slows right down.
7. Content Log: no errors about `water_beam` or `ice_beam`.

## Barf Blaster

`scripts/blaster.js` handles it, like the other blasters (hold use to fire).

- **Barf Blaster** (slimy green barrel): a green beam with little angry puffs. It doesn't change any blocks and does
  **no damage**. Anyone it hits (players and creatures) **throws up**: green-brown chunks fly out of their mouth and
  splat on the ground, with slimy sounds, for about 4 s after the last hit, then a burp. Players also get **nausea**
  (the screen wobbles, 10 s) and a little **hunger**.
- It never affects you, your own pets or Morph Wand costumes.

Crafting: like the Laser Blaster, but with a spider eye on top and 2 slime balls at the sides.

1. `/give @s mymod:barf_blaster`. Check the green icon and the name **Barf Blaster**.
2. Aim at a cow or villager: chunks come out of its mouth, in the direction it's looking, and fall to the ground.
3. Stop firing: it keeps throwing up for about 4 s, then burps and stops.
4. With a second player (or ask someone): hit them, their screen wobbles and their hunger bar drains a bit.
5. Content Log: no errors about `barf_beam` or `barf_spew`.

**What could go wrong:**

| Symptom | Likely cause |
|---|---|
| The chunks shoot straight up or stay still | `variable.direction` isn't reaching `barf_spew.particle.json`. Check the Content Log. |
| The chunks fall through the floor | Particle collision is off in some graphics modes. Harmless. |


## Mooshroom Drill

A digging vehicle with a real **mooshroom** on the front as its drill bit. `scripts/drill.js` does the digging; the
chassis model and its texture come from `tools/gen_mooshroom_drill.py`; the mooshroom is Minecraft's own model and
texture.

- **Put it down:** use the **Mooshroom Drill** item on the ground. It faces the way you're looking.
- **Get in:** use it (right-click / tap). **Get out:** sneak. **Pick it up:** sneak and hit it.
- **Dig:** hold forward. The mooshroom spins like a drill bit and a 5-wide, 5-tall tunnel opens in front of you,
  every tick, so you can drive straight through stone. Where you look decides the shape:
  - look level: a flat tunnel
  - look up: stairs going up
  - look down: stairs going down
  - look straight down: a shaft straight down
- **Ores** go straight into your inventory (coal, raw iron/copper/gold, redstone, lapis, diamonds, emeralds,
  nether gold and quartz, ancient debris). Everything else just disappears, so the tunnel doesn't fill with items.
- It never breaks bedrock, portals, command blocks or anything with an inventory (chests, furnaces...), and it
  leaves water and lava alone.
- **Nothing can hurt it**, the mooshroom included: swords, fire, lava, drowning, falling, explosions.
- While you drive it you get **night vision**, **fire resistance** and **water breathing**.

Crafting: red mushroom, diamond pickaxe, brown mushroom over iron block, minecart, iron block.

### Test steps

1. `/give @s mymod:mooshroom_drill`. Check the icon (a red-and-white mooshroom in front of a yellow digger) and the
   name **Mooshroom Drill**.
2. Use it on the ground: a yellow tracked digger appears with a mooshroom on the front, mushrooms on its back and
   head, facing away from you. It moos.
3. Hit it with a sword (not sneaking): no damage, no red flash. It moos and tells you how to pick it up.
4. Get in. You should sit on the seat at the back, behind the mooshroom. If you float above it or sink into it,
   change the seat `position` in `big_cat_bp/entities/mooshroom_drill_vehicle.json`.
5. Without pressing anything, look around: nothing gets dug and the mooshroom only wobbles gently.
6. Drive into a hill, looking level: the mooshroom spins fast and a 5x5 tunnel opens in front of you. You drive
   straight through without slowing down. Stone sounds and mycelium specks at the front.
7. Look down while driving: stairs going down. Look straight down: a shaft. Look up: stairs going up (it climbs one
   block at a time).
8. Dig through some ores: you hear an XP "ding" and the raw ores, diamonds, etc. land in your inventory.
9. Dig next to a chest and into bedrock: the chest and the bedrock stay.
10. Drive into lava and water: the drill is fine and so are you (fire resistance, water breathing).
11. Get out (sneak): the mooshroom stops spinning. Sneak and hit it: it disappears and the item comes back (in
    Survival; in Creative the item isn't used up in the first place).
12. Content Log: no errors about `mooshroom_drill`.

**What could go wrong:**

| Symptom | Likely cause |
|---|---|
| The drill doesn't move when you press forward | The game didn't accept `minecraft:input_ground_controlled` for this entity. Check the Content Log. |
| It digs while you sit still and look around | `player.inputInfo` isn't available on this game version, so the script falls back to "always dig while ridden". |
| The mooshroom spins but its mushrooms don't, or the mushrooms float next to it | The vanilla mooshroom model changed its `body` / `head` pivots. Update `BODY_PIVOT` / `HEAD_PIVOT` in `tools/gen_mooshroom_drill.py`. |
| The mooshroom has no mushrooms at all | Our chassis model didn't load. Check the Content Log for `geometry.mymod.mooshroom_drill`. |
| It gets stuck on the step when going up | Step height (`minecraft:variable_max_auto_step`) wasn't accepted; look down a little and back up. |

## Portal Pads

Flat glowing pads. Step on one and you come out on top of its partner: **pads of the same colour are linked**.
`scripts/portal.js` does the linking and teleporting; the block and its 16 colour textures come from
`tools/gen_portal.py`.

- Every new pad is **purple**, so any two pads you put down are linked straight away.
- **Use a dye on a pad** to change its colour: two red pads link to each other, two blue pads link to each other,
  and so on (16 colours, one per dye; ink sac, lapis, cocoa beans and bone meal work too). In Survival it uses up
  the dye.
- **Use a pad with an empty hand** to see where it goes.
- With **three or more** pads of one colour, they go round in a loop in the order you placed them.
- Works over any distance, even into chunks nobody is in, and between the Overworld, the Nether and the End.
- Players and creatures (mobs, animals, Big Cats) travel. Items, arrows, vehicles and bosses don't. Creatures only
  travel to places that are loaded (near a player).
- When you arrive you have to **step off and back on** to go back.
- Explosions can't break pads; pick one up by breaking it.

Crafting: obsidian, ender pearl, obsidian in a row. Makes 2.

### Test steps

1. `/give @s mymod:portal_pad 4`. Check the icon (a purple swirl pad) and the name **Portal Pad**.
2. Put one down. It glows and swirls purple, and the action bar says to place another one.
3. Walk about 50 blocks away and put the second one down: "linked!". Step on it: whoosh, you're on the first pad,
   with purple sparkles at both ends.
4. Stand still on the pad you arrived on: nothing happens. Step off and back on: you go back.
5. Use a red dye on both pads: they turn red and still link to each other. A third, purple pad: "not linked yet".
6. Put a third red pad down. Step on pad 1 → pad 2 → pad 3 → pad 1 (a loop).
7. Lead a cow (or push a mob) onto a pad: it travels too. Drop an item on it: the item stays.
8. Put one pad in the Overworld and one in the Nether (same colour): you travel between the dimensions.
9. Walk far away from both pads (so their chunks unload), save and quit, reopen, then go back to one: it still
   takes you to the other.
10. Break a pad, then step on its old partner: "No other ... portal pad yet".
11. Content Log: no errors about `portal_pad` or `portal_swirl`.

**What could go wrong:**

| Symptom | Likely cause |
|---|---|
| The pad is invisible or a purple/black checkerboard | A texture is missing from `terrain_texture.json`; rebuild. |
| Dye does nothing | The game ignored the block's `mymod:color` state. Check the Content Log for `portal_pad`. |
| You bounce back and forth | The "step off first" check isn't working; tell me what you were standing on. |
| The swirl particles are white | `variable.pr/pg/pb` aren't reaching `portal_swirl.particle.json`. Harmless. |
