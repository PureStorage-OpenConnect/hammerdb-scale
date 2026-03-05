#!/bin/bash
# Modular HammerDB Entrypoint for Kubernetes
# Supports: SQL Server, PostgreSQL (future), Oracle (future), MySQL (future)

# Force unbuffered output
export PYTHONUNBUFFERED=1
stty -onlcr 2>/dev/null || true

# Log function for better output
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

# Set TMPDIR if not already set
export TMPDIR="${TMPDIR:-/tmp}"

# Ensure all required environment variables are set
if [ -z "$USERNAME" ] || [ -z "$PASSWORD" ] || [ -z "$HOST" ] || [ -z "$BENCHMARK" ]; then
  log "ERROR: Environment variables USERNAME, PASSWORD, HOST and BENCHMARK must be set."
  exit 1
fi

# Check if RUN_MODE is set
if [[ -z "$RUN_MODE" ]]; then
    log "ERROR: RUN_MODE is not set."
    exit 1
fi

# Check if DATABASE_TYPE is set
if [[ -z "$DATABASE_TYPE" ]]; then
    log "ERROR: DATABASE_TYPE is not set."
    exit 1
fi

# Check if TARGET_NAME is set
if [[ -z "$TARGET_NAME" ]]; then
    log "ERROR: TARGET_NAME is not set."
    exit 1
fi

log "Starting HammerDB for target: $TARGET_NAME"
log "Database Type: $DATABASE_TYPE"
log "Benchmark: $BENCHMARK"
log "Mode: $RUN_MODE"

# Validate database type
case "$DATABASE_TYPE" in
    mssql)
        log "Database: Microsoft SQL Server"
        ;;
    postgres)
        log "Database: PostgreSQL"
        log "ERROR: PostgreSQL support not yet implemented"
        exit 1
        ;;
    oracle)
        log "Database: Oracle"
        # Check if Oracle Instant Client is installed
        if [ ! -d "/opt/oracle/instantclient_21_11" ]; then
            log ""
            log "============================================================"
            log "ERROR: Oracle Instant Client not found!"
            log "============================================================"
            log ""
            log "You are trying to run an Oracle benchmark but the Oracle"
            log "client libraries are not installed in this container."
            log ""
            log "Oracle Instant Client cannot be included in the public"
            log "hammerdb-scale image due to Oracle's licensing restrictions."
            log ""
            log "TO FIX: Build the Oracle extension image:"
            log ""
            log "  1. Clone the repository:"
            log "     git clone https://github.com/sillidata/hammerdb-scale"
            log ""
            log "  2. Build the Oracle image (downloads Oracle client from Oracle):"
            log "     docker build -f Dockerfile.oracle -t myregistry/hammerdb-scale-oracle:latest ."
            log ""
            log "  3. Push to your registry:"
            log "     docker push myregistry/hammerdb-scale-oracle:latest"
            log ""
            log "  4. Update your values.yaml:"
            log "     global:"
            log "       image:"
            log "         repository: myregistry/hammerdb-scale-oracle"
            log ""
            log "For detailed instructions, see ORACLE-SETUP.md"
            log "============================================================"
            log ""
            exit 1
        fi
        ;;
    mysql)
        log "Database: MySQL/MariaDB"
        log "ERROR: MySQL support not yet implemented"
        exit 1
        ;;
    *)
        log "ERROR: Unsupported DATABASE_TYPE: $DATABASE_TYPE"
        log "Supported types: mssql, postgres, oracle, mysql"
        exit 1
        ;;
esac

# Set SCRIPT_NAME based on DATABASE_TYPE, BENCHMARK, and RUN_MODE
if [[ "$DATABASE_TYPE" == "mssql" ]]; then
    if [[ "$BENCHMARK" == "tprocc" ]]; then
        case "$RUN_MODE" in
            build)
                SCRIPT_NAME="build_schema_tprocc.tcl"
                ;;
            load)
                SCRIPT_NAME="load_test_tprocc.tcl"
                ;;
            parse)
                SCRIPT_NAME="generic_tprocc_result.tcl"
                ;;
            *)
                log "ERROR: Unknown RUN_MODE: '$RUN_MODE' for benchmark '$BENCHMARK'"
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
            parse)
                SCRIPT_NAME="parse_output_tproch.tcl"
                ;;
            *)
                log "ERROR: Unknown RUN_MODE: '$RUN_MODE' for benchmark '$BENCHMARK'"
                exit 1
                ;;
        esac
    else
        log "ERROR: Unknown BENCHMARK: '$BENCHMARK'. Supported: tprocc, tproch"
        exit 1
    fi
