"""Provision Hive ClusterDeployment + ManagedCluster on AWS."""

from __future__ import annotations

import logging
import re
import secrets
import string
from dataclasses import dataclass
from importlib import resources
from typing import Any

import yaml
from jinja2 import Template
from kubernetes import client
from kubernetes.client.rest import ApiException

from opdev_cluster_bot.acm.client import (
    AGENT_GROUP,
    AGENT_VERSION,
    HIVE_GROUP,
    HIVE_VERSION,
    OCM_GROUP,
    OCM_VERSION,
    core_v1,
    resource,
)
from opdev_cluster_bot.acm.inventory import list_clusters
from opdev_cluster_bot.config import (
    ANNOTATION_INSTANCE_TYPE,
    ANNOTATION_OWNER_EMAIL,
    ANNOTATION_OWNER_SLACK_ID,
    ANNOTATION_TOPOLOGY,
    LABEL_MANAGED_BY,
    LABEL_WEEKEND_HIBERNATE,
    Settings,
)

logger = logging.getLogger(__name__)

_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,50}[a-z0-9])?$")


class ProvisionError(Exception):
    pass


@dataclass
class ProvisionRequest:
    version: str
    topology: str  # SNO | multinode
    instance_type: str
    cluster_name: str | None = None
    owner_slack_id: str | None = None
    owner_email: str | None = None
    aws_region: str | None = None


@dataclass
class ProvisionResult:
    cluster_name: str
    namespace: str
    dry_run: bool
    manifests: list[dict[str, Any]]
    message: str


def _normalize_topology(topology: str) -> str:
    t = topology.strip().lower()
    if t in {"sno", "single", "single-node"}:
        return "SNO"
    if t in {"multinode", "multi", "ha", "multi-node"}:
        return "multinode"
    raise ProvisionError(f"Unknown topology '{topology}'. Use SNO or multinode.")


def _generate_name() -> str:
    suffix = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(5))
    return f"opdev-{suffix}"


def _validate_name(name: str) -> str:
    name = name.strip().lower()
    if name.startswith("opdev-"):
        candidate = name
    else:
        candidate = f"opdev-{name}"
    if not _NAME_RE.match(candidate):
        raise ProvisionError(
            f"Invalid cluster name '{name}'. Use lowercase alphanumeric and hyphens."
        )
    if candidate == "local-cluster" or candidate.endswith("local-cluster"):
        raise ProvisionError("Refusing to provision local-cluster")
    return candidate


def _find_imageset(version: str) -> dict[str, Any]:
    imagesets = resource(f"{HIVE_GROUP}/{HIVE_VERSION}", "ClusterImageSet")
    items = imagesets.get().to_dict().get("items") or []
    version = version.lstrip("v")
    exact: list[dict[str, Any]] = []
    partial: list[dict[str, Any]] = []
    for item in items:
        name = (item.get("metadata") or {}).get("name", "")
        release = ((item.get("spec") or {}).get("releaseImage") or "")
        if version in name or version in release:
            if name.endswith(version) or f"{version}-" in name or f":{version}-" in release:
                exact.append(item)
            else:
                partial.append(item)
    chosen = (exact or partial)
    if not chosen:
        raise ProvisionError(
            f"No ClusterImageSet found matching version '{version}'. "
            "Create or import an image set on the hub first."
        )
    # Prefer names containing the version string most specifically.
    chosen.sort(key=lambda i: (i.get("metadata") or {}).get("name", ""))
    return chosen[-1]


def _render_install_config(
    *,
    cluster_name: str,
    settings: Settings,
    topology: str,
    instance_type: str,
) -> str:
    if topology == "SNO":
        control_plane_replicas = 1
        compute_replicas = 0
    else:
        control_plane_replicas = 3
        compute_replicas = settings.default_compute_replicas

    tpl_path = resources.files("opdev_cluster_bot.templates").joinpath(
        "install-config-aws.yaml.j2"
    )
    template = Template(tpl_path.read_text(encoding="utf-8"))
    rendered = template.render(
        cluster_name=cluster_name,
        base_domain=settings.base_domain,
        aws_region=settings.aws_region,
        instance_type=instance_type,
        control_plane_replicas=control_plane_replicas,
        compute_replicas=compute_replicas,
    )
    # Validate YAML
    yaml.safe_load(rendered)
    return rendered


