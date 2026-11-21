"""package.py: version bumping and the .mcaddon zip (all inside tmp_path)."""

from __future__ import annotations

import zipfile

import pytest

import common
import package
from common import BuildError


def _versions(p):
    bp = common.load_json(p.bp / "manifest.json")
    rp = common.load_json(p.rp / "manifest.json")
    return bp, rp


def _set_version(path, v):
    m = common.load_json(path)
    m["header"]["version"] = v
    common.write_json(path, m)


def test_bump_versions_bumps_everything(raw_project, capsys):
    bp, _rp = _versions(raw_project)
    old = bp["header"]["version"]
    new = package.bump_versions()
    assert new == [old[0], old[1], old[2] + 1]
    bp, rp = _versions(raw_project)
    for m in (bp, rp):
        assert m["header"]["version"] == new
        assert all(mod["version"] == new for mod in m["modules"])
    deps = {d.get("uuid"): d["version"] for d in bp["dependencies"]}
    assert deps[rp["header"]["uuid"]] == new
    assert deps[None] == "2.11.0"  # the @minecraft/server dependency is left alone
    assert f"-> {'.'.join(map(str, new))}" in capsys.readouterr().out


def test_bump_versions_twice(raw_project):
    first = package.bump_versions()
    assert package.bump_versions() == [first[0], first[1], first[2] + 1]


@pytest.mark.parametrize(
    ("bp_v", "rp_v", "expected"),
    [([1, 0, 3], [1, 0, 7], [1, 0, 8]), ([2, 0, 0], [1, 9, 9], [2, 0, 1]), ([1, 2, 3], [1, 2, 3], [1, 2, 4])],
)
def test_bump_versions_takes_the_higher_one(raw_project, bp_v, rp_v, expected):
    _set_version(raw_project.bp / "manifest.json", bp_v)
    _set_version(raw_project.rp / "manifest.json", rp_v)
    assert package.bump_versions() == expected


def test_bump_versions_needs_rp_dependency(raw_project):
    path = raw_project.bp / "manifest.json"
    m = common.load_json(path)
    m["dependencies"] = [d for d in m["dependencies"] if "uuid" not in d]
    common.write_json(path, m)
    before = path.read_bytes()
    with pytest.raises(BuildError, match="no dependency on the RP"):
        package.bump_versions()
    assert path.read_bytes() == before  # nothing written on failure


def test_bump_versions_writes_valid_json_without_bom(raw_project):
    package.bump_versions()
    for pack in (raw_project.bp, raw_project.rp):
        raw = (pack / "manifest.json").read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf")
        assert b"\r\n" not in raw


def test_make_mcaddon(raw_project, capsys):
    bp, rp = raw_project.bp, raw_project.rp
    (bp / "Thumbs.db").write_bytes(b"junk")
    (rp / "textures" / "desktop.ini").write_text("junk", encoding="utf-8")
    (rp / "textures" / ".DS_Store").write_bytes(b"junk")
    package.make_mcaddon()
    out = raw_project.paths.dist / "big_cat.mcaddon"
    assert out.is_file()
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert z.testzip() is None
        assert z.read("big_cat_bp/manifest.json") == (bp / "manifest.json").read_bytes()
    expected = sorted(
        f"{pack.name}/{f.relative_to(pack).as_posix()}"
        for pack in (bp, rp)
        for f in pack.rglob("*")
        if f.is_file() and f.name not in package.SKIP_NAMES
    )
    assert sorted(names) == expected
    assert all("\\" not in n for n in names)
    assert {n.split("/")[0] for n in names} == {"big_cat_bp", "big_cat_rp"}
    assert not any(n.rsplit("/", 1)[-1] in package.SKIP_NAMES for n in names)
    assert f"packaged {len(names)} files" in capsys.readouterr().out


def test_make_mcaddon_overwrites_previous(raw_project):
    dist = raw_project.paths.dist
    dist.mkdir()
    (dist / "big_cat.mcaddon").write_bytes(b"not a zip")
    package.make_mcaddon()
    assert zipfile.is_zipfile(dist / "big_cat.mcaddon")
