"""Hibernate / resume ClusterDeployment power state."""

from __future__ import annotations

import logging
from typing import Any

from kubernetes.client.rest import ApiException

from opdev_cluster_bot.acm.client import HIVE_GROUP, HIVE_VERSION, resource
from opdev_cluster_bot.acm.inventory import ClusterInfo, get_cluster
from opdev_cluster_bot.config import LABEL_WEEKEND_HIBERNATE, LOCAL_CLUSTER, Settings

logger = logging.getLogger(__name__)


class PowerError(Exception):
    pass


def _patch_power_state(namespace: str, name: str, power_state: str) -> dict[str, Any]:
    if name == LOCAL_CLUSTER or namespace == LOCAL_CLUSTER:
        raise PowerError("Refusing to change power state of local-cluster")
    cds = resource(f"{HIVE_GROUP}/{HIVE_VERSION}", "ClusterDeployment")
    body = {"spec": {"powerState": power_state}}
    try:
        return cds.patch(
            name=name,
            namespace=namespace,
            body=body,
            content_type="application/merge-patch+json",
        ).to_dict()
    except ApiException as exc:
        raise PowerError(f"Failed to set powerState={power_state} on {namespace}/{name}: {exc}") from exc


def hibernate_cluster(name: str, settings: Settings | None = None) -> ClusterInfo:
    settings = settings or Settings.from_env()
    info = get_cluster(name, settings)
    if info is None:
        raise PowerError(f"Cluster {name} not found")
    if not info.cluster_deployment_name:
        raise PowerError(f"Cluster {name} has no ClusterDeployment (cannot hibernate)")
    _patch_power_state(info.namespace, info.cluster_deployment_name, "Hibernating")
    logger.info("Hibernating cluster %s in namespace %s", name, info.namespace)
    updated = get_cluster(name, settings)
    assert updated is not None
    return updated


def resume_cluster(name: str, settings: Settings | None = None) -> ClusterInfo:
    settings = settings or Settings.from_env()
    info = get_cluster(name, settings)
    if info is None:
        raise PowerError(f"Cluster {name} not found")
    if not info.cluster_deployment_name:
        raise PowerError(f"Cluster {name} has no ClusterDeployment (cannot resume)")
    _patch_power_state(info.namespace, info.cluster_deployment_name, "Running")
    logger.info("Resuming cluster %s in namespace %s", name, info.namespace)
    updated = get_cluster(name, settings)
    assert updated is not None
    return updated


def set_weekend_opt_out(name: str, opt_out: bool = True, settings: Settings | None = None) -> ClusterInfo:
    """Set opdev.io/weekend-hibernate=false to skip weekend auto-hibernate."""
    settings = settings or Settings.from_env()
    info = get_cluster(name, settings)
    if info is None:
        raise PowerError(f"Cluster {name} not found")
    if not info.cluster_deployment_name:
        raise PowerError(f"Cluster {name} has no ClusterDeployment")
    value = "false" if opt_out else "true"
    cds = resource(f"{HIVE_GROUP}/{HIVE_VERSION}", "ClusterDeployment")
    body = {"metadata": {"labels": {LABEL_WEEKEND_HIBERNATE: value}}}
    try:
        cds.patch(
            name=info.cluster_deployment_name,
            namespace=info.namespace,
            body=body,
            content_type="application/merge-patch+json",
        )
    except ApiException as exc:
        raise PowerError(f"Failed to update weekend label on {name}: {exc}") from exc
    updated = get_cluster(name, settings)
    assert updated is not None
    return updated
