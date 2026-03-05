# Usage Guide

## Installation

```bash
pip install hammerdb-scale
```

This installs the `hammerdb-scale` CLI globally, including the bundled Helm chart. You can run it from any directory.

Requires:
- **Python 3.10+**
- **Helm 3.x** and **kubectl** installed and on your `PATH`
- A Kubernetes cluster accessible via your current `kubectl` context

For isolated installations, use [pipx](https://pipx.pypa.io/):

```bash
pipx install hammerdb-scale
```

For development:

```bash
git clone https://github.com/PureStorage-OpenConnect/hammerdb-scale.git
cd hammerdb-scale
pip install -e ".[dev]"
```

## Quick Start

```bash
# 1. Generate a config file (or use -i for a guided wizard)
hammerdb-scale init

# 2. Validate configuration and connectivity
hammerdb-scale validate

# 3. Build schema and run benchmark in one step
hammerdb-scale run --build --wait

# 4. Collect and view results
hammerdb-scale results

# 5. Generate HTML scorecard
hammerdb-scale report --open
```

## Commands

### `hammerdb-scale version`

Prints CLI, Python, helm, and kubectl versions along with the current Kubernetes context.

### `hammerdb-scale init`

Interactive config generator. Prompts for deployment name, database type, benchmark, targets, and credentials. Writes a v2 YAML config file.

```bash
hammerdb-scale init                    # Default: hammerdb-scale.yaml
hammerdb-scale init -o my-config.yaml  # Custom output path
hammerdb-scale init --force            # Overwrite existing file
hammerdb-scale init -i                 # Guided wizard mode
```

#### Wizard Mode (`--interactive` / `-i`)

The `--interactive` flag launches a step-by-step guided wizard with a polished terminal UI:

```bash
hammerdb-scale init -i
```

The wizard walks through 6 steps:

1. **Deployment** — Name your benchmark
2. **Database & Benchmark** — Select Oracle or SQL Server, TPC-C or TPC-H
3. **Database Targets** — Enter hostnames/IPs (with auto-generated names like `db-01`)
4. **Credentials** — Database username and password (Oracle: service name, schema password)
5. **Benchmark Parameters** — Warehouses (TPC-C) or scale factor (TPC-H)
6. **Infrastructure** — Kubernetes namespace, Pure Storage metrics

After the core steps, an optional **Advanced Options** prompt lets you configure virtual users, rampup/duration, and pod resources. If declined, sensible defaults are used.

A **Configuration Summary** table is shown before writing, giving you a chance to review all values (passwords masked) and confirm or cancel.

Both `init` and `init -i` produce identical YAML output — the wizard is purely a UX enhancement for the input experience.

### `hammerdb-scale validate`

Validates configuration through 6 layers:

1. YAML syntax
2. Schema validation (Pydantic)
3. Image/database type consistency
4. Tool prerequisites (helm, kubectl)
5. Kubernetes cluster access
6. Database connectivity (actual login test)

```bash
hammerdb-scale validate                     # Full validation
hammerdb-scale validate --skip-connectivity # Skip DB login test
hammerdb-scale validate -f config.yaml      # Explicit config
```

### `hammerdb-scale build`

Creates benchmark schema (tables, indexes) on all database targets. Deploys one Kubernetes Job per target.

```bash
hammerdb-scale build --benchmark tprocc
hammerdb-scale build --benchmark tprocc --id my-test-001
hammerdb-scale build --wait              # Poll until all jobs complete
hammerdb-scale build --dry-run           # Render Helm templates only
```

`--benchmark` is optional if `default_benchmark` is set in your config.

### `hammerdb-scale run`

Executes the benchmark workload against all targets.

```bash
hammerdb-scale run --benchmark tprocc
hammerdb-scale run --build               # Build schema first, then run
hammerdb-scale run --wait                # Poll until completion
hammerdb-scale run --dry-run
```

With `--build`, the build phase must fully succeed before the run begins. This is the recommended workflow for new benchmarks.

### `hammerdb-scale status`

Shows current job status across all targets.

```bash
hammerdb-scale status                    # Most recent test
hammerdb-scale status --id <test-id>
hammerdb-scale status --watch            # Auto-refresh every 10s
hammerdb-scale status --json             # Machine-readable output
```

### `hammerdb-scale logs`

View HammerDB output logs from benchmark jobs.

```bash
hammerdb-scale logs                      # All targets, most recent test
hammerdb-scale logs --target ora-01      # Specific target
hammerdb-scale logs --follow             # Stream logs live
hammerdb-scale logs --tail 50            # Last 50 lines
```

### `hammerdb-scale results`

Aggregates results from K8s job logs, parses benchmark metrics, and saves to a local directory.

```bash
hammerdb-scale results
hammerdb-scale results --id <test-id>
hammerdb-scale results --json            # Machine-readable output
```

### `hammerdb-scale report`

Generates a self-contained HTML scorecard with charts and tables. The file can be opened in any browser, shared, or viewed offline — all CSS and JavaScript are embedded.

```bash
hammerdb-scale report                    # Default: results/{test-id}/scorecard.html
hammerdb-scale report --open             # Open in browser
hammerdb-scale report -o report.html     # Custom output path
```

### `hammerdb-scale clean`

Removes benchmark resources.

```bash
# Remove K8s resources (Helm releases, jobs)
hammerdb-scale clean --resources --id <test-id>
hammerdb-scale clean --resources --everything

# Drop database tables
hammerdb-scale clean --database --benchmark tprocc
hammerdb-scale clean --database --benchmark tprocc --target ora-01
hammerdb-scale clean --database --benchmark tprocc --dry-run

# Both
hammerdb-scale clean --resources --database --benchmark tprocc --id <test-id>

# Skip confirmation
hammerdb-scale clean --resources --everything --force
```

## Understanding Results

### Benchmark Metrics

**TPC-C** (Online Transaction Processing):

| Metric | What It Measures |
|--------|-----------------|
| **TPM** (Transactions Per Minute) | Total transaction throughput including all transaction types. Higher is better. |
| **NOPM** (New Orders Per Minute) | Throughput of the "New Order" transaction only. This is the TPC-C primary metric. Higher is better. |

**TPC-H** (Decision Support / Analytics):

| Metric | What It Measures |
|--------|-----------------|
| **QphH** (Queries Per Hour) | Composite metric reflecting how quickly the 22 standard TPC-H queries execute. Higher is better. |

### What to Expect

- TPM/NOPM scale roughly linearly with the number of database targets when storage is not the bottleneck
- When storage saturates, adding more databases will show diminishing returns — this is the point of scale testing
- Per-target metrics should be roughly equal. Large variance suggests a configuration or resource imbalance

### Output Directory

After running `results`, a directory is created at `./results/<test-id>/`:

```
results/my-benchmark-20250304-1200/
├── summary.json          # Aggregated metrics (TPM, NOPM, per-target breakdown)
├── ora-01.log            # HammerDB output log for target ora-01
├── ora-02.log            # HammerDB output log for target ora-02
├── ...                   # One log file per target
├── pure_metrics.json     # Pure Storage metrics (if enabled)
└── scorecard.html        # HTML report (after running `report`)
```

- **summary.json** — Machine-readable results. Contains per-target metrics, aggregate totals, and the config snapshot used for the test.
- **Target logs** — Raw HammerDB output. Useful for debugging failed targets or verifying benchmark parameters.
- **pure_metrics.json** — Time-series storage metrics from Pure Storage FlashArray (IOPS, latency, bandwidth).
- **scorecard.html** — Self-contained HTML report. Can be opened in any browser without a web server.

### Reading the Scorecard

The HTML scorecard contains:

**TPC-C Scorecard:**
- **Summary cards** — Total TPM, Total NOPM, Average TPM/target, Average NOPM/target
- **Per-target table** — Status, duration, TPM, and NOPM for each database target
- **Distribution charts** — Horizontal bar charts showing TPM and NOPM per target. Even bars indicate balanced load; uneven bars suggest an issue with specific targets.
- **Storage performance** (if Pure Storage metrics enabled) — Latency, IOPS, and bandwidth time-series charts showing how the storage array performed during the benchmark

**TPC-H Scorecard:**
- **QphH summary** — Composite query throughput metric
- **Per-query timing table** — Execution time for each of the 22 TPC-H queries (avg, min, max across targets)
- **Query distribution chart** — Visual comparison of query execution times

## Pure Storage Metrics

When `storage_metrics.enabled: true` in your config, HammerDB-Scale collects performance metrics from a Pure Storage FlashArray during the benchmark run phase.

### Setup

1. Obtain an API token from your FlashArray (Settings > Users > API Tokens)
2. Add to your config:

```yaml
storage_metrics:
  enabled: true
  pure:
    host: "10.0.0.100"           # FlashArray management IP
    api_token: "your-api-token"  # REST API token
    volume: ""                   # Leave empty for array-level metrics
    poll_interval: 5             # Collection interval in seconds
    verify_ssl: false
```

### What's Collected

- **Read/Write IOPS** — I/O operations per second
- **Read/Write Latency** — Response time in microseconds (average, P95, P99)
- **Read/Write Bandwidth** — Data throughput in bytes per second
- **Queue Depth** — Outstanding I/O requests

Metrics are collected from the first target pod only (to avoid duplicate API calls) and run as a background process for the duration of the benchmark.

### In the Report

The storage performance section of the scorecard shows:
- Summary cards with peak and average values
- Time-series line charts for latency, IOPS, and bandwidth over the duration of the test
- These charts help identify storage bottlenecks — look for latency spikes or IOPS plateaus that correlate with benchmark load

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Fatal error |
| 2 | Partial failure (some targets failed) |

## Global Options

| Option | Description |
|--------|-------------|
| `-f, --file PATH` | Config file path |
| `-v, --verbose` | Verbose output |

## Troubleshooting

### `helm not found` or `kubectl not found`

Install [Helm](https://helm.sh/docs/intro/install/) and [kubectl](https://kubernetes.io/docs/tasks/tools/), then ensure they're on your `PATH`. Run `hammerdb-scale version` to verify.

### Namespace doesn't exist

Create the namespace before running:

```bash
kubectl create namespace hammerdb
```

Or change the namespace in your config (`kubernetes.namespace`).

### Database connectivity failures during `validate`

- Verify the database host is reachable from your workstation: `telnet <host> <port>`
- Check credentials are correct
- For Oracle: ensure the listener is running and the service name matches your config
- For MSSQL: if using `encrypt_connection: true`, the server must support TLS

### Jobs stuck in Pending

Check pod events:

```bash
kubectl describe pod -n hammerdb -l hammerdb.io/test-id=<test-id>
```

Common causes:
- **ImagePullBackOff** — Container image can't be pulled. Check image name and registry access.
- **Insufficient resources** — Reduce `resources.requests` in your config or ensure your cluster has available capacity.

### Build jobs fail

```bash
hammerdb-scale logs --id <test-id>
```

Common causes:
- Wrong credentials (check `targets.defaults.username`/`password`)
- Database not reachable from inside the Kubernetes cluster (different from your workstation)
- For Oracle: tablespace doesn't exist — create it before building
- For MSSQL: database name conflict — use `clean --database` first

### Results show 0 TPM

- Ensure `driver: timed` (not `test`) in your TPC-C config
- Ensure `duration` is long enough (at least 5 minutes recommended)
- Check logs for errors: `hammerdb-scale logs --target <name>`

### Partial failures (exit code 2)

Some targets completed but others failed. Run `hammerdb-scale results` to see which targets succeeded. Check logs for failed targets individually:

```bash
hammerdb-scale logs --target <failed-target-name>
```
