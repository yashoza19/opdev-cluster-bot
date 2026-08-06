"""Runtime configuration from environment / ConfigMap-injected env."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


@dataclass(frozen=True)
class Settings:
    slack_bot_token: str = ""
    slack_app_token: str = ""
    aws_region: str = "us-east-1"
    base_domain: str = ""
    creds_namespace: str = "opdev-cluster-bot-creds"
    aws_creds_secret: str = "aws-creds"
    pull_secret_name: str = "pull-secret"
    ssh_secret_name: str = "ssh-privatekey"
    reminder_channel: str = ""
    admin_slack_group_ids: list[str] = field(default_factory=list)
    default_compute_replicas: int = 3
    sno_min_instance_type: str = "m5.2xlarge"
    max_concurrent_provisions: int = 3
    dry_run: bool = False
    managed_by_label: str = "opdev-cluster-bot"
    timezone: str = "America/New_York"

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            slack_bot_token=os.environ.get("SLACK_BOT_TOKEN", ""),
            slack_app_token=os.environ.get("SLACK_APP_TOKEN", ""),
            aws_region=os.environ.get("AWS_REGION", "us-east-1"),
            base_domain=os.environ.get("BASE_DOMAIN", ""),
            creds_namespace=os.environ.get("CREDS_NAMESPACE", "opdev-cluster-bot-creds"),
            aws_creds_secret=os.environ.get("AWS_CREDS_SECRET", "aws-creds"),
            pull_secret_name=os.environ.get("PULL_SECRET_NAME", "pull-secret"),
            ssh_secret_name=os.environ.get("SSH_SECRET_NAME", "ssh-privatekey"),
            reminder_channel=os.environ.get("REMINDER_CHANNEL", ""),
            admin_slack_group_ids=_csv(os.environ.get("ADMIN_SLACK_GROUP_IDS")),
            default_compute_replicas=int(os.environ.get("DEFAULT_COMPUTE_REPLICAS", "3")),
            sno_min_instance_type=os.environ.get("SNO_MIN_INSTANCE_TYPE", "m5.2xlarge"),
            max_concurrent_provisions=int(os.environ.get("MAX_CONCURRENT_PROVISIONS", "3")),
            dry_run=_bool(os.environ.get("DRY_RUN"), False),
            managed_by_label=os.environ.get("MANAGED_BY_LABEL", "opdev-cluster-bot"),
            timezone=os.environ.get("TZ", "America/New_York"),
        )


LABEL_MANAGED_BY = "opdev.io/managed-by"
LABEL_WEEKEND_HIBERNATE = "opdev.io/weekend-hibernate"
ANNOTATION_OWNER_SLACK_ID = "opdev.io/owner-slack-id"
ANNOTATION_OWNER_EMAIL = "opdev.io/owner-email"
ANNOTATION_TOPOLOGY = "opdev.io/topology"
ANNOTATION_INSTANCE_TYPE = "opdev.io/instance-type"
LOCAL_CLUSTER = "local-cluster"
