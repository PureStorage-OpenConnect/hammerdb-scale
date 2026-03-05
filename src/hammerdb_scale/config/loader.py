"""Config file discovery, YAML loading, v1 migration, and Pydantic validation."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import ValidationError

from hammerdb_scale.config.defaults import _strip_nones
from hammerdb_scale.config.schema import HammerDBScaleConfig
from hammerdb_scale.constants import (
    CONFIG_ENV_VAR,
    DEFAULT_CONFIG_FILENAMES,
    ConfigError,
)
from hammerdb_scale.output import console


def discover_config_file(explicit_path: Path | None = None) -> Path:
    """Find the config file using the 4-step discovery chain.

    1. Explicit -f path
    2. HAMMERDB_SCALE_CONFIG environment variable
    3. ./hammerdb-scale.yaml in CWD
    4. ./hammerdb-scale.yml in CWD
    """
    if explicit_path is not None:
        if not explicit_path.exists():
            raise ConfigError(f"Config file not found: {explicit_path}")
        return explicit_path

    env_path = os.environ.get(CONFIG_ENV_VAR)
    if env_path:
        p = Path(env_path)
        if not p.exists():
            raise ConfigError(
                f"Config file from {CONFIG_ENV_VAR} not found: {env_path}"
            )
        return p

    for filename in DEFAULT_CONFIG_FILENAMES:
        p = Path.cwd() / filename
        if p.exists():
            return p

    raise ConfigError(
        "No config file found. Run 'hammerdb-scale init' to create one,\n"
        "or specify a path with -f."
    )


def detect_and_migrate(data: dict) -> dict:
    """If data contains 'testRun', it's v1.x format. Convert to v2 format."""
    if "testRun" not in data:
        return data

    console.print(
        "[yellow]Detected v1.x config format. "
        "Auto-converting to v2. Run 'hammerdb-scale init' to generate "
        "a clean v2 config.[/yellow]"
    )

    v2: dict = {}

    # Name from testRun.id or generate
    v2["name"] = data.get("testRun", {}).get("id", "migrated-config")

    # Targets: extract common fields as defaults
    old_targets = data.get("targets", [])
    if old_targets:
        first = old_targets[0]
        v2["targets"] = {
            "defaults": {
                "type": first.get("type"),
                "username": first.get("username"),
                "password": first.get("password"),
            },
            "hosts": [{"name": t["name"], "host": t["host"]} for t in old_targets],
        }
        # Carry per-target overrides if they differ from first target
        for i, t in enumerate(old_targets):
            host = v2["targets"]["hosts"][i]
            if t.get("type") != first.get("type"):
                host["type"] = t["type"]
            if t.get("username") != first.get("username"):
                host["username"] = t["username"]
            if t.get("password") != first.get("password"):
                host["password"] = t["password"]

    # HammerDB config: rename fields to snake_case
    old_hdb = data.get("hammerdb", {})
    v2["hammerdb"] = {}

    if "tprocc" in old_hdb:
        tc = old_hdb["tprocc"]
        v2["hammerdb"]["tprocc"] = {
            "warehouses": tc.get("warehouses"),
            "build_virtual_users": tc.get("build_num_vu"),
            "load_virtual_users": tc.get("load_num_vu"),
            "driver": tc.get("driver", "timed"),
            "rampup": tc.get("rampup"),
            "duration": tc.get("duration"),
            "total_iterations": tc.get("total_iterations"),
            "all_warehouses": tc.get("allwarehouse"),
            "checkpoint": tc.get("checkpoint"),
            "time_profile": tc.get("timeprofile", False),
        }

    if "tproch" in old_hdb:
        th = old_hdb["tproch"]
        v2["hammerdb"]["tproch"] = {
            "scale_factor": th.get("scaleFactor"),
            "build_threads": th.get("buildThreads"),
            "build_virtual_users": th.get("build_num_vu"),
            "load_virtual_users": th.get("load_num_vu"),
            "total_querysets": th.get("totalQuerysets"),
        }

    # Image - now lives in targets.defaults.image
    g = data.get("global", {})
    if "image" in g:
        if "targets" not in v2:
            v2["targets"] = {"defaults": {}, "hosts": []}
        v2["targets"]["defaults"]["image"] = {
            "repository": g["image"].get("repository"),
            "tag": g["image"].get("tag"),
            "pull_policy": g["image"].get("pullPolicy", "Always"),
        }
    if "resources" in g:
        v2["resources"] = g["resources"]

    # Storage metrics
    ps = data.get("pureStorage", {})
    if ps:
        v2["storage_metrics"] = {
            "enabled": ps.get("enabled", False),
            "provider": "pure",
            "pure": {
                "host": ps.get("host", ""),
                "api_token": ps.get("apiToken", ""),
                "volume": ps.get("volume", ""),
                "poll_interval": ps.get("pollInterval", 5),
                "verify_ssl": ps.get("verifySSL", False),
                "api_version": ps.get("apiVersion", "2.4"),
            },
        }

    # Database-specific config
    old_dbs = data.get("databases", {})
    if "oracle" in old_dbs:
        orc = old_dbs["oracle"]
        if "targets" not in v2:
            v2["targets"] = {"defaults": {}, "hosts": []}
        v2["targets"]["defaults"]["oracle"] = {
            "service": orc.get("service", "ORCLPDB"),
            "port": orc.get("port", 1521),
            "tablespace": orc.get("tablespace", "TPCC"),
            "temp_tablespace": orc.get("tempTablespace", "TEMP"),
        }
        if "tprocc" in orc:
            v2["targets"]["defaults"]["oracle"]["tprocc"] = {
                "user": orc["tprocc"].get("user", "TPCC"),
                "password": orc["tprocc"].get("password", ""),
            }
        if "tproch" in orc:
            v2["targets"]["defaults"]["oracle"]["tproch"] = {
                "user": orc["tproch"].get("user", "tpch"),
                "password": orc["tproch"].get("password", ""),
                "degree_of_parallel": orc["tproch"].get("degreeOfParallel", 8),
            }

    # MSSQL connection config → targets.defaults.mssql.connection (v2.1 format)
    if "connection" in old_hdb:
        conn = old_hdb["connection"]
        if "targets" not in v2:
            v2["targets"] = {"defaults": {}, "hosts": []}
        if "mssql" not in v2["targets"]["defaults"]:
            v2["targets"]["defaults"]["mssql"] = {}
        v2["targets"]["defaults"]["mssql"]["connection"] = {
            "tcp": conn.get("tcp", True),
            "authentication": conn.get("authentication", "sql"),
            "odbc_driver": conn.get("odbc_driver", "ODBC Driver 18 for SQL Server"),
            "encrypt_connection": conn.get("encrypt_connection", True),
            "trust_server_cert": conn.get("trust_server_cert", True),
        }

    # Strip None values recursively
    return _strip_nones(v2)


def load_config(path: Path) -> HammerDBScaleConfig:
    """Load and validate a config file. Handles v1 migration automatically."""
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML syntax in {path}:\n{e}") from e

    if not isinstance(data, dict):
        raise ConfigError(
            f"Config file {path} must contain a YAML mapping, not {type(data).__name__}"
        )

    # Auto-migrate v1 format
    data = detect_and_migrate(data)

    try:
        return HammerDBScaleConfig(**data)
    except ValidationError as e:
        # Re-format Pydantic errors into actionable messages
        messages = []
        for err in e.errors():
            loc = " -> ".join(str(x) for x in err["loc"])
            messages.append(f"  {loc}: {err['msg']}")
        raise ConfigError(
            f"Config validation failed ({path}):\n" + "\n".join(messages)
        ) from e
