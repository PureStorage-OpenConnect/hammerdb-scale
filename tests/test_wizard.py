"""Tests for the interactive configuration wizard."""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from rich.console import Console

from hammerdb_scale.cli import _build_config_yaml
from hammerdb_scale.wizard import _build_summary_table, run_wizard


# ── Fixtures ────────────────────────────────────────────────────────────────


def _oracle_values() -> dict:
    """Minimal Oracle TPC-C wizard values."""
    return {
        "name": "oracle-bench",
        "db_type_str": "oracle",
        "benchmark_str": "tprocc",
        "hosts": [
            {"name": "ora-01", "host": "10.0.0.1"},
            {"name": "ora-02", "host": "10.0.0.2"},
        ],
        "username": "system",
        "password": "secret123",
        "oracle_config": {
            "service": "ORCLPDB",
            "port": 1521,
            "tablespace": "TPCC",
            "temp_tablespace": "TEMP",
            "tprocc": {"user": "TPCC", "password": "secret123"},
            "tproch": {"user": "tpch", "password": "secret123"},
        },
        "warehouses": 500,
        "scale_factor": 1,
        "namespace": "hammerdb",
        "storage_metrics": None,
    }


def _mssql_values() -> dict:
    """Minimal MSSQL TPC-H wizard values."""
    return {
        "name": "mssql-bench",
        "db_type_str": "mssql",
        "benchmark_str": "tproch",
        "hosts": [{"name": "sql-01", "host": "10.0.0.10"}],
        "username": "sa",
        "password": "P@ssw0rd",
        "oracle_config": None,
        "warehouses": 100,
        "scale_factor": 10,
        "namespace": "benchmarks",
        "storage_metrics": {
            "enabled": True,
            "provider": "pure",
            "pure": {
                "host": "flasharray.local",
                "api_token": "token123",
                "volume": "",
                "poll_interval": 5,
                "verify_ssl": False,
                "api_version": "2.4",
            },
        },
    }


# ── Summary Table Tests ────────────────────────────────────────────────────


class TestBuildSummaryTable:
    def test_oracle_tprocc_table(self) -> None:
        values = _oracle_values()
        table = _build_summary_table(values)
        assert table.row_count > 0
        # Render to string to verify content
        buf = StringIO()
        c = Console(file=buf, width=100)
        c.print(table)
        output = buf.getvalue()
        assert "oracle-bench" in output
        assert "Oracle" in output
        assert "TPC-C" in output
        assert "ora-01" in output
        assert "ora-02" in output
        assert "500" in output
        assert "ORCLPDB" in output
        assert "********" in output
        assert "secret123" not in output

    def test_mssql_tproch_table(self) -> None:
        values = _mssql_values()
        table = _build_summary_table(values)
        buf = StringIO()
        c = Console(file=buf, width=100)
        c.print(table)
        output = buf.getvalue()
        assert "mssql-bench" in output
        assert "SQL Server" in output
        assert "TPC-H" in output
        assert "sql-01" in output
        assert "10" in output  # scale factor
        assert "benchmarks" in output  # namespace
        assert "flasharray.local" in output
        assert "P@ssw0rd" not in output

    def test_advanced_values_shown(self) -> None:
        values = _oracle_values()
        values["build_virtual_users"] = 16
        values["load_virtual_users"] = 32
        table = _build_summary_table(values)
        buf = StringIO()
        c = Console(file=buf, width=100)
        c.print(table)
        output = buf.getvalue()
        assert "16" in output
        assert "32" in output

    def test_default_advanced_not_shown(self) -> None:
        """Advanced values at defaults should not add extra rows."""
        values = _oracle_values()
        values["build_virtual_users"] = 4
        values["load_virtual_users"] = 4
        table = _build_summary_table(values)
        buf = StringIO()
        c = Console(file=buf, width=100)
        c.print(table)
        output = buf.getvalue()
        assert "Build VUs" not in output


# ── Wizard Flow Tests (mocked prompts) ──────────────────────────────────────


