"""Block Kit action handlers."""

from __future__ import annotations

import logging
from typing import Any

from slack_bolt import Ack, BoltContext
from slack_sdk import WebClient

from opdev_cluster_bot.acm.destroy import DestroyError, cluster_for_destroy, destroy_cluster
from opdev_cluster_bot.acm.inventory import get_cluster
from opdev_cluster_bot.acm.power import PowerError, hibernate_cluster, resume_cluster
from opdev_cluster_bot.acm.provision import ProvisionError, ProvisionRequest, provision_cluster
from opdev_cluster_bot.config import Settings
from opdev_cluster_bot.identity import is_authorized, resolve_email

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


def handle_submit_spin_request(
    ack: Ack,
    body: dict[str, Any],
    client: WebClient,
    context: BoltContext,
) -> None:
    ack()
    settings = _settings(context)
    user_id = body.get("user", {}).get("id") or ""
    channel = body.get("channel", {}).get("id") or body.get("container", {}).get("channel_id")
    state = (body.get("state") or {}).get("values") or {}

    version = _state_value(state, "spin_version", "value")
    topology = _state_value(state, "spin_topology", "value")
    region = _state_value(state, "spin_region", "value")
    profile = _state_value(state, "spin_profile", "value")
    cluster_name = (_state_text(state, "spin_name", "value") or "").strip() or None

    if not all([version, topology, region, profile]):
        _notify(client, channel, user_id, "Missing required spin options. Please try again.")
        return
    instance_type = _profile_instance_type(profile, settings)
    if region not in settings.allowed_aws_regions:
        _notify(client, channel, user_id, f"Region `{region}` is not allowed.")
        return

    email = resolve_email(client, user_id)
    _notify(
        client,
        channel,
        user_id,
        f"Starting provision: OCP `{version}` `{topology}` `{instance_type}` in `{region}`"
        + (f" as `{cluster_name}`" if cluster_name else "")
        + (" _(dry-run)_" if settings.dry_run else "")
        + "…",
    )
    try:
        result = provision_cluster(
            ProvisionRequest(
                version=version,
                topology=topology,
                instance_type=instance_type,
                cluster_name=cluster_name,
                owner_slack_id=user_id,
                owner_email=email,
                aws_region=region,
            ),
            settings,
        )
    except ProvisionError as exc:
        _notify(client, channel, user_id, f"Provision failed: {exc}")
        return

    logger.info(
        "audit spin user=%s cluster=%s dry_run=%s profile=%s region=%s",
        user_id,
        result.cluster_name,
        result.dry_run,
        profile,
        region,
    )
    if channel:
        client.chat_postMessage(channel=channel, text=result.message)
    else:
        _notify(client, channel, user_id, result.message)


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


def _state_value(state: dict[str, Any], block_id: str, action_id: str) -> str | None:
    element = ((state.get(block_id) or {}).get(action_id) or {})
    if "selected_option" in element:
        return ((element.get("selected_option") or {}).get("value")) or None
    if "selected_options" in element:
        options = element.get("selected_options") or []
        if options:
            return options[0].get("value")
    return None


def _state_text(state: dict[str, Any], block_id: str, action_id: str) -> str | None:
    element = ((state.get(block_id) or {}).get(action_id) or {})
    return element.get("value")


def _profile_instance_type(profile: str, settings: Settings) -> str:
    profile_key = profile.strip().lower()
    if profile_key == "virt":
        return settings.profile_virt_instance_type
    if profile_key == "ai":
        return settings.profile_ai_instance_type
    return settings.profile_base_instance_type
