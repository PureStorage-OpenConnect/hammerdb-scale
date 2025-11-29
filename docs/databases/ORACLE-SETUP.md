# Oracle Database Support Setup

## Overview

The hammerdb-scale solution supports Oracle database benchmarking for both TPC-C (OLTP) and TPC-H (Analytics) workloads. This document provides setup instructions, configuration examples, and important considerations for running Oracle benchmarks.

## License Notice

**IMPORTANT:** Oracle Instant Client is required for Oracle database support.

Oracle Instant Client is proprietary software provided by Oracle Corporation under their license terms. By downloading and using Oracle Instant Client, you agree to Oracle's license terms:

https://www.oracle.com/downloads/licenses/instant-client-lic.html

**This repository does not include Oracle Instant Client binaries.** You must download and install them separately as described below.

## Installation

### Why a Separate Image?

Oracle Instant Client is proprietary software that Oracle does not permit to be redistributed in public Docker images. The base `sillidata/hammerdb-scale` image cannot include Oracle binaries.

**Solution:** You build the Oracle image yourself. When you run `docker build`, the Oracle client is downloaded directly from Oracle's servers to your machine, satisfying their licensing requirements.

### Building the Oracle-Enabled Image (One-Time Setup)

```bash
# Clone the repository
git clone https://github.com/sillidata/hammerdb-scale
cd hammerdb-scale

# Build the Oracle image (downloads Oracle Instant Client from oracle.com)
docker build -f Dockerfile.oracle -t myregistry/hammerdb-scale-oracle:latest .

# Push to your private registry
docker push myregistry/hammerdb-scale-oracle:latest
```

**That's it.** You only need to do this once. The image extends the public `sillidata/hammerdb-scale:latest` image and adds Oracle Instant Client.

### What Happens If You Forget?

If you try to run Oracle benchmarks using the base image (without Oracle client), you'll see a helpful error:

```
============================================================
ERROR: Oracle Instant Client not found!
============================================================

You are trying to run an Oracle benchmark but the Oracle
client libraries are not installed in this container.

TO FIX: Build the Oracle extension image:

  1. Clone the repository:
     git clone https://github.com/sillidata/hammerdb-scale

  2. Build the Oracle image:
     docker build -f Dockerfile.oracle -t myregistry/hammerdb-scale-oracle:latest .

  3. Push to your registry:
     docker push myregistry/hammerdb-scale-oracle:latest

  4. Update your values.yaml:
     global:
       image:
         repository: myregistry/hammerdb-scale-oracle

============================================================
```

### What Gets Installed

The Oracle image includes:
- Oracle Instant Client 21.11 (Basic Package)
- Oracle SQL*Plus
- HammerDB 5.0 with Oracle support
- All Oracle-specific TCL scripts for TPC-C and TPC-H

## Oracle Database Prerequisites

### 1. Database Setup

Before running benchmarks, ensure your Oracle database is properly configured:

```sql
-- Create tablespaces for benchmark data
CREATE TABLESPACE tpcc_data
  DATAFILE '/u01/oradata/tpcc_data01.dbf' SIZE 10G AUTOEXTEND ON;

CREATE TABLESPACE tpch_data
  DATAFILE '/u01/oradata/tpch_data01.dbf' SIZE 50G AUTOEXTEND ON;

-- Create schema users
CREATE USER tpcc IDENTIFIED BY <password>
  DEFAULT TABLESPACE tpcc_data
  TEMPORARY TABLESPACE temp
  QUOTA UNLIMITED ON tpcc_data;

CREATE USER tpch IDENTIFIED BY <password>
  DEFAULT TABLESPACE tpch_data
  TEMPORARY TABLESPACE temp
  QUOTA UNLIMITED ON tpch_data;

-- Grant necessary privileges
GRANT CONNECT, RESOURCE TO tpcc;
GRANT CONNECT, RESOURCE TO tpch;
GRANT CREATE VIEW TO tpcc;
GRANT CREATE VIEW TO tpch;

-- Optional: Grant system privileges for performance monitoring
GRANT SELECT ON v_$database TO tpcc;
GRANT SELECT ON v_$database TO tpch;
```

