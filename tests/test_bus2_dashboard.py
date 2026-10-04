"""
SmartFeeder EMS — BUS-2 Detailed Dashboard (Page 4) Automated Test Suite
Verifies BUS-2 route, authentication protection, engineering calculations,
consistency with Home Dashboard, Feeder 5-8 data, Solar-B, BESS-B,
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


class TestBus2Dashboard(unittest.TestCase):
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

    def test_01_unauthenticated_bus2_redirects_to_login(self):
        """TEST 1: Unauthenticated access to /bus/2 redirects to /login."""
        res = self.client.get("/bus/2", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

    def test_02_unauthenticated_api_bus2_live_returns_401(self):
        """TEST 2: Unauthenticated access to /api/bus/2/live returns 401."""
        res = self.client.get("/api/bus/2/live")
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data["success"])

    def test_03_authenticated_bus2_renders_successfully(self):
        """TEST 3: Authenticated access renders BUS-2 Detailed Dashboard with required elements."""
        self._login()
        res = self.client.get("/bus/2")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")

        # Headings & Subtitles
        self.assertIn("BUS-2", html)
        self.assertIn("11 kV Distribution Bus — Detailed Asset & Telemetry Overview", html)
        self.assertIn("BUS-2 • 4 Feeders • Solar-B • BESS-B", html)

        # Breadcrumb & Navigation
        self.assertIn("← Back to Home", html)
        self.assertIn('href="/"', html)

        # BUS-2 Summary Card
        self.assertIn("BUS-2 STATUS", html)
        self.assertIn("Current Bus Demand", html)
        self.assertIn("Bus Voltage", html)
        self.assertIn("Bus Current", html)
        self.assertIn("Bus Frequency", html)
        self.assertIn("Solar Status", html)
        self.assertIn("BESS Status", html)

        # Feeders Section
        self.assertIn("BUS-2 FEEDERS", html)
        self.assertIn("FEEDER-5", html)
        self.assertIn("FEEDER-6", html)
        self.assertIn("FEEDER-7", html)
        self.assertIn("FEEDER-8", html)

        # Clickable Feeder Links
        self.assertIn('href="/feeder/5"', html)
        self.assertIn('href="/feeder/6"', html)
        self.assertIn('href="/feeder/7"', html)
        self.assertIn('href="/feeder/8"', html)

        # Solar-B & BESS-B Assets
        self.assertIn("SOLAR-B", html)
        self.assertIn("420 kW Installed Capacity", html)
        self.assertIn('href="/solar/B"', html)

        self.assertIn("BESS-B", html)
        self.assertIn("Operating Window: 15% – 90%", html)
        self.assertIn('href="/bess/B"', html)

        # Footer Credit
        self.assertIn("Team Nexora", html)

    def test_04_api_bus2_live_telemetry_calculations(self):
        """TEST 4: Verify /api/bus/2/live returns dataset-backed, mathematically consistent values."""
        self._login()
        res = self.client.get("/api/bus/2/live")
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertTrue(json_data["success"])
        data = json_data["data"]

        summary = data["summary"]
        feeders = data["feeders"]
        solar_b = data["solar_b"]
        bess_b = data["bess_b"]

        # 1. BUS-2 Demand equals sum of Feeders 5 to 8
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

        # 5. Solar-B Rules: Capacity <= 420 kW, Status ACTIVE if >= 8 kW else INACTIVE
        self.assertLessEqual(solar_b["generation_kw"], 420.0)
        if solar_b["generation_kw"] >= 8.0:
            self.assertEqual(solar_b["status"], "ACTIVE")
        else:
            self.assertEqual(solar_b["status"], "INACTIVE")

        # 6. BESS-B Power and Status agreement
        self.assertIn(bess_b["status"], ["CHARGING", "DISCHARGING", "IDLE"])
        self.assertGreaterEqual(bess_b["soc_pct"], 0.0)
        self.assertLessEqual(bess_b["soc_pct"], 100.0)

        # 7. Feeders 5 to 8 Validations
        self.assertEqual(len(feeders), 4)
        for f in feeders:
            self.assertIn(f["id"], [5, 6, 7, 8])
            self.assertGreaterEqual(f["voltage_kv"], 10.80)
            self.assertLessEqual(f["voltage_kv"], 12.00)
            self.assertGreaterEqual(f["frequency_hz"], 49.90)
            self.assertLessEqual(f["frequency_hz"], 50.10)
            self.assertGreaterEqual(f["power_factor"], 0.90)
            self.assertLessEqual(f["power_factor"], 0.99)
            self.assertEqual(f["route"], f"/feeder/{f['id']}")

    def test_05_consistency_between_home_and_bus2(self):
        """TEST 5: Ensure BUS-2 telemetry values match Home Dashboard BUS-2 card for same dataset record."""
        self._login()

        # Fetch Home live telemetry
        res_home = self.client.get("/api/dashboard/live")
        self.assertEqual(res_home.status_code, 200)
        home_bus2 = res_home.get_json()["data"]["bus2"]

        # Fetch BUS-2 live telemetry
        res_bus2 = self.client.get("/api/bus/2/live")
        self.assertEqual(res_bus2.status_code, 200)
        bus2_summary = res_bus2.get_json()["data"]["summary"]

        # Compare values
        self.assertEqual(home_bus2["demand_kw"], bus2_summary["demand_kw"])
        self.assertEqual(home_bus2["voltage_kv"], bus2_summary["voltage_kv"])
        self.assertEqual(home_bus2["current_a"], bus2_summary["current_a"])
        self.assertEqual(home_bus2["frequency_hz"], bus2_summary["frequency_hz"])
        self.assertEqual(home_bus2["solar_status"], bus2_summary["solar_status"])
        self.assertEqual(home_bus2["bess_status"], bus2_summary["bess_status"])

    def test_06_child_feeder_and_der_routes(self):
        """TEST 6: Child feeder (/feeder/5..8), /solar/B, /bess/B routes require auth and render when authenticated."""
        unauth_client = self.app.test_client()
        routes = ["/feeder/5", "/feeder/6", "/feeder/7", "/feeder/8", "/solar/B", "/bess/B"]

        # Unauthenticated: Redirects to /login
        for route in routes:
            res_unauth = unauth_client.get(route, follow_redirects=False)
            self.assertEqual(res_unauth.status_code, 302, f"Route {route} should redirect when unauthenticated")
            self.assertIn("/login", res_unauth.headers.get("Location", ""))

        # Authenticated: Returns 200 with back_url pointing to /bus/2
        self._login()
        for route in routes:
            res_auth = self.client.get(route)
            self.assertEqual(res_auth.status_code, 200, f"Route {route} should render 200 when authenticated")
            html = res_auth.data.decode("utf-8")
            self.assertIn('href="/bus/2"', html)


if __name__ == "__main__":
    unittest.main()
