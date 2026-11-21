"""Shared helpers for the Gear build tools (config, paths, JSON I/O).

Adapted from the Big Cat project's tools/common.py (copied, not imported).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "tools" / "gear_config.json"


class BuildError(Exception):
    """A problem that should stop the build with a clear message."""


def rel(path: Path | str) -> str:
    """Path relative to the project root, for readable messages."""
    p = Path(path)
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


# --------------------------------------------------------------------------- JSON

_COMMENT_RE = re.compile(r'("(?:\\.|[^"\\])*")|//[^\n]*|/\*.*?\*/', re.S)


def strip_json_comments(text: str) -> str:
    """Remove // and /* */ comments (vanilla sample files use them), keeping strings intact."""
    return _COMMENT_RE.sub(lambda m: m.group(1) or "", text)


def load_json(path: Path | str, allow_comments: bool = False):
    path = Path(path)
    if not path.is_file():
        raise BuildError(f"{rel(path)}: file not found")
    text = path.read_text(encoding="utf-8-sig")
    if allow_comments:
        text = strip_json_comments(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise BuildError(f"{rel(path)}: invalid JSON: {e}") from None


def dumps(obj, indent: int = 2, inline_width: int = 100) -> str:
    """JSON with nested objects indented but short scalar lists kept on one line."""

    def fmt(o, level):
        pad = " " * (indent * level)
        pad2 = " " * (indent * (level + 1))
        if isinstance(o, dict):
            if not o:
                return "{}"
            items = [f"{pad2}{json.dumps(k)}: {fmt(v, level + 1)}" for k, v in o.items()]
            return "{\n" + ",\n".join(items) + "\n" + pad + "}"
        if isinstance(o, list):
            if not o:
                return "[]"
            if all(not isinstance(x, (dict, list)) for x in o):
                one = "[" + ", ".join(json.dumps(x) for x in o) + "]"
                if len(one) + len(pad) <= inline_width:
                    return one
            return "[\n" + ",\n".join(pad2 + fmt(x, level + 1) for x in o) + "\n" + pad + "]"
        return json.dumps(o)

    return fmt(obj, 0) + "\n"


def write_text(path: Path, text: str) -> None:
    """UTF-8 without BOM (a BOM breaks Bedrock), LF line endings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_json(path: Path, obj) -> None:
    write_text(path, dumps(obj))


# ------------------------------------------------------------------------- config


@dataclass
class Paths:
    bp: Path
    rp: Path
    vanilla_art: Path
    build: Path
    dist: Path
    item_texture_dir: str  # pack-relative, e.g. "textures/gear/items"
    armor_texture_dir: str  # pack-relative, e.g. "textures/gear/armor"
    samples: Path  # Mojang bedrock-samples checkout (read-only reference)


def load_config() -> tuple[dict, Paths]:
    cfg = load_json(CONFIG_PATH)
    required = ["namespace", "addon_name", "paths", "material", "palette", "layers", "pieces", "kinds"]
    missing = [k for k in required if k not in cfg]
    if missing:
        raise BuildError(f"{rel(CONFIG_PATH)}: missing keys {missing}")
    ns = cfg["namespace"]
    for piece in cfg["pieces"]:
        for key in (
            "id",
            "name",
            "slot",
            "script_slot",
            "enchant_slot",
            "protection",
            "durability",
            "kind",
            "layer",
            "icon_source",
            "group",
            "recipe",
        ):
            if key not in piece:
                raise BuildError(f"{rel(CONFIG_PATH)}: piece {piece.get('id', '?')} is missing '{key}'")
        if not re.fullmatch(r"[a-z0-9_]+", piece["id"]):
            raise BuildError(f"{rel(CONFIG_PATH)}: bad piece id {piece['id']!r}")
        if piece["kind"] not in cfg["kinds"]:
            raise BuildError(f"{rel(CONFIG_PATH)}: piece {piece['id']} has unknown kind {piece['kind']!r}")
        if piece["layer"] not in cfg["layers"]:
            raise BuildError(f"{rel(CONFIG_PATH)}: piece {piece['id']} has unknown layer {piece['layer']!r}")
        piece["identifier"] = f"{ns}:{piece['id']}"
    p = cfg["paths"]
    samples = Path(
        os.environ.get("MC_SAMPLES") or os.environ.get("GEAR_SAMPLES") or ROOT / p["bedrock_samples_default"]
    ).resolve()
    paths = Paths(
        bp=ROOT / p["behavior_pack"],
        rp=ROOT / p["resource_pack"],
        vanilla_art=ROOT / p["vanilla_art"],
        build=ROOT / p["build_dir"],
        dist=ROOT / p["dist_dir"],
        item_texture_dir=p["item_texture_dir"].strip("/"),
        armor_texture_dir=p["armor_texture_dir"].strip("/"),
        samples=samples,
    )
    return cfg, paths


def texture_key(cfg: dict, piece: dict) -> str:
    """Short name in textures/item_texture.json (prefixed so it can't clash with other packs)."""
    return f"{cfg['namespace']}_{piece['id']}"
