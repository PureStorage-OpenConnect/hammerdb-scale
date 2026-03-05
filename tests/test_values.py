"""Tests for helm/values.py — Helm values field mapping and translation."""

from __future__ import annotations

from pathlib import Path

import yaml

from hammerdb_scale.config.loader import load_config
from hammerdb_scale.helm.values import (
    _build_databases_section,
    _build_hammerdb_section,
    _build_pure_storage_section,
    generate_helm_values,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load_oracle_config():
    return load_config(FIXTURES / "v2-oracle-config.yaml")


def _load_mssql_config():
    return load_config(FIXTURES / "v2-mssql-config.yaml")




class TestGenerateHelmValues:
    def test_top_level_keys(self):
        config = _load_oracle_config()
        vals = generate_helm_values(config, "build", "tprocc", "test-20260101-1200")
        expected_keys = {
            "testRun", "targets", "hammerdb", "global", "databases",
            "pureStorage", "naming", "extraLabels", "kubernetes",
        }
        assert set(vals.keys()) == expected_keys

    def test_test_run_section(self):
        config = _load_oracle_config()
        vals = generate_helm_values(config, "run", "tprocc", "test-20260101-1200")
        assert vals["testRun"]["id"] == "test-20260101-1200"
        assert vals["testRun"]["benchmark"] == "tprocc"

    def test_phase_mapping_run_to_load(self):
        """CLI 'run' maps to Helm 'load'."""
        config = _load_oracle_config()
        vals = generate_helm_values(config, "run", "tprocc", "test-id")
        assert vals["testRun"]["phase"] == "load"

    def test_phase_mapping_build_stays_build(self):
        config = _load_oracle_config()
        vals = generate_helm_values(config, "build", "tprocc", "test-id")
        assert vals["testRun"]["phase"] == "build"

    def test_targets_expanded(self):
        config = _load_oracle_config()
        vals = generate_helm_values(config, "build", "tprocc", "test-id")
        assert isinstance(vals["targets"], list)
        assert len(vals["targets"]) == 4
        assert vals["targets"][0]["name"] == "ora-01"

    def test_image_section(self):
        config = _load_oracle_config()
        vals = generate_helm_values(config, "build", "tprocc", "test-id")
        img = vals["global"]["image"]
        assert img["repository"] == "sillidata/hammerdb-scale-oracle"
        assert img["tag"] == "latest"
        assert img["pullPolicy"] == "Always"

    def test_naming_section(self):
        config = _load_oracle_config()
        vals = generate_helm_values(config, "build", "tprocc", "test-id")
        assert vals["naming"]["useV2Naming"] is True
        assert vals["naming"]["prefix"] == "hdb"
        assert len(vals["naming"]["runHash"]) == 8

    def test_extra_labels_contain_test_id(self):
        config = _load_oracle_config()
        vals = generate_helm_values(config, "run", "tprocc", "my-test-id")
        assert vals["extraLabels"]["hammerdb.io/test-id"] == "my-test-id"

    def test_kubernetes_job_ttl(self):
        config = _load_oracle_config()
        vals = generate_helm_values(config, "build", "tprocc", "test-id")
        assert vals["kubernetes"]["job_ttl"] == 86400




class TestBuildHammerdbSection:
    def test_tprocc_camel_case_mapping(self):
        """v2 snake_case → v1 camelCase."""
        config = _load_oracle_config()
        section = _build_hammerdb_section(config, "tprocc")
        tc = section["tprocc"]
        assert "build_num_vu" in tc  # build_virtual_users → build_num_vu
        assert "load_num_vu" in tc  # load_virtual_users → load_num_vu
        assert "allwarehouse" in tc  # all_warehouses → allwarehouse
        assert "timeprofile" in tc  # time_profile → timeprofile

    def test_tprocc_values(self):
        config = _load_oracle_config()
        section = _build_hammerdb_section(config, "tprocc")
        tc = section["tprocc"]
        assert tc["warehouses"] == 1000
        assert tc["build_num_vu"] == 32
        assert tc["load_num_vu"] == 200
        assert tc["allwarehouse"] is True
        assert tc["checkpoint"] is True
        assert tc["timeprofile"] is False

    def test_tproch_section(self):
        config = _load_oracle_config()
        section = _build_hammerdb_section(config, "tprocc")
        th = section["tproch"]
        assert "scaleFactor" in th
        assert "buildThreads" in th
        assert "totalQuerysets" in th

    def test_connection_section(self):
        config = _load_mssql_config()
        section = _build_hammerdb_section(config, "tprocc")
        conn = section["connection"]
        assert conn["tcp"] is True
        assert conn["authentication"] == "sql"
        assert "odbc_driver" in conn




class TestBuildDatabasesSection:
    def test_oracle_config_present(self):
        config = _load_oracle_config()
        section = _build_databases_section(config)
        assert "oracle" in section
        oracle = section["oracle"]
        assert oracle["port"] == 1521
        assert oracle["service"] == "ORCLPDB"
        assert oracle["tablespace"] == "TPCC"
        assert oracle["tempTablespace"] == "TEMP"

    def test_oracle_tprocc_user(self):
        config = _load_oracle_config()
        section = _build_databases_section(config)
        assert section["oracle"]["tprocc"]["user"] == "TPCC"

    def test_oracle_tproch_degree_of_parallel(self):
        config = _load_oracle_config()
        section = _build_databases_section(config)
        assert section["oracle"]["tproch"]["degreeOfParallel"] == 8

    def test_mssql_always_included(self):
        config = _load_oracle_config()
        section = _build_databases_section(config)
        assert "mssql" in section
        assert section["mssql"]["driver"] == "mssqls"

    def test_mssql_port(self):
        config = _load_mssql_config()
        section = _build_databases_section(config)
        assert section["mssql"]["port"] == 1433

    def test_no_oracle_uses_defaults(self):
        """When no oracle config, provide template-compatible defaults."""
        config = _load_mssql_config()
        section = _build_databases_section(config)
        oracle = section["oracle"]
        assert oracle["port"] == 1521
        assert oracle["service"] == "ORCLPDB"




class TestBuildPureStorageSection:
    def test_disabled_by_default(self):
        config = _load_oracle_config()
        section = _build_pure_storage_section(config)
        assert section["enabled"] is False

    def test_camel_case_keys(self):
        config = _load_oracle_config()
        section = _build_pure_storage_section(config)
        assert "apiToken" in section
        assert "pollInterval" in section
        assert "verifySSL" in section
        assert "apiVersion" in section

    def test_default_values(self):
        config = _load_oracle_config()
        section = _build_pure_storage_section(config)
        assert section["pollInterval"] == 5
        assert section["verifySSL"] is False
        assert section["apiVersion"] == "2.4"
