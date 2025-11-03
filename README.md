# HammerDB Scale

A Kubernetes orchestrator for parallel HammerDB testing designed to validate storage platform performance at scale.

Full blog post here: https://sillidata.com/2025/11/03/stress-testing-consolidated-systems-with-database-workloads/ 

## What is HammerDB Scale?

HammerDB Scale allows you to run **synchronized database performance tests across multiple database instances simultaneously**. This is particularly valuable for:

- **Storage Platform Testing**: Validate storage array performance under realistic multi-database workloads
- **Scale Testing**: Test how storage performs when serving 2, 4, 8+ databases concurrently
- **Unified Testing**: Generate consistent, reproducible load across multiple SQL Server instances
- **Capacity Planning**: Understand how many database workloads your storage can support

### Use Cases

**Primary Use Case: Storage Performance Validation**
- Deploy multiple SQL Server instances on the same storage platform (SAN, NAS, cloud storage)
- Run identical TPC-C or TPC-H benchmarks across all instances simultaneously
- Measure aggregate throughput, latency, and IOPS at the storage level
- Validate storage array behavior under realistic multi-tenant database workloads

**Other Use Cases:**
- Database cluster performance testing
- Multi-region deployment validation
- Disaster recovery configuration testing
- Performance regression testing across multiple environments

## How It Works

Instead of testing one database at a time, HammerDB Scale orchestrates parallel tests:

```
Storage Platform (SAN/NAS/Cloud)
         |
    ┌────┴────┬────────┬────────┐
    │         │        │        │
 SQL-01   SQL-02   SQL-03   SQL-04  ← Multiple SQL Server instances
    │         │        │        │
    └────┬────┴────────┴────────┘
         │
  HammerDB Scale (Kubernetes Jobs)
    Parallel TPC-C/TPC-H Tests
         │
    Aggregate Results
```

Each database gets its own Kubernetes job running HammerDB, all starting simultaneously to create realistic storage load patterns.

## Features

- **Parallel Execution**: Test multiple databases simultaneously to stress storage platforms
- **Simple Design**: One Kubernetes job per database target, no complex orchestration
- **Results in Logs**: No persistent storage needed, all output to stdout
- **Helm Deployment**: Simple configuration and management
- **Manual Phase Control**: Run build, then load phases separately for flexibility
- **Storage Metrics**: Optional Pure Storage FlashArray performance monitoring
- **Aggregate Results**: Automatic collection and summarization across all targets

## Currently Supported Databases

- SQL Server (fully implemented)
- PostgreSQL (structure ready)
- Oracle (structure ready)
- MySQL/MariaDB (structure ready)

See [ADDING-DATABASES.md](ADDING-DATABASES.md) for extending to other databases.

## Architecture

```
Helm Install
     ↓
Creates N Jobs (one per target in values.yaml)
     ↓
Jobs run in parallel, independently
     ↓
Each job writes results to stdout
     ↓
User views results: kubectl logs
```

## Quick Start

### Prerequisites

Before you begin, ensure you have the following:

**Required:**
- **Kubernetes cluster** (1.19+) with sufficient resources
  - Worker nodes with adequate CPU and memory for your test scale
  - Network connectivity to target databases
- **kubectl** CLI tool installed and configured
  - Verify: `kubectl version --client`
- **Helm 3.x** installed
  - Verify: `helm version`
  - Installation: https://helm.sh/docs/intro/install/
- **Docker** (if building custom images)
  - Verify: `docker --version`
- **Database targets** properly configured
  - SQL Server instances accessible from Kubernetes cluster
  - Database credentials with appropriate permissions
  - Network ports open (default: 1433 for SQL Server)

**Optional (for development):**
- **Container registry** access (if using private images)
- **Pure Storage FlashArray** with API access (for storage metrics)
- **git** for version control
- **jq** for JSON processing in aggregation scripts