def _copy_secret(core: client.CoreV1Api, src_ns: str, src_name: str, dst_ns: str, dst_name: str) -> None:
    src = core.read_namespaced_secret(src_name, src_ns)
    body = client.V1Secret(
        api_version="v1",
        kind="Secret",
        metadata=client.V1ObjectMeta(name=dst_name, namespace=dst_ns),
        type=src.type,
        data=src.data,
    )
    try:
        core.create_namespaced_secret(dst_ns, body)
    except ApiException as exc:
        if exc.status != 409:
            raise


def _count_provisioning(settings: Settings) -> int:
    count = 0
    for c in list_clusters(settings, bot_managed_only=True):
        if not c.installed and (c.power_actual or "Running") not in {"Hibernating"}:
            count += 1
    return count


def build_manifests(
    req: ProvisionRequest,
    settings: Settings,
    imageset_name: str,
) -> list[dict[str, Any]]:
    topology = _normalize_topology(req.topology)
    cluster_name = _validate_name(req.cluster_name) if req.cluster_name else _generate_name()
    namespace = cluster_name

    if not settings.base_domain:
        raise ProvisionError("BASE_DOMAIN is required for provisioning")

    if topology == "SNO" and req.instance_type == settings.sno_min_instance_type:
        pass  # ok
    # Soft guidance only; do not hard-block other sizes.

    install_config = _render_install_config(
        cluster_name=cluster_name,
        settings=settings,
        topology=topology,
        instance_type=req.instance_type,
    )

    labels = {
        LABEL_MANAGED_BY: settings.managed_by_label,
        LABEL_WEEKEND_HIBERNATE: "true",
        # Required by ACM OCM webhook for ManagedClusterSet assignment
        "cluster.open-cluster-management.io/clusterset": "default",
    }
    annotations = {
        ANNOTATION_TOPOLOGY: topology,
        ANNOTATION_INSTANCE_TYPE: req.instance_type,
    }
    if req.owner_slack_id:
        annotations[ANNOTATION_OWNER_SLACK_ID] = req.owner_slack_id
    if req.owner_email:
        annotations[ANNOTATION_OWNER_EMAIL] = req.owner_email

    ns = {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": namespace,
            "labels": labels,
            "annotations": annotations,
        },
    }

    install_secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": f"{cluster_name}-install-config", "namespace": namespace},
        "type": "Opaque",
        "stringData": {"install-config.yaml": install_config},
    }

    region = req.aws_region or settings.aws_region
    cd = {
        "apiVersion": f"{HIVE_GROUP}/{HIVE_VERSION}",
        "kind": "ClusterDeployment",
        "metadata": {
            "name": cluster_name,
            "namespace": namespace,
            "labels": labels,
            "annotations": annotations,
        },
        "spec": {
            "baseDomain": settings.base_domain,
            "clusterName": cluster_name,
            "platform": {
                "aws": {
                    "region": region,
                    "credentialsSecretRef": {"name": settings.aws_creds_secret},
                }
            },
            "provisioning": {
                "installConfigSecretRef": {"name": f"{cluster_name}-install-config"},
                "imageSetRef": {"name": imageset_name},
                "sshPrivateKeySecretRef": {"name": settings.ssh_secret_name},
            },
            "pullSecretRef": {"name": settings.pull_secret_name},
        },
    }

    mc = {
        "apiVersion": f"{OCM_GROUP}/{OCM_VERSION}",
        "kind": "ManagedCluster",
        "metadata": {
            "name": cluster_name,
            "labels": {
                **labels,
                "name": cluster_name,
                "cloud": "Amazon",
                "vendor": "OpenShift",
            },
            "annotations": annotations,
        },
        "spec": {"hubAcceptsClient": True},
    }

    addon = {
        "apiVersion": f"{AGENT_GROUP}/{AGENT_VERSION}",
        "kind": "KlusterletAddonConfig",
        "metadata": {"name": cluster_name, "namespace": namespace},
        "spec": {
            "clusterName": cluster_name,
            "clusterNamespace": namespace,
            "clusterLabels": {"cloud": "Amazon", "vendor": "OpenShift"},
            "applicationManager": {"enabled": True},
            "policyController": {"enabled": True},
            "searchCollector": {"enabled": True},
            "certPolicyController": {"enabled": True},
        },
    }

    return [ns, install_secret, cd, mc, addon]


