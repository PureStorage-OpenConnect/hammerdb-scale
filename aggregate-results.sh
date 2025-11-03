#!/bin/bash
# Aggregate HammerDB Test Results from Kubernetes Jobs
# Collects logs from all jobs and creates a summary report

set -e

NAMESPACE="${NAMESPACE:-default}"
OUTPUT_DIR="${OUTPUT_DIR:-./results}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

usage() {
    cat << EOF
Usage: $0 [OPTIONS] <phase> <test-id> [namespace]
   OR: $0 -p <phase> -t <test-id> [-n <namespace>]

Aggregates logs from all HammerDB jobs for a given test run.

Arguments:
    phase       Required: Phase to aggregate (build or load)
    test-id     Required: Test run identifier
    namespace   Optional: Kubernetes namespace (default: 'default')

Options:
    -p, --phase      Phase (build, load)
    -t, --test-id    Test identifier
    -n, --namespace  Kubernetes namespace
    -o, --output     Output directory (default: ./results)
    -h, --help       Show this help message

Examples:
    # Positional arguments (backward compatible)
    $0 load test-001
    $0 load test-001 compass

    # Named arguments
    $0 --phase load --test-id test-001
    $0 -p load -t test-001 -n compass

    # Mixed (named take precedence)
    $0 -t my-test load placeholder

    # Custom output directory
    $0 -p load -t test-001 -o /tmp/results

    # Environment variable
    NAMESPACE=compass $0 load test-001

Environment Variables:
    NAMESPACE       Kubernetes namespace (default: 'default')
    OUTPUT_DIR      Output directory for results (default: ./results)

EOF
    exit 1
}

# Parse named arguments
PHASE=""
TEST_ID=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--phase)
            PHASE="$2"
            shift 2
            ;;
        -t|--test-id)
            TEST_ID="$2"
            shift 2
            ;;
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        -*)
            echo "Unknown option: $1"
            usage
            ;;
        *)
            # Positional arguments (backward compatibility)
            if [ -z "$PHASE" ]; then
                PHASE="$1"
            elif [ -z "$TEST_ID" ]; then
                TEST_ID="$1"
            elif [ -z "$NAMESPACE" ] || [ "$NAMESPACE" == "default" ]; then
                NAMESPACE="$1"
            fi
            shift
            ;;
    esac
done

# Validate required arguments
if [ -z "$PHASE" ] || [ -z "$TEST_ID" ]; then
    echo "Error: Missing required arguments"
    echo ""
    usage
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}HammerDB Results Aggregation${NC}"
echo -e "${BLUE}========================================${NC}"
echo "Phase:      ${PHASE}"
echo "Test ID:    ${TEST_ID}"
echo "Namespace:  ${NAMESPACE}"
echo ""

# Create output directory
RESULTS_DIR="${OUTPUT_DIR}/${TEST_ID}/${PHASE}"
mkdir -p "${RESULTS_DIR}"

echo -e "${GREEN}[INFO]${NC} Output directory: ${RESULTS_DIR}"
echo -e "${GREEN}[INFO]${NC} Test ID: ${TEST_ID}"
echo -e "${GREEN}[INFO]${NC} Phase: ${PHASE}"
echo ""

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}[ERROR]${NC} kubectl not found. Please install kubectl."
    exit 1
fi

# Get all jobs for this test run and phase
echo -e "${GREEN}[INFO]${NC} Fetching jobs for test-run=${TEST_ID}, phase=${PHASE}..."
JOBS=$(kubectl get jobs -n "${NAMESPACE}" \
    -l "hammerdb.io/test-run=${TEST_ID},hammerdb.io/phase=${PHASE}" \
    -o jsonpath='{.items[*].metadata.name}' 2>/dev/null)

if [ -z "$JOBS" ]; then
    echo -e "${RED}[ERROR]${NC} No jobs found for test-run=${TEST_ID}, phase=${PHASE}"
    echo "Check if the test has been deployed:"
    echo "  kubectl get jobs -n ${NAMESPACE} -l hammerdb.io/test-run=${TEST_ID}"
    exit 1
fi