### 2. Network Configuration

Ensure the Oracle database is accessible from your Kubernetes cluster:

- **Listener**: Verify the Oracle listener is running and accepting connections
- **Firewall**: Open port 1521 (or your custom port) for incoming connections
- **TNS Names**: Confirm service name or SID is properly configured

Test connectivity from the Kubernetes cluster:

```bash
# Test with sqlplus
sqlplus system/<password>@//<host>:<port>/<service_name>

# Or with tnsping
tnsping <service_name>
```

## Configuration

### values.yaml Configuration

The hammerdb-scale solution uses a **defaults + overrides** pattern that makes Oracle configuration as simple as SQL Server.

#### Simple Configuration (Recommended)

Most users only need to specify host, username, and password. All Oracle-specific settings use sensible defaults:

```yaml
testRun:
  id: "o001"
  phase: "build"
  benchmark: "tprocc"

# Database defaults (configured once, used by all targets)
databases:
  oracle:
    driver: oracle
    port: 1521
    service: "ORCL"                    # Default service name
    tablespace: "TPCC"                 # Default data tablespace
    tempTablespace: "TEMP"             # Default temp tablespace
    tprocc:
      user: "tpcc"                     # Default TPC-C user
    tproch:
      user: "tpch"                     # Default TPC-H user
      degreeOfParallel: 8              # Default parallelism

# Targets - simple configuration using defaults
targets:
  - name: oracle-db1
    type: oracle
    host: "oracle.example.com"
    username: system
    password: "YourPassword"
    # All other settings use defaults from databases.oracle

  - name: oracle-db2
    type: oracle
    host: "oracle2.example.com"
    username: system
    password: "YourPassword"
    # Also uses defaults

# Test parameters
hammerdb:
  tprocc:
    warehouses: 100
    build_num_vu: 8
    load_num_vu: 4
    driver: timed
    rampup: 2
    duration: 10

# Image configuration
global:
  image:
    repository: <your-registry>/hammerdb-scale-oracle
    tag: latest
    pullPolicy: Always
```

#### Advanced Configuration (Per-Target Overrides)

Override defaults on a per-target basis when needed:

```yaml
databases:
  oracle:
    service: "ORCL"           # Default for most
    tablespace: "USERS"       # Default tablespace

targets:
  # Uses all defaults
  - name: oracle-dev
    type: oracle
    host: "dev-oracle.local"
    username: system
    password: "DevPass"

  # Overrides service and tablespace
  - name: oracle-prod
    type: oracle
    host: "prod-oracle.local"
    username: system
    password: "ProdPass"
    oracleService: "PROD"              # Override: production service
    oracleTablespace: "TPCC_PROD"      # Override: production tablespace

  # Uses SID instead of service
  - name: oracle-legacy
    type: oracle
    host: "legacy-oracle.local"
    username: system
    password: "LegacyPass"
    oracleSid: "LEGACY"                # Override: use SID instead
    tprocc:
      user: "tpcc_legacy"              # Override: different user
```

**Key Benefits:**
- ✅ **Simple by default** - Just like SQL Server configuration
- ✅ **Flexible when needed** - Override any setting per-target
- ✅ **DRY principle** - Define once in defaults, use everywhere
- ✅ **Self-documenting** - Defaults section shows all options

### Connection Methods

Oracle supports two connection methods:

#### 1. Service Name (Recommended - Uses Default)

```yaml
# Set default service in databases.oracle
databases:
  oracle:
    service: "ORCL"

# Targets automatically use default
targets:
  - name: oracle-db1
    type: oracle
    host: "oracle.example.com"
    # Uses service "ORCL" from defaults
```

This connects using: `oracle.example.com:1521/ORCL`

#### 2. Service Name (Per-Target Override)

```yaml
targets:
  - name: oracle-db1
    type: oracle
    host: "oracle.example.com"
    oracleService: "PROD"    # Override default service
```

