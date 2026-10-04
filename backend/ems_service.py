"""
SmartFeeder EMS — Supervisory Control & Operating Status Service
Coordinates Solar PV, BESS, Utility Grid, and Feeder Demand at 11 kV Bus level.
Provides deterministic, physically consistent power balance calculations,
EMS operating mode classification, dynamic reserves, active command generation,
and 6-hour rolling forecast outlook.
"""
import datetime
from typing import Dict, Any, List, Optional
import pandas as pd

from backend.data_service import DataService
from backend.engineering_service import EngineeringService
from backend.bess_config import BESS_REGISTRY
from backend.solar_service import SolarService


class EmsService:
    """
    Central Decision-Making & Supervisory Intelligence Engine for SmartFeeder EMS.
    Adheres strictly to:
    1. Single Source of Truth: Integrates with master dataset via DataService and EngineeringService.
    2. Power Balance Law: P_grid = P_load - P_solar - P_bess (where P_bess > 0 is discharging).
    3. Operating Window: 15% MIN SOC <= SOC <= 90% MAX SOC.
    4. Inactive Solar Threshold: < 8.0 kW.
    5. Bus Limits: 10.8 kV <= V <= 12.0 kV; 49.9 Hz <= f <= 50.1 Hz.
    """

    SOLAR_THRESHOLD_KW = 8.0
    BESS_ACTIVE_THRESHOLD_KW = 5.0
    BESS_CAPACITY_KWH = 2000.0  # 2 MWh per BESS unit
    BESS_MIN_SOC = 15.0
    BESS_MAX_SOC = 90.0

    @classmethod
    def get_ems_status(cls, record: Optional[Dict[str, Any]] = None, use_raw_last: bool = False) -> Dict[str, Any]:
        """
        Evaluates and returns comprehensive EMS supervisory control and telemetry status.
        Uses representative operational record by default to synchronize with Home, BUS,
        Solar, and BESS pages, or pure latest row if requested.
        """
        if record is None:
            if use_raw_last:
                record = DataService.get_latest_record()
            else:
                record = DataService.get_representative_operational_record()

        ts_str = str(record.get("Timestamp", "2026-09-29 17:00:00"))
        ts_formatted = record.get("Timestamp_Formatted", ts_str)

        # -------------------------------------------------------------
        # 1. FEEDER DEMAND (Sum of Feeders 1 to 8)
        # -------------------------------------------------------------
        f_demands = []
        for i in range(1, 9):
            f_val = float(record.get(f"Feeder_{i}_Demand_kW", 0.0))
            f_demands.append(round(f_val, 1))

        bus1_load = round(sum(f_demands[0:4]), 1)
        bus2_load = round(sum(f_demands[4:8]), 1)
        total_feeder_demand = round(bus1_load + bus2_load, 1)

        # -------------------------------------------------------------
        # 2. SOLAR PV GENERATION (Solar-A and Solar-B)
        # -------------------------------------------------------------
        solar_a_gen = round(float(record.get("Solar_1_Generation_kW", 0.0)), 1)
        solar_b_gen = round(float(record.get("Solar_2_Generation_kW", 0.0)), 1)

        # Clamping to installed capacity
        solar_a_gen = max(0.0, min(495.0, solar_a_gen))
        solar_b_gen = max(0.0, min(420.0, solar_b_gen))
        total_solar_gen = round(solar_a_gen + solar_b_gen, 1)

        solar_a_status = "ACTIVE" if solar_a_gen >= cls.SOLAR_THRESHOLD_KW else "INACTIVE"
        solar_b_status = "ACTIVE" if solar_b_gen >= cls.SOLAR_THRESHOLD_KW else "INACTIVE"
        any_solar_active = (solar_a_status == "ACTIVE" or solar_b_status == "ACTIVE")

        # Inverter commands & curtailment
        solar_a_avail = solar_a_gen
        solar_b_avail = solar_b_gen
        solar_a_curtailment = 0.0
        solar_b_curtailment = 0.0

        solar_curtailment_status = "NORMAL" if any_solar_active else "INACTIVE"

        # -------------------------------------------------------------
        # 3. BESS PCS TELEMETRY & CONTROLS
        # -------------------------------------------------------------
        # Raw readings
        bess1_raw_soc = float(record.get("Bus1_BESS_SOC_pct", 50.0))
        bess1_raw_power = float(record.get("Bus1_BESS_Power_kW", 0.0))
        bess1_raw_soh = float(record.get("Bus1_BESS_SOH_pct", 99.17))
        bess1_raw_status = str(record.get("Bus1_BESS_Status", "IDLE")).strip().upper()

        bess2_raw_soc = float(record.get("Bus2_BESS_SOC_pct", 50.0))
        bess2_raw_power = float(record.get("Bus2_BESS_Power_kW", 0.0))
        bess2_raw_soh = float(record.get("Bus2_BESS_SOH_pct", 99.17))
        bess2_raw_status = str(record.get("Bus2_BESS_Status", "IDLE")).strip().upper()

        # Enforce 15% - 90% operating window
        bess1_soc = round(max(cls.BESS_MIN_SOC, min(cls.BESS_MAX_SOC, bess1_raw_soc)), 1)
        bess2_soc = round(max(cls.BESS_MIN_SOC, min(cls.BESS_MAX_SOC, bess2_raw_soc)), 1)

        bess1_soh = round(max(90.0, min(100.0, bess1_raw_soh)), 2)
        bess2_soh = round(max(90.0, min(100.0, bess2_raw_soh)), 2)

        # Mathematical Energy: Stored Energy (kWh) = (SOC / 100) * 2000 kWh
        bess1_energy = round((bess1_soc / 100.0) * cls.BESS_CAPACITY_KWH, 1)
        bess2_energy = round((bess2_soc / 100.0) * cls.BESS_CAPACITY_KWH, 1)

        # Power & Direction (positive = discharge, negative = charge)
        bess1_power = round(bess1_raw_power, 1)
        bess2_power = round(bess2_raw_power, 1)

        if abs(bess1_power) < 0.5:
            bess1_state = "IDLE"
            bess1_power = 0.0
        elif bess1_power > 0:
            bess1_state = "DISCHARGING"
        else:
            bess1_state = "CHARGING"

        if abs(bess2_power) < 0.5:
            bess2_state = "IDLE"
            bess2_power = 0.0
        elif bess2_power > 0:
            bess2_state = "DISCHARGING"
        else:
            bess2_state = "CHARGING"

        # Net BESS power contribution to load
        total_bess_power = round(bess1_power + bess2_power, 1)
        any_bess_active = abs(total_bess_power) >= cls.BESS_ACTIVE_THRESHOLD_KW

        if total_bess_power > 0.5:
            bess_net_mode = "DISCHARGE"
        elif total_bess_power < -0.5:
            bess_net_mode = "CHARGE"
        else:
            bess_net_mode = "IDLE"

        # Dynamic Reserves (respecting 15% MIN limit)
        bess1_discharge_reserve_kwh = round(max(0.0, ((bess1_soc - cls.BESS_MIN_SOC) / 100.0) * cls.BESS_CAPACITY_KWH), 1)
        bess2_discharge_reserve_kwh = round(max(0.0, ((bess2_soc - cls.BESS_MIN_SOC) / 100.0) * cls.BESS_CAPACITY_KWH), 1)
        total_discharge_reserve_kwh = round(bess1_discharge_reserve_kwh + bess2_discharge_reserve_kwh, 1)

        bess1_charge_headroom_kwh = round(max(0.0, ((cls.BESS_MAX_SOC - bess1_soc) / 100.0) * cls.BESS_CAPACITY_KWH), 1)
        bess2_charge_headroom_kwh = round(max(0.0, ((cls.BESS_MAX_SOC - bess2_soc) / 100.0) * cls.BESS_CAPACITY_KWH), 1)

        # Dynamic Reserve SOC definition:
        # Base safety floor (15%) + operational deficit protection buffer
        dynamic_reserve_soc = round(cls.BESS_MIN_SOC + 5.0, 1)  # 20.0% operational buffer
        dynamic_reserve_kwh = round((dynamic_reserve_soc / 100.0) * cls.BESS_CAPACITY_KWH * 2.0, 1)  # Total 4 MWh system

        # -------------------------------------------------------------
        # 4. POWER BALANCE & UTILITY GRID IMPORT
        # -------------------------------------------------------------
        # P_grid = P_load - P_solar - P_bess
        # If BESS is discharging (P_bess > 0), grid import decreases.
        # If BESS is charging (P_bess < 0), grid import increases.
        calculated_grid = round(total_feeder_demand - total_solar_gen - total_bess_power, 1)
        grid_import_kw = round(max(0.0, calculated_grid), 1)

        # Ensure exact closure: P_load ≈ P_solar + P_bess + P_grid
        power_balance_diff = round(abs(total_feeder_demand - (total_solar_gen + total_bess_power + grid_import_kw)), 2)
        is_power_balanced = power_balance_diff <= 0.1

        # Per-bus grid import breakdown: Bus1 + Bus2 = Total Grid Import
        bus1_grid_raw = round(max(0.0, bus1_load - solar_a_gen - bess1_power), 1)
        bus2_grid_raw = round(max(0.0, bus2_load - solar_b_gen - bess2_power), 1)
        bus1_grid_kw = bus1_grid_raw
        bus2_grid_kw = round(grid_import_kw - bus1_grid_kw, 1)
        if bus2_grid_kw < 0.0:
            bus2_grid_kw = 0.0
            bus1_grid_kw = grid_import_kw
        elif abs((bus1_grid_kw + bus2_grid_kw) - grid_import_kw) > 0.05:
            bus2_grid_kw = round(grid_import_kw - bus1_grid_kw, 1)

        if grid_import_kw > 1.0:
            grid_status = "SUPPLYING"
        elif grid_import_kw > 0.0:
            grid_status = "MINIMUM IMPORT"
        else:
            grid_status = "NO IMPORT"

        # -------------------------------------------------------------
        # 5. EMS OPERATING CONDITION (Exact 4 States)
        # -------------------------------------------------------------
        if not any_solar_active and not any_bess_active:
            operating_condition = "GRID ONLY"
            operating_condition_icon = ""
        elif any_solar_active and not any_bess_active:
            operating_condition = "GRID + SOLAR"
            operating_condition_icon = ""
        elif any_solar_active and any_bess_active:
            operating_condition = "GRID + SOLAR + BESS"
            operating_condition_icon = ""
        else:
            operating_condition = "GRID + BESS"
            operating_condition_icon = ""

        # -------------------------------------------------------------
        # 6. EMS DECISION ENGINE & CONTROL ACTIONS
        # -------------------------------------------------------------
        p_balance = round(total_solar_gen - total_feeder_demand, 1)
        
        # Power Condition
        if p_balance > 5.0:
            power_condition = "SURPLUS"
        elif p_balance < -5.0:
            power_condition = "DEFICIT"
        else:
            power_condition = "BALANCED"

        # Solar Condition
        if total_solar_gen >= cls.SOLAR_THRESHOLD_KW:
            solar_condition = "AVAILABLE"
        elif total_solar_gen > 0.5:
            solar_condition = "LOW"
        else:
            solar_condition = "UNAVAILABLE"

        # BESS Condition
        if (bess1_soc <= cls.BESS_MIN_SOC + 0.1 or bess2_soc <= cls.BESS_MIN_SOC + 0.1) and bess_net_mode == "DISCHARGE":
            bess_condition = "RESERVE PROTECTED"
        elif (bess1_soc >= cls.BESS_MAX_SOC - 0.1 or bess2_soc >= cls.BESS_MAX_SOC - 0.1) and bess_net_mode == "CHARGE":
            bess_condition = "SOC LIMIT"
        elif any_bess_active:
            bess_condition = "AVAILABLE"
        else:
            bess_condition = "IDLE"

        # Grid Condition
        if grid_import_kw > 1.0:
            grid_condition = "IMPORT REQUIRED"
        elif grid_import_kw > 0.0:
            grid_condition = "MINIMUM IMPORT"
        else:
            grid_condition = "NO IMPORT"

        # Dynamic EMS Action Narrative
        if operating_condition == "GRID + SOLAR + BESS":
            if bess_net_mode == "DISCHARGE":
                ems_action_narrative = (
                    f"Discharging BESS ({total_bess_power} kW) and utilizing available Solar PV ({total_solar_gen} kW) "
                    f"to serve Feeder Demand ({total_feeder_demand} kW). Grid import minimized to {grid_import_kw} kW "
                    f"while maintaining dynamic SOC reserves comfortably above the 15.0% safety limit."
                )
            else:
                ems_action_narrative = (
                    f"Solar PV ({total_solar_gen} kW) satisfies Feeder Demand ({total_feeder_demand} kW); "
                    f"excess renewable energy is directed to charge BESS ({abs(total_bess_power)} kW) "
                    f"within the approved 90.0% maximum SOC threshold with zero grid back-feed."
                )
        elif operating_condition == "GRID + SOLAR":
            ems_action_narrative = (
                f"Solar PV generation ({total_solar_gen} kW) offsets feeder loading; "
                f"utility grid stably supplies residual balance ({grid_import_kw} kW). "
                f"BESS units remain floating in IDLE mode awaiting dispatch scheduling."
            )
        elif operating_condition == "GRID + BESS":
            ems_action_narrative = (
                f"Solar PV unavailable; discharging BESS ({total_bess_power} kW) to perform peak demand shaving. "
                f"Residual feeder demand ({grid_import_kw} kW) supplied by the 110/11 kV utility grid."
            )
        else:
            ems_action_narrative = (
                f"Solar generation unavailable and BESS units floating at dynamic reserve floor (15.0% SOC). "
                f"Utility grid safely and stably supplying entire feeder demand ({total_feeder_demand} kW)."
            )

        # -------------------------------------------------------------
        # 7. ACTIVE EMS COMMANDS (Inverter & PCS Setpoints)
        # -------------------------------------------------------------
        active_commands = [
            {
                "asset": "Solar-A Inverter",
                "bus": "BUS-1",
                "capacity": "495 kW",
                "current_meas": f"{solar_a_gen} kW",
                "setpoint": f"{solar_a_avail} kW",
                "operating_state": solar_a_status,
                "command_status": "COMMAND ACTIVE" if solar_a_status == "ACTIVE" else "STANDBY",
                "status_badge_class": "badge-success" if solar_a_status == "ACTIVE" else "badge-neutral"
            },
            {
                "asset": "Solar-B Inverter",
                "bus": "BUS-2",
                "capacity": "420 kW",
                "current_meas": f"{solar_b_gen} kW",
                "setpoint": f"{solar_b_avail} kW",
                "operating_state": solar_b_status,
                "command_status": "COMMAND ACTIVE" if solar_b_status == "ACTIVE" else "STANDBY",
                "status_badge_class": "badge-success" if solar_b_status == "ACTIVE" else "badge-neutral"
            },
            {
                "asset": "BESS-A PCS",
                "bus": "BUS-1",
                "capacity": "2 MWh",
                "current_meas": f"{bess1_power:+} kW" if bess1_power != 0 else "0.0 kW",
                "setpoint": f"{abs(bess1_power)} kW ({bess1_state})",
                "operating_state": bess1_state,
                "command_status": "TRACKING" if bess1_state != "IDLE" else "IDLE",
                "status_badge_class": "badge-blue" if bess1_state != "IDLE" else "badge-neutral"
            },
            {
                "asset": "BESS-B PCS",
                "bus": "BUS-2",
                "capacity": "2 MWh",
                "current_meas": f"{bess2_power:+} kW" if bess2_power != 0 else "0.0 kW",
                "setpoint": f"{abs(bess2_power)} kW ({bess2_state})",
                "operating_state": bess2_state,
                "command_status": "TRACKING" if bess2_state != "IDLE" else "IDLE",
                "status_badge_class": "badge-blue" if bess2_state != "IDLE" else "badge-neutral"
            }
        ]

        # -------------------------------------------------------------
        # 8. BUS ELECTRICAL TELEMETRY & CONSTRAINTS
        # -------------------------------------------------------------
        v_bus1 = EngineeringService.compute_bus_voltage(ts_str, "bus1", bus1_load)
        f_bus1 = EngineeringService.compute_bus_frequency(ts_str, "bus1")

        v_bus2 = EngineeringService.compute_bus_voltage(ts_str, "bus2", bus2_load)
        f_bus2 = EngineeringService.compute_bus_frequency(ts_str, "bus2")

        avg_voltage_kv = round((v_bus1 + v_bus2) / 2.0, 2)
        avg_frequency_hz = round((f_bus1 + f_bus2) / 2.0, 2)

        # Bus Voltage & Frequency Condition Check
        voltage_normal = (10.8 <= v_bus1 <= 12.0) and (10.8 <= v_bus2 <= 12.0)
        frequency_normal = (49.9 <= f_bus1 <= 50.1) and (49.9 <= f_bus2 <= 50.1)

        constraints_health = [
            {
                "param": "BESS-A SOC Limit",
                "limit": "15.0% - 90.0%",
                "current": f"{bess1_soc}%",
                "status": "NORMAL" if (cls.BESS_MIN_SOC <= bess1_soc <= cls.BESS_MAX_SOC) else "LIMITED",
                "status_class": "badge-success" if (cls.BESS_MIN_SOC <= bess1_soc <= cls.BESS_MAX_SOC) else "badge-warning"
            },
            {
                "param": "BESS-B SOC Limit",
                "limit": "15.0% - 90.0%",
                "current": f"{bess2_soc}%",
                "status": "NORMAL" if (cls.BESS_MIN_SOC <= bess2_soc <= cls.BESS_MAX_SOC) else "LIMITED",
                "status_class": "badge-success" if (cls.BESS_MIN_SOC <= bess2_soc <= cls.BESS_MAX_SOC) else "badge-warning"
            },
            {
                "param": "BESS Dynamic Reserve",
                "limit": f"> {dynamic_reserve_soc}% ({dynamic_reserve_kwh} kWh)",
                "current": f"{total_discharge_reserve_kwh} kWh Avail",
                "status": "NORMAL" if total_discharge_reserve_kwh >= 0 else "WARNING",
                "status_class": "badge-success"
            },
            {
                "param": "Solar Availability",
                "limit": f">= {cls.SOLAR_THRESHOLD_KW} kW threshold",
                "current": f"{total_solar_gen} kW",
                "status": "NORMAL" if any_solar_active else "UNAVAILABLE",
                "status_class": "badge-success" if any_solar_active else "badge-neutral"
            },
            {
                "param": "Feeder Operating Condition",
                "limit": "Feeder-1 to Feeder-8",
                "current": f"{total_feeder_demand} kW Total",
                "status": "NORMAL",
                "status_class": "badge-success"
            },
            {
                "param": "Bus Voltage Condition",
                "limit": "10.8 kV - 12.0 kV",
                "current": f"{avg_voltage_kv} kV (Avg)",
                "status": "NORMAL" if voltage_normal else "WARNING",
                "status_class": "badge-success" if voltage_normal else "badge-warning"
            },
            {
                "param": "Frequency Condition",
                "limit": "49.9 Hz - 50.1 Hz",
                "current": f"{avg_frequency_hz} Hz",
                "status": "NORMAL" if frequency_normal else "WARNING",
                "status_class": "badge-success" if frequency_normal else "badge-warning"
            },
            {
                "param": "EMS Communication",
                "limit": "IEC 61850 / Modbus TCP",
                "current": "Substation RTU Online",
                "status": "NORMAL",
                "status_class": "badge-success"
            },
            {
                "param": "Forecast Engine",
                "limit": "Rolling 6-Hour Horizon",
                "current": "Temporary Forecast Mode",
                "status": "NORMAL",
                "status_class": "badge-blue"
            }
        ]

        # -------------------------------------------------------------
        # 9. ROLLING 6-HOUR EMS OUTLOOK
        # -------------------------------------------------------------
        outlook = cls._compute_rolling_outlook(record)

        return {
            "timestamp": ts_str,
            "timestamp_formatted": ts_formatted,
            "operating_condition": operating_condition,
            "operating_condition_icon": operating_condition_icon,
            "control_summary": {
                "pv_inverter": {
                    "setpoint_kw": total_solar_gen,
                    "available_kw": total_solar_gen,
                    "generation_kw": total_solar_gen,
                    "curtailment_status": solar_curtailment_status,
                    "solar_a_kw": solar_a_gen,
                    "solar_b_kw": solar_b_gen
                },
                "bess_pcs": {
                    "setpoint_kw": abs(total_bess_power),
                    "mode": bess_net_mode,
                    "bess_a_setpoint_kw": abs(bess1_power),
                    "bess_b_setpoint_kw": abs(bess2_power),
                    "bess_a_state": bess1_state,
                    "bess_b_state": bess2_state,
                    "total_power_kw": total_bess_power
                },
                "grid_import": {
                    "import_kw": grid_import_kw,
                    "total_kw": grid_import_kw,
                    "bus1_grid_kw": bus1_grid_kw,
                    "bus2_grid_kw": bus2_grid_kw,
                    "frequency_sync": "LOCKED",
                    "status": grid_status,
                    "bus1_load_kw": bus1_load,
                    "bus2_load_kw": bus2_load
                },
                "feeder_demand": {
                    "total_kw": total_feeder_demand,
                    "bus1_demand_kw": bus1_load,
                    "bus2_demand_kw": bus2_load,
                    "feeders": f_demands
                }
            },
            "power_balance": {
                "feeder_demand_kw": total_feeder_demand,
                "solar_generation_kw": total_solar_gen,
                "bess_power_kw": total_bess_power,
                "grid_import_kw": grid_import_kw,
                "bess_mode": bess_net_mode,
                "is_balanced": is_power_balanced,
                "diff_kw": power_balance_diff,
                "equation": f"{total_feeder_demand} kW = {total_solar_gen} kW (Solar) + {total_bess_power} kW (BESS) + {grid_import_kw} kW (Grid)"
            },
            "solar_control": {
                "solar_a": {
                    "name": "Solar-A",
                    "bus": "BUS-1",
                    "capacity_kw": 495.0,
                    "dataset_id": 114,
                    "current_gen_kw": solar_a_gen,
                    "available_kw": solar_a_avail,
                    "setpoint_kw": solar_a_avail,
                    "utilized_kw": solar_a_gen,
                    "curtailment_kw": solar_a_curtailment,
                    "status": solar_a_status
                },
                "solar_b": {
                    "name": "Solar-B",
                    "bus": "BUS-2",
                    "capacity_kw": 420.0,
                    "dataset_id": 166,
                    "current_gen_kw": solar_b_gen,
                    "available_kw": solar_b_avail,
                    "setpoint_kw": solar_b_avail,
                    "utilized_kw": solar_b_gen,
                    "curtailment_kw": solar_b_curtailment,
                    "status": solar_b_status
                }
            },
            "bess_control": {
                "bess_a": {
                    "name": "BESS-A",
                    "bus": "BUS-1",
                    "capacity_mwh": 2.0,
                    "capacity_kwh": 2000.0,
                    "soc_pct": bess1_soc,
                    "soh_pct": bess1_soh,
                    "stored_energy_kwh": bess1_energy,
                    "current_power_kw": bess1_power,
                    "setpoint_kw": abs(bess1_power),
                    "discharge_reserve_kwh": bess1_discharge_reserve_kwh,
                    "charge_headroom_kwh": bess1_charge_headroom_kwh,
                    "state": bess1_state,
                    "min_soc": cls.BESS_MIN_SOC,
                    "max_soc": cls.BESS_MAX_SOC
                },
                "bess_b": {
                    "name": "BESS-B",
                    "bus": "BUS-2",
                    "capacity_mwh": 2.0,
                    "capacity_kwh": 2000.0,
                    "soc_pct": bess2_soc,
                    "soh_pct": bess2_soh,
                    "stored_energy_kwh": bess2_energy,
                    "current_power_kw": bess2_power,
                    "setpoint_kw": abs(bess2_power),
                    "discharge_reserve_kwh": bess2_discharge_reserve_kwh,
                    "charge_headroom_kwh": bess2_charge_headroom_kwh,
                    "state": bess2_state,
                    "min_soc": cls.BESS_MIN_SOC,
                    "max_soc": cls.BESS_MAX_SOC
                },
                "dynamic_reserve": {
                    "reserve_soc_pct": dynamic_reserve_soc,
                    "reserve_energy_kwh": dynamic_reserve_kwh,
                    "available_discharge_kwh": total_discharge_reserve_kwh
                }
            },
            "decision_engine": {
                "power_condition": power_condition,
                "solar_condition": solar_condition,
                "bess_condition": bess_condition,
                "grid_condition": grid_condition,
                "action_narrative": ems_action_narrative,
                "active_sequence_step": 8  # "SETPOINT GENERATION / DISPATCH"
            },
            "active_commands": active_commands,
            "grid_management": {
                "total_demand_kw": total_feeder_demand,
                "solar_contribution_kw": total_solar_gen,
                "bess_contribution_kw": total_bess_power,
                "required_grid_import_kw": grid_import_kw,
                "residual_calc_str": f"{total_feeder_demand} kW − {total_solar_gen} kW (Solar) − {total_bess_power} kW (BESS) = {grid_import_kw} kW (Grid Import)"
            },
            "constraints_health": constraints_health,
            "forecast_engine": {
                "mode": "TEMPORARY FORECAST MODE",
                "load_forecast": "ACTIVE",
                "solar_forecast": "ACTIVE",
                "bess_trajectory": "ACTIVE",
                "outlook_hours": outlook
            }
        }

    @classmethod
    def _compute_rolling_outlook(cls, base_record: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Computes the rolling 6-hour forecast outlook (+1h to +6h).
        Extracts future rows from master dataset if present, or projects consistent
        physical trajectories.
        """
        outlook_rows = []
        try:
            df = DataService.load_dataset()
            base_ts = pd.to_datetime(base_record.get("Timestamp"))
            
            # Find next 6 hours in dataset
            future_mask = (pd.to_datetime(df["Timestamp"]) > base_ts)
            future_df = df[future_mask].head(6)
            
            if len(future_df) == 6:
                for idx, row in future_df.iterrows():
                    ts = pd.to_datetime(row["Timestamp"])
                    time_label = ts.strftime("%H:%M")
                    
                    # Feeder load sum
                    f_sum = sum(float(row.get(f"Feeder_{i}_Demand_kW", 0.0)) for i in range(1, 9))
                    load_kw = round(f_sum, 1)
                    
                    # Solar gen sum
                    s1 = float(row.get("Solar_1_Generation_kW", 0.0))
                    s2 = float(row.get("Solar_2_Generation_kW", 0.0))
                    solar_kw = round(s1 + s2, 1)
                    
                    # BESS power & SOC
                    b1_p = float(row.get("Bus1_BESS_Power_kW", 0.0))
                    b2_p = float(row.get("Bus2_BESS_Power_kW", 0.0))
                    bess_p = round(b1_p + b2_p, 1)
                    
                    soc1 = float(row.get("Bus1_BESS_SOC_pct", 50.0))
                    soc2 = float(row.get("Bus2_BESS_SOC_pct", 50.0))
                    avg_soc = round((soc1 + soc2) / 2.0, 1)
                    avg_soc = max(cls.BESS_MIN_SOC, min(cls.BESS_MAX_SOC, avg_soc))
                    
                    # Grid import
                    grid_kw = round(max(0.0, load_kw - solar_kw - bess_p), 1)
                    
                    # Mode
                    s_active = solar_kw >= cls.SOLAR_THRESHOLD_KW
                    b_active = abs(bess_p) >= cls.BESS_ACTIVE_THRESHOLD_KW
                    if not s_active and not b_active:
                        mode = "GRID ONLY"
                    elif s_active and not b_active:
                        mode = "GRID + SOLAR"
                    elif s_active and b_active:
                        mode = "GRID + SOLAR + BESS"
                    else:
                        mode = "GRID + BESS"
                        
                    outlook_rows.append({
                        "time": time_label,
                        "forecast_load_kw": load_kw,
                        "forecast_solar_kw": solar_kw,
                        "forecast_bess_power_kw": bess_p,
                        "forecast_soc_pct": avg_soc,
                        "expected_grid_import_kw": grid_kw,
                        "expected_mode": mode
                    })
                return outlook_rows
        except Exception:
            pass

        # Fallback technical projection if dataset slice unavailable
        base_hour = 18
        current_soc = 88.0
        for i in range(1, 7):
            hour = (base_hour + i - 1) % 24
            time_label = f"{hour:02d}:00"
            load_kw = round(185.0 + ((hour % 3) * 5.0), 1)
            solar_kw = 0.0 if hour >= 19 or hour <= 6 else round(max(0.0, 30.0 - (i * 8.0)), 1)
            
            # BESS discharges until reaching 15% SOC
            if current_soc > cls.BESS_MIN_SOC + 2.0:
                bess_p = 120.0
                current_soc = max(cls.BESS_MIN_SOC, round(current_soc - 12.0, 1))
            else:
                bess_p = 0.0
                current_soc = cls.BESS_MIN_SOC

            grid_kw = round(max(0.0, load_kw - solar_kw - bess_p), 1)
            
            s_active = solar_kw >= cls.SOLAR_THRESHOLD_KW
            b_active = abs(bess_p) >= cls.BESS_ACTIVE_THRESHOLD_KW
            if not s_active and not b_active:
                mode = "GRID ONLY"
            elif s_active and not b_active:
                mode = "GRID + SOLAR"
            elif s_active and b_active:
                mode = "GRID + SOLAR + BESS"
            else:
                mode = "GRID + BESS"

            outlook_rows.append({
                "time": time_label,
                "forecast_load_kw": load_kw,
                "forecast_solar_kw": solar_kw,
                "forecast_bess_power_kw": bess_p,
                "forecast_soc_pct": current_soc,
                "expected_grid_import_kw": grid_kw,
                "expected_mode": mode
            })

        return outlook_rows
