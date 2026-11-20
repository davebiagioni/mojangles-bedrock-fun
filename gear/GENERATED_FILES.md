# Generated files - do not edit by hand

`python tools/build.py` overwrites everything listed here. Minecraft rejects extra
fields in pack JSON, so this list is the "generated" marker instead.

| File | Edit this instead |
|---|---|
| `gear_bp/items/*.json` | `tools/gear_config.json` (`pieces`, `material`), `tools/gen_json.py` |
| `gear_bp/recipes/*.json` | `recipe` of each piece in `tools/gear_config.json` |
| `gear_rp/attachables/*.json` (2 per item: generic + `.player`) | `kinds` in `tools/gear_config.json`, `tools/gen_json.py` |
| `gear_rp/textures/item_texture.json` | `tools/gen_json.py` |
| `gear_rp/texts/en_US.lang`, `gear_rp/texts/languages.json` | piece `name`s in `tools/gear_config.json`; script messages in `tools/gen_json.py` |
| `gear_rp/textures/gear/armor/*.png` (64x32 armor layers) | `palette` / `layers` in `tools/gear_config.json`, `tools/gen_textures.py` |
| `gear_rp/textures/gear/items/*.png` (16x16 icons) | `palette` + piece `icon_source` in `tools/gear_config.json`, `tools/gen_textures.py` |
| `gear_bp/pack_icon.png`, `gear_rp/pack_icon.png` | `tools/gen_textures.py` |
| `build/armor_preview.png` | (preview only, not shipped) |
| `gear_bp/manifest.json`, `gear_rp/manifest.json` - version only | bumped by `python tools/build.py --package` |

## Hand-written source files

- `gear_bp/scripts/main.js`: set bonus and goggles logic (`@minecraft/server` 2.11.0).
- `gear_bp/manifest.json`, `gear_rp/manifest.json`: everything except the version numbers.
- `tools/*.py`, `tools/gear_config.json`.
- `vanilla/*`: copied from bedrock-samples at build time by `tools/fetch_vanilla.py` (list in `tools/vanilla_files.json`). Not committed.
  (`diamond_1.png`, `diamond_2.png` from `resource_pack/textures/models/armor/`, and
  `diamond_helmet/chestplate/leggings/boots.png`, `amethyst_shard.png` from
  `resource_pack/textures/items/` in Mojang's bedrock-samples). They're © Mojang and subject to the Minecraft EULA.
