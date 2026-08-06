"""Unit tests for Block Kit helpers and job power filters."""

from jobs._common import is_hibernating, is_running
from opdev_cluster_bot.blocks import HELP_TEXT, confirm_power_blocks, hibernate_reminder_blocks


def test_help_text_mentions_spin():
    assert "spin" in HELP_TEXT
    assert "keep-weekend" in HELP_TEXT


def test_confirm_power_blocks():
    blocks = confirm_power_blocks(action_id="confirm_hibernate", cluster_name="opdev-a", verb="hibernate")
    assert blocks[0]["type"] == "section"
    assert blocks[1]["elements"][0]["action_id"] == "confirm_hibernate"
    assert blocks[1]["elements"][0]["value"] == "opdev-a"


def test_hibernate_reminder_blocks():
    blocks = hibernate_reminder_blocks("opdev-b")
    assert "opdev-b" in blocks[0]["text"]["text"]
    assert blocks[1]["elements"][0]["action_id"] == "confirm_hibernate"


def test_power_filters():
    assert is_running("Running") is True
    assert is_running(None) is True
    assert is_running("Hibernating") is False
    assert is_hibernating("Hibernating") is True
    assert is_hibernating("Stopping") is True
    assert is_hibernating("Running") is False
