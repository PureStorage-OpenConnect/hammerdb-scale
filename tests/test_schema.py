"""Tests for Pydantic config schema validation."""

import pytest
from pydantic import ValidationError

from hammerdb_scale.config.schema import (
    BenchmarkType,
    DatabaseType,
    HammerDBScaleConfig,
    ImageConfig,
    ImagePullPolicy,
    MssqlConfig,
    MssqlTprochConfig,
    OracleConfig,
    TargetDefaults,
    TargetHost,
    TargetsConfig,
)


def _minimal_config(**overrides):
    """Create a minimal valid config dict, with optional overrides."""
    data = {
        "name": "test",
        "targets": {
            "defaults": {
                "type": "oracle",
                "username": "system",
                "password": "pass",
                "oracle": {},
            },
            "hosts": [{"name": "ora-01", "host": "10.0.0.1"}],
        },
    }
    data.update(overrides)
    return data


class TestMinimalConfig:
    def test_valid_minimal(self):
        config = HammerDBScaleConfig(**_minimal_config())
        assert config.name == "test"
        assert len(config.targets.hosts) == 1
        assert config.targets.hosts[0].name == "ora-01"

    def test_missing_name(self):
        data = _minimal_config()
        del data["name"]
        with pytest.raises(ValidationError):
            HammerDBScaleConfig(**data)

    def test_empty_hosts(self):
        data = _minimal_config()
        data["targets"]["hosts"] = []
        with pytest.raises(ValidationError):
            HammerDBScaleConfig(**data)

    def test_missing_targets(self):
        with pytest.raises(ValidationError):
            HammerDBScaleConfig(name="test")


class TestRequiredFields:
    def test_host_missing_type_no_default(self):
        data = _minimal_config()
        data["targets"]["defaults"]["type"] = None
        with pytest.raises(ValidationError, match="has no database type"):
            HammerDBScaleConfig(**data)

    def test_host_missing_username_no_default(self):
        data = _minimal_config()
        data["targets"]["defaults"]["username"] = None
        with pytest.raises(ValidationError, match="has no username"):
            HammerDBScaleConfig(**data)

    def test_host_missing_password_no_default(self):
        data = _minimal_config()
        data["targets"]["defaults"]["password"] = None
        with pytest.raises(ValidationError, match="has no password"):
            HammerDBScaleConfig(**data)

    def test_host_provides_own_type(self):
        """Host can override type even if defaults has None."""
        data = _minimal_config()
        data["targets"]["defaults"]["type"] = None
        data["targets"]["hosts"][0]["type"] = "mssql"
        config = HammerDBScaleConfig(**data)
        assert config.targets.hosts[0].type == DatabaseType.mssql


class TestFieldConstraints:
    def test_port_too_low(self):
        with pytest.raises(ValidationError):
            OracleConfig(port=0)

    def test_port_too_high(self):
        with pytest.raises(ValidationError):
            OracleConfig(port=65536)

    def test_valid_port(self):
        cfg = OracleConfig(port=1521)
        assert cfg.port == 1521

    def test_warehouses_zero(self):
        data = _minimal_config()
        data["hammerdb"] = {"tprocc": {"warehouses": 0}}
        with pytest.raises(ValidationError):
            HammerDBScaleConfig(**data)

    def test_warehouses_positive(self):
        data = _minimal_config()
        data["hammerdb"] = {"tprocc": {"warehouses": 10000}}
        config = HammerDBScaleConfig(**data)
        assert config.hammerdb.tprocc.warehouses == 10000


class TestEnums:
    def test_database_type_values(self):
        assert DatabaseType.oracle.value == "oracle"
        assert DatabaseType.mssql.value == "mssql"

    def test_benchmark_type_values(self):
        assert BenchmarkType.tprocc.value == "tprocc"
        assert BenchmarkType.tproch.value == "tproch"

    def test_image_pull_policy_values(self):
        assert ImagePullPolicy.always.value == "Always"
        assert ImagePullPolicy.if_not_present.value == "IfNotPresent"
        assert ImagePullPolicy.never.value == "Never"


