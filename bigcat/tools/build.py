"""One command for everything:

    python tools/build.py               generate coats + JSON -> validate -> deploy to Minecraft
    python tools/build.py --package     ... and bump the version and write dist/big_cat.mcaddon
    python tools/build.py --no-deploy   skip copying into Minecraft (e.g. on a machine without it)
"""
from __future__ import annotations

import argparse
import sys
import time

from build_coats import build_coats
from common import BuildError
from fetch_vanilla import fetch_vanilla
from deploy_dev import deploy
from gen_json import generate_json
from gen_laser import generate_laser_textures
from gen_orb import generate_orb_textures
from package import bump_versions, make_mcaddon
from validate import validate


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package", action="store_true", help="bump version and build dist/*.mcaddon")
    ap.add_argument("--no-deploy", action="store_true", help="don't copy packs into Minecraft")
    args = ap.parse_args()
    t0 = time.time()
    steps = [("fetch Mojang files", fetch_vanilla), ("generate coats", build_coats), ("generate JSON", generate_json),
             ("generate laser textures", generate_laser_textures), ("generate orb textures", generate_orb_textures), ("validate", validate)]
    if args.package:
        steps += [("bump version", bump_versions), ("re-validate", validate)]
    if not args.no_deploy:
        steps.append(("deploy to Minecraft", deploy))
    if args.package:
        steps.append(("package .mcaddon", make_mcaddon))
    try:
        for i, (name, fn) in enumerate(steps, 1):
            print(f"[{i}/{len(steps)}] {name}")
            fn()
    except BuildError as e:
        print(f"\nBUILD FAILED: {e}", file=sys.stderr)
        return 1
    print(f"done in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
