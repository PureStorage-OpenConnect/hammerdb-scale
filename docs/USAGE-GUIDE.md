[← Back to README](../README.md) | [Configuration](CONFIGURATION.md) | [Security](SECURITY.md)

# Usage Guide

Complete guide for running HammerDB Scale tests, including workflows, monitoring, and troubleshooting.

## Prerequisites

Before you begin, ensure you have the following:

### Required

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
  - SQL Server or Oracle instances accessible from Kubernetes cluster
  - Database credentials with appropriate permissions
  - Network ports open (1433 for SQL Server, 1521 for Oracle)

### Optional

- **Container registry** access (if using private images)
- **Pure Storage FlashArray** with API access (for storage metrics)
- **git** for version control
- **jq** for JSON processing in aggregation scripts

### Verification Commands

```bash
# Verify Kubernetes access
kubectl cluster-info
kubectl get nodes

# Verify Helm
helm version

# Verify kubectl can create resources
kubectl auth can-i create jobs --namespace=hammerdb-scale

# Test database connectivity (SQL Server)
kubectl run test-db --rm -it --image=mcr.microsoft.com/mssql-tools \
  --restart=Never -- /opt/mssql-tools/bin/sqlcmd \
  -S your-sql-server.com -U sa -P YourPassword -Q "SELECT @@VERSION"
```

## Complete Workflow

### 1. Build Phase

Build the database schemas:

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

### 2. Wait for Build Completion

```bash
kubectl wait --for=condition=complete -n hammerdb-scale \
  job -l hammerdb.io/phase=build --timeout=3600s
```

### 3. Cleanup Build Release

```bash
helm uninstall build-test-001 -n hammerdb-scale
```

### 4. Load Phase

Run the performance test:

```bash
# Deploy load jobs
helm install load-test-001 . -n hammerdb-scale \
  --set testRun.phase=load \
  --set testRun.id=test-001

# Watch progress
kubectl logs -n hammerdb-scale -l hammerdb.io/phase=load --follow

# Save results
kubectl logs -n hammerdb-scale job/hammerdb-scale-load-sqleng-node03-test-001 > results-node03.txt
```

### 5. Wait for Load Completion

```bash
kubectl wait --for=condition=complete -n hammerdb-scale \
  job -l hammerdb.io/phase=load --timeout=3600s
```

### 6. Aggregate Results

```bash
./aggregate-results.sh --phase load --test-id test-001

# View summary
cat ./results/test-001/load/summary.txt
```

### 7. Cleanup

```bash
helm uninstall load-test-001 -n hammerdb-scale
```

## Using the Deploy Script

The deploy script simplifies the workflow:

```bash
# Make script executable (one-time)
chmod +x deploy-test.sh

# Build phase (named arguments - recommended)
./deploy-test.sh --phase build --test-id test-001 --benchmark tprocc

# Load phase
./deploy-test.sh --phase load --test-id test-001 --benchmark tprocc

# With custom namespace
./deploy-test.sh --phase load --test-id test-001 --benchmark tprocc --namespace my-namespace

# Positional arguments (backward compatible)
./deploy-test.sh build test-001 tprocc
./deploy-test.sh load test-001 tprocc compass
```

## Monitoring

### View Job Status

```bash
# All jobs
kubectl get jobs -n hammerdb-scale

# Jobs for specific test run
kubectl get jobs -n hammerdb-scale -l hammerdb.io/test-run=test-001

# Jobs by phase
kubectl get jobs -n hammerdb-scale -l hammerdb.io/phase=build

# Watch pods
kubectl get pods -n hammerdb-scale -l hammerdb.io/test-run=test-001 -w
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

### Describe Jobs

```bash
kubectl describe job -n hammerdb-scale <job-name>
```

## Aggregating Results

Use the aggregation script to collect all logs and create a summary:

```bash
# Make script executable (one-time)
chmod +x aggregate-results.sh

# Aggregate load test results
./aggregate-results.sh --phase load --test-id test-001

# Or use positional arguments
./aggregate-results.sh load test-001
```

**Output files:**
- `./results/test-001/load/summary.txt` - Human-readable summary
- `./results/test-001/load/summary.json` - Machine-readable JSON
- `./results/test-001/load/*.log` - Individual job logs

**What it extracts:**
- TPM, NOPM for TPC-C
- QphH for TPC-H
- Per-target performance metrics

### Manual Log Collection

```bash
# Save all load test results
for job in $(kubectl get jobs -n hammerdb-scale -l hammerdb.io/phase=load -o name); do
  kubectl logs -n hammerdb-scale $job > ${job##*/}.log
done

# Or specific target
kubectl logs -n hammerdb-scale job/hammerdb-scale-load-sqleng-node03-test-001 > results-node03.txt
```

## Troubleshooting

### Jobs Not Starting

```bash
# Check events
kubectl get events -n hammerdb-scale --sort-by='.lastTimestamp'

# Describe pod
kubectl describe pod -n hammerdb-scale <pod-name>
```

**Common causes:**
- Insufficient resources (CPU/memory)
- Image pull errors
- ConfigMap not found

### Database Connection Issues

```bash
# Check logs for connection errors
kubectl logs -n hammerdb-scale job/<job-name> | grep -i error

# Test connectivity
kubectl run test -n hammerdb-scale --rm -it --image=busybox -- nc -zv sqlserver.example.com 1433
```

**Common causes:**
- Wrong hostname/port
- Firewall blocking connections
- Invalid credentials
- Database not accessible from cluster

### Test Failures

```bash
# View full logs
kubectl logs -n hammerdb-scale job/<job-name>

# Check exit code
kubectl get job -n hammerdb-scale <job-name> -o jsonpath='{.status.conditions[?(@.type=="Failed")].reason}'
```

### Oracle Client Missing

If you see the error "Oracle Instant Client not found", you need to build the Oracle extension image:

```bash
docker build -f Dockerfile.oracle -t myregistry/hammerdb-scale-oracle:latest .
docker push myregistry/hammerdb-scale-oracle:latest
```

Then update your values.yaml to use this image.

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
