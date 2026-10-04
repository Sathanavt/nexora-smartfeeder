"""
SmartFeeder EMS — Admin Control & Role-Based Access Control Automated Test Suite
Verifies all 12 test specifications defined in the Admin Control specification.
"""
import unittest
import json
import os
import sys

# Ensure root directory is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app import create_app
from backend.config import Config
from backend.auth.user_model import user_repository

class TestAdminControl(unittest.TestCase):
    def setUp(self):
        self.app = create_app(Config)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.admin_username = Config.ADMIN_USERNAME
        self.admin_password = Config.ADMIN_PASSWORD

        # Clean up test users to guarantee test repeatability
        test_usernames = [
            "dispatcher_01", "dispatcher_renamed", "normal_operator",
            "dispatcher_pw", "dispatcher_to_disable", "user_to_delete"
        ]
        for u in test_usernames:
            existing = user_repository.get_by_username(u)
            if existing:
                user_repository.delete_user(existing.user_id)

        # Ensure default admin is active and has default password
        admin = user_repository.get_by_username(self.admin_username)
        if admin:
            admin.role = "ADMIN"
            admin.status = "ACTIVE"
            admin.set_password(self.admin_password)
            user_repository._save_to_disk()

    def tearDown(self):
        test_usernames = [
            "dispatcher_01", "dispatcher_renamed", "normal_operator",
            "dispatcher_pw", "dispatcher_to_disable", "user_to_delete"
        ]
        for u in test_usernames:
            existing = user_repository.get_by_username(u)
            if existing:
                user_repository.delete_user(existing.user_id)

    def _login(self, username, password):
        return self.client.post("/api/auth/login",
                               data=json.dumps({"username": username, "password": password}),
                               content_type="application/json")

    def test_01_admin_login_shows_clickable_admin_control(self):
        """TEST 1: Login as ADMIN -> Admin control is visible and clickable in header."""
        res_login = self._login(self.admin_username, self.admin_password)
        self.assertEqual(res_login.status_code, 200)

        res_home = self.client.get("/")
        self.assertEqual(res_home.status_code, 200)
        html = res_home.data.decode("utf-8")
        
        # Must contain link to /admin
        self.assertIn('href="/admin"', html)
        self.assertIn('user-chip-admin', html)
        self.assertIn(self.admin_username, html)

    def test_02_admin_clicks_admin_control_opens_page(self):
        """TEST 2: Navigate to /admin as ADMIN -> /admin opens with 200."""
        self._login(self.admin_username, self.admin_password)
        res_admin = self.client.get("/admin")
        self.assertEqual(res_admin.status_code, 200)
        html = res_admin.data.decode("utf-8")
        
        self.assertIn("ADMIN CONTROL", html)
        self.assertIn("USER MANAGEMENT", html)
        self.assertIn("Back to Home", html)
        self.assertIn('href="/"', html)

    def test_03_user_login_does_not_render_admin_control_link(self):
        """TEST 3: Login as USER -> Admin control link is not rendered in header."""
        # Create normal user
        user_repository.create_user("normal_operator", "OperatorPass123!", role="USER", status="ACTIVE")
        
        user_client = self.app.test_client()
        res_login = user_client.post("/api/auth/login",
                                    data=json.dumps({"username": "normal_operator", "password": "OperatorPass123!"}),
                                    content_type="application/json")
        self.assertEqual(res_login.status_code, 200)

        res_home = user_client.get("/")
        self.assertEqual(res_home.status_code, 200)
        html = res_home.data.decode("utf-8")
        
        # Must NOT contain link to /admin
        self.assertNotIn('href="/admin"', html)
        self.assertIn('user-chip-static', html)
        self.assertIn('normal_operator', html)

    def test_04_user_cannot_access_admin_route_or_apis(self):
        """TEST 4: As USER, manual navigation to /admin or admin APIs is blocked (403/redirect)."""
        user_repository.create_user("normal_operator", "OperatorPass123!", role="USER", status="ACTIVE")
        user_client = self.app.test_client()
        user_client.post("/api/auth/login",
                         data=json.dumps({"username": "normal_operator", "password": "OperatorPass123!"}),
                         content_type="application/json")

        # Page route redirects to /
        res_page = user_client.get("/admin", follow_redirects=False)
        self.assertEqual(res_page.status_code, 302)
        self.assertEqual(res_page.headers.get("Location", ""), "/")

        # API returns 403 Forbidden
        res_api = user_client.get("/api/admin/users")
        self.assertEqual(res_api.status_code, 403)
        data = res_api.get_json()
        self.assertFalse(data["success"])
        self.assertIn("Administrator privileges required", data["error"])

    def test_05_admin_creates_user(self):
        """TEST 5: As ADMIN, create a USER -> user appears in list."""
        self._login(self.admin_username, self.admin_password)

        new_user_data = {
            "username": "dispatcher_01",
            "password": "SecurePassword2026!",
            "confirm_password": "SecurePassword2026!",
            "role": "USER",
            "status": "ACTIVE"
        }
        res_create = self.client.post("/api/admin/users",
                                     data=json.dumps(new_user_data),
                                     content_type="application/json")
        self.assertEqual(res_create.status_code, 201)
        created_user = res_create.get_json()["user"]
        self.assertEqual(created_user["username"], "dispatcher_01")
        self.assertEqual(created_user["role"], "USER")

        # Verify appears in list
        res_list = self.client.get("/api/admin/users")
        self.assertEqual(res_list.status_code, 200)
        usernames = [u["username"] for u in res_list.get_json()["users"]]
        self.assertIn("dispatcher_01", usernames)

    def test_06_admin_edits_user(self):
        """TEST 6: Edit the USER -> updated information is saved."""
        self._login(self.admin_username, self.admin_password)
        target, _ = user_repository.create_user("dispatcher_edit", "SecurePassword2026!", role="USER", status="ACTIVE")
        self.assertIsNotNone(target)

        update_payload = {
            "username": "dispatcher_renamed",
            "role": "USER",
            "status": "ACTIVE"
        }
        res_update = self.client.put(f"/api/admin/users/{target.user_id}",
                                    data=json.dumps(update_payload),
                                    content_type="application/json")
        self.assertEqual(res_update.status_code, 200)
        self.assertEqual(res_update.get_json()["user"]["username"], "dispatcher_renamed")

    def test_07_admin_resets_user_password(self):
        """TEST 7: Change/reset the USER password -> password is securely updated."""
        self._login(self.admin_username, self.admin_password)
        target, _ = user_repository.create_user("dispatcher_pw", "OriginalPassword2026!", role="USER", status="ACTIVE")
        self.assertIsNotNone(target)

        reset_payload = {
            "new_password": "BrandNewPassword2026!",
            "confirm_password": "BrandNewPassword2026!"
        }
        res_reset = self.client.post(f"/api/admin/users/{target.user_id}/password",
                                    data=json.dumps(reset_payload),
                                    content_type="application/json")
        self.assertEqual(res_reset.status_code, 200)

        # Verify user can log in with new password
        test_client = self.app.test_client()
        res_login = test_client.post("/api/auth/login",
                                    data=json.dumps({"username": "dispatcher_pw", "password": "BrandNewPassword2026!"}),
                                    content_type="application/json")
        self.assertEqual(res_login.status_code, 200)

    def test_08_disable_user_blocks_login(self):
        """TEST 8: Disable the USER -> that user cannot log in."""
        self._login(self.admin_username, self.admin_password)
        target, _ = user_repository.create_user("dispatcher_to_disable", "BrandNewPassword2026!", role="USER", status="ACTIVE")
        self.assertIsNotNone(target)

        res_disable = self.client.patch(f"/api/admin/users/{target.user_id}/status",
                                       data=json.dumps({"status": "DISABLED"}),
                                       content_type="application/json")
        self.assertEqual(res_disable.status_code, 200)

        # Login attempt with disabled user must be rejected
        test_client = self.app.test_client()
        res_login = test_client.post("/api/auth/login",
                                    data=json.dumps({"username": "dispatcher_to_disable", "password": "BrandNewPassword2026!"}),
                                    content_type="application/json")
        self.assertIn(res_login.status_code, [400, 401, 403])
        self.assertIn("Account disabled", res_login.get_json()["error"])

    def test_09_change_admin_password(self):
        """TEST 9: Change ADMIN password -> new password works for next authentication."""
        self._login(self.admin_username, self.admin_password)

        new_admin_pw = "NewAdminPassword@2026!"
        pw_payload = {
            "current_password": self.admin_password,
            "new_password": new_admin_pw,
            "confirm_password": new_admin_pw
        }
        res_pw = self.client.post("/api/admin/account/password",
                                 data=json.dumps(pw_payload),
                                 content_type="application/json")
        self.assertEqual(res_pw.status_code, 200)

        # Verify next login requires new password
        new_client = self.app.test_client()
        res_old = new_client.post("/api/auth/login",
                                  data=json.dumps({"username": self.admin_username, "password": self.admin_password}),
                                  content_type="application/json")
        self.assertEqual(res_old.status_code, 401)

        res_new = new_client.post("/api/auth/login",
                                  data=json.dumps({"username": self.admin_username, "password": new_admin_pw}),
                                  content_type="application/json")
        self.assertEqual(res_new.status_code, 200)

        # Restore original password for other tests
        restore_payload = {
            "current_password": new_admin_pw,
            "new_password": self.admin_password,
            "confirm_password": self.admin_password
        }
        new_client.post("/api/admin/account/password",
                        data=json.dumps(restore_payload),
                        content_type="application/json")

    def test_10_safeguard_prevents_removing_only_active_admin(self):
        """TEST 10: Attempt to remove or disable the only active ADMIN -> operation blocked."""
        self._login(self.admin_username, self.admin_password)
        admin_user = user_repository.get_by_username(self.admin_username)

        # Try to disable
        res_disable = self.client.patch(f"/api/admin/users/{admin_user.user_id}/status",
                                       data=json.dumps({"status": "DISABLED"}),
                                       content_type="application/json")
        self.assertEqual(res_disable.status_code, 400)
        self.assertIn("At least one active administrator account must remain available", res_disable.get_json()["error"])

        # Try to delete
        res_delete = self.client.delete(f"/api/admin/users/{admin_user.user_id}")
        self.assertEqual(res_delete.status_code, 400)
        self.assertIn("At least one active administrator account must remain available", res_delete.get_json()["error"])

    def test_11_back_to_home_button_navigates_to_home(self):
        """TEST 11: Back to Home button navigates to Home Dashboard."""
        self._login(self.admin_username, self.admin_password)
        res = self.client.get("/admin")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertIn('href="/"', html)
        self.assertIn("Back to Home", html)

    def test_12_logout_invalidates_session(self):
        """TEST 12: Logout invalidates session and redirects to /login."""
        self._login(self.admin_username, self.admin_password)
        res_logout = self.client.post("/api/auth/logout")
        self.assertEqual(res_logout.status_code, 200)

        res_admin = self.client.get("/admin", follow_redirects=False)
        self.assertEqual(res_admin.status_code, 302)
        self.assertIn("/login", res_admin.headers.get("Location", ""))


if __name__ == "__main__":
    unittest.main()
