# Adding New Database Types

This guide explains how to extend HammerDB Scale to support additional database types beyond SQL Server.

## Currently Supported
- **SQL Server** (fully implemented)
- **Oracle Database** (fully implemented)

## Planned Support
- **PostgreSQL** (structure ready, implementation needed)
- **MySQL/MariaDB** (structure ready, implementation needed)

## Architecture Overview

The project is designed with modularity in mind:

```
Database Type Definition (values.yaml)
         ↓
Database-Specific ConfigMap (scripts)
         ↓
Worker Job (conditional env vars)
         ↓
Entrypoint (script selection)
         ↓
HammerDB TCL Scripts
```

## Steps to Add a New Database Type

### 1. Update Dockerfile

Add the required database drivers and client tools.

**Location**: `dockerfile`

**Example for PostgreSQL**:
```dockerfile
# Add PostgreSQL client libraries
RUN apt-get update && \
    apt-get install -y postgresql-client libpq-dev && \
    apt-get clean
```

**Example for Oracle**:
```dockerfile
# Add Oracle Instant Client
RUN wget https://download.oracle.com/otn_software/linux/instantclient/instantclient-basic-linux.x64-21.1.0.0.0.zip && \
    unzip instantclient-basic-linux.x64-21.1.0.0.0.zip -d /opt/ && \
    echo '/opt/instantclient_21_1' > /etc/ld.so.conf.d/oracle.conf && \
    ldconfig
```

### 2. Create Database-Specific TCL Scripts

Create a new directory and add HammerDB scripts for your database.

**Location**: `scripts/<database-type>/`

**Structure**:
```
scripts/
├── mssql/                          # SQL Server (existing)
│   ├── build_schema_tprocc.tcl
│   ├── build_schema_tproch.tcl
│   ├── load_test_tprocc.tcl
│   └── load_test_tproch.tcl
├── postgres/                       # PostgreSQL (add these)
│   ├── build_schema_tprocc.tcl
│   ├── build_schema_tproch.tcl
│   ├── load_test_tprocc.tcl
│   └── load_test_tproch.tcl
└── oracle/                         # Oracle (add these)
    ├── build_schema_tprocc.tcl
    ├── build_schema_tproch.tcl
    ├── load_test_tprocc.tcl
    └── load_test_tproch.tcl
```

**Example PostgreSQL TPC-C Build Script**:
```tcl
#!/bin/tclsh
set username $::env(USERNAME)
set password $::env(PASSWORD)
set pg_host $::env(HOST)

set tprocc_database_name $::env(TPROCC_DATABASE_NAME)
set warehouses $::env(WAREHOUSES)

# Initialize HammerDB
puts "SETTING UP TPROC-C SCHEMA BUILD FOR POSTGRESQL"
dbset db pg

# Set benchmark to TPC-C
dbset bm TPC-C

# Configure connection
diset connection pg_host $pg_host
diset connection pg_user $username
diset connection pg_pass $password

# Configure TPC-C Schema Build
diset tpcc pg_count_ware $warehouses
diset tpcc pg_dbase $tprocc_database_name

# Load and build
loadscript
buildschema

puts "TPROC-C SCHEMA BUILD COMPLETE"
```

### 3. Create Database-Specific ConfigMap Template

**Location**: `templates/configmap-<database-type>.yaml`

**Example for PostgreSQL**:
```yaml
# templates/configmap-postgres.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "hammerdb-scale-test.fullname" . }}-scripts-postgres
  labels:
    {{- include "hammerdb-scale-test.labels" . | nindent 4 }}
    hammerdb.io/database-type: postgres
data:
  {{- range $path, $_ := .Files.Glob "scripts/postgres/*.tcl" }}
  {{ base $path }}: |-
{{ $.Files.Get $path | indent 4 }}
  {{- end }}
```

### 4. Update Helper Functions

Add database driver mapping to the helpers template.

**Location**: `templates/_helpers.tpl`

**Find the `hammerdb-scale-test.dbDriver` function and add your database**:
```tpl
{{- define "hammerdb-scale-test.dbDriver" -}}
{{- $dbType := . -}}
{{- if eq $dbType "mssql" -}}
mssqls
{{- else if eq $dbType "postgres" -}}
pg
{{- else if eq $dbType "oracle" -}}
oracle
{{- else if eq $dbType "mysql" -}}
mysql
{{- else -}}
{{- fail (printf "Unsupported database type: %s" $dbType) -}}
{{- end -}}
{{- end }}
```

### 5. Update Worker Job Template

Add database-specific environment variables.

**Location**: `templates/job-hammerdb-worker.yaml`

**Add a new conditional block after the existing `{{- if eq .type "mssql" }}` block**:

```yaml
{{- if eq .type "postgres" }}
# PostgreSQL specific settings
- name: PG_HOST
  value: {{ .host | quote }}
- name: PG_PORT
  value: "5432"
{{- if .pgSslMode }}
- name: PG_SSLMODE
  value: {{ .pgSslMode | quote }}
{{- end }}
{{- end }}
```

### 6. Update Entrypoint Script

Add script selection logic for the new database type.

**Location**: `entrypoint.sh`

**Find the comment `# EXTENSION POINT: Add PostgreSQL script selection here` and uncomment/add**:

```bash
elif [[ "$DATABASE_TYPE" == "postgres" ]]; then
    if [[ "$BENCHMARK" == "tprocc" ]]; then
        case "$RUN_MODE" in
            build)
                SCRIPT_NAME="build_schema_tprocc.tcl"
                ;;
            load)
                SCRIPT_NAME="load_test_tprocc.tcl"
                ;;
            *)
                log "ERROR: Unknown RUN_MODE: '$RUN_MODE'. Supported: build, load"
                exit 1
                ;;
        esac
    elif [[ "$BENCHMARK" == "tproch" ]]; then
        case "$RUN_MODE" in
            build)
                SCRIPT_NAME="build_schema_tproch.tcl"
                ;;
            load)
                SCRIPT_NAME="load_test_tproch.tcl"
                ;;
            *)
                log "ERROR: Unknown RUN_MODE: '$RUN_MODE'. Supported: build, load"
                exit 1
                ;;
        esac
    fi
```

