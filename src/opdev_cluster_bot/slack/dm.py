"""Slack direct-message helpers (credentials and owner notifications)."""

from __future__ import annotations

from slack_sdk import WebClient


def open_dm_channel(client: WebClient, user_id: str) -> str:
    opened = client.conversations_open(users=[user_id])
    return opened["channel"]["id"]


def post_dm(
    client: WebClient,
    user_id: str,
    *,
    text: str,
    blocks: list[dict] | None = None,
) -> str:
    channel = open_dm_channel(client, user_id)
    client.chat_postMessage(channel=channel, text=text, blocks=blocks)
    return channel


def upload_dm_file(
    client: WebClient,
    user_id: str,
    *,
    filename: str,
    content: bytes,
    initial_comment: str | None = None,
) -> None:
    channel = open_dm_channel(client, user_id)
    client.files_upload_v2(
        channel=channel,
        filename=filename,
        content=content,
        initial_comment=initial_comment,
    )