class TestDefaults:
    def test_oracle_defaults(self):
        cfg = OracleConfig()
        assert cfg.port == 1521
        assert cfg.service == "ORCLPDB"
        assert cfg.tablespace == "TPCC"
        assert cfg.temp_tablespace == "TEMP"

    def test_image_defaults(self):
        cfg = ImageConfig()
        assert cfg.repository == "sillidata/hammerdb-scale"
        assert cfg.tag == "latest"
        assert cfg.pull_policy == ImagePullPolicy.always

    def test_tprocc_defaults(self):
        config = HammerDBScaleConfig(**_minimal_config())
        assert config.hammerdb.tprocc.warehouses == 100
        assert config.hammerdb.tprocc.rampup == 5
        assert config.hammerdb.tprocc.duration == 10

    def test_default_benchmark_optional(self):
        config = HammerDBScaleConfig(**_minimal_config())
        assert config.default_benchmark is None


class TestImageWarnings:
    def test_oracle_with_oracle_image_no_warning(self):
        data = _minimal_config()
        data["targets"]["defaults"]["image"] = {
            "repository": "sillidata/hammerdb-scale-oracle",
            "tag": "latest",
        }
        config = HammerDBScaleConfig(**data)
        assert len(config.get_image_warnings()) == 0

    def test_oracle_with_base_image_warning(self):
        data = _minimal_config()
        data["targets"]["defaults"]["image"] = {
            "repository": "sillidata/hammerdb-scale",
            "tag": "latest",
        }
        config = HammerDBScaleConfig(**data)
        warnings = config.get_image_warnings()
        assert len(warnings) == 1
        assert "oracle" in warnings[0].lower()

    def test_mssql_with_base_image_no_warning(self):
        data = _minimal_config()
        data["targets"]["defaults"]["type"] = "mssql"
        data["targets"]["defaults"]["mssql"] = {}
        del data["targets"]["defaults"]["oracle"]
        config = HammerDBScaleConfig(**data)
        assert len(config.get_image_warnings()) == 0


class TestDatabaseTypeValidation:
    def test_oracle_type_requires_oracle_block(self):
        data = _minimal_config()
        del data["targets"]["defaults"]["oracle"]
        with pytest.raises(ValidationError, match="targets.defaults.oracle"):
            HammerDBScaleConfig(**data)

    def test_mssql_type_requires_mssql_block(self):
        data = _minimal_config()
        data["targets"]["defaults"]["type"] = "mssql"
        del data["targets"]["defaults"]["oracle"]
        with pytest.raises(ValidationError, match="targets.defaults.mssql"):
            HammerDBScaleConfig(**data)

    def test_mssql_type_with_mssql_block_valid(self):
        data = _minimal_config()
        data["targets"]["defaults"]["type"] = "mssql"
        data["targets"]["defaults"]["mssql"] = {"port": 1433}
        del data["targets"]["defaults"]["oracle"]
        config = HammerDBScaleConfig(**data)
        assert config.targets.defaults.mssql.port == 1433

    def test_inactive_type_block_ignored(self):
        """Having both oracle and mssql blocks is allowed — only active type matters."""
        data = _minimal_config()
        data["targets"]["defaults"]["mssql"] = {"port": 1433}
        config = HammerDBScaleConfig(**data)
        assert config.targets.defaults.oracle is not None
        assert config.targets.defaults.mssql is not None

    def test_maxdop_default_is_2(self):
        cfg = MssqlTprochConfig()
        assert cfg.maxdop == 2

    def test_hammerdb_mssql_not_on_model(self):
        """HammerDBConfig no longer has an mssql attribute."""
        data = _minimal_config()
        config = HammerDBScaleConfig(**data)
        assert not hasattr(config.hammerdb, "mssql")


class TestFullConfig:
    def test_all_fields_populated(self):
        data = _minimal_config()
        data["description"] = "Full test"
        data["default_benchmark"] = "tprocc"
        data["targets"]["defaults"]["image"] = {
            "repository": "sillidata/hammerdb-scale-oracle",
            "tag": "v5.0",
            "pull_policy": "IfNotPresent",
        }
        data["targets"]["defaults"]["oracle"] = {
            "service": "PROD",
            "port": 1522,
        }
        data["storage_metrics"] = {
            "enabled": True,
            "provider": "pure",
            "pure": {
                "host": "10.0.0.1",
                "api_token": "token",
            },
        }
        config = HammerDBScaleConfig(**data)
        assert config.description == "Full test"
        assert config.default_benchmark == BenchmarkType.tprocc
        assert config.targets.defaults.image.pull_policy == ImagePullPolicy.if_not_present
        assert config.targets.defaults.oracle.port == 1522
        assert config.storage_metrics.enabled is True
