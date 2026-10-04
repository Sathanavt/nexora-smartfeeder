"""
SmartFeeder EMS — Home Dashboard (Page 2) Automated Test Suite
Verifies data integration, engineering calculations, protected routing,
and UI template criteria.
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

class TestHomeDashboard(unittest.TestCase):
    def setUp(self):
        self.app = create_app(Config)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.valid_username = Config.ADMIN_USERNAME
        self.valid_password = Config.ADMIN_PASSWORD

    def _login(self):
        """Helper to establish an authenticated session."""
        return self.client.post("/api/auth/login",
                               data=json.dumps({"username": self.valid_username, "password": self.valid_password}),
                               content_type="application/json")

    def test_01_unauthenticated_home_redirects_to_login(self):
        """Unauthenticated access to Home Dashboard redirects to /login."""
        res = self.client.get("/", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

    def test_02_unauthenticated_api_live_returns_401(self):
        """Unauthenticated access to /api/dashboard/live returns 401."""
        res = self.client.get("/api/dashboard/live")
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data["success"])

    def test_03_authenticated_home_dashboard_renders_successfully(self):
        """Authenticated access renders Home Dashboard with required hierarchy."""
        self._login()
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")

        # Headings
        self.assertIn("HOME DASHBOARD", html)
        self.assertIn("11 kV Feeder-Level Energy Management Overview", html)

        # 3 Major Cards
        self.assertIn("BUS-1 STATUS", html)
        self.assertIn("BUS-2 STATUS", html)
        self.assertIn("EMS STATUS", html)

        # Card Links
        self.assertIn('href="/bus/1"', html)
        self.assertIn('href="/bus/2"', html)
        self.assertIn('href="/ems"', html)

        # Secondary Metrics
        self.assertIn("TOTAL FEEDER DEMAND", html)
        self.assertIn("TOTAL SOLAR GENERATION", html)
        self.assertIn("TOTAL GRID IMPORT", html)
        self.assertIn("BESS-A SOC", html)
        self.assertIn("BESS-B SOC", html)

        # Status Strip
        self.assertIn("SUBSTATION", html)
        self.assertIn("ONLINE", html)

        # No Back button to /login
        self.assertNotIn('href="/login"', html)

        # Footer Credit
        self.assertIn("Developed for Schneider Yuva Yodha by <strong>Team Nexora</strong>", html)

    def test_04_api_live_telemetry_returns_calculated_metrics(self):
        """Verify /api/dashboard/live returns correct engineering calculations."""
        self._login()
        res = self.client.get("/api/dashboard/live")
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertTrue(json_data["success"])
        data = json_data["data"]

        # Validate BUS-1
        b1 = data["bus1"]
        self.assertIn("demand_kw", b1)
        self.assertIn("voltage_kv", b1)
        self.assertIn("current_a", b1)
        self.assertIn("frequency_hz", b1)

        # Voltage limits: 10.8 <= V <= 12.0
        self.assertGreaterEqual(b1["voltage_kv"], 10.8)
        self.assertLessEqual(b1["voltage_kv"], 12.0)

        # Frequency limits: 49.9 <= f <= 50.1
        self.assertGreaterEqual(b1["frequency_hz"], 49.9)
        self.assertLessEqual(b1["frequency_hz"], 50.1)

        # 3-Phase Current Equation: I = P / (sqrt(3) * V * PF)
        if b1["demand_kw"] > 0:
            expected_current = b1["demand_kw"] / (math.sqrt(3) * b1["voltage_kv"] * 0.95)
            self.assertAlmostEqual(b1["current_a"], expected_current, delta=0.2)

        # Validate BUS-2
        b2 = data["bus2"]
        self.assertGreaterEqual(b2["voltage_kv"], 10.8)
        self.assertLessEqual(b2["voltage_kv"], 12.0)
        self.assertGreaterEqual(b2["frequency_hz"], 49.9)
        self.assertLessEqual(b2["frequency_hz"], 50.1)

        # Solar rules: < 8 kW -> INACTIVE, >= 8 kW -> ACTIVE
        if b1["solar_gen_kw"] >= 8.0:
            self.assertEqual(b1["solar_status"], "ACTIVE")
        else:
            self.assertEqual(b1["solar_status"], "INACTIVE")

        # Validate Summary Metrics
        summary = data["summary"]
        expected_total_demand = round(b1["demand_kw"] + b2["demand_kw"], 1)
        self.assertEqual(summary["total_feeder_demand_kw"], expected_total_demand)

    def test_05_protected_child_routes(self):
        """Verify /bus/1, /bus/2, /ems are protected by authentication."""
        # Unauthenticated access
        unauth_client = self.app.test_client()
        for route in ["/bus/1", "/bus/2", "/ems"]:
            res = unauth_client.get(route, follow_redirects=False)
            self.assertEqual(res.status_code, 302, f"Route {route} should redirect when unauthenticated")
            self.assertIn("/login", res.headers.get("Location", ""))

        # Authenticated access
        self._login()
        for route in ["/bus/1", "/bus/2", "/ems"]:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200, f"Route {route} should render when authenticated")

    def test_06_login_page_remains_intact(self):
        """Verify Page 1 Login page still renders with exact light theme and elements."""
        res = self.client.get("/login")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn("SmartFeeder", html)
        self.assertIn("Welcome Back", html)
        self.assertIn("Developed for Schneider Yuva Yodha by <strong>Team Nexora</strong>", html)

    def test_07_admin_indicator_role_based_behavior(self):
        """Verify admin user indicator is a link for ADMIN, and static div for normal USER."""
        from backend.auth.user_model import user_repository
        
        # When logged in as ADMIN -> renders link to /admin
        self._login()
        res_admin = self.client.get("/")
        self.assertEqual(res_admin.status_code, 200)
        html_admin = res_admin.data.decode("utf-8")
        self.assertIn('<a href="/admin" class="user-chip user-chip-admin"', html_admin)
        self.assertIn('<span class="user-name">admin</span>', html_admin)

        # When logged in as normal USER -> renders static div
        user_repository.create_user("temp_operator", "Pass1234!", role="USER", status="ACTIVE")
        user_client = self.app.test_client()
        user_client.post("/api/auth/login",
                         data=json.dumps({"username": "temp_operator", "password": "Pass1234!"}),
                         content_type="application/json")
        res_user = user_client.get("/")
        self.assertEqual(res_user.status_code, 200)
        html_user = res_user.data.decode("utf-8")
        self.assertIn('<div class="user-chip user-chip-static"', html_user)
        self.assertIn('<span class="user-name">temp_operator</span>', html_user)
        
        # Cleanup
        u = user_repository.get_by_username("temp_operator")
        if u:
            user_repository.delete_user(u.user_id)
        
        # Logout button remains functional button
        self.assertIn('<button id="shellLogoutBtn"', html_admin)

    def test_09_global_background_rendered_across_pages(self):
        """Verifies root layout includes the global background elements and background.css."""
        # Unauthenticated login page
        login_res = self.client.get("/login")
        self.assertEqual(login_res.status_code, 200)
        login_html = login_res.data.decode("utf-8")
        self.assertIn("global-background-container", login_html)
        self.assertIn("global-background-image", login_html)
        self.assertIn("global-background-overlay", login_html)
        self.assertIn("background.css", login_html)

        # Authenticated Home Dashboard
        self._login()
        home_res = self.client.get("/")
        self.assertEqual(home_res.status_code, 200)
        home_html = home_res.data.decode("utf-8")
        self.assertIn("global-background-container", home_html)
        self.assertIn("global-background-image", home_html)
        self.assertIn("global-background-overlay", home_html)
        self.assertIn("background.css", home_html)


if __name__ == "__main__":
    unittest.main()
