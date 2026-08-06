"""List and describe managed clusters joined with ClusterDeployment power state."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from opdev_cluster_bot.acm.client import HIVE_GROUP, HIVE_VERSION, OCM_GROUP, OCM_VERSION, resource
from opdev_cluster_bot.config import (
    ANNOTATION_INSTANCE_TYPE,
    ANNOTATION_OWNER_EMAIL,
    ANNOTATION_OWNER_SLACK_ID,
    ANNOTATION_TOPOLOGY,
    LABEL_MANAGED_BY,
    LABEL_WEEKEND_HIBERNATE,
    LOCAL_CLUSTER,
    Settings,
)

logger = logging.getLogger(__name__)


@dataclass
class ClusterInfo:
    name: str
    namespace: str
    power_desired: str | None
    power_actual: str | None
    installed: bool
    available: str | None
    version: str | None
    owner_slack_id: str | None
    owner_email: str | None
    topology: str | None
    instance_type: str | None
    managed_by_bot: bool
    weekend_hibernate: bool
    cluster_deployment_name: str | None

    def summary_line(self) -> str:
        power = self.power_actual or self.power_desired or "Unknown"
        version = self.version or "?"
        topo = self.topology or "?"
        owner = self.owner_email or self.owner_slack_id or "unowned"
        return f"`{self.name}` | {power} | {version} | {topo} | {owner}"


def _condition_status(conditions: list[dict[str, Any]], type_name: str) -> str | None:
    for cond in conditions or []:
        if cond.get("type") == type_name:
            return cond.get("status")
    return None


def _cd_for_cluster(name: str) -> dict[str, Any] | None:
    try:
        cds = resource(f"{HIVE_GROUP}/{HIVE_VERSION}", "ClusterDeployment")
        # Prefer namespace matching cluster name (Hive convention).
        try:
            return cds.get(name=name, namespace=name).to_dict()
        except Exception:
            pass
        items = cds.get().to_dict().get("items") or []
        for item in items:
            if item.get("metadata", {}).get("name") == name:
                return item
            if item.get("spec", {}).get("clusterName") == name:
                return item
    except Exception:
        logger.exception("Failed listing ClusterDeployments for %s", name)
    return None


def _from_objects(
    mc: dict[str, Any],
    cd: dict[str, Any] | None,
    settings: Settings,
) -> ClusterInfo:
    md = mc.get("metadata") or {}
    name = md.get("name") or ""
    labels = md.get("labels") or {}
    annotations = md.get("annotations") or {}
    status = mc.get("status") or {}
    claims = {c.get("name"): c.get("value") for c in (status.get("clusterClaims") or []) if c.get("name")}

    cd_md = (cd or {}).get("metadata") or {}
    cd_labels = cd_md.get("labels") or {}
    cd_annotations = cd_md.get("annotations") or {}
    cd_spec = (cd or {}).get("spec") or {}
    cd_status = (cd or {}).get("status") or {}

    merged_labels = {**labels, **cd_labels}
    merged_annotations = {**annotations, **cd_annotations}

    weekend = merged_labels.get(LABEL_WEEKEND_HIBERNATE, "true").lower() != "false"
    managed = merged_labels.get(LABEL_MANAGED_BY) == settings.managed_by_label

    return ClusterInfo(
        name=name,
        namespace=cd_md.get("namespace") or name,
        power_desired=cd_spec.get("powerState"),
        power_actual=cd_status.get("powerState") or cd_spec.get("powerState"),
        installed=bool(cd_spec.get("installed")),
        available=_condition_status(status.get("conditions") or [], "ManagedClusterConditionAvailable"),
        version=claims.get("version.openshift.io") or status.get("version", {}).get("kubernetes"),
        owner_slack_id=merged_annotations.get(ANNOTATION_OWNER_SLACK_ID),
        owner_email=merged_annotations.get(ANNOTATION_OWNER_EMAIL),
        topology=merged_annotations.get(ANNOTATION_TOPOLOGY),
        instance_type=merged_annotations.get(ANNOTATION_INSTANCE_TYPE),
        managed_by_bot=managed,
        weekend_hibernate=weekend,
        cluster_deployment_name=(cd_md.get("name") if cd else None),
    )


def list_clusters(
    settings: Settings | None = None,
    *,
    bot_managed_only: bool = False,
) -> list[ClusterInfo]:
    settings = settings or Settings.from_env()
    mcs = resource(f"{OCM_GROUP}/{OCM_VERSION}", "ManagedCluster")
    items = mcs.get().to_dict().get("items") or []
    results: list[ClusterInfo] = []
    for mc in items:
        name = (mc.get("metadata") or {}).get("name")
        if not name or name == LOCAL_CLUSTER:
            continue
        cd = _cd_for_cluster(name)
        info = _from_objects(mc, cd, settings)
        if bot_managed_only and not info.managed_by_bot:
            continue
        results.append(info)
    results.sort(key=lambda c: c.name)
    return results


def get_cluster(name: str, settings: Settings | None = None) -> ClusterInfo | None:
    settings = settings or Settings.from_env()
    if name == LOCAL_CLUSTER:
        return None
    try:
        mcs = resource(f"{OCM_GROUP}/{OCM_VERSION}", "ManagedCluster")
        mc = mcs.get(name=name).to_dict()
    except Exception:
        logger.exception("ManagedCluster %s not found", name)
        return None
    cd = _cd_for_cluster(name)
    return _from_objects(mc, cd, settings)
