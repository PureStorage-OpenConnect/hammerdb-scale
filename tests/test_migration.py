"""Tests for v1 config migration to v2 format."""

from pathlib import Path

import yaml

from hammerdb_scale.config.loader import detect_and_migrate, load_config

FIXTURES = Path(__file__).parent / "fixtures"


class TestV1Detection:
    def test_v1_detected_by_testrun_key(self):
        data = {"testRun": {"id": "test-001"}, "targets": []}
        result = detect_and_migrate(data)
        # Should have been migrated (no testRun in result)
        assert "testRun" not in result

    def test_v2_passes_through(self):
        data = {
            "name": "test",
            "targets": {
                "defaults": {"type": "oracle"},
                "hosts": [{"name": "a", "host": "b"}],
            },
        }
        result = detect_and_migrate(data)
        assert result == data


class TestOracleMigration:
    def test_load_v1_oracle_config(self):
        config = load_config(FIXTURES / "v1-oracle-config.yaml")
        assert config.name == "test-oracle-tprocc"

    def test_field_mapping_tprocc(self):
        with open(FIXTURES / "v1-oracle-config.yaml") as f:
            data = yaml.safe_load(f)
        result = detect_and_migrate(data)
        tprocc = result["hammerdb"]["tprocc"]
        # build_num_vu -> build_virtual_users
        assert tprocc["build_virtual_users"] == 2
        # load_num_vu -> load_virtual_users
        assert tprocc["load_virtual_users"] == 2
        # allwarehouse -> all_warehouses
        assert tprocc["all_warehouses"] is True
        # timeprofile -> time_profile
        assert tprocc["time_profile"] is False

    def test_image_migration(self):
        with open(FIXTURES / "v1-oracle-config.yaml") as f:
            data = yaml.safe_load(f)
        result = detect_and_migrate(data)
        image = result["targets"]["defaults"]["image"]
        assert image["repository"] == "localhost/hammerdb-scale-oracle-test"
        assert image["tag"] == "latest"
        assert image["pull_policy"] == "Never"

    def test_oracle_db_migration(self):
        with open(FIXTURES / "v1-oracle-config.yaml") as f:
            data = yaml.safe_load(f)
        result = detect_and_migrate(data)
        oracle = result["targets"]["defaults"]["oracle"]
        assert oracle["service"] == "ORCL"
        assert oracle["port"] == 1521
        assert oracle["tablespace"] == "TPCC"
        assert oracle["temp_tablespace"] == "TEMP"
        assert oracle["tprocc"]["user"] == "tpcc"

    def test_pure_storage_disabled(self):
        with open(FIXTURES / "v1-oracle-config.yaml") as f:
            data = yaml.safe_load(f)
        result = detect_and_migrate(data)
        # pureStorage.enabled: false should migrate
        assert "storage_metrics" in result
        assert result["storage_metrics"]["enabled"] is False

    def test_resources_migration(self):
        with open(FIXTURES / "v1-oracle-config.yaml") as f:
            data = yaml.safe_load(f)
        result = detect_and_migrate(data)
        assert result["resources"]["requests"]["memory"] == "2Gi"
        assert result["resources"]["limits"]["cpu"] == "2"


class TestMssqlMigration:
    def test_load_v1_mssql_config(self):
        config = load_config(FIXTURES / "v1-mssql-config.yaml")
        assert config.name == "test-mssql-tprocc"

    def test_connection_migration(self):
        with open(FIXTURES / "v1-mssql-config.yaml") as f:
            data = yaml.safe_load(f)
        result = detect_and_migrate(data)
        conn = result["targets"]["defaults"]["mssql"]["connection"]
        assert conn["tcp"] is True
        assert conn["authentication"] == "sql"
        assert conn["odbc_driver"] == "ODBC Driver 18 for SQL Server"
        assert conn["encrypt_connection"] is True
        assert conn["trust_server_cert"] is True


class TestV2ConfigLoading:
    def test_load_v2_oracle_config(self):
        config = load_config(FIXTURES / "v2-oracle-config.yaml")
        assert config.name == "oracle-scale-test"
        assert len(config.targets.hosts) == 4
        assert config.hammerdb.tprocc.warehouses == 1000

    def test_load_v2_mssql_config(self):
        config = load_config(FIXTURES / "v2-mssql-config.yaml")
        assert config.name == "mssql-scale-test"
        assert len(config.targets.hosts) == 4
        assert config.hammerdb.tprocc.warehouses == 500
