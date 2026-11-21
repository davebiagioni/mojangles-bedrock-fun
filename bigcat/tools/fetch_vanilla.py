"""Copy the Mojang files this add-on builds from out of a local bedrock-samples checkout.

Mojang's files are not stored in this repo (Minecraft EULA: a mod must not contain a
substantial part of Mojang's content). Instead, each build copies the few files it needs
from https://github.com/Mojang/bedrock-samples into ./vanilla/ (gitignored).

Samples location: %MC_SAMPLES% if set, else ../bedrock-samples next to this project's folder.
Get it once with:
    git clone --depth 1 --branch v1.26.60.5 https://github.com/Mojang/bedrock-samples ../bedrock-samples

Run standalone:  python tools/fetch_vanilla.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from common import ROOT, BuildError

LIST = ROOT / "tools" / "vanilla_files.json"
DEST = ROOT / "vanilla"


def samples_dir() -> Path:
    p = Path(os.environ["MC_SAMPLES"]) if os.environ.get("MC_SAMPLES") else ROOT.parent / "bedrock-samples"
    if not (p / "resource_pack").is_dir():
        raise BuildError(
            f"Mojang bedrock-samples not found at {p}.\n  Clone it with:\n    git clone --depth 1 "
            f'--branch v1.26.60.5 https://github.com/Mojang/bedrock-samples "{p}"\n'
            f"  or set MC_SAMPLES to an existing checkout."
        )
    return p


def fetch_vanilla() -> None:
    src_root = samples_dir()
    files = json.loads(LIST.read_text(encoding="utf-8"))
    for dest_name, src_rel in files.items():
        src = src_root / src_rel
        if not src.is_file():
            raise BuildError(f"{src_rel} is missing from {src_root} (is the checkout an older version?)")
        dest = DEST / dest_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    print(f"  {len(files)} files from {src_root} -> vanilla/")


if __name__ == "__main__":
    try:
        fetch_vanilla()
    except BuildError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
