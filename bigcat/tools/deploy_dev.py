"""Copy the packs into Minecraft Bedrock's development pack folders (Windows).

Looks for com.mojang in, in order:
  1. %BIGCAT_COM_MOJANG%                      (manual override)
  2. %APPDATA%\\Minecraft Bedrock\\Users\\Shared\\games\\com.mojang          (newer installs)
  3. %LOCALAPPDATA%\\Packages\\Microsoft.MinecraftUWP_8wekyb3d8bbwe\\LocalState\\games\\com.mojang  (older)

Run standalone:  python tools/deploy_dev.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from common import BuildError, load_config, load_json, rel


def candidates() -> list[tuple[str, Path]]:
    out = []
    if os.environ.get("BIGCAT_COM_MOJANG"):
        out.append(("BIGCAT_COM_MOJANG", Path(os.environ["BIGCAT_COM_MOJANG"])))
    if os.environ.get("APPDATA"):
        out.append(("newer install (APPDATA)",
                    Path(os.environ["APPDATA"]) / "Minecraft Bedrock" / "Users" / "Shared" / "games" / "com.mojang"))
    if os.environ.get("LOCALAPPDATA"):
        out.append(("older UWP install (LOCALAPPDATA)",
                    Path(os.environ["LOCALAPPDATA"]) / "Packages" / "Microsoft.MinecraftUWP_8wekyb3d8bbwe"
                    / "LocalState" / "games" / "com.mojang"))
    return out


def find_com_mojang() -> Path:
    found = [(label, p) for label, p in candidates() if p.is_dir()]
    if not found:
        tried = "\n    ".join(str(p) for _, p in candidates())
        raise BuildError("could not find Minecraft's com.mojang folder. Tried:\n    " + tried +
                         "\n  Launch Minecraft once, or set BIGCAT_COM_MOJANG to the folder.")
    label, path = found[0]
    print(f"  com.mojang: {path}  [{label}]")
    for other_label, other in found[1:]:
        print(f"  note: another com.mojang also exists ({other_label}): {other} - not used")
    return path


def warn_imported_copies(com_mojang: Path, uuids: dict[str, str]) -> None:
    """An imported (non-development) copy with the same UUID can shadow the dev copy."""
    for folder in ("behavior_packs", "resource_packs"):
        root = com_mojang / folder
        if not root.is_dir():
            continue
        for mf in root.glob("*/manifest.json"):
            try:
                u = json.loads(mf.read_text(encoding="utf-8-sig"))["header"]["uuid"]
            except (OSError, ValueError, KeyError):
                continue
            if u in uuids:
                print(f"  WARNING: an imported copy of {uuids[u]} is in {mf.parent}. Minecraft may load it "
                      f"instead of the development copy. Delete it (Settings > Storage) if changes don't show.")


def deploy() -> None:
    cfg, paths = load_config()
    com = find_com_mojang()
    uuids = {}
    for pack, dest_folder in ((paths.bp, "development_behavior_packs"), (paths.rp, "development_resource_packs")):
        m = load_json(pack / "manifest.json")
        uuids[m["header"]["uuid"]] = pack.name
        dest = com / dest_folder / pack.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(pack, dest)
        print(f"  {rel(pack)} -> {dest}  (v{'.'.join(map(str, m['header']['version']))})")
    warn_imported_copies(com, uuids)


if __name__ == "__main__":
    try:
        deploy()
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
