from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema
import yaml

SCHEMA_VERSION = 1
_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "config.schema.json"


class ConfigError(Exception):
    pass


def _looks_absolute(path_str: str) -> bool:
    r"""Check if a path looks absolute without depending on host OS.

    Returns True if the path:
    - Starts with / or \ (POSIX style or Windows root path)
    - Matches Windows drive letter pattern like C:/ or D:\
    """
    if path_str.startswith("/") or path_str.startswith("\\"):
        return True
    # Windows drive letter pattern: C:/, C:\, D:/, etc.
    if re.match(r"^[A-Za-z]:[/\\]", path_str):
        return True
    return False


def load_config(path: str | Path) -> dict:
    p = Path(path)
    if not p.is_file():
        raise ConfigError(f"config not found: {p}")

    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"config is not valid YAML: {e}") from e
    except (OSError, PermissionError) as e:
        raise ConfigError(f"config file is not readable: {p}") from e

    if not isinstance(raw, dict):
        raise ConfigError("config root must be a mapping")

    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(instance=raw, schema=schema)
    except jsonschema.ValidationError as e:
        raise ConfigError(f"config failed schema validation: {e.message}") from e

    if raw["spotcat_schema_version"] != SCHEMA_VERSION:
        raise ConfigError(
            f"spotcat_schema_version {raw['spotcat_schema_version']} != expected {SCHEMA_VERSION}; "
            "run the config migration before continuing"
        )

    # Resolve relative data_root against the project root (2 levels up from config file)
    data_root = raw["paths"]["data_root"]

    if not _looks_absolute(data_root):
        # Config file is at <project_root>/.spotcat/config.yml
        # So project_root is 2 levels up from the config file
        project_root = p.resolve().parent.parent
        resolved_path = (project_root / data_root).resolve()
        raw["paths"]["data_root"] = str(resolved_path)
    else:
        # Already absolute, but normalize it (handle .. and . segments)
        # Use Path to handle both POSIX and Windows style paths
        resolved_path = Path(data_root).resolve()
        raw["paths"]["data_root"] = str(resolved_path)

    return raw
