# Bedrock add-ons

Two Minecraft: Bedrock Edition add-ons, built with Python scripts.

| Folder | What it is |
|---|---|
| [`bigcat/`](bigcat/) | **Big Cat**: a giant, tameable cat with 200 generated coats, plus gadgets: blasters, wands, traps, a digging vehicle and teleport pads (list below). |
| [`gear/`](gear/) | **Amethyst armor**: a full armor set with a set bonus, plus **geode goggles** that give night vision. |

### What's in Big Cat

- **Cats:** the **Big Cat** itself; a **Laser Pointer** that cats chase; **Evolution Stones** (dropped by ores) that
  evolve a cat through 8 stages until it grows wings and flies.
- **Catching things:** **Cat Orb**, **Creature Orb** and **Player Trap Orb**; a **Net Trap** that holds whatever walks
  onto it; a **Drowned Trap** that blows up drowned for enchanted weapons; tameable zombies, skeletons and creepers.
- **Wands:** **Size Wand** (mini or huge), **Vapor Wand** (rainbow or stinky clouds), **Morph Wand** (turn into
  8 creatures, each with a perk).
- **Blasters and guns:** **Laser Blaster** (burns through blocks), **Flame Blaster**, **Water** and **Ice Blasters**
  (put fires out), **Barf Blaster** (makes whoever it hits throw up), **Air Cannon** (blasts things super far),
  **Grappling Gun**, and **Monster / Animal Vortex Guns** that pull creatures to you from far away.
- **Big stuff:** an **Atomic Bomb** with a crater and a mushroom cloud; a **Mountain Seed** that grows a fractal
  mountain.
- **Getting around:** the **Mooshroom Drill**, a vehicle with a spinning mooshroom as its drill bit that digs tunnels
  super fast; **Portal Pads**: place two of the same colour and step on one to teleport to the other.

Each folder has a `TESTING.md` with the full test steps.

## Setup (Windows)

1. Install Python 3.12+ and [uv](https://docs.astral.sh/uv/), then create the environment (Pillow, pytest, ruff):
   ```
   uv sync
   ```
2. Clone Mojang's samples next to the add-on folders. The build copies the few vanilla files it needs from there:
   ```
   git clone --depth 1 --branch v1.26.60.5 https://github.com/Mojang/bedrock-samples
   ```
   To use a checkout somewhere else, set `MC_SAMPLES` to its path.
3. Build and deploy to Minecraft's development packs:
   ```
   uv run python bigcat/tools/build.py
   uv run python gear/tools/build.py
   ```
   Add `--package` to also build an `.mcaddon` in `dist/`, or `--no-deploy` to skip copying into Minecraft.

## Tests and linting

```
uv run pytest                 # tests for both projects (bigcat/tests, gear/tests)
uv run ruff check             # lint
uv run ruff format            # format (CI-style check: uv run ruff format --check)
```

Tests don't need Minecraft. Tests that read the real `bedrock-samples` or `vanilla/` files skip when those are missing.

## Mojang content

This repo contains no Mojang files. Every build copies the vanilla files it uses (models and textures) from your local
`bedrock-samples` checkout into a gitignored `vanilla/` folder. Each project lists them in `tools/vanilla_files.json`.
Textures generated from vanilla textures, such as the cat coats and the recolored armor, are also gitignored and
rebuilt locally.

NOT AN OFFICIAL MINECRAFT PRODUCT. NOT APPROVED BY OR ASSOCIATED WITH MOJANG OR MICROSOFT.

## Due diligence

On 2026-11-19 we checked this repository against the Minecraft EULA [1] and the Minecraft Usage Guidelines [2].
To the best of our understanding, nothing in it violates their terms. This is not legal advice.

| Rule | How this repo follows it |
|---|---|
| A mod must not contain a substantial part of Mojang's code or content, and you may not distribute Mojang's content [1][3] | No Mojang files are committed. Builds copy vanilla files from your own clone of Mojang's samples into the gitignored `vanilla/` folder. Textures generated from them are gitignored too. |
| Mojang's sample files are covered by the EULA [4] | This repo doesn't contain or redistribute them. You clone them yourself from Mojang. |
| Mods must be free [5] | Free, with no monetization. |
| You must not suggest Mojang made or endorses the project [6] | The disclaimer above says it isn't official. |

This check covers the files in this repo. It does not cover `.mcaddon` packages you build locally: those include
textures generated from vanilla art, so check the same rules before sharing one.

minecraft.net timed out when we tried to load it. The rules above were checked against third-party copies that quote
the official text [3][5][6].

1. Minecraft EULA: https://www.minecraft.net/en-us/eula
2. Minecraft Usage Guidelines: https://www.minecraft.net/en-us/usage-guidelines
3. "Mods must not include substantial copyrightable game code": https://conductatlas.com/platform/minecraft/minecraft-usage-guidelines/provision/CA-P-025379/mods-must-not-include-substantial-copyrightable-game-code/
4. Mojang/bedrock-samples license: https://github.com/Mojang/bedrock-samples/blob/main/LICENSE.md
5. Mod and fan creation rules: https://conductatlas.com/platform/minecraft/minecraft-usage-guidelines/mod-and-fan-creation-rules/
6. No implied endorsement: https://conductatlas.com/platform/minecraft/minecraft-usage-guidelines/no-implied-endorsement-restriction/
