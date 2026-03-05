"""HammerDB-Scale CLI — Typer application with all commands."""

from __future__ import annotations

import platform
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import typer
import yaml

from hammerdb_scale.config.loader import discover_config_file, load_config
from hammerdb_scale.config.schema import HammerDBScaleConfig
from hammerdb_scale.constants import (
    DEFAULT_IMAGES,
    DEFAULT_NAMESPACE,
    VERSION,
    ConfigError,
    get_chart_path,
)
from hammerdb_scale.output import console, print_error, print_success, print_warning
from rich.table import Table

app = typer.Typer(
    name="hammerdb-scale",
    help="CLI for orchestrating parallel HammerDB database benchmarks at scale on Kubernetes",
    no_args_is_help=True,
)

# Module-level state for global options
_state: dict = {}


@app.callback()
def main(
    file: Optional[Path] = typer.Option(None, "-f", "--file", help="Config file path."),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose output."),
) -> None:
    """HammerDB-Scale: orchestrate parallel database benchmarks on Kubernetes."""
    _state["file"] = file
    _state["verbose"] = verbose


@app.command()
def version() -> None:
    """Show CLI and tooling versions."""
    console.print(f"  hammerdb-scale  {VERSION}")
    console.print(f"  Python          {platform.python_version()}")

    # helm
    helm_path = shutil.which("helm")
    if helm_path:
        try:
            result = subprocess.run(
                [helm_path, "version", "--short"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            console.print(f"  helm            {result.stdout.strip()}")
        except Exception:
            console.print(
                "  helm            [yellow]found but version check failed[/yellow]"
            )
    else:
        console.print(
            "  helm            [red]not found[/red] (install from https://helm.sh)"
        )

    # kubectl
    kubectl_path = shutil.which("kubectl")
    if kubectl_path:
        try:
            result = subprocess.run(
                [kubectl_path, "version", "--client", "--short"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            version_str = result.stdout.strip()
            ctx_result = subprocess.run(
                [kubectl_path, "config", "current-context"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            ctx = ctx_result.stdout.strip() if ctx_result.returncode == 0 else "unknown"
            console.print(f"  kubectl         {version_str} (context: {ctx})")
        except Exception:
            console.print(
                "  kubectl         [yellow]found but version check failed[/yellow]"
            )
    else:
        console.print(
            "  kubectl         [red]not found[/red] "
            "(install from https://kubernetes.io/docs/tasks/tools/)"
        )


def _build_config_yaml(
    *,
    name: str,
    db_type_str: str,
    benchmark_str: str,
    hosts: list[dict],
    username: str,
    password: str,
    oracle_config: dict | None,
    warehouses: int = 100,
    namespace: str = "hammerdb",
    storage_metrics: dict | None = None,
    build_virtual_users: int = 4,
    load_virtual_users: int = 4,
    rampup: int = 5,
    duration: int = 10,
    scale_factor: int = 1,
    build_threads: int = 4,
    tproch_load_virtual_users: int = 1,
    total_querysets: int = 1,
    req_memory: str = "4Gi",
    req_cpu: str = "4",
    lim_memory: str = "8Gi",
    lim_cpu: str = "8",
) -> str:
    """Build the commented YAML config template string."""
    image_repo = DEFAULT_IMAGES.get(db_type_str, "sillidata/hammerdb-scale")

    # Host entries
    hosts_yaml = "\n".join(
        f'    - name: {h["name"]}\n      host: "{h["host"]}"' for h in hosts
    )

    # Database-specific defaults block
    if db_type_str == "oracle":
        assert oracle_config is not None
        db_defaults = f"""    oracle:
      service: "{oracle_config["service"]}"
      port: 1521
      tablespace: "TPCC"                   # bigfile tablespace for benchmark data
      temp_tablespace: "TEMP"              # temp tablespace (usually default)
      tprocc:
        user: "TPCC"                       # TPC-C schema owner (created during build)
        password: "{oracle_config["tprocc"]["password"]}"
      tproch:
        user: "tpch"                       # TPC-H schema owner (created during build)
        password: "{oracle_config["tproch"]["password"]}"
        degree_of_parallel: 8              # Oracle parallel query degree"""
    else:
        db_defaults = """    mssql:
      port: 1433
      connection:
        tcp: true
        authentication: sql
        odbc_driver: "ODBC Driver 18 for SQL Server"
        encrypt_connection: true             # TLS encryption (recommended)
        trust_server_cert: true              # accept self-signed certs
      tprocc:
        database_name: tpcc                # database created during build phase
        use_bcp: false                     # bulk copy for faster data loading
      tproch:
        database_name: tpch                # database created during build phase
        maxdop: 2                          # max degree of parallelism for queries
        use_clustered_columnstore: false   # columnstore indexes (analytics optimization)"""

    # TPC-C section (always included, commented out if not selected)
    tprocc_comment = "" if benchmark_str == "tprocc" else "# "
    tprocc_section = f"""{tprocc_comment}  tprocc:
{tprocc_comment}    warehouses: {warehouses}                  # data size: 100 = ~10GB, 1000 = ~100GB, 10000 = ~1TB per target
{tprocc_comment}    build_virtual_users: {build_virtual_users}           # parallel threads for schema creation
{tprocc_comment}    load_virtual_users: {load_virtual_users}            # concurrent users during benchmark (tune to match CPU cores)
{tprocc_comment}    driver: timed                    # "timed" = run for fixed duration, "test" = single iteration
{tprocc_comment}    rampup: {rampup}                        # warm-up period before measuring (minutes)
{tprocc_comment}    duration: {duration}                     # measurement window (minutes), 5-60 typical
{tprocc_comment}    total_iterations: 10000000       # max iterations (effectively unlimited with timed driver)
{tprocc_comment}    all_warehouses: true             # distribute load across all warehouses
{tprocc_comment}    checkpoint: true                 # issue checkpoint before benchmark
{tprocc_comment}    time_profile: false              # detailed per-transaction timing (adds overhead)"""

    # TPC-H section (always included, commented out if not selected)
    tproch_comment = "" if benchmark_str == "tproch" else "# "
    tproch_section = f"""{tproch_comment}  tproch:
{tproch_comment}    scale_factor: {scale_factor}                  # data size multiplier: 1 = ~1GB, 10 = ~10GB, 100 = ~100GB
{tproch_comment}    build_threads: {build_threads}                 # parallel threads for data generation
{tproch_comment}    build_virtual_users: 1           # HammerDB orchestrator (keep at 1)
{tproch_comment}    load_virtual_users: {tproch_load_virtual_users}            # query concurrency: 1 = Power run, >1 = Throughput run
{tproch_comment}    total_querysets: {total_querysets}               # number of full 22-query runs"""

    # Storage metrics section
    if storage_metrics:
        pure = storage_metrics["pure"]
        storage_section = f"""
# ============================================================================
# PURE STORAGE METRICS (optional)
# Collects IOPS, latency, and bandwidth from the FlashArray during benchmarks.
# Metrics appear in the HTML scorecard alongside database results.
# ============================================================================
storage_metrics:
  enabled: true
  provider: pure
  pure:
    host: "{pure["host"]}"               # FlashArray management IP or hostname
    api_token: "{pure["api_token"]}"     # REST API token (Settings > Users > API Tokens)
    volume: ""                           # leave empty for array-level metrics
    poll_interval: 5                     # collection interval in seconds
    verify_ssl: false"""
    else:
        storage_section = """
# ============================================================================
# PURE STORAGE METRICS (optional)
# Uncomment to collect IOPS, latency, and bandwidth from a FlashArray
# during benchmarks. Metrics appear in the HTML scorecard.
# ============================================================================
storage_metrics:
  enabled: false
  # pure:
  #   host: ""                           # FlashArray management IP or hostname
  #   api_token: ""                      # REST API token (Settings > Users > API Tokens)
  #   volume: ""                         # leave empty for array-level metrics
  #   poll_interval: 5                   # collection interval in seconds
  #   verify_ssl: false"""

    # Assemble full config
    return f"""# ============================================================================
# HammerDB-Scale Configuration
# ============================================================================
# Docs:  https://github.com/PureStorage-OpenConnect/hammerdb-scale/blob/main/docs/CONFIGURATION.md
# Guide: https://github.com/PureStorage-OpenConnect/hammerdb-scale/blob/main/docs/USAGE-GUIDE.md
#
# Quick start:
#   1. Review and edit the values below (especially targets, warehouses, and virtual users)
#   2. hammerdb-scale validate          # check config, tools, and database connectivity
#   3. hammerdb-scale run --build --wait # build schemas and run the benchmark
#   4. hammerdb-scale results            # aggregate results
#   5. hammerdb-scale report --open      # generate HTML scorecard
# ============================================================================

name: {name}
description: "{db_type_str.upper()} {benchmark_str.upper()} benchmark — {len(hosts)} target{"s" if len(hosts) != 1 else ""}"
default_benchmark: {benchmark_str}

# ============================================================================
# DATABASE TARGETS
# ============================================================================
# "defaults" are inherited by all hosts — override any field per-host if needed.
# Add or remove hosts to match your environment.
targets:
  defaults:
    type: {db_type_str}
    username: {username}
    password: "{password}"
    image:
      repository: {image_repo}
      tag: latest
      pull_policy: Always              # Always | IfNotPresent | Never
{db_defaults}

  hosts:
{hosts_yaml}

# ============================================================================
# BENCHMARK PARAMETERS
# ============================================================================
# Tune these to control data size, concurrency, and test duration.
# Uncomment the other benchmark section to switch between TPC-C and TPC-H.
hammerdb:
{tprocc_section}
{tproch_section}

# ============================================================================
# KUBERNETES RESOURCES
# ============================================================================
# Resource requests/limits for each HammerDB Job pod.
# Each target gets one pod — scale these based on virtual user count.
resources:
  requests:
    memory: "{req_memory}"
    cpu: "{req_cpu}"
  limits:
    memory: "{lim_memory}"
    cpu: "{lim_cpu}"

# ============================================================================
# KUBERNETES SETTINGS
# ============================================================================
kubernetes:
  namespace: {namespace}                 # namespace for benchmark jobs (must exist)
  job_ttl: 86400                         # auto-cleanup completed jobs after N seconds (24h)
{storage_section}
"""


@app.command()
def init(
    output: Path = typer.Option(
        Path("./hammerdb-scale.yaml"), "-o", "--output", help="Output file path."
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite if file exists."),
    interactive: bool = typer.Option(
        False, "-i", "--interactive", help="Launch guided configuration wizard."
    ),
) -> None:
    """Generate a starter config file through interactive prompts."""
    if output.exists() and not force:
        overwrite = typer.confirm(f"File {output} exists. Overwrite?")
        if not overwrite:
            raise typer.Abort()

    if interactive:
        from hammerdb_scale.wizard import run_wizard

        values = run_wizard()
        if values is None:
            raise typer.Abort()

        config_yaml = _build_config_yaml(**values)
    else:
        # Deployment name
        name = typer.prompt("Deployment name")

        # Database type
        db_type_str = typer.prompt("Database type (oracle/mssql)")
        while db_type_str not in ("oracle", "mssql"):
            console.print("[red]Must be 'oracle' or 'mssql'[/red]")
            db_type_str = typer.prompt("Database type (oracle/mssql)")

        # Benchmark
        benchmark_str = typer.prompt("Benchmark (tprocc/tproch)")
        while benchmark_str not in ("tprocc", "tproch"):
            console.print("[red]Must be 'tprocc' or 'tproch'[/red]")
            benchmark_str = typer.prompt("Benchmark (tprocc/tproch)")

        # Targets
        num_targets = typer.prompt("Number of database targets", type=int)
        hosts: list[dict] = []
        for i in range(num_targets):
            console.print(f"\nTarget {i + 1}:")
            t_name = typer.prompt("  Name (short identifier)")
            t_host = typer.prompt("  Hostname or IP")
            hosts.append({"name": t_name, "host": t_host})

        # Credentials
        default_user = "system" if db_type_str == "oracle" else "sa"
        username = typer.prompt("\nDatabase username", default=default_user)
        password = typer.prompt("Database password", hide_input=True)

        # Oracle-specific prompts
        oracle_config = None
        if db_type_str == "oracle":
            service = typer.prompt("\nOracle service name", default="ORCLPDB")
            oracle_schema_password = typer.prompt(
                "TPC-C schema password",
                default=password,
                hide_input=True,
            )
            oracle_config = {
                "service": service,
                "port": 1521,
                "tablespace": "TPCC",
                "temp_tablespace": "TEMP",
                "tprocc": {"user": "TPCC", "password": oracle_schema_password},
                "tproch": {"user": "tpch", "password": oracle_schema_password},
            }

        # Warehouses (for TPC-C)
        warehouses = 100
        if benchmark_str == "tprocc":
            warehouses = typer.prompt("\nTPC-C warehouses", default=100, type=int)

        # Namespace
        namespace = typer.prompt("\nKubernetes namespace", default="hammerdb")

        # Pure Storage
        storage_metrics = None
        enable_pure = typer.confirm("\nEnable Pure Storage metrics?", default=False)
        if enable_pure:
            pure_host = typer.prompt("  FlashArray host/IP")
            pure_token = typer.prompt("  API token", hide_input=True)
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

        config_yaml = _build_config_yaml(
            name=name,
            db_type_str=db_type_str,
            benchmark_str=benchmark_str,
            hosts=hosts,
            username=username,
            password=password,
            oracle_config=oracle_config,
            warehouses=warehouses,
            namespace=namespace,
            storage_metrics=storage_metrics,
        )

    # Write YAML
    with open(output, "w") as f:
        f.write(config_yaml)

    console.print(f"\n[green]Config written to {output}[/green]")
    console.print("\nNext steps:")
    console.print("  hammerdb-scale validate        Check config and prerequisites")
    console.print("  hammerdb-scale run --build     Build schemas and run benchmark")
    console.print(
        "  hammerdb-scale run             Run benchmark (if schemas already built)"
    )


@app.command()
def validate(
    file: Optional[Path] = typer.Option(None, "-f", "--file", help="Config file."),
    skip_connectivity: bool = typer.Option(
        False, "--skip-connectivity", help="Skip network connectivity checks."
    ),
) -> None:
    """Multi-layer validation with clear, actionable output."""
    config_path = file or _state.get("file")
    errors_found = False

    console.print("Validating configuration...")

    # Layer 1: YAML syntax
    try:
        resolved_path = discover_config_file(config_path)
        with open(resolved_path) as f:
            yaml.safe_load(f)
        print_success("YAML syntax valid")
    except ConfigError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except yaml.YAMLError as e:
        print_error(f"YAML syntax error: {e}")
        raise typer.Exit(1)

    # Layer 2: Schema validation
    try:
        config = load_config(resolved_path)
        target_count = len(config.targets.hosts)
        db_type = config.targets.defaults.type or config.targets.hosts[0].type
        print_success("Schema validates (all required fields present)")
        print_success(
            f"{target_count} targets configured "
            f"(type: {db_type.value if db_type else 'mixed'})"
        )

        # Benchmark settings summary
        if config.default_benchmark:
            bm = config.default_benchmark.value
            if bm == "tprocc":
                print_success(
                    f"Benchmark settings valid (tprocc, "
                    f"{config.hammerdb.tprocc.warehouses} warehouses)"
                )
            else:
                print_success(
                    f"Benchmark settings valid (tproch, "
                    f"scale factor {config.hammerdb.tproch.scale_factor})"
                )
            print_success(f"Default benchmark: {bm}")
        else:
            print_warning(
                "No default_benchmark set. --benchmark flag will be required."
            )
    except ConfigError as e:
        print_error(str(e))
        raise typer.Exit(1)

    # Layer 3: Image/type check
    warnings = config.get_image_warnings()
    for w in warnings:
        print_warning(w)

    # Layer 4: Prerequisites
    console.print("\nChecking prerequisites...")
    helm_path = shutil.which("helm")
    if helm_path:
        try:
            result = subprocess.run(
                [helm_path, "version", "--short"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            print_success(f"helm found ({result.stdout.strip()})")
        except Exception:
            print_warning("helm found but version check failed")
    else:
        print_error("helm not found (install from https://helm.sh)")
        errors_found = True

    kubectl_path = shutil.which("kubectl")
    if kubectl_path:
        try:
            result = subprocess.run(
                [kubectl_path, "version", "--client", "--short"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            ctx_result = subprocess.run(
                [kubectl_path, "config", "current-context"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            ctx = ctx_result.stdout.strip() if ctx_result.returncode == 0 else "unknown"
            print_success(f"kubectl found ({result.stdout.strip()})")
            print_success(f"Current context: {ctx}")
        except Exception:
            print_warning("kubectl found but version check failed")
    else:
        print_error(
            "kubectl not found (install from https://kubernetes.io/docs/tasks/tools/)"
        )
        errors_found = True

    # Layer 5: K8s access
    if kubectl_path:
        console.print("\nChecking Kubernetes access...")
        ns = config.kubernetes.namespace
        try:
            result = subprocess.run(
                [kubectl_path, "get", "ns", ns],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                print_success(f"Namespace '{ns}' exists")
            else:
                print_warning(
                    f"Namespace '{ns}' does not exist. "
                    f"It will be created during deployment."
                )
        except Exception:
            print_warning("Could not check namespace")

        try:
            result = subprocess.run(
                [kubectl_path, "auth", "can-i", "create", "jobs", "-n", ns],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and "yes" in result.stdout.lower():
                print_success("Can create Jobs in namespace")
            else:
                print_warning("Cannot verify Job creation permissions")
        except Exception:
            print_warning("Could not check permissions")

        try:
            result = subprocess.run(
                [kubectl_path, "auth", "can-i", "create", "configmaps", "-n", ns],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and "yes" in result.stdout.lower():
                print_success("Can create ConfigMaps in namespace")
            else:
                print_warning("Cannot verify ConfigMap creation permissions")
        except Exception:
            print_warning("Could not check permissions")

    # Layer 6: Database connectivity
    if not skip_connectivity:
        console.print("\nChecking database connectivity...")
        conn_failures = _check_connectivity(config)
        if conn_failures:
            errors_found = True
    else:
        console.print("\n[dim]Skipping connectivity checks (--skip-connectivity)[/dim]")

    # Summary
    warning_count = len(warnings)
    if errors_found:
        console.print(
            f"\nValidation complete: {warning_count} warning(s), errors found."
        )
        raise typer.Exit(1)
    else:
        console.print(f"\nValidation complete: {warning_count} warning(s), 0 errors.")


def _check_connectivity(config: HammerDBScaleConfig) -> int:
    """Check database connectivity for all targets in parallel. Returns failure count."""
    from hammerdb_scale.config.defaults import expand_targets

    targets = expand_targets(config)
    defaults = config.targets.defaults

    def check_target(target: dict) -> tuple[str, bool, str]:
        """Returns (target_name, success, message)."""
        name = target["name"]
        host = target["host"]
        db_type = target["type"]
        username = target["username"]
        password = target["password"]

        if db_type == "oracle":
            oracle_cfg = target.get("oracle", {})
            port = oracle_cfg.get("port", 1521)
            service = oracle_cfg.get("service", "ORCLPDB")
            try:
                import oracledb

                conn = oracledb.connect(
                    user=username,
                    password=password,
                    dsn=f"{host}:{port}/{service}",
                )
                conn.close()
                return (
                    name,
                    True,
                    f"{host}:{port}  Connected (service: {service}, user: {username})",
                )
            except Exception as e:
                err_str = str(e)
                suggestion = ""
                if "ORA-12514" in err_str:
                    suggestion = (
                        f"\n      Check that service name '{service}' "
                        f"exists on this host."
                    )
                elif "ORA-01017" in err_str:
                    suggestion = f"\n      Check username '{username}' and password."
                elif "ORA-12541" in err_str:
                    suggestion = f"\n      No listener running on {host}:{port}."
                return (name, False, f"{host}:{port}  {err_str}{suggestion}")

        elif db_type == "mssql":
            port = 1433
            if defaults.mssql:
                port = defaults.mssql.port
            try:
                import pymssql

                conn = pymssql.connect(
                    server=host,
                    port=port,
                    user=username,
                    password=password,
                    login_timeout=10,
                )
                conn.close()
                return (
                    name,
                    True,
                    f"{host}:{port}  Connected (user: {username})",
                )
            except Exception as e:
                return (name, False, f"{host}:{port}  {e}")

        return (name, False, f"Unknown database type: {db_type}")

    failures = 0
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(check_target, t): t for t in targets}
        for future in as_completed(futures):
            name, success, msg = future.result()
            if success:
                print_success(f"{name}  {msg}")
            else:
                print_error(f"{name}  {msg}")
                failures += 1

    # Pure Storage check
    if config.storage_metrics.enabled:
        pure = config.storage_metrics.pure
        if pure.host:
            try:
                import socket

                sock = socket.create_connection((pure.host, 443), timeout=5)
                sock.close()
                print_success(f"Pure Storage API ({pure.host}) reachable")
            except Exception as e:
                print_error(f"Pure Storage API ({pure.host}) unreachable: {e}")
                failures += 1

    return failures


@app.command()
def build(
    benchmark: Optional[str] = typer.Option(
        None, "--benchmark", help="tprocc or tproch."
    ),
    file: Optional[Path] = typer.Option(None, "-f", "--file", help="Config file."),
    id: Optional[str] = typer.Option(None, "--id", help="Test ID override."),
    namespace: Optional[str] = typer.Option(
        None, "-n", "--namespace", help="Override namespace."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Render Helm templates without deploying."
    ),
    wait: bool = typer.Option(False, "--wait", help="Wait for all jobs to complete."),
    timeout: int = typer.Option(7200, "--timeout", help="Wait timeout in seconds."),
) -> None:
    """Create database schemas. Wraps helm install with phase=build."""
    from hammerdb_scale.helm.deployer import helm_install
    from hammerdb_scale.helm.values import generate_helm_values
    from hammerdb_scale.k8s.jobs import resolve_benchmark
    from hammerdb_scale.k8s.naming import (
        generate_release_name,
        generate_run_hash,
        generate_test_id,
    )

    config_path = file or _state.get("file")
    config = load_config(discover_config_file(config_path))
    ns = namespace or config.kubernetes.namespace

    try:
        bm = resolve_benchmark(benchmark, config, "build")
    except ConfigError as e:
        print_error(str(e))
        raise typer.Exit(1)
    test_id = id or generate_test_id(config.name)
    run_hash = generate_run_hash(config.name, test_id)
    release_name = generate_release_name("build", run_hash)

    target_count = len(config.targets.hosts)
    from hammerdb_scale.output import print_banner

    if bm == "tprocc":
        wh = config.hammerdb.tprocc.warehouses
        print_banner(config.name, bm, target_count, f"{wh} wh")
        console.print(
            f"\nBuilding {bm} schemas ({wh} warehouses, {config.hammerdb.tprocc.build_virtual_users} virtual users, {target_count} targets)\n"
        )
    else:
        print_banner(
            config.name, bm, target_count, f"SF {config.hammerdb.tproch.scale_factor}"
        )

    values = generate_helm_values(config, "build", bm, test_id)
    chart_path = get_chart_path()

    console.print("Deploying jobs...")
    result = helm_install(release_name, chart_path, ns, values, dry_run=dry_run)

    if dry_run:
        console.print(result.stdout)
        return

    # Print deployed jobs
    for i, host in enumerate(config.targets.hosts):
        job_name = f"hdb-build-{i:02d}-{run_hash}"
        print_success(f"{job_name}  ({host.name})")

    console.print(f"\n{target_count} build jobs deployed to namespace '{ns}'.\n")
    console.print(f"Monitor progress:  hammerdb-scale status --id {test_id}")
    console.print(f"View logs:         hammerdb-scale logs --id {test_id}")

    if wait:
        _wait_for_jobs(ns, test_id, "build", timeout)


@app.command()
def run(
    benchmark: Optional[str] = typer.Option(
        None, "--benchmark", help="tprocc or tproch."
    ),
    build_first: bool = typer.Option(
        False, "--build", help="Build schemas before running."
    ),
    file: Optional[Path] = typer.Option(None, "-f", "--file", help="Config file."),
    id: Optional[str] = typer.Option(None, "--id", help="Test ID override."),
    namespace: Optional[str] = typer.Option(
        None, "-n", "--namespace", help="Override namespace."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Render only."),
    wait: bool = typer.Option(False, "--wait", help="Wait for completion."),
    timeout: int = typer.Option(
        3600, "--timeout", help="Wait timeout seconds for run phase."
    ),
) -> None:
    """Execute the benchmark. Wraps helm install with phase=load."""
    from hammerdb_scale.constants import BUILD_TIMEOUT_DEFAULT
    from hammerdb_scale.helm.deployer import helm_install, helm_uninstall
    from hammerdb_scale.helm.values import generate_helm_values
    from hammerdb_scale.k8s.jobs import resolve_benchmark
    from hammerdb_scale.k8s.naming import (
        generate_release_name,
        generate_run_hash,
        generate_test_id,
    )
    from hammerdb_scale.output import print_banner

    config_path = file or _state.get("file")
    config = load_config(discover_config_file(config_path))
    ns = namespace or config.kubernetes.namespace

    try:
        bm = resolve_benchmark(benchmark, config, "run")
    except ConfigError as e:
        print_error(str(e))
        raise typer.Exit(1)
    test_id = id or generate_test_id(config.name)
    run_hash = generate_run_hash(config.name, test_id)
    target_count = len(config.targets.hosts)

    # --build: build schemas first
    if build_first:
        console.print("Building schemas first...\n")
        build_release = generate_release_name("build", run_hash)
        build_values = generate_helm_values(config, "build", bm, test_id)
        chart_path = get_chart_path()

        helm_install(build_release, chart_path, ns, build_values, dry_run=dry_run)
        if dry_run:
            return

        console.print("Build jobs deployed. Waiting for completion...\n")
        success = _wait_for_jobs(ns, test_id, "build", BUILD_TIMEOUT_DEFAULT)

        if not success:
            console.print(
                "\n[red]Build failed. Run phase not started.[/red]\n"
                f"Investigate:  hammerdb-scale logs --id {test_id}\n"
                f"After fixing: hammerdb-scale run --benchmark {bm} --build"
            )
            raise typer.Exit(1)

        console.print("\n[green]All builds completed successfully.[/green]\n")
        # Clean build release before proceeding
        try:
            helm_uninstall(build_release, ns)
        except Exception:
            pass  # Non-fatal

    run_release = generate_release_name("run", run_hash)
    run_values = generate_helm_values(config, "run", bm, test_id)
    chart_path = get_chart_path()

    detail = ""
    if bm == "tprocc":
        vu = config.hammerdb.tprocc.load_virtual_users
        rampup = config.hammerdb.tprocc.rampup
        duration = config.hammerdb.tprocc.duration
        detail = f"{config.hammerdb.tprocc.warehouses} wh"
        print_banner(config.name, bm, target_count, detail)
        console.print(
            f"\nRunning {bm} benchmark ({vu} virtual users, "
            f"{rampup} min rampup + {duration} min test)"
        )
        console.print(f"Expected completion: ~{rampup + duration} minutes\n")
    else:
        detail = f"SF {config.hammerdb.tproch.scale_factor}"
        print_banner(config.name, bm, target_count, detail)

    console.print("Deploying jobs...")
    result = helm_install(run_release, chart_path, ns, run_values, dry_run=dry_run)

    if dry_run:
        console.print(result.stdout)
        return

    for i, host in enumerate(config.targets.hosts):
        job_name = f"hdb-run-{i:02d}-{run_hash}"
        extra = ""
        if i == 0 and config.storage_metrics.enabled:
            extra = "  [Pure Storage collector active]"
        print_success(f"{job_name}  ({host.name}){extra}")

    console.print(f"\n{target_count} benchmark jobs deployed to namespace '{ns}'.\n")
    console.print(
        f"When complete:     hammerdb-scale results --benchmark {bm} --id {test_id}"
    )
    console.print(f"Generate report:   hammerdb-scale report --id {test_id}")

    if wait:
        _wait_for_jobs(ns, test_id, "load", timeout)


@app.command()
def status(
    id: Optional[str] = typer.Option(None, "--id", help="Test ID."),
    namespace: Optional[str] = typer.Option(
        None, "-n", "--namespace", help="Namespace."
    ),
    watch: bool = typer.Option(False, "--watch", help="Refresh every 10 seconds."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Show current state of jobs for a test run."""
    import json as json_mod
    import time

    from hammerdb_scale.k8s.jobs import (
        discover_jobs,
        get_job_duration,
        get_job_status,
        get_job_target_host,
        get_job_target_name,
        resolve_test_id,
    )
    from hammerdb_scale.results.parsers import get_parser

    config_path = _state.get("file")
    deploy_name = None
    try:
        config = load_config(discover_config_file(config_path))
        ns = namespace or config.kubernetes.namespace
        deploy_name = config.name
    except ConfigError:
        ns = namespace or DEFAULT_NAMESPACE

    test_id = resolve_test_id(id, ns, deployment_name=deploy_name)

    while True:
        jobs = discover_jobs(ns, test_id)
        if not jobs:
            console.print(f"No jobs found for test '{test_id}' in namespace '{ns}'.")
            raise typer.Exit(1)

        first_labels = jobs[0].get("metadata", {}).get("labels", {})
        phase = first_labels.get("hammerdb.io/phase", "unknown")
        bm = first_labels.get("hammerdb.io/benchmark", "unknown")

        if json_output:
            data = []
            for job in jobs:
                data.append(
                    {
                        "target": get_job_target_name(job),
                        "host": get_job_target_host(job),
                        "status": get_job_status(job),
                        "duration": get_job_duration(job),
                    }
                )
            console.print(json_mod.dumps(data, indent=2))
            return

        console.print(f"\nTest: {test_id}")
        console.print(f"Phase: {phase} | Benchmark: {bm} | Namespace: {ns}\n")

        table = Table()
        table.add_column("#", style="dim")
        table.add_column("Target")
        table.add_column("Host")
        table.add_column("Status")
        table.add_column("Duration")
        if bm == "tprocc":
            table.add_column("TPM", justify="right")
            table.add_column("NOPM", justify="right")
        elif bm == "tproch":
            table.add_column("QphH", justify="right")

        completed = 0
        failed = 0
        running = 0

        for i, job in enumerate(jobs):
            job_status = get_job_status(job)
            duration = get_job_duration(job)
            dur_str = _format_duration(duration) if duration else "-"
            target_name = get_job_target_name(job)
            target_host = get_job_target_host(job)

            status_style = (
                "green"
                if job_status == "Completed"
                else "red"
                if job_status == "Failed"
                else "yellow"
            )

            tpm_str = "-"
            nopm_str = "-"
            qphh_str = "-"

            if job_status == "Completed":
                completed += 1
                db_type = (
                    job.get("metadata", {})
                    .get("labels", {})
                    .get("hammerdb.io/database-type", "oracle")
                )
                try:
                    parser = get_parser(db_type)
                    from hammerdb_scale.k8s.jobs import get_job_logs

                    log_text = get_job_logs(
                        ns, job.get("metadata", {}).get("name", ""), tail=200
                    )
                    if bm == "tprocc":
                        result = parser.parse_tprocc(log_text)
                        if result:
                            tpm_str = f"{result.tpm:,}"
                            nopm_str = f"{result.nopm:,}"
                    elif bm == "tproch":
                        result = parser.parse_tproch(log_text)
                        if result:
                            qphh_str = f"{result.qphh:,.1f}"
                except Exception:
                    pass
            elif job_status == "Failed":
                failed += 1
            else:
                running += 1

            row = [
                str(i),
                target_name,
                target_host,
                f"[{status_style}]{job_status}[/{status_style}]",
                dur_str,
            ]
            if bm == "tprocc":
                row.extend([tpm_str, nopm_str])
            elif bm == "tproch":
                row.append(qphh_str)
            table.add_row(*row)

        console.print(table)
        console.print(
            f"\nStatus: {completed} completed, {failed} failed, {running} running"
        )

        if not watch:
            break
        time.sleep(10)
        console.clear()


@app.command()
def logs(
    id: Optional[str] = typer.Option(None, "--id", help="Test ID."),
    namespace: Optional[str] = typer.Option(
        None, "-n", "--namespace", help="Namespace."
    ),
    target: Optional[str] = typer.Option(
        None, "--target", help="Specific target name."
    ),
    follow: bool = typer.Option(False, "--follow", help="Stream live."),
    tail: int = typer.Option(100, "--tail", help="Lines from end."),
) -> None:
    """Stream or fetch logs from benchmark jobs."""
    from hammerdb_scale.k8s.jobs import (
        discover_jobs,
        get_job_logs,
        get_job_target_name,
        resolve_test_id,
    )

    config_path = _state.get("file")
    deploy_name = None
    try:
        config = load_config(discover_config_file(config_path))
        ns = namespace or config.kubernetes.namespace
        deploy_name = config.name
    except ConfigError:
        ns = namespace or DEFAULT_NAMESPACE

    test_id = resolve_test_id(id, ns, deployment_name=deploy_name)
    jobs = discover_jobs(ns, test_id)

    if not jobs:
        console.print(f"No jobs found for test '{test_id}'.")
        raise typer.Exit(1)

    if target:
        # Find job for specific target
        matching = [j for j in jobs if get_job_target_name(j) == target]
        if not matching:
            console.print(f"[red]No job found for target '{target}'.[/red]")
            raise typer.Exit(1)
        job = matching[0]
        job_name = job.get("metadata", {}).get("name", "")
        log_text = get_job_logs(ns, job_name, tail=tail, follow=follow)
        console.print(log_text)
    else:
        # Show all logs, prefixed with target name
        colors = ["cyan", "green", "yellow", "magenta", "blue", "red"]
        for i, job in enumerate(jobs):
            target_name = get_job_target_name(job)
            job_name = job.get("metadata", {}).get("name", "")
            color = colors[i % len(colors)]
            log_text = get_job_logs(ns, job_name, tail=tail)
            for line in log_text.splitlines():
                console.print(f"[{color}]{target_name}[/{color}] {line}")


@app.command()
def results(
    benchmark: Optional[str] = typer.Option(
        None, "--benchmark", help="tprocc or tproch."
    ),
    id: Optional[str] = typer.Option(None, "--id", help="Test ID."),
    file: Optional[Path] = typer.Option(None, "-f", "--file", help="Config file."),
    namespace: Optional[str] = typer.Option(
        None, "-n", "--namespace", help="Namespace."
    ),
    output: Optional[Path] = typer.Option(
        None, "-o", "--output", help="Output directory."
    ),
    json_output: bool = typer.Option(False, "--json", help="Print JSON to stdout."),
) -> None:
    """Aggregate results from completed jobs."""
    import json as json_mod

    from hammerdb_scale.k8s.jobs import resolve_benchmark, resolve_test_id
    from hammerdb_scale.results.aggregator import aggregate_results
    from hammerdb_scale.results.storage import load_results, save_results

    config_path = file or _state.get("file")
    config = load_config(discover_config_file(config_path))
    ns = namespace or config.kubernetes.namespace

    bm = resolve_benchmark(benchmark, config, "results")
    test_id = resolve_test_id(id, ns, deployment_name=config.name)

    results_dir = output or Path("./results")

    # Try aggregating from K8s first, fall back to local
    try:
        summary, logs_dict, pure_metrics = aggregate_results(
            config, ns, test_id, bm, results_dir
        )
        # Only save if K8s returned actual target data
        if summary.get("targets"):
            save_results(test_id, summary, logs_dict, pure_metrics, results_dir)
        else:
            # K8s jobs cleaned — try loading previously saved results
            local = load_results(test_id, results_dir)
            if local and local.get("targets"):
                summary = local
            else:
                console.print(f"[red]No results found for test '{test_id}'.[/red]")
                raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception:
        # Fall back to local results
        summary = load_results(test_id, results_dir)
        if not summary:
            console.print("[red]No results found.[/red]")
            raise typer.Exit(1)

    if json_output:
        console.print(json_mod.dumps(summary, indent=2))
        return

    # Display Rich table
    _display_results_table(summary, bm)

    completed = summary.get("aggregate", {}).get("targets_completed", 0)
    failed = summary.get("aggregate", {}).get("targets_failed", 0)
    if failed > 0:
        console.print(
            f"\n[yellow]{completed} of {completed + failed} targets completed. {failed} failed.[/yellow]"
        )

    console.print(f"\nResults saved to ./results/{test_id}/")
    console.print(f"Generate report: hammerdb-scale report --id {test_id}")


@app.command()
def report(
    id: Optional[str] = typer.Option(None, "--id", help="Test ID."),
    output: Optional[Path] = typer.Option(
        None, "-o", "--output", help="Output HTML file."
    ),
    open_browser: bool = typer.Option(False, "--open", help="Open in default browser."),
    file: Optional[Path] = typer.Option(None, "-f", "--file", help="Config file."),
) -> None:
    """Generate a self-contained HTML scorecard."""
    import webbrowser

    from hammerdb_scale.k8s.jobs import resolve_test_id
    from hammerdb_scale.results.storage import (
        load_results,
        load_pure_metrics,
        results_exist,
    )

    config_path = file or _state.get("file")
    config = None
    deploy_name = None
    try:
        config = load_config(discover_config_file(config_path))
        ns = config.kubernetes.namespace
        deploy_name = config.name
    except ConfigError:
        ns = DEFAULT_NAMESPACE

    test_id = resolve_test_id(id, ns, deployment_name=deploy_name)
    results_dir = Path("./results")

    # Auto-run results if not aggregated yet
    if not results_exist(test_id, results_dir):
        if config is None:
            console.print(
                "[red]No results found and no config file to aggregate from.[/red]"
            )
            raise typer.Exit(1)
        console.print("Results not yet aggregated. Running aggregation first...")
        try:
            from hammerdb_scale.results.aggregator import aggregate_results
            from hammerdb_scale.results.storage import save_results

            bm = (
                config.default_benchmark.value if config.default_benchmark else "tprocc"
            )
            summary, logs_dict, pure_metrics = aggregate_results(
                config, ns, test_id, bm, results_dir
            )
            if summary.get("targets"):
                save_results(test_id, summary, logs_dict, pure_metrics, results_dir)
            else:
                console.print(f"[red]No results found for test '{test_id}'.[/red]")
                raise typer.Exit(1)
        except typer.Exit:
            raise
        except Exception as e:
            console.print(f"[red]Could not aggregate results: {e}[/red]")
            raise typer.Exit(1)

    summary = load_results(test_id, results_dir)
    pure_metrics = load_pure_metrics(test_id, results_dir)

    if not summary:
        console.print("[red]No results data found.[/red]")
        raise typer.Exit(1)

    try:
        from hammerdb_scale.reports.generator import generate_scorecard

        html = generate_scorecard(summary, pure_metrics)
    except ImportError:
        console.print(
            "[yellow]Report generator not yet implemented (Phase 3).[/yellow]"
        )
        raise typer.Exit(1)

    output_path = output or (results_dir / test_id / "scorecard.html")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)

    console.print(f"[green]Report generated: {output_path}[/green]")

    if open_browser:
        webbrowser.open(str(output_path.resolve()))


@app.command()
def clean(
    resources: bool = typer.Option(
        False, "--resources", help="Remove K8s Helm releases and jobs."
    ),
    database: bool = typer.Option(
        False, "--database", help="Drop benchmark tables from targets."
    ),
    id: Optional[str] = typer.Option(None, "--id", help="Test ID to clean."),
    everything: bool = typer.Option(
        False, "--everything", help="Clean all hammerdb-scale releases."
    ),
    namespace: Optional[str] = typer.Option(
        None, "-n", "--namespace", help="Namespace."
    ),
    benchmark: Optional[str] = typer.Option(
        None, "--benchmark", help="Required for --database."
    ),
    file: Optional[Path] = typer.Option(None, "-f", "--file", help="Config file."),
    target: Optional[str] = typer.Option(
        None, "--target", help="Clean specific target only."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print SQL without executing."
    ),
    force: bool = typer.Option(False, "--force", help="Skip confirmation prompts."),
) -> None:
    """Clean up test artifacts."""
    if not resources and not database:
        console.print(
            "At least one scope flag is required:\n"
            "  --resources    Remove K8s Helm releases and jobs\n"
            "  --database     Drop benchmark tables from database targets\n\n"
            "Examples:\n"
            "  hammerdb-scale clean --resources --id <test-id>\n"
            "  hammerdb-scale clean --database --benchmark tprocc\n"
            "  hammerdb-scale clean --resources --everything --database --benchmark tprocc"
        )
        raise typer.Exit(1)

    if database and not benchmark:
        console.print(
            "[red]Specify --benchmark to indicate which tables to drop. "
            "This flag is required for database cleanup (no default).[/red]"
        )
        raise typer.Exit(1)

    if benchmark and benchmark not in ("tprocc", "tproch"):
        console.print(
            f"[red]Invalid benchmark '{benchmark}'. Must be 'tprocc' or 'tproch'.[/red]"
        )
        raise typer.Exit(1)

    if resources and not id and not everything:
        console.print(
            "[red]Specify --id or --everything to indicate which releases to remove.[/red]"
        )
        raise typer.Exit(1)

    config_path = file or _state.get("file")

    if resources:
        try:
            config = load_config(discover_config_file(config_path))
            ns = namespace or config.kubernetes.namespace
        except ConfigError:
            ns = namespace or DEFAULT_NAMESPACE

        from hammerdb_scale.clean.resources import clean_resources

        clean_resources(
            namespace=ns,
            test_id=id,
            everything=everything,
            force=force,
        )

    if database:
        config = load_config(discover_config_file(config_path))

        from hammerdb_scale.clean.database import clean_database

        clean_database(
            config=config,
            benchmark=benchmark,
            target_name=target,
            dry_run=dry_run,
            force=force,
        )


def _format_duration(seconds: int | None) -> str:
    """Format seconds as 'Xm Ys'."""
    if seconds is None:
        return "-"
    minutes = seconds // 60
    secs = seconds % 60
    if minutes > 0:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def _wait_for_jobs(namespace: str, test_id: str, phase: str, timeout: int) -> bool:
    """Poll job status until all complete or timeout. Returns True if all succeeded."""
    import time

    from hammerdb_scale.k8s.jobs import (
        discover_jobs,
        get_job_status,
        get_job_target_name,
    )
    from hammerdb_scale.constants import POLL_INTERVAL

    start = time.time()
    while time.time() - start < timeout:
        jobs = discover_jobs(namespace, test_id, phase=phase)
        if not jobs:
            time.sleep(POLL_INTERVAL)
            continue

        statuses = [(get_job_target_name(j), get_job_status(j)) for j in jobs]
        completed = sum(1 for _, s in statuses if s == "Completed")
        failed = sum(1 for _, s in statuses if s == "Failed")
        total = len(statuses)

        # Show progress
        console.print(
            f"  [{completed}/{total}] completed, {failed} failed",
            end="\r",
        )

        if completed + failed >= total:
            console.print()  # New line after progress
            if failed > 0:
                for name, s in statuses:
                    if s == "Failed":
                        print_error(f"{name} Failed")
                    else:
                        print_success(f"{name} {s}")
                return False
            else:
                for name, s in statuses:
                    print_success(f"{name} {s}")
                return True

        time.sleep(POLL_INTERVAL)

    console.print(f"\n[yellow]Timeout ({timeout}s) reached.[/yellow]")
    return False


def _display_results_table(summary: dict, benchmark: str) -> None:
    """Display results as a Rich table."""
    table = Table(title=f"Results: {summary.get('test_id', 'unknown')}")

    table.add_column("#", style="dim")
    table.add_column("Target")
    table.add_column("Host")
    table.add_column("Status")
    table.add_column("Duration")
    if benchmark == "tprocc":
        table.add_column("TPM", justify="right")
        table.add_column("NOPM", justify="right")
    elif benchmark == "tproch":
        table.add_column("QphH", justify="right")

    for t in summary.get("targets", []):
        status = t.get("status", "unknown")
        status_style = "green" if status == "completed" else "red"
        dur = _format_duration(t.get("duration_seconds"))

        row = [
            str(t.get("index", "")),
            t.get("name", ""),
            t.get("host", ""),
            f"[{status_style}]{status}[/{status_style}]",
            dur,
        ]

        if benchmark == "tprocc":
            tprocc = t.get("tprocc", {})
            row.append(f"{tprocc.get('tpm', 0):,}" if tprocc else "-")
            row.append(f"{tprocc.get('nopm', 0):,}" if tprocc else "-")
        elif benchmark == "tproch":
            tproch = t.get("tproch", {})
            row.append(f"{tproch.get('qphh', 0):,.1f}" if tproch else "-")

        table.add_row(*row)

    console.print(table)

    # Aggregate summary
    agg = summary.get("aggregate", {})
    if benchmark == "tprocc":
        console.print(f"\nTotal TPM: {agg.get('total_tpm', 0):,}")
        console.print(f"Total NOPM: {agg.get('total_nopm', 0):,}")
    elif benchmark == "tproch":
        console.print(f"\nAvg QphH: {agg.get('avg_qphh', 0):,.1f}")
