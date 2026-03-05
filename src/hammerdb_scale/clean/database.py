"""Database object cleanup (--database scope)."""

from __future__ import annotations

import typer

from hammerdb_scale.config.defaults import expand_targets
from hammerdb_scale.config.schema import HammerDBScaleConfig
from hammerdb_scale.output import console, print_error, print_success


def clean_database(
    config: HammerDBScaleConfig,
    benchmark: str,
    target_name: str | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> None:
    """Drop benchmark tables from database targets."""
    targets = expand_targets(config)

    if target_name:
        targets = [t for t in targets if t["name"] == target_name]
        if not targets:
            console.print(f"[red]Target '{target_name}' not found in config.[/red]")
            raise typer.Exit(1)

    db_type = targets[0]["type"] if targets else "unknown"

    if db_type == "oracle":
        from hammerdb_scale.clean.oracle_drop import (
            get_tprocc_drop_statements,
            get_tproch_drop_statements,
            execute_drops as oracle_execute,
        )

        for t in targets:
            oracle_cfg = t.get("oracle", {})
            tprocc_cfg = oracle_cfg.get("tprocc", {})
            tproch_cfg = oracle_cfg.get("tproch", {})
            schema_user = tprocc_cfg.get("user", "TPCC") if benchmark == "tprocc" else tproch_cfg.get("user", "tpch")

            if benchmark == "tprocc":
                stmts = get_tprocc_drop_statements(schema_user)
            else:
                stmts = get_tproch_drop_statements(schema_user)

            table_count = len(stmts)

            if dry_run:
                console.print(f"\n-- Target: {t['name']} ({t['host']})")
                console.print(f"-- Connect as: {schema_user}")
                for stmt in stmts:
                    console.print(f"{stmt};")
                continue

            if not force:
                console.print(
                    f"\n  {t['name']}  {t['host']}  "
                    f"(user: {schema_user}, {table_count} tables)"
                )

        if dry_run:
            return

        if not force:
            console.print(
                f"\nWill drop {benchmark} tables from {len(targets)} target(s)."
            )
            console.print("This will delete all benchmark data.")
            if not typer.confirm("Proceed?"):
                raise typer.Abort()

        # Execute drops
        for t in targets:
            oracle_cfg = t.get("oracle", {})
            tprocc_cfg = oracle_cfg.get("tprocc", {})
            tproch_cfg = oracle_cfg.get("tproch", {})
            schema_user = tprocc_cfg.get("user", "TPCC") if benchmark == "tprocc" else tproch_cfg.get("user", "tpch")
            schema_pass = tprocc_cfg.get("password", "") if benchmark == "tprocc" else tproch_cfg.get("password", "")

            if benchmark == "tprocc":
                stmts = get_tprocc_drop_statements(schema_user)
            else:
                stmts = get_tproch_drop_statements(schema_user)

            dropped, errors = oracle_execute(
                host=t["host"],
                port=oracle_cfg.get("port", 1521),
                service=oracle_cfg.get("service", "ORCLPDB"),
                username=schema_user,
                password=schema_pass or t["password"],
                statements=stmts,
            )

            if errors:
                print_error(f"{t['name']}  {'; '.join(errors)}")
            else:
                print_success(f"{t['name']}  {dropped} tables dropped")

    elif db_type == "mssql":
        from hammerdb_scale.clean.mssql_drop import (
            get_tprocc_drop_statements,
            get_tproch_drop_statements,
            execute_drops as mssql_execute,
        )

        for t in targets:
            tprocc_db = t.get("tprocc", {}).get("databaseName", "tpcc")
            tproch_db = t.get("tproch", {}).get("databaseName", "tpch")
            db_name = tprocc_db if benchmark == "tprocc" else tproch_db

            if benchmark == "tprocc":
                stmts = get_tprocc_drop_statements(db_name)
            else:
                stmts = get_tproch_drop_statements(db_name)

            if dry_run:
                console.print(f"\n-- Target: {t['name']} ({t['host']})")
                console.print(f"-- Database: {db_name}")
                for stmt in stmts:
                    console.print(f"{stmt};")
                continue

            if not force:
                table_count = len([s for s in stmts if s.startswith("DROP")])
                console.print(
                    f"\n  {t['name']}  {t['host']}  "
                    f"(database: {db_name}, {table_count} tables)"
                )

        if dry_run:
            return

        if not force:
            console.print(
                f"\nWill drop {benchmark} tables from {len(targets)} target(s)."
            )
            console.print("This will delete all benchmark data.")
            if not typer.confirm("Proceed?"):
                raise typer.Abort()

        mssql_port = config.targets.defaults.mssql.port if config.targets.defaults.mssql else 1433

        for t in targets:
            tprocc_db = t.get("tprocc", {}).get("databaseName", "tpcc")
            tproch_db = t.get("tproch", {}).get("databaseName", "tpch")
            db_name = tprocc_db if benchmark == "tprocc" else tproch_db

            if benchmark == "tprocc":
                stmts = get_tprocc_drop_statements(db_name)
            else:
                stmts = get_tproch_drop_statements(db_name)

            dropped, errors = mssql_execute(
                host=t["host"],
                port=mssql_port,
                username=t["username"],
                password=t["password"],
                statements=stmts,
            )

            if errors:
                print_error(f"{t['name']}  {'; '.join(errors)}")
            else:
                print_success(f"{t['name']}  {dropped} tables dropped")
