"""Unit tests for credentials fetch and ready notification."""

import base64
from unittest.mock import MagicMock, patch

import pytest

from opdev_cluster_bot.acm.credentials import (
    ClusterCredentials,
    CredentialsError,
    build_ready_message,
    clusters_pending_creds_notification,
    fetch_cluster_credentials,
    mark_creds_notified,
    notify_cluster_ready,
)
from opdev_cluster_bot.acm.inventory import ClusterInfo
from opdev_cluster_bot.config import Settings


def _info(**overrides) -> ClusterInfo:
    base = dict(
        name="opdev-demo",
        namespace="opdev-demo",
        power_desired="Running",
        power_actual="Running",
        installed=True,
        available="True",
        version="4.22.8",
        owner_slack_id="U123",
        owner_email="dev@example.com",
        topology="SNO",
        instance_type="m5.2xlarge",
        managed_by_bot=True,
        weekend_hibernate=True,
        cluster_deployment_name="opdev-demo",
        creds_notified=False,
        api_url="https://api.opdev-demo.opdev.io:6443",
        console_url="https://console-openshift-console.apps.opdev-demo.opdev.io",
    )
    base.update(overrides)
    return ClusterInfo(**base)


def _cd_dict() -> dict:
    return {
        "spec": {
            "clusterMetadata": {
                "adminPasswordSecretRef": {"name": "opdev-demo-admin-password"},
                "adminKubeconfigSecretRef": {"name": "opdev-demo-admin-kubeconfig"},
            }
        },
        "status": {
            "apiURL": "https://api.opdev-demo.opdev.io:6443",
            "webConsoleURL": "https://console-openshift-console.apps.opdev-demo.opdev.io",
        },
    }


def test_clusters_pending_skips_notified_and_not_installed():
    clusters = [
        _info(),
        _info(name="opdev-done", creds_notified=True),
        _info(name="opdev-installing", installed=False),
        _info(name="opdev-no-owner", owner_slack_id=None),
    ]
    with patch("opdev_cluster_bot.acm.credentials.list_clusters", return_value=clusters):
        pending = clusters_pending_creds_notification(Settings())
    assert [c.name for c in pending] == ["opdev-demo"]


def test_fetch_cluster_credentials_reads_secrets():
    info = _info()
    passwd = MagicMock(data={"password": base64.b64encode(b"secret-pass").decode()})
    kube = MagicMock(data={"kubeconfig": base64.b64encode(b"apiVersion: v1").decode()})
    cds_api = MagicMock()
    cds_api.get.return_value.to_dict.return_value = _cd_dict()
    core = MagicMock()
    core.read_namespaced_secret.side_effect = [passwd, kube]

    with (
        patch("opdev_cluster_bot.acm.credentials.resource", return_value=cds_api),
        patch("opdev_cluster_bot.acm.credentials.core_v1", return_value=core),
    ):
        creds = fetch_cluster_credentials(info, Settings())

    assert creds.password == "secret-pass"
    assert creds.kubeconfig.startswith("apiVersion")
    assert creds.api_url.endswith(":6443")


def test_fetch_cluster_credentials_missing_refs():
    info = _info()
    cds_api = MagicMock()
    cds_api.get.return_value.to_dict.return_value = {"spec": {"clusterMetadata": {}}}
    with patch("opdev_cluster_bot.acm.credentials.resource", return_value=cds_api):
        with pytest.raises(CredentialsError, match="secret refs"):
            fetch_cluster_credentials(info, Settings())


def test_build_ready_message_includes_urls_and_policy():
    creds = ClusterCredentials(
        cluster_name="opdev-demo",
        namespace="opdev-demo",
        api_url="https://api.example:6443",
        console_url="https://console.example",
        password="pw",
        kubeconfig="kube",
        owner_slack_id="U123",
    )
    msg = build_ready_message(creds)
    assert "opdev-demo" in msg
    assert "https://api.example:6443" in msg
    assert "pw" in msg
    assert "8 AM ET" in msg


def test_notify_cluster_ready_dry_run_skips_slack():
    info = _info()
    client = MagicMock()
    settings = Settings(dry_run=True)
    with (
        patch("opdev_cluster_bot.acm.credentials.fetch_cluster_credentials") as fetch,
        patch("opdev_cluster_bot.acm.credentials.mark_creds_notified") as mark,
        patch("opdev_cluster_bot.acm.credentials.send_credentials_dm") as send,
    ):
        fetch.return_value = ClusterCredentials(
            cluster_name=info.name,
            namespace=info.namespace,
            api_url=info.api_url,
            console_url=info.console_url,
            password="pw",
            kubeconfig="kube",
            owner_slack_id=info.owner_slack_id,
        )
        notify_cluster_ready(info, client, settings)
    send.assert_not_called()
    mark.assert_not_called()


def test_notify_cluster_ready_sends_and_marks():
    info = _info()
    client = MagicMock()
    creds = ClusterCredentials(
        cluster_name=info.name,
        namespace=info.namespace,
        api_url=info.api_url,
        console_url=info.console_url,
        password="pw",
        kubeconfig="kube",
        owner_slack_id=info.owner_slack_id,
    )
    with (
        patch("opdev_cluster_bot.acm.credentials.fetch_cluster_credentials", return_value=creds),
        patch("opdev_cluster_bot.acm.credentials.send_credentials_dm") as send,
        patch("opdev_cluster_bot.acm.credentials.mark_creds_notified") as mark,
    ):
        notify_cluster_ready(info, client, Settings())
    send.assert_called_once()
    mark.assert_called_once_with(info, Settings())


def test_mark_creds_notified_patches_cd():
    info = _info()
    cds_api = MagicMock()
    with patch("opdev_cluster_bot.acm.credentials.resource", return_value=cds_api):
        mark_creds_notified(info, Settings())
    cds_api.patch.assert_called_once()
