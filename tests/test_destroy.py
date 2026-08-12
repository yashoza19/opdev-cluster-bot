"""Unit tests for destroy guards and dry-run path."""

from unittest.mock import patch

import pytest

from opdev_cluster_bot.acm.destroy import DestroyError, destroy_cluster
from opdev_cluster_bot.acm.inventory import ClusterInfo
from opdev_cluster_bot.blocks import HELP_TEXT, confirm_destroy_blocks
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
    )
    base.update(overrides)
    return ClusterInfo(**base)


def test_help_mentions_destroy():
    assert "destroy" in HELP_TEXT


def test_confirm_destroy_blocks_double_confirm():
    blocks = confirm_destroy_blocks(cluster_name="opdev-demo")
    assert "opdev-demo" in blocks[0]["text"]["text"]
    assert "cannot be undone" in blocks[0]["text"]["text"].lower()
    btn = blocks[1]["elements"][0]
    assert btn["action_id"] == "confirm_destroy"
    assert btn["style"] == "danger"
    assert btn["value"] == "opdev-demo"
    assert "confirm" in btn


def test_destroy_refuses_local_cluster():
    with pytest.raises(DestroyError, match="local-cluster"):
        destroy_cluster("local-cluster", Settings())


def test_destroy_refuses_non_bot_managed():
    with patch("opdev_cluster_bot.acm.destroy.get_cluster", return_value=_info(managed_by_bot=False)):
        with pytest.raises(DestroyError, match="not labeled"):
            destroy_cluster("opdev-demo", Settings())


def test_destroy_refuses_missing_clusterdeployment():
    with patch(
        "opdev_cluster_bot.acm.destroy.get_cluster",
        return_value=_info(cluster_deployment_name=None),
    ):
        with pytest.raises(DestroyError, match="ClusterDeployment"):
            destroy_cluster("opdev-demo", Settings())


def test_destroy_dry_run():
    settings = Settings(dry_run=True, managed_by_label="opdev-cluster-bot")
    with patch("opdev_cluster_bot.acm.destroy.get_cluster", return_value=_info()):
        result = destroy_cluster("opdev-demo", settings)
    assert result.dry_run is True
    assert result.message == "Dry-run: cluster `opdev-demo` would be deleted."
    assert any("ClusterDeployment" in d for d in result.deleted)
    assert not any("Namespace" in d for d in result.deleted)


def test_destroy_deletes_cd_and_mc_keeps_namespace():
    settings = Settings(dry_run=False, managed_by_label="opdev-cluster-bot")
    with (
        patch("opdev_cluster_bot.acm.destroy.get_cluster", return_value=_info()),
        patch("opdev_cluster_bot.acm.destroy._delete_namespaced", return_value=True) as ns_del,
        patch("opdev_cluster_bot.acm.destroy._delete_cluster_scoped", return_value=True) as cs_del,
    ):
        result = destroy_cluster("opdev-demo", settings)
    assert result.dry_run is False
    assert result.message == "Cluster `opdev-demo` will be deleted."
    assert len(result.deleted) == 2
    ns_del.assert_called_once()
    cs_del.assert_called_once()
    # Must not delete the namespace (that aborts Hive uninstall).
    assert not any("Namespace" in d for d in result.deleted)
