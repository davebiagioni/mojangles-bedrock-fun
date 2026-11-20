# Hand-painted coat layers

Paint a pattern, save it here as a PNG, and run `python tools/build.py`. About 30% of the coats will get one of the layers in this folder painted over them. You can change that share with `coat_layers.chance` in `tools/coats_config.json`.

## How to paint one

1. Run the build once. Then open `build/uv_template.png` (1024×512) in a paint program. It's the cat's skin unfolded flat, with each part labelled, such as "body front" (the belly), "head front" (the face) and "frontLegL side".
2. Add a **new transparent layer** on top and paint on it. Anything you leave transparent keeps the generated coat.
3. Hide the template and save **only your layer** as a PNG in this folder. It must be 1024×512, 64×32, or another exact multiple of 64×32.
4. Rebuild and look at `build/coat_preview.png`. Coats that used a layer have a `+` after their name.

## Notes

- The eyes, nose and inner ears are never painted over.
- The left and right legs share the same picture, so whatever you paint on one leg shows on both.
- Files whose names start with `_` are ignored, which is handy for works in progress.
- Adding or removing a layer only changes the coats that use layers. The other coats stay the same.
