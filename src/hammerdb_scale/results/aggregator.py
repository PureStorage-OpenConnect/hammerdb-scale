"""Result aggregation: discover jobs, fetch logs, parse, build summary."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from hammerdb_scale.config.schema import HammerDBScaleConfig
from hammerdb_scale.constants import VERSION
from hammerdb_scale.k8s.jobs import (
    discover_jobs,
    get_job_database_type,
    get_job_duration,
    get_job_logs,
    get_job_status,
    get_job_target_host,
    get_job_target_name,
)
from hammerdb_scale.results.parsers import get_parser


_PURE_JSON_START = ">>>PURE_METRICS_JSON_START<<<"
_PURE_JSON_END = ">>>PURE_METRICS_JSON_END<<<"


def _extract_pure_metrics_from_log(log_text: str) -> dict | None:
    """Extract Pure Storage metrics from log output.

    Tries two methods:
    1. JSON block between delimiters (new entrypoint images)
    2. Fallback: parse 'Sample #N:' log lines (older images)

    Returns the parsed dict matching the collector JSON format, or None.
    """
    # Method 1: Delimited JSON block
    start = log_text.find(_PURE_JSON_START)
    end = log_text.find(_PURE_JSON_END)
    if start != -1 and end != -1 and end > start:
        raw = log_text[start + len(_PURE_JSON_START):end].strip()
        if raw:
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                pass

    # Method 2: Parse structured log sample lines + summary stats
    # Sample format: "Sample #N: R:571 IOPS W:127520 IOPS R_lat:416µs W_lat:1026µs"
    sample_pattern = (
        r"Sample #(\d+):\s+"
        r"R:(\d+)\s+IOPS\s+"
        r"W:(\d+)\s+IOPS\s+"
        r"R_lat:(\d+)µs\s+"
        r"W_lat:(\d+)µs"
    )
    matches = re.findall(sample_pattern, log_text)
    if not matches:
        return None

    raw_metrics = []
    for m in matches:
        raw_metrics.append({
            "timestamp": "",
            "read_iops": int(m[1]),
            "write_iops": int(m[2]),
            "read_latency_us": int(m[3]),
            "write_latency_us": int(m[4]),
            "read_bandwidth_mbps": 0,
            "write_bandwidth_mbps": 0,
        })

    # Parse the summary stats block printed by the collector
    summary = _parse_pure_summary_from_log(log_text)

    return {"raw_metrics": raw_metrics, "summary": summary, "metadata": {}}


def _parse_pure_summary_from_log(log_text: str) -> dict:
    """Parse the PURE STORAGE PERFORMANCE SUMMARY block from log output."""
    summary: dict = {}

    def _extract(pattern: str, *keys: str) -> None:
        m = re.search(pattern, log_text)
        if m:
            for i, key in enumerate(keys):
                try:
                    summary[key] = float(m.group(i + 1))
                except (ValueError, IndexError):
                    pass

    _extract(
        r"Read Latency \(µs\):\s+avg=(\d+)\s+p95=(\d+)\s+p99=(\d+)",
        "read_latency_us_avg", "read_latency_us_p95", "read_latency_us_p99",
    )
    _extract(
        r"Write Latency \(µs\):\s+avg=(\d+)\s+p95=(\d+)\s+p99=(\d+)",
        "write_latency_us_avg", "write_latency_us_p95", "write_latency_us_p99",
    )
    _extract(
        r"Read IOPS:\s+avg=(\d+)\s+max=(\d+)",
        "read_iops_avg", "read_iops_max",
    )
    _extract(
        r"Write IOPS:\s+avg=(\d+)\s+max=(\d+)",
        "write_iops_avg", "write_iops_max",
    )
    _extract(
        r"Read BW \(MB/s\):\s+avg=([0-9.]+)\s+max=([0-9.]+)",
        "read_bandwidth_mbps_avg", "read_bandwidth_mbps_max",
    )
    _extract(
        r"Write BW \(MB/s\):\s+avg=([0-9.]+)\s+max=([0-9.]+)",
        "write_bandwidth_mbps_avg", "write_bandwidth_mbps_max",
    )
    _extract(
        r"Avg Read Block \(KB\):\s+([0-9.]+)",
        "avg_read_block_size_kb",
    )
    _extract(
        r"Avg Write Block \(KB\):\s+([0-9.]+)",
        "avg_write_block_size_kb",
    )

    return summary


def aggregate_results(
    config: HammerDBScaleConfig,
    namespace: str,
    test_id: str,
    benchmark: str,
    results_dir: Path = Path("./results"),
) -> dict:
    """Aggregate results from all jobs for a test run."""
    # Determine phase to look for (run jobs have phase=load in Helm)
    jobs = discover_jobs(namespace, test_id, phase="load")
    if not jobs:
        jobs = discover_jobs(namespace, test_id, phase="run")
    if not jobs:
        jobs = discover_jobs(namespace, test_id)

    # Sort jobs by target index
    def _sort_key(j):
        labels = j.get("metadata", {}).get("labels", {})
        try:
            return int(labels.get("hammerdb.io/target-index", "99"))
        except ValueError:
            return 99

    jobs.sort(key=_sort_key)

    # Determine db type
    db_type = "oracle"
    if config.targets.defaults.type:
        db_type = config.targets.defaults.type.value

    # Build per-target results
    targets_results = []
    logs_dict: dict[str, str] = {}
    pure_metrics = None

    for i, job in enumerate(jobs):
        job_name = job.get("metadata", {}).get("name", "")
        target_name = get_job_target_name(job)
        target_host = get_job_target_host(job)
        job_db_type = get_job_database_type(job)
        if job_db_type != "unknown":
            db_type = job_db_type

        status = get_job_status(job)
        duration = get_job_duration(job)
        log_text = get_job_logs(namespace, job_name)

        logs_dict[target_name] = log_text

        # Extract Pure Storage metrics from the collector pod (index 0)
        if i == 0 and config.storage_metrics.enabled and pure_metrics is None:
            pure_metrics = _extract_pure_metrics_from_log(log_text)

        parser = get_parser(db_type)
        target_result: dict = {
            "name": target_name,
            "host": target_host,
            "index": i,
            "status": status.lower(),
            "duration_seconds": duration,
        }

        if status == "Completed":
            if benchmark == "tprocc":
                parsed = parser.parse_tprocc(log_text)
                if parsed:
                    target_result["tprocc"] = {
                        "tpm": parsed.tpm,
                        "nopm": parsed.nopm,
                    }
            elif benchmark == "tproch":
                parsed = parser.parse_tproch(log_text)
                if parsed:
                    target_result["tproch"] = {
                        "qphh": parsed.qphh,
                        "queries": [
                            {"query": q.query_number, "time_seconds": q.time_seconds}
                            for q in parsed.queries
                        ],
                    }
        elif status == "Failed":
            error = parser.detect_error(log_text)
            if error:
                target_result["error"] = error

        targets_results.append(target_result)

    # Build aggregate
    aggregate = _build_aggregate(targets_results, benchmark)

    # Build config summary
    config_summary = {
        "database_type": db_type,
        "target_count": len(config.targets.hosts),
        "image": f"{config.targets.defaults.image.repository}:{config.targets.defaults.image.tag}",
    }
    if benchmark == "tprocc":
        config_summary.update({
            "warehouses": config.hammerdb.tprocc.warehouses,
            "virtual_users": config.hammerdb.tprocc.load_virtual_users,
            "rampup_minutes": config.hammerdb.tprocc.rampup,
            "duration_minutes": config.hammerdb.tprocc.duration,
        })
    elif benchmark == "tproch":
        config_summary.update({
            "scale_factor": config.hammerdb.tproch.scale_factor,
            "virtual_users": config.hammerdb.tproch.load_virtual_users,
        })

    summary = {
        "version": VERSION,
        "test_id": test_id,
        "deployment_name": config.name,
        "phase": "run",
        "benchmark": benchmark,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": config_summary,
        "targets": targets_results,
        "aggregate": aggregate,
        "storage_metrics": {
            "available": pure_metrics is not None,
            "source": "pure_metrics.json" if pure_metrics else None,
        },
    }

    return summary, logs_dict, pure_metrics


def _build_aggregate(targets: list[dict], benchmark: str) -> dict:
    """Build aggregate stats from completed targets."""
    completed = [t for t in targets if t["status"] == "completed"]
    failed = [t for t in targets if t["status"] == "failed"]

    if benchmark == "tprocc":
        tpms = [t["tprocc"]["tpm"] for t in completed if "tprocc" in t]
        nopms = [t["tprocc"]["nopm"] for t in completed if "tprocc" in t]
        return {
            "total_tpm": sum(tpms),
            "total_nopm": sum(nopms),
            "avg_tpm": int(sum(tpms) / len(tpms)) if tpms else 0,
            "targets_completed": len(completed),
            "targets_failed": len(failed),
        }
    elif benchmark == "tproch":
        qphhs = [t["tproch"]["qphh"] for t in completed if "tproch" in t]

        # Per-query averages
        per_query: dict[int, list[float]] = {}
        for t in completed:
            if "tproch" in t:
                for q in t["tproch"].get("queries", []):
                    qn = q["query"]
                    per_query.setdefault(qn, []).append(q["time_seconds"])

        per_query_avg = []
        for qn in sorted(per_query):
            times = per_query[qn]
            per_query_avg.append({
                "query": qn,
                "avg_seconds": round(sum(times) / len(times), 2),
                "min_seconds": round(min(times), 2),
                "max_seconds": round(max(times), 2),
            })

        return {
            "avg_qphh": round(sum(qphhs) / len(qphhs), 1) if qphhs else 0,
            "per_query_avg": per_query_avg,
            "targets_completed": len(completed),
            "targets_failed": len(failed),
        }

    return {"targets_completed": len(completed), "targets_failed": len(failed)}
