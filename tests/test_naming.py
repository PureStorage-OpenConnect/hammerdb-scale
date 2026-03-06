"""Tests for k8s/naming.py — hash determinism, job name format, labels."""

from __future__ import annotations

from hammerdb_scale.k8s.naming import (
    generate_annotations,
    generate_job_name,
    generate_labels,
    generate_release_name,
    generate_run_hash,
    generate_test_id,
)


def test_run_hash_is_deterministic():
    h1 = generate_run_hash("myapp", "myapp-20260101-1200")
    h2 = generate_run_hash("myapp", "myapp-20260101-1200")
    assert h1 == h2


def test_run_hash_length():
    h = generate_run_hash("abc", "abc-20260101-0000")
    assert len(h) == 8


def test_run_hash_is_hex():
    h = generate_run_hash("abc", "abc-20260101-0000")
    int(h, 16)  # Raises ValueError if not valid hex


def test_run_hash_different_inputs():
    h1 = generate_run_hash("app-a", "app-a-20260101-1200")
    h2 = generate_run_hash("app-b", "app-b-20260101-1200")
    assert h1 != h2


def test_run_hash_starts_with_letter():
    """Hash must start with a letter to avoid YAML scientific notation parsing.

    e.g. '764303e9' looks like 7.64303e+9 to YAML 1.1 parsers.
    """
    for i in range(100):
        h = generate_run_hash(f"app-{i}", f"app-{i}-20260101-{i:04d}")
        assert h[0].isalpha(), f"Hash {h!r} starts with a digit"


def test_job_name_format():
    name = generate_job_name("run", 3, "a1b2c3d4")
    assert name == "hdb-run-03-a1b2c3d4"


def test_job_name_format_build():
    name = generate_job_name("build", 0, "deadbeef")
    assert name == "hdb-build-00-deadbeef"


def test_job_name_within_k8s_limit():
    """K8s name limit is 63 chars. Our names should be well under."""
    name = generate_job_name("build", 99, "a1b2c3d4")
    assert len(name) <= 63


def test_job_name_index_zero_padded():
    name = generate_job_name("run", 1, "abcdef01")
    assert "-01-" in name


def test_release_name_format():
    name = generate_release_name("run", "a1b2c3d4")
    assert name == "hdb-run-a1b2c3d4"


def test_release_name_build():
    name = generate_release_name("build", "deadbeef")
    assert name == "hdb-build-deadbeef"


def test_test_id_starts_with_name():
    tid = generate_test_id("my-deployment")
    assert tid.startswith("my-deployment-")


def test_test_id_has_timestamp_format():
    tid = generate_test_id("test")
    # Format: test-YYYYMMDD-HHMM
    parts = tid.split("-")
    # At minimum: "test", "YYYYMMDD", "HHMM"
    assert len(parts) >= 3
    assert len(parts[-2]) == 8  # YYYYMMDD
    assert len(parts[-1]) == 4  # HHMM


def test_labels_has_all_keys():
    labels = generate_labels(
        test_id="test-20260101-1200",
        phase="run",
        benchmark="tprocc",
        target_name="ora-01",
        target_index=0,
        database_type="oracle",
        deployment_name="test",
    )
    expected_keys = {
        "hammerdb.io/version",
        "hammerdb.io/test-id",
        "hammerdb.io/phase",
        "hammerdb.io/benchmark",
        "hammerdb.io/target-name",
        "hammerdb.io/target-index",
        "hammerdb.io/database-type",
        "hammerdb.io/deployment-name",
    }
    assert set(labels.keys()) == expected_keys


def test_labels_values():
    labels = generate_labels(
        test_id="mytest-20260228-1000",
        phase="build",
        benchmark="tproch",
        target_name="sql-02",
        target_index=5,
        database_type="mssql",
        deployment_name="mytest",
    )
    assert labels["hammerdb.io/test-id"] == "mytest-20260228-1000"
    assert labels["hammerdb.io/phase"] == "build"
    assert labels["hammerdb.io/benchmark"] == "tproch"
    assert labels["hammerdb.io/target-name"] == "sql-02"
    assert labels["hammerdb.io/target-index"] == "5"
    assert labels["hammerdb.io/database-type"] == "mssql"


def test_labels_target_index_is_string():
    labels = generate_labels(
        test_id="t",
        phase="run",
        benchmark="tprocc",
        target_name="n",
        target_index=3,
        database_type="oracle",
        deployment_name="d",
    )
    assert isinstance(labels["hammerdb.io/target-index"], str)


def test_annotations_keys():
    ann = generate_annotations("db-host.local", 2)
    assert ann["hammerdb.io/target-host"] == "db-host.local"
    assert ann["hammerdb.io/target-index"] == "2"


def test_annotations_index_is_string():
    ann = generate_annotations("host", 0)
    assert isinstance(ann["hammerdb.io/target-index"], str)
