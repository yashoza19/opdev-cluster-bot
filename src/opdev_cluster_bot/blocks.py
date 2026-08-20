"""Shared Block Kit helpers."""

from __future__ import annotations


HELP_TEXT = """*opdev-cluster-bot* — ACM/Hive cluster helper

• `/opdev-cluster-bot list` — list clusters and power state
• `/opdev-cluster-bot spin` — interactive provision wizard (region/profile/topology/version)
• `/opdev-cluster-bot spin <version> <SNO|multinode> <instance-type> [name]` — advanced direct provision
• `/opdev-cluster-bot hibernate <name>` — confirm then hibernate
• `/opdev-cluster-bot resume <name>` — confirm then resume
• `/opdev-cluster-bot destroy <name>` — confirm then deprovision (AWS teardown)
• `/opdev-cluster-bot status <name>` — cluster details
• `/opdev-cluster-bot keep-weekend <name>` — skip weekend auto-hibernate
• `/opdev-cluster-bot help` — this message
"""



def confirm_power_blocks(*, action_id: str, cluster_name: str, verb: str) -> list[dict]:
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Confirm *{verb}* for cluster `{cluster_name}`?",
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": verb.title()},
                    "style": "danger" if verb == "hibernate" else "primary",
                    "action_id": action_id,
                    "value": cluster_name,
                    "confirm": {
                        "title": {"type": "plain_text", "text": f"Confirm {verb}"},
                        "text": {
                            "type": "mrkdwn",
                            "text": f"Are you sure you want to {verb} `{cluster_name}`?",
                        },
                        "confirm": {"type": "plain_text", "text": verb.title()},
                        "deny": {"type": "plain_text", "text": "Cancel"},
                    },
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Cancel"},
                    "action_id": "cancel_power_action",
                    "value": cluster_name,
                },
            ],
        },
    ]


def confirm_destroy_blocks(*, cluster_name: str) -> list[dict]:
    """Destructive confirm: danger button + Slack confirm dialog (double confirm)."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"Destroy cluster `{cluster_name}`? This cannot be undone."
                ),
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Destroy"},
                    "style": "danger",
                    "action_id": "confirm_destroy",
                    "value": cluster_name,
                    "confirm": {
                        "title": {"type": "plain_text", "text": "Confirm destroy"},
                        "text": {
                            "type": "mrkdwn",
                            "text": f"Delete `{cluster_name}`?",
                        },
                        "confirm": {"type": "plain_text", "text": "Destroy"},
                        "deny": {"type": "plain_text", "text": "Cancel"},
                    },
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Cancel"},
                    "action_id": "cancel_power_action",
                    "value": cluster_name,
                },
            ],
        },
    ]


def hibernate_reminder_blocks(cluster_name: str) -> list[dict]:
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"End of day reminder: cluster `{cluster_name}` is still *Running*. "
                    "Hibernate it to save cost?"
                ),
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Hibernate"},
                    "style": "danger",
                    "action_id": "confirm_hibernate",
                    "value": cluster_name,
                    "confirm": {
                        "title": {"type": "plain_text", "text": "Confirm hibernate"},
                        "text": {
                            "type": "mrkdwn",
                            "text": f"Hibernate `{cluster_name}` now?",
                        },
                        "confirm": {"type": "plain_text", "text": "Hibernate"},
                        "deny": {"type": "plain_text", "text": "Cancel"},
                    },
                }
            ],
        },
    ]


def spin_wizard_blocks(
    *,
    versions: list[str],
    regions: list[str],
    default_region: str,
    base_instance: str,
    virt_instance: str,
    ai_instance: str,
) -> list[dict]:
    version_options = [
        {"text": {"type": "plain_text", "text": v}, "value": v}
        for v in versions[:15]
    ]
    region_options = [
        {"text": {"type": "plain_text", "text": r}, "value": r}
        for r in regions
    ]
    profile_options = [
        {"text": {"type": "plain_text", "text": f"base ({base_instance})"}, "value": "base"},
        {"text": {"type": "plain_text", "text": f"virt ({virt_instance})"}, "value": "virt"},
        {"text": {"type": "plain_text", "text": f"ai ({ai_instance})"}, "value": "ai"},
    ]
    topology_options = [
        {"text": {"type": "plain_text", "text": "SNO"}, "value": "SNO"},
        {"text": {"type": "plain_text", "text": "multinode"}, "value": "multinode"},
    ]
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Select cluster options, then click *Start provision*.",
            },
        },
        {
            "type": "section",
            "block_id": "spin_version",
            "text": {"type": "mrkdwn", "text": "*OpenShift version*"},
            "accessory": {
                "type": "static_select",
                "action_id": "value",
                "options": version_options,
                "initial_option": version_options[0] if version_options else None,
            },
        },
        {
            "type": "section",
            "block_id": "spin_topology",
            "text": {"type": "mrkdwn", "text": "*Topology*"},
            "accessory": {
                "type": "static_select",
                "action_id": "value",
                "options": topology_options,
                "initial_option": topology_options[0],
            },
        },
        {
            "type": "section",
            "block_id": "spin_region",
            "text": {"type": "mrkdwn", "text": "*AWS region*"},
            "accessory": {
                "type": "static_select",
                "action_id": "value",
                "options": region_options,
                "initial_option": next(
                    (o for o in region_options if o["value"] == default_region),
                    region_options[0],
                ),
            },
        },
        {
            "type": "section",
            "block_id": "spin_profile",
            "text": {"type": "mrkdwn", "text": "*Workload profile*"},
            "accessory": {
                "type": "static_select",
                "action_id": "value",
                "options": profile_options,
                "initial_option": profile_options[0],
            },
        },
        {
            "type": "section",
            "block_id": "spin_name",
            "text": {"type": "mrkdwn", "text": "*Cluster name (optional)*"},
            "accessory": {
                "type": "plain_text_input",
                "action_id": "value",
                "placeholder": {"type": "plain_text", "text": "example: team-sno-1"},
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Start provision"},
                    "style": "primary",
                    "action_id": "submit_spin_request",
                    "value": "spin_wizard",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Cancel"},
                    "action_id": "cancel_power_action",
                    "value": "spin_wizard",
                },
            ],
        },
    ]
