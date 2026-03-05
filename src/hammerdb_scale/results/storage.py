"""Results persistence: JSON files and log storage."""

from __future__ import annotations

import json
from pathlib import Path


def save_results(
    test_id: str,
    summary: dict,
    logs: dict[str, str],
    pure_metrics: dict | None = None,
    results_dir: Path = Path("./results"),
) -> Path:
    """Save results to results/{test-id}/ directory."""
    output_dir = results_dir / test_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write summary.json
    with open(output_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    # Write per-target log files
    for target_name, log_text in logs.items():
        with open(output_dir / f"{target_name}.log", "w") as f:
            f.write(log_text)

    # Write pure_metrics.json if available
    if pure_metrics:
        with open(output_dir / "pure_metrics.json", "w") as f:
            json.dump(pure_metrics, f, indent=2)

    return output_dir


def load_results(
    test_id: str, results_dir: Path = Path("./results")
) -> dict | None:
    """Load previously saved results from summary.json."""
    summary_path = results_dir / test_id / "summary.json"
    if not summary_path.exists():
        return None

    with open(summary_path) as f:
        return json.load(f)


def load_pure_metrics(
    test_id: str, results_dir: Path = Path("./results")
) -> dict | None:
    """Load Pure Storage metrics if available."""
    metrics_path = results_dir / test_id / "pure_metrics.json"
    if not metrics_path.exists():
        return None

    with open(metrics_path) as f:
        return json.load(f)


def results_exist(
    test_id: str, results_dir: Path = Path("./results")
) -> bool:
    """Check if results have been saved for a test ID."""
    return (results_dir / test_id / "summary.json").exists()
