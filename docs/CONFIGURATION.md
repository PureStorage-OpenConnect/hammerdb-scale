[← Back to README](../README.md) | [Usage Guide](USAGE-GUIDE.md) | [Security](SECURITY.md)

# Configuration Guide

Complete reference for configuring HammerDB Scale tests.

## Test Run Settings

```yaml
testRun:
  id: "test-001"           # Unique test identifier
  phase: "build"           # Options: "build" or "load"
  benchmark: "tprocc"      # Options: "tprocc" or "tproch"
  cleanBeforeBuild: false  # Drop existing schema before build
```

## Virtual Users: Build vs Load

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

**Recommendations:**
| Test Size | Warehouses | build_num_vu | load_num_vu |
|-----------|------------|--------------|-------------|
| Small | 10-50 | 8 | 4 |
| Medium | 100 | 16 | 8 |
| Large | 1000+ | 32 | 16 |

## Database Targets

Define your database targets with connection details:

```yaml
targets:
  - name: sqleng-node03
    type: mssql              # Options: mssql, oracle
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

### Oracle Target Example

```yaml
targets:
  - name: oracle-prod-01
    type: oracle
    host: "oracle.example.com"
    username: system
    password: "SecurePassword"
    oracle:
      service: ORCL
      port: 1521
      tablespace: USERS
      tempTablespace: TEMP
```

## Global Test Parameters

Set defaults that apply to all targets (can be overridden per target):

### Connection Settings

```yaml
hammerdb:
  connection:
    tcp: true
    port: 1433
    authentication: sql
    encrypt_connection: false
    trust_server_cert: false
```

### TPC-C (OLTP) Settings

```yaml
hammerdb:
  tprocc:
    warehouses: 100           # Number of warehouses (scale factor)
    build_num_vu: 16          # Virtual users for BUILD phase
    load_num_vu: 8            # Virtual users for LOAD phase
    use_bcp: false            # Use bulk copy for faster loading
    driver: timed             # Driver type: timed or test
    rampup: 5                 # Ramp-up time in minutes
    duration: 10              # Test duration in minutes
    total_iterations: 10000000
    allwarehouse: true        # Use all warehouses
    checkpoint: true          # Checkpoint before test
    timeprofile: false        # Enable time profiling
```

### TPC-H (Analytics) Settings

```yaml
hammerdb:
  tproch:
    scaleFactor: 100          # Scale factor (GB of data)
    buildThreads: 8           # Threads for building data
    build_num_vu: 8           # Virtual users for BUILD
    load_num_vu: 4            # Virtual users for LOAD
    totalQuerysets: 1         # Number of query sets to run
    maxdop: 8                 # Max degree of parallelism
    useClusteredColumnstore: false  # Use columnstore indexes (SQL Server)
```

### Oracle-Specific Settings

```yaml
hammerdb:
  oracle:
    service: ORCL
    port: 1521
    tablespace: USERS
    tempTablespace: TEMP
    tproccUser: tpcc
    tprochUser: tpch
    degreeOfParallel: 4
```

## Resource Requirements

Configure resources per worker pod:

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

**Sizing guidelines:**

| Test Size | Warehouses | Memory | CPU |
|-----------|------------|--------|-----|
| Small | 10-50 | 2Gi | 1 |
| Medium | 100 | 4Gi | 2 |
| Large | 200+ | 8Gi | 4 |

## Pure Storage Metrics (Optional)

Enable Pure Storage FlashArray performance monitoring:

```yaml
pureStorage:
  enabled: true
  host: "10.21.158.110"
  apiToken: "your-api-token"
  pollInterval: 5            # Seconds between samples
  verifySSL: false           # Verify SSL certificates
  apiVersion: "2.4"          # Pure Storage API version
```

## Image Configuration

```yaml
global:
  image:
    repository: sillidata/hammerdb-scale
    tag: latest
    pullPolicy: IfNotPresent
```

For Oracle, use your custom-built image:

```yaml
global:
  image:
    repository: myregistry/hammerdb-scale-oracle
    tag: latest
```

## Complete values.yaml Reference

See [values.yaml](../values.yaml) for the complete configuration file with all options.

See [values-examples.yaml](../values-examples.yaml) for example configurations for different scenarios.
