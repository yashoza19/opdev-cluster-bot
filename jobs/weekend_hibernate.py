"""Friday evening auto-hibernate for bot-managed clusters (unless opted out)."""

from __future__ import annotations

import logging

from opdev_cluster_bot.acm.inventory import list_clusters
from opdev_cluster_bot.acm.power import PowerError, hibernate_cluster
from opdev_cluster_bot.config import Settings
from jobs._common import configure_logging, is_running, post_or_dm, slack_client

logger = logging.getLogger(__name__)


def run(settings: Settings | None = None) -> int:
    settings = settings or Settings.from_env()
    client = slack_client(settings)
    clusters = list_clusters(settings, bot_managed_only=True)
    hibernated = 0
    skipped = 0
    errors = 0

    for cluster in clusters:
        if not cluster.weekend_hibernate:
            skipped += 1
            logger.info("Skipping %s (weekend hibernate opted out)", cluster.name)
            continue
        power = cluster.power_actual or cluster.power_desired
        if not is_running(power):
            continue
        try:
            hibernate_cluster(cluster.name, settings)
        except PowerError as exc:
            errors += 1
            logger.error("Failed hibernating %s: %s", cluster.name, exc)
            continue
        hibernated += 1
        text = (
            f"Weekend auto-hibernate: requested Hibernating for `{cluster.name}`."
        )
        post_or_dm(
            client,
            channel=settings.reminder_channel or None,
            owner_slack_id=cluster.owner_slack_id,
            text=text,
        )
        logger.info("audit weekend-hibernate cluster=%s", cluster.name)

    logger.info(
        "Weekend hibernate complete hibernated=%s skipped_opt_out=%s errors=%s",
        hibernated,
        skipped,
        errors,
    )
    return 1 if errors else 0


def main() -> None:
    configure_logging()
    raise SystemExit(run())


if __name__ == "__main__":
    main()
