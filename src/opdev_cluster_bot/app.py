"""Slack Bolt Socket Mode entrypoint."""

from __future__ import annotations

import logging
import sys

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from opdev_cluster_bot.actions import (
    handle_cancel_power_action,
    handle_confirm_destroy,
    handle_confirm_hibernate,
    handle_confirm_resume,
)
from opdev_cluster_bot.commands import handle_opdev_command
from opdev_cluster_bot.config import Settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> App:
    settings = settings or Settings.from_env()
    if not settings.slack_bot_token:
        raise SystemExit("SLACK_BOT_TOKEN is required")

    app = App(token=settings.slack_bot_token)

    @app.middleware
    def inject_settings(context, next):
        context["settings"] = settings
        next()

    app.command("/opdev-cluster-bot")(handle_opdev_command)
    app.action("confirm_hibernate")(handle_confirm_hibernate)
    app.action("confirm_resume")(handle_confirm_resume)
    app.action("confirm_destroy")(handle_confirm_destroy)
    app.action("cancel_power_action")(handle_cancel_power_action)
    return app


def main() -> None:
    settings = Settings.from_env()
    if not settings.slack_app_token:
        raise SystemExit("SLACK_APP_TOKEN is required for Socket Mode")
    app = create_app(settings)
    logger.info(
        "Starting opdev-cluster-bot (Socket Mode) dry_run=%s region=%s",
        settings.dry_run,
        settings.aws_region,
    )
    SocketModeHandler(app, settings.slack_app_token).start()


if __name__ == "__main__":
    main()
