"""package.py: version bumping and the .mcaddon zip, all inside tmp_path."""

from __future__ import annotations

import json
import zipfile

import pytest

import package
from common import BuildError


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def packs(gear_root):
    gear_root.write_manifests()
    return gear_root


def test_bump_versions(packs, capsys):
    assert package.bump_versions() == [1, 0, 2]
    bp, rp = _read(packs.bp / "manifest.json"), _read(packs.rp / "manifest.json")
    assert bp["header"]["version"] == rp["header"]["version"] == [1, 0, 2]
    assert [m["version"] for m in bp["modules"]] == [[1, 0, 2], [1, 0, 2]]
    assert [m["version"] for m in rp["modules"]] == [[1, 0, 2]]
    assert bp["dependencies"][0] == {"uuid": rp["header"]["uuid"], "version": [1, 0, 2]}
    assert bp["dependencies"][1] == {"module_name": "@minecraft/server", "version": "2.11.0"}, "left alone"
    assert "1.0.1 -> 1.0.2" in capsys.readouterr().out


def test_bump_is_cumulative(packs):
    package.bump_versions()
    package.bump_versions()
    assert _read(packs.bp / "manifest.json")["header"]["version"] == [1, 0, 3]


@pytest.mark.parametrize(
    ("bp_ver", "rp_ver", "expected"),
    [
        pytest.param([1, 0, 5], [1, 0, 1], [1, 0, 6], id="bp-ahead"),
        pytest.param([1, 0, 1], [1, 0, 9], [1, 0, 10], id="rp-ahead"),
        pytest.param([1, 2, 0], [1, 1, 9], [1, 2, 1], id="minor-wins-over-patch"),
        pytest.param([2, 0, 0], [1, 9, 9], [2, 0, 1], id="major-wins"),
    ],
)
def test_bump_takes_the_higher_version(packs, bp_ver, rp_ver, expected):
    bp, rp = _read(packs.bp / "manifest.json"), _read(packs.rp / "manifest.json")
    bp["header"]["version"], rp["header"]["version"] = bp_ver, rp_ver
    packs.write_manifests(bp, rp)
    assert package.bump_versions() == expected
    assert _read(packs.rp / "manifest.json")["header"]["version"] == expected


def test_bump_without_rp_dependency_fails_and_writes_nothing(packs):
    bp, rp = _read(packs.bp / "manifest.json"), _read(packs.rp / "manifest.json")
    bp["dependencies"] = [d for d in bp["dependencies"] if "uuid" not in d]
    packs.write_manifests(bp, rp)
    before = (packs.bp / "manifest.json").read_bytes(), (packs.rp / "manifest.json").read_bytes()
    with pytest.raises(BuildError, match="no dependency on the RP"):
        package.bump_versions()
    assert ((packs.bp / "manifest.json").read_bytes(), (packs.rp / "manifest.json").read_bytes()) == before


def test_bump_missing_manifest(gear_root):
    with pytest.raises(BuildError, match=r"manifest\.json: file not found"):
        package.bump_versions()


def test_make_mcaddon(packs, capsys):
    (packs.bp / "scripts").mkdir()
    (packs.bp / "scripts" / "main.js").write_text("// js", encoding="utf-8")
    (packs.rp / "textures" / "gear").mkdir(parents=True)
    (packs.rp / "textures" / "gear" / "a.png").write_bytes(b"png")
    for junk in package.SKIP_NAMES:
        (packs.rp / "textures" / junk).write_bytes(b"junk")
    (packs.rp / "empty_dir").mkdir()

    package.make_mcaddon()

    out = packs.root / "dist" / "gear.mcaddon"
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
        names = sorted(z.namelist())
        assert names == [
            "gear_bp/manifest.json",
            "gear_bp/scripts/main.js",
            "gear_rp/manifest.json",
            "gear_rp/textures/gear/a.png",
        ]
        assert all(i.compress_type == zipfile.ZIP_DEFLATED for i in z.infolist())
        assert json.loads(z.read("gear_rp/manifest.json")) == _read(packs.rp / "manifest.json")
        assert z.read("gear_bp/scripts/main.js") == b"// js"
    printed = capsys.readouterr().out
    assert "packaged 4 files" in printed
    assert "(v1.0.1," in printed


def test_make_mcaddon_overwrites_previous(packs):
    package.make_mcaddon()
    (packs.bp / "extra.txt").write_text("x", encoding="utf-8")
    package.make_mcaddon()
    with zipfile.ZipFile(packs.root / "dist" / "gear.mcaddon") as z:
        names = z.namelist()
    assert names.count("gear_bp/extra.txt") == 1
    assert len(names) == len(set(names))


def test_make_mcaddon_uses_addon_name(packs, base_config):
    base_config["addon_name"] = "op_gear"
    packs.write_config(base_config)
    package.make_mcaddon()
    assert (packs.root / "dist" / "op_gear.mcaddon").is_file()
