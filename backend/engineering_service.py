import math
import hashlib
from typing import Dict, Any
from backend.feeder_config import get_feeders_by_bus

class EngineeringService:
    """
    Computes deterministic, technically sound electrical engineering parameters,
    power balance calculations, and operational states for SmartFeeder EMS.
    """
    NOMINAL_VOLTAGE_KV = 11.0
    NOMINAL_FREQUENCY_HZ = 50.0
    POWER_FACTOR = 0.95
    SOLAR_THRESHOLD_KW = 8.0

    @staticmethod
    def _deterministic_noise(seed_str: str, min_val: float, max_val: float) -> float:
        """Generates deterministic pseudo-random float strictly bounded by [min_val, max_val]."""
        h = hashlib.sha256(seed_str.encode("utf-8")).hexdigest()
        norm = int(h[:8], 16) / 0xFFFFFFFF
        return min_val + norm * (max_val - min_val)

    @classmethod
    def compute_bus_voltage(cls, timestamp_str: str, bus_id: str, demand_kw: float) -> float:
        """
        Determines realistic bus voltage within mandatory 10.8 kV <= V <= 12.0 kV limits.
        Smoothly accounts for substation voltage drop under load and minute-level variation.
        """
        # Base nominal 11.25 kV - slight drop for higher demand
        load_droop = min(0.18, (demand_kw / 3000.0) * 0.15) if demand_kw > 0 else 0.0
        variation = cls._deterministic_noise(f"v_{bus_id}_{timestamp_str}", -0.05, 0.06)
        v = 11.28 - load_droop + variation
        # Clamp strictly between 10.80 and 12.00 kV
        return round(float(max(10.80, min(12.00, v))), 2)

    @classmethod
    def compute_bus_frequency(cls, timestamp_str: str, bus_id: str) -> float:
        """
        Determines grid frequency within mandatory 49.90 Hz <= f <= 50.10 Hz limits.
        Reflects tight grid-synchronized frequency regulation.
        """
        variation = cls._deterministic_noise(f"freq_{bus_id}_{timestamp_str}", -0.045, 0.045)
        f = cls.NOMINAL_FREQUENCY_HZ + variation
        return round(float(max(49.90, min(50.10, f))), 2)

    @classmethod
    def compute_bus_current(cls, demand_kw: float, voltage_kv: float, power_factor: float = POWER_FACTOR) -> float:
        """
        Calculates 3-phase line current strictly using:
        P = √3 × V × I × PF  ==>  I = P / (√3 × V × PF)
        Where P in kW, V in kV, yielding I in Amperes.
        """
        if demand_kw <= 0.0 or voltage_kv <= 0.0 or power_factor <= 0.0:
            return 0.0
        # I (A) = P (kW) / (sqrt(3) * V (kV) * PF)
        current_a = demand_kw / (math.sqrt(3) * voltage_kv * power_factor)
        return round(float(current_a), 1)

    @classmethod
    def evaluate_home_metrics(cls, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translates raw telemetry record into full structured metrics for the Home Dashboard.
        """
        ts_str = str(record.get("Timestamp", "2026-09-29 23:00:00"))
        ts_formatted = record.get("Timestamp_Formatted", ts_str)

        # 1. Feeder demands (kW)
        f1 = float(record.get("Feeder_1_Demand_kW", 0.0))
        f2 = float(record.get("Feeder_2_Demand_kW", 0.0))
        f3 = float(record.get("Feeder_3_Demand_kW", 0.0))
        f4 = float(record.get("Feeder_4_Demand_kW", 0.0))
        f5 = float(record.get("Feeder_5_Demand_kW", 0.0))
        f6 = float(record.get("Feeder_6_Demand_kW", 0.0))
        f7 = float(record.get("Feeder_7_Demand_kW", 0.0))
        f8 = float(record.get("Feeder_8_Demand_kW", 0.0))

        # Bus demands
        p_bus1 = round(f1 + f2 + f3 + f4, 1)
        p_bus2 = round(f5 + f6 + f7 + f8, 1)
        total_feeder_demand = round(p_bus1 + p_bus2, 1)

        # 2. Solar Generations (kW)
        solar_a_kw = round(float(record.get("Solar_1_Generation_kW", 0.0)), 1)
        solar_b_kw = round(float(record.get("Solar_2_Generation_kW", 0.0)), 1)
        total_solar_kw = round(solar_a_kw + solar_b_kw, 1)

        # Solar Active / Inactive states (threshold: 8 kW)
        solar_a_status = "ACTIVE" if solar_a_kw >= cls.SOLAR_THRESHOLD_KW else "INACTIVE"
        solar_b_status = "ACTIVE" if solar_b_kw >= cls.SOLAR_THRESHOLD_KW else "INACTIVE"
        any_solar_active = (solar_a_status == "ACTIVE" or solar_b_status == "ACTIVE")

        # 3. BESS Telemetry
        bess1_status = str(record.get("Bus1_BESS_Status", "IDLE")).strip().upper()
        bess1_power = float(record.get("Bus1_BESS_Power_kW", 0.0))
        bess1_soc = round(float(record.get("Bus1_BESS_SOC_pct", 50.0)), 1)

        bess2_status = str(record.get("Bus2_BESS_Status", "IDLE")).strip().upper()
        bess2_power = float(record.get("Bus2_BESS_Power_kW", 0.0))
        bess2_soc = round(float(record.get("Bus2_BESS_SOC_pct", 50.0)), 1)

        # Standardize states if power is zero
        if abs(bess1_power) < 0.1 and bess1_status not in ("CHARGING", "DISCHARGING"):
            bess1_status = "IDLE"
        if abs(bess2_power) < 0.1 and bess2_status not in ("CHARGING", "DISCHARGING"):
            bess2_status = "IDLE"

        any_bess_active = (
            (bess1_status in ("CHARGING", "DISCHARGING") and abs(bess1_power) >= 0.5) or
            (bess2_status in ("CHARGING", "DISCHARGING") and abs(bess2_power) >= 0.5)
        )

        # 4. Bus Electrical Parameters (Voltage, Current, Frequency)
        v_bus1 = cls.compute_bus_voltage(ts_str, "bus1", p_bus1)
        f_bus1 = cls.compute_bus_frequency(ts_str, "bus1")
        i_bus1 = cls.compute_bus_current(p_bus1, v_bus1, cls.POWER_FACTOR)

        v_bus2 = cls.compute_bus_voltage(ts_str, "bus2", p_bus2)
        f_bus2 = cls.compute_bus_frequency(ts_str, "bus2")
        i_bus2 = cls.compute_bus_current(p_bus2, v_bus2, cls.POWER_FACTOR)

        # 5. Grid Import & Power Balance
        # For BESS discharge: P_grid = P_load - P_PV - P_BESS_discharge
        # For BESS charge:    P_grid = P_load - P_PV + P_BESS_charge
        bess1_discharge = abs(bess1_power) if bess1_status == "DISCHARGING" else 0.0
        bess1_charge = abs(bess1_power) if bess1_status == "CHARGING" else 0.0

        bess2_discharge = abs(bess2_power) if bess2_status == "DISCHARGING" else 0.0
        bess2_charge = abs(bess2_power) if bess2_status == "CHARGING" else 0.0

        total_bess_discharge = bess1_discharge + bess2_discharge
        total_bess_charge = bess1_charge + bess2_charge

        net_grid_import = total_feeder_demand - total_solar_kw - total_bess_discharge + total_bess_charge
        net_grid_import = round(max(0.0, net_grid_import), 1)

        # 6. EMS Operating Mode
        if not any_solar_active and not any_bess_active:
            operating_mode = "Grid Only"
        elif any_solar_active and not any_bess_active:
            operating_mode = "Grid + Solar"
        elif any_solar_active and any_bess_active:
            operating_mode = "Grid + Solar + BESS"
        else:
            operating_mode = "Grid + BESS"

        # PV Inverter setpoint and BESS PCS setpoint
        pv_setpoint_kw = total_solar_kw
        net_bess_setpoint = round(total_bess_discharge - total_bess_charge, 1)

        return {
            "timestamp": ts_str,
            "timestamp_formatted": ts_formatted,
            "bus1": {
                "name": "BUS-1",
                "title": "BUS-1 STATUS",
                "type": "11 kV Distribution Bus",
                "status": "LIVE",
                "demand_kw": p_bus1,
                "voltage_kv": v_bus1,
                "current_a": i_bus1,
                "frequency_hz": f_bus1,
                "solar_name": "Solar-A (495 kW)",
                "solar_gen_kw": solar_a_kw,
                "solar_status": solar_a_status,
                "bess_name": "BESS-A",
                "bess_status": bess1_status,
                "bess_power_kw": round(bess1_power, 1),
                "bess_soc_pct": bess1_soc,
                "route": "/bus/1"
            },
            "bus2": {
                "name": "BUS-2",
                "title": "BUS-2 STATUS",
                "type": "11 kV Distribution Bus",
                "status": "LIVE",
                "demand_kw": p_bus2,
                "voltage_kv": v_bus2,
                "current_a": i_bus2,
                "frequency_hz": f_bus2,
                "solar_name": "Solar-B (420 kW)",
                "solar_gen_kw": solar_b_kw,
                "solar_status": solar_b_status,
                "bess_name": "BESS-B",
                "bess_status": bess2_status,
                "bess_power_kw": round(bess2_power, 1),
                "bess_soc_pct": bess2_soc,
                "route": "/bus/2"
            },
            "ems": {
                "title": "EMS STATUS",
                "type": "Energy Management System",
                "status": "ACTIVE",
                "operating_mode": operating_mode,
                "pv_setpoint_kw": pv_setpoint_kw,
                "bess_setpoint_kw": net_bess_setpoint,
                "grid_import_kw": net_grid_import,
                "route": "/ems"
            },
            "summary": {
                "total_feeder_demand_kw": total_feeder_demand,
                "total_solar_gen_kw": total_solar_kw,
                "total_grid_import_kw": net_grid_import,
                "bess_a_soc_pct": bess1_soc,
                "bess_b_soc_pct": bess2_soc,
                "bess_soc_min": 15.0,
                "bess_soc_max": 90.0
            },
            "system_strip": {
                "substation": "ONLINE",
                "bus1": "ONLINE",
                "bus2": "ONLINE",
                "solar": "ACTIVE" if any_solar_active else "INACTIVE",
                "bess": "AVAILABLE",
                "ems": "ACTIVE"
            }
        }

    @classmethod
    def evaluate_bus1_metrics(cls, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translates raw telemetry record into full structured metrics for the BUS-1 Detailed Dashboard.
        Guarantees mathematical and electrical consistency with the Home Dashboard.
        """
        ts_str = str(record.get("Timestamp", "2026-09-29 17:00:00"))
        ts_formatted = record.get("Timestamp_Formatted", ts_str)

        # 1. Feeder demands (kW) from dataset
        f1 = round(float(record.get("Feeder_1_Demand_kW", 0.0)), 2)
        f2 = round(float(record.get("Feeder_2_Demand_kW", 0.0)), 2)
        f3 = round(float(record.get("Feeder_3_Demand_kW", 0.0)), 2)
        f4 = round(float(record.get("Feeder_4_Demand_kW", 0.0)), 2)

        # BUS-1 Demand is strictly the sum of Feeders 1 to 4
        p_bus1 = round(f1 + f2 + f3 + f4, 1)

        # 2. Bus-level Electrical Parameters
        v_bus1 = cls.compute_bus_voltage(ts_str, "bus1", p_bus1)
        f_bus1 = cls.compute_bus_frequency(ts_str, "bus1")
        i_bus1 = cls.compute_bus_current(p_bus1, v_bus1, cls.POWER_FACTOR)

        # 3. Solar-A Telemetry
        raw_solar_a = float(record.get("Solar_1_Generation_kW", 0.0))
        solar_a_kw = round(min(495.0, max(0.0, raw_solar_a)), 1)
        solar_a_status = "ACTIVE" if solar_a_kw >= cls.SOLAR_THRESHOLD_KW else "INACTIVE"
        temp_c = round(float(record.get("Temperature_C", 27.0)), 1)

        # 4. BESS-A Telemetry
        bess1_status = str(record.get("Bus1_BESS_Status", "IDLE")).strip().upper()
        bess1_power = round(float(record.get("Bus1_BESS_Power_kW", 0.0)), 1)
        bess1_soc = round(float(record.get("Bus1_BESS_SOC_pct", 50.0)), 1)
        bess1_soh = round(float(record.get("Bus1_BESS_SOH_pct", 99.0)), 1)

        if abs(bess1_power) < 0.1 and bess1_status not in ("CHARGING", "DISCHARGING"):
            bess1_status = "IDLE"

        # 5. Solar Flow Power Balance (Solar -> Grid & Solar -> BESS)
        # BESS Import: Solar redirected to BESS charging (if BESS charging and power < 0)
        if bess1_status == "CHARGING" and bess1_power < 0:
            solar_to_bess_kw = round(min(solar_a_kw, abs(bess1_power)), 1)
        else:
            solar_to_bess_kw = 0.0

        solar_remaining = max(0.0, solar_a_kw - solar_to_bess_kw)
        if solar_remaining > p_bus1:
            solar_to_grid_kw = round(solar_remaining - p_bus1, 1)
        else:
            solar_to_grid_kw = 0.0

        # 6. Dynamic Reserve Calculation (E_reserve = Expected Deficit + Uncertainty Margin)
        # Expected deficit when demand > solar over 1-hour dispatch interval
        expected_deficit_kwh = max(0.0, p_bus1 - solar_a_kw)
        uncertainty_kwh = expected_deficit_kwh * 0.15
        e_reserve_kwh = round(expected_deficit_kwh + uncertainty_kwh, 1)
        # Corresponding SOC percentage within 15% - 90% operating window
        soc_reserve_pct = round(min(90.0, max(15.0, (e_reserve_kwh / 2000.0) * 100.0 + 15.0)), 1)

        # 7. Feeders 1 to 4 Detailed Profiles from Single Source of Truth
        feeder_configs = get_feeders_by_bus(1)

        feeders_data = []
        for cfg in feeder_configs:
            f_id = cfg["id"]
            p_feeder = float(record.get(cfg["column"], 0.0))
            # Realistic line voltage with slight drop based on demand
            drop = min(0.06, (p_feeder / 100.0) * 0.04) if p_feeder > 0 else 0.01
            v_feeder = round(float(max(10.80, min(12.00, v_bus1 - drop))), 2)
            # Power factor smoothly in 0.90 - 0.99
            pf_variation = cls._deterministic_noise(f"pf_f{f_id}_{ts_str}", -0.015, 0.015)
            pf_feeder = round(float(max(0.90, min(0.99, cfg["pf_base"] + pf_variation))), 2)
            # 3-phase current for feeder
            i_feeder = cls.compute_bus_current(p_feeder, v_feeder, pf_feeder)

            feeders_data.append({
                "id": f_id,
                "name": cfg["name"],
                "type": cfg["classification"],
                "demand_kw": p_feeder,
                "voltage_kv": v_feeder,
                "current_a": i_feeder,
                "frequency_hz": f_bus1,
                "power_factor": pf_feeder,
                "status": "LIVE",
                "route": f"/feeder/{f_id}"
            })

        return {
            "timestamp": ts_str,
            "timestamp_formatted": ts_formatted,
            "summary": {
                "name": "BUS-1",
                "status": "LIVE",
                "type": "11 kV Distribution Bus",
                "demand_kw": p_bus1,
                "voltage_kv": v_bus1,
                "current_a": i_bus1,
                "frequency_hz": f_bus1,
                "power_factor": cls.POWER_FACTOR,
                "solar_status": solar_a_status,
                "bess_status": bess1_status,
                "feeders_count": 4,
                "substation": "110/11 kV Substation"
            },
            "feeders": feeders_data,
            "solar_a": {
                "name": "SOLAR-A",
                "capacity_kw": 495.0,
                "generation_kw": solar_a_kw,
                "status": solar_a_status,
                "temperature_c": temp_c,
                "grid_import_kw": solar_to_grid_kw,
                "bess_import_kw": solar_to_bess_kw,
                "route": "/solar/A"
            },
            "bess_a": {
                "name": "BESS-A",
                "status": bess1_status,
                "soc_pct": bess1_soc,
                "soh_pct": bess1_soh,
                "power_kw": bess1_power,
                "capacity_kwh": 2000.0,
                "dynamic_reserve_kwh": e_reserve_kwh,
                "dynamic_reserve_soc_pct": soc_reserve_pct,
                "operating_window": "15% – 90%",
                "soc_alert": (bess1_soc < 15.0 or bess1_soc > 90.0),
                "route": "/bess/A"
            }
        }

    @classmethod
    def evaluate_bus2_metrics(cls, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translates raw telemetry record into full structured metrics for the BUS-2 Detailed Dashboard.
        Covers Feeders 5 to 8, Solar-B (420 kW capacity), and BESS-B.
        Maintains rigorous engineering limits and electrical equation consistency.
        """
        ts_str = str(record.get("Timestamp", record.get("timestamp", "2026-09-29 17:00:00")))
        ts_formatted = record.get("Timestamp_Formatted", ts_str)

        # 1. Feeder Demands (kW)
        f5 = round(float(record.get("Feeder_5_Demand_kW", 0.0)), 2)
        f6 = round(float(record.get("Feeder_6_Demand_kW", 0.0)), 2)
        f7 = round(float(record.get("Feeder_7_Demand_kW", 0.0)), 2)
        f8 = round(float(record.get("Feeder_8_Demand_kW", 0.0)), 2)

        # Bus-2 Total Demand (kW)
        p_bus2 = round(f5 + f6 + f7 + f8, 1)

        # 2. Bus-2 Operating Electrical Parameters
        v_bus2 = cls.compute_bus_voltage(ts_str, "bus2", p_bus2)
        f_bus2 = cls.compute_bus_frequency(ts_str, "bus2")
        i_bus2 = cls.compute_bus_current(p_bus2, v_bus2, cls.POWER_FACTOR)

        # 3. Solar-B Status & Weather (420 kW max capacity)
        raw_solar_b = float(record.get("Solar_2_Generation_kW", 0.0))
        solar_b_kw = round(min(420.0, max(0.0, raw_solar_b)), 1)
        solar_b_status = "ACTIVE" if solar_b_kw >= cls.SOLAR_THRESHOLD_KW else "INACTIVE"
        temp_c = round(float(record.get("Temperature_C", 28.5)), 1)

        # 4. BESS-B Operating Parameters
        bess2_status = str(record.get("Bus2_BESS_Status", "IDLE")).strip().upper()
        bess2_power = round(float(record.get("Bus2_BESS_Power_kW", 0.0)), 1)
        bess2_soc = round(float(record.get("Bus2_BESS_SOC_pct", 50.0)), 1)
        bess2_soh = round(float(record.get("Bus2_BESS_SOH_pct", 99.0)), 1)

        if abs(bess2_power) < 0.1 and bess2_status not in ("CHARGING", "DISCHARGING"):
            bess2_status = "IDLE"

        # 5. Solar Flow Power Balance (Solar -> Grid & Solar -> BESS)
        # BESS Import: Solar redirected to BESS charging (if BESS charging and power < 0)
        if bess2_status == "CHARGING" and bess2_power < 0:
            solar_to_bess_kw = round(min(solar_b_kw, abs(bess2_power)), 1)
        else:
            solar_to_bess_kw = 0.0

        solar_remaining = max(0.0, solar_b_kw - solar_to_bess_kw)
        if solar_remaining > p_bus2:
            solar_to_grid_kw = round(solar_remaining - p_bus2, 1)
        else:
            solar_to_grid_kw = 0.0

        # 6. Dynamic Reserve Calculation (E_reserve = Expected Deficit + Uncertainty Margin)
        expected_deficit_kwh = max(0.0, p_bus2 - solar_b_kw)
        uncertainty_kwh = expected_deficit_kwh * 0.15
        e_reserve_kwh = round(expected_deficit_kwh + uncertainty_kwh, 1)
        soc_reserve_pct = round(min(90.0, max(15.0, (e_reserve_kwh / 2000.0) * 100.0 + 15.0)), 1)

        # 7. Feeders 5 to 8 Detailed Profiles from Single Source of Truth
        feeder_configs = get_feeders_by_bus(2)

        feeders_data = []
        for cfg in feeder_configs:
            f_id = cfg["id"]
            p_feeder = float(record.get(cfg["column"], 0.0))
            # Realistic line voltage with slight drop based on demand
            drop = min(0.06, (p_feeder / 100.0) * 0.04) if p_feeder > 0 else 0.01
            v_feeder = round(float(max(10.80, min(12.00, v_bus2 - drop))), 2)
            # Power factor smoothly in 0.90 - 0.99
            pf_variation = cls._deterministic_noise(f"pf_f{f_id}_{ts_str}", -0.015, 0.015)
            pf_feeder = round(float(max(0.90, min(0.99, cfg["pf_base"] + pf_variation))), 2)
            # 3-phase current for feeder
            i_feeder = cls.compute_bus_current(p_feeder, v_feeder, pf_feeder)

            feeders_data.append({
                "id": f_id,
                "name": cfg["name"],
                "type": cfg["classification"],
                "demand_kw": p_feeder,
                "voltage_kv": v_feeder,
                "current_a": i_feeder,
                "frequency_hz": f_bus2,
                "power_factor": pf_feeder,
                "status": "LIVE",
                "route": f"/feeder/{f_id}"
            })

        return {
            "timestamp": ts_str,
            "timestamp_formatted": ts_formatted,
            "summary": {
                "name": "BUS-2",
                "status": "LIVE",
                "type": "11 kV Distribution Bus",
                "demand_kw": p_bus2,
                "voltage_kv": v_bus2,
                "current_a": i_bus2,
                "frequency_hz": f_bus2,
                "power_factor": cls.POWER_FACTOR,
                "solar_status": solar_b_status,
                "bess_status": bess2_status,
                "feeders_count": 4,
                "substation": "110/11 kV Substation"
            },
            "feeders": feeders_data,
            "solar_b": {
                "name": "SOLAR-B",
                "capacity_kw": 420.0,
                "generation_kw": solar_b_kw,
                "status": solar_b_status,
                "temperature_c": temp_c,
                "grid_import_kw": solar_to_grid_kw,
                "bess_import_kw": solar_to_bess_kw,
                "route": "/solar/B"
            },
            "bess_b": {
                "name": "BESS-B",
                "status": bess2_status,
                "soc_pct": bess2_soc,
                "soh_pct": bess2_soh,
                "power_kw": bess2_power,
                "capacity_kwh": 2000.0,
                "dynamic_reserve_kwh": e_reserve_kwh,
                "dynamic_reserve_soc_pct": soc_reserve_pct,
                "operating_window": "15% – 90%",
                "soc_alert": (bess2_soc < 15.0 or bess2_soc > 90.0),
                "route": "/bess/B"
            }
        }