#### 3. SID (Legacy)

```yaml
targets:
  - name: oracle-db1
    type: oracle
    host: "oracle.example.com"
    oracleSid: "LEGACY"      # Use SID instead of service
```

**Note:** Use either `oracleService` OR `oracleSid`, not both.

## Running Benchmarks

### TPC-C (OLTP Workload)

#### Build Phase (Create Schema)

```bash
# Update values.yaml
testRun:
  phase: "build"
  benchmark: "tprocc"

# Deploy
helm upgrade --install hammerdb-tpcc . -f values.yaml

# Monitor progress
kubectl logs -f job/hammerdb-scale-test-build-oracle-db1-o001
```

Build creates:
- 9 tables (warehouse, district, customer, orders, etc.)
- Indexes and constraints
- Data population based on warehouse count

#### Load Phase (Run Test)

```bash
# Update values.yaml
testRun:
  phase: "load"
  benchmark: "tprocc"

# Deploy
helm upgrade --install hammerdb-tpcc . -f values.yaml

# Monitor progress
kubectl logs -f job/hammerdb-scale-test-load-oracle-db1-o001

# Get results
./aggregate-results.sh
```

Key metrics collected:
- **TPM**: Transactions Per Minute
- **NOPM**: New Orders Per Minute (primary TPC-C metric)
- Response times per transaction type

### TPC-H (Analytics Workload)

#### Build Phase (Create Schema)

```bash
# Update values.yaml
testRun:
  phase: "build"
  benchmark: "tproch"
hammerdb:
  tproch:
    scaleFactor: 10          # 10GB database

# Deploy
helm upgrade --install hammerdb-tpch . -f values.yaml

# Monitor
kubectl logs -f job/hammerdb-scale-test-build-oracle-db1-o001
```

Build creates:
- 8 tables (lineitem, orders, customer, part, etc.)
- Indexes and foreign keys
- Data generation based on scale factor

#### Load Phase (Run Queries)

```bash
# Update values.yaml
testRun:
  phase: "load"
  benchmark: "tproch"

# Deploy
helm upgrade --install hammerdb-tpch . -f values.yaml

# Monitor
kubectl logs -f job/hammerdb-scale-test-load-oracle-db1-o001

# Get results
./aggregate-results.sh
```

Key metrics collected:
- **QphH**: Queries per Hour at Scale Factor (primary TPC-H metric)
- Individual query execution times (Q1-Q22)
- Total elapsed time

## Oracle-Specific Configuration

### Tablespaces

Oracle uses tablespaces for storage management:

```yaml
targets:
  - name: oracle-db1
    oracleTablespace: "USERS"        # Main data tablespace
    oracleTempTablespace: "TEMP"     # Temporary operations
```

Best practices:
- Use separate tablespaces for TPC-C and TPC-H
- Consider separate tablespace for Order Line table (TPC-C)
- Ensure adequate space for your scale factor

### Parallelism

Oracle's parallel query execution:

```yaml
tproch:
  degreeOfParallel: 8    # Number of parallel processes per query
```

Guidelines:
- Power Test (1 VU): Use high DOP (8-16)
- Throughput Test (4+ VU): Use lower DOP (2-4)
- Match DOP to CPU core count
- Monitor system resources to avoid over-parallelization

### Performance Tuning

Recommended Oracle parameters:

```sql
-- Memory settings
ALTER SYSTEM SET sga_target = 8G SCOPE=BOTH;
ALTER SYSTEM SET pga_aggregate_target = 4G SCOPE=BOTH;

-- Parallelism
ALTER SYSTEM SET parallel_max_servers = 32 SCOPE=BOTH;
ALTER SYSTEM SET parallel_degree_policy = MANUAL SCOPE=BOTH;

-- Optimizer
ALTER SYSTEM SET optimizer_mode = ALL_ROWS SCOPE=BOTH;
ALTER SYSTEM SET optimizer_index_cost_adj = 100 SCOPE=BOTH;

-- Statistics
EXEC DBMS_STATS.SET_GLOBAL_PREFS('ESTIMATE_PERCENT', 'AUTO_SAMPLE_SIZE');
```