**Verification Commands:**
```bash
# Verify Kubernetes access
kubectl cluster-info
kubectl get nodes

# Verify Helm
helm version

# Verify kubectl can create resources
kubectl auth can-i create jobs --namespace=hammerdb-scale

# Test database connectivity (optional)
kubectl run test-db --rm -it --image=mcr.microsoft.com/mssql-tools \
  --restart=Never -- /opt/mssql-tools/bin/sqlcmd \
  -S your-sql-server.com -U sa -P YourPassword -Q "SELECT @@VERSION"
```

### 1. Clone and Build

```bash
git clone <repository-url>
cd hammerdb-scale

# Build Docker image
docker build -t hammerdb:latest .

# Push to registry if needed
docker tag hammerdb:latest your-registry.com/hammerdb:latest
docker push your-registry.com/hammerdb:latest
```

### 2. Configure Your Test

Edit [values.yaml](values.yaml):

```yaml
testRun:
  id: "test-001"
  phase: "build"  # Options: "build" or "load"
  benchmark: "tprocc"  # Options: "tprocc" or "tproch"

targets:
  - name: sqleng-node03
    type: mssql
    host: "sqlserver1.example.com"
    username: sa
    password: "YourPassword"
    tprocc:
      databaseName: tpcc
    tproch:
      databaseName: tpch
```

### 3. Run Tests

#### Build Phase

```bash
# Deploy build jobs
helm install build-test-001 . -n hammerdb-scale --create-namespace \
  --set testRun.phase=build \
  --set testRun.id=test-001

# Watch progress
kubectl logs -n hammerdb-scale -l hammerdb.io/phase=build --follow

# View specific target
kubectl logs -n hammerdb-scale job/hammerdb-scale-build-sqleng-node03-test-001
```

#### Load Phase

```bash
# After build completes, uninstall build
helm uninstall build-test-001 -n hammerdb-scale

# Deploy load jobs
helm install load-test-001 . -n hammerdb-scale \
  --set testRun.phase=load \
  --set testRun.id=test-001

# Watch progress
kubectl logs -n hammerdb-scale -l hammerdb.io/phase=load --follow

# Save results
kubectl logs -n hammerdb-scale job/hammerdb-scale-load-sqleng-node03-test-001 > results-node03.txt
```

#### Using the Deploy Script

```bash
# Make script executable
chmod +x deploy-test.sh

# Build phase (using named arguments - recommended)
./deploy-test.sh --phase build --test-id test-001 --benchmark tprocc

# Load phase (using named arguments - recommended)
./deploy-test.sh --phase load --test-id test-001 --benchmark tprocc

# You can also use positional arguments for backward compatibility
./deploy-test.sh build test-001 tprocc
```

## Project Structure

```
hammerdb-scale/
├── Chart.yaml                          # Helm chart metadata
├── values.yaml                         # Default configuration
├── values-examples.yaml                # Example configurations
├── deploy-test.sh                      # Deployment script
├── dockerfile                          # HammerDB container image
├── entrypoint.sh                       # Container entrypoint
│
├── templates/                          # Helm templates
│   ├── _helpers.tpl                   # Template helpers (config merging)
│   ├── configmap-mssql.yaml           # SQL Server TCL scripts
│   └── job-hammerdb-worker.yaml       # Parallel worker jobs
│
└── scripts/                            # HammerDB TCL scripts
    └── mssql/                         # SQL Server specific
        ├── build_schema_tprocc.tcl
        ├── build_schema_tproch.tcl
        ├── load_test_tprocc.tcl
        ├── load_test_tproch.tcl
        ├── generic_tprocc_result.tcl
        └── parse_output_tproch.tcl
```

## Configuration

### Test Run Settings

```yaml
testRun:
  id: "test-001"           # Unique test identifier
  phase: "build"           # Options: "build" or "load"
  benchmark: "tprocc"      # Options: "tprocc" or "tproch"
  cleanBeforeBuild: false  # Drop existing schema before build
```

### Virtual Users: Build vs Load

**Important:** Build and load phases use **different VU counts** for optimal performance:

