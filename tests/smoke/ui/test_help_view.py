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
"""Smoke tests for the HelpDialog view component."""

from __future__ import annotations

from app.views.help_view import HelpDialog, HELP_TOPICS


def test_help_dialog_initialization(qtbot) -> None:
    """Verify that the HelpDialog instantiates and populates all topics."""
    dialog = HelpDialog()
    qtbot.addWidget(dialog)

    # Check topic list counts
    assert dialog.topic_list.count() == len(HELP_TOPICS)

    # Verify first topic is selected by default
    first_topic_name = list(HELP_TOPICS.keys())[0]
    assert dialog.topic_list.currentItem().text() == first_topic_name
    assert "The Librarian" in dialog.text_browser.toPlainText()


def test_help_dialog_topic_switching(qtbot) -> None:
    """Verify selecting a topic in the list updates the browser content."""
    dialog = HelpDialog()
    qtbot.addWidget(dialog)

    # Select the second topic
    assert dialog.topic_list.count() > 1
    second_topic_name = list(HELP_TOPICS.keys())[1]
    
    dialog.topic_list.setCurrentRow(1)
    
    assert dialog.topic_list.currentItem().text() == second_topic_name
    assert "Search & Navigation" in dialog.text_browser.toPlainText()


def test_help_dialog_filter_topics(qtbot) -> None:
    """Verify that search/filter input correctly reduces the topic list."""
    dialog = HelpDialog()
    qtbot.addWidget(dialog)

    # Let's search for "Shortcuts" (should match "Preferences & Shortcuts")
    dialog.search_input.setText("Shortcuts")
    
    # Check that only matching topics are in the list
    matching_count = dialog.topic_list.count()
    assert matching_count > 0
    assert matching_count < len(HELP_TOPICS)
    
    for i in range(matching_count):
        item = dialog.topic_list.item(i)
        assert "shortcuts" in item.text().lower() or "shortcuts" in HELP_TOPICS[item.text()].lower()

