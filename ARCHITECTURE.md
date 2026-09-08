# Architectural Specification: Enterprise GitOps & Progressive Delivery

## 1. Declarative Control Plane & GitOps Invariants

The platform establishes the following invariants across all Kubernetes environments (`dev`, `staging`, `prod`):

1. **Git as the Single Source of Truth:** All Kubernetes resource configurations, replicas, ingress rules, and container versions exist exclusively in Git. Direct mutations via `kubectl apply` or `kubectl edit` are strictly forbidden.
2. **Automated Reconciliation:** The ArgoCD controller polls the repository every 3 minutes (and receives instant GitHub webhooks on push). In the event of drift, the engine executes automated reconciliation:
   ```yaml
   syncPolicy:
     automated:
       prune: true      # Deletes resources removed from Git
       selfHeal: true   # Overwrites out-of-band manual changes
   ```
3. **App-of-Apps Hierarchy:** A root ArgoCD Application (`payment-gateway-root`) monitors the `argocd/applications/` directory and declaratively instantiates child Applications for each environment. This enables provisioning entire new staging or preview environments simply by adding a single YAML manifest to Git.

---

## 2. Progressive Delivery Mechanics: Argo Rollouts vs. Standard RollingUpdate

Standard Kubernetes `Deployment` controllers utilize `RollingUpdate`:
- **Problem:** If a newly deployed container version contains an uncaught exception (e.g. database schema incompatibility), `RollingUpdate` continues deploying until 100% of pods are crashing, impacting all active users.
- **Solution:** This platform replaces `Deployment` with the custom resource `Rollout` from **Argo Rollouts**:
  - Directs 20% of traffic to the Canary replica set via NGINX ingress traffic weighting.
  - Spawns an `AnalysisRun` executing real-time PromQL queries against cluster Prometheus instances.
  - Inspects two key reliability indicators:
    1. **HTTP Error Rate:** `sum(rate(http_requests_total{status=~"5.."})) / sum(rate(http_requests_total))` $\le$ 1.0%
    2. **P99 Request Duration:** `histogram_quantile(0.99, ...)` $\le$ 300ms
  - If either metric breaches the threshold twice consecutively, the rollout enters an `Aborted` phase, instantly reducing Canary traffic weighting to 0% and rolling back to stable with zero downtime.

---

## 3. Threat Model & Security Posture

| Attack Vector | Defense Mechanism | Validation Control |
| :--- | :--- | :--- |
| **CI Runner Compromise** | Pull-based architecture: CI has zero cluster credentials or kubeconfig files. | GitHub Actions permissions limited to `contents: write` (Git only). |
| **Container Escape / Root Exploits** | Workload runs as non-root (UID 10001) with `readOnlyRootFilesystem: true` and `drop: ALL` capabilities. | Enforced via Kyverno `ClusterPolicy` and verified during Helm template generation. |
| **Lateral Cluster Movement** | Zero-trust `NetworkPolicy` dropping all inter-namespace traffic except approved Ingress and Prometheus scrape paths. | Verified in `charts/payment-gateway/templates/hpa-pdb-netpol.yaml`. |
| **Supply Chain Tampering** | Trivy vulnerability scanning halts CI if any CRITICAL CVEs are detected in base OS or Python packages. | Integrated as a required gate in `.github/workflows/ci.yml`. |
