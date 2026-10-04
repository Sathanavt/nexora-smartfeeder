"""
SmartFeeder EMS — Centralized Solar Assets Registry (Single Source of Truth)

Defines fixed asset configurations for Solar-A (BUS-1) and Solar-B (BUS-2).
These mappings are permanently frozen and strictly aligned with the master dataset.
"""
from typing import Dict, Any

SOLAR_REGISTRY: Dict[str, Dict[str, Any]] = {
    "a": {
        "id": "a",
        "key": "a",
        "name": "Solar-A",
        "title": "SOLAR-A",
        "subtitle": "Solar PV Generation Analysis",
        "bus": "BUS-1",
        "bus_id": 1,
        "bus_route": "/bus/1",
        "capacity_kw": 495.0,
        "installed_capacity_text": "495 kW",
        "source_id": 114,
        "column": "Solar_1_Generation_kW",
        "bess_name": "BESS-A",
        "bess_column": "Bus1_BESS_Power_kW",
        "bess_status_column": "Bus1_BESS_Status",
        "feeder_columns": [
            "Feeder_1_Demand_kW",
            "Feeder_2_Demand_kW",
            "Feeder_3_Demand_kW",
            "Feeder_4_Demand_kW"
        ]
    },
    "b": {
        "id": "b",
        "key": "b",
        "name": "Solar-B",
        "title": "SOLAR-B",
        "subtitle": "Solar PV Generation Analysis",
        "bus": "BUS-2",
        "bus_id": 2,
        "bus_route": "/bus/2",
        "capacity_kw": 420.0,
        "installed_capacity_text": "420 kW",
        "source_id": 166,
        "column": "Solar_2_Generation_kW",
        "bess_name": "BESS-B",
        "bess_column": "Bus2_BESS_Power_kW",
        "bess_status_column": "Bus2_BESS_Status",
        "feeder_columns": [
            "Feeder_5_Demand_kW",
            "Feeder_6_Demand_kW",
            "Feeder_7_Demand_kW",
            "Feeder_8_Demand_kW"
        ]
    }
}

def get_solar_config(solar_id: Any) -> Dict[str, Any]:
    """
    Retrieves the solar configuration for a given identifier (a, b, A, B, 1, 2, etc.).
    Defaults to Solar-A if unrecognized.
    """
    normalized = str(solar_id).strip().lower()
    if normalized in ("a", "1", "solar-a", "solar_a"):
        return SOLAR_REGISTRY["a"]
    elif normalized in ("b", "2", "solar-b", "solar_b"):
        return SOLAR_REGISTRY["b"]
    return SOLAR_REGISTRY["a"]
