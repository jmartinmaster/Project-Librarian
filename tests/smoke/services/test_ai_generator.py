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
"""Smoke tests for the AI generation and triad method propagation service."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from app.models.ai_generator import AIGenerationService


def test_ai_generator_scans_and_replaces(tmp_path, monkeypatch):
    """Test that AIGenerationService successfully detects #AI-request, calls AI, and updates all triad files."""
    m_file = tmp_path / "book_model.py"
    v_file = tmp_path / "book_view.py"
    c_file = tmp_path / "book_controller.py"

    m_file.write_text("class BookModel:\n    pass\n", encoding="utf-8")
    v_file.write_text("class BookView:\n    # AI-request: add a refresh button to clear list\n    pass\n", encoding="utf-8")
    c_file.write_text("class BookController:\n    pass\n", encoding="utf-8")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def read(self):
            inner_dict = {
                "model_imports": "import sys",
                "model_additions": "    def reset(self):\n        pass",
                "view_imports": "",
                "view_additions": "",
                "controller_imports": "",
                "controller_additions": "    def handle_reset(self):\n        pass"
            }
            outer_dict = {
                "response": json.dumps(inner_dict)
            }
            return json.dumps(outer_dict).encode("utf-8")

    def mock_urlopen(req, *args, **kwargs):
        if hasattr(req, "full_url") and "/api/tags" in req.full_url:
            class FakeTags:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

                def read(self):
                    return b'{"models": [{"name": "qwen2.5-coder:7b"}]}'
            return FakeTags()
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    generator = AIGenerationService()
    ok, msg = generator.process_triad(str(m_file), str(v_file), str(c_file))

    assert ok, msg
    assert "completed successfully" in msg

    m_content = m_file.read_text(encoding="utf-8")
    v_content = v_file.read_text(encoding="utf-8")
    c_content = c_file.read_text(encoding="utf-8")

    assert "import sys" in m_content
    assert "def reset(self):" in m_content
    assert "AI-addition" in v_content
    assert "AI-request" not in v_content
    assert "def handle_reset(self):" in c_content

