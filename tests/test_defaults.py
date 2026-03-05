"""Tests for target expansion and deep merge logic."""

from hammerdb_scale.config.defaults import _deep_merge, _strip_nones, expand_targets
from hammerdb_scale.config.schema import (
    DatabaseType,
    HammerDBScaleConfig,
    MssqlConfig,
    OracleConfig,
    TargetDefaults,
    TargetHost,
    TargetsConfig,
)


class TestDeepMerge:
    def test_flat_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 99, "z": 100}}
        result = _deep_merge(base, override)
        assert result == {"a": {"x": 1, "y": 99, "z": 100}, "b": 3}

    def test_none_values_skipped(self):
        base = {"a": 1, "b": 2}
        override = {"a": None, "c": 3}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_deep_none_skipped(self):
        base = {"a": {"x": 1, "y": 2}}
        override = {"a": {"x": None, "z": 3}}
        result = _deep_merge(base, override)
        assert result == {"a": {"x": 1, "y": 2, "z": 3}}

    def test_empty_override(self):
        base = {"a": 1}
        result = _deep_merge(base, {})
        assert result == {"a": 1}

    def test_empty_base(self):
        result = _deep_merge({}, {"a": 1})
        assert result == {"a": 1}


class TestStripNones:
    def test_removes_top_level_nones(self):
        assert _strip_nones({"a": 1, "b": None}) == {"a": 1}

    def test_removes_nested_nones(self):
        result = _strip_nones({"a": {"x": 1, "y": None}})
        assert result == {"a": {"x": 1}}

    def test_removes_empty_dicts(self):
        result = _strip_nones({"a": {"x": None}})
        assert result == {}


class TestExpandTargets:
    def test_oracle_targets_inherit_defaults(self):
        config = HammerDBScaleConfig(
            name="test",
            targets=TargetsConfig(
                defaults=TargetDefaults(
                    type=DatabaseType.oracle,
                    username="system",
                    password="pass",
                    oracle=OracleConfig(
                        service="PROD",
                        port=1521,
                        tablespace="TPCC",
                    ),
                ),
                hosts=[
                    TargetHost(name="ora-01", host="10.0.0.1"),
                    TargetHost(name="ora-02", host="10.0.0.2"),
                ],
            ),
        )
        targets = expand_targets(config)
        assert len(targets) == 2
        for t in targets:
            assert t["type"] == "oracle"
            assert t["username"] == "system"
            assert t["password"] == "pass"
            assert t["oracle"]["service"] == "PROD"
            assert t["oracle"]["port"] == 1521

    def test_oracle_per_host_override(self):
        config = HammerDBScaleConfig(
            name="test",
            targets=TargetsConfig(
                defaults=TargetDefaults(
                    type=DatabaseType.oracle,
                    username="system",
                    password="pass",
                    oracle=OracleConfig(
                        service="ORCLPDB",
                        port=1521,
                    ),
                ),
                hosts=[
                    TargetHost(name="ora-01", host="10.0.0.1"),
                    TargetHost(
                        name="ora-02",
                        host="10.0.0.2",
                        oracle=OracleConfig(
                            service="PRODPDB",
                            port=1522,
                        ),
                    ),
                ],
            ),
        )
        targets = expand_targets(config)
        assert targets[0]["oracle"]["service"] == "ORCLPDB"
        assert targets[0]["oracle"]["port"] == 1521
        assert targets[1]["oracle"]["service"] == "PRODPDB"
        assert targets[1]["oracle"]["port"] == 1522

    def test_mssql_targets_flatten_database_name(self):
        config = HammerDBScaleConfig(
            name="test",
            targets=TargetsConfig(
                defaults=TargetDefaults(
                    type=DatabaseType.mssql,
                    username="sa",
                    password="pass",
                    mssql=MssqlConfig(
                        port=1433,
                    ),
                ),
                hosts=[
                    TargetHost(name="sql-01", host="10.0.0.1"),
                ],
            ),
        )
        targets = expand_targets(config)
        assert len(targets) == 1
        assert targets[0]["type"] == "mssql"
        assert targets[0]["tprocc"]["databaseName"] == "tpcc"
        assert targets[0]["tproch"]["databaseName"] == "tpch"

    def test_mssql_per_host_database_name_override(self):
        config = HammerDBScaleConfig(
            name="test",
            targets=TargetsConfig(
                defaults=TargetDefaults(
                    type=DatabaseType.mssql,
                    username="sa",
                    password="pass",
                    mssql=MssqlConfig(port=1433),
                ),
                hosts=[
                    TargetHost(name="sql-01", host="10.0.0.1"),
                    TargetHost(
                        name="sql-02",
                        host="10.0.0.2",
                        mssql=MssqlConfig(
                            port=1434,
                        ),
                    ),
                ],
            ),
        )
        targets = expand_targets(config)
        assert targets[0]["tprocc"]["databaseName"] == "tpcc"
        assert targets[1]["tprocc"]["databaseName"] == "tpcc"

    def test_no_image_in_output(self):
        config = HammerDBScaleConfig(
            name="test",
            targets=TargetsConfig(
                defaults=TargetDefaults(
                    type=DatabaseType.oracle,
                    username="system",
                    password="pass",
                    oracle=OracleConfig(),
                ),
                hosts=[
                    TargetHost(name="ora-01", host="10.0.0.1"),
                ],
            ),
        )
        targets = expand_targets(config)
        assert "image" not in targets[0]

    def test_per_host_credentials_override(self):
        config = HammerDBScaleConfig(
            name="test",
            targets=TargetsConfig(
                defaults=TargetDefaults(
                    type=DatabaseType.oracle,
                    username="system",
                    password="pass",
                    oracle=OracleConfig(),
                ),
                hosts=[
                    TargetHost(name="ora-01", host="10.0.0.1"),
                    TargetHost(
                        name="ora-02",
                        host="10.0.0.2",
                        username="admin",
                        password="secret",
                    ),
                ],
            ),
        )
        targets = expand_targets(config)
        assert targets[0]["username"] == "system"
        assert targets[0]["password"] == "pass"
        assert targets[1]["username"] == "admin"
        assert targets[1]["password"] == "secret"

    def test_mssql_per_host_connection_override(self):
        """Per-host override of mssql.connection settings works via deep merge."""
        from hammerdb_scale.config.schema import MssqlConnectionConfig

        config = HammerDBScaleConfig(
            name="test",
            targets=TargetsConfig(
                defaults=TargetDefaults(
                    type=DatabaseType.mssql,
                    username="sa",
                    password="pass",
                    mssql=MssqlConfig(
                        port=1433,
                        connection=MssqlConnectionConfig(
                            encrypt_connection=True,
                            trust_server_cert=True,
                        ),
                    ),
                ),
                hosts=[
                    TargetHost(name="sql-01", host="10.0.0.1"),
                    TargetHost(
                        name="sql-02",
                        host="10.0.0.2",
                        mssql=MssqlConfig(
                            connection=MssqlConnectionConfig(
                                encrypt_connection=False,
                            ),
                        ),
                    ),
                ],
            ),
        )
        targets = expand_targets(config)
        # sql-01 inherits defaults
        assert targets[0]["tprocc"]["databaseName"] == "tpcc"
        # sql-02 overrides connection but keeps other defaults
        assert targets[1]["tprocc"]["databaseName"] == "tpcc"