JOB_ARRAY=($JOBS)
JOB_COUNT=${#JOB_ARRAY[@]}
echo -e "${GREEN}[INFO]${NC} Found ${JOB_COUNT} job(s)"
echo ""

# Create summary file
SUMMARY_FILE="${RESULTS_DIR}/summary.txt"
SUMMARY_JSON="${RESULTS_DIR}/summary.json"

echo "========================================" > "${SUMMARY_FILE}"
echo "HammerDB Test Results Summary" >> "${SUMMARY_FILE}"
echo "========================================" >> "${SUMMARY_FILE}"
echo "Test ID:    ${TEST_ID}" >> "${SUMMARY_FILE}"
echo "Phase:      ${PHASE}" >> "${SUMMARY_FILE}"
echo "Timestamp:  $(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "${SUMMARY_FILE}"
echo "Jobs Found: ${JOB_COUNT}" >> "${SUMMARY_FILE}"
echo "" >> "${SUMMARY_FILE}"

# Start JSON array
echo "{" > "${SUMMARY_JSON}"
echo "  \"testId\": \"${TEST_ID}\"," >> "${SUMMARY_JSON}"
echo "  \"phase\": \"${PHASE}\"," >> "${SUMMARY_JSON}"
echo "  \"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\"," >> "${SUMMARY_JSON}"
echo "  \"jobCount\": ${JOB_COUNT}," >> "${SUMMARY_JSON}"
echo "  \"results\": [" >> "${SUMMARY_JSON}"

SUCCESS_COUNT=0
FAILED_COUNT=0
FIRST=true
TOTAL_TPM=0
TOTAL_NOPM=0
TOTAL_QPHH=0

# Identify the first job (collector pod for Pure Storage metrics)
FIRST_JOB=$(echo "${JOBS}" | awk '{print $1}')
echo -e "${GREEN}[INFO]${NC} First job (Pure Storage metrics collector): ${FIRST_JOB}"
echo ""

# Process each job
for JOB in ${JOBS}; do
    echo -e "${BLUE}[Processing]${NC} ${JOB}"

    # Extract target name from job name
    # Expected format: {release-name}-{chart-name}-{phase}-{target}-{namespace}
    # Example: load-compass-hammerdb-scale-load-sql-bench-01-compass
    # We want to extract the target name (sql-bench-01)

    # The job name components are:
    # load-compass (release) | hammerdb-scale (chart) | load (phase) | sql-bench-01 (target) | compass (namespace)

    # Method 1: Extract everything between "-{phase}-" and the last dash (namespace)
    # This handles targets with multiple dashes like "sql-bench-01"
    TARGET=$(echo "${JOB}" | sed -E "s/.*-${PHASE}-(.+)-[^-]+$/\1/")

    # Get job status
    JOB_STATUS=$(kubectl get job "${JOB}" -n "${NAMESPACE}" \
        -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}' 2>/dev/null || echo "Unknown")

    FAILED_STATUS=$(kubectl get job "${JOB}" -n "${NAMESPACE}" \
        -o jsonpath='{.status.conditions[?(@.type=="Failed")].status}' 2>/dev/null || echo "")

    # Determine status
    if [ "${JOB_STATUS}" == "True" ]; then
        STATUS="Completed"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        STATUS_ICON="${GREEN}✓${NC}"
    elif [ "${FAILED_STATUS}" == "True" ]; then
        STATUS="Failed"
        FAILED_COUNT=$((FAILED_COUNT + 1))
        STATUS_ICON="${RED}✗${NC}"
    else
        STATUS="Running/Pending"
        STATUS_ICON="${YELLOW}⋯${NC}"
    fi

    echo -e "  Status: ${STATUS_ICON} ${STATUS}"

    # Fetch logs
    LOG_FILE="${RESULTS_DIR}/${TARGET}.log"
    echo "  Fetching logs..."
    kubectl logs -n "${NAMESPACE}" "job/${JOB}" > "${LOG_FILE}" 2>&1 || {
        echo -e "  ${YELLOW}[WARN]${NC} Failed to fetch logs for ${JOB}"
        echo "ERROR: Could not fetch logs" > "${LOG_FILE}"
    }

    # Check if Pure Storage metrics are available (only in first job/collector pod)
    PURE_METRICS_FILE="${RESULTS_DIR}/${TARGET}_pure_metrics.json"
    PURE_SUMMARY_FILE="${RESULTS_DIR}/${TARGET}_pure_metrics_summary.txt"
    HAS_PURE_METRICS=false
    if [ "${JOB}" == "${FIRST_JOB}" ]; then
        # This is the collector pod - check for Pure Storage metrics in logs
        if grep -q "PURE STORAGE PERFORMANCE SUMMARY" "${LOG_FILE}" 2>/dev/null; then
            echo "  Pure Storage metrics detected in collector pod logs"

            # Extract the summary from logs and save to a text file
            # Simple approach: extract 20 lines after "PURE STORAGE PERFORMANCE SUMMARY"
            grep -A 20 "PURE STORAGE PERFORMANCE SUMMARY" "${LOG_FILE}" > "${PURE_SUMMARY_FILE}"

            # Also try to extract JSON if pod is still running
            POD_NAME=$(kubectl get pods -n "${NAMESPACE}" --selector=job-name="${JOB}" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
            if [ -n "$POD_NAME" ]; then
                echo "  Attempting to extract full metrics JSON from pod..."
                kubectl cp -n "${NAMESPACE}" "${POD_NAME}:/tmp/pure_metrics.json" "${PURE_METRICS_FILE}" 2>/dev/null && {
                    HAS_PURE_METRICS=true
                    echo "  Successfully extracted metrics JSON"

                    # Trim metrics to match actual test duration (happens later after DURATION is extracted)
                } || {
                    echo -e "  ${YELLOW}[INFO]${NC} Pod terminated, using summary from logs only"
                    HAS_PURE_METRICS=false
                }
            else
                echo -e "  ${YELLOW}[INFO]${NC} Pod not found (likely terminated), using summary from logs"
            fi
        else
            echo "  No Pure Storage metrics found in logs"
            echo "  (Checking for 'PURE STORAGE PERFORMANCE SUMMARY' pattern)"
        fi
    else
        echo "  Skipping Pure Storage metrics check (not the collector pod)"
    fi

    # Extract timestamps and duration from logs
    START_TIME=$(grep "Test started at:" "${LOG_FILE}" | sed 's/.*Test started at: //' | head -1 || echo "N/A")
    END_TIME=$(grep "Test finished at:" "${LOG_FILE}" | sed 's/.*Test finished at: //' | head -1 || echo "N/A")
    DURATION=$(grep "Duration:" "${LOG_FILE}" | grep "seconds" | sed 's/.*Duration: \([0-9]*\) seconds/\1/' | head -1 || echo "0")

    # Detect database type and benchmark from logs
    DATABASE_TYPE=$(grep "Database Type:" "${LOG_FILE}" | sed 's/.*Database Type: //' | head -1 || echo "unknown")
    BENCHMARK_TYPE=$(grep "Benchmark:" "${LOG_FILE}" | sed 's/.*Benchmark: //' | head -1 || echo "unknown")
    echo "  Detected database: ${DATABASE_TYPE}, benchmark: ${BENCHMARK_TYPE}"

    # Extract key metrics from logs
    if [ "${PHASE}" == "load" ]; then
        echo "  Parsing results..."

        # Database-specific result parsing
        case "${DATABASE_TYPE}" in
            mssql)
                # SQL Server specific patterns
                # TPC-C: Look for HammerDB TPM/NOPM output patterns
                # Patterns: "12500 TPM" or "System achieved 12500 NOPM from 125000 SQL Server TPM"
                TPM_VALUE=$(grep -oP '(\d+)\s+(?:SQL Server\s+)?TPM' "${LOG_FILE}" | grep -oP '\d+' | tail -1 || echo "0")
                NOPM_VALUE=$(grep -oP '(\d+)\s+NOPM' "${LOG_FILE}" | grep -oP '\d+' | tail -1 || echo "0")

                # Alternative: Try "System achieved X NOPM from Y TPM"
                if [ "$TPM_VALUE" == "0" ]; then
                    TPM_VALUE=$(grep -i "system achieved" "${LOG_FILE}" | grep -oP 'from\s+(\d+)' | grep -oP '\d+' | tail -1 || echo "0")
                fi
                if [ "$NOPM_VALUE" == "0" ]; then
                    NOPM_VALUE=$(grep -i "system achieved" "${LOG_FILE}" | grep -oP 'achieved\s+(\d+)' | grep -oP '\d+' | tail -1 || echo "0")
                fi

                # TPC-H: Look for QphH metrics
                # Pattern: "QphH@100: 12345.67" (where 100 is the scale factor)
                QPHH_VALUE=$(grep -oP 'QphH@\d+:\s+([0-9]+\.?[0-9]*)' "${LOG_FILE}" | grep -oP ':\s+\K[0-9]+\.?[0-9]*' | tail -1 || echo "0")

                # Alternative: Try "QphH: 12345.67" without scale factor
                if [ "$QPHH_VALUE" == "0" ] || [ -z "$QPHH_VALUE" ]; then
                    QPHH_VALUE=$(grep -oP 'QphH:\s+([0-9]+\.?[0-9]*)' "${LOG_FILE}" | grep -oP ':\s+\K[0-9]+\.?[0-9]*' | tail -1 || echo "0")
                fi
                ;;

            postgres)
                # PostgreSQL specific patterns
                # TPC-C: Look for PostgreSQL TPM/NOPM patterns
                # Pattern: "PostgreSQL TPM: 12345"
                TPM_VALUE=$(grep -oP '(?:PostgreSQL\s+)?TPM:\s*(\d+)' "${LOG_FILE}" | grep -oP '\d+' | tail -1 || echo "0")
                NOPM_VALUE=$(grep -oP 'NOPM:\s*(\d+)' "${LOG_FILE}" | grep -oP '\d+' | tail -1 || echo "0")

                # TPC-H: QphH pattern
                QPHH_VALUE=$(grep -oP 'QphH:\s+([0-9]+\.?[0-9]*)' "${LOG_FILE}" | grep -oP ':\s+\K[0-9]+\.?[0-9]*' | tail -1 || echo "0")
                ;;

            oracle)
                # Oracle specific patterns
                # TPC-C: Look for Oracle TPM/NOPM patterns
                TPM_VALUE=$(grep -oP 'TPM:\s*(\d+)' "${LOG_FILE}" | grep -oP '\d+' | tail -1 || echo "0")
                NOPM_VALUE=$(grep -oP 'NOPM:\s*(\d+)' "${LOG_FILE}" | grep -oP '\d+' | tail -1 || echo "0")

                # TPC-H: QphH pattern
                QPHH_VALUE=$(grep -oP 'QphH:\s+([0-9]+\.?[0-9]*)' "${LOG_FILE}" | grep -oP ':\s+\K[0-9]+\.?[0-9]*' | tail -1 || echo "0")
                ;;

            mysql)
                # MySQL specific patterns
                # TPC-C: Look for MySQL TPM/NOPM patterns
                TPM_VALUE=$(grep -oP 'TPM:\s*(\d+)' "${LOG_FILE}" | grep -oP '\d+' | tail -1 || echo "0")
                NOPM_VALUE=$(grep -oP 'NOPM:\s*(\d+)' "${LOG_FILE}" | grep -oP '\d+' | tail -1 || echo "0")

                # TPC-H: QphH pattern
                QPHH_VALUE=$(grep -oP 'QphH:\s+([0-9]+\.?[0-9]*)' "${LOG_FILE}" | grep -oP ':\s+\K[0-9]+\.?[0-9]*' | tail -1 || echo "0")
                ;;

            *)
                echo "  WARNING: Unknown database type '${DATABASE_TYPE}', attempting generic parsing"
                # Generic fallback patterns
                TPM_VALUE=$(grep -oP 'TPM[:\s]+(\d+)' "${LOG_FILE}" | grep -oP '\d+' | tail -1 || echo "0")
                NOPM_VALUE=$(grep -oP 'NOPM[:\s]+(\d+)' "${LOG_FILE}" | grep -oP '\d+' | tail -1 || echo "0")
                QPHH_VALUE=$(grep -oP 'QphH[:\s]+([0-9]+\.?[0-9]*)' "${LOG_FILE}" | grep -oP '[0-9]+\.?[0-9]*' | tail -1 || echo "0")
                ;;
        esac

        # Extract per-query timing data for TPC-H (database-agnostic)
        # Pattern: "Query  1:   61.676 seconds" or "  Query  1:   61.676 seconds"
        # Note: Using sort -u to deduplicate since parse script outputs query times twice
        if [[ "$BENCHMARK_TYPE" == "tproch" ]]; then
            # Create temporary file for this target's query times
            QUERY_TIMES_FILE="${RESULTS_DIR}/${TARGET}_query_times.txt"
            grep -oP 'Query\s+(\d+):\s+([0-9]+\.?[0-9]*)\s+seconds' "${LOG_FILE}" | sort -u > "${QUERY_TIMES_FILE}" 2>/dev/null || true
        fi

        # Trim Pure Storage metrics to match actual test duration
        if [ "$HAS_PURE_METRICS" = true ] && [ -f "${PURE_METRICS_FILE}" ] && [ "$DURATION" -gt 0 ]; then
            echo "  Trimming Pure Storage metrics to match test duration (${DURATION}s)"

            # Get sample interval from metrics file (default 5 seconds)
            SAMPLE_INTERVAL=$(jq -r '.metadata.interval // 5' "${PURE_METRICS_FILE}" 2>/dev/null || echo "5")

            # Calculate how many samples we should keep
            MAX_SAMPLES=$((DURATION / SAMPLE_INTERVAL))

            # Get actual sample count in file
            ACTUAL_SAMPLES=$(jq '.samples | length' "${PURE_METRICS_FILE}" 2>/dev/null || echo "0")

            if [ "$ACTUAL_SAMPLES" -gt "$MAX_SAMPLES" ]; then
                echo "    Trimming ${ACTUAL_SAMPLES} samples down to ${MAX_SAMPLES} (${DURATION}s / ${SAMPLE_INTERVAL}s intervals)"

                # Create trimmed version
                jq ".samples |= .[:${MAX_SAMPLES}]" "${PURE_METRICS_FILE}" > "${PURE_METRICS_FILE}.tmp" && \
                    mv "${PURE_METRICS_FILE}.tmp" "${PURE_METRICS_FILE}"
            else
                echo "    No trimming needed (${ACTUAL_SAMPLES} samples covers ${DURATION}s test)"
            fi
        fi

        # Add to totals (if numeric and not zero)
        if [[ "$TPM_VALUE" =~ ^[0-9]+$ ]] && [ "$TPM_VALUE" -gt 0 ]; then
            TOTAL_TPM=$((TOTAL_TPM + TPM_VALUE))
        fi
        if [[ "$NOPM_VALUE" =~ ^[0-9]+$ ]] && [ "$NOPM_VALUE" -gt 0 ]; then
            TOTAL_NOPM=$((TOTAL_NOPM + NOPM_VALUE))
        fi
        if [[ "$QPHH_VALUE" =~ ^[0-9]+\.?[0-9]*$ ]] && [ "$(echo "$QPHH_VALUE > 0" | bc -l 2>/dev/null || echo 0)" == "1" ]; then
            TOTAL_QPHH=$(echo "$TOTAL_QPHH + $QPHH_VALUE" | bc -l 2>/dev/null || echo "$TOTAL_QPHH")
        fi

        # Write to summary
        echo "----------------------------------------" >> "${SUMMARY_FILE}"
        echo "Target:     ${TARGET}" >> "${SUMMARY_FILE}"
        echo "Benchmark:  ${BENCHMARK_TYPE}" >> "${SUMMARY_FILE}"
        echo "Status:     ${STATUS}" >> "${SUMMARY_FILE}"
        echo "Started:    ${START_TIME}" >> "${SUMMARY_FILE}"
        echo "Finished:   ${END_TIME}" >> "${SUMMARY_FILE}"
        echo "Duration:   ${DURATION} seconds" >> "${SUMMARY_FILE}"

        # Show TPC-C metrics only for TPC-C benchmarks
        if [[ "$BENCHMARK_TYPE" == "tprocc" ]]; then
            echo "TPM:        ${TPM_VALUE}" >> "${SUMMARY_FILE}"
            echo "NOPM:       ${NOPM_VALUE}" >> "${SUMMARY_FILE}"
        fi

        # Show TPC-H metrics only for TPC-H benchmarks
        if [[ "$BENCHMARK_TYPE" == "tproch" ]] && [[ "$QPHH_VALUE" != "0" ]] && [[ -n "$QPHH_VALUE" ]]; then
            echo "QphH:       ${QPHH_VALUE}" >> "${SUMMARY_FILE}"
        fi

        # Add Pure Storage metrics to text summary if available
        PURE_SUMMARY_FILE="${RESULTS_DIR}/${TARGET}_pure_metrics_summary.txt"
        if [ -f "${PURE_SUMMARY_FILE}" ]; then
            echo "" >> "${SUMMARY_FILE}"
            echo "Pure Storage Metrics (from logs):" >> "${SUMMARY_FILE}"
            # Append the extracted summary directly
            cat "${PURE_SUMMARY_FILE}" >> "${SUMMARY_FILE}"
        elif [ "$HAS_PURE_METRICS" = true ] && [ -f "${PURE_METRICS_FILE}" ]; then
            echo "" >> "${SUMMARY_FILE}"
            echo "Pure Storage Metrics:" >> "${SUMMARY_FILE}"
            if command -v jq &> /dev/null; then
                # Extract key metrics using jq
                READ_LAT=$(jq -r '.summary.read_latency_us_avg // "N/A"' "${PURE_METRICS_FILE}" 2>/dev/null)
                WRITE_LAT=$(jq -r '.summary.write_latency_us_avg // "N/A"' "${PURE_METRICS_FILE}" 2>/dev/null)
                READ_IOPS=$(jq -r '.summary.read_iops_avg // "N/A"' "${PURE_METRICS_FILE}" 2>/dev/null)
                WRITE_IOPS=$(jq -r '.summary.write_iops_avg // "N/A"' "${PURE_METRICS_FILE}" 2>/dev/null)
                READ_BW=$(jq -r '.summary.read_bandwidth_mbps_avg // "N/A"' "${PURE_METRICS_FILE}" 2>/dev/null)
                WRITE_BW=$(jq -r '.summary.write_bandwidth_mbps_avg // "N/A"' "${PURE_METRICS_FILE}" 2>/dev/null)
                READ_BLOCK=$(jq -r '.summary.avg_read_block_size_kb_avg // "N/A"' "${PURE_METRICS_FILE}" 2>/dev/null)
                WRITE_BLOCK=$(jq -r '.summary.avg_write_block_size_kb_avg // "N/A"' "${PURE_METRICS_FILE}" 2>/dev/null)

                echo "  Read Latency:    ${READ_LAT} µs" >> "${SUMMARY_FILE}"
                echo "  Write Latency:   ${WRITE_LAT} µs" >> "${SUMMARY_FILE}"
                echo "  Read IOPS:       ${READ_IOPS}" >> "${SUMMARY_FILE}"
                echo "  Write IOPS:      ${WRITE_IOPS}" >> "${SUMMARY_FILE}"
                echo "  Read BW:         ${READ_BW} MB/s" >> "${SUMMARY_FILE}"
                echo "  Write BW:        ${WRITE_BW} MB/s" >> "${SUMMARY_FILE}"
                echo "  Avg Read Block:  ${READ_BLOCK} KB" >> "${SUMMARY_FILE}"
                echo "  Avg Write Block: ${WRITE_BLOCK} KB" >> "${SUMMARY_FILE}"
            else
                echo "  (See ${PURE_METRICS_FILE} for details)" >> "${SUMMARY_FILE}"
            fi
        fi

        echo "" >> "${SUMMARY_FILE}"

        # Add to JSON
        if [ "${FIRST}" = false ]; then
            echo "    }," >> "${SUMMARY_JSON}"
        fi
        FIRST=false

        echo "    {" >> "${SUMMARY_JSON}"
        echo "      \"target\": \"${TARGET}\"," >> "${SUMMARY_JSON}"
        echo "      \"benchmark\": \"${BENCHMARK_TYPE}\"," >> "${SUMMARY_JSON}"
        echo "      \"status\": \"${STATUS}\"," >> "${SUMMARY_JSON}"
        echo "      \"startTime\": \"${START_TIME}\"," >> "${SUMMARY_JSON}"
        echo "      \"endTime\": \"${END_TIME}\"," >> "${SUMMARY_JSON}"
        echo "      \"durationSec\": ${DURATION}," >> "${SUMMARY_JSON}"

        # Add benchmark-specific metrics
        if [[ "$BENCHMARK_TYPE" == "tprocc" ]]; then
            echo "      \"tpm\": ${TPM_VALUE}," >> "${SUMMARY_JSON}"
            echo "      \"nopm\": ${NOPM_VALUE}," >> "${SUMMARY_JSON}"
        elif [[ "$BENCHMARK_TYPE" == "tproch" ]]; then
            echo "      \"qphh\": ${QPHH_VALUE:-0}," >> "${SUMMARY_JSON}"
        fi

        echo "      \"logFile\": \"${LOG_FILE}\"," >> "${SUMMARY_JSON}"

        # Add Pure Storage metrics if available
        if [ "$HAS_PURE_METRICS" = true ] && [ -f "${PURE_METRICS_FILE}" ]; then
            echo "      \"pureStorageMetrics\": {" >> "${SUMMARY_JSON}"
            echo "        \"metricsFile\": \"${PURE_METRICS_FILE}\"," >> "${SUMMARY_JSON}"

            # Extract summary metrics from Pure Storage JSON using jq if available
            if command -v jq &> /dev/null; then
                PURE_SUMMARY=$(jq '.summary' "${PURE_METRICS_FILE}" 2>/dev/null || echo "{}")
                echo "        \"summary\": ${PURE_SUMMARY}" >> "${SUMMARY_JSON}"
            else
                echo "        \"summary\": \"jq not available - see metricsFile for details\"" >> "${SUMMARY_JSON}"
            fi
            echo "      }" >> "${SUMMARY_JSON}"
        else
            echo "      \"pureStorageMetrics\": null" >> "${SUMMARY_JSON}"
        fi

    else
        # Build phase - record status and timestamps
        echo "----------------------------------------" >> "${SUMMARY_FILE}"
        echo "Target:     ${TARGET}" >> "${SUMMARY_FILE}"
        echo "Status:     ${STATUS}" >> "${SUMMARY_FILE}"
        echo "Started:    ${START_TIME}" >> "${SUMMARY_FILE}"
        echo "Finished:   ${END_TIME}" >> "${SUMMARY_FILE}"
        echo "Duration:   ${DURATION} seconds" >> "${SUMMARY_FILE}"
        echo "" >> "${SUMMARY_FILE}"

        # Add to JSON
        if [ "${FIRST}" = false ]; then
            echo "    }," >> "${SUMMARY_JSON}"
        fi
        FIRST=false

        echo "    {" >> "${SUMMARY_JSON}"
        echo "      \"target\": \"${TARGET}\"," >> "${SUMMARY_JSON}"
        echo "      \"status\": \"${STATUS}\"," >> "${SUMMARY_JSON}"
        echo "      \"startTime\": \"${START_TIME}\"," >> "${SUMMARY_JSON}"
        echo "      \"endTime\": \"${END_TIME}\"," >> "${SUMMARY_JSON}"
        echo "      \"durationSec\": ${DURATION}," >> "${SUMMARY_JSON}"
        echo "      \"logFile\": \"${LOG_FILE}\"" >> "${SUMMARY_JSON}"
    fi

    echo ""
