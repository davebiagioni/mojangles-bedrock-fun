# Bedrock add-ons

Two Minecraft: Bedrock Edition add-ons, built with Python scripts.

| Folder | What it is |
|---|---|
| [`bigcat/`](bigcat/) | **Big Cat**: a giant, tameable cat with 200 generated coats, plus a **laser pointer** that cats chase, orbs, tameable monsters, and wands that make players **mini or huge** or give them **rainbow or stinky vapor**, a **grappling gun** that pulls you to blocks or pulls mobs to you, **Evolution Stones** (dropped by ores) that evolve cats through 8 stages until they grow wings and fly, a **net trap** that holds whatever walks onto it, and a **Drowned Trap** that blows up drowned for enchanted weapons. |
| [`gear/`](gear/) | **Amethyst armor**: a full armor set with a set bonus, plus **geode goggles** that give night vision. |

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
