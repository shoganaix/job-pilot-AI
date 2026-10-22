"""Read and write the YAML configs edited by the web UI.

The rules here are the ones the whole UI is built on:

* every save keeps the previous file as ``<name>.yaml.bak`` (PyYAML drops
  comments, so the backup is the only place they survive);
* nothing is written unless the payload first passes the *same* parsers the
  CLI uses (``parse_master_cv`` / ``parse_search`` / ``parse_profile`` /
  ``parse_families``), so a half-broken form can never corrupt a config the
  rest of jobpilot depends on.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

import yaml

from ..config import (
    ConfigError,
    parse_families,
    parse_master_cv,
    parse_profile,
    parse_search,
)

MCV_SECTIONS = ("contact", "summary", "experience", "education", "skills")


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML mapping; a missing file yields an empty dict (first run)."""
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path} is not a YAML mapping")
    return data


def backup_name(path: Path) -> Path:
    return path.with_name(path.name + ".bak")


def save_yaml(path: Path, data: dict[str, Any]) -> Path:
    """Write ``data`` to ``path`` keeping the old file as ``.bak``.

    Returns the backup path (only meaningful when the file already existed).
    """
    backup = backup_name(path)
    if path.exists():
        shutil.copy2(path, backup)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return backup


def validate_master_cv(data: dict[str, Any]) -> None:
    """Run the payload through the real CV parser (raises ``ConfigError``)."""
    for key in MCV_SECTIONS:
        if key not in data:
            raise ConfigError(f"missing key {key!r} in master CV")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir) / "master_cv.yaml"
        tmp.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        parse_master_cv(tmp)


def validate_profile(data: dict[str, Any]) -> None:
    """Validate the profile sections through the CLI parsers.

    Only the sections the web UI writes are parsed; ``project`` / ``scoring``
    pass through untouched.
    """
    for key in ("search", "profile"):
        if key in data and not isinstance(data[key], dict):
            raise ConfigError(f"{key} must be a mapping")
    if "families" in data and not isinstance(data["families"], list):
        raise ConfigError("families must be a list")
    parse_search(data.get("search", {}) or {})
    parse_profile(data.get("profile", {}) or {})
    parse_families(data.get("families", []) or [])
    ats = data.get("ats_companies", {}) or {}
    if not isinstance(ats, dict):
        raise ConfigError("ats_companies must be a mapping")
    for key in ats:
        if key not in ("greenhouse", "lever"):
            raise ConfigError(f"unknown ats source: {key!r}")
        if not isinstance(ats[key], list) or not all(
            isinstance(c, str) for c in ats[key]
        ):
            raise ConfigError(f"ats_companies.{key} must be a list of strings")
