# HammerDB Scale

A Kubernetes orchestrator for parallel HammerDB testing designed to validate storage platform performance at scale.

## What is HammerDB Scale?

HammerDB Scale runs **synchronized database performance tests across multiple database instances simultaneously**. This is particularly valuable for:

- **Storage Platform Testing**: Validate storage array performance under realistic multi-database workloads
- **Scale Testing**: Test how storage performs when serving 2, 4, 8+ databases concurrently
- **Capacity Planning**: Understand how many database workloads your storage can support

## How It Works

```
Storage Platform (SAN/NAS/Cloud)
         |
    ┌────┴────┬────────┬────────┐
    │         │        │        │
  DB-01    DB-02    DB-03    DB-04  ← Multiple database instances
    │         │        │        │
    └────┬────┴────────┴────────┘
         │
  HammerDB Scale (Kubernetes Jobs)
    Parallel TPC-C/TPC-H Tests
```

Each database gets its own Kubernetes job running HammerDB, all starting simultaneously to create realistic storage load patterns.

## Features

- **Parallel Execution**: Test multiple databases simultaneously
- **Simple Design**: One Kubernetes job per database target
- **Helm Deployment**: Simple configuration and management
- **Storage Metrics**: Optional Pure Storage FlashArray monitoring
- **Result Aggregation**: Automatic collection and summarization

## Supported Databases

| Database | Status | Image |
|----------|--------|-------|
| **SQL Server** | Ready | `sillidata/hammerdb-scale:latest` |
| **Oracle** | Ready | Build `Dockerfile.oracle` ([setup guide](docs/databases/ORACLE-SETUP.md)) |
| PostgreSQL | Planned | - |
| MySQL | Planned | - |

## Quick Start

### 1. Configure targets in `values.yaml`

```yaml
targets:
  - name: sqlserver-01
    type: mssql
    host: "sqlserver1.example.com"
    username: sa
    password: "YourPassword"
    tprocc:
      databaseName: tpcc
```

### 2. Build schemas

```bash
./deploy-test.sh --phase build --test-id test-001 --benchmark tprocc
kubectl logs -n default -l hammerdb.io/phase=build --follow
```

### 3. Run load test

```bash
helm uninstall build-test-001
./deploy-test.sh --phase load --test-id test-001 --benchmark tprocc
kubectl logs -n default -l hammerdb.io/phase=load --follow
```

### 4. Aggregate results

```bash
./aggregate-results.sh --phase load --test-id test-001
cat ./results/test-001/load/summary.txt
```

## Docker Images

```
┌─────────────────────────────────────────────────────────────┐
│  sillidata/hammerdb-scale:latest (PUBLIC)                   │
│  ✓ SQL Server, PostgreSQL, MySQL drivers                    │
│  ✓ All TCL scripts and Pure Storage collector               │
└─────────────────────────────────────────────────────────────┘
                              │
                    docker build -f Dockerfile.oracle
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  myregistry/hammerdb-scale-oracle:latest (USER BUILDS)      │
│  + Oracle Instant Client 21.11                             │
└─────────────────────────────────────────────────────────────┘
```

## Documentation

| Document | Description |
|----------|-------------|
| [Configuration Guide](docs/CONFIGURATION.md) | All values.yaml options |
| [Usage Guide](docs/USAGE-GUIDE.md) | Workflows and troubleshooting |
| [Oracle Setup](docs/databases/ORACLE-SETUP.md) | Building Oracle-enabled images |
| [Adding Databases](docs/ADDING-DATABASES.md) | Extend to PostgreSQL, MySQL |
| [Changelog](CHANGELOG.md) | Version history |

## Project Structure

```
hammerdb-scale/
├── Chart.yaml              # Helm chart metadata
├── values.yaml             # Configuration
├── CHANGELOG.md            # Version history
├── Dockerfile              # Base image (SQL Server)
├── Dockerfile.oracle       # Oracle extension
├── templates/              # Helm templates
├── scripts/                # HammerDB TCL scripts
├── examples/               # Example configurations
└── docs/                   # Documentation
```

## Quick Reference

```bash
# Deploy
./deploy-test.sh --phase build --test-id test-001 --benchmark tprocc
./deploy-test.sh --phase load --test-id test-001 --benchmark tprocc

# Monitor
kubectl get jobs -n hammerdb-scale -w
kubectl logs -n hammerdb-scale -l hammerdb.io/phase=load --follow

# Results
./aggregate-results.sh --phase load --test-id test-001

# Cleanup
helm uninstall load-test-001 -n hammerdb-scale
```

## Contributing

Contributions welcome! Especially:
- PostgreSQL implementation
- MySQL/MariaDB implementation
- Additional monitoring features

## License

Same as HammerDB project.

## Credits

Built on [HammerDB](https://www.hammerdb.com) by Steve Shaw.