```yaml
hammerdb:
  tprocc:
    build_num_vu: 16   # More VUs for faster parallel build
    load_num_vu: 8     # Fewer VUs for realistic load simulation
```

**Why different?**
- **Build phase:** Uses more VUs (16-32) to parallelize schema creation and data loading across warehouses
- **Load phase:** Uses fewer VUs (4-16) to simulate realistic user concurrency and get accurate TPM metrics

**Recommendation:**
- Small tests (10-50 warehouses): `build_num_vu: 8`, `load_num_vu: 4`
- Medium tests (100 warehouses): `build_num_vu: 16`, `load_num_vu: 8`
- Large tests (1000+ warehouses): `build_num_vu: 32`, `load_num_vu: 16`

### Database Targets

Define your database targets with connection details:

```yaml
targets:
  - name: sqleng-node03
    type: mssql
    host: "server.example.com"
    username: sa
    password: "SecurePassword"

    # TPC-C configuration
    tprocc:
      databaseName: tpcc
      # Optional: Override global settings
      # warehouses: 500
      # num_vu: 8

    # TPC-H configuration
    tproch:
      databaseName: tpch
      # Optional: Override global settings
      # scaleFactor: 50
```

### Global Test Parameters

Set defaults that apply to all targets (can be overridden per target):

```yaml
hammerdb:
  connection:
    tcp: true
    port: 1433
    authentication: sql
    encrypt_connection: false
    trust_server_cert: false

  tprocc:
    warehouses: 100
    build_num_vu: 16        # Virtual users for BUILD phase
    load_num_vu: 8          # Virtual users for LOAD phase
    use_bcp: false
    driver: timed
    rampup: 5
    duration: 10
    total_iterations: 10000000
    allwarehouse: true
    checkpoint: true
    timeprofile: false

  tproch:
    scaleFactor: 100
    buildThreads: 8
    virtualUsers: 4
    totalQuerysets: 1
    maxdop: 8
    useClusteredColumnstore: false
```

See [values.yaml](values.yaml) for complete configuration reference.

## Usage Examples

### Complete Workflow with Aggregation

```bash
# 1. Build schemas
./deploy-test.sh --phase build --test-id test-001 --benchmark tprocc

# 2. Wait for completion
kubectl wait --for=condition=complete -n hammerdb-scale job -l hammerdb.io/phase=build --timeout=3600s

# 3. Cleanup build
helm uninstall build-test-001 -n hammerdb-scale

# 4. Run load test
./deploy-test.sh --phase load --test-id test-001 --benchmark tprocc

# 5. Wait for load test completion
kubectl wait --for=condition=complete -n hammerdb-scale job -l hammerdb.io/phase=load --timeout=3600s

# 6. Aggregate results
./aggregate-results.sh --phase load --test-id test-001

# 7. View summary
cat ./results/test-001/load/summary.txt

# 8. Cleanup
helm uninstall load-test-001 -n hammerdb-scale
```

### Monitor Job Status

```bash
# All jobs for a test run
kubectl get jobs -n hammerdb-scale -l hammerdb.io/test-run=test-001

# View specific worker logs
kubectl logs -n hammerdb-scale job/hammerdb-scale-build-sqleng-node03-test-001

# Watch pods
kubectl get pods -n hammerdb-scale -l hammerdb.io/test-run=test-001 -w
```

### Aggregate Results

Use the aggregation script to collect all logs and create a summary:

```bash
# Make script executable (one-time)
chmod +x aggregate-results.sh

# Aggregate load test results (using named arguments - recommended)
./aggregate-results.sh --phase load --test-id test-001

# Or use positional arguments for backward compatibility
./aggregate-results.sh load test-001

# Output will be saved to:
#   ./results/test-001/load/summary.txt      # Human-readable summary
#   ./results/test-001/load/summary.json     # Machine-readable JSON
#   ./results/test-001/load/*.log            # Individual job logs
```

**What it does:**
- Fetches logs from all jobs for the test run
- Extracts key metrics (TPM, NOPM for TPC-C; QphH for TPC-H)
- Creates summary report with all results
- Saves individual logs per target

