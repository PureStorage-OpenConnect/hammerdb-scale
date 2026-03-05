"""Subprocess wrappers for helm and kubectl."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

from hammerdb_scale.constants import HelmError, KubectlError, ToolNotFoundError


def find_binary(name: str) -> Path | None:
    """Cross-platform binary discovery."""
    path = shutil.which(name)
    return Path(path) if path else None


def run_helm(
    args: list[str], capture: bool = True, timeout: int = 300
) -> subprocess.CompletedProcess:
    """Run helm with consistent error handling."""
    helm = find_binary("helm")
    if not helm:
        raise ToolNotFoundError(
            "helm not found. Install from https://helm.sh/docs/intro/install/"
        )
    cmd = [str(helm)] + args
    result = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise HelmError(f"helm {' '.join(args)} failed:\n{result.stderr}")
    return result


def run_kubectl(
    args: list[str], capture: bool = True, timeout: int = 300
) -> subprocess.CompletedProcess:
    """Run kubectl with consistent error handling."""
    kubectl = find_binary("kubectl")
    if not kubectl:
        raise ToolNotFoundError(
            "kubectl not found. Install from https://kubernetes.io/docs/tasks/tools/"
        )
    cmd = [str(kubectl)] + args
    result = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise KubectlError(f"kubectl {' '.join(args)} failed:\n{result.stderr}")
    return result


def helm_install(
    release_name: str,
    chart_path: str,
    namespace: str,
    values_dict: dict,
    dry_run: bool = False,
) -> subprocess.CompletedProcess:
    """Install a Helm release with a generated values dict."""
    # Write values to temp file
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    try:
        yaml.dump(values_dict, tmp, default_flow_style=False, sort_keys=False)
        tmp.close()  # Close before helm reads (Windows compatibility)

        args = [
            "install",
            release_name,
            chart_path,
            "-n",
            namespace,
            "--create-namespace",
            "-f",
            tmp.name,
        ]
        if dry_run:
            args.extend(["--dry-run", "--debug"])

        return run_helm(args)
    finally:
        Path(tmp.name).unlink(missing_ok=True)


def helm_uninstall(release_name: str, namespace: str) -> subprocess.CompletedProcess:
    """Uninstall a Helm release."""
    return run_helm(["uninstall", release_name, "-n", namespace])


def helm_list(namespace: str, filter_pattern: str = "hdb-") -> list[dict]:
    """List Helm releases matching a pattern."""
    result = run_helm(
        [
            "list",
            "-n",
            namespace,
            "--filter",
            filter_pattern,
            "-o",
            "json",
        ]
    )
    try:
        return json.loads(result.stdout) if result.stdout.strip() else []
    except json.JSONDecodeError:
        return []