## Troubleshooting

### Connection Issues

**Problem:** "ORA-12154: TNS:could not resolve the connect identifier"

**Solution:**
- Verify `oracleService` or `oracleSid` is correct
- Check Oracle listener status: `lsnrctl status`
- Test connection: `sqlplus system/<pass>@<host>:<port>/<service>`

### Schema Build Failures

**Problem:** "ORA-01950: no privileges on tablespace"

**Solution:**
```sql
ALTER USER tpcc QUOTA UNLIMITED ON tpcc_data;
ALTER USER tpch QUOTA UNLIMITED ON tpch_data;
```

**Problem:** "ORA-01031: insufficient privileges"

**Solution:**
```sql
GRANT CONNECT, RESOURCE TO tpcc;
GRANT CREATE VIEW TO tpcc;
```

### Performance Issues

**Problem:** Slow query execution

**Solutions:**
1. Check parallelism settings
2. Gather statistics: `EXEC DBMS_STATS.GATHER_SCHEMA_STATS('TPCH');`
3. Review execution plans: `SET AUTOTRACE ON`
4. Monitor system resources: `SELECT * FROM v$sysmetric;`

### Memory Errors

**Problem:** "ORA-04031: unable to allocate memory"

**Solution:**
```sql
ALTER SYSTEM SET sga_target = 16G SCOPE=BOTH;
ALTER SYSTEM SET pga_aggregate_target = 8G SCOPE=BOTH;
```

## Comparison with SQL Server

Key differences when migrating from SQL Server:

| Feature | SQL Server | Oracle |
|---------|-----------|--------|
| Schema | Database-based | User-based |
| Connection | host:port/database | host:port/service |
| Parallelism | MAXDOP | Degree of Parallel |
| Storage | Filegroups | Tablespaces |
| Temp Storage | tempdb | TEMP tablespace |
| Fast Load | BCP | SQL*Loader (not used) |

## Best Practices

1. **Start Small**: Test with small scale factors first
   - TPC-C: 10-100 warehouses
   - TPC-H: SF=1 or SF=10

2. **Monitor Resources**: Watch CPU, memory, and I/O during tests
   ```sql
   SELECT * FROM v$sysmetric WHERE metric_name LIKE '%CPU%';
   ```

3. **Gather Statistics**: Always gather stats after schema build
   ```sql
   EXEC DBMS_STATS.GATHER_SCHEMA_STATS('TPCC');
   EXEC DBMS_STATS.GATHER_SCHEMA_STATS('TPCH');
   ```

4. **Use Appropriate Hardware**: Oracle Enterprise Edition recommended for:
   - Parallelism features
   - Partitioning (for large warehouses)
   - Advanced compression

5. **Network Latency**: Keep benchmarking pods close to database
   - Same data center
   - Low-latency network
   - Consider Oracle RAC for multi-node testing

## Support and Resources

- HammerDB Oracle Documentation: https://www.hammerdb.com/docs/
- Oracle Database Documentation: https://docs.oracle.com/en/database/
- hammerdb-scale Issues: https://github.com/<your-repo>/hammerdb-scale/issues

## Known Limitations

1. **Oracle SE**: Some features require Enterprise Edition
   - Parallel query execution
   - Table partitioning
   - Advanced compression

2. **TimesTen**: TimesTen compatibility mode not implemented

3. **Hash Clusters**: Disabled by default (can enable in TCL scripts)

4. **Connection Pooling**: XML-based connection pooling not configured

## Next Steps

After successful Oracle setup:

1. Run baseline tests with default configuration
2. Tune Oracle parameters for your workload
3. Scale up to production-size tests
4. Compare results across different storage platforms
5. Integrate with Pure Storage metrics collection (optional)

For questions or issues, please open a GitHub issue or consult the main README.