class TestRunWizard:
    @patch("hammerdb_scale.wizard.Confirm")
    @patch("hammerdb_scale.wizard.IntPrompt")
    @patch("hammerdb_scale.wizard.Prompt")
    def test_oracle_tprocc_basic(self, mock_prompt, mock_int, mock_confirm) -> None:
        """Full wizard flow for Oracle TPC-C without advanced options."""
        mock_prompt.ask.side_effect = [
            "my-bench",  # deployment name
            "1",  # oracle
            "1",  # tprocc
            "ora-01",  # target name
            "10.0.0.1",  # target host
            "system",  # username
            "pass",  # password
            "ORCLPDB",  # oracle service
            "pass",  # schema password (reuse)
            "hammerdb",  # namespace
        ]
        mock_int.ask.side_effect = [
            1,  # num targets
            100,  # warehouses
        ]
        mock_confirm.ask.side_effect = [
            False,  # pure storage
            False,  # advanced
            True,  # write confirmation
        ]

        result = run_wizard()

        assert result is not None
        assert result["name"] == "my-bench"
        assert result["db_type_str"] == "oracle"
        assert result["benchmark_str"] == "tprocc"
        assert len(result["hosts"]) == 1
        assert result["hosts"][0]["name"] == "ora-01"
        assert result["oracle_config"] is not None
        assert result["oracle_config"]["service"] == "ORCLPDB"

    @patch("hammerdb_scale.wizard.Confirm")
    @patch("hammerdb_scale.wizard.IntPrompt")
    @patch("hammerdb_scale.wizard.Prompt")
    def test_mssql_tproch_basic(self, mock_prompt, mock_int, mock_confirm) -> None:
        """Full wizard flow for MSSQL TPC-H."""
        mock_prompt.ask.side_effect = [
            "sql-test",  # deployment name
            "2",  # mssql
            "2",  # tproch
            "sql-01",  # target name
            "10.0.0.5",  # target host
            "sa",  # username
            "pass",  # password
            "hammerdb",  # namespace
        ]
        mock_int.ask.side_effect = [
            1,  # num targets
            10,  # scale factor
        ]
        mock_confirm.ask.side_effect = [
            False,  # pure storage
            False,  # advanced
            True,  # write confirmation
        ]

        result = run_wizard()

        assert result is not None
        assert result["db_type_str"] == "mssql"
        assert result["benchmark_str"] == "tproch"
        assert result["oracle_config"] is None
        assert result["scale_factor"] == 10

    @patch("hammerdb_scale.wizard.Confirm")
    @patch("hammerdb_scale.wizard.IntPrompt")
    @patch("hammerdb_scale.wizard.Prompt")
    def test_user_cancels_at_confirmation(
        self, mock_prompt, mock_int, mock_confirm
    ) -> None:
        """Wizard returns None when user declines at the write confirmation."""
        mock_prompt.ask.side_effect = [
            "test",
            "2",
            "1",
            "db-01",
            "10.0.0.1",
            "sa",
            "pass",
            "hammerdb",
        ]
        mock_int.ask.side_effect = [1, 100]
        mock_confirm.ask.side_effect = [
            False,  # pure storage
            False,  # advanced
            False,  # decline write
        ]

        result = run_wizard()
        assert result is None

    @patch("hammerdb_scale.wizard.Confirm")
    @patch("hammerdb_scale.wizard.IntPrompt")
    @patch("hammerdb_scale.wizard.Prompt")
    def test_with_advanced_options(self, mock_prompt, mock_int, mock_confirm) -> None:
        """Wizard with advanced options for TPC-C."""
        mock_prompt.ask.side_effect = [
            "adv-bench",
            "2",
            "1",  # name, mssql, tprocc
            "db-01",
            "10.0.0.1",  # target
            "sa",
            "pass",  # credentials
            "hammerdb",  # namespace
            "8Gi",
            "8",
            "16Gi",
            "16",  # resources
        ]
        mock_int.ask.side_effect = [
            1,  # num targets
            200,  # warehouses
            8,  # build VUs
            32,  # load VUs
            10,  # rampup
            30,  # duration
        ]
        mock_confirm.ask.side_effect = [
            False,  # pure storage
            True,  # want advanced
            True,  # write confirmation
        ]

        result = run_wizard()

        assert result is not None
        assert result["build_virtual_users"] == 8
        assert result["load_virtual_users"] == 32
        assert result["rampup"] == 10
        assert result["duration"] == 30
        assert result["req_memory"] == "8Gi"
        assert result["lim_cpu"] == "16"

    @patch("hammerdb_scale.wizard.Confirm")
    @patch("hammerdb_scale.wizard.IntPrompt")
    @patch("hammerdb_scale.wizard.Prompt")
    def test_ctrl_c_returns_none(self, mock_prompt, mock_int, mock_confirm) -> None:
        """Ctrl+C during wizard returns None gracefully."""
        mock_prompt.ask.side_effect = KeyboardInterrupt

        result = run_wizard()
        assert result is None


# ── YAML Output Tests ───────────────────────────────────────────────────────


class TestYamlOutput:
    def test_wizard_values_produce_valid_yaml(self) -> None:
        """Wizard values dict can be passed to _build_config_yaml."""
        values = _oracle_values()
        yaml_str = _build_config_yaml(**values)
        assert "name: oracle-bench" in yaml_str
        assert "type: oracle" in yaml_str
        assert "warehouses: 500" in yaml_str
        assert 'host: "10.0.0.1"' in yaml_str
        assert 'host: "10.0.0.2"' in yaml_str

    def test_mssql_yaml_output(self) -> None:
        values = _mssql_values()
        yaml_str = _build_config_yaml(**values)
        assert "name: mssql-bench" in yaml_str
        assert "type: mssql" in yaml_str
        assert "namespace: benchmarks" in yaml_str
        assert "enabled: true" in yaml_str
        assert "flasharray.local" in yaml_str

    def test_advanced_overrides_in_yaml(self) -> None:
        values = _oracle_values()
        values["build_virtual_users"] = 16
        values["load_virtual_users"] = 64
        values["rampup"] = 15
        values["duration"] = 30
        values["req_memory"] = "8Gi"
        values["lim_cpu"] = "16"
        yaml_str = _build_config_yaml(**values)
        assert "build_virtual_users: 16" in yaml_str
        assert "load_virtual_users: 64" in yaml_str
        assert "rampup: 15" in yaml_str
        assert "duration: 30" in yaml_str
        assert 'memory: "8Gi"' in yaml_str

    def test_default_values_match_original(self) -> None:
        """Calling with defaults should produce the same output as the old hardcoded template."""
        yaml_str = _build_config_yaml(
            name="test",
            db_type_str="mssql",
            benchmark_str="tprocc",
            hosts=[{"name": "db-01", "host": "10.0.0.1"}],
            username="sa",
            password="pass",
            oracle_config=None,
        )
        # Verify the default values appear
        assert "build_virtual_users: 4" in yaml_str
        assert "load_virtual_users: 4" in yaml_str
        assert "rampup: 5" in yaml_str
        assert "duration: 10" in yaml_str
        assert 'memory: "4Gi"' in yaml_str
        assert 'cpu: "4"' in yaml_str
