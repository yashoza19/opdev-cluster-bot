"""Weekday EOD hibernate reminders for Running bot-managed clusters."""

from __future__ import annotations

import logging

from opdev_cluster_bot.acm.inventory import list_clusters
from opdev_cluster_bot.blocks import hibernate_reminder_blocks
from opdev_cluster_bot.config import Settings
from jobs._common import configure_logging, is_running, post_or_dm, slack_client

logger = logging.getLogger(__name__)


def run(settings: Settings | None = None) -> int:
    settings = settings or Settings.from_env()
    client = slack_client(settings)
    clusters = list_clusters(settings, bot_managed_only=True)
    reminded = 0
    for cluster in clusters:
        power = cluster.power_actual or cluster.power_desired
        if not is_running(power):
            continue
        text = (
            f"End of day reminder: `{cluster.name}` is still Running. "
            "Hibernate it to save cost?"
        )
        blocks = hibernate_reminder_blocks(cluster.name)
        if cluster.owner_slack_id and not settings.reminder_channel:
            mention = f"<@{cluster.owner_slack_id}> "
            text = mention + text
        post_or_dm(
            client,
            channel=settings.reminder_channel or None,
            owner_slack_id=cluster.owner_slack_id,
            text=text,
            blocks=blocks,
        )
        reminded += 1
        logger.info("Reminded about cluster %s owner=%s", cluster.name, cluster.owner_slack_id)
    logger.info("Hibernate reminders sent: %s", reminded)
    return 0


def main() -> None:
    configure_logging()
    raise SystemExit(run())


if __name__ == "__main__":
    main()
