#!/bin/bash
# HammerDB Scale deployment script

NAMESPACE="${NAMESPACE:-default}"
CHART_PATH="${CHART_PATH:-.}"

usage() {
    cat << EOF
Usage: $0 [OPTIONS] <phase> <test-id> <benchmark> [namespace]
   OR: $0 -p <phase> -t <test-id> -b <benchmark> [-n <namespace>]

Phases:
    build      Build database schemas
    load       Run load test
    parse      Parse test results (run after load)

Benchmarks:
    tprocc     TPC-C (OLTP)
    tproch     TPC-H (OLAP)

Arguments:
    phase       Required: build, load, or parse
    test-id     Required: Unique test identifier (e.g., test-001)
    benchmark   Required: tprocc or tproch
    namespace   Optional: Kubernetes namespace (default: 'default')

Options:
    -p, --phase      Phase (build, load, parse)
    -t, --test-id    Test identifier
    -b, --benchmark  Benchmark (tprocc, tproch)
    -n, --namespace  Kubernetes namespace
    -c, --chart      Path to Helm chart (default: .)
    -h, --help       Show this help message

Examples:
    # Positional arguments (backward compatible)
    $0 load test-001 tprocc
    $0 load test-001 tprocc compass

    # Named arguments
    $0 --phase load --test-id test-001 --benchmark tprocc
    $0 -p load -t test-001 -b tprocc -n compass

    # Mixed (named take precedence)
    $0 -t my-test load placeholder tprocc

    # Environment variable
    NAMESPACE=compass $0 load test-001 tprocc

    # Monitor logs
    kubectl logs -n <namespace> -l hammerdb.io/phase=load --follow

    # Cleanup
    helm uninstall load-test-001 -n <namespace>

Environment Variables:
    NAMESPACE       Kubernetes namespace (default: 'default')
    CHART_PATH      Path to Helm chart (default: .)

EOF
    exit 1
}

# Parse named arguments
PHASE=""
TEST_ID=""
BENCHMARK=""

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
        -b|--benchmark)
            BENCHMARK="$2"
            shift 2
            ;;
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        -c|--chart)
            CHART_PATH="$2"
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
            elif [ -z "$BENCHMARK" ]; then
                BENCHMARK="$1"
            elif [ -z "$NAMESPACE" ] || [ "$NAMESPACE" == "default" ]; then
                NAMESPACE="$1"
            fi
            shift
            ;;
    esac
done

# Validate required arguments
if [ -z "$PHASE" ] || [ -z "$TEST_ID" ] || [ -z "$BENCHMARK" ]; then
    echo "Error: Missing required arguments"
    echo ""
    usage
fi

echo "=========================================="
echo "HammerDB Scale Deployment"
echo "=========================================="
echo "Phase:      ${PHASE}"
echo "Test ID:    ${TEST_ID}"
echo "Benchmark:  ${BENCHMARK}"
echo "Namespace:  ${NAMESPACE}"
echo "=========================================="
echo ""

if ! helm install "${PHASE}-${TEST_ID}" "${CHART_PATH}" \
    --namespace "${NAMESPACE}" \
    --create-namespace \
    --set testRun.id="${TEST_ID}" \
    --set testRun.phase="${PHASE}" \
    --set testRun.benchmark="${BENCHMARK}"; then
    echo ""
    echo "ERROR: Helm installation failed"
    echo "Check the error message above for details"
    exit 1
fi

echo ""
echo "=========================================="
echo "Monitor logs:"
echo "  kubectl logs -n ${NAMESPACE} -l hammerdb.io/phase=${PHASE} --follow"
echo ""
echo "View job status:"
echo "  kubectl get jobs -n ${NAMESPACE} -l hammerdb.io/test-run=${TEST_ID}"
echo ""
echo "Aggregate results (after completion):"
echo "  ./aggregate-results.sh ${PHASE} ${TEST_ID}"
echo ""
echo "Cleanup when done:"
echo "  helm uninstall ${PHASE}-${TEST_ID} -n ${NAMESPACE}"
echo "=========================================="
