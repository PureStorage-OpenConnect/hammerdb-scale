"""Shared constants, defaults, and custom exceptions for HammerDB-Scale."""

from pathlib import Path

VERSION = "2.0.0"

DEFAULT_CONFIG_FILENAMES = ["hammerdb-scale.yaml", "hammerdb-scale.yml"]
CONFIG_ENV_VAR = "HAMMERDB_SCALE_CONFIG"
DEFAULT_NAMESPACE = "hammerdb"

# CLI phase -> Helm/entrypoint phase
PHASE_MAP = {"build": "build", "run": "load"}

DEFAULT_RESULTS_DIR = "results"
DEFAULT_JOB_TTL = 86400
NAMING_PREFIX = "hdb"

BUILD_TIMEOUT_DEFAULT = 7200  # 2 hours
RUN_TIMEOUT_DEFAULT = 3600  # 1 hour
POLL_INTERVAL = 10  # seconds

# Build time estimates (upper_bound_warehouses, description)
BUILD_TIME_ESTIMATES = [
    (100, "< 5 minutes"),
    (1000, "10-30 minutes"),
    (5000, "30-90 minutes"),
    (10000, "1-4 hours"),
    (float("inf"), "4+ hours"),
]


def estimate_build_time(warehouses: int) -> str:
    """Return a human-readable build time estimate for the given warehouse count."""
    for upper, desc in BUILD_TIME_ESTIMATES:
        if warehouses <= upper:
            return desc
    return "4+ hours"


def get_chart_path() -> str:
    """Return the path to the bundled Helm chart directory.

    Works for both editable installs (pip install -e .) and standard
    PyPI installs where the chart is bundled inside the package.
    """
    # Bundled chart inside the package (works for all install methods)
    bundled = Path(__file__).parent / "chart"
    if (bundled / "Chart.yaml").exists():
        return str(bundled)

    # Fallback: repo root (editable install / development)
    repo_root = Path(__file__).parent.parent.parent
    if (repo_root / "Chart.yaml").exists():
        return str(repo_root)

    raise FileNotFoundError(
        "Helm chart not found. If you installed via pip, ensure the package "
        "includes the chart/ directory. If developing locally, run from the "
        "repository root."
    )


# Default images by database type
DEFAULT_IMAGES = {
    "oracle": "sillidata/hammerdb-scale-oracle",
    "mssql": "sillidata/hammerdb-scale",
}


# --- Custom Exceptions ---


class HammerDBScaleError(Exception):
    """Base exception for all HammerDB-Scale errors."""


class ConfigError(HammerDBScaleError):
    """Configuration file errors (missing fields, invalid values, file not found)."""


class ToolNotFoundError(HammerDBScaleError):
    """Required CLI tool (helm, kubectl) not found in PATH."""


class HelmError(HammerDBScaleError):
    """Helm command execution failed."""


class KubectlError(HammerDBScaleError):
    """kubectl command execution failed."""


class AmbiguousTestIdError(HammerDBScaleError):
    """Multiple test runs found and --id not specified."""


class NoResultsError(HammerDBScaleError):
    """No test results found in K8s or local results directory."""
