"""K8s job discovery, status, log retrieval, and resolution utilities."""

from __future__ import annotations

import json
from pathlib import Path

from hammerdb_scale.constants import (
    AmbiguousTestIdError,
    ConfigError,
    KubectlError,
    NoResultsError,
)
from hammerdb_scale.helm.deployer import run_kubectl, helm_list
from hammerdb_scale.output import console


def discover_jobs(
    namespace: str, test_id: str, phase: str | None = None
) -> list[dict]:
    """Find all jobs for a given test run and optional phase."""
    selector = f"hammerdb.io/test-id={test_id}"
    if phase:
        selector += f",hammerdb.io/phase={phase}"

    try:
        result = run_kubectl([
            "get", "jobs",
            "-n", namespace,
            "-l", selector,
            "-o", "json",
        ])
        data = json.loads(result.stdout)
        return data.get("items", [])
    except (KubectlError, json.JSONDecodeError):
        return []


def get_job_status(job: dict) -> str:
    """Determine job status from K8s job object."""
    status = job.get("status", {})
    conditions = status.get("conditions", [])

    for cond in conditions:
        if cond.get("type") == "Complete" and cond.get("status") == "True":
            return "Completed"
        if cond.get("type") == "Failed" and cond.get("status") == "True":
            return "Failed"

    if status.get("active", 0) > 0:
        return "Running"

    # Check succeeded/failed counts
    if status.get("succeeded", 0) > 0:
        return "Completed"
    if status.get("failed", 0) > 0:
        return "Failed"

    return "Pending"


def get_job_logs(
    namespace: str, job_name: str, tail: int | None = None, follow: bool = False
) -> str:
    """Fetch logs from a job's pod."""
    args = ["logs", "-n", namespace, f"job/{job_name}"]
    if tail is not None:
        args.extend(["--tail", str(tail)])
    if follow:
        args.append("-f")

    try:
        result = run_kubectl(args, timeout=60)
        return result.stdout
    except KubectlError:
        return ""


def get_job_duration(job: dict) -> int | None:
    """Calculate job duration in seconds from start to completion time."""
    status = job.get("status", {})
    start = status.get("startTime")
    end = status.get("completionTime")

    if not start or not end:
        return None

    from datetime import datetime
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    try:
        start_dt = datetime.strptime(start, fmt)
        end_dt = datetime.strptime(end, fmt)
        return int((end_dt - start_dt).total_seconds())
    except (ValueError, TypeError):
        return None


def get_job_target_name(job: dict) -> str:
    """Extract target name from job labels."""
    labels = job.get("metadata", {}).get("labels", {})
    return labels.get("hammerdb.io/target-name", labels.get("hammerdb.io/target", "unknown"))


def get_job_target_host(job: dict) -> str:
    """Extract target host from job annotations."""
    annotations = job.get("metadata", {}).get("annotations", {})
    return annotations.get("hammerdb.io/target-host", "unknown")


def get_job_database_type(job: dict) -> str:
    """Extract database type from job labels."""
    labels = job.get("metadata", {}).get("labels", {})
    return labels.get("hammerdb.io/database-type", "unknown")



def resolve_test_id(
    cli_id: str | None,
    namespace: str,
    results_dir: Path = Path("./results"),
    deployment_name: str | None = None,
) -> str:
    """Resolve which test ID to operate on.

    1. CLI --id flag wins.
    2. K8s: most recent Helm release matching hdb-*.
    3. Local: scan results_dir for summary.json (filter by deployment_name if given).
    4. Error if none found.
    """
    if cli_id:
        return cli_id

    # Try K8s
    k8s_id = _find_most_recent_k8s_test_id(namespace)
    if k8s_id:
        return k8s_id

    # Try local results
    local_ids = _find_local_test_ids(results_dir)
    if deployment_name and len(local_ids) > 1:
        filtered = [tid for tid in local_ids if tid.startswith(deployment_name + "-")]
        if filtered:
            local_ids = filtered

    if len(local_ids) == 1:
        return local_ids[0]
    if len(local_ids) > 1:
        return sorted(local_ids)[-1]

    raise NoResultsError(
        "No test runs found in K8s or local results directory."
    )


def _find_most_recent_k8s_test_id(namespace: str) -> str | None:
    """Find the most recent test ID from Helm releases."""
    try:
        releases = helm_list(namespace)
        if not releases:
            return None

        releases.sort(key=lambda r: r.get("updated", ""), reverse=True)

        for release in releases:
            release_name = release.get("name", "")
            if not release_name.startswith("hdb-"):
                continue
            try:
                result = run_kubectl([
                    "get", "jobs",
                    "-n", namespace,
                    "-l", f"app.kubernetes.io/instance={release_name}",
                    "-o", "json",
                ])
                data = json.loads(result.stdout)
                items = data.get("items", [])
                if items:
                    labels = items[0].get("metadata", {}).get("labels", {})
                    test_id = labels.get("hammerdb.io/test-id")
                    if test_id:
                        return test_id
            except (KubectlError, json.JSONDecodeError):
                continue

        return None
    except Exception:
        return None


def _find_local_test_ids(results_dir: Path) -> list[str]:
    """Scan results directory for test IDs with summary.json."""
    if not results_dir.exists():
        return []

    ids = []
    for d in results_dir.iterdir():
        if d.is_dir() and (d / "summary.json").exists():
            ids.append(d.name)
    return ids


def resolve_benchmark(
    cli_benchmark: str | None,
    config,
    command_name: str,
) -> str:
    """Resolve which benchmark to use.

    1. CLI --benchmark flag wins.
    2. Config default_benchmark if set.
    3. Error if neither.
    """
    if cli_benchmark:
        console.print(f"Benchmark: {cli_benchmark} (from --benchmark flag)")
        return cli_benchmark

    if config.default_benchmark:
        val = config.default_benchmark.value
        console.print(f"Benchmark: {val} (from config default)")
        return val

    raise ConfigError(
        "No benchmark specified. Use --benchmark tprocc/tproch "
        "or set default_benchmark in config."
    )
