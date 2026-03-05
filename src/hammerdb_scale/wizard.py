"""Interactive configuration wizard for hammerdb-scale init --interactive."""

from __future__ import annotations

from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from hammerdb_scale.constants import VERSION
from hammerdb_scale.output import console


def _step_header(step: int, total: int, title: str, subtitle: str) -> None:
    """Print a styled step header panel."""
    console.print()
    console.print(
        Panel(
            f"[dim]{subtitle}[/dim]",
            title=f"[bold]Step {step} of {total} — {title}[/bold]",
            border_style="cyan",
            padding=(0, 2),
        )
    )


def _prompt_required(prompt_text: str, **kwargs: object) -> str:
    """Prompt for a non-empty string, re-asking if blank."""
    while True:
        value = Prompt.ask(prompt_text, **kwargs)
        if value and value.strip():
            return value.strip()
        console.print("[red]This field is required.[/red]")


def _select_option(prompt_text: str, options: list[tuple[str, str]]) -> str:
    """Display a numbered menu and return the selected value.

    Args:
        prompt_text: The prompt to show after the menu.
        options: List of (value, display_label) tuples.

    Returns:
        The value string of the selected option.
    """
    for i, (_, label) in enumerate(options, 1):
        console.print(f"  [bold]{i}.[/bold] {label}")
    console.print()
    choices = [str(i) for i in range(1, len(options) + 1)]
    choice = Prompt.ask(prompt_text, choices=choices, show_choices=True)
    return options[int(choice) - 1][0]


def _build_summary_table(values: dict) -> Table:
    """Build a Rich Table summarising the collected wizard values."""
    table = Table(show_header=True, header_style="bold", expand=True)
    table.add_column("Setting", style="cyan", min_width=22)
    table.add_column("Value")

    db_label = "Oracle" if values["db_type_str"] == "oracle" else "SQL Server"
    bench_label = (
        "TPC-C (OLTP)" if values["benchmark_str"] == "tprocc" else "TPC-H (OLAP)"
    )

    table.add_row("Deployment name", values["name"])
    table.add_row("Database type", db_label)
    table.add_row("Benchmark", bench_label)
    table.add_row("Targets", str(len(values["hosts"])))
    for h in values["hosts"]:
        table.add_row(f"  {h['name']}", h["host"], style="dim")
    table.add_row("Username", values["username"])
    table.add_row("Password", "********")

    if values["db_type_str"] == "oracle" and values.get("oracle_config"):
        table.add_row("Oracle service", values["oracle_config"]["service"])
        table.add_row("Schema password", "********")

    if values["benchmark_str"] == "tprocc":
        table.add_row("Warehouses", str(values.get("warehouses", 100)))
    else:
        table.add_row("Scale factor", str(values.get("scale_factor", 1)))

    table.add_row("Namespace", values.get("namespace", "hammerdb"))

    storage = values.get("storage_metrics")
    if storage and storage.get("enabled"):
        table.add_row("Pure Storage", f"Enabled ({storage['pure']['host']})")
    else:
        table.add_row("Pure Storage", "Disabled")

    # Show advanced values if they differ from defaults
    adv_fields = [
        ("build_virtual_users", "Build VUs", 4),
        ("load_virtual_users", "Load VUs", 4),
        ("rampup", "Rampup (min)", 5),
        ("duration", "Duration (min)", 10),
        ("req_memory", "Pod request memory", "4Gi"),
        ("req_cpu", "Pod request CPU", "4"),
        ("lim_memory", "Pod limit memory", "8Gi"),
        ("lim_cpu", "Pod limit CPU", "8"),
    ]
    has_advanced = False
    for key, label, default in adv_fields:
        val = values.get(key)
        if val is not None and val != default:
            if not has_advanced:
                table.add_section()
                has_advanced = True
            table.add_row(label, str(val))

    return table


