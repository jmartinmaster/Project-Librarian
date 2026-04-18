"""Application configuration model for Project Librarian."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".config" / "project-librarian"
CONFIG_PATH = CONFIG_DIR / "config.json"


@dataclass
class AppConfig:
    """Persistent application settings for indexing and UI behavior."""

    project_root: str = ""
    output_dir: str = "build"
    excluded_dirs: list[str] = field(default_factory=lambda: [".git", ".venv", "__pycache__", "build"])
    file_extensions: list[str] = field(
        default_factory=lambda: [".py", ".c", ".h", ".md", ".json", ".txt", ".xlsx", ".csv"]
    )
    refresh_interval_seconds: int = 30
    index_python: bool = True
    index_c: bool = True
    excel_folder: str = ""
    excel_keyword_columns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary for the current config."""
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AppConfig":
        """Create a config from a mapping while preserving defaults for missing fields."""
        default = cls()
        allowed = default.to_dict().keys()
        merged = default.to_dict()
        merged.update({key: value for key, value in payload.items() if key in allowed})
        return cls(**merged)


def load_config(config_path: Path = CONFIG_PATH) -> AppConfig:
    """Load configuration from disk or return defaults when unavailable."""
    if not config_path.exists():
        return AppConfig()

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppConfig()

    if not isinstance(payload, dict):
        return AppConfig()
    return AppConfig.from_dict(payload)


def save_config(config: AppConfig, config_path: Path = CONFIG_PATH) -> Path:
    """Save configuration to disk and return the written path."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")
    return config_path