elif [[ "$DATABASE_TYPE" == "oracle" ]]; then
    if [[ "$BENCHMARK" == "tprocc" ]]; then
        case "$RUN_MODE" in
            build)
                SCRIPT_NAME="build_schema_tprocc.tcl"
                ;;
            load)
                SCRIPT_NAME="load_test_tprocc.tcl"
                ;;
            parse)
                SCRIPT_NAME="parse_output_tprocc.tcl"
                ;;
            *)
                log "ERROR: Unknown RUN_MODE: '$RUN_MODE' for benchmark '$BENCHMARK'"
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
            parse)
                SCRIPT_NAME="parse_output_tproch.tcl"
                ;;
            *)
                log "ERROR: Unknown RUN_MODE: '$RUN_MODE' for benchmark '$BENCHMARK'"
                exit 1
                ;;
        esac
    else
        log "ERROR: Unknown BENCHMARK: '$BENCHMARK'. Supported: tprocc, tproch"
        exit 1
    fi
# EXTENSION POINT: Add PostgreSQL script selection here
# elif [[ "$DATABASE_TYPE" == "postgres" ]]; then
#     if [[ "$BENCHMARK" == "tprocc" ]]; then
#         case "$RUN_MODE" in
#             build)
#                 SCRIPT_NAME="build_schema_tprocc_pg.tcl"
#                 ;;
#             load)
#                 SCRIPT_NAME="load_test_tprocc_pg.tcl"
#                 ;;
#             parse)
#                 SCRIPT_NAME="parse_output_tprocc_pg.tcl"
#                 ;;
#         esac
#     fi

# EXTENSION POINT: Add Oracle script selection here
# elif [[ "$DATABASE_TYPE" == "oracle" ]]; then
#     ...

# EXTENSION POINT: Add MySQL script selection here
# elif [[ "$DATABASE_TYPE" == "mysql" ]]; then
#     ...

else
    log "ERROR: Script selection not implemented for DATABASE_TYPE: $DATABASE_TYPE"
    exit 1
fi

# Check if the script exists
if [ ! -f "/opt/HammerDB-5.0/scripts/$SCRIPT_NAME" ]; then
  log "ERROR: Script '/opt/HammerDB-5.0/scripts/$SCRIPT_NAME' not found."
  exit 1
fi

log "Executing script: $SCRIPT_NAME"

# Create a timestamp for this run
START_TIME=$(date +'%Y-%m-%d %H:%M:%S')
START_EPOCH=$(date +%s)

