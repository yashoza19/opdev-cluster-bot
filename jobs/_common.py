"""Shared helpers for CronJob scripts."""

from __future__ import annotations

import logging
import sys

from slack_sdk import WebClient

from opdev_cluster_bot.config import Settings

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )


def slack_client(settings: Settings) -> WebClient:
    if not settings.slack_bot_token:
        raise SystemExit("SLACK_BOT_TOKEN is required")
    return WebClient(token=settings.slack_bot_token)


def is_running(power: str | None) -> bool:
    return (power or "Running") == "Running"


def is_hibernating(power: str | None) -> bool:
    return (power or "") in {"Hibernating", "Stopping"}


def post_or_dm(
    client: WebClient,
    *,
    channel: str | None,
    owner_slack_id: str | None,
    text: str,
    blocks: list[dict] | None = None,
) -> None:
    target = channel or owner_slack_id
    if not target:
        logger.warning("No REMINDER_CHANNEL or owner Slack ID; skipping message: %s", text)
        return
    if channel:
        client.chat_postMessage(channel=channel, text=text, blocks=blocks)
        return
    # Open IM then post
    opened = client.conversations_open(users=[owner_slack_id])
    dm = opened["channel"]["id"]
    client.chat_postMessage(channel=dm, text=text, blocks=blocks)
