"""Block Kit action handlers."""

from __future__ import annotations

import logging
from typing import Any

from slack_bolt import Ack, BoltContext
from slack_sdk import WebClient

from opdev_cluster_bot.acm.destroy import DestroyError, cluster_for_destroy, destroy_cluster
from opdev_cluster_bot.acm.inventory import get_cluster
from opdev_cluster_bot.acm.power import PowerError, hibernate_cluster, resume_cluster
from opdev_cluster_bot.config import Settings
from opdev_cluster_bot.identity import is_authorized

logger = logging.getLogger(__name__)


def _settings(context: BoltContext) -> Settings:
    return context.get("settings") or Settings.from_env()


def handle_confirm_hibernate(
    ack: Ack,
    body: dict[str, Any],
    client: WebClient,
    context: BoltContext,
) -> None:
    ack()
    _apply_power(body, client, context, verb="hibernate", apply=hibernate_cluster)


def handle_confirm_resume(
    ack: Ack,
    body: dict[str, Any],
    client: WebClient,
    context: BoltContext,
) -> None:
    ack()
    _apply_power(body, client, context, verb="resume", apply=resume_cluster)


def handle_confirm_destroy(
    ack: Ack,
    body: dict[str, Any],
    client: WebClient,
    context: BoltContext,
) -> None:
    ack()
    settings = _settings(context)
    user_id = body.get("user", {}).get("id") or ""
    channel = body.get("channel", {}).get("id") or body.get("container", {}).get("channel_id")
    actions = body.get("actions") or []
    cluster_name = (actions[0].get("value") if actions else None) or ""
    if not cluster_name:
        return

    info = cluster_for_destroy(cluster_name, settings)
    if info is None:
        _notify(client, channel, user_id, f"Cluster `{cluster_name}` not found.")
        return
    if not info.managed_by_bot:
        _notify(
            client,
            channel,
            user_id,
            f"Refusing to destroy `{info.name}`: not managed by this bot.",
        )
        return
    if not is_authorized(
        actor_slack_id=user_id,
        owner_slack_id=info.owner_slack_id,
        settings=settings,
        client=client,
    ):
        _notify(client, channel, user_id, f"Not authorized to destroy `{info.name}`.")
        return

    try:
        result = destroy_cluster(info.name, settings)
    except DestroyError as exc:
        _notify(client, channel, user_id, str(exc))
        return

    logger.info("audit destroy user=%s cluster=%s", user_id, result.cluster_name)
    text = f"Cluster `{result.cluster_name}` will be deleted by <@{user_id}>."
    if result.dry_run:
        text = f"Dry-run: cluster `{result.cluster_name}` would be deleted by <@{user_id}>."
    if channel:
        client.chat_postMessage(channel=channel, text=text)
    else:
        _notify(client, channel, user_id, text)


def handle_cancel_power_action(
    ack: Ack,
    body: dict[str, Any],
    client: WebClient,
) -> None:
    ack()
    user_id = body.get("user", {}).get("id")
    channel = body.get("channel", {}).get("id") or body.get("container", {}).get("channel_id")
    if channel and user_id:
        client.chat_postEphemeral(channel=channel, user=user_id, text="Cancelled.")


def _apply_power(
    body: dict[str, Any],
    client: WebClient,
    context: BoltContext,
    *,
    verb: str,
    apply,
) -> None:
    settings = _settings(context)
    user_id = body.get("user", {}).get("id") or ""
    channel = body.get("channel", {}).get("id") or body.get("container", {}).get("channel_id")
    actions = body.get("actions") or []
    cluster_name = (actions[0].get("value") if actions else None) or ""

    if not cluster_name:
        return

    info = get_cluster(cluster_name, settings)
    if info is None:
        _notify(client, channel, user_id, f"Cluster `{cluster_name}` not found.")
        return
    if not is_authorized(
        actor_slack_id=user_id,
        owner_slack_id=info.owner_slack_id,
        settings=settings,
        client=client,
    ):
        _notify(client, channel, user_id, f"Not authorized to {verb} `{cluster_name}`.")
        return

    try:
        updated = apply(cluster_name, settings)
    except PowerError as exc:
        _notify(client, channel, user_id, str(exc))
        return

    logger.info("audit %s user=%s cluster=%s", verb, user_id, cluster_name)
    text = (
        f"{verb.title()} requested for `{updated.name}`. "
        f"Power state: desired=`{updated.power_desired}` actual=`{updated.power_actual}`."
    )
    if channel:
        client.chat_postMessage(channel=channel, text=text)
    else:
        _notify(client, channel, user_id, text)


def _notify(client: WebClient, channel: str | None, user_id: str, text: str) -> None:
    if channel and user_id:
        client.chat_postEphemeral(channel=channel, user=user_id, text=text)
    elif user_id:
        client.chat_postMessage(channel=user_id, text=text)
