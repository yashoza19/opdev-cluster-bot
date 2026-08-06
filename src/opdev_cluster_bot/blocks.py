"""Shared Block Kit helpers."""

from __future__ import annotations


HELP_TEXT = """*opdev-cluster-bot* — ACM/Hive cluster helper

• `/opdev-cluster-bot list` — list clusters and power state
• `/opdev-cluster-bot spin <version> <SNO|multinode> <instance-type> [name]` — provision on AWS
• `/opdev-cluster-bot hibernate <name>` — confirm then hibernate
• `/opdev-cluster-bot resume <name>` — confirm then resume
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
