"""
SmartFeeder EMS — BUS-1 Detailed Dashboard (Page 3) Automated Test Suite
Verifies BUS-1 route, authentication protection, engineering calculations,
consistency with Home Dashboard, Feeder 1-4 data, Solar-A, BESS-A,
navigation links, and API telemetry.
"""
import unittest
import json
import math
import os
import sys

# Ensure root directory is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app import create_app
from backend.config import Config
from backend.engineering_service import EngineeringService
from backend.data_service import DataService


class TestBus1Dashboard(unittest.TestCase):
    def setUp(self):
        self.app = create_app(Config)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.admin_username = Config.ADMIN_USERNAME
        self.admin_password = Config.ADMIN_PASSWORD

    def _login(self):
        """Helper to establish an authenticated session."""
        return self.client.post("/api/auth/login",
                                data=json.dumps({"username": self.admin_username, "password": self.admin_password}),
                                content_type="application/json")

    def test_01_unauthenticated_bus1_redirects_to_login(self):
        """TEST 1: Unauthenticated access to /bus/1 redirects to /login."""
        res = self.client.get("/bus/1", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

    def test_02_unauthenticated_api_bus1_live_returns_401(self):
        """TEST 2: Unauthenticated access to /api/bus/1/live returns 401."""
        res = self.client.get("/api/bus/1/live")
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data["success"])

    def test_03_authenticated_bus1_renders_successfully(self):
        """TEST 3: Authenticated access renders BUS-1 Detailed Dashboard with required elements."""
        self._login()
        res = self.client.get("/bus/1")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")

        # Headings & Subtitles
        self.assertIn("BUS-1", html)
        self.assertIn("11 kV Distribution Bus — Detailed Asset & Telemetry Overview", html)
        self.assertIn("BUS-1 • 4 Feeders • Solar-A • BESS-A", html)

        # Breadcrumb & Navigation
        self.assertIn("← Back to Home", html)
        self.assertIn('href="/"', html)

        # BUS-1 Summary Card
        self.assertIn("BUS-1 STATUS", html)
        self.assertIn("Current Bus Demand", html)
        self.assertIn("Bus Voltage", html)
        self.assertIn("Bus Current", html)
        self.assertIn("Bus Frequency", html)
        self.assertIn("Solar Status", html)
        self.assertIn("BESS Status", html)

        # Feeders Section
        self.assertIn("BUS-1 FEEDERS", html)
        self.assertIn("FEEDER-1", html)
        self.assertIn("FEEDER-2", html)
        self.assertIn("FEEDER-3", html)
        self.assertIn("FEEDER-4", html)

        # Clickable Feeder Links
        self.assertIn('href="/feeder/1"', html)
        self.assertIn('href="/feeder/2"', html)
        self.assertIn('href="/feeder/3"', html)
        self.assertIn('href="/feeder/4"', html)

        # Solar-A & BESS-A Assets
        self.assertIn("SOLAR-A", html)
        self.assertIn("495 kW Installed Capacity", html)
        self.assertIn('href="/solar/A"', html)

        self.assertIn("BESS-A", html)
        self.assertIn("Operating Window: 15% – 90%", html)
        self.assertIn('href="/bess/A"', html)

        # Footer Credit
        self.assertIn("Team Nexora", html)

    def test_04_api_bus1_live_telemetry_calculations(self):
        """TEST 4: Verify /api/bus/1/live returns dataset-backed, mathematically consistent values."""
        self._login()
        res = self.client.get("/api/bus/1/live")
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertTrue(json_data["success"])
        data = json_data["data"]

        summary = data["summary"]
        feeders = data["feeders"]
        solar_a = data["solar_a"]
        bess_a = data["bess_a"]

        # 1. BUS-1 Demand equals sum of Feeders 1 to 4
        f_demands = [f["demand_kw"] for f in feeders]
        expected_bus_demand = round(sum(f_demands), 1)
        self.assertAlmostEqual(summary["demand_kw"], expected_bus_demand, delta=0.1)

        # 2. Bus Voltage limits: 10.8 <= V <= 12.0 kV
        self.assertGreaterEqual(summary["voltage_kv"], 10.80)
        self.assertLessEqual(summary["voltage_kv"], 12.00)

        # 3. Bus Frequency limits: 49.9 <= f <= 50.1 Hz
        self.assertGreaterEqual(summary["frequency_hz"], 49.90)
        self.assertLessEqual(summary["frequency_hz"], 50.10)

        # 4. 3-Phase Bus Current Equation: I = P / (sqrt(3) * V * PF)
        if summary["demand_kw"] > 0:
            expected_current = summary["demand_kw"] / (math.sqrt(3) * summary["voltage_kv"] * 0.95)
            self.assertAlmostEqual(summary["current_a"], expected_current, delta=0.2)

        # 5. Solar-A Rules: Capacity <= 495 kW, Status ACTIVE if >= 8 kW else INACTIVE
        self.assertLessEqual(solar_a["generation_kw"], 495.0)
        if solar_a["generation_kw"] >= 8.0:
            self.assertEqual(solar_a["status"], "ACTIVE")
        else:
            self.assertEqual(solar_a["status"], "INACTIVE")

        # 6. BESS-A Power and Status agreement
        self.assertIn(bess_a["status"], ["CHARGING", "DISCHARGING", "IDLE"])
        self.assertGreaterEqual(bess_a["soc_pct"], 0.0)
        self.assertLessEqual(bess_a["soc_pct"], 100.0)

        # 7. Feeders 1 to 4 Validations
        self.assertEqual(len(feeders), 4)
        for f in feeders:
            self.assertIn(f["id"], [1, 2, 3, 4])
            self.assertGreaterEqual(f["voltage_kv"], 10.80)
            self.assertLessEqual(f["voltage_kv"], 12.00)
            self.assertGreaterEqual(f["frequency_hz"], 49.90)
            self.assertLessEqual(f["frequency_hz"], 50.10)
            self.assertGreaterEqual(f["power_factor"], 0.90)
            self.assertLessEqual(f["power_factor"], 0.99)
            self.assertEqual(f["route"], f"/feeder/{f['id']}")

    def test_05_consistency_between_home_and_bus1(self):
        """TEST 5: Ensure BUS-1 telemetry values match Home Dashboard BUS-1 card for same dataset record."""
        self._login()

        # Fetch Home live telemetry
        res_home = self.client.get("/api/dashboard/live")
        self.assertEqual(res_home.status_code, 200)
        home_bus1 = res_home.get_json()["data"]["bus1"]

        # Fetch BUS-1 live telemetry
        res_bus1 = self.client.get("/api/bus/1/live")
        self.assertEqual(res_bus1.status_code, 200)
        bus1_summary = res_bus1.get_json()["data"]["summary"]

        # Compare values
        self.assertEqual(home_bus1["demand_kw"], bus1_summary["demand_kw"])
        self.assertEqual(home_bus1["voltage_kv"], bus1_summary["voltage_kv"])
        self.assertEqual(home_bus1["current_a"], bus1_summary["current_a"])
        self.assertEqual(home_bus1["frequency_hz"], bus1_summary["frequency_hz"])
        self.assertEqual(home_bus1["solar_status"], bus1_summary["solar_status"])
        self.assertEqual(home_bus1["bess_status"], bus1_summary["bess_status"])

    def test_06_child_feeder_and_der_routes(self):
        """TEST 6: Child feeder (/feeder/1..4), /solar/A, /bess/A routes require auth and render when authenticated."""
        unauth_client = self.app.test_client()
        routes = ["/feeder/1", "/feeder/2", "/feeder/3", "/feeder/4", "/solar/A", "/bess/A"]

        # Unauthenticated: Redirects to /login
        for route in routes:
            res_unauth = unauth_client.get(route, follow_redirects=False)
            self.assertEqual(res_unauth.status_code, 302, f"Route {route} should redirect when unauthenticated")
            self.assertIn("/login", res_unauth.headers.get("Location", ""))

        # Authenticated: Returns 200
        self._login()
        for route in routes:
            res_auth = self.client.get(route)
            self.assertEqual(res_auth.status_code, 200, f"Route {route} should render 200 when authenticated")


if __name__ == "__main__":
    unittest.main()
