import unittest
import urllib.request
import urllib.error
import json
import threading
import time
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))
from main import GatewayRequestHandler, CHAOS_CONFIG, REQUEST_COUNTS
from http.server import HTTPServer

TEST_PORT = 18085
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"

class TestPaymentGatewayMicroservice(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", TEST_PORT), GatewayRequestHandler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever)
        cls.server_thread.daemon = True
        cls.server_thread.start()
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        CHAOS_CONFIG["error_rate"] = 0.0
        CHAOS_CONFIG["latency_ms"] = 0.0

    def test_root_endpoint_operational(self):
        with urllib.request.urlopen(f"{BASE_URL}/") as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode("utf-8"))
            self.assertEqual(data["service"], "payment-gateway")
            self.assertEqual(data["status"], "operational")

    def test_liveness_probe_healthz(self):
        with urllib.request.urlopen(f"{BASE_URL}/healthz") as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode("utf-8"))
            self.assertEqual(data["status"], "alive")

    def test_readiness_probe_ready(self):
        with urllib.request.urlopen(f"{BASE_URL}/ready") as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode("utf-8"))
            self.assertEqual(data["upstream_connected"], True)

    def test_prometheus_metrics_exposition(self):
        with urllib.request.urlopen(f"{BASE_URL}/metrics") as response:
            self.assertEqual(response.status, 200)
            content = response.read().decode("utf-8")
            self.assertIn("http_requests_total", content)
            self.assertIn("payment_gateway_info", content)

    def test_chaos_injection_triggers_500(self):
        req = urllib.request.Request(f"{BASE_URL}/chaos/inject?error_rate=1.0", method="POST")
        with urllib.request.urlopen(req) as response:
            self.assertEqual(response.status, 200)

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(f"{BASE_URL}/")
        self.assertEqual(ctx.exception.code, 500)

    def test_chaos_injection_reset_restores_service(self):
        # Inject error
        inject_req = urllib.request.Request(f"{BASE_URL}/chaos/inject?error_rate=1.0", method="POST")
        with urllib.request.urlopen(inject_req) as response:
            self.assertEqual(response.status, 200)

        # Reset error
        reset_req = urllib.request.Request(f"{BASE_URL}/chaos/inject?error_rate=0.0", method="POST")
        with urllib.request.urlopen(reset_req) as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode("utf-8"))
            self.assertEqual(data["active_error_rate"], 0.0)

        # Verify traffic succeeds
        with urllib.request.urlopen(f"{BASE_URL}/") as response:
            self.assertEqual(response.status, 200)

    def test_not_found_404_routing(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(f"{BASE_URL}/nonexistent-route")
        self.assertEqual(ctx.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
