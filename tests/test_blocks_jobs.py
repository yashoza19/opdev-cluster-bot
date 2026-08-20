"""Unit tests for Block Kit helpers and job power filters."""

from jobs._common import is_hibernating, is_running
from opdev_cluster_bot.blocks import (
    HELP_TEXT,
    confirm_power_blocks,
    hibernate_reminder_blocks,
    spin_wizard_blocks,
)


def test_help_text_mentions_spin():
    assert "spin" in HELP_TEXT
    assert "keep-weekend" in HELP_TEXT
    assert "destroy" in HELP_TEXT


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


def test_spin_wizard_blocks():
    blocks = spin_wizard_blocks(
        versions=["4.22.8", "4.22.7"],
        regions=["us-east-1", "us-west-2"],
        default_region="us-east-1",
        base_instance="m5.4xlarge",
        virt_instance="m5.metal",
        ai_instance="g5.2xlarge",
    )
    assert any(b.get("block_id") == "spin_version" for b in blocks)
    assert any(b.get("block_id") == "spin_region" for b in blocks)
    assert any(b.get("block_id") == "spin_profile" for b in blocks)
    action_block = [b for b in blocks if b.get("type") == "actions"][0]
    assert action_block["elements"][0]["action_id"] == "submit_spin_request"
