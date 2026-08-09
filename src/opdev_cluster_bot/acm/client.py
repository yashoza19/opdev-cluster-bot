"""Kubernetes dynamic client bootstrap for in-cluster or kubeconfig use."""

from __future__ import annotations

import logging
from functools import lru_cache

from kubernetes import client, config
from kubernetes.dynamic import DynamicClient

logger = logging.getLogger(__name__)

HIVE_GROUP = "hive.openshift.io"
HIVE_VERSION = "v1"
OCM_GROUP = "cluster.open-cluster-management.io"
OCM_VERSION = "v1"
AGENT_GROUP = "agent.open-cluster-management.io"
AGENT_VERSION = "v1"


@lru_cache(maxsize=1)
def load_api_client() -> client.ApiClient:
    try:
        config.load_incluster_config()
        logger.info("Loaded in-cluster Kubernetes config")
    except config.ConfigException:
        config.load_kube_config()
        logger.info("Loaded kubeconfig")
    return client.ApiClient()


def get_dynamic_client() -> DynamicClient:
    # Prefer TMPDIR (emptyDir /tmp in the Deployment); fall back to in-memory
    # discovery if no writable temp dir is available.
    import os
    import tempfile

    cache_file = None
    try:
        tempfile.gettempdir()
    except FileNotFoundError:
        cache_file = False
    else:
        cache_file = os.path.join(tempfile.gettempdir(), "opdev_k8s_discover.json")
    return DynamicClient(load_api_client(), cache_file=cache_file)


def resource(api_version: str, kind: str):
    dyn = get_dynamic_client()
    return dyn.resources.get(api_version=api_version, kind=kind)


def core_v1() -> client.CoreV1Api:
    return client.CoreV1Api(load_api_client())