def run_wizard() -> dict | None:
    """Run the interactive configuration wizard.

    Returns:
        A dict of keyword arguments for ``_build_config_yaml()``,
        or ``None`` if the user cancels.
    """
    total_steps = 6

    try:
        # Welcome banner
        console.print()
        console.print(
            Panel(
                "[bold]HammerDB-Scale Configuration Wizard[/bold]\n\n"
                "This wizard will guide you through creating a benchmark\n"
                "configuration file step by step.\n\n"
                "[dim]Press Ctrl+C at any time to cancel.[/dim]",
                title=f"hammerdb-scale {VERSION}",
                border_style="blue",
                padding=(1, 2),
            )
        )

        # ── Step 1: Deployment ──────────────────────────────────────
        _step_header(1, total_steps, "Deployment", "Give this benchmark a name.")
        console.print()
        name = _prompt_required("Deployment name")

        # ── Step 2: Database & Benchmark ────────────────────────────
        _step_header(
            2,
            total_steps,
            "Database & Benchmark",
            "Select the database engine and TPC benchmark type.",
        )
        console.print()

        db_type_str = _select_option(
            "Database type",
            [("oracle", "Oracle"), ("mssql", "Microsoft SQL Server")],
        )

        console.print()
        benchmark_str = _select_option(
            "Benchmark",
            [
                ("tprocc", "TPC-C  (OLTP transactional)"),
                ("tproch", "TPC-H  (OLAP analytical)"),
            ],
        )

        # ── Step 3: Database Targets ────────────────────────────────
        _step_header(
            3,
            total_steps,
            "Database Targets",
            "Define the database hosts to benchmark against.\n"
            "[dim]Each target gets its own HammerDB Job pod in Kubernetes.[/dim]",
        )

        console.print()
        num_targets = IntPrompt.ask("Number of database targets", default=1)
        while num_targets < 1:
            console.print("[red]Must be at least 1.[/red]")
            num_targets = IntPrompt.ask("Number of database targets", default=1)

        hosts: list[dict] = []
        for i in range(num_targets):
            console.print(f"\n  [bold cyan]Target {i + 1} of {num_targets}[/bold cyan]")
            t_name = Prompt.ask("    Name", default=f"db-{i + 1:02d}")
            t_host = _prompt_required("    Hostname or IP")
            hosts.append({"name": t_name, "host": t_host})

        # ── Step 4: Credentials ─────────────────────────────────────
        _step_header(
            4,
            total_steps,
            "Credentials",
            "Database authentication shared by all targets.\n"
            "[dim]You can override per-host in the YAML later.[/dim]",
        )

        console.print()
        default_user = "system" if db_type_str == "oracle" else "sa"
        username = Prompt.ask("Database username", default=default_user)
        password = _prompt_required("Database password", password=True)

        oracle_config = None
        if db_type_str == "oracle":
            console.print("\n  [dim]Oracle-specific settings:[/dim]")
            service = Prompt.ask("  Oracle service name", default="ORCLPDB")
            console.print(
                "  [dim]Schema password for TPC-C/H user "
                "(Enter to reuse database password).[/dim]"
            )
            schema_password = Prompt.ask("  Schema password", password=True)
            if not schema_password:
                schema_password = password
            oracle_config = {
                "service": service,
                "port": 1521,
                "tablespace": "TPCC",
                "temp_tablespace": "TEMP",
                "tprocc": {"user": "TPCC", "password": schema_password},
                "tproch": {"user": "tpch", "password": schema_password},
            }

        # ── Step 5: Benchmark Parameters ────────────────────────────
        _step_header(
            5,
            total_steps,
            "Benchmark Parameters",
            "Configure the benchmark workload.",
        )

        warehouses = 100
        scale_factor = 1
        if benchmark_str == "tprocc":
            console.print()
            console.print(
                "  [dim]Rule of thumb: 100 warehouses ~ 10 GB per target.[/dim]\n"
            )
            warehouses = IntPrompt.ask("Warehouses per target", default=100)
            while warehouses < 1:
                console.print("[red]Must be at least 1.[/red]")
                warehouses = IntPrompt.ask("Warehouses per target", default=100)
        else:
            console.print()
            console.print(
                "  [dim]Scale factor controls data size: 1 ~ 1 GB, 10 ~ 10 GB.[/dim]\n"
            )
            scale_factor = IntPrompt.ask("Scale factor", default=1)
            while scale_factor < 1:
                console.print("[red]Must be at least 1.[/red]")
                scale_factor = IntPrompt.ask("Scale factor", default=1)

        # ── Step 6: Infrastructure ──────────────────────────────────
        _step_header(
            6,
            total_steps,
            "Infrastructure",
            "Kubernetes and storage settings.",
        )

        console.print()
        namespace = Prompt.ask("Kubernetes namespace", default="hammerdb")

        storage_metrics = None
        console.print()
        enable_pure = Confirm.ask(
            "Enable Pure Storage metrics collection?", default=False
        )
        if enable_pure:
            pure_host = Prompt.ask("  FlashArray host/IP")
            pure_token = Prompt.ask("  API token", password=True)
            storage_metrics = {
                "enabled": True,
                "provider": "pure",
                "pure": {
                    "host": pure_host,
                    "api_token": pure_token,
                    "volume": "",
                    "poll_interval": 5,
                    "verify_ssl": False,
                    "api_version": "2.4",
                },
            }

        # ── Advanced Options (optional) ─────────────────────────────
        values: dict = {
            "name": name,
            "db_type_str": db_type_str,
            "benchmark_str": benchmark_str,
            "hosts": hosts,
            "username": username,
            "password": password,
            "oracle_config": oracle_config,
            "warehouses": warehouses,
            "scale_factor": scale_factor,
            "namespace": namespace,
            "storage_metrics": storage_metrics,
        }

        console.print()
        want_advanced = Confirm.ask(
            "Configure advanced options (VUs, rampup, duration, resources)?",
            default=False,
        )
        if want_advanced:
            console.print(
                Panel(
                    "[dim]Tune concurrency, timing, and pod resources.[/dim]",
                    title="[bold]Advanced Options[/bold]",
                    border_style="yellow",
                    padding=(0, 2),
                )
            )
            console.print()

            if benchmark_str == "tprocc":
                values["build_virtual_users"] = IntPrompt.ask(
                    "Build virtual users", default=4
                )
                values["load_virtual_users"] = IntPrompt.ask(
                    "Load virtual users", default=4
                )
                values["rampup"] = IntPrompt.ask("Rampup (minutes)", default=5)
                values["duration"] = IntPrompt.ask("Duration (minutes)", default=10)
            else:
                values["build_threads"] = IntPrompt.ask("Build threads", default=4)
                values["tproch_load_virtual_users"] = IntPrompt.ask(
                    "Load virtual users (query concurrency)", default=1
                )
                values["total_querysets"] = IntPrompt.ask("Total query sets", default=1)

            console.print("\n  [dim]Kubernetes pod resources:[/dim]\n")
            values["req_memory"] = Prompt.ask("Request memory", default="4Gi")
            values["req_cpu"] = Prompt.ask("Request CPU", default="4")
            values["lim_memory"] = Prompt.ask("Limit memory", default="8Gi")
            values["lim_cpu"] = Prompt.ask("Limit CPU", default="8")

        # ── Summary & Confirmation ──────────────────────────────────
        console.print()
        table = _build_summary_table(values)
        console.print(
            Panel(
                table, title="[bold]Configuration Summary[/bold]", border_style="green"
            )
        )
        console.print()

        if not Confirm.ask("Write configuration?", default=True):
            return None

        return values

    except KeyboardInterrupt:
        console.print("\n[yellow]Wizard cancelled.[/yellow]")
        return None
