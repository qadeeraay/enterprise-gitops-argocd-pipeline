#!/usr/bin/env python3
"""
Enterprise Payment Gateway Microservice
High-availability microservice with health probes, Prometheus telemetry, and chaos simulation.
Designed for GitOps, Kubernetes Restricted Pod Security, and Argo Rollouts.
"""
import os
import json
import time
import random
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Service configuration
SERVICE_NAME = "payment-gateway"
APP_VERSION = os.getenv("APP_VERSION", "1.2.0")
APP_ENV = os.getenv("APP_ENV", "production")
PORT = int(os.getenv("PORT", "8080"))

# State & Telemetry Counters
REQUEST_COUNTS = {
    "total": 0,
    "success": 0,
    "error": 0
}
LATENCIES = []

CHAOS_CONFIG = {
    "error_rate": float(os.getenv("INITIAL_ERROR_RATE", "0.0")),
    "latency_ms": float(os.getenv("INITIAL_LATENCY_MS", "0.0"))
}

class GatewayRequestHandler(BaseHTTPRequestHandler):
    server_version = "PaymentGateway/1.2.0"

    def _send_json(self, status_code: int, data: dict):
        response_bytes = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def do_GET(self):
        start_time = time.time()
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        REQUEST_COUNTS["total"] += 1

        # 1. Liveness Probe
        if path == "/healthz":
            REQUEST_COUNTS["success"] += 1
            self._send_json(200, {"status": "alive", "service": SERVICE_NAME})
            return

        # 2. Readiness Probe
        if path == "/ready":
            REQUEST_COUNTS["success"] += 1
            self._send_json(200, {
                "status": "ready",
                "service": SERVICE_NAME,
                "upstream_connected": True
            })
            return

        # 3. Prometheus Telemetry Endpoint
        if path == "/metrics":
            REQUEST_COUNTS["success"] += 1
            metrics_payload = (
                f"# HELP http_requests_total Total HTTP requests processed\n"
                f"# TYPE http_requests_total counter\n"
                f'http_requests_total{{service="{SERVICE_NAME}",status="200"}} {REQUEST_COUNTS["success"]}\n'
                f'http_requests_total{{service="{SERVICE_NAME}",status="500"}} {REQUEST_COUNTS["error"]}\n'
                f"# HELP payment_gateway_info Service build metadata\n"
                f"# TYPE payment_gateway_info gauge\n"
                f'payment_gateway_info{{version="{APP_VERSION}",env="{APP_ENV}"}} 1\n'
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(metrics_payload)))
            self.end_headers()
            self.wfile.write(metrics_payload)
            return

        # 4. Root Endpoint (Simulates Business Transaction)
        if path == "/":
            # Chaos Simulation for Canary Rollback testing
            if random.random() < CHAOS_CONFIG["error_rate"]:
                REQUEST_COUNTS["error"] += 1
                self._send_json(500, {
                    "error": "Synthetic Canary Fault Injected",
                    "code": "CANARY_CHAOS_ACTIVE",
                    "version": APP_VERSION
                })
                return

            if CHAOS_CONFIG["latency_ms"] > 0:
                time.sleep(CHAOS_CONFIG["latency_ms"] / 1000.0)

            elapsed = time.time() - start_time
            LATENCIES.append(elapsed)
            REQUEST_COUNTS["success"] += 1

            self._send_json(200, {
                "service": SERVICE_NAME,
                "version": APP_VERSION,
                "environment": APP_ENV,
                "status": "operational",
                "processed_in_sec": round(elapsed, 4)
            })
            return

        # 404 Fallback
        self._send_json(404, {"error": "Not Found", "path": path})

    def do_POST(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        # 5. Chaos Injection Endpoint for Canary Testing
        if path == "/chaos/inject":
            query_params = parse_qs(parsed_path.query)
            error_rate = float(query_params.get("error_rate", [0.0])[0])
            latency_ms = float(query_params.get("latency_ms", [0.0])[0])
            
            CHAOS_CONFIG["error_rate"] = max(0.0, min(1.0, error_rate))
            CHAOS_CONFIG["latency_ms"] = max(0.0, latency_ms)
            
            self._send_json(200, {
                "status": "chaos_updated",
                "active_error_rate": CHAOS_CONFIG["error_rate"],
                "active_latency_ms": CHAOS_CONFIG["latency_ms"]
            })
            return

        self._send_json(404, {"error": "Endpoint Not Found"})

    def log_message(self, format, *args):
        # Quiet standard output during test suites
        pass

def run_server():
    server = HTTPServer(("0.0.0.0", PORT), GatewayRequestHandler)
    print(f"[{SERVICE_NAME}] Listening on port {PORT} (Version: {APP_VERSION}, Env: {APP_ENV})...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == "__main__":
    run_server()
