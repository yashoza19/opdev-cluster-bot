"""Slack user identity helpers and authorization."""

from __future__ import annotations

import logging
from typing import Any, Protocol

from opdev_cluster_bot.config import (
    ANNOTATION_OWNER_EMAIL,
    ANNOTATION_OWNER_SLACK_ID,
    Settings,
)

logger = logging.getLogger(__name__)


class SlackClientProto(Protocol):
    def users_info(self, *, user: str) -> dict[str, Any]: ...

    def usergroups_users_list(self, *, usergroup: str) -> dict[str, Any]: ...


def owner_annotations(slack_user_id: str, email: str | None) -> dict[str, str]:
    annotations = {ANNOTATION_OWNER_SLACK_ID: slack_user_id}
    if email:
        annotations[ANNOTATION_OWNER_EMAIL] = email
    return annotations


def resolve_email(client: SlackClientProto, slack_user_id: str) -> str | None:
    try:
        resp = client.users_info(user=slack_user_id)
        profile = (resp.get("user") or {}).get("profile") or {}
        return profile.get("email")
    except Exception:
        logger.exception("Failed to resolve email for Slack user %s", slack_user_id)
        return None


def is_authorized(
    *,
    actor_slack_id: str,
    owner_slack_id: str | None,
    settings: Settings,
    client: SlackClientProto | None = None,
) -> bool:
    if owner_slack_id and actor_slack_id == owner_slack_id:
        return True
    if not settings.admin_slack_group_ids or client is None:
        # Without admin groups configured, allow any teammate for MVP ops.
        return owner_slack_id is None or actor_slack_id == owner_slack_id
    for group_id in settings.admin_slack_group_ids:
        try:
            resp = client.usergroups_users_list(usergroup=group_id)
            if actor_slack_id in (resp.get("users") or []):
                return True
        except Exception:
            logger.exception("Failed listing usergroup %s", group_id)
    return False
