"""Translate v2 config schema into v1 Helm-compatible values dict."""

from __future__ import annotations

from hammerdb_scale.config.defaults import expand_targets
from hammerdb_scale.config.schema import HammerDBScaleConfig, MssqlConfig
from hammerdb_scale.constants import PHASE_MAP, VERSION
from hammerdb_scale.k8s.naming import generate_run_hash


def generate_helm_values(
    config: HammerDBScaleConfig,
    phase: str,  # CLI phase: "build" or "run"
    benchmark: str,  # "tprocc" or "tproch"
    test_id: str,
) -> dict:
    """Produce a dict matching the existing Helm values.yaml schema.

    Image comes from targets.defaults.image (all targets in a single
    Helm release share the same image).
    """
    targets = expand_targets(config)
    run_hash = generate_run_hash(config.name, test_id)

    # Map CLI phase to Helm phase
    helm_phase = PHASE_MAP.get(phase, phase)

    # Resolve image from targets.defaults
    default_image = config.targets.defaults.image

    values = {
        "testRun": {
            "id": test_id,
            "phase": helm_phase,
            "benchmark": benchmark,
        },
        "targets": targets,
        "hammerdb": _build_hammerdb_section(config, benchmark),
        "global": {
            "image": {
                "repository": default_image.repository,
                "tag": default_image.tag,
                "pullPolicy": default_image.pull_policy.value,
            },
            "resources": {
                "requests": config.resources.requests.model_dump(),
                "limits": config.resources.limits.model_dump(),
            },
        },
        "databases": _build_databases_section(config),
        "pureStorage": _build_pure_storage_section(config),
        # v2 additions for naming
        "naming": {
            "prefix": "hdb",
            "runHash": run_hash,
            "useV2Naming": True,
        },
        "extraLabels": {
            "hammerdb.io/version": VERSION,
            "hammerdb.io/test-id": test_id,
            "hammerdb.io/deployment-name": config.name,
        },
        "kubernetes": {
            "job_ttl": config.kubernetes.job_ttl,
        },
    }

    return values


def _build_hammerdb_section(config: HammerDBScaleConfig, benchmark: str) -> dict:
    """Translate v2 snake_case fields to v1 camelCase Helm values."""
    section: dict = {}

    # Connection settings (MSSQL-specific, but always included for Helm compatibility)
    mssql_cfg = config.targets.defaults.mssql or MssqlConfig()
    section["connection"] = {
        "tcp": mssql_cfg.connection.tcp,
        "port": mssql_cfg.port,
        "azure": False,
        "authentication": mssql_cfg.connection.authentication,
        "odbc_driver": mssql_cfg.connection.odbc_driver,
        "linux_odbc": mssql_cfg.connection.odbc_driver,
        "encrypt_connection": mssql_cfg.connection.encrypt_connection,
        "trust_server_cert": mssql_cfg.connection.trust_server_cert,
    }

    # TPC-C settings
    tc = config.hammerdb.tprocc
    section["tprocc"] = {
        "warehouses": tc.warehouses,
        "build_num_vu": tc.build_virtual_users,
        "load_num_vu": tc.load_virtual_users,
        "use_bcp": mssql_cfg.tprocc.use_bcp,
        "driver": tc.driver,
        "rampup": tc.rampup,
        "duration": tc.duration,
        "total_iterations": tc.total_iterations,
        "allwarehouse": tc.all_warehouses,
        "checkpoint": tc.checkpoint,
        "timeprofile": tc.time_profile,
    }

    # TPC-H settings
    th = config.hammerdb.tproch
    section["tproch"] = {
        "scaleFactor": th.scale_factor,
        "buildThreads": th.build_threads,
        "build_num_vu": th.build_virtual_users,
        "load_num_vu": th.load_virtual_users,
        "totalQuerysets": th.total_querysets,
        "maxdop": mssql_cfg.tproch.maxdop,
        "useClusteredColumnstore": mssql_cfg.tproch.use_clustered_columnstore,
    }

    return section


def _build_databases_section(config: HammerDBScaleConfig) -> dict:
    """Produce the databases: block in v1 Helm format."""
    section: dict = {}

    # Always include both for template compatibility
    mssql_cfg = config.targets.defaults.mssql or MssqlConfig()
    section["mssql"] = {
        "driver": "mssqls",
        "port": mssql_cfg.port,
    }

    # Oracle config from targets.defaults.oracle
    oracle = config.targets.defaults.oracle
    if oracle:
        section["oracle"] = {
            "driver": "oracle",
            "port": oracle.port,
            "service": oracle.service,
            "tablespace": oracle.tablespace,
            "tempTablespace": oracle.temp_tablespace,
            "tprocc": {
                "user": oracle.tprocc.user,
                "password": oracle.tprocc.password,
            },
            "tproch": {
                "user": oracle.tproch.user,
                "password": oracle.tproch.password,
                "degreeOfParallel": oracle.tproch.degree_of_parallel,
            },
        }
    else:
        # Provide defaults for template compatibility
        section["oracle"] = {
            "driver": "oracle",
            "port": 1521,
            "service": "ORCLPDB",
            "tablespace": "TPCC",
            "tempTablespace": "TEMP",
            "tprocc": {"user": "TPCC", "password": ""},
            "tproch": {"user": "tpch", "password": "", "degreeOfParallel": 8},
        }

    return section


def _build_pure_storage_section(config: HammerDBScaleConfig) -> dict:
    """Produce the pureStorage: block in v1 Helm format."""
    sm = config.storage_metrics
    pure = sm.pure
    section = {
        "enabled": sm.enabled,
        "host": pure.host,
        "apiToken": pure.api_token,
        "volume": pure.volume,
        "pollInterval": pure.poll_interval,
        "verifySSL": pure.verify_ssl,
        "apiVersion": pure.api_version,
    }
    if pure.duration is not None:
        section["duration"] = pure.duration
    return section