Also update the validation at the top of the script:

```bash
case "$DATABASE_TYPE" in
    mssql)
        log "Database: Microsoft SQL Server"
        ;;
    postgres)
        log "Database: PostgreSQL"
        # Remove the "not yet implemented" error
        ;;
    ...
esac
```

### 7. Update values.yaml

Add database-specific configuration section.

**Location**: `values.yaml`

**Uncomment and configure**:
```yaml
databases:
  mssql:
    driver: mssqls
    tcp: true
    authentication: sql
  
  postgres:
    driver: pg
    port: 5432
    sslmode: prefer
  
  # Add more as needed
```

### 8. Update Result Parsing in aggregate-results.sh

Add database-specific result parsing patterns to handle your database's output format.

**Location**: `aggregate-results.sh`

**Find the database-specific parsing section (around line 285) and add your database case:**

```bash
case "${DATABASE_TYPE}" in
    mssql)
        # SQL Server patterns...
        ;;

    postgres)
        # PostgreSQL specific patterns
        # TPC-C: Look for PostgreSQL TPM/NOPM patterns
        TPM_VALUE=$(grep -oP '(?:PostgreSQL\s+)?TPM:\s*(\d+)' "${LOG_FILE}" | grep -oP '\d+' | tail -1 || echo "0")
        NOPM_VALUE=$(grep -oP 'NOPM:\s*(\d+)' "${LOG_FILE}" | grep -oP '\d+' | tail -1 || echo "0")

        # TPC-H: QphH pattern
        QPHH_VALUE=$(grep -oP 'QphH:\s+([0-9]+\.?[0-9]*)' "${LOG_FILE}" | grep -oP ':\s+\K[0-9]+\.?[0-9]*' | tail -1 || echo "0")
        ;;

    # Add your database here
esac
```

**Important Notes:**
- The script detects database type from logs: `grep "Database Type:" "${LOG_FILE}"`
- Ensure your TCL scripts output results in a parseable format
- Test your patterns with actual HammerDB output for your database
- The generic fallback will attempt basic parsing if your case is missing

### 9. Add Example Configuration

Update `values-examples.yaml` with PostgreSQL examples.

**Example**:
```yaml
targets:
  - name: postgres-db1
    type: postgres
    host: "postgres.example.com"
    username: hammerdb
    password: "SecurePass!"
    pgSslMode: require  # Optional PostgreSQL-specific setting

    tprocc:
      databaseName: tpcc
      warehouses: 100
      virtualUsers: 16
      # PostgreSQL doesn't support some SQL Server options
      # like clustered columnstore
```

## Testing Your Implementation

### 1. Build the Docker Image
```bash
docker build -t hammerdb:latest .
```

### 2. Test Locally with Docker
```bash
docker run -it \
  -e DATABASE_TYPE=postgres \
  -e BENCHMARK=tprocc \
  -e RUN_MODE=build \
  -e USERNAME=hammerdb \
  -e PASSWORD=test \
  -e HOST=postgres.example.com \
  hammerdb:latest
```

### 3. Deploy to Kubernetes
```bash
# Update values.yaml with PostgreSQL target
helm install test-postgres . -n hammerdb

# Check logs
kubectl logs -n hammerdb -l hammerdb.io/database-type=postgres
```

## Database-Specific Considerations

### PostgreSQL
- **Connection**: Uses libpq connection strings
- **Authentication**: Supports password, md5, scram-sha-256
- **SSL**: May require sslmode configuration
- **Port**: Default 5432
- **Driver**: HammerDB uses `pg` driver

### Oracle
- **Connection**: Requires Oracle Instant Client
- **Authentication**: Supports password, Kerberos, wallet
- **Connection String**: Uses service name or SID
- **Port**: Default 1521
- **Driver**: HammerDB uses `oracle` driver
- **Note**: May require `ORACLE_HOME` and `LD_LIBRARY_PATH`

### MySQL/MariaDB
- **Connection**: Uses MySQL client libraries
- **Authentication**: Supports password, socket
- **SSL**: May require SSL configuration
- **Port**: Default 3306
- **Driver**: HammerDB uses `mysql` driver

## Checklist for Adding a Database

- [ ] Update `dockerfile` with required client libraries
- [ ] Create `scripts/<db-type>/` directory with TCL scripts
- [ ] Create `templates/configmap-<db-type>.yaml`
- [ ] Update `templates/_helpers.tpl` with driver mapping
- [ ] Update `templates/job-hammerdb-worker.yaml` with env vars
- [ ] Update `entrypoint.sh` with script selection logic
- [ ] **Update `aggregate-results.sh` with database-specific result parsing patterns**
- [ ] Update `values.yaml` with database configuration
- [ ] Add examples to `values-examples.yaml`
- [ ] Update documentation
- [ ] Test with local Docker run
- [ ] Test with Kubernetes deployment
- [ ] Update `README.md` with new database support

## Getting Help

- HammerDB Documentation: https://www.hammerdb.com/documentation.html
- Database-specific forums and communities
- Open an issue in this repository

## Contributing

When adding support for a new database:
1. Follow the structure outlined above
2. Include comprehensive TCL scripts
3. Add examples and documentation
4. Test thoroughly
5. Submit a pull request with:
   - All necessary files
   - Documentation updates
   - Example configurations
   - Test results
