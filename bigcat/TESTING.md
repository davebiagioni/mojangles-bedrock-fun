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
| "The cat slipped away" every time | The cat can't be moved to the safe spot above it. Report it with the Content Log. |
| "The orb fizzled" | Saving the cat failed. The Content Log shows `[bigcat orb] capture failed: …`. |
| Releasing says "Its cat could not be found" | The saved cat was deleted, for example by `/structure delete`. The orb resets to empty. |
| Nothing happens when right-clicking the cat | The click-on-cat event didn't fire. Aim at the cat and use the orb instead, and tell me. |
