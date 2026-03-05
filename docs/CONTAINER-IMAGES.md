# Container Images

HammerDB-Scale deploys HammerDB as Kubernetes Jobs using pre-built container images. Each Job runs a container that connects to a single database target, executes the benchmark, and outputs results to its logs.

## Pre-Built Images

| Image | Database | Source |
|-------|----------|--------|
| `sillidata/hammerdb-scale:latest` | SQL Server | [dockerfile](../dockerfile) |
| `sillidata/hammerdb-scale-oracle:latest` | Oracle | [Dockerfile.oracle](../Dockerfile.oracle) |

These images are hosted on Docker Hub and can be pulled without authentication.

## What's Inside

Both images include:

- **Ubuntu 24.04** base
- **HammerDB 5.0** — the benchmark engine
- **Python 3** — for the Pure Storage metrics collector
- **entrypoint.sh** — orchestration script that receives configuration via environment variables, runs HammerDB, and manages metrics collection

The **MSSQL image** additionally includes:
- Microsoft ODBC Driver 18 for SQL Server
- `mssql-tools18` (including `bcp` for bulk data loading)

The **Oracle image** extends the MSSQL image and adds:
- Oracle Instant Client 21.11 (Basic + SQL*Plus)
- Required shared libraries for HammerDB's Oratcl interface

## Building Your Own Images

### SQL Server Image

```bash
docker build -f dockerfile -t my-org/hammerdb-scale:latest .
```

### Oracle Image

The Oracle image extends the base image:

```bash
# Build base first
docker build -f dockerfile -t my-org/hammerdb-scale:latest .

# Then build Oracle (references base image)
docker build -f Dockerfile.oracle -t my-org/hammerdb-scale-oracle:latest .
```

> **Note:** Building the Oracle image downloads Oracle Instant Client from Oracle's servers. By building and using this image, you accept the [Oracle Technology Network License Agreement](https://www.oracle.com/downloads/licenses/instant-client-lic.html).

### Using Custom Images

Update `targets.defaults.image` in your config to point to your image:

```yaml
targets:
  defaults:
    image:
      repository: my-org/hammerdb-scale-oracle
      tag: v2.0.0
      pull_policy: Always
```

Ensure your Kubernetes cluster can pull from your registry (configure `imagePullSecrets` if needed).

## Image Architecture

```
entrypoint.sh (container startup)
     │
     ├── Validates environment variables
     ├── Selects TCL script based on DATABASE_TYPE + BENCHMARK + PHASE
     ├── Runs: hammerdbcli auto <script>
     ├── [If Pure Storage enabled] Spawns collect_pure_metrics.py as background process
     └── Writes metadata.json with results and timing
```

The CLI never connects to the container directly. All configuration passes through environment variables set by the Helm chart, and all results are extracted from pod logs via `kubectl`.

## Environment Variables

The Helm chart sets these environment variables on each Job pod. You don't need to set these manually — they're populated from your config file automatically.

| Variable | Description |
|----------|-------------|
| `RUN_MODE` | `build` or `load` |
| `BENCHMARK` | `tprocc` or `tproch` |
| `DATABASE_TYPE` | `mssql` or `oracle` |
| `HOST` | Database hostname |
| `USERNAME` | Database admin user |
| `PASSWORD` | Database admin password |
| `TARGET_NAME` | Target identifier from config |
| `TARGET_INDEX` | 0-based index of this target |
| `TEST_RUN_ID` | Test run identifier |

Additional database-specific and benchmark-specific variables are documented in the [Helm template](../templates/job-hammerdb-worker.yaml).
