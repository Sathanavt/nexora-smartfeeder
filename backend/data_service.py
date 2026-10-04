import os
import glob
import pandas as pd
from typing import Optional, Dict, Any

class DataService:
    """
    Service for loading and querying the master SmartFeeder EMS Excel dataset.
    Strictly read-only; never modifies the master workbook.
    """
    _df: Optional[pd.DataFrame] = None
    _workbook_path: Optional[str] = None

    @classmethod
    def find_master_workbook(cls) -> Optional[str]:
        """Locates the master dataset Excel workbook across configured paths."""
        custom_env = os.environ.get("EXCEL_DATASET_PATH")
        if custom_env and os.path.exists(custom_env):
            return custom_env

        candidate_patterns = [
            os.path.join(os.path.dirname(__file__), "data", "*.xlsx"),
            os.path.join(os.path.dirname(__file__), "..", "data", "*.xlsx"),
            r"C:\Users\satha\Downloads\Final master data sheet for 110_11kv SS(1).xlsx",
            r"C:\Users\satha\Downloads\Final master data sheet for 110_11kv SS*.xlsx",
            r"C:\Users\satha\Downloads\110_11KV SS - FEEDER DEMAND,SOLAR GENERATION & BESS DATA*.xlsx",
            os.path.join(os.path.dirname(__file__), "..", "..", "*110_11kv*.xlsx"),
        ]

        for pattern in candidate_patterns:
            matches = glob.glob(pattern)
            if matches:
                return matches[0]

        return None

    @classmethod
    def load_dataset(cls) -> pd.DataFrame:
        """Loads and caches the master dataset sheet."""
        if cls._df is not None:
            return cls._df

        path = cls.find_master_workbook()
        if not path or not os.path.exists(path):
            raise FileNotFoundError(f"Master dataset workbook not found at candidate paths.")

        cls._workbook_path = path

        # Try loading 'Live_Data' sheet first as required
        try:
            df = pd.read_excel(path, sheet_name="Live_Data")
        except Exception:
            # Fallback to first available sheet if name differs
            xl = pd.ExcelFile(path)
            sheet = "Live_Data" if "Live_Data" in xl.sheet_names else xl.sheet_names[0]
            df = pd.read_excel(path, sheet_name=sheet)

        # Clean column names
        df.columns = [str(c).strip() for c in df.columns]

        # Numeric conversions
        numeric_cols = [
            "Feeder_1_Demand_kW", "Feeder_2_Demand_kW", "Feeder_3_Demand_kW", "Feeder_4_Demand_kW",
            "Feeder_5_Demand_kW", "Feeder_6_Demand_kW", "Feeder_7_Demand_kW", "Feeder_8_Demand_kW",
            "Solar_1_Generation_kW", "Solar_2_Generation_kW", "Temperature_C",
            "Bus1_BESS_SOC_pct", "Bus1_BESS_Power_kW", "Bus1_BESS_Energy_kWh", "Bus1_BESS_SOH_pct", "Bus1_BESS_Available_Capacity_kWh",
            "Bus2_BESS_SOC_pct", "Bus2_BESS_Power_kW", "Bus2_BESS_Energy_kWh", "Bus2_BESS_SOH_pct", "Bus2_BESS_Available_Capacity_kWh"
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        # Standardize BESS Status strings
        for status_col in ["Bus1_BESS_Status", "Bus2_BESS_Status"]:
            if status_col in df.columns:
                df[status_col] = df[status_col].astype(str).str.strip().str.upper()

        cls._df = df
        return cls._df

    @classmethod
    def get_latest_record(cls) -> Dict[str, Any]:
        """Returns the latest available record as a dictionary."""
        df = cls.load_dataset()
        if df.empty:
            raise ValueError("Dataset is empty.")
        
        last_row = df.iloc[-1].to_dict()
        
        # Ensure timestamp is clean string
        if "Timestamp" in last_row:
            ts = last_row["Timestamp"]
            if hasattr(ts, "strftime"):
                last_row["Timestamp_Formatted"] = ts.strftime("%d-%b-%Y %H:%M")
                last_row["Timestamp_ISO"] = ts.isoformat()
            else:
                last_row["Timestamp_Formatted"] = str(ts)
                last_row["Timestamp_ISO"] = str(ts)
        else:
            last_row["Timestamp_Formatted"] = "Latest Telemetry"
            last_row["Timestamp_ISO"] = ""

        return last_row

    @classmethod
    def get_representative_operational_record(cls) -> Dict[str, Any]:
        """
        Returns a rich operational record (e.g. active solar / DER participation)
        if the very last record of the dataset occurs at late night (23:00) with zero solar,
        while maintaining full actual data integrity.
        """
        df = cls.load_dataset()
        if df.empty:
            raise ValueError("Dataset is empty.")

        # Find latest record where daytime solar or BESS was actively operating,
        # or fallback to absolute last row
        active_day = df[(df["Solar_1_Generation_kW"] >= 8.0) | (df["Solar_2_Generation_kW"] >= 8.0)]
        if not active_day.empty:
            record = active_day.iloc[-1].to_dict()
        else:
            record = df.iloc[-1].to_dict()

        if "Timestamp" in record:
            ts = record["Timestamp"]
            if hasattr(ts, "strftime"):
                record["Timestamp_Formatted"] = ts.strftime("%d-%b-%Y %H:%M")
                record["Timestamp_ISO"] = ts.isoformat()
            else:
                record["Timestamp_Formatted"] = str(ts)
                record["Timestamp_ISO"] = str(ts)

        return record
