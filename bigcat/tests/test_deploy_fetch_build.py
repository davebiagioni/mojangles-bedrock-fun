"""deploy_dev.py, fetch_vanilla.py and build.py, with every external folder redirected into tmp_path.

deploy is only ever pointed at a fake com.mojang folder under tmp_path; the conftest's autouse
fixture removes APPDATA / LOCALAPPDATA / BIGCAT_COM_MOJANG so the real Minecraft folders can't be found.
"""

from __future__ import annotations

import json

import pytest

import build
import common
import deploy_dev
import fetch_vanilla
from common import BuildError

# ------------------------------------------------------------------------------ deploy


def test_candidates_order(tmp_path, monkeypatch):
    monkeypatch.setenv("BIGCAT_COM_MOJANG", str(tmp_path / "override"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    got = deploy_dev.candidates()
    assert [label for label, _ in got] == [
        "BIGCAT_COM_MOJANG",
        "newer install (APPDATA)",
        "older UWP install (LOCALAPPDATA)",
    ]
    assert got[0][1] == tmp_path / "override"
    assert got[1][1] == tmp_path / "roaming" / "Minecraft Bedrock" / "Users" / "Shared" / "games" / "com.mojang"
    uwp = ("Packages", "Microsoft.MinecraftUWP_8wekyb3d8bbwe", "LocalState", "games", "com.mojang")
    assert got[2][1] == tmp_path.joinpath("local", *uwp)


def test_candidates_empty_without_env():
    assert deploy_dev.candidates() == []


def test_find_com_mojang_none_found(tmp_path, monkeypatch):
    monkeypatch.setenv("BIGCAT_COM_MOJANG", str(tmp_path / "missing"))
    with pytest.raises(BuildError, match=r"could not find Minecraft's com\.mojang folder") as exc:
        deploy_dev.find_com_mojang()
    assert str(tmp_path / "missing") in str(exc.value)


def test_find_com_mojang_prefers_first_and_notes_others(tmp_path, monkeypatch, capsys):
    override = tmp_path / "override"
    newer = tmp_path / "roaming" / "Minecraft Bedrock" / "Users" / "Shared" / "games" / "com.mojang"
    override.mkdir()
    newer.mkdir(parents=True)
    monkeypatch.setenv("BIGCAT_COM_MOJANG", str(override))
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    assert deploy_dev.find_com_mojang() == override
    out = capsys.readouterr().out
    assert "[BIGCAT_COM_MOJANG]" in out
    assert "another com.mojang also exists" in out


def test_find_com_mojang_skips_missing_override(tmp_path, monkeypatch):
    newer = tmp_path / "roaming" / "Minecraft Bedrock" / "Users" / "Shared" / "games" / "com.mojang"
    newer.mkdir(parents=True)
    monkeypatch.setenv("BIGCAT_COM_MOJANG", str(tmp_path / "nope"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    assert deploy_dev.find_com_mojang() == newer


@pytest.fixture
def fake_mojang(tmp_path, monkeypatch):
    com = tmp_path / "fake_com_mojang"
    com.mkdir()
    monkeypatch.setenv("BIGCAT_COM_MOJANG", str(com))
    return com


def test_deploy_copies_both_packs(raw_project, fake_mojang, capsys):
    stale = fake_mojang / "development_behavior_packs" / "big_cat_bp" / "stale.txt"
    stale.parent.mkdir(parents=True)
    stale.write_text("old", encoding="utf-8")
    deploy_dev.deploy()
    for folder, pack in (
        ("development_behavior_packs", raw_project.bp),
        ("development_resource_packs", raw_project.rp),
    ):
        dest = fake_mojang / folder / pack.name
        assert (dest / "manifest.json").read_bytes() == (pack / "manifest.json").read_bytes()
        assert sorted(p.relative_to(dest) for p in dest.rglob("*")) == sorted(
            p.relative_to(pack) for p in pack.rglob("*")
        )
    assert not stale.exists()  # the old copy is replaced, not merged
    out = capsys.readouterr().out
    assert "big_cat_bp ->" in out
    assert "WARNING" not in out


def test_deploy_warns_about_imported_copy(raw_project, fake_mojang, capsys):
    rp_uuid = common.load_json(raw_project.rp / "manifest.json")["header"]["uuid"]
    imported = fake_mojang / "resource_packs" / "imported_big_cat"
    imported.mkdir(parents=True)
    (imported / "manifest.json").write_text(json.dumps({"header": {"uuid": rp_uuid}}), encoding="utf-8")
    broken = fake_mojang / "resource_packs" / "broken"
    broken.mkdir()
    (broken / "manifest.json").write_text("{ nope", encoding="utf-8")  # ignored, not a crash
    deploy_dev.deploy()
    out = capsys.readouterr().out
    assert "WARNING: an imported copy of big_cat_rp" in out


def test_deploy_without_minecraft_fails_cleanly(raw_project):
    with pytest.raises(BuildError, match=r"could not find Minecraft's com\.mojang"):
        deploy_dev.deploy()


# ------------------------------------------------------------------------------- fetch


@pytest.fixture
def samples(tmp_path, monkeypatch):
    """A fake bedrock-samples checkout with the files vanilla_files.json lists."""
    root = tmp_path / "bedrock-samples"
    (root / "resource_pack").mkdir(parents=True)
    monkeypatch.setenv("MC_SAMPLES", str(root))
    return root


@pytest.fixture
def file_list(tmp_path, monkeypatch, synth):
    proj = tmp_path / "proj"
    real = json.loads((synth.BIGCAT / "tools" / "vanilla_files.json").read_text(encoding="utf-8"))
    common.write_json(proj / "tools" / "vanilla_files.json", real)
    monkeypatch.setattr(common, "ROOT", proj)
    monkeypatch.setattr(fetch_vanilla, "LIST", proj / "tools" / "vanilla_files.json")
    monkeypatch.setattr(fetch_vanilla, "DEST", proj / "vanilla")
    return real


def test_samples_dir_from_env(samples):
    assert fetch_vanilla.samples_dir() == samples


def test_samples_dir_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("MC_SAMPLES", str(tmp_path / "nothing"))
    with pytest.raises(BuildError, match="bedrock-samples not found") as exc:
        fetch_vanilla.samples_dir()
    assert "git clone" in str(exc.value)


def test_samples_dir_default_is_next_to_project(tmp_path, monkeypatch):
    monkeypatch.delenv("MC_SAMPLES")
    monkeypatch.setattr(fetch_vanilla, "ROOT", tmp_path / "mc" / "bigcat")
    (tmp_path / "mc" / "bedrock-samples" / "resource_pack").mkdir(parents=True)
    assert fetch_vanilla.samples_dir() == tmp_path / "mc" / "bedrock-samples"


def test_fetch_vanilla_copies_listed_files(samples, file_list, capsys):
    for i, src in enumerate(file_list.values()):
        (samples / src).parent.mkdir(parents=True, exist_ok=True)
        (samples / src).write_text(f"file {i}", encoding="utf-8")
    fetch_vanilla.fetch_vanilla()
    for i, dest in enumerate(file_list):
        assert (fetch_vanilla.DEST / dest).read_text(encoding="utf-8") == f"file {i}"
    assert f"{len(file_list)} files" in capsys.readouterr().out


def test_fetch_vanilla_missing_source(samples, file_list):
    with pytest.raises(BuildError, match="is missing from"):
        fetch_vanilla.fetch_vanilla()


def test_vanilla_list_covers_configured_inputs(synth):
    """Every Mojang file the config and generators read is in vanilla_files.json."""
    files = json.loads((synth.BIGCAT / "tools" / "vanilla_files.json").read_text(encoding="utf-8"))
    cfg = synth.small_config()
    for key in ("geometry", "base_texture", "tame_reference"):
        assert cfg["paths"][key].removeprefix("vanilla/") in files
    for mob in ("zombie", "skeleton", "creeper", "player", "drowned"):
        assert f"{mob}.json" in files


# ------------------------------------------------------------------------------- build


STEP_NAMES = [
    "fetch_vanilla",
    "build_coats",
    "generate_json",
    "generate_laser_textures",
    "generate_orb_textures",
    "generate_tame",
    "generate_wand_textures",
    "generate_grapple_textures",
    "generate_drowned_trap",
    "generate_evolution_textures",
    "generate_net_textures",
    "generate_morph",
    "generate_player",
    "validate",
    "bump_versions",
    "deploy",
    "make_mcaddon",
]


@pytest.fixture
def calls(monkeypatch):
    """Replace every build step with a recorder (so nothing real runs, least of all deploy)."""
    log = []
    for name in STEP_NAMES:
        monkeypatch.setattr(build, name, lambda name=name: log.append(name))
    return log


BASE_STEPS = STEP_NAMES[: STEP_NAMES.index("validate") + 1]  # every step up to validate


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        ([], [*BASE_STEPS, "deploy"]),
        (["--no-deploy"], BASE_STEPS),
        (["--package"], [*BASE_STEPS, "bump_versions", "validate", "deploy", "make_mcaddon"]),
        (["--package", "--no-deploy"], [*BASE_STEPS, "bump_versions", "validate", "make_mcaddon"]),
    ],
)
def test_build_step_order(calls, monkeypatch, capsys, argv, expected):
    monkeypatch.setattr("sys.argv", ["build.py", *argv])
    assert build.main() == 0
    assert calls == expected
    out = capsys.readouterr().out
    assert f"[1/{len(expected)}] fetch Mojang files" in out
    assert "done in" in out


def test_build_stops_on_build_error(calls, monkeypatch, capsys):
    def boom():
        raise BuildError("coat trouble")

    monkeypatch.setattr(build, "build_coats", boom)
    monkeypatch.setattr("sys.argv", ["build.py"])
    assert build.main() == 1
    assert calls == ["fetch_vanilla"]
    assert "BUILD FAILED: coat trouble" in capsys.readouterr().err


def test_build_steps_all_exist():
    for name in STEP_NAMES:
        assert callable(getattr(build, name))
