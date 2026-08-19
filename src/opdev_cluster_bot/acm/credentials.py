"""Fetch Hive admin credentials and notify cluster owners via Slack DM."""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass

from kubernetes.client.rest import ApiException
from slack_sdk import WebClient

from opdev_cluster_bot.acm.client import HIVE_GROUP, HIVE_VERSION, core_v1, resource
from opdev_cluster_bot.acm.inventory import ClusterInfo, list_clusters
from opdev_cluster_bot.config import ANNOTATION_CREDS_NOTIFIED, Settings
from opdev_cluster_bot.slack.dm import post_dm, upload_dm_file

logger = logging.getLogger(__name__)

LIFECYCLE_POLICY = (
    "EOD hibernate reminders Mon–Fri 5 PM ET; weekend auto-hibernate Fri 6 PM ET "
    "unless `keep-weekend`; daily auto-resume 8 AM ET."
)


class CredentialsError(Exception):
    pass


@dataclass
class ClusterCredentials:
    cluster_name: str
    namespace: str
    api_url: str | None
    console_url: str | None
    password: str
    kubeconfig: str
    owner_slack_id: str


def _decode_secret_field(data: dict[str, str] | None, key: str) -> str:
    if not data or key not in data:
        raise CredentialsError(f"Secret missing key `{key}`")
    return base64.b64decode(data[key]).decode("utf-8")


def _admin_secret_refs(cd: dict) -> tuple[str, str]:
    meta = (cd.get("spec") or {}).get("clusterMetadata") or {}
    passwd_ref = meta.get("adminPasswordSecretRef") or {}
    kube_ref = meta.get("adminKubeconfigSecretRef") or {}
    passwd_name = passwd_ref.get("name")
    kube_name = kube_ref.get("name")
    if not passwd_name or not kube_name:
        raise CredentialsError("ClusterDeployment has no admin credential secret refs yet")
    return passwd_name, kube_name


def fetch_cluster_credentials(
    info: ClusterInfo,
    settings: Settings | None = None,
) -> ClusterCredentials:
    settings = settings or Settings.from_env()
    if not info.cluster_deployment_name:
        raise CredentialsError(f"Cluster `{info.name}` has no ClusterDeployment")
    if not info.owner_slack_id:
        raise CredentialsError(f"Cluster `{info.name}` has no owner Slack ID")

    cds = resource(f"{HIVE_GROUP}/{HIVE_VERSION}", "ClusterDeployment")
    try:
        cd = cds.get(name=info.cluster_deployment_name, namespace=info.namespace).to_dict()
    except ApiException as exc:
        raise CredentialsError(f"Failed reading ClusterDeployment: {exc}") from exc

    passwd_name, kube_name = _admin_secret_refs(cd)
    core = core_v1()
    try:
        passwd_secret = core.read_namespaced_secret(passwd_name, info.namespace)
        kube_secret = core.read_namespaced_secret(kube_name, info.namespace)
    except ApiException as exc:
        raise CredentialsError(f"Failed reading admin secrets: {exc}") from exc

    password = _decode_secret_field(passwd_secret.data, "password")
    kubeconfig = _decode_secret_field(kube_secret.data, "kubeconfig")
    status = cd.get("status") or {}

    return ClusterCredentials(
        cluster_name=info.name,
        namespace=info.namespace,
        api_url=status.get("apiURL") or info.api_url,
        console_url=status.get("webConsoleURL") or info.console_url,
        password=password,
        kubeconfig=kubeconfig,
        owner_slack_id=info.owner_slack_id,
    )


def mark_creds_notified(info: ClusterInfo, settings: Settings | None = None) -> None:
    settings = settings or Settings.from_env()
    if not info.cluster_deployment_name:
        raise CredentialsError(f"Cluster `{info.name}` has no ClusterDeployment")
    cds = resource(f"{HIVE_GROUP}/{HIVE_VERSION}", "ClusterDeployment")
    body = {"metadata": {"annotations": {ANNOTATION_CREDS_NOTIFIED: "true"}}}
    try:
        cds.patch(
            name=info.cluster_deployment_name,
            namespace=info.namespace,
            body=body,
            content_type="application/merge-patch+json",
        )
    except ApiException as exc:
        raise CredentialsError(f"Failed marking creds notified on {info.name}: {exc}") from exc


def clusters_pending_creds_notification(
    settings: Settings | None = None,
) -> list[ClusterInfo]:
    settings = settings or Settings.from_env()
    pending: list[ClusterInfo] = []
    for info in list_clusters(settings, bot_managed_only=True):
        if not info.installed:
            continue
        if info.creds_notified:
            continue
        if not info.owner_slack_id:
            continue
        pending.append(info)
    return pending


def build_ready_message(creds: ClusterCredentials) -> str:
    api = creds.api_url or "pending"
    console = creds.console_url or "pending"
    return (
        f"Your cluster `{creds.cluster_name}` is ready.\n\n"
        f"*API:* {api}\n"
        f"*Console:* {console}\n"
        f"*kubeadmin password:* `{creds.password}`\n\n"
        f"*Lifecycle policy:* {LIFECYCLE_POLICY}"
    )


def send_credentials_dm(client: WebClient, creds: ClusterCredentials) -> None:
    post_dm(client, creds.owner_slack_id, text=build_ready_message(creds))
    upload_dm_file(
        client,
        creds.owner_slack_id,
        filename=f"{creds.cluster_name}-admin-kubeconfig.yaml",
        content=creds.kubeconfig.encode("utf-8"),
        initial_comment=f"Admin kubeconfig for `{creds.cluster_name}`.",
    )
    logger.info("Sent credentials DM owner=%s cluster=%s", creds.owner_slack_id, creds.cluster_name)


def notify_cluster_ready(
    info: ClusterInfo,
    client: WebClient,
    settings: Settings | None = None,
) -> None:
    settings = settings or Settings.from_env()
    creds = fetch_cluster_credentials(info, settings)
    if settings.dry_run:
        logger.info(
            "Dry-run: would DM owner=%s cluster=%s api=%s",
            creds.owner_slack_id,
            creds.cluster_name,
            creds.api_url,
        )
        return
    send_credentials_dm(client, creds)
    mark_creds_notified(info, settings)
