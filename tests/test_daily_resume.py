"""Unit tests for daily resume job."""

from unittest.mock import patch

from opdev_cluster_bot.acm.inventory import ClusterInfo
from opdev_cluster_bot.config import Settings
from jobs.daily_resume import run


def _cluster(name: str, power: str, weekend: bool = True) -> ClusterInfo:
    return ClusterInfo(
        name=name,
        namespace=name,
        power_desired=power,
        power_actual=power,
        installed=True,
        available="True",
        version="4.22.8",
        owner_slack_id="U1",
        owner_email=None,
        topology="SNO",
        instance_type="m5.2xlarge",
        managed_by_bot=True,
        weekend_hibernate=weekend,
        cluster_deployment_name=name,
    )


def test_daily_resume_skips_running():
    settings = Settings(slack_bot_token="xoxb-test")
    clusters = [
        _cluster("opdev-a", "Running"),
        _cluster("opdev-b", "Hibernating"),
    ]
    with (
        patch("jobs.daily_resume.list_clusters", return_value=clusters),
        patch("jobs.daily_resume.resume_cluster") as resume,
        patch("jobs.daily_resume.slack_client"),
        patch("jobs.daily_resume.post_or_dm"),
    ):
        code = run(settings)
    assert code == 0
    resume.assert_called_once_with("opdev-b", settings)


def test_daily_resume_includes_keep_weekend_clusters():
    """Unlike Monday resume, daily resume wakes all hibernating bot-managed clusters."""
    settings = Settings(slack_bot_token="xoxb-test")
    clusters = [_cluster("opdev-optout", "Hibernating", weekend=False)]
    with (
        patch("jobs.daily_resume.list_clusters", return_value=clusters),
        patch("jobs.daily_resume.resume_cluster") as resume,
        patch("jobs.daily_resume.slack_client"),
        patch("jobs.daily_resume.post_or_dm"),
    ):
        run(settings)
    resume.assert_called_once_with("opdev-optout", settings)
