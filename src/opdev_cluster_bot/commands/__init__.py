"""Slash command router for /opdev-cluster-bot."""

from __future__ import annotations

import logging
import shlex
from typing import Any

from slack_bolt import Ack, BoltContext, Say
from slack_sdk import WebClient

from opdev_cluster_bot.acm.inventory import get_cluster, list_clusters
from opdev_cluster_bot.acm.power import PowerError, set_weekend_opt_out
from opdev_cluster_bot.acm.provision import ProvisionError, ProvisionRequest, provision_cluster
from opdev_cluster_bot.blocks import HELP_TEXT, confirm_power_blocks
from opdev_cluster_bot.config import Settings
from opdev_cluster_bot.identity import is_authorized, resolve_email

logger = logging.getLogger(__name__)


def _settings(context: BoltContext) -> Settings:
    return context.get("settings") or Settings.from_env()


def handle_opdev_command(
    ack: Ack,
    command: dict[str, Any],
    say: Say,
    client: WebClient,
    context: BoltContext,
) -> None:
    ack()
    text = (command.get("text") or "").strip()
    user_id = command.get("user_id") or ""
    channel_id = command.get("channel_id") or ""
    response_url = command.get("response_url")

    try:
        parts = shlex.split(text) if text else []
    except ValueError:
        _reply(client, channel_id, user_id, "Could not parse arguments. Try `/opdev-cluster-bot help`.", response_url)
        return

    sub = parts[0].lower() if parts else "help"
    args = parts[1:]
    settings = _settings(context)

    handlers = {
        "help": _cmd_help,
        "list": _cmd_list,
        "spin": _cmd_spin,
        "hibernate": _cmd_hibernate,
        "resume": _cmd_resume,
        "status": _cmd_status,
        "keep-weekend": _cmd_keep_weekend,
    }
    handler = handlers.get(sub)
    if handler is None:
        _reply(
            client,
            channel_id,
            user_id,
            f"Unknown subcommand `{sub}`. Try `/opdev-cluster-bot help`.",
            response_url,
        )
        return

    try:
        handler(
            args=args,
            user_id=user_id,
            channel_id=channel_id,
            client=client,
            settings=settings,
            response_url=response_url,
            say=say,
        )
    except Exception:
        logger.exception("Command %s failed for user %s", sub, user_id)
        _reply(client, channel_id, user_id, f"Command `{sub}` failed. Check bot logs.", response_url)


def _reply(
    client: WebClient,
    channel_id: str,
    user_id: str,
    text: str,
    response_url: str | None = None,
    *,
    blocks: list[dict] | None = None,
) -> None:
    if response_url:
        try:
            from slack_sdk.webhook import WebhookClient

            WebhookClient(response_url).send(text=text, blocks=blocks, response_type="ephemeral")
            return
        except Exception:
            logger.exception("response_url post failed; falling back to chat API")
    kwargs: dict[str, Any] = {
        "channel": channel_id,
        "user": user_id,
        "text": text,
    }
    if blocks:
        kwargs["blocks"] = blocks
    client.chat_postEphemeral(**kwargs)


def _cmd_help(**kwargs: Any) -> None:
    _reply(kwargs["client"], kwargs["channel_id"], kwargs["user_id"], HELP_TEXT, kwargs.get("response_url"))


def _cmd_list(**kwargs: Any) -> None:
    settings: Settings = kwargs["settings"]
    clusters = list_clusters(settings)
    if not clusters:
        _reply(
            kwargs["client"],
            kwargs["channel_id"],
            kwargs["user_id"],
            "No managed clusters found (excluding `local-cluster`).",
            kwargs.get("response_url"),
        )
        return
    lines = ["*Managed clusters*", "```"]
    lines.append(f"{'NAME':24} {'POWER':14} {'VERSION':10} TOPOLOGY")
    for c in clusters:
        power = (c.power_actual or c.power_desired or "?")[:14]
        version = (c.version or "?")[:10]
        topo = c.topology or "?"
        lines.append(f"{c.name[:24]:24} {power:14} {version:10} {topo}")
    lines.append("```")
    _reply(
        kwargs["client"],
        kwargs["channel_id"],
        kwargs["user_id"],
        "\n".join(lines),
        kwargs.get("response_url"),
    )


def _cmd_spin(**kwargs: Any) -> None:
    args: list[str] = kwargs["args"]
    if len(args) < 3:
        _reply(
            kwargs["client"],
            kwargs["channel_id"],
            kwargs["user_id"],
            "Usage: `/opdev-cluster-bot spin <version> <SNO|multinode> <instance-type> [name]`",
            kwargs.get("response_url"),
        )
        return

    version, topology, instance_type = args[0], args[1], args[2]
    name = args[3] if len(args) > 3 else None
    user_id = kwargs["user_id"]
    client: WebClient = kwargs["client"]
    settings: Settings = kwargs["settings"]
    email = resolve_email(client, user_id)

    _reply(
        client,
        kwargs["channel_id"],
        user_id,
        f"Starting provision: OCP `{version}` `{topology}` `{instance_type}`"
        + (f" as `{name}`" if name else "")
        + (" _(dry-run)_" if settings.dry_run else "")
        + "…",
        kwargs.get("response_url"),
    )

    try:
        result = provision_cluster(
            ProvisionRequest(
                version=version,
                topology=topology,
                instance_type=instance_type,
                cluster_name=name,
                owner_slack_id=user_id,
                owner_email=email,
            ),
            settings,
        )
    except ProvisionError as exc:
        _reply(client, kwargs["channel_id"], user_id, f"Provision failed: {exc}", kwargs.get("response_url"))
        return

    logger.info(
        "audit spin user=%s cluster=%s dry_run=%s",
        user_id,
        result.cluster_name,
        result.dry_run,
    )
    msg = result.message
    if result.dry_run and result.manifests:
        kinds = ", ".join(f"{m.get('kind')}" for m in result.manifests)
        msg += f"\nManifests: {kinds}"
    client.chat_postMessage(channel=kwargs["channel_id"], text=msg)