# Start Pure Storage metrics collection if enabled (only for load phase)
PURE_PID=""
if [[ "$RUN_MODE" == "load" ]] && [[ "${PURE_ENABLED:-false}" == "true" ]]; then

    # Check if this pod should collect metrics (only first target to avoid duplicate API calls)
    if [[ "${PURE_COLLECT_METRICS:-false}" == "true" ]]; then
        log "Pure Storage metrics collection enabled for this pod (target index: ${TARGET_INDEX:-unknown})"
        log "This pod is designated as the Pure Storage metrics collector"

        # Calculate collection duration based on benchmark type
        if [[ "$BENCHMARK" == "tprocc" ]]; then
            # TPC-C: DURATION and RAMPUP are in MINUTES for HammerDB, convert to seconds
            DURATION_SECONDS=$((${DURATION:-1} * 60))
            RAMPUP_SECONDS=$((${RAMPUP:-0} * 60))
            COLLECTION_DURATION=$((${DURATION_SECONDS} + ${RAMPUP_SECONDS}))
            log "TPC-C benchmark: Collection duration = ${DURATION}min (${DURATION_SECONDS}s) + ${RAMPUP}min (${RAMPUP_SECONDS}s) = ${COLLECTION_DURATION}s"
        else
            # TPC-H: Use PURE_DURATION override if set, otherwise estimate based on scale factor
            # Formula based on empirical data: 600s base + (querysets × scale_factor × 3.3s) + 20% buffer
            # For SF=1000, 1 queryset: 600 + (1 × 1000 × 3.3) × 1.2 = ~4,680 seconds (78 minutes)
            if [ -n "$PURE_DURATION" ]; then
                COLLECTION_DURATION=$PURE_DURATION
                log "TPC-H benchmark: Using PURE_DURATION override = ${COLLECTION_DURATION}s"
            else
                QUERYSETS=${TPROCH_TOTAL_QUERYSETS:-1}
                SCALE_FACTOR=${TPROCH_SCALE_FACTOR:-100}

                # Calculate base estimate: 600s + (querysets × SF × 3.3)
                BASE_ESTIMATE=$((600 + (QUERYSETS * SCALE_FACTOR * 33 / 10)))

                # Add 20% buffer for storage variance and safety
                COLLECTION_DURATION=$((BASE_ESTIMATE * 120 / 100))

                log "TPC-H benchmark: Auto-calculated collection duration"
                log "  Querysets: ${QUERYSETS}"
                log "  Scale Factor: ${SCALE_FACTOR}"
                log "  Base Estimate: ${BASE_ESTIMATE}s"
                log "  With 20% buffer: ${COLLECTION_DURATION}s (~$((COLLECTION_DURATION / 60)) minutes)"
            fi
        fi

        # Check if Python script exists
        if [ -f "/opt/HammerDB-5.0/scripts/collect_pure_metrics.py" ]; then
            log "Starting Pure Storage metrics collector"
            log "  Array: ${PURE_HOST}"
            log "  Duration: ${COLLECTION_DURATION}s"
            log "  Poll Interval: ${PURE_INTERVAL:-5}s"
            log "  API Version: ${PURE_API_VERSION:-2.4}"
            log "  Output: ${PURE_OUTPUT:-/tmp/pure_metrics.json}"
            log "  Log: ${TMPDIR}/pure_metrics.log"

            # Determine which Python interpreter to use
            if command -v python3 &> /dev/null; then
                PYTHON_CMD="python3"
            elif command -v python &> /dev/null; then
                PYTHON_CMD="python"
            else
                log "ERROR: No Python interpreter found (tried python3, python)"
                PYTHON_CMD=""
            fi

            if [ -n "$PYTHON_CMD" ]; then
                log "Using Python interpreter: $PYTHON_CMD"

                # Start collector in background with all parameters from environment
                $PYTHON_CMD /opt/HammerDB-5.0/scripts/collect_pure_metrics.py \
                    --host "${PURE_HOST}" \
                    --token "${PURE_API_TOKEN}" \
                    --duration "$COLLECTION_DURATION" \
                    --interval "${PURE_INTERVAL:-5}" \
                    --api-version "${PURE_API_VERSION:-2.4}" \
                    --output "${PURE_OUTPUT:-/tmp/pure_metrics.json}" \
                    --no-verify-ssl \
                    > "${TMPDIR}/pure_metrics.log" 2>&1 &

                PURE_PID=$!
                log "Pure Storage collector started with PID: $PURE_PID"
            fi
        else
            log "WARNING: Pure Storage metrics script not found at /opt/HammerDB-5.0/scripts/collect_pure_metrics.py"
        fi
    else
        log "Pure Storage monitoring enabled but this pod is NOT the designated collector"
        log "Metrics will be collected by the first target pod (target index: 0)"
        log "This pod (target: ${TARGET_NAME}, index: ${TARGET_INDEX:-unknown}) will skip metrics collection"
    fi
fi

# Run the specified HammerDB script with unbuffered output
log "Test started at: $START_TIME"
EXIT_CODE=0
/opt/HammerDB-5.0/hammerdbcli auto /opt/HammerDB-5.0/scripts/$SCRIPT_NAME 2>&1 || EXIT_CODE=$?

