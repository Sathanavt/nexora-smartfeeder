"""
SmartFeeder EMS — Single Source of Truth for Feeder Identity & Classification
Centralized, immutable configuration for all 8 feeders across the entire application.
"""

from typing import Dict, Any, List

FEEDER_REGISTRY: Dict[int, Dict[str, Any]] = {
    1: {
        "id": 1,
        "source_id": 107,
        "name": "FEEDER-1",
        "type": "Residential Feeder",
        "classification": "Residential Feeder",
        "bus": "BUS-1",
        "bus_id": 1,
        "bus_route": "/bus/1",
        "column": "Feeder_1_Demand_kW",
        "pf_base": 0.96
    },
    2: {
        "id": 2,
        "source_id": 119,
        "name": "FEEDER-2",
        "type": "Commercial Feeder",
        "classification": "Commercial Feeder",
        "bus": "BUS-1",
        "bus_id": 1,
        "bus_route": "/bus/1",
        "column": "Feeder_2_Demand_kW",
        "pf_base": 0.94
    },
    3: {
        "id": 3,
        "source_id": 129,
        "name": "FEEDER-3",
        "type": "Industrial Feeder",
        "classification": "Industrial Feeder",
        "bus": "BUS-1",
        "bus_id": 1,
        "bus_route": "/bus/1",
        "column": "Feeder_3_Demand_kW",
        "pf_base": 0.92
    },
    4: {
        "id": 4,
        "source_id": 135,
        "name": "FEEDER-4",
        "type": "Mixed / Critical Load",
        "classification": "Mixed / Critical Load",
        "bus": "BUS-1",
        "bus_id": 1,
        "bus_route": "/bus/1",
        "column": "Feeder_4_Demand_kW",
        "pf_base": 0.95
    },
    5: {
        "id": 5,
        "source_id": 145,
        "name": "FEEDER-5",
        "type": "Commercial Feeder",
        "classification": "Commercial Feeder",
        "bus": "BUS-2",
        "bus_id": 2,
        "bus_route": "/bus/2",
        "column": "Feeder_5_Demand_kW",
        "pf_base": 0.94
    },
    6: {
        "id": 6,
        "source_id": 152,
        "name": "FEEDER-6",
        "type": "Rural / Agricultural Feeder",
        "classification": "Rural / Agricultural Feeder",
        "bus": "BUS-2",
        "bus_id": 2,
        "bus_route": "/bus/2",
        "column": "Feeder_6_Demand_kW",
        "pf_base": 0.91
    },
    7: {
        "id": 7,
        "source_id": 155,
        "name": "FEEDER-7",
        "type": "Industrial / Manufacturing Feeder",
        "classification": "Industrial / Manufacturing Feeder",
        "bus": "BUS-2",
        "bus_id": 2,
        "bus_route": "/bus/2",
        "column": "Feeder_7_Demand_kW",
        "pf_base": 0.93
    },
    8: {
        "id": 8,
        "source_id": 157,
        "name": "FEEDER-8",
        "type": "Residential / Municipal Feeder",
        "classification": "Residential / Municipal Feeder",
        "bus": "BUS-2",
        "bus_id": 2,
        "bus_route": "/bus/2",
        "column": "Feeder_8_Demand_kW",
        "pf_base": 0.95
    }
}

def get_feeder_config(feeder_id: int) -> Dict[str, Any]:
    """Returns the immutable configuration for a given feeder ID (1-8) or source ID."""
    if feeder_id in FEEDER_REGISTRY:
        return dict(FEEDER_REGISTRY[feeder_id])
    for cfg in FEEDER_REGISTRY.values():
        if cfg.get("source_id") == feeder_id:
            return dict(cfg)
    return dict(FEEDER_REGISTRY[1])

def get_feeders_by_bus(bus_id: int) -> List[Dict[str, Any]]:
    """Returns the list of feeder configurations associated with a specific bus (1 or 2)."""
    return [dict(cfg) for cfg in FEEDER_REGISTRY.values() if cfg["bus_id"] == bus_id]
