"""Target expansion logic: merge defaults into each host to produce flat target dicts."""

from __future__ import annotations

from hammerdb_scale.config.schema import DatabaseType, HammerDBScaleConfig


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Override wins on conflicts.

    None values in override are skipped (Pydantic Optional fields serialize
    to None when not set; we must not overwrite defaults with None).
    """
    result = base.copy()
    for key, value in override.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _strip_nones(d: dict) -> dict:
    """Recursively remove None values from a dict."""
    result = {}
    for key, value in d.items():
        if value is None:
            continue
        if isinstance(value, dict):
            cleaned = _strip_nones(value)
            if cleaned:
                result[key] = cleaned
        else:
            result[key] = value
    return result


def expand_targets(config: HammerDBScaleConfig) -> list[dict]:
    """Merge defaults into each host to produce flat target dicts."""
    defaults = config.targets.defaults
    expanded = []

    for host in config.targets.hosts:
        target: dict = {
            "name": host.name,
            "host": host.host,
            "type": (host.type or defaults.type).value,
            "username": host.username or defaults.username,
            "password": host.password or defaults.password,
        }

        # Deep merge database-specific config
        effective_type = host.type or defaults.type
        if effective_type == DatabaseType.oracle:
            oracle = _deep_merge(
                defaults.oracle.model_dump() if defaults.oracle else {},
                host.oracle.model_dump(exclude_none=True) if host.oracle else {},
            )
            target["oracle"] = oracle
        elif effective_type == DatabaseType.mssql:
            mssql = _deep_merge(
                defaults.mssql.model_dump() if defaults.mssql else {},
                host.mssql.model_dump(exclude_none=True) if host.mssql else {},
            )
            target["tprocc"] = {
                "databaseName": mssql.get("tprocc", {}).get("database_name", "tpcc")
            }
            target["tproch"] = {
                "databaseName": mssql.get("tproch", {}).get("database_name", "tpch")
            }

        expanded.append(target)

    return expanded
