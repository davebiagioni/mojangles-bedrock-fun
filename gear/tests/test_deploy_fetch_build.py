"""deploy_dev, fetch_vanilla and build.main. Nothing here touches the real Minecraft install,
the real vanilla/ folder or bedrock-samples: every target is redirected into tmp_path."""

from __future__ import annotations

import json
import sys

import pytest

import build
import deploy_dev
import fetch_vanilla
from common import BuildError

# --------------------------------------------------------------------------- deploy_dev


@pytest.fixture
def no_minecraft_env(monkeypatch):
    """Hide every real com.mojang location, so nothing can resolve to the user's install."""
    for var in ("GEAR_COM_MOJANG", "APPDATA", "LOCALAPPDATA"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def com_mojang(tmp_path, monkeypatch, no_minecraft_env):
    com = tmp_path / "com.mojang"
    com.mkdir()
    monkeypatch.setenv("GEAR_COM_MOJANG", str(com))
    return com


def test_candidates_order(monkeypatch, tmp_path, no_minecraft_env):
    monkeypatch.setenv("GEAR_COM_MOJANG", str(tmp_path / "override"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    got = deploy_dev.candidates()
    assert [label for label, _ in got] == [
        "GEAR_COM_MOJANG",
        "newer install (APPDATA)",
        "older UWP install (LOCALAPPDATA)",
    ]
    assert got[0][1] == tmp_path / "override"
    assert got[1][1] == tmp_path / "roaming" / "Minecraft Bedrock" / "Users" / "Shared" / "games" / "com.mojang"
    assert got[2][1].parts[-5:] == (
        "Packages",
        "Microsoft.MinecraftUWP_8wekyb3d8bbwe",
        "LocalState",
        "games",
        "com.mojang",
    )


def test_candidates_empty_without_env(no_minecraft_env):
    assert deploy_dev.candidates() == []


def test_find_com_mojang_none_found(monkeypatch, tmp_path, no_minecraft_env):
    monkeypatch.setenv("GEAR_COM_MOJANG", str(tmp_path / "missing"))
    with pytest.raises(BuildError, match=r"could not find Minecraft's com\.mojang"):
        deploy_dev.find_com_mojang()


def test_find_com_mojang_prefers_first_and_notes_others(monkeypatch, tmp_path, no_minecraft_env, capsys):
    override = tmp_path / "override"
    override.mkdir()
    newer = tmp_path / "roaming" / "Minecraft Bedrock" / "Users" / "Shared" / "games" / "com.mojang"
    newer.mkdir(parents=True)
    monkeypatch.setenv("GEAR_COM_MOJANG", str(override))
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    assert deploy_dev.find_com_mojang() == override
    assert "another com.mojang also exists" in capsys.readouterr().out


def test_deploy_copies_and_replaces(project, com_mojang):
    stale = com_mojang / "development_behavior_packs" / "gear_bp" / "stale.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("{}", encoding="utf-8")
    neighbour = com_mojang / "development_behavior_packs" / "other_pack" / "manifest.json"
    neighbour.parent.mkdir(parents=True)
    neighbour.write_text("{}", encoding="utf-8")

    deploy_dev.deploy()

    for pack, folder in ((project.bp, "development_behavior_packs"), (project.rp, "development_resource_packs")):
        dest = com_mojang / folder / pack.name
        src_files = sorted(p.relative_to(pack) for p in pack.rglob("*") if p.is_file())
        assert sorted(p.relative_to(dest) for p in dest.rglob("*") if p.is_file()) == src_files
    assert not stale.exists()
    assert neighbour.is_file(), "other packs must not be touched"


@pytest.mark.parametrize("which", ["behavior_pack", "resource_pack"])
def test_deploy_refuses_unexpected_pack_names(project, com_mojang, base_config, which):
    base_config["paths"][which] = "tools"
    project.write_config(base_config)
    with pytest.raises(BuildError, match="refusing to deploy a pack folder named 'tools'"):
        deploy_dev.deploy()
    assert not (com_mojang / "development_behavior_packs" / "tools").exists()
    assert not (com_mojang / "development_resource_packs" / "tools").exists()


def test_warn_imported_copies(tmp_path, capsys):
    com = tmp_path / "com.mojang"
    for name, data in {
        "behavior_packs/old_gear/manifest.json": {"header": {"uuid": "u-bp"}},
        "behavior_packs/unrelated/manifest.json": {"header": {"uuid": "u-other"}},
        "resource_packs/broken/manifest.json": None,
    }.items():
        p = com / name
        p.parent.mkdir(parents=True)
        p.write_text("{" if data is None else json.dumps(data), encoding="utf-8")
    deploy_dev.warn_imported_copies(com, {"u-bp": "gear_bp", "u-rp": "gear_rp"})
    out = capsys.readouterr().out
    assert out.count("WARNING") == 1
    assert "imported copy of gear_bp" in out
    assert "old_gear" in out


def test_warn_imported_copies_no_folders(tmp_path, capsys):
    deploy_dev.warn_imported_copies(tmp_path, {"u": "gear_bp"})
    assert capsys.readouterr().out == ""


# --------------------------------------------------------------------------- fetch_vanilla


@pytest.fixture
def fetch_env(gear_root, samples, monkeypatch):
    listing = {
        "diamond_1.png": "resource_pack/textures/misc/enchanted_actor_glint.png",
        "sub/sounds.json": "resource_pack/sounds/sound_definitions.json",
    }
    list_path = gear_root.root / "tools" / "vanilla_files.json"
    list_path.write_text(json.dumps(listing), encoding="utf-8")
    dest = gear_root.root / "vanilla"
    monkeypatch.setattr(fetch_vanilla, "LIST", list_path)
    monkeypatch.setattr(fetch_vanilla, "DEST", dest)
    return listing, dest


def test_fetch_vanilla_copies_listed_files(fetch_env, samples):
    listing, dest = fetch_env
    fetch_vanilla.fetch_vanilla()
    for name, src in listing.items():
        assert (dest / name).read_bytes() == (samples / src).read_bytes()


def test_fetch_vanilla_missing_source_file(fetch_env):
    listing, _ = fetch_env
    listing["x.png"] = "resource_pack/textures/nope.png"
    fetch_vanilla.LIST.write_text(json.dumps(listing), encoding="utf-8")
    with pytest.raises(BuildError, match=r"resource_pack/textures/nope\.png is missing"):
        fetch_vanilla.fetch_vanilla()


def test_samples_dir_requires_resource_pack(monkeypatch, tmp_path):
    monkeypatch.setenv("MC_SAMPLES", str(tmp_path))
    with pytest.raises(BuildError, match="bedrock-samples not found"):
        fetch_vanilla.samples_dir()


def test_samples_dir_from_mc_samples(samples):
    assert fetch_vanilla.samples_dir() == samples


@pytest.mark.xfail(
    strict=True,
    reason="BUG: common.load_config (validate) honours GEAR_SAMPLES but fetch_vanilla.samples_dir ignores it, "
    "so with only GEAR_SAMPLES set the two steps of one build read different checkouts",
)
def test_samples_dir_honours_gear_samples(samples, monkeypatch):
    monkeypatch.delenv("MC_SAMPLES")
    monkeypatch.setenv("GEAR_SAMPLES", str(samples))
    assert fetch_vanilla.samples_dir() == samples


def test_real_vanilla_list_matches_config():
    """Read-only: every source texture the committed config needs is listed in vanilla_files.json."""
    import common

    cfg, _ = common.load_config()
    listed = set(json.loads(fetch_vanilla.LIST.read_text(encoding="utf-8")))
    needed = {spec["source"] for spec in cfg["layers"].values()} | {p["icon_source"] for p in cfg["pieces"]}
    assert needed <= listed


# --------------------------------------------------------------------------- build.main


@pytest.fixture
def fake_steps(monkeypatch):
    calls: list[str] = []
    for name in (
        "fetch_vanilla",
        "build_textures",
        "generate_json",
        "validate",
        "bump_versions",
        "deploy",
        "make_mcaddon",
    ):
        monkeypatch.setattr(build, name, lambda name=name: calls.append(name))
    return calls


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        pytest.param([], ["fetch_vanilla", "build_textures", "generate_json", "validate", "deploy"], id="default"),
        pytest.param(["--no-deploy"], ["fetch_vanilla", "build_textures", "generate_json", "validate"], id="no-deploy"),
        pytest.param(
            ["--package"],
            [
                "fetch_vanilla",
                "build_textures",
                "generate_json",
                "validate",
                "bump_versions",
                "validate",
                "deploy",
                "make_mcaddon",
            ],
            id="package",
        ),
        pytest.param(
            ["--package", "--no-deploy"],
            [
                "fetch_vanilla",
                "build_textures",
                "generate_json",
                "validate",
                "bump_versions",
                "validate",
                "make_mcaddon",
            ],
            id="package-no-deploy",
        ),
    ],
)
def test_build_step_order(monkeypatch, fake_steps, argv, expected):
    monkeypatch.setattr(sys, "argv", ["build.py", *argv])
    assert build.main() == 0
    assert fake_steps == expected


def test_build_stops_at_first_failure(monkeypatch, fake_steps, capsys):
    def boom():
        fake_steps.append("generate_json")
        raise BuildError("kaboom")

    monkeypatch.setattr(build, "generate_json", boom)
    monkeypatch.setattr(sys, "argv", ["build.py"])
    assert build.main() == 1
    assert fake_steps == ["fetch_vanilla", "build_textures", "generate_json"]
    assert "BUILD FAILED: kaboom" in capsys.readouterr().err
