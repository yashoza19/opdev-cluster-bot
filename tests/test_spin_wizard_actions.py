"""Unit tests for spin wizard action helpers."""

from opdev_cluster_bot.actions import _profile_instance_type, _state_text, _state_value
from opdev_cluster_bot.config import Settings


def test_profile_instance_type_mapping():
    settings = Settings(
        profile_base_instance_type="m5.4xlarge",
        profile_virt_instance_type="m5.metal",
        profile_ai_instance_type="g5.4xlarge",
    )
    assert _profile_instance_type("base", settings) == "m5.4xlarge"
    assert _profile_instance_type("virt", settings) == "m5.metal"
    assert _profile_instance_type("ai", settings) == "g5.4xlarge"


def test_state_value_and_text_helpers():
    state = {
        "spin_region": {
            "value": {
                "selected_option": {"value": "us-east-1"},
            }
        },
        "spin_name": {
            "value": {
                "value": "team-a",
            }
        },
    }
    assert _state_value(state, "spin_region", "value") == "us-east-1"
    assert _state_text(state, "spin_name", "value") == "team-a"
