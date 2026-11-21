"""Bump the pack versions and zip both packs into dist/<addon_name>.mcaddon.

The patch number of header.version (and module versions, and the BP's dependency on
the RP) goes up by one each time, so an iPad that already has the add-on accepts the
new file as an update.

Run standalone:  python tools/package.py          (bump + zip)
                 python tools/package.py --no-bump
"""

from __future__ import annotations

import sys
import zipfile

from common import BuildError, load_config, load_json, rel, write_json

SKIP_NAMES = {"Thumbs.db", ".DS_Store", "desktop.ini"}


def bump_versions() -> list[int]:
    _cfg, paths = load_config()
    bp_path, rp_path = paths.bp / "manifest.json", paths.rp / "manifest.json"
    bp, rp = load_json(bp_path), load_json(rp_path)
    cur = max(tuple(bp["header"]["version"]), tuple(rp["header"]["version"]))
    new = [cur[0], cur[1], cur[2] + 1]
    for m in (bp, rp):
        m["header"]["version"] = list(new)
        for mod in m.get("modules", []):
            mod["version"] = list(new)
    rp_uuid = rp["header"]["uuid"]
    hit = False
    for dep in bp.get("dependencies", []):
        if dep.get("uuid") == rp_uuid:
            dep["version"] = list(new)
            hit = True
    if not hit:
        raise BuildError("BP manifest has no dependency on the RP; cannot bump it")
    write_json(bp_path, bp)
    write_json(rp_path, rp)
    print(f"  version {'.'.join(map(str, cur))} -> {'.'.join(map(str, new))} (both manifests + dependency)")
    return new


def make_mcaddon() -> None:
    cfg, paths = load_config()
    version = ".".join(map(str, load_json(paths.bp / "manifest.json")["header"]["version"]))
    paths.dist.mkdir(parents=True, exist_ok=True)
    out = paths.dist / f"{cfg['entity']['addon_name']}.mcaddon"
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for pack in (paths.bp, paths.rp):
            for f in sorted(pack.rglob("*")):
                if f.is_file() and f.name not in SKIP_NAMES:
                    # forward slashes, pack folder at the top level: works on iPad and Windows
                    z.write(f, f"{pack.name}/{f.relative_to(pack).as_posix()}")
                    count += 1
    print(f"  packaged {count} files -> {rel(out)}  (v{version}, {out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    try:
        if "--no-bump" not in sys.argv:
            bump_versions()
        make_mcaddon()
    except BuildError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