def _cmd_hibernate(**kwargs: Any) -> None:
    _power_confirm(verb="hibernate", action_id="confirm_hibernate", **kwargs)


def _cmd_resume(**kwargs: Any) -> None:
    _power_confirm(verb="resume", action_id="confirm_resume", **kwargs)


def _power_confirm(*, verb: str, action_id: str, **kwargs: Any) -> None:
    args: list[str] = kwargs["args"]
    if len(args) != 1:
        _reply(
            kwargs["client"],
            kwargs["channel_id"],
            kwargs["user_id"],
            f"Usage: `/opdev-cluster-bot {verb} <name>`",
            kwargs.get("response_url"),
        )
        return
    name = args[0]
    info = get_cluster(name, kwargs["settings"])
    if info is None:
        _reply(
            kwargs["client"],
            kwargs["channel_id"],
            kwargs["user_id"],
            f"Cluster `{name}` not found.",
            kwargs.get("response_url"),
        )
        return
    if not is_authorized(
        actor_slack_id=kwargs["user_id"],
        owner_slack_id=info.owner_slack_id,
        settings=kwargs["settings"],
        client=kwargs["client"],
    ):
        _reply(
            kwargs["client"],
            kwargs["channel_id"],
            kwargs["user_id"],
            f"Not authorized to {verb} `{name}`.",
            kwargs.get("response_url"),
        )
        return
    blocks = confirm_power_blocks(action_id=action_id, cluster_name=name, verb=verb)
    _reply(
        kwargs["client"],
        kwargs["channel_id"],
        kwargs["user_id"],
        f"Confirm {verb} for `{name}`",
        kwargs.get("response_url"),
        blocks=blocks,
    )


def _cmd_status(**kwargs: Any) -> None:
    args: list[str] = kwargs["args"]
    if len(args) != 1:
        _reply(
            kwargs["client"],
            kwargs["channel_id"],
            kwargs["user_id"],
            "Usage: `/opdev-cluster-bot status <name>`",
            kwargs.get("response_url"),
        )
        return
    info = get_cluster(args[0], kwargs["settings"])
    if info is None:
        _reply(
            kwargs["client"],
            kwargs["channel_id"],
            kwargs["user_id"],
            f"Cluster `{args[0]}` not found.",
            kwargs.get("response_url"),
        )
        return
    text = (
        f"*Cluster `{info.name}`*\n"
        f"• Namespace: `{info.namespace}`\n"
        f"• Power desired/actual: `{info.power_desired}` / `{info.power_actual}`\n"
        f"• Installed: `{info.installed}`\n"
        f"• Available: `{info.available}`\n"
        f"• Version: `{info.version}`\n"
        f"• Topology: `{info.topology}`\n"
        f"• Instance type: `{info.instance_type}`\n"
        f"• Owner: `{info.owner_email or info.owner_slack_id or 'n/a'}`\n"
        f"• Weekend hibernate: `{info.weekend_hibernate}`\n"
        f"• Bot-managed: `{info.managed_by_bot}`"
    )
    _reply(kwargs["client"], kwargs["channel_id"], kwargs["user_id"], text, kwargs.get("response_url"))


def _cmd_keep_weekend(**kwargs: Any) -> None:
    args: list[str] = kwargs["args"]
    if len(args) != 1:
        _reply(
            kwargs["client"],
            kwargs["channel_id"],
            kwargs["user_id"],
            "Usage: `/opdev-cluster-bot keep-weekend <name>`",
            kwargs.get("response_url"),
        )
        return
    name = args[0]
    info = get_cluster(name, kwargs["settings"])
    if info is None:
        _reply(
            kwargs["client"],
            kwargs["channel_id"],
            kwargs["user_id"],
            f"Cluster `{name}` not found.",
            kwargs.get("response_url"),
        )
        return
    if not is_authorized(
        actor_slack_id=kwargs["user_id"],
        owner_slack_id=info.owner_slack_id,
        settings=kwargs["settings"],
        client=kwargs["client"],
    ):
        _reply(
            kwargs["client"],
            kwargs["channel_id"],
            kwargs["user_id"],
            f"Not authorized to update `{name}`.",
            kwargs.get("response_url"),
        )
        return
    try:
        updated = set_weekend_opt_out(name, opt_out=True, settings=kwargs["settings"])
    except PowerError as exc:
        _reply(kwargs["client"], kwargs["channel_id"], kwargs["user_id"], str(exc), kwargs.get("response_url"))
        return
    logger.info("audit keep-weekend user=%s cluster=%s", kwargs["user_id"], name)
    _reply(
        kwargs["client"],
        kwargs["channel_id"],
        kwargs["user_id"],
        f"`{updated.name}` will stay running over the weekend "
        f"(label `opdev.io/weekend-hibernate=false`).",
        kwargs.get("response_url"),
    )
