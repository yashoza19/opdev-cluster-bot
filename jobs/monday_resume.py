"""Monday morning resume for bot-managed clusters that participate in weekend hibernate."""

from __future__ import annotations

import logging

from opdev_cluster_bot.acm.inventory import list_clusters
from opdev_cluster_bot.acm.power import PowerError, resume_cluster
from opdev_cluster_bot.config import Settings
from jobs._common import configure_logging, is_hibernating, post_or_dm, slack_client

logger = logging.getLogger(__name__)


def run(settings: Settings | None = None) -> int:
    settings = settings or Settings.from_env()
    client = slack_client(settings)
    clusters = list_clusters(settings, bot_managed_only=True)
    resumed = 0
    skipped = 0
    errors = 0

    for cluster in clusters:
        if not cluster.weekend_hibernate:
            skipped += 1
            continue
        power = cluster.power_actual or cluster.power_desired
        if not is_hibernating(power):
            continue
        try:
            resume_cluster(cluster.name, settings)
        except PowerError as exc:
            errors += 1
            logger.error("Failed resuming %s: %s", cluster.name, exc)
            continue
        resumed += 1
        text = f"Monday auto-resume: requested Running for `{cluster.name}`."
        post_or_dm(
            client,
            channel=settings.reminder_channel or None,
            owner_slack_id=cluster.owner_slack_id,
            text=text,
        )
        logger.info("audit monday-resume cluster=%s", cluster.name)

    logger.info(
        "Monday resume complete resumed=%s skipped_opt_out=%s errors=%s",
        resumed,
        skipped,
        errors,
    )
    return 1 if errors else 0


def main() -> None:
    configure_logging()
    raise SystemExit(run())


if __name__ == "__main__":
    main()
