# Testing the Gear add-on (Amethyst armor + Geode Goggles)

Most files under `gear_bp/` and `gear_rp/` are **generated**, so don't edit them by hand (see `GENERATED_FILES.md`). To change:
- **stats, recipes, names, colours**: edit `tools/gear_config.json`.
- **set bonus / goggles behaviour**: edit `gear_bp/scripts/main.js`. It's hand-written.

Then rebuild.

## What's in it

| Item | Slot | Armor points | Durability | Recipe (S = amethyst shard, I = iron ingot, T = tinted glass) |
|---|---|---|---|---|
| `gear:amethyst_helmet` | head | 2 | 264 | `SIS / S S` |
| `gear:amethyst_chestplate` | chest | 7 | 384 | `S S / SIS / SSS` |
| `gear:amethyst_leggings` | legs | 5 | 360 | `SIS / S S / S S` |
| `gear:amethyst_boots` | feet | 2 | 312 | `I I / S S` |
| `gear:geode_goggles` | head | 2 | 264 | `SIS / T T` |

For comparison, iron is 15 armor points in total, amethyst is 16 and diamond is 20 (plus toughness). Durability sits between iron (x15) and diamond (x33) at x24. Enchantability is 15. All pieces repair at an anvil with amethyst shards (25% per shard) or with a second copy of the same piece.

- **Stats**: protection 5 / 10 / 8 / 5 (28 total; vanilla netherite is 20), durability 4000 / 6000 / 5500 / 4500, enchantability 30. Geode Goggles: protection 5, durability 4000.
- **Auto-enchanted**: every piece in your inventory or armor slots gets the best vanilla enchantments at max level within a second, and shows the enchantment glint. All pieces: Protection IV, Unbreaking III, Mending, Thorns III. Helmet and goggles also get Respiration III and Aqua Affinity; leggings get Swift Sneak III; boots get Feather Falling IV, Depth Strider III and Soul Speed III. Removed enchantments come back.
- **Set bonus** (all four amethyst pieces, "OVERPOWERED"): Resistance III, Strength II, Speed II, Haste II, Regeneration II, Jump Boost I, Fire Resistance and Water Breathing, refreshed every second. When the set completes you get a chime, sparkles and the actionbar message *"Amethyst set bonus: OVERPOWERED"*. When you take a piece off you get a lower chime and *"Amethyst set bonus lost"*, and the effects are removed.
- **Purple flames**: while the full set is worn, small purple flames flicker up around your legs, body and feet (about 30 a second). They stop when the set bonus ends. The particle is `gear_rp/particles/amethyst_flame.particle.json`, which tints vanilla's white flame sprite from pale pink to deep purple.
- **Geode Goggles**: Night Vision and Water Breathing while worn, with the actionbar message *"Geode Goggles: Night Vision + Water Breathing"*. The effects are removed when you take them off. The goggles take the helmet slot, so they can't be combined with the set bonus.

## One-time setup (Windows)

1. Install Python 3.12+ and Pillow: `pip install pillow`. Both are already installed on this PC. Nothing else is needed: the JSON-schema checker is built in.
2. The build reads Mojang's `bedrock-samples` checkout for schemas and API metadata. By default it uses `C:\mc\bigcat\bedrock-samples` (read-only). Set `GEAR_SAMPLES` to use another checkout.
3. In Minecraft, go to **Settings > Creator** and turn on **Content Log File** and **Content Log GUI**.
4. Create a test world:
   - **Creative**, **Cheats on**, **Flat**.
   - No experiments are needed. `@minecraft/server` 2.11.0 is stable.
5. In the world settings, activate **OP Gear** under **Behavior Packs**. **OP Gear Resources** attaches automatically as a dependency.

## Every iteration