### Manual Log Collection

```bash
# Save all load test results manually
for job in $(kubectl get jobs -n hammerdb-scale -l hammerdb.io/phase=load -o name); do
  kubectl logs -n hammerdb-scale $job > ${job##*/}.log
done

# Or specific target
kubectl logs -n hammerdb-scale job/hammerdb-scale-load-sqleng-node03-test-001 > results-node03.txt
```

## Monitoring and Troubleshooting

### View Job Status

```bash
# All jobs
kubectl get jobs -n hammerdb-scale

# With labels
kubectl get jobs -n hammerdb-scale -l hammerdb.io/phase=build

# Describe failed job
kubectl describe job -n hammerdb-scale <job-name>
```

### View Logs

```bash
# All jobs in a phase
kubectl logs -n hammerdb-scale -l hammerdb.io/phase=build --follow

# Specific job
kubectl logs -n hammerdb-scale job/<job-name>

# Tail last 100 lines
kubectl logs -n hammerdb-scale job/<job-name> --tail=100
```

### Common Issues

**Jobs not starting:**
```bash
# Check events
kubectl get events -n hammerdb-scale --sort-by='.lastTimestamp'

# Describe pod
kubectl describe pod -n hammerdb-scale <pod-name>
```

**Database connection issues:**
```bash
# Check logs for connection errors
kubectl logs -n hammerdb-scale job/<job-name> | grep -i error

# Test connectivity
kubectl run test -n hammerdb-scale --rm -it --image=busybox -- nc -zv sqlserver.example.com 1433
```

**Test failures:**
```bash
# View full logs
kubectl logs -n hammerdb-scale job/<job-name>

# Check exit code
kubectl get job -n hammerdb-scale <job-name> -o jsonpath='{.status.conditions[?(@.type=="Failed")].reason}'
```

## Cleanup

```bash
# Uninstall specific release
helm uninstall build-test-001 -n hammerdb-scale
helm uninstall load-test-001 -n hammerdb-scale

# Delete all jobs for a test run
kubectl delete jobs -n hammerdb-scale -l hammerdb.io/test-run=test-001

# Delete entire namespace
kubectl delete namespace hammerdb-scale
```

## Advanced Usage

### Override at Install Time

```bash
# Change test parameters
helm install test . -n hammerdb-scale \
  --set testRun.id=custom-001 \
  --set testRun.phase=build \
  --set hammerdb.tprocc.warehouses=500 \
  --set hammerdb.tprocc.num_vu=32
```

### Multiple Benchmarks

```bash
# Run TPC-C
helm install tpcc-test . -n hammerdb-scale \
  --set testRun.benchmark=tprocc \
  --set testRun.phase=build

# Run TPC-H
helm install tpch-test . -n hammerdb-scale \
  --set testRun.benchmark=tproch \
  --set testRun.phase=build
```

### Custom Values Files

Create scenario-specific configurations:

```bash
# Small development test
helm install dev-test . -n hammerdb-scale -f values-small.yaml

# Production-like test
helm install prod-test . -n hammerdb-scale -f values-production.yaml
```

## Best Practices

1. **Start Small**: Test with 1-2 databases first
2. **Build Once**: Build schemas separately, then run multiple load tests
3. **Save Logs**: Always save kubectl logs output before cleanup
4. **Use Unique IDs**: Use descriptive test IDs like `perf-2024-01-15-baseline`
5. **Monitor Resources**: Watch CPU/memory on both Kubernetes and databases
6. **Cleanup Between Runs**: Uninstall previous release before new test

## Security Best Practices

**IMPORTANT**: Follow these security guidelines when deploying in production:

1. **Credentials Management**
   - **Never commit real passwords to version control**
   - Use Kubernetes Secrets for sensitive data:
     ```bash
     kubectl create secret generic db-credentials \
       --from-literal=username=sa \
       --from-literal=password='YourSecurePassword' \
       -n hammerdb-scale
     ```
   - Consider using external secret management (HashiCorp Vault, AWS Secrets Manager, etc.)
   - Use separate values files for each environment (dev, staging, prod)
   - Add `values-local.yaml` to `.gitignore`

