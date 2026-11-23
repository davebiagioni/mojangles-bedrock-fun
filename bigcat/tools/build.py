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
from deploy_dev import deploy
from fetch_vanilla import fetch_vanilla
from gen_air_cannon import generate_air_cannon_textures
from gen_atomic_bomb import generate_atomic_bomb_textures
from gen_blaster import generate_blaster_texture
from gen_drowned_trap import generate_drowned_trap
from gen_evolution import generate_evolution_textures
from gen_grapple import generate_grapple_textures
from gen_json import generate_json
from gen_laser import generate_laser_textures
from gen_mooshroom_drill import generate_mooshroom_drill
from gen_morph import generate_morph
from gen_mountain import generate_mountain_texture
from gen_net import generate_net_textures
from gen_orb import generate_orb_textures
from gen_player import generate_player
from gen_portal import generate_portal
from gen_tame import generate_tame
from gen_vortex import generate_vortex_texture
from gen_wand import generate_wand_textures
from package import bump_versions, make_mcaddon
from validate import validate


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package", action="store_true", help="bump version and build dist/*.mcaddon")
    ap.add_argument("--no-deploy", action="store_true", help="don't copy packs into Minecraft")
    args = ap.parse_args()
    t0 = time.time()
    steps = [
        ("fetch Mojang files", fetch_vanilla),
        ("generate coats", build_coats),
        ("generate JSON", generate_json),
        ("generate laser textures", generate_laser_textures),
        ("generate orb textures", generate_orb_textures),
        ("make monsters tameable", generate_tame),
        ("generate wand textures", generate_wand_textures),
        ("generate grappling gun textures", generate_grapple_textures),
        ("drowned trap: patch drowned + textures", generate_drowned_trap),
        ("generate evolution stone textures", generate_evolution_textures),
        ("generate net trap textures", generate_net_textures),
        ("generate morph wand costume", generate_morph),
        ("generate air cannon texture", generate_air_cannon_textures),
        ("generate atomic bomb textures", generate_atomic_bomb_textures),
        ("generate laser blaster texture", generate_blaster_texture),
        ("generate mountain seed texture", generate_mountain_texture),
        ("generate vortex gun texture", generate_vortex_texture),
        ("generate mooshroom drill model + textures", generate_mooshroom_drill),
        ("generate portal pad block + textures", generate_portal),
        ("add player sizes", generate_player),
        ("validate", validate),
    ]
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
