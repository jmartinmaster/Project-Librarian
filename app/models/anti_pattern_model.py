# Copyright (C) 2026 The Librarian contributors
#
# This file is part of The Librarian.
#
# The Librarian is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# The Librarian is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with The Librarian. If not, see <https://www.gnu.org/licenses/>.
"""Anti-pattern rule configuration service."""

from __future__ import annotations

import json
from pathlib import Path

ANTI_PATTERN_CONFIG_NAME = "anti_pattern_config.json"

DEFAULT_ANTI_PATTERNS = [
    {
        "name": "Bare Except",
        "regex": r"except\s*:",
        "description": "Using bare except without specifying an exception class catches system exits and interrupts.",
        "severity": "warning",
        "enabled": True,
    },
    {
        "name": "Wildcard Import",
        "regex": r"from\s+\S+\s+import\s+\*",
        "description": "Importing * pollutes the namespace and can mask other symbols.",
        "severity": "warning",
        "enabled": True,
    },
    {
        "name": "Mutable Default Argument",
        "regex": r"def\s+\w+\([^)]*=\s*[\[\{]",
        "description": "Mutable default arguments are shared across all function calls, leading to potential state pollution.",
        "severity": "warning",
        "enabled": True,
    },
    {
        "name": "Eval / Exec Usage",
        "regex": r"(?<!\.)\b(eval|exec)\s*\(",
        "description": "Using eval or exec can run arbitrary code, presenting security risks.",
        "severity": "error",
        "enabled": True,
    },
    {
        "name": "Breakpoint left in code",
        "regex": r"\bbreakpoint\s*\(",
        "description": "Hardcoded breakpoints block execution and should be removed before shipping.",
        "severity": "error",
        "enabled": True,
    },
]


def load_anti_pattern_config(output_dir: str | Path) -> dict:
    """Load the current anti-pattern configuration file or return defaults."""
    config_path = Path(output_dir) / ANTI_PATTERN_CONFIG_NAME
    if config_path.exists():
        try:
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and "presets" in loaded:
                presets = []
                for p in loaded["presets"]:
                    if isinstance(p, dict) and "name" in p and "regex" in p:
                        name = str(p["name"])
                        regex = str(p["regex"])
                        description = str(p.get("description", ""))
                        
                        # Upgrade regex and description to solve false positives in old configs
                        if name == "Eval / Exec Usage" and regex == r"\b(eval|exec)\s*\(":
                            regex = r"(?<!\.)\b(eval|exec)\s*\("
                            description = "Using eval or exec can run arbitrary code, presenting security risks."
                        elif name == "Bare Except" and "except" + ":" in description:
                            description = "Using bare except without specifying an exception class catches system exits and interrupts."
                            
                        presets.append({
                            "name": name,
                            "regex": regex,
                            "description": description,
                            "severity": str(p.get("severity", "warning")),
                            "enabled": bool(p.get("enabled", True)),
                        })
                return {"presets": presets}
        except Exception:
            pass
    return {"presets": list(DEFAULT_ANTI_PATTERNS)}


def save_anti_pattern_config(output_dir: str | Path, config: dict) -> None:
    """Save the updated presets configuration dictionary to file."""
    config_path = Path(output_dir) / ANTI_PATTERN_CONFIG_NAME
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