2. **Network Security**
   - Use NetworkPolicies to restrict traffic between namespaces
   - Enable TLS/SSL encryption for database connections where possible
   - Use private container registries for custom images
   - Restrict access to Kubernetes API and namespaces using RBAC

3. **Pure Storage API Tokens**
   - Treat API tokens as passwords - never commit to git
   - Rotate API tokens regularly
   - Use read-only API tokens if write access is not needed
   - Store tokens in Kubernetes Secrets

4. **Container Security**
   - Scan container images for vulnerabilities regularly
   - Use specific image tags instead of `latest` in production
   - Run containers as non-root user where possible
   - Keep base images updated

5. **Example Secure Deployment**
   ```bash
   # Create secrets
   kubectl create secret generic db-credentials \
     --from-literal=password='YourSecurePassword' \
     -n hammerdb-scale

   kubectl create secret generic pure-api \
     --from-literal=token='your-api-token' \
     -n hammerdb-scale

   # Deploy using secrets (requires Helm chart modifications)
   helm install test-001 . -n hammerdb-scale \
     --set-file valuesFile=values-prod.yaml
   ```

6. **Audit and Compliance**
   - Enable Kubernetes audit logging
   - Review logs regularly for unauthorized access attempts
   - Document all test runs and their configurations
   - Maintain change logs for infrastructure modifications

## Resource Requirements

### Per Worker Pod
- **Small** (10-50 warehouses): 2Gi RAM, 1 CPU
- **Medium** (100 warehouses): 4Gi RAM, 2 CPU
- **Large** (200+ warehouses): 8Gi RAM, 4 CPU

Configure in [values.yaml](values.yaml):

```yaml
global:
  resources:
    requests:
      memory: "4Gi"
      cpu: "2"
    limits:
      memory: "8Gi"
      cpu: "4"
```

## Extending to Other Databases

This project is designed to easily support PostgreSQL, Oracle, and MySQL. See [ADDING-DATABASES.md](ADDING-DATABASES.md) for a complete guide on adding new database types.

**Extension points:**
- ✅ Modular ConfigMaps per database type
- ✅ Conditional environment variables in worker jobs
- ✅ Database-specific script directories
- ✅ Driver mapping in Helm helpers
- ✅ Clear documentation for adding new types

## Documentation

- [ADDING-DATABASES.md](ADDING-DATABASES.md) - Add PostgreSQL, Oracle, MySQL support
- [values-examples.yaml](values-examples.yaml) - Configuration examples

## Contributing

Contributions welcome! Especially:
- PostgreSQL implementation
- Oracle implementation
- MySQL/MariaDB implementation
- Additional monitoring/observability features
- CI/CD integration examples

## License

Same as HammerDB project.

## Support

- Open an issue for bugs or feature requests
- See HammerDB documentation: https://www.hammerdb.com
- Check Kubernetes logs for troubleshooting

## Quick Reference

Common commands for quick access:

```bash
# Deploy build phase
./deploy-test.sh --phase build --test-id test-001 --benchmark tprocc

# Deploy load phase
./deploy-test.sh --phase load --test-id test-001 --benchmark tprocc

# Watch job progress
kubectl get jobs -n hammerdb-scale -w

# View logs (follow)
kubectl logs -n hammerdb-scale -l hammerdb.io/phase=load --follow

# Aggregate results
./aggregate-results.sh --phase load --test-id test-001

# Cleanup
helm uninstall load-test-001 -n hammerdb-scale

# Quick test connectivity
kubectl run test-sql --rm -it --image=mcr.microsoft.com/mssql-tools \
  --restart=Never -- /opt/mssql-tools/bin/sqlcmd \
  -S sqlserver.example.com -U sa -P Password -Q "SELECT @@VERSION"
```

## Credits

Built on top of [HammerDB](https://www.hammerdb.com) by Steve Shaw.
