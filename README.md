# Bedrock add-ons

Two Minecraft: Bedrock Edition add-ons, built with Python scripts.

| Folder | What it is |
|---|---|
| [`bigcat/`](bigcat/) | **Big Cat**: a giant, tameable cat with 200 generated coats, plus a **laser pointer** that cats chase. |
| [`gear/`](gear/) | **Amethyst armor**: a full armor set with a set bonus, plus **geode goggles** that give night vision. |

Each folder has a `TESTING.md` with the full test steps.

## Setup (Windows)

1. Install Python 3.12+ and Pillow: `pip install pillow`.
2. Clone Mojang's samples next to the add-on folders. The build copies the few vanilla files it needs from there:
   ```
   git clone --depth 1 --branch v1.26.60.5 https://github.com/Mojang/bedrock-samples
   ```
   To use a checkout somewhere else, set `MC_SAMPLES` to its path.
3. Build and deploy to Minecraft's development packs:
   ```
   python bigcat/tools/build.py
   python gear/tools/build.py
   ```
   Add `--package` to also build an `.mcaddon` in `dist/`.

## Mojang content

This repo contains no Mojang files. Every build copies the vanilla files it uses (models and textures) from your local
`bedrock-samples` checkout into a gitignored `vanilla/` folder. Each project lists them in `tools/vanilla_files.json`.
Textures generated from vanilla textures, such as the cat coats and the recolored armor, are also gitignored and
rebuilt locally.

NOT AN OFFICIAL MINECRAFT PRODUCT. NOT APPROVED BY OR ASSOCIATED WITH MOJANG OR MICROSOFT.
