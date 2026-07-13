# Copyright (C) 2026 Project Librarian contributors
#
# This file is part of Project Librarian.
#
# Project Librarian is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Project Librarian is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Project Librarian. If not, see <https://www.gnu.org/licenses/>.

"""Smoke tests for local AI integration and AIRequestWorker."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from app.views.mvc_sync.worker import AIRequestWorker


def test_ai_request_worker_success() -> None:
    """Test AIRequestWorker handles successful Ollama responses."""
    url = "http://localhost:11434/api/generate"
    model = "test-model"
    source_code = "def hello():\n    #AI-request: add a name argument\n    pass"
    instruction = "add a name argument"
    expected_response = "def hello(name):\n    pass"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": expected_response}

    success_signal_received: list[str] = []
    finished_signal_received: list[bool] = []

    worker = AIRequestWorker(url, model, source_code, instruction)
    worker.success.connect(success_signal_received.append)
    worker.finished.connect(lambda: finished_signal_received.append(True))

    with patch("requests.post", return_value=mock_response) as mock_post:
        worker.run()
        
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] in [url, "http://127.0.0.1:11434/api/generate"]
        assert kwargs["json"]["model"] == model
        assert instruction in kwargs["json"]["prompt"]

    assert success_signal_received == [expected_response]
    assert finished_signal_received == [True]


def test_ai_request_worker_refused() -> None:
    """Test AIRequestWorker handles refusal message correctly."""
    url = "http://localhost:11434/api/generate"
    model = "test-model"
    source_code = "def hello():\n    #AI-request: bake a cake\n    pass"
    instruction = "bake a cake"
    refusal_response = "I cannot fulfill this request."

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": refusal_response}

    refused_signal_received: list[str] = []
    finished_signal_received: list[bool] = []

    worker = AIRequestWorker(url, model, source_code, instruction)
    worker.refused.connect(refused_signal_received.append)
    worker.finished.connect(lambda: finished_signal_received.append(True))

    with patch("requests.post", return_value=mock_response) as mock_post:
        worker.run()

    assert len(refused_signal_received) == 1
    assert "cannot fulfill" in refused_signal_received[0]
    assert finished_signal_received == [True]


def test_ai_request_worker_error() -> None:
    """Test AIRequestWorker handles connection or HTTP errors."""
    url = "http://localhost:11434/api/generate"
    model = "test-model"
    source_code = "pass"
    instruction = "test"

    error_signal_received: list[str] = []
    finished_signal_received: list[bool] = []

    worker = AIRequestWorker(url, model, source_code, instruction)
    worker.error.connect(error_signal_received.append)
    worker.finished.connect(lambda: finished_signal_received.append(True))

    with patch("requests.post", side_effect=Exception("Connection refused")):
        worker.run()

    assert len(error_signal_received) == 1
    assert "Connection refused" in error_signal_received[0]
    assert finished_signal_received == [True]
