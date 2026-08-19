"""Unit tests for provision helpers and install-config rendering."""

import pytest

from opdev_cluster_bot.acm.provision import (
    ProvisionError,
    ProvisionRequest,
    _normalize_topology,
    _validate_name,
    build_manifests,
)
from opdev_cluster_bot.config import Settings


def test_normalize_topology():
    assert _normalize_topology("sno") == "SNO"
    assert _normalize_topology("multinode") == "multinode"
    with pytest.raises(ProvisionError):
        _normalize_topology("baremetal")


def test_validate_name():
    assert _validate_name("demo") == "opdev-demo"
    assert _validate_name("opdev-demo") == "opdev-demo"
    with pytest.raises(ProvisionError):
        _validate_name("INVALID_NAME")


def test_build_manifests_sno():
    settings = Settings(
        base_domain="dev.example.com",
        aws_region="us-east-1",
        managed_by_label="opdev-cluster-bot",
    )
    manifests = build_manifests(
        ProvisionRequest(
            version="4.16.0",
            topology="SNO",
            instance_type="m5.2xlarge",
            cluster_name="smoke",
            owner_slack_id="U123",
            owner_email="dev@example.com",
        ),
        settings,
        imageset_name="img4.16.0-x86-64",
    )
    kinds = [m["kind"] for m in manifests]
    assert kinds == [
        "Namespace",
        "Secret",
        "ClusterDeployment",
        "ManagedCluster",
        "KlusterletAddonConfig",
    ]
    ns = manifests[0]
    assert ns["metadata"]["name"] == "opdev-smoke"
    assert ns["metadata"]["labels"]["opdev.io/managed-by"] == "opdev-cluster-bot"
    assert ns["metadata"]["labels"]["opdev.io/weekend-hibernate"] == "true"
    assert ns["metadata"]["annotations"]["opdev.io/topology"] == "SNO"

    install = manifests[1]["stringData"]["install-config.yaml"]
    # SNO must use an explicit worker pool with replicas: 0.
    # `compute: []` makes openshift-install default to 3 workers.
    assert "compute: []" not in install
    assert "name: worker" in install
    assert "replicas: 0" in install
    assert "replicas: 1" in install
    assert "m5.2xlarge" in install
    assert "us-east-1" in install

    cd = manifests[2]
    assert cd["spec"]["provisioning"]["imageSetRef"]["name"] == "img4.16.0-x86-64"
    assert cd["spec"]["platform"]["aws"]["region"] == "us-east-1"


def test_build_manifests_multinode():
    settings = Settings(base_domain="dev.example.com", default_compute_replicas=3)
    manifests = build_manifests(
        ProvisionRequest(
            version="4.16.0",
            topology="multinode",
            instance_type="m5.xlarge",
            cluster_name="multi1",
        ),
        settings,
        imageset_name="img4.16.0-x86-64",
    )
    install = manifests[1]["stringData"]["install-config.yaml"]
    assert "name: worker" in install
    assert "replicas: 3" in install


def test_build_manifests_uses_request_region_override():
    settings = Settings(base_domain="dev.example.com", aws_region="us-east-1")
    manifests = build_manifests(
        ProvisionRequest(
            version="4.22.8",
            topology="SNO",
            instance_type="m5.4xlarge",
            cluster_name="regioncheck",
            aws_region="us-west-2",
        ),
        settings,
        imageset_name="img4.22.8-x86-64-appsub",
    )
    cd = manifests[2]
    assert cd["spec"]["platform"]["aws"]["region"] == "us-west-2"