done

# Calculate per-query averages for TPC-H if we have query timing data
declare -A QUERY_TOTAL_TIMES
declare -A QUERY_COUNTS
QUERY_TIMING_FILE="${RESULTS_DIR}/per_query_timing.txt"

if ls "${RESULTS_DIR}"/*_query_times.txt 1> /dev/null 2>&1; then
    echo -e "${GREEN}[INFO]${NC} Calculating per-query averages across all targets..."

    # Process each target's query times
    for QUERY_FILE in "${RESULTS_DIR}"/*_query_times.txt; do
        while IFS= read -r line; do
            # Parse: "Query  1:   61.676 seconds"
            if [[ "$line" =~ Query[[:space:]]+([0-9]+):[[:space:]]+([0-9]+\.?[0-9]*)[[:space:]]+seconds ]]; then
                QUERY_NUM="${BASH_REMATCH[1]}"
                QUERY_TIME="${BASH_REMATCH[2]}"

                # Add to running total
                if [ -z "${QUERY_TOTAL_TIMES[$QUERY_NUM]}" ]; then
                    QUERY_TOTAL_TIMES[$QUERY_NUM]="$QUERY_TIME"
                    QUERY_COUNTS[$QUERY_NUM]=1
                else
                    QUERY_TOTAL_TIMES[$QUERY_NUM]=$(echo "${QUERY_TOTAL_TIMES[$QUERY_NUM]} + $QUERY_TIME" | bc -l)
                    QUERY_COUNTS[$QUERY_NUM]=$((${QUERY_COUNTS[$QUERY_NUM]} + 1))
                fi
            fi
        done < "$QUERY_FILE"
    done

    # Calculate averages and write to file
    if [ ${#QUERY_TOTAL_TIMES[@]} -gt 0 ]; then
        echo "========================================" > "${QUERY_TIMING_FILE}"
        echo "TPC-H Per-Query Timing Averages" >> "${QUERY_TIMING_FILE}"
        echo "========================================" >> "${QUERY_TIMING_FILE}"
        echo "Targets: ${JOB_COUNT}" >> "${QUERY_TIMING_FILE}"
        echo "" >> "${QUERY_TIMING_FILE}"

        # Sort query numbers and display
        for QUERY_NUM in $(echo "${!QUERY_TOTAL_TIMES[@]}" | tr ' ' '\n' | sort -n); do
            TOTAL="${QUERY_TOTAL_TIMES[$QUERY_NUM]}"
            COUNT="${QUERY_COUNTS[$QUERY_NUM]}"
            AVG=$(echo "scale=3; $TOTAL / $COUNT" | bc -l)
            printf "Query %2d: %8.3f seconds (avg of %d targets)\n" "$QUERY_NUM" "$AVG" "$COUNT" >> "${QUERY_TIMING_FILE}"
        done

        echo "========================================" >> "${QUERY_TIMING_FILE}"
    fi
fi

# Close JSON
echo "    }" >> "${SUMMARY_JSON}"
echo "  ]," >> "${SUMMARY_JSON}"
echo "  \"summary\": {" >> "${SUMMARY_JSON}"
echo "    \"totalJobs\": ${JOB_COUNT}," >> "${SUMMARY_JSON}"
echo "    \"successful\": ${SUCCESS_COUNT}," >> "${SUMMARY_JSON}"
echo "    \"failed\": ${FAILED_COUNT}" >> "${SUMMARY_JSON}"

if [ "${PHASE}" == "load" ]; then
    # Add TPC-C totals if any exist
    if [ "$TOTAL_TPM" -gt 0 ] || [ "$TOTAL_NOPM" -gt 0 ]; then
        echo "    ," >> "${SUMMARY_JSON}"
        echo "    \"totalTPM\": ${TOTAL_TPM}," >> "${SUMMARY_JSON}"
        echo "    \"totalNOPM\": ${TOTAL_NOPM}" >> "${SUMMARY_JSON}"
    fi

    # Add TPC-H totals if any exist
    if [ "$(echo "$TOTAL_QPHH > 0" | bc -l 2>/dev/null || echo 0)" == "1" ]; then
        # Add comma if we already have TPC-C metrics
        if [ "$TOTAL_TPM" -gt 0 ] || [ "$TOTAL_NOPM" -gt 0 ]; then
            sed -i '$ s/$/,/' "${SUMMARY_JSON}"
        else
            echo "    ," >> "${SUMMARY_JSON}"
        fi
        FORMATTED_QPHH=$(printf "%.2f" "$TOTAL_QPHH" 2>/dev/null || echo "0")
        echo "    \"totalQphH\": ${FORMATTED_QPHH}" >> "${SUMMARY_JSON}"
    fi
fi
echo "  }" >> "${SUMMARY_JSON}"
echo "}" >> "${SUMMARY_JSON}"

# Write summary footer
echo "========================================" >> "${SUMMARY_FILE}"
echo "Summary:" >> "${SUMMARY_FILE}"
echo "  Total Jobs: ${JOB_COUNT}" >> "${SUMMARY_FILE}"
echo "  Successful: ${SUCCESS_COUNT}" >> "${SUMMARY_FILE}"
echo "  Failed:     ${FAILED_COUNT}" >> "${SUMMARY_FILE}"
if [ "${PHASE}" == "load" ]; then
    echo "" >> "${SUMMARY_FILE}"
    echo "Aggregated Metrics:" >> "${SUMMARY_FILE}"

    # Show TPC-C metrics if present
    if [ "$TOTAL_TPM" -gt 0 ] || [ "$TOTAL_NOPM" -gt 0 ]; then
        echo "  Total TPM:  ${TOTAL_TPM}" >> "${SUMMARY_FILE}"
        echo "  Total NOPM: ${TOTAL_NOPM}" >> "${SUMMARY_FILE}"
    fi

    # Show TPC-H metrics if present
    if [ "$(echo "$TOTAL_QPHH > 0" | bc -l 2>/dev/null || echo 0)" == "1" ]; then
        FORMATTED_QPHH=$(printf "%.2f" "$TOTAL_QPHH" 2>/dev/null || echo "0.00")
        echo "  Total QphH: ${FORMATTED_QPHH}" >> "${SUMMARY_FILE}"
    fi

    # Append per-query timing averages to summary if available
    if [ -f "${QUERY_TIMING_FILE}" ]; then
        echo "" >> "${SUMMARY_FILE}"
        cat "${QUERY_TIMING_FILE}" >> "${SUMMARY_FILE}"
    fi
fi
echo "========================================" >> "${SUMMARY_FILE}"

# Display summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Results Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo "Total Jobs:  ${JOB_COUNT}"
echo -e "Successful:  ${GREEN}${SUCCESS_COUNT}${NC}"
if [ ${FAILED_COUNT} -gt 0 ]; then
    echo -e "Failed:      ${RED}${FAILED_COUNT}${NC}"
else
    echo "Failed:      ${FAILED_COUNT}"
fi

if [ "${PHASE}" == "load" ]; then
    echo ""
    echo -e "${GREEN}Aggregated Metrics:${NC}"

    # Show TPC-C metrics if present
    if [ "$TOTAL_TPM" -gt 0 ] || [ "$TOTAL_NOPM" -gt 0 ]; then
        echo "  Total TPM:  ${TOTAL_TPM}"
        echo "  Total NOPM: ${TOTAL_NOPM}"
    fi

    # Show TPC-H metrics if present
    if [ "$(echo "$TOTAL_QPHH > 0" | bc -l 2>/dev/null || echo 0)" == "1" ]; then
        FORMATTED_QPHH=$(printf "%.2f" "$TOTAL_QPHH" 2>/dev/null || echo "0.00")
        echo "  Total QphH: ${FORMATTED_QPHH}"
    fi
fi

echo ""
echo "Results saved to:"
echo "  Summary:     ${SUMMARY_FILE}"
echo "  JSON:        ${SUMMARY_JSON}"
echo "  Logs:        ${RESULTS_DIR}/*.log"
if [ -f "${QUERY_TIMING_FILE}" ]; then
    echo "  Query Times: ${QUERY_TIMING_FILE}"
fi
echo ""

# Display summary content
echo -e "${GREEN}[INFO]${NC} Summary content:"
echo ""
cat "${SUMMARY_FILE}"

# Display per-query timing if available
if [ -f "${QUERY_TIMING_FILE}" ]; then
    echo ""
    echo -e "${GREEN}[INFO]${NC} Per-Query Timing Averages:"
    echo ""
    cat "${QUERY_TIMING_FILE}"
fi

echo ""
echo -e "${GREEN}[SUCCESS]${NC} Aggregation complete!"