def provision_cluster(req: ProvisionRequest, settings: Settings | None = None) -> ProvisionResult:
    settings = settings or Settings.from_env()
    topology = _normalize_topology(req.topology)
    req = ProvisionRequest(
        version=req.version,
        topology=topology,
        instance_type=req.instance_type,
        cluster_name=req.cluster_name,
        owner_slack_id=req.owner_slack_id,
        owner_email=req.owner_email,
        aws_region=req.aws_region,
    )

    if not settings.dry_run:
        provisioning = _count_provisioning(settings)
        if provisioning >= settings.max_concurrent_provisions:
            raise ProvisionError(
                f"Too many concurrent provisions ({provisioning}). "
                f"Max is {settings.max_concurrent_provisions}."
            )

    imageset = _find_imageset(req.version) if not settings.dry_run else {
        "metadata": {"name": f"img{req.version}-x86-64"}
    }
    # In dry-run without API access, allow a synthetic imageset name.
    try:
        if not settings.dry_run:
            imageset = _find_imageset(req.version)
        else:
            try:
                imageset = _find_imageset(req.version)
            except Exception:
                imageset = {"metadata": {"name": f"img{req.version.replace('.', '')}-x86-64"}}
    except ProvisionError:
        raise
    except Exception as exc:
        raise ProvisionError(str(exc)) from exc

    imageset_name = (imageset.get("metadata") or {}).get("name")
    manifests = build_manifests(req, settings, imageset_name)
    cluster_name = manifests[0]["metadata"]["name"]
    namespace = cluster_name

    if settings.dry_run:
        return ProvisionResult(
            cluster_name=cluster_name,
            namespace=namespace,
            dry_run=True,
            manifests=manifests,
            message=f"Dry-run: would create cluster `{cluster_name}` "
            f"({topology}, {req.instance_type}, OCP {req.version}) "
            f"using ClusterImageSet `{imageset_name}`.",
        )

    core = core_v1()
    # Create namespace first
    ns_body = client.V1Namespace(
        metadata=client.V1ObjectMeta(
            name=namespace,
            labels=manifests[0]["metadata"]["labels"],
            annotations=manifests[0]["metadata"]["annotations"],
        )
    )
    try:
        core.create_namespace(ns_body)
    except ApiException as exc:
        if exc.status != 409:
            raise ProvisionError(f"Failed creating namespace {namespace}: {exc}") from exc

    for secret_name in (
        settings.aws_creds_secret,
        settings.pull_secret_name,
        settings.ssh_secret_name,
    ):
        try:
            _copy_secret(core, settings.creds_namespace, secret_name, namespace, secret_name)
        except ApiException as exc:
            raise ProvisionError(
                f"Failed copying secret {settings.creds_namespace}/{secret_name}: {exc}"
            ) from exc

    # install-config secret
    install = manifests[1]
    try:
        core.create_namespaced_secret(
            namespace,
            client.V1Secret(
                metadata=client.V1ObjectMeta(name=install["metadata"]["name"]),
                string_data=install["stringData"],
                type="Opaque",
            ),
        )
    except ApiException as exc:
        if exc.status != 409:
            raise ProvisionError(f"Failed creating install-config secret: {exc}") from exc

    dyn_kinds = [
        (f"{HIVE_GROUP}/{HIVE_VERSION}", "ClusterDeployment", manifests[2]),
        (f"{OCM_GROUP}/{OCM_VERSION}", "ManagedCluster", manifests[3]),
        (f"{AGENT_GROUP}/{AGENT_VERSION}", "KlusterletAddonConfig", manifests[4]),
    ]
    for api_version, kind, body in dyn_kinds:
        api = resource(api_version, kind)
        try:
            if kind == "ManagedCluster":
                api.create(body=body)
            else:
                api.create(body=body, namespace=namespace)
        except ApiException as exc:
            if exc.status != 409:
                raise ProvisionError(f"Failed creating {kind}: {exc}") from exc

    logger.info(
        "Provisioned cluster %s version=%s topology=%s type=%s owner=%s",
        cluster_name,
        req.version,
        topology,
        req.instance_type,
        req.owner_slack_id,
    )
    return ProvisionResult(
        cluster_name=cluster_name,
        namespace=namespace,
        dry_run=False,
        manifests=manifests,
        message=f"Provisioning started for `{cluster_name}` "
        f"({topology}, {req.instance_type}, OCP {req.version}).",
    )
