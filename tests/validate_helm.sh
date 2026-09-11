#!/usr/bin/env bash
# Helm chart and security context verification runner
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART_DIR="${SCRIPT_DIR}/charts/payment-gateway"

echo "[1/3] Linting Helm chart..."
helm lint "${CHART_DIR}" > /dev/null
echo "✓ Helm lint passed."

echo "[2/3] Rendering templates across dev, staging, prod..."
for env in dev staging prod; do
    MANIFEST=$(helm template payment-gateway "${CHART_DIR}" -f "${CHART_DIR}/values-${env}.yaml")
    
    # Assert zero-trust security context parameters in rendered manifest
    if ! echo "${MANIFEST}" | grep -q "runAsNonRoot: true"; then
        echo "Error: runAsNonRoot not enforced in ${env}"
        exit 1
    fi
    if ! echo "${MANIFEST}" | grep -q "readOnlyRootFilesystem: true"; then
        echo "Error: readOnlyRootFilesystem not enforced in ${env}"
        exit 1
    fi
    echo "✓ ${env} rendered with zero-trust security controls verified."
done

echo "[3/3] Validating PodDisruptionBudget & NetworkPolicy presence..."
PROD_MANIFEST=$(helm template payment-gateway "${CHART_DIR}" -f "${CHART_DIR}/values-prod.yaml")
echo "${PROD_MANIFEST}" | grep -q "kind: PodDisruptionBudget" || (echo "Missing PDB in prod"; exit 1)
echo "${PROD_MANIFEST}" | grep -q "kind: NetworkPolicy" || (echo "Missing NetworkPolicy in prod"; exit 1)
echo "✓ Production PDB and NetworkPolicy verified."

echo "All Helm chart validations passed."