# Auto-invoke parse phase after load tests complete successfully
if [[ "$RUN_MODE" == "load" ]] && [ $EXIT_CODE -eq 0 ]; then
    if [[ "$BENCHMARK" == "tproch" ]]; then
        log "TPC-H load test completed successfully - auto-parsing results"
        PARSE_SCRIPT="parse_output_tproch.tcl"
    elif [[ "$BENCHMARK" == "tprocc" ]]; then
        log "TPC-C load test completed successfully - auto-parsing results"
        PARSE_SCRIPT="parse_output_tprocc.tcl"
    fi

    if [ -n "$PARSE_SCRIPT" ]; then
        if [ -f "/opt/HammerDB-5.0/scripts/$PARSE_SCRIPT" ]; then
            log "Executing parse script: $PARSE_SCRIPT"
            /opt/HammerDB-5.0/hammerdbcli auto /opt/HammerDB-5.0/scripts/$PARSE_SCRIPT 2>&1 || {
                log "WARNING: Parse script failed but continuing (exit code: $?)"
            }
        else
            log "WARNING: Parse script not found at /opt/HammerDB-5.0/scripts/$PARSE_SCRIPT"
        fi
    fi
fi

# Stop Pure Storage collector gracefully now that the benchmark is done
if [[ -n "$PURE_PID" ]]; then
    if kill -0 $PURE_PID 2>/dev/null; then
        log "Benchmark finished — sending SIGTERM to Pure Storage collector (PID: $PURE_PID)"
        kill -TERM $PURE_PID 2>/dev/null
        # Give it up to 10 seconds to save results and exit
        for i in $(seq 1 10); do
            kill -0 $PURE_PID 2>/dev/null || break
            sleep 1
        done
        # Force kill if still running
        if kill -0 $PURE_PID 2>/dev/null; then
            log "WARNING: Collector still running after 10s — force killing"
            kill -9 $PURE_PID 2>/dev/null
        fi
    fi
    wait $PURE_PID 2>/dev/null
    PURE_EXIT=$?
    if [ $PURE_EXIT -eq 0 ]; then
        log "Pure Storage metrics collection completed successfully"

        # Display Pure Storage metrics summary if available
        if [ -f "${TMPDIR}/pure_metrics.log" ]; then
            log "=== Pure Storage Metrics Summary ==="
            cat "${TMPDIR}/pure_metrics.log"
            log "===================================="
        fi

        # Emit the JSON data to stdout with delimiters so the CLI can extract it from logs
        if [ -f "${PURE_OUTPUT:-/tmp/pure_metrics.json}" ]; then
            echo ">>>PURE_METRICS_JSON_START<<<"
            cat "${PURE_OUTPUT:-/tmp/pure_metrics.json}"
            echo ">>>PURE_METRICS_JSON_END<<<"
        fi
    else
        log "WARNING: Pure Storage metrics collector exited with code $PURE_EXIT"
        if [ -f "${TMPDIR}/pure_metrics.log" ]; then
            log "Pure Storage collector log:"
            cat "${TMPDIR}/pure_metrics.log"
        fi
    fi
fi

# Calculate duration
END_EPOCH=$(date +%s)
TEST_DURATION=$((END_EPOCH - START_EPOCH))
END_TIME=$(date +'%Y-%m-%d %H:%M:%S')

log "Test finished at: $END_TIME"
log "Duration: ${TEST_DURATION} seconds"

# Write metadata file
if [ -n "$TMPDIR" ]; then
    METADATA_FILE="${TMPDIR}/metadata.json"
    cat > "$METADATA_FILE" <<EOF
{
  "target": "$TARGET_NAME",
  "databaseType": "$DATABASE_TYPE",
  "benchmark": "$BENCHMARK",
  "phase": "$RUN_MODE",
  "startTime": "$START_TIME",
  "endTime": "$END_TIME",
  "durationSeconds": $TEST_DURATION,
  "exitCode": $EXIT_CODE,
  "testRunId": "${TEST_RUN_ID:-unknown}",
  "pureStorageMetricsAvailable": $([ -f "${TMPDIR}/pure_metrics.json" ] && echo "true" || echo "false")
}
EOF
    log "Metadata written to: $METADATA_FILE"
fi

if [ $EXIT_CODE -eq 0 ]; then
    log "SUCCESS: Test completed successfully for $TARGET_NAME"
else
    log "ERROR: Test failed with exit code $EXIT_CODE for $TARGET_NAME"
fi

exit $EXIT_CODE