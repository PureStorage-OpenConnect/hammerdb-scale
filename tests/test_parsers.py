"""Tests for results/parsers.py — Oracle/MSSQL TPC-C/TPC-H parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from hammerdb_scale.results.parsers import (
    MssqlParser,
    OracleParser,
    TproccResult,
    TprochResult,
    get_parser,
)

FIXTURES = Path(__file__).parent / "fixtures"




def _load(filename: str) -> str:
    return (FIXTURES / filename).read_text()




class TestOracleTprocc:
    parser = OracleParser()

    def test_parses_tpm_and_nopm(self):
        log = _load("oracle_tprocc_log.txt")
        result = self.parser.parse_tprocc(log)
        assert result is not None
        assert isinstance(result, TproccResult)
        assert result.tpm > 0
        assert result.nopm > 0

    def test_takes_last_match(self):
        """When log has multiple TPM lines, use the last one (v1 tail -1 behavior)."""
        log = _load("oracle_tprocc_log.txt")
        result = self.parser.parse_tprocc(log)
        assert result is not None
        # The fixture has two lines; last is 287654 TPM / 125890 NOPM
        assert result.tpm == 287654
        assert result.nopm == 125890

    def test_returns_none_on_empty(self):
        assert self.parser.parse_tprocc("") is None

    def test_returns_none_on_no_match(self):
        assert self.parser.parse_tprocc("no results here\njust logs\n") is None

    def test_inline_log(self):
        """Parse from an inline log snippet."""
        log = "TEST RESULT : System achieved 50000 Oracle NOPM from 120000 Oracle TPM"
        result = self.parser.parse_tprocc(log)
        assert result is not None
        assert result.tpm == 120000
        assert result.nopm == 50000

    def test_without_oracle_prefix(self):
        """Parser handles lines without 'Oracle' prefix."""
        log = "42000 TPM\n18000 NOPM"
        result = self.parser.parse_tprocc(log)
        assert result is not None
        assert result.tpm == 42000
        assert result.nopm == 18000




class TestOracleTproch:
    parser = OracleParser()

    def test_parses_qphh(self):
        log = _load("oracle_tproch_log.txt")
        result = self.parser.parse_tproch(log)
        assert result is not None
        assert isinstance(result, TprochResult)
        assert result.qphh == pytest.approx(1523.45)

    def test_parses_queries(self):
        log = _load("oracle_tproch_log.txt")
        result = self.parser.parse_tproch(log)
        assert result is not None
        assert len(result.queries) == 22
        assert result.queries[0].query_number == 1
        assert result.queries[0].time_seconds == pytest.approx(12.5)
        assert result.queries[-1].query_number == 22

    def test_returns_none_on_empty(self):
        assert self.parser.parse_tproch("") is None

    def test_returns_none_on_no_qphh(self):
        log = "Query 1: 10.0 seconds\nQuery 2: 5.0 seconds"
        assert self.parser.parse_tproch(log) is None

    def test_deduplicates_queries(self):
        """HammerDB sometimes outputs query times twice; last occurrence wins."""
        log = (
            "Query 1: 10.0 seconds\n"
            "Query 2: 5.0 seconds\n"
            "Query 1: 12.0 seconds\n"
            "QphH@1: 100.0\n"
        )
        result = self.parser.parse_tproch(log)
        assert result is not None
        assert len(result.queries) == 2
        # Last occurrence of Query 1 should be 12.0
        q1 = [q for q in result.queries if q.query_number == 1][0]
        assert q1.time_seconds == pytest.approx(12.0)




class TestMssqlTprocc:
    parser = MssqlParser()

    def test_parses_system_achieved_pattern(self):
        log = _load("mssql_tprocc_log.txt")
        result = self.parser.parse_tprocc(log)
        assert result is not None
        assert result.tpm == 215432
        assert result.nopm == 98765

    def test_returns_none_on_empty(self):
        assert self.parser.parse_tprocc("") is None

    def test_fallback_to_generic_pattern(self):
        """When 'System achieved' isn't present, fall back to generic TPM/NOPM."""
        log = "55000 SQL Server TPM\n22000 SQL Server NOPM"
        result = self.parser.parse_tprocc(log)
        assert result is not None
        assert result.tpm == 55000
        assert result.nopm == 22000

    def test_without_sqlserver_prefix(self):
        log = "33000 TPM\n14000 NOPM"
        result = self.parser.parse_tprocc(log)
        assert result is not None
        assert result.tpm == 33000
        assert result.nopm == 14000




class TestMssqlTproch:
    parser = MssqlParser()

    def test_parses_qphh(self):
        log = _load("mssql_tproch_log.txt")
        result = self.parser.parse_tproch(log)
        assert result is not None
        assert result.qphh == pytest.approx(1876.32)

    def test_parses_queries(self):
        log = _load("mssql_tproch_log.txt")
        result = self.parser.parse_tproch(log)
        assert result is not None
        assert len(result.queries) == 22

    def test_returns_none_on_empty(self):
        assert self.parser.parse_tproch("") is None




class TestErrorDetection:
    def test_oracle_ora_error(self):
        parser = OracleParser()
        log = "ORA-12154: TNS:could not resolve the connect identifier"
        err = parser.detect_error(log)
        assert err is not None
        assert "ORA-12154" in err

    def test_oracle_no_error(self):
        parser = OracleParser()
        assert parser.detect_error("all good\nno errors") is None

    def test_mssql_msg_error(self):
        parser = MssqlParser()
        log = "Msg 18456, Level 14: Login failed for user 'sa'."
        err = parser.detect_error(log)
        assert err is not None
        assert "Msg 18456" in err

    def test_mssql_no_error(self):
        parser = MssqlParser()
        assert parser.detect_error("all good\nno errors") is None

    def test_generic_error_detected(self):
        """Both parsers detect generic 'Error' or 'FATAL' in log."""
        for parser_cls in (OracleParser, MssqlParser):
            parser = parser_cls()
            err = parser.detect_error("FATAL: something went wrong")
            assert err is not None
            assert "FATAL" in err

    def test_no_false_positive_on_clean_log(self):
        for parser_cls in (OracleParser, MssqlParser):
            parser = parser_cls()
            assert parser.detect_error("Vuser 1:FINISHED SUCCESS\n") is None




class TestGetParser:
    def test_oracle_returns_oracle_parser(self):
        assert isinstance(get_parser("oracle"), OracleParser)

    def test_mssql_returns_mssql_parser(self):
        assert isinstance(get_parser("mssql"), MssqlParser)

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="No parser"):
            get_parser("postgres")
