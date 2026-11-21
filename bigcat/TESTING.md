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
