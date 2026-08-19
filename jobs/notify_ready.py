"""Poll for installed clusters and DM owners their admin credentials."""

from __future__ import annotations

import logging

from opdev_cluster_bot.acm.credentials import CredentialsError, clusters_pending_creds_notification, notify_cluster_ready
from opdev_cluster_bot.config import Settings
from jobs._common import configure_logging, slack_client

logger = logging.getLogger(__name__)


def run(settings: Settings | None = None) -> int:
    settings = settings or Settings.from_env()
    client = slack_client(settings)
    pending = clusters_pending_creds_notification(settings)
    errors = 0

    for info in pending:
        try:
            notify_cluster_ready(info, client, settings)
            logger.info("audit creds-notified cluster=%s owner=%s", info.name, info.owner_slack_id)
        except CredentialsError as exc:
            errors += 1
            logger.error("Credentials notify failed for %s: %s", info.name, exc)
        except Exception:
            errors += 1
            logger.exception("Unexpected error notifying %s", info.name)

    logger.info(
        "Notify-ready complete pending=%s errors=%s dry_run=%s",
        len(pending),
        errors,
        settings.dry_run,
    )
    return 1 if errors else 0


def main() -> None:
    configure_logging()
    raise SystemExit(run())


if __name__ == "__main__":
    main()
