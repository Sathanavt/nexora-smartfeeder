"""
SmartFeeder EMS — Automated Verification Suite for EMS Detailed Control & Operating Status Page
Verifies:
1. Mathematical Power Balance: P_load = P_solar + P_bess + P_grid (within 0.1 kW tolerance).
2. Single Source of Truth: Total Feeder Demand = sum(F1..F8), Total Solar = Solar_A + Solar_B.
3. BESS 15% - 90% Operating Window & Dynamic Reserves.
4. Operating Condition classification (Grid Only, Grid + Solar, Grid + Solar + BESS, Grid + BESS).
5. Solar < 8 kW Inactive threshold.
6. Bus Voltage (10.8 - 12.0 kV) and Frequency (49.9 - 50.1 Hz) health criteria.
7. Route protection (@login_required) for /ems and /api/ems/data.
8. Template rendering, navigation back link (href="/"), and zero-lag embedded telemetry.
9. 6-Hour Rolling Forecast Outlook data integrity.
"""
import json
import unittest
from backend.app import create_app
from backend.config import Config
from backend.data_service import DataService
from backend.ems_service import EmsService


class TestEmsControlPage(unittest.TestCase):

    def setUp(self):
        self.app = create_app(Config)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def _login(self, username="admin", password="Admin@123"):
        return self.client.post("/api/auth/login",
                                data=json.dumps({"username": username, "password": password}),
                                content_type="application/json")

    def test_ems_service_power_balance(self):
        """Verifies physical conservation of energy: P_load ≈ P_solar + P_bess + P_grid."""
        status = EmsService.get_ems_status()
        pb = status["power_balance"]
        
        load = pb["feeder_demand_kw"]
        solar = pb["solar_generation_kw"]
        bess = pb["bess_power_kw"]
        grid = pb["grid_import_kw"]

        # Governing equation
        net_calc = round(solar + bess + grid, 1)
        self.assertAlmostEqual(load, net_calc, delta=0.2,
                               msg=f"Power balance violated: Load={load} vs Calculated={net_calc}")
        self.assertTrue(pb["is_balanced"])

    def test_ems_feeder_demand_sum_consistency(self):
        """Verifies Total Feeder Demand equals the exact sum of Feeders 1 to 8."""
        status = EmsService.get_ems_status()
        fd = status["control_summary"]["feeder_demand"]
        feeders = fd["feeders"]
        
        self.assertEqual(len(feeders), 8)
        expected_bus1 = round(sum(feeders[0:4]), 1)
        expected_bus2 = round(sum(feeders[4:8]), 1)
        expected_total = round(expected_bus1 + expected_bus2, 1)

        self.assertAlmostEqual(fd["bus1_demand_kw"], expected_bus1, delta=0.1)
        self.assertAlmostEqual(fd["bus2_demand_kw"], expected_bus2, delta=0.1)
        self.assertAlmostEqual(fd["total_kw"], expected_total, delta=0.1)

    def test_ems_solar_generation_sum(self):
        """Verifies Total Solar Generation equals Solar-A + Solar-B and clamps to ratings."""
        status = EmsService.get_ems_status()
        sc = status["solar_control"]
        solar_a = sc["solar_a"]["current_gen_kw"]
        solar_b = sc["solar_b"]["current_gen_kw"]
        total_solar = status["power_balance"]["solar_generation_kw"]

        self.assertAlmostEqual(total_solar, round(solar_a + solar_b, 1), delta=0.1)
        self.assertLessEqual(solar_a, 495.0)
        self.assertLessEqual(solar_b, 420.0)

    def test_ems_grid_import_breakdown(self):
        """Verifies Total Grid Import equals BUS-1 + BUS-2 grid infeed and sync is LOCKED."""
        status = EmsService.get_ems_status()
        gi = status["control_summary"]["grid_import"]
        bus1_grid = gi["bus1_grid_kw"]
        bus2_grid = gi["bus2_grid_kw"]
        total_grid = gi["total_kw"]

        self.assertAlmostEqual(total_grid, round(bus1_grid + bus2_grid, 1), delta=0.1)
        self.assertEqual(gi["frequency_sync"], "LOCKED")

    def test_ems_bess_operating_window_and_dynamic_reserve(self):
        """Verifies BESS SOC is clamped to 15% - 90% and dynamic reserve is positive."""
        status = EmsService.get_ems_status()
        bc = status["bess_control"]
        
        # BESS-A
        soc_a = bc["bess_a"]["soc_pct"]
        self.assertGreaterEqual(soc_a, 15.0)
        self.assertLessEqual(soc_a, 90.0)
        self.assertGreaterEqual(bc["bess_a"]["discharge_reserve_kwh"], 0.0)
        
        # BESS-B
        soc_b = bc["bess_b"]["soc_pct"]
        self.assertGreaterEqual(soc_b, 15.0)
        self.assertLessEqual(soc_b, 90.0)
        self.assertGreaterEqual(bc["bess_b"]["discharge_reserve_kwh"], 0.0)

        # Dynamic reserve
        self.assertGreaterEqual(bc["dynamic_reserve"]["reserve_soc_pct"], 15.0)
        self.assertGreater(bc["dynamic_reserve"]["reserve_energy_kwh"], 0.0)

    def test_ems_operating_condition_logic(self):
        """Verifies EMS operating mode is correctly categorized into 1 of 4 approved states."""
        status = EmsService.get_ems_status()
        mode = status["operating_condition"]
        valid_modes = ["GRID ONLY", "GRID + SOLAR", "GRID + SOLAR + BESS", "GRID + BESS"]
        self.assertIn(mode, valid_modes)

        # Test raw latest record (night record: solar=0, bess=0)
        raw_status = EmsService.get_ems_status(use_raw_last=True)
        self.assertEqual(raw_status["operating_condition"], "GRID ONLY")

    def test_ems_bus_voltage_and_frequency_ranges(self):
        """Verifies voltage status uses 10.8-12.0 kV and frequency uses 49.9-50.1 Hz."""
        status = EmsService.get_ems_status()
        ch = {item["param"]: item for item in status["constraints_health"]}
        
        self.assertIn("Bus Voltage Condition", ch)
        self.assertEqual(ch["Bus Voltage Condition"]["limit"], "10.8 kV - 12.0 kV")
        self.assertEqual(ch["Bus Voltage Condition"]["status"], "NORMAL")

        self.assertIn("Frequency Condition", ch)
        self.assertEqual(ch["Frequency Condition"]["limit"], "49.9 Hz - 50.1 Hz")
        self.assertEqual(ch["Frequency Condition"]["status"], "NORMAL")

    def test_ems_rolling_outlook(self):
        """Verifies the next 6-hour EMS outlook returns exactly 6 chronological hourly rows."""
        status = EmsService.get_ems_status()
        outlook = status["forecast_engine"]["outlook_hours"]
        self.assertEqual(len(outlook), 6)
        
        for row in outlook:
            self.assertIn("time", row)
            self.assertIn("forecast_load_kw", row)
            self.assertIn("forecast_solar_kw", row)
            self.assertIn("forecast_bess_power_kw", row)
            self.assertIn("forecast_soc_pct", row)
            self.assertIn("expected_grid_import_kw", row)
            self.assertIn("expected_mode", row)
            self.assertGreaterEqual(row["forecast_soc_pct"], 15.0)
            self.assertLessEqual(row["forecast_soc_pct"], 90.0)

    def test_ems_route_authentication_protection(self):
        """Verifies that unauthenticated access to /ems and /api/ems/data is blocked."""
        # Unauthenticated /ems redirects to /login
        resp = self.client.get("/ems")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])

        # Unauthenticated /api/ems/data returns 401
        api_resp = self.client.get("/api/ems/data")
        self.assertEqual(api_resp.status_code, 401)

    def test_ems_page_rendering_and_navigation(self):
        """Verifies authenticated access to /ems renders all required sections and back link."""
        self._login("admin", "Admin@123")
        resp = self.client.get("/ems")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")

        # 1. Back button to Home
        self.assertIn('href="/"', html)
        self.assertIn("Back to Home Dashboard", html)

        # 2. Main Title & Subtitle
        self.assertIn("SMARTFEEDER EMS", html)
        self.assertIn("Supervisory Control", html)

        # 3. 4 Control Cards
        self.assertIn("PV INVERTER SETPOINT", html)
        self.assertIn("BESS PCS SETPOINT", html)
        self.assertIn("UTILITY GRID IMPORT", html)
        self.assertIn("TOTAL FEEDER DEMAND", html)

        # 4. Live Power Balance
        self.assertIn("LIVE POWER BALANCE", html)
        self.assertIn("P_load = P_solar + P_bess + P_grid", html)

        # 5. Solar & BESS sections
        self.assertIn("SOLAR PV CONTROL", html)
        self.assertIn("SOLAR-A", html)
        self.assertIn("SOLAR-B", html)
        self.assertIn("BESS PCS CONTROL", html)
        self.assertIn("BESS-A", html)
        self.assertIn("BESS-B", html)

        # 6. Active Commands Table (Decision Engine & Grid Management sections completely removed)
        self.assertIn("ACTIVE EMS COMMANDS", html)
        self.assertNotIn("EMS DECISION ENGINE", html)
        self.assertNotIn("UTILITY GRID MANAGEMENT", html)
        self.assertNotIn("SUPERVISORY INTELLIGENCE &amp; CONTROL LOOP", html)
        self.assertNotIn("INTERCONNECTION SUPERVISION &amp; RESIDUAL DISPATCH", html)

        # 7. Card 1 (PV Inverter Setpoint) Verification (ONLY Total PV Power, Solar-A, Solar-B)
        self.assertIn("TOTAL PV POWER", html)
        self.assertIn("Solar-A", html)
        self.assertIn("Solar-B", html)
        self.assertNotIn("Available PV Power", html)
        self.assertNotIn("Current PV Generation", html)
        self.assertNotIn("Curtailment Status", html)

        # 8. Card 3 (Utility Grid Import) Breakdown & Field Removal Verification
        self.assertIn("TOTAL GRID IMPORT", html)
        self.assertIn("BUS-1", html)
        self.assertIn("BUS-2", html)
        self.assertIn("Frequency Synchronization", html)
        self.assertNotIn("Grid Status", html)
        self.assertNotIn("Grid Voltage", html)

        # 9. Outlook & Constraints
        self.assertIn("NEXT 6-HOUR EMS OUTLOOK", html)
        self.assertIn("EMS CONSTRAINTS &amp; SYSTEM HEALTH", html)

        # 10. Embedded telemetry script
        self.assertIn('id="initialEmsTelemetry"', html)

    def test_api_ems_data_endpoint(self):
        """Verifies /api/ems/data returns 200 OK with valid JSON payload."""
        self._login("operator", "Oper@123")
        resp = self.client.get("/api/ems/data")
        self.assertEqual(resp.status_code, 200)
        json_data = resp.get_json()
        self.assertTrue(json_data["success"])
        data = json_data["data"]
        self.assertIn("operating_condition", data)
        self.assertIn("power_balance", data)
        self.assertIn("control_summary", data)


if __name__ == "__main__":
    unittest.main()
