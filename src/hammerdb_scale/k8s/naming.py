"""Naming scheme: job name generation, hash, labels, annotations."""

from __future__ import annotations

import hashlib
from datetime import datetime

from hammerdb_scale.constants import NAMING_PREFIX, VERSION


def generate_run_hash(deployment_name: str, test_id: str) -> str:
    """Deterministic 8-char hash for job naming."""
    raw = f"{deployment_name}-{test_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:8]


def generate_job_name(phase: str, target_index: int, run_hash: str) -> str:
    """Generate a v2 job name: hdb-{phase}-{idx:02d}-{hash}.

    Example: hdb-run-03-a1b2c3d4 (22 chars, well within K8s 63 limit).
    """
    return f"{NAMING_PREFIX}-{phase}-{target_index:02d}-{run_hash}"


def generate_release_name(phase: str, run_hash: str) -> str:
    """Generate a Helm release name: hdb-{phase}-{hash}.

    Uses CLI phase (e.g., 'run', not Helm 'load').
    """
    return f"{NAMING_PREFIX}-{phase}-{run_hash}"


def generate_test_id(deployment_name: str) -> str:
    """Generate a test ID: {name}-{YYYYMMDD-HHMM}."""
    now = datetime.now()
    return f"{deployment_name}-{now.strftime('%Y%m%d-%H%M')}"


def generate_labels(
    test_id: str,
    phase: str,
    benchmark: str,
    target_name: str,
    target_index: int,
    database_type: str,
    deployment_name: str,
) -> dict[str, str]:
    """Generate the full label dict for a K8s job."""
    return {
        "hammerdb.io/version": VERSION,
        "hammerdb.io/test-id": test_id,
        "hammerdb.io/phase": phase,
        "hammerdb.io/benchmark": benchmark,
        "hammerdb.io/target-name": target_name,
        "hammerdb.io/target-index": str(target_index),
        "hammerdb.io/database-type": database_type,
        "hammerdb.io/deployment-name": deployment_name,
    }


def generate_annotations(target_host: str, target_index: int) -> dict[str, str]:
    """Generate annotations for a K8s job."""
    return {
        "hammerdb.io/target-host": target_host,
        "hammerdb.io/target-index": str(target_index),
    }
