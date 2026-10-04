"""
SmartFeeder EMS — Solar Detailed Analysis Automated Test Suite
Verifies all 43 technical validation criteria for Solar-A (495 kW, BUS-1, ID 114)
and Solar-B (420 kW, BUS-2, ID 166).
"""
import unittest
import json
import os
import sys
import re
import io
import openpyxl

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app import create_app
from backend.config import Config
from backend.solar_config import SOLAR_REGISTRY, get_solar_config
from backend.solar_service import SolarService
from backend.forecast_service import ForecastService

class TestSolarAnalysis(unittest.TestCase):
    def setUp(self):
        self.app = create_app(Config)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

        # Log in as authorized user
        res = self.client.post("/api/auth/login",
                               data=json.dumps({"username": "admin", "password": "Admin@123"}),
                               content_type="application/json")
        self.assertEqual(res.status_code, 200, "Admin login must succeed")

    def test_01_solar_asset_definitions_frozen(self):
        """TEST 1: Solar-A and Solar-B fixed definitions match requirements exactly."""
        # Solar-A
        cfg_a = get_solar_config("a")
        self.assertEqual(cfg_a["name"], "Solar-A")
        self.assertEqual(cfg_a["bus"], "BUS-1")
        self.assertEqual(cfg_a["capacity_kw"], 495.0)
        self.assertEqual(cfg_a["source_id"], 114)
        self.assertEqual(cfg_a["bus_route"], "/bus/1")

        # Solar-B
        cfg_b = get_solar_config("b")
        self.assertEqual(cfg_b["name"], "Solar-B")
        self.assertEqual(cfg_b["bus"], "BUS-2")
        self.assertEqual(cfg_b["capacity_kw"], 420.0)
        self.assertEqual(cfg_b["source_id"], 166)
        self.assertEqual(cfg_b["bus_route"], "/bus/2")

    def test_02_solar_a_page_rendering_and_metadata(self):
        """TEST 2: /solar/a renders correctly with Solar-A metadata, back button, and breadcrumbs."""
        res = self.client.get("/solar/a")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        
        self.assertIn("SOLAR-A", html)
        self.assertIn("495 kW Installed Capacity", html)
        self.assertIn("BUS-1", html)
        self.assertIn("ID 114", html)
        self.assertIn("Back to BUS-1", html)
        self.assertIn('href="/bus/1"', html)

        # Breadcrumb check
        plain_text = " ".join(re.sub(r"<[^>]+>", " ", html).split())
        self.assertIn("Home / BUS-1 / SOLAR-A", plain_text)

    def test_03_solar_b_page_rendering_and_metadata(self):
        """TEST 3: /solar/b renders correctly with Solar-B metadata, back button, and breadcrumbs."""
        res = self.client.get("/solar/b")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        
        self.assertIn("SOLAR-B", html)
        self.assertIn("420 kW Installed Capacity", html)
        self.assertIn("BUS-2", html)
        self.assertIn("ID 166", html)
        self.assertIn("Back to BUS-2", html)
        self.assertIn('href="/bus/2"', html)

        # Breadcrumb check
        plain_text = " ".join(re.sub(r"<[^>]+>", " ", html).split())
        self.assertIn("Home / BUS-2 / SOLAR-B", plain_text)

    def test_04_solar_api_date_telemetry_and_physical_limits(self):
        """TEST 4: API returns valid telemetry, never exceeding capacity and never negative."""
        for plant, cap in [("a", 495.0), ("b", 420.0)]:
            res = self.client.get(f"/api/solar/{plant}/data?date=2026-09-29")
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data["success"])
            telemetry = data["data"]
            self.assertTrue(telemetry["available"])
            self.assertEqual(len(telemetry["hourly"]), 24)

            for rec in telemetry["hourly"]:
                actual = rec["actual_generation_kw"]
                forecast = rec["forecast_generation_kw"]
                utilized = rec["utilized_kw"]

                # Non-negative
                self.assertGreaterEqual(actual, 0.0)
                self.assertGreaterEqual(forecast, 0.0)
                self.assertGreaterEqual(utilized, 0.0)

                # Clamped to installed capacity
                self.assertLessEqual(actual, cap)
                self.assertLessEqual(forecast, cap)
                self.assertLessEqual(utilized, actual)

                # Night-time logic: between 21:00 and 04:00, solar should be zero or negligible
                if rec["hour"] in (0, 1, 2, 3, 22, 23):
                    self.assertLessEqual(actual, 0.5, f"Hour {rec['hour']} should have near-zero solar")
                    self.assertLessEqual(forecast, 0.5, f"Hour {rec['hour']} forecast should be near-zero")

    def test_05_pre_dataset_date_availability_rule(self):
        """TEST 5: Selecting dates before 05-Aug-2026 returns available=False with exact guidance."""
        for plant in ["a", "b"]:
            res = self.client.get(f"/api/solar/{plant}/data?date=2026-07-15")
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            telemetry = data["data"]
            self.assertFalse(telemetry["available"])
            self.assertEqual(telemetry["message"], "DATA NOT AVAILABLE")
            self.assertIn("Historical solar data is available from 05-Aug-2026", telemetry["info"])

    def test_06_power_balance_and_utilization_logic(self):
        """TEST 6: Solar power balance logic ensures physical consistency."""
        res = self.client.get("/api/solar/a/data?date=2026-09-29")
        telemetry = res.get_json()["data"]
        
        for rec in telemetry["hourly"]:
            actual = rec["actual_generation_kw"]
            utilized = rec["utilized_kw"]
            export_grid = rec["grid_import_kw"]
            bess_import = rec["bess_import_kw"]

            # Utilized can never exceed actual generation
            self.assertLessEqual(utilized, actual + 0.01)

            # Export to grid + Utilized equals actual generation (within rounding precision)
            self.assertAlmostEqual(actual, utilized + export_grid, delta=0.1)

            # BESS import cannot exceed actual generation
            self.assertLessEqual(bess_import, actual + 0.01)

    def test_07_excel_download_generation(self):
        """TEST 7: Excel report downloads successfully with Hourly and Daily Summary sheets."""
        for plant in ["a", "b"]:
            res = self.client.get(f"/api/solar/{plant}/download?date=2026-09-29")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(
                res.headers.get("Content-Type"),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            # Verify openpyxl can load workbook and find both sheets
            wb = openpyxl.load_workbook(io.BytesIO(res.data))
            sheet_names = wb.sheetnames
            self.assertIn("Hourly Telemetry", sheet_names)
            self.assertIn("Daily Summary Report", sheet_names)

    def test_08_unauthenticated_access_is_protected(self):
        """TEST 8: Unauthenticated access to solar pages and APIs is blocked/redirected."""
        unauth_client = self.app.test_client()

        # Browser routes redirect to /login
        res_a = unauth_client.get("/solar/a", follow_redirects=False)
        self.assertEqual(res_a.status_code, 302)
        self.assertIn("/login", res_a.headers.get("Location", ""))

        res_b = unauth_client.get("/solar/b", follow_redirects=False)
        self.assertEqual(res_b.status_code, 302)
        self.assertIn("/login", res_b.headers.get("Location", ""))

        # API routes return 401 JSON
        res_api = unauth_client.get("/api/solar/a/data")
        self.assertEqual(res_api.status_code, 401)

    def test_09_three_permanent_sections_structure(self):
        """TEST 9: Exactly three permanent sections with exact independent dropdown options."""
        for plant in ["a", "b"]:
            res = self.client.get(f"/solar/{plant}")
            self.assertEqual(res.status_code, 200)
            html = res.data.decode("utf-8")

            # Check that total number of select dropdowns is exactly 3
            selects = re.findall(r'<select[^>]*id="([^"]+)"', html)
            self.assertEqual(len(selects), 3, f"Expected exactly 3 dropdowns, found {selects}")
            self.assertEqual(selects, ["selectTimeAnalysis", "selectTempAnalysis", "selectPowerAnalysis"])

            # Check that the legacy global dropdown is NOT present
            self.assertNotIn('id="selectAnalysisView"', html)
            self.assertNotIn("Global Analysis View", html)

            # Check Section 1: SOLAR GENERATION VS TIME (3 options)
            self.assertIn('id="sectionTime"', html)
            self.assertIn("SOLAR GENERATION VS TIME", html)
            self.assertIn('id="selectTimeAnalysis"', html)
            self.assertIn('id="chartTime"', html)
            self.assertIn("Actual Generation vs Time", html)
            self.assertIn("Forecasted Generation vs Time", html)
            self.assertIn("Actual vs Forecasted Generation", html)

            # Check Section 2: SOLAR GENERATION VS TEMPERATURE (3 options)
            self.assertIn('id="sectionTemp"', html)
            self.assertIn("SOLAR GENERATION VS TEMPERATURE", html)
            self.assertIn('id="selectTempAnalysis"', html)
            self.assertIn('id="chartTemp"', html)
            self.assertIn("Actual Generation vs Temperature", html)
            self.assertIn("Forecasted Generation vs Temperature", html)
            self.assertIn("Actual vs Forecasted Generation vs Temperature", html)

            # Check Section 3: SOLAR UTILIZATION (EXACTLY 1 option)
            self.assertIn('id="sectionPower"', html)
            self.assertIn("SOLAR UTILIZATION", html)
            self.assertIn('id="selectPowerAnalysis"', html)
            self.assertIn('id="chartPower"', html)
            self.assertIn("Solar Generated vs Utilized", html)

            # Ensure forbidden options are NOT present
            self.assertNotIn("Solar Generation vs Feeder Demand", html)
            self.assertNotIn("Solar Generation vs BESS Charging", html)
            self.assertNotIn("Solar Power Balance", html)

    def test_10_embedded_initial_telemetry_and_data_binding(self):
        """TEST 10: Embedded initial telemetry script exists with valid 24h JSON data for instant rendering."""
        for plant, cap in [("a", 495.0), ("b", 420.0)]:
            res = self.client.get(f"/solar/{plant}")
            self.assertEqual(res.status_code, 200)
            html = res.data.decode("utf-8")

            # Must contain the initialSolarTelemetry JSON script tag
            self.assertIn('id="initialSolarTelemetry"', html)
            
            # Extract JSON from the tag
            match = re.search(r'<script[^>]*id="initialSolarTelemetry"[^>]*>(.*?)</script>', html, re.DOTALL)
            self.assertIsNotNone(match, "initialSolarTelemetry script tag must exist")
            
            raw_json = match.group(1).strip()
            data = json.loads(raw_json)
            self.assertTrue(data.get("available"), "Initial embedded telemetry must be available")
            self.assertEqual(len(data.get("hourly", [])), 24, "Must contain exactly 24 hourly records")
            
            # Verify data bounds and fields for all 7 chart states
            for h in data["hourly"]:
                self.assertIn("time", h)
                self.assertIn("hour", h)
                self.assertIn("actual_generation_kw", h)
                self.assertIn("forecast_generation_kw", h)
                self.assertIn("temperature_c", h)
                self.assertIn("utilized_kw", h)

                actual = h["actual_generation_kw"]
                forecast = h["forecast_generation_kw"]
                utilized = h["utilized_kw"]

                self.assertGreaterEqual(actual, 0.0)
                self.assertLessEqual(actual, cap)
                self.assertGreaterEqual(forecast, 0.0)
                self.assertLessEqual(forecast, cap)
                self.assertGreaterEqual(utilized, 0.0)
                self.assertLessEqual(utilized, actual + 0.01)


if __name__ == "__main__":
    unittest.main()
