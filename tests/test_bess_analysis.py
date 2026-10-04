"""
SmartFeeder EMS — BESS Detailed Energy Storage Analysis Automated Test Suite
Verifies all technical validation criteria for BESS-A (BUS-1, 2 MWh) and BESS-B (BUS-2, 2 MWh).
Tests cover asset configurations, HTML rendering, 4 permanent sections, 4 dropdowns,
12 dropdown states, mathematical consistency (SOC vs Energy vs Power), Excel generation,
date availability rules, and access control.
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
from backend.bess_config import BESS_REGISTRY, get_bess_config
from backend.bess_service import BessService


class TestBessAnalysis(unittest.TestCase):
    def setUp(self):
        self.app = create_app(Config)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

        # Log in as authorized admin user
        res = self.client.post("/api/auth/login",
                               data=json.dumps({"username": "admin", "password": "Admin@123"}),
                               content_type="application/json")
        self.assertEqual(res.status_code, 200, "Admin login must succeed")

    def test_01_bess_asset_definitions_frozen(self):
        """TEST 1: BESS-A and BESS-B fixed definitions match requirements exactly."""
        # BESS-A
        cfg_a = get_bess_config("a")
        self.assertEqual(cfg_a["name"], "BESS-A")
        self.assertEqual(cfg_a["bus"], "BUS-1")
        self.assertEqual(cfg_a["energy_capacity_mwh"], 2.0)
        self.assertEqual(cfg_a["energy_capacity_kwh"], 2000.0)
        self.assertEqual(cfg_a["solar_name"], "Solar-A")
        self.assertEqual(cfg_a["solar_capacity_kw"], 495.0)
        self.assertEqual(cfg_a["bus_route"], "/bus/1")

        # BESS-B
        cfg_b = get_bess_config("b")
        self.assertEqual(cfg_b["name"], "BESS-B")
        self.assertEqual(cfg_b["bus"], "BUS-2")
        self.assertEqual(cfg_b["energy_capacity_mwh"], 2.0)
        self.assertEqual(cfg_b["energy_capacity_kwh"], 2000.0)
        self.assertEqual(cfg_b["solar_name"], "Solar-B")
        self.assertEqual(cfg_b["solar_capacity_kw"], 420.0)
        self.assertEqual(cfg_b["bus_route"], "/bus/2")

    def test_02_bess_a_page_rendering_and_metadata(self):
        """TEST 2: /bess/a renders correctly with BESS-A metadata, back button, and breadcrumbs."""
        for route in ["/bess/a", "/bess/A"]:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200)
            html = res.data.decode("utf-8")

            self.assertIn("BESS-A", html)
            self.assertIn("2 MWh (2000 kWh)", html)
            self.assertIn("BUS-1", html)
            self.assertIn("Back to BUS-1", html)
            self.assertIn('href="/bus/1"', html)

            # Breadcrumb check
            plain_text = " ".join(re.sub(r"<[^>]+>", " ", html).split())
            self.assertIn("Home / BUS-1 / BESS-A", plain_text)

    def test_03_bess_b_page_rendering_and_metadata(self):
        """TEST 3: /bess/b renders correctly with BESS-B metadata, back button, and breadcrumbs."""
        for route in ["/bess/b", "/bess/B"]:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200)
            html = res.data.decode("utf-8")

            self.assertIn("BESS-B", html)
            self.assertIn("2 MWh (2000 kWh)", html)
            self.assertIn("BUS-2", html)
            self.assertIn("Back to BUS-2", html)
            self.assertIn('href="/bus/2"', html)

            # Breadcrumb check
            plain_text = " ".join(re.sub(r"<[^>]+>", " ", html).split())
            self.assertIn("Home / BUS-2 / BESS-B", plain_text)

    def test_04_four_permanent_sections_and_dropdowns_structure(self):
        """TEST 4: Exactly four permanent sections exist simultaneously with 4 independent dropdowns."""
        for plant in ["a", "b"]:
            res = self.client.get(f"/bess/{plant}")
            self.assertEqual(res.status_code, 200)
            html = res.data.decode("utf-8")

            # Check that total number of select dropdowns is exactly 4
            selects = re.findall(r'<select[^>]*id="([^"]+)"', html)
            self.assertEqual(len(selects), 4, f"Expected exactly 4 dropdowns, found {selects}")
            self.assertEqual(selects, ["selectSocAnalysis", "selectSohAnalysis", "selectEnergyAnalysis", "selectPowerAnalysis"])

            # Check Section 1: BESS STATE OF CHARGE (SOC) (3 options)
            self.assertIn('id="sectionSoc"', html)
            self.assertIn("BESS STATE OF CHARGE (SOC)", html)
            self.assertIn('id="selectSocAnalysis"', html)
            self.assertIn('id="chartSoc"', html)
            self.assertIn("Actual SOC vs Time", html)
            self.assertIn("Forecasted SOC vs Time", html)
            self.assertIn("Actual vs Forecasted SOC", html)

            # Check Section 2: BESS STATE OF HEALTH (SOH) (3 options)
            self.assertIn('id="sectionSoh"', html)
            self.assertIn("BESS STATE OF HEALTH (SOH)", html)
            self.assertIn('id="selectSohAnalysis"', html)
            self.assertIn('id="chartSoh"', html)
            self.assertIn("Actual SOH vs Time", html)
            self.assertIn("Forecasted SOH vs Time", html)
            self.assertIn("Actual vs Forecasted SOH", html)

            # Check Section 3: BESS ENERGY ANALYSIS (3 options)
            self.assertIn('id="sectionEnergy"', html)
            self.assertIn("BESS ENERGY ANALYSIS", html)
            self.assertIn('id="selectEnergyAnalysis"', html)
            self.assertIn('id="chartEnergy"', html)
            self.assertIn("Actual Energy vs Time", html)
            self.assertIn("Forecasted Energy vs Time", html)
            self.assertIn("Actual vs Forecasted Energy", html)

            # Check Section 4: BESS POWER ANALYSIS (3 options)
            self.assertIn('id="sectionPower"', html)
            self.assertIn("BESS POWER ANALYSIS", html)
            self.assertIn('id="selectPowerAnalysis"', html)
            self.assertIn('id="chartPower"', html)
            self.assertIn("Actual Power vs Time", html)
            self.assertIn("Forecasted Power vs Time", html)
            self.assertIn("Actual vs Forecasted Power", html)

    def test_05_embedded_initial_telemetry_for_instant_rendering(self):
        """TEST 5: Embedded initial telemetry script exists with valid 24h JSON data for instant rendering."""
        for plant in ["a", "b"]:
            res = self.client.get(f"/bess/{plant}")
            self.assertEqual(res.status_code, 200)
            html = res.data.decode("utf-8")

            # Must contain the initialBessTelemetry JSON script tag
            self.assertIn('id="initialBessTelemetry"', html)
            match = re.search(r'<script[^>]*id="initialBessTelemetry"[^>]*>(.*?)</script>', html, re.DOTALL)
            self.assertIsNotNone(match, "initialBessTelemetry script tag must exist")

            data = json.loads(match.group(1).strip())
            self.assertTrue(data.get("available"), "Initial embedded telemetry must be available")
            self.assertEqual(len(data.get("hourly", [])), 24, "Must contain exactly 24 hourly records")

    def test_06_bess_api_telemetry_and_engineering_consistency(self):
        """TEST 6: API returns valid telemetry, strictly enforcing engineering relationships."""
        for plant in ["a", "b"]:
            res = self.client.get(f"/api/bess/{plant}/data?date=2026-09-29")
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertTrue(data["success"])
            telemetry = data["data"]
            self.assertTrue(telemetry["available"])
            self.assertEqual(len(telemetry["hourly"]), 24)

            for rec in telemetry["hourly"]:
                soc = rec["actual_soc_pct"]
                forecast_soc = rec["forecast_soc_pct"]
                energy = rec["actual_energy_kwh"]
                forecast_energy = rec["forecast_energy_kwh"]
                soh = rec["actual_soh_pct"]
                power = rec["actual_power_kw"]
                status = rec["status"]

                # 1. SOC strictly bounded by 0-100% and within 15%-90% window
                self.assertGreaterEqual(soc, 15.0)
                self.assertLessEqual(soc, 90.0)
                self.assertGreaterEqual(forecast_soc, 15.0)
                self.assertLessEqual(forecast_soc, 90.0)

                # 2. Mathematical Consistency: Stored Energy (kWh) = (SOC / 100) * 2000 kWh
                expected_energy = (soc / 100.0) * 2000.0
                self.assertAlmostEqual(energy, expected_energy, delta=1.0)

                expected_f_energy = (forecast_soc / 100.0) * 2000.0
                self.assertAlmostEqual(forecast_energy, expected_f_energy, delta=1.0)

                # 3. Energy cannot exceed 2000 kWh capacity
                self.assertLessEqual(energy, 2000.0)
                self.assertGreaterEqual(energy, 0.0)

                # 4. SOH strictly positive and <= 100%
                self.assertGreater(soh, 0.0)
                self.assertLessEqual(soh, 100.0)

                # 5. Status logic consistency
                if status == "CHARGING":
                    self.assertLess(power, 0.0, "Charging power must be negative (into BESS)")
                elif status == "DISCHARGING":
                    self.assertGreater(power, 0.0, "Discharging power must be positive (to bus)")
                else:
                    self.assertEqual(status, "IDLE")
                    self.assertEqual(power, 0.0)

    def test_07_pre_dataset_date_availability_rule(self):
        """TEST 7: Dates before 05-Aug-2026 return available=False with exact guidance."""
        for plant in ["a", "b"]:
            res = self.client.get(f"/api/bess/{plant}/data?date=2026-07-20")
            self.assertEqual(res.status_code, 200)
            data = res.get_json()["data"]
            self.assertFalse(data["available"])
            self.assertEqual(data["message"], "DATA NOT AVAILABLE")
            self.assertIn("Historical BESS telemetry is available from 05-Aug-2026 onwards.", data["info"])

    def test_08_excel_download_generation(self):
        """TEST 8: Excel report downloads successfully with Hourly and Daily Summary sheets."""
        for plant in ["a", "b"]:
            res = self.client.get(f"/api/bess/{plant}/download?date=2026-09-29")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(
                res.headers.get("Content-Type"),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            wb = openpyxl.load_workbook(io.BytesIO(res.data))
            sheet_names = wb.sheetnames
            self.assertIn("Hourly Telemetry", sheet_names)
            self.assertIn("Daily Summary Report", sheet_names)

    def test_09_unauthenticated_access_is_protected(self):
        """TEST 9: Unauthenticated access to BESS pages and APIs is redirected or blocked."""
        unauth_client = self.app.test_client()

        # Browser routes redirect to /login
        res_a = unauth_client.get("/bess/a", follow_redirects=False)
        self.assertEqual(res_a.status_code, 302)
        self.assertIn("/login", res_a.headers.get("Location", ""))

        res_b = unauth_client.get("/bess/b", follow_redirects=False)
        self.assertEqual(res_b.status_code, 302)
        self.assertIn("/login", res_b.headers.get("Location", ""))

        # API routes return 401 JSON
        res_api = unauth_client.get("/api/bess/a/data")
        self.assertEqual(res_api.status_code, 401)


if __name__ == "__main__":
    unittest.main()
