"""
SmartFeeder EMS — Automated Authentication & Acceptance Test Suite
Tests all 12 test requirements specified in the SmartFeeder EMS specification,
plus final visual acceptance criteria.
"""
import unittest
import json
import os
import sys

# Ensure root directory is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app import create_app
from backend.config import Config

class TestSmartFeederAuth(unittest.TestCase):
    def setUp(self):
        self.app = create_app(Config)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.valid_username = Config.ADMIN_USERNAME
        self.valid_password = Config.ADMIN_PASSWORD

    def test_01_unauthenticated_dashboard_redirects_to_login(self):
        """TEST 1: Open dashboard URL (/) -> Redirects to /login."""
        response = self.client.get("/", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertTrue("/login" in response.headers.get("Location", ""))

    def test_02_empty_submission_validation(self):
        """TEST 2: Submit completely empty form -> Username is required. Password is required."""
        response = self.client.post("/api/auth/login",
                                  data=json.dumps({"username": "", "password": ""}),
                                  content_type="application/json")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Username is required", data["error"])

    def test_03_username_only_validation(self):
        """TEST 3: Enter username but no password -> Password is required."""
        response = self.client.post("/api/auth/login",
                                  data=json.dumps({"username": "admin", "password": ""}),
                                  content_type="application/json")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Password is required", data["error"])

    def test_04_password_only_validation(self):
        """TEST 4: Enter password but no username -> Username is required."""
        response = self.client.post("/api/auth/login",
                                  data=json.dumps({"username": "", "password": "anyPassword"}),
                                  content_type="application/json")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Username is required", data["error"])

    def test_05_invalid_credentials_rejected(self):
        """TEST 5: Enter invalid credentials -> Invalid username or password."""
        response = self.client.post("/api/auth/login",
                                  data=json.dumps({"username": "wrong_user", "password": "wrong_password"}),
                                  content_type="application/json")
        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Invalid username or password.")

    def test_06_valid_credentials_succeeds(self):
        """TEST 6: Enter valid credentials -> Authentication succeeds, session set."""
        response = self.client.post("/api/auth/login",
                                  data=json.dumps({"username": self.valid_username, "password": self.valid_password}),
                                  content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["user"]["username"], self.valid_username)
        self.assertEqual(data["redirect"], "/")

        # Check that protected route can now be accessed with this session
        home_res = self.client.get("/")
        self.assertEqual(home_res.status_code, 200)
        self.assertIn(b"SmartFeeder", home_res.data)
        self.assertIn(b"HOME DASHBOARD", home_res.data)
        self.assertIn(b"BUS-1 STATUS", home_res.data)

    def test_07_protected_home_route_requires_auth(self):
        """TEST 7: Open protected Home route without authentication -> Redirects to /login."""
        fresh_client = self.app.test_client()
        res = fresh_client.get("/")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

    def test_08_session_persistence_across_page_refresh(self):
        """TEST 8: After successful login, refresh the page -> Session persists."""
        self.client.post("/api/auth/login",
                        data=json.dumps({"username": self.valid_username, "password": self.valid_password}),
                        content_type="application/json")
        
        # First page access
        res1 = self.client.get("/")
        self.assertEqual(res1.status_code, 200)

        # Second page access (simulating refresh)
        res2 = self.client.get("/")
        self.assertEqual(res2.status_code, 200)
        self.assertIn(b"SmartFeeder", res2.data)

        # Visiting /login while authenticated should redirect to /
        login_res = self.client.get("/login", follow_redirects=False)
        self.assertEqual(login_res.status_code, 302)

    def test_09_logout_invalidates_session(self):
        """TEST 9: Logout using the backend logout mechanism -> Session is invalidated."""
        self.client.post("/api/auth/login",
                        data=json.dumps({"username": self.valid_username, "password": self.valid_password}),
                        content_type="application/json")
        
        # Verify authenticated
        res_auth = self.client.get("/")
        self.assertEqual(res_auth.status_code, 200)

        # Call logout endpoint
        logout_res = self.client.post("/api/auth/logout")
        self.assertEqual(logout_res.status_code, 200)
        data = logout_res.get_json()
        self.assertTrue(data["success"])

        # Attempt to access protected route after logout -> redirects to /login
        res_after = self.client.get("/", follow_redirects=False)
        self.assertEqual(res_after.status_code, 302)
        self.assertIn("/login", res_after.headers.get("Location", ""))

    def test_10_api_me_endpoint_requires_auth(self):
        """Verify GET /api/auth/me returns 401 when not logged in and 200 when logged in."""
        unauth_client = self.app.test_client()
        res = unauth_client.get("/api/auth/me")
        self.assertEqual(res.status_code, 401)

        # Log in
        self.client.post("/api/auth/login",
                        data=json.dumps({"username": self.valid_username, "password": self.valid_password}),
                        content_type="application/json")
        me_res = self.client.get("/api/auth/me")
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.get_json()["user"]["username"], self.valid_username)

    def test_11_login_template_rendered_elements(self):
        """Verify login.html contains required fields and accessibility attributes."""
        res = self.client.get("/login")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn("SmartFeeder", html)
        self.assertIn("Intelligent Renewable Management at Feeder Level", html)
        self.assertIn('id="usernameInput"', html)
        self.assertIn('placeholder="Enter your username"', html)
        self.assertIn('id="passwordInput"', html)
        self.assertIn('placeholder="Enter your password"', html)
        self.assertIn('id="togglePasswordBtn"', html)
        self.assertIn('id="loginSubmitBtn"', html)
        self.assertIn('id="authAlert"', html)
        # Check exact required footer message
        self.assertIn("Developed for Schneider Yuva Yodha by <strong>Team Nexora</strong>", html)

    def test_12_removed_scada_and_technical_blocks_absent(self):
        """Verify removed SCADA blocks and technical text are NOT in login page."""
        res = self.client.get("/login")
        html = res.data.decode("utf-8")
        self.assertNotIn("SUBSTATION 110/11 KV STATUS", html)
        self.assertNotIn("GRID SYNCHRONIZED", html)
        self.assertNotIn("BUS TOPOLOGY", html)
        self.assertNotIn("ACTIVE FEEDERS", html)
        self.assertNotIn("DER INTEGRATION", html)
        self.assertNotIn("FIPS-Compliant Auth", html)
        self.assertNotIn("TLS 256-bit Session", html)
        self.assertNotIn("11 KV DISTRIBUTION SCADA", html)

    def test_13_security_headers_present(self):
        """Verify response security headers are set properly."""
        res = self.client.get("/login")
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(res.headers.get("X-XSS-Protection"), "1; mode=block")

    def test_14_home_route_requires_auth(self):
        """Verify unauthenticated access to /home redirects to /login."""
        res = self.client.get("/home", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

    def test_15_all_default_seeded_accounts_authenticate(self):
        """Verify all seeded authorized accounts authenticate with their respective passwords."""
        accounts = [
            ("admin", "Admin@123", "ADMIN"),
            ("engineer", "Engg@123", "ENGINEER"),
            ("operator", "Oper@123", "OPERATOR"),
            ("viewer", "View@123", "VIEWER"),
        ]
        for uname, pwd, expected_role in accounts:
            client = self.app.test_client()
            res = client.post("/api/auth/login",
                              data=json.dumps({"username": uname, "password": pwd}),
                              content_type="application/json")
            self.assertEqual(res.status_code, 200, f"Account {uname} failed to authenticate")
            data = res.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["user"]["username"], uname)
            self.assertEqual(data["user"]["role"], expected_role)

            # Protected / and /home should open
            home_res = client.get("/home")
            self.assertEqual(home_res.status_code, 200)

    def test_16_no_exposed_default_credentials_table_in_frontend(self):
        """Verify no visible 'Default User Credentials' table or exposed passwords appear in login page."""
        res = self.client.get("/login")
        html = res.data.decode("utf-8")
        self.assertNotIn("Default User Credentials", html)
        self.assertNotIn("Admin@123", html)
        self.assertNotIn("Engg@123", html)
        self.assertNotIn("Oper@123", html)
        self.assertNotIn("View@123", html)


if __name__ == "__main__":
    unittest.main()