1. Run `python tools/build.py`. It generates the textures and JSON, validates them (including the Mojang item schemas and the script's API names), and copies `gear_bp` / `gear_rp` into `development_behavior_packs` / `development_resource_packs`.
   - Check `build/armor_preview.png` first. It shows every icon and armor layer without launching the game.
2. Fully exit the world and reopen it. Item, attachable and texture changes aren't picked up live. For script-only changes, `/reload` is enough.

## `/give` commands

```
/give @s gear:amethyst_helmet
/give @s gear:amethyst_chestplate
/give @s gear:amethyst_leggings
/give @s gear:amethyst_boots
/give @s gear:geode_goggles
/give @s amethyst_shard 64
/give @s iron_ingot 16
/give @s tinted_glass 4
/give @s anvil
/give @s crafting_table
/give @s enchanting_table
/give @s armor_stand
```

The items are also in the creative inventory under **Equipment**, in the helmet, chestplate, leggings and boots groups.

## What to check

1. **Names and icons:** each item shows its English name ("Amethyst Helmet" and so on) and a purple icon. There's no purple/black checkerboard and no `item.gear:...` raw key.
2. **Wearing:** each piece goes only into its own armor slot, both by shift-click and by right-clicking with it in hand. The armor bar goes up by 2/7/5/2 (16 in total for the full set).
3. **On-body rendering** (third person, F5):
   - Each piece renders purple on the player, correctly aligned (same shape as vanilla diamond armor).
   - It's not doubled, and no vanilla layer shows through.
   - It moves with the arms and legs when walking or sneaking.
   - Put the pieces on an **armor stand**: they should render there too (that uses the generic, non-`.player` attachable).
   - Check the goggles: there's a dark band with two lilac lenses over the eyes and a strap around the head.
4. **Enchanting:**
   - The enchanting table offers armor enchantments (Protection, plus Respiration/Aqua Affinity on helmets, Feather Falling/Depth Strider on boots, Swift Sneak on leggings).
   - Enchanted books apply at an anvil.
   - Enchanted pieces show the glint both in the inventory and on the body.
5. **Durability and repair:**
   - Take damage (for example `/damage @s 5`, or let a zombie hit you in survival) and check that the durability bar drops.
   - At an anvil, damaged piece + amethyst shards repairs 25% per shard.
   - Two damaged pieces combine.
6. **Crafting:** the recipes in the table above work in a crafting table. In survival, they unlock in the recipe book once you pick up an amethyst shard.
7. **Set bonus:**
   - Put on all four pieces. Within about 1 second you should get the actionbar message, a chime, green sparkles and a small totem burst, and all eight effects in the inventory effects list (shown without particles).
   - Remove one piece. You should get *"Amethyst set bonus lost"* and a lower chime, and the effects should disappear within a second or two.
   - Re-equip the piece: the message appears again, once, not every second.
   - Give yourself a stronger effect (`/effect @s resistance 60 3`, Resistance IV) while wearing the set. It shouldn't be downgraded or removed.
8. **Goggles:**
   - Wear the goggles at night or in a cave. Night Vision should start within 1 second and show no flicker over a few minutes.
   - Take them off: Night Vision ends, with the message *"Geode Goggles removed"*.
   - A real Night Vision potion (8 minutes) isn't removed when you take the goggles off.
9. **Content Log:** there should be no errors or warnings mentioning `gear`. Script errors are logged with the prefix `[gear]`.

## Packaging (optional)

`python tools/build.py --package` bumps the patch version in both manifests and the BP's dependency on the RP, re-validates, deploys, and writes `dist/gear.mcaddon`. Commit the bumped manifests afterwards. `python tools/package.py --no-bump` only zips.

## Useful commands

| Command | What it does |
|---|---|
| `python tools/build.py` | Generate, validate and deploy |
| `python tools/build.py --no-deploy` | Generate and validate only |
| `python tools/build.py --package` | The same as `build.py`, plus a version bump and `dist/gear.mcaddon` |
| `python tools/gen_textures.py` | Textures and preview only |
| `python tools/validate.py` | Validation only |
| `python tools/deploy_dev.py` | Copy the packs into Minecraft only |

Set `GEAR_COM_MOJANG` to override the detected `com.mojang` folder. The deploy step only ever replaces `development_behavior_packs/gear_bp` and `development_resource_packs/gear_rp`.
