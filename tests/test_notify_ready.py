"""Unit tests for notify-ready CronJob."""

from unittest.mock import patch

from opdev_cluster_bot.acm.inventory import ClusterInfo
from opdev_cluster_bot.config import Settings
from jobs.notify_ready import run


def _info(name: str = "opdev-demo") -> ClusterInfo:
    return ClusterInfo(
        name=name,
        namespace=name,
        power_desired="Running",
        power_actual="Running",
        installed=True,
        available="True",
        version="4.22.8",
        owner_slack_id="U1",
        owner_email=None,
        topology="SNO",
        instance_type="m5.2xlarge",
        managed_by_bot=True,
        weekend_hibernate=True,
        cluster_deployment_name=name,
        creds_notified=False,
        api_url="https://api.example:6443",
        console_url="https://console.example",
    )


def test_notify_ready_job_processes_pending():
    settings = Settings(slack_bot_token="xoxb-test")
    pending = [_info()]
    with (
        patch("jobs.notify_ready.clusters_pending_creds_notification", return_value=pending),
        patch("jobs.notify_ready.notify_cluster_ready") as notify,
        patch("jobs.notify_ready.slack_client"),
    ):
        code = run(settings)
    assert code == 0
    notify.assert_called_once()


def test_notify_ready_job_counts_errors():
    settings = Settings(slack_bot_token="xoxb-test")
    pending = [_info(), _info("opdev-other")]
    with (
        patch("jobs.notify_ready.clusters_pending_creds_notification", return_value=pending),
        patch("jobs.notify_ready.notify_cluster_ready", side_effect=[None, RuntimeError("boom")]),
        patch("jobs.notify_ready.slack_client"),
    ):
        code = run(settings)
    assert code == 1
