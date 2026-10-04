"""
SmartFeeder EMS — Centralized BESS Configuration (Single Source of Truth)

Defines fixed asset configurations for BESS-A (BUS-1, 2 MWh) and BESS-B (BUS-2, 2 MWh).
These mappings are permanently frozen and strictly aligned with the master dataset.
"""
from typing import Dict, Any

BESS_REGISTRY: Dict[str, Dict[str, Any]] = {
    "a": {
        "id": "a",
        "key": "a",
        "name": "BESS-A",
        "title": "BESS-A",
        "full_name": "BESS-A Detailed Energy Storage Analysis",
        "subtitle": "2 MWh Utility-Scale Battery Energy Storage System",
        "bus": "BUS-1",
        "bus_id": 1,
        "bus_route": "/bus/1",
        "solar_name": "Solar-A",
        "solar_route": "/solar/a",
        "solar_capacity_kw": 495.0,
        "energy_capacity_mwh": 2.0,
        "energy_capacity_kwh": 2000.0,
        "usable_energy_capacity_kwh": 1500.0,  # 15% to 90% window = 75% of 2000 kWh = 1500 kWh
        "soc_min_pct": 15.0,
        "soc_max_pct": 90.0,
        "nominal_power_kw": 500.0,
        "dataset_columns": {
            "soc": "Bus1_BESS_SOC_pct",
            "power": "Bus1_BESS_Power_kW",
            "energy": "Bus1_BESS_Energy_kWh",
            "soh": "Bus1_BESS_SOH_pct",
            "available_capacity": "Bus1_BESS_Available_Capacity_kWh",
            "status": "Bus1_BESS_Status"
        }
    },
    "b": {
        "id": "b",
        "key": "b",
        "name": "BESS-B",
        "title": "BESS-B",
        "full_name": "BESS-B Detailed Energy Storage Analysis",
        "subtitle": "2 MWh Utility-Scale Battery Energy Storage System",
        "bus": "BUS-2",
        "bus_id": 2,
        "bus_route": "/bus/2",
        "solar_name": "Solar-B",
        "solar_route": "/solar/b",
        "solar_capacity_kw": 420.0,
        "energy_capacity_mwh": 2.0,
        "energy_capacity_kwh": 2000.0,
        "usable_energy_capacity_kwh": 1500.0,  # 15% to 90% window = 75% of 2000 kWh = 1500 kWh
        "soc_min_pct": 15.0,
        "soc_max_pct": 90.0,
        "nominal_power_kw": 500.0,
        "dataset_columns": {
            "soc": "Bus2_BESS_SOC_pct",
            "power": "Bus2_BESS_Power_kW",
            "energy": "Bus2_BESS_Energy_kWh",
            "soh": "Bus2_BESS_SOH_pct",
            "available_capacity": "Bus2_BESS_Available_Capacity_kWh",
            "status": "Bus2_BESS_Status"
        }
    }
}


def get_bess_config(bess_id: Any) -> Dict[str, Any]:
    """
    Retrieves the BESS configuration for a given identifier (a, b, A, B, 1, 2, etc.).
    Defaults to BESS-A if unrecognized.
    """
    clean_id = str(bess_id).strip().lower()
    if clean_id in ("b", "2", "bess-b", "bess_b"):
        return BESS_REGISTRY["b"]
    return BESS_REGISTRY["a"]
