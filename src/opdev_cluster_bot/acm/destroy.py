"""Destroy / deprovision bot-managed Hive clusters."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from kubernetes.client.rest import ApiException

from opdev_cluster_bot.acm.client import (
    HIVE_GROUP,
    HIVE_VERSION,
    OCM_GROUP,
    OCM_VERSION,
    resource,
)
from opdev_cluster_bot.acm.inventory import ClusterInfo, get_cluster
from opdev_cluster_bot.config import LOCAL_CLUSTER, Settings

logger = logging.getLogger(__name__)


class DestroyError(Exception):
    pass


@dataclass
class DestroyResult:
    cluster_name: str
    namespace: str
    dry_run: bool
    deleted: list[str]
    message: str


def _delete_namespaced(api_version: str, kind: str, name: str, namespace: str) -> bool:
    api = resource(api_version, kind)
    try:
        api.delete(name=name, namespace=namespace)
        return True
    except ApiException as exc:
        if exc.status == 404:
            return False
        raise DestroyError(f"Failed deleting {kind} {namespace}/{name}: {exc}") from exc


def _delete_cluster_scoped(api_version: str, kind: str, name: str) -> bool:
    api = resource(api_version, kind)
    try:
        api.delete(name=name)
        return True
    except ApiException as exc:
        if exc.status == 404:
            return False
        raise DestroyError(f"Failed deleting {kind} {name}: {exc}") from exc


def destroy_cluster(name: str, settings: Settings | None = None) -> DestroyResult:
    """Start Hive cloud deprovision and detach the spoke from ACM.

    Correct order (do **not** delete the namespace up front):

    1. Delete ``ClusterDeployment`` — Hive finalizer runs the uninstall/deprovision
       Job in the cluster namespace and tears down AWS.
    2. Delete ``ManagedCluster`` — removes the spoke from the ACM console.
    3. Leave the namespace (and secrets/jobs) until the CD is fully gone; deleting
       the namespace early kills the deprovision Job and orphans cloud resources.
    """
    settings = settings or Settings.from_env()
    if name == LOCAL_CLUSTER:
        raise DestroyError("Refusing to destroy local-cluster")

    info = get_cluster(name, settings)
    if info is None:
        raise DestroyError(f"Cluster {name} not found")
    if not info.managed_by_bot:
        raise DestroyError(
            f"Refusing to destroy `{info.name}`: not labeled "
            f"opdev.io/managed-by={settings.managed_by_label}"
        )
    if not info.cluster_deployment_name:
        raise DestroyError(
            f"Cluster `{info.name}` has no ClusterDeployment; "
            "refusing ManagedCluster-only detach (that would skip AWS teardown)"
        )

    namespace = info.namespace
    cd_name = info.cluster_deployment_name
    planned = [
        f"ClusterDeployment {namespace}/{cd_name} (Hive AWS deprovision)",
        f"ManagedCluster {info.name} (ACM detach)",
    ]

    if settings.dry_run:
        return DestroyResult(
            cluster_name=info.name,
            namespace=namespace,
            dry_run=True,
            deleted=planned,
            message=f"Dry-run: cluster `{info.name}` would be deleted.",
        )

    deleted: list[str] = []

    # CD delete triggers Hive uninstall; namespace must remain for that Job.
    if _delete_namespaced(f"{HIVE_GROUP}/{HIVE_VERSION}", "ClusterDeployment", cd_name, namespace):
        deleted.append(f"ClusterDeployment {namespace}/{cd_name}")
        logger.info("ClusterDeployment delete requested %s/%s", namespace, cd_name)

    if _delete_cluster_scoped(f"{OCM_GROUP}/{OCM_VERSION}", "ManagedCluster", info.name):
        deleted.append(f"ManagedCluster {info.name}")
        logger.info("ManagedCluster deleted %s", info.name)

    if not deleted:
        raise DestroyError(f"Nothing deleted for `{info.name}` (already gone?)")

    return DestroyResult(
        cluster_name=info.name,
        namespace=namespace,
        dry_run=False,
        deleted=deleted,
        message=f"Cluster `{info.name}` will be deleted.",
    )


def cluster_for_destroy(name: str, settings: Settings | None = None) -> ClusterInfo | None:
    """Resolve cluster name, trying `opdev-` prefix when needed."""
    settings = settings or Settings.from_env()
    info = get_cluster(name, settings)
    if info is not None:
        return info
    if not name.startswith("opdev-"):
        return get_cluster(f"opdev-{name}", settings)
    return None
