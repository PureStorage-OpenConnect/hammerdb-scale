# HammerDB-Scale

[![PyPI version](https://img.shields.io/pypi/v/hammerdb-scale)](https://pypi.org/project/hammerdb-scale/)
[![Python versions](https://img.shields.io/pypi/pyversions/hammerdb-scale)](https://pypi.org/project/hammerdb-scale/)
[![License](https://img.shields.io/pypi/l/hammerdb-scale)](LICENSE)

A Python CLI for orchestrating parallel HammerDB database benchmarks at scale on Kubernetes.

## What is HammerDB-Scale?

HammerDB-Scale runs **synchronized database performance tests across multiple database instances simultaneously**. It deploys HammerDB as Kubernetes Jobs targeting multiple databases in parallel, making it ideal for:

- **Storage Platform Testing**: Validate storage array performance under realistic multi-database workloads
- **Scale Testing**: Test how storage performs when serving 2, 4, 8+ databases concurrently
- **Capacity Planning**: Understand how many database workloads your storage can support

## How It Works

HammerDB-Scale is a CLI orchestrator that sits on your workstation and drives benchmarks through Kubernetes:

```
                         +--------------------------------------+
                         |        Kubernetes Cluster            |
hammerdb-scale CLI       |                                      |
 (your machine)          |  +-----------+    +--------------+   |
       |                 |  | HammerDB  |--->| Database 1   |   |
       | helm install    |  | Job 1     |    +--------------+   |
       |---------------->|  +-----------+                       |
       |                 |  +-----------+    +--------------+   |
       | kubectl logs    |  | HammerDB  |--->| Database 2   |   |
       |---------------->|  | Job 2     |    +--------------+   |
       |                 |  +-----------+                       |
       | results/report  |  +-----------+    +--------------+   |
       |                 |  | HammerDB  |--->| Database N   |   |
       |                 |  | Job N     |    +--------------+   |
       |                 |  +-----------+                       |
       |                 +--------------------------------------+
```

1. You define your database targets and benchmark parameters in a YAML config file
2. The CLI translates your config into Helm values and deploys one Kubernetes Job per database target
3. Each Job runs a HammerDB container that connects to its assigned database and executes the benchmark
4. All Jobs run in parallel, producing synchronized load across all targets
5. The CLI collects results from Job logs, aggregates metrics (TPM/NOPM for TPC-C, QphH for TPC-H), and generates an HTML scorecard

## Quick Start

```bash
# Install
pip install hammerdb-scale

# Generate config interactively
hammerdb-scale init

# Validate config and database connectivity
hammerdb-scale validate

# Build schema, run benchmark, collect results
hammerdb-scale run --build --wait
hammerdb-scale results
hammerdb-scale report --open
```

## Supported Databases

| Database | Benchmarks | Container Image |
|----------|-----------|-----------------|
| **SQL Server** | TPC-C, TPC-H | `sillidata/hammerdb-scale:latest` |
| **Oracle** | TPC-C, TPC-H | `sillidata/hammerdb-scale-oracle:latest` |

## Workflow

```
init  →  validate  →  run --build  →  results  →  report
 │          │             │              │           │
 │          │             │              │           └─ HTML scorecard
 │          │             │              └─ aggregate TPM/NOPM/QphH
 │          │             └─ build schema + run benchmark (parallel K8s jobs)
 │          └─ check config, helm, kubectl, DB connectivity
 └─ generate config interactively
```

## Commands

| Command | Description |
|---------|-------------|
| `version` | Show CLI, Python, helm, kubectl versions |
| `init` | Generate config file interactively |
| `validate` | Validate config, prerequisites, and connectivity |
| `build` | Create benchmark schema on database targets |
| `run` | Execute benchmark workload (`--build` for combined) |
| `status` | Show job status with `--watch` for live updates |
| `logs` | View HammerDB output logs |
| `results` | Aggregate and display benchmark results |
| `report` | Generate self-contained HTML scorecard |
| `clean` | Remove K8s resources and/or database tables |

## Documentation

- [Configuration Reference](https://github.com/PureStorage-OpenConnect/hammerdb-scale/blob/main/docs/CONFIGURATION.md) — YAML schema, target defaults, examples
- [Usage Guide](https://github.com/PureStorage-OpenConnect/hammerdb-scale/blob/main/docs/USAGE-GUIDE.md) — Command reference, results interpretation, troubleshooting
- [Container Images](https://github.com/PureStorage-OpenConnect/hammerdb-scale/blob/main/docs/CONTAINER-IMAGES.md) — Pre-built images, building your own, architecture
- [Migration Guide (v1 to v2)](https://github.com/PureStorage-OpenConnect/hammerdb-scale/blob/main/docs/MIGRATION.md) — Upgrading from shell-script version
- [Security](https://github.com/PureStorage-OpenConnect/hammerdb-scale/blob/main/docs/SECURITY.md) — Credential handling and network considerations
- [Changelog](https://github.com/PureStorage-OpenConnect/hammerdb-scale/blob/main/CHANGELOG.md)

## Requirements

- **Python 3.10+**
- **Helm 3.x** — used to template and deploy Kubernetes Jobs
- **kubectl** — configured with a context that has access to your cluster
- **Kubernetes cluster** — with permissions to create Jobs and Namespaces
- **Database targets** — one or more Oracle or SQL Server instances reachable from the cluster

### Optional

- [pipx](https://pipx.pypa.io/) — recommended for installing CLI tools in isolated environments: `pipx install hammerdb-scale`

## Configuration

See the [Configuration Reference](https://github.com/PureStorage-OpenConnect/hammerdb-scale/blob/main/docs/CONFIGURATION.md) for the full schema. Minimal example:

```yaml
name: my-benchmark
default_benchmark: tprocc

targets:
  defaults:
    type: mssql
    username: sa
    password: "YourPassword"
    mssql: {}
  hosts:
    - name: sql-01
      host: sql-01.example.com
    - name: sql-02
      host: sql-02.example.com

hammerdb:
  tprocc:
    warehouses: 100
    load_virtual_users: 4
    driver: timed
    rampup: 2
    duration: 5
```

Complete examples for all database/benchmark combinations are in the [examples/](https://github.com/PureStorage-OpenConnect/hammerdb-scale/tree/main/examples) directory.

## Contributing

Contributions are welcome! Please [open an issue](https://github.com/PureStorage-OpenConnect/hammerdb-scale/issues) to report bugs or request features.

## License

[Apache 2.0](https://github.com/PureStorage-OpenConnect/hammerdb-scale/blob/main/LICENSE)
