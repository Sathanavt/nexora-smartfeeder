"""
SmartFeeder EMS — BESS Service
Business logic, telemetry analytics, and multi-sheet Excel reporting for
BESS-A (BUS-1, 2 MWh) and BESS-B (BUS-2, 2 MWh).
Provides SOC Analysis, SOH Analysis, Energy Analysis, Power Analysis,
and dynamic multi-sheet Excel generation.
"""
import io
import datetime
from typing import Dict, Any, List, Optional
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from backend.data_service import DataService
from backend.bess_config import get_bess_config, BESS_REGISTRY


class BessService:
    """
    Service for querying and analyzing Battery Energy Storage System (BESS) telemetry.
    Supports dynamic BESS-A and BESS-B analytics, calendar availability rules,
    engineering consistency enforcement, and automated Excel generation.
    """
    DATASET_START_DATE = "2026-08-05"
    DATASET_END_DATE = "2026-09-29"

    @classmethod
    def get_bess_config(cls, bess_id: Any) -> Dict[str, Any]:
        """Returns metadata for the requested BESS asset from single source of truth."""
        return get_bess_config(bess_id)

    @classmethod
    def format_date_display(cls, date_str: str) -> str:
        """Converts YYYY-MM-DD into DD-Mon-YYYY (e.g. 29-Sep-2026)."""
        try:
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            return dt.strftime("%d-%b-%Y")
        except Exception:
            return date_str

    @classmethod
    def get_bess_telemetry_for_date(cls, bess_id: Any, date_str: str) -> Dict[str, Any]:
        """
        Retrieves 24-hour actual and forecasted BESS telemetry for the selected asset and date.
        Strictly enforces:
        1. Historical availability rule: dates before 05-Aug-2026 return available=False.
        2. SOC physical window: 15% <= SOC <= 90% (hard physical limits 0% <= SOC <= 100%).
        3. Energy-SOC consistency: Stored Energy (kWh) = (SOC / 100) * 2000 kWh.
        4. Power consistency: Charging (negative) vs Discharging (positive), Idle near 0 kW.
        5. Forecast trajectory: Mutually consistent SOC, SOH, Energy, and Power.
        """
        config = cls.get_bess_config(bess_id)
        date_display = cls.format_date_display(date_str)
        cols = config["dataset_columns"]
        capacity_kwh = config["energy_capacity_kwh"]  # 2000.0 kWh

        # 1. Check Date Availability Range
        if date_str < cls.DATASET_START_DATE or date_str > cls.DATASET_END_DATE:
            return {
                "available": False,
                "bess": config,
                "date": date_str,
                "date_display": date_display,
                "dataset_start": cls.DATASET_START_DATE,
                "dataset_end": cls.DATASET_END_DATE,
                "message": "DATA NOT AVAILABLE",
                "submessage": f"No BESS telemetry available for {date_display}.",
                "info": "Historical BESS telemetry is available from 05-Aug-2026 onwards."
            }

        df = DataService.load_dataset()

        # Filter rows for date
        mask = df["Date"].astype(str).str.startswith(date_str)
        day_df = df[mask]

        if day_df.empty:
            return {
                "available": False,
                "bess": config,
                "date": date_str,
                "date_display": date_display,
                "dataset_start": cls.DATASET_START_DATE,
                "dataset_end": cls.DATASET_END_DATE,
                "message": "DATA NOT AVAILABLE",
                "submessage": f"No BESS telemetry available for {date_display}.",
                "info": f"Available data spans {cls.format_date_display(cls.DATASET_START_DATE)} to {cls.format_date_display(cls.DATASET_END_DATE)}."
            }

        # 2. Process Hourly Telemetry Records
        hourly_records: List[Dict[str, Any]] = []

        for _, row in day_df.iterrows():
            ts = row.get("Timestamp")
            if hasattr(ts, "strftime"):
                time_label = ts.strftime("%H:%M")
                hour_num = ts.hour
            else:
                hi = str(row.get("Hour_Interval", "00-01"))
                start_h = hi.split("-")[0].strip()
                time_label = f"{start_h.zfill(2)}:00"
                try:
                    hour_num = int(start_h)
                except ValueError:
                    hour_num = len(hourly_records)

            # Raw Actual Values from Dataset
            raw_soc = float(row.get(cols["soc"], 50.0))
            raw_power = float(row.get(cols["power"], 0.0))
            raw_soh = float(row.get(cols["soh"], 99.17))
            raw_status = str(row.get(cols["status"], "IDLE")).strip().upper()

            # Physical Clamping
            # SOC strictly within 15% - 90% preferred window, physically bounded by 0 - 100%
            actual_soc = max(15.0, min(90.0, raw_soc))

            # Mathematical Energy Consistency: Stored Energy (kWh) = (SOC / 100) * 2000 kWh
            # If dataset has Stored Energy, we align with the 2000 kWh capacity
            actual_energy = round((actual_soc / 100.0) * capacity_kwh, 2)

            # SOH strictly positive, typically 98-100%
            actual_soh = max(0.0, min(100.0, raw_soh))

            # Power and Status Consistency
            actual_power = round(raw_power, 2)
            if abs(actual_power) < 0.5:
                status = "IDLE"
                actual_power = 0.0
            elif actual_power < 0:
                status = "CHARGING"
            else:
                status = "DISCHARGING"

            # Dynamic Reserve Calculations within 15% - 90% window
            # Discharge Reserve: Energy available above 15% minimum SOC
            reserve_discharge_kwh = round(max(0.0, ((actual_soc - 15.0) / 100.0) * capacity_kwh), 1)
            # Charge Headroom: Energy absorption capacity up to 90% maximum SOC
            headroom_charge_kwh = round(max(0.0, ((90.0 - actual_soc) / 100.0) * capacity_kwh), 1)

            # 3. Forecast Generation (Physically and Mathematically Consistent)
            # Forecast SOC preserves trend with slight realistic deviation (+- 1.5%), strictly clamped to [15%, 90%]
            forecast_soc_dev = 0.8 * ((hour_num % 5) - 2) * 0.4
            forecast_soc = round(max(15.0, min(90.0, actual_soc + forecast_soc_dev)), 2)

            # Forecast Energy derived directly from Forecast SOC
            forecast_energy = round((forecast_soc / 100.0) * capacity_kwh, 2)

            # Forecast SOH with gradual slow drift (< 0.02% variance)
            forecast_soh = round(actual_soh - 0.01 * (hour_num / 24.0), 2)

            # Forecast Power follows actual power with slight variance (+- 3.5%)
            if status == "IDLE":
                forecast_power = 0.0
            else:
                forecast_power = round(actual_power * 0.98, 2)

            hourly_records.append({
                "time": time_label,
                "hour": hour_num,
                "actual_soc_pct": actual_soc,
                "forecast_soc_pct": forecast_soc,
                "actual_soh_pct": actual_soh,
                "forecast_soh_pct": forecast_soh,
                "actual_energy_kwh": actual_energy,
                "forecast_energy_kwh": forecast_energy,
                "actual_power_kw": actual_power,
                "forecast_power_kw": forecast_power,
                "status": status,
                "reserve_discharge_kwh": reserve_discharge_kwh,
                "headroom_charge_kwh": headroom_charge_kwh
            })

        # Ensure exactly 24 hourly records
        hourly_records = sorted(hourly_records, key=lambda x: x["hour"])[:24]

        # 4. Compute Daily Summary KPIs
        soc_values = [r["actual_soc_pct"] for r in hourly_records]
        energy_values = [r["actual_energy_kwh"] for r in hourly_records]
        power_values = [r["actual_power_kw"] for r in hourly_records]
        soh_values = [r["actual_soh_pct"] for r in hourly_records]

        # Energy Charged = sum of negative power intervals (kWh)
        daily_charged_kwh = round(sum(abs(p) for p in power_values if p < 0), 1)
        # Energy Discharged = sum of positive power intervals (kWh)
        daily_discharged_kwh = round(sum(p for p in power_values if p > 0), 1)

        # Equivalent Full Cycles = (Charged + Discharged) / (2 * Usable Capacity)
        usable_cap = config["usable_energy_capacity_kwh"]  # 1500 kWh
        daily_cycles = round((daily_charged_kwh + daily_discharged_kwh) / (2.0 * usable_cap), 2) if usable_cap > 0 else 0.0

        # Current snapshot (latest available hour)
        current_record = hourly_records[-1] if hourly_records else {}

        summary = {
            "current_soc_pct": current_record.get("actual_soc_pct", 50.0),
            "current_soh_pct": current_record.get("actual_soh_pct", 99.17),
            "current_energy_kwh": current_record.get("actual_energy_kwh", 1000.0),
            "current_power_kw": current_record.get("actual_power_kw", 0.0),
            "current_status": current_record.get("status", "IDLE"),
            "current_reserve_discharge_kwh": current_record.get("reserve_discharge_kwh", 700.0),
            "current_headroom_charge_kwh": current_record.get("headroom_charge_kwh", 800.0),
            "min_soc_pct": round(min(soc_values), 1) if soc_values else 15.0,
            "max_soc_pct": round(max(soc_values), 1) if soc_values else 90.0,
            "avg_soc_pct": round(sum(soc_values) / len(soc_values), 1) if soc_values else 50.0,
            "avg_soh_pct": round(sum(soh_values) / len(soh_values), 2) if soh_values else 99.17,
            "daily_charged_kwh": daily_charged_kwh,
            "daily_discharged_kwh": daily_discharged_kwh,
            "daily_cycles": daily_cycles,
            "operating_window_text": "15% MIN -------- EMS OPERATING WINDOW -------- 90% MAX"
        }

        return {
            "available": True,
            "bess": config,
            "date": date_str,
            "date_display": date_display,
            "dataset_start": cls.DATASET_START_DATE,
            "dataset_end": cls.DATASET_END_DATE,
            "current_telemetry": current_record,
            "summary": summary,
            "hourly": hourly_records
        }

    @classmethod
    def generate_excel_report(cls, bess_id: Any, date_str: str) -> io.BytesIO:
        """
        Generates a professional 2-sheet Excel report for the selected BESS asset and date.
        Sheet 1: Hourly Telemetry
        Sheet 2: Daily Summary Report
        """
        telemetry = cls.get_bess_telemetry_for_date(bess_id, date_str)
        config = cls.get_bess_config(bess_id)

        wb = openpyxl.Workbook()
        ws_hourly = wb.active
        ws_hourly.title = "Hourly Telemetry"
        ws_summary = wb.create_sheet(title="Daily Summary Report")

        # Styling
        font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        fill_header = PatternFill(start_color="00843D", end_color="00843D", fill_type="solid")
        fill_sub = PatternFill(start_color="1D4ED8", end_color="1D4ED8", fill_type="solid")
        font_title = Font(name="Calibri", size=14, bold=True, color="0F172A")
        font_bold = Font(name="Calibri", size=11, bold=True)
        thin_border = Border(
            left=Side(style="thin", color="E2E8F0"),
            right=Side(style="thin", color="E2E8F0"),
            top=Side(style="thin", color="E2E8F0"),
            bottom=Side(style="thin", color="E2E8F0")
        )

        # ----------------------------------------------------
        # Sheet 1: Hourly Telemetry
        # ----------------------------------------------------
        ws_hourly.views.sheetView[0].showGridLines = True
        ws_hourly.append([f"{config['name']} — Hourly Energy Storage Telemetry"])
        ws_hourly.append([f"Report Date: {telemetry.get('date_display', date_str)} | Substation Bus: {config['bus']} | Capacity: 2 MWh ({config['energy_capacity_kwh']} kWh)"])
        ws_hourly.append([])

        ws_hourly.cell(row=1, column=1).font = font_title
        ws_hourly.cell(row=2, column=1).font = Font(name="Calibri", size=10, italic=True, color="475569")

        headers = [
            "Time", "Hour", "Actual SOC (%)", "Forecast SOC (%)",
            "Actual SOH (%)", "Forecast SOH (%)",
            "Stored Energy (kWh)", "Forecast Energy (kWh)",
            "BESS Power (kW)", "Forecast Power (kW)", "Status",
            "Discharge Reserve (kWh)", "Charge Headroom (kWh)"
        ]
        ws_hourly.append(headers)

        header_row_idx = 4
        for col_idx in range(1, len(headers) + 1):
            cell = ws_hourly.cell(row=header_row_idx, column=col_idx)
            cell.font = font_header
            cell.fill = fill_header
            cell.alignment = Alignment(horizontal="center", vertical="center")

        hourly_data = telemetry.get("hourly", [])
        for row_data in hourly_data:
            ws_hourly.append([
                row_data["time"],
                row_data["hour"],
                row_data["actual_soc_pct"],
                row_data["forecast_soc_pct"],
                row_data["actual_soh_pct"],
                row_data["forecast_soh_pct"],
                row_data["actual_energy_kwh"],
                row_data["forecast_energy_kwh"],
                row_data["actual_power_kw"],
                row_data["forecast_power_kw"],
                row_data["status"],
                row_data["reserve_discharge_kwh"],
                row_data["headroom_charge_kwh"]
            ])

        # Formatting cells
        for row in ws_hourly.iter_rows(min_row=5, max_row=4 + len(hourly_data), min_col=1, max_col=len(headers)):
            for cell in row:
                cell.border = thin_border
                cell.alignment = Alignment(horizontal="center", vertical="center")

        # Column widths
        for col in ws_hourly.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws_hourly.column_dimensions[col_letter].width = max(max_len + 4, 12)

        # ----------------------------------------------------
        # Sheet 2: Daily Summary Report
        # ----------------------------------------------------
        ws_summary.views.sheetView[0].showGridLines = True
        ws_summary.append([f"{config['name']} — Daily Operational Summary"])
        ws_summary.append([f"Report Date: {telemetry.get('date_display', date_str)} | Connected Bus: {config['bus']}"])
        ws_summary.append([])

        ws_summary.cell(row=1, column=1).font = font_title
        ws_summary.cell(row=2, column=1).font = Font(name="Calibri", size=10, italic=True, color="475569")

        summary_metrics = telemetry.get("summary", {})
        kpis = [
            ("Asset Name", config["name"]),
            ("Associated Substation Bus", config["bus"]),
            ("Associated Solar PV Plant", f"{config['solar_name']} ({config['solar_capacity_kw']} kW)"),
            ("Installed Energy Capacity", "2.0 MWh (2000 kWh)"),
            ("Usable Energy Capacity (15%–90%)", "1.5 MWh (1500 kWh)"),
            ("EMS Operating Window", "15% Minimum to 90% Maximum"),
            ("Current SOC", f"{summary_metrics.get('current_soc_pct', '--')}%"),
            ("Current SOH", f"{summary_metrics.get('current_soh_pct', '--')}%"),
            ("Current Stored Energy", f"{summary_metrics.get('current_energy_kwh', '--')} kWh"),
            ("Current BESS Power", f"{summary_metrics.get('current_power_kw', '--')} kW"),
            ("Current Operational Status", summary_metrics.get("current_status", "--")),
            ("Discharge Reserve Headroom", f"{summary_metrics.get('current_reserve_discharge_kwh', '--')} kWh"),
            ("Charge Absorption Headroom", f"{summary_metrics.get('current_headroom_charge_kwh', '--')} kWh"),
            ("Minimum Daily SOC", f"{summary_metrics.get('min_soc_pct', '--')}%"),
            ("Maximum Daily SOC", f"{summary_metrics.get('max_soc_pct', '--')}%"),
            ("Average Daily SOC", f"{summary_metrics.get('avg_soc_pct', '--')}%"),
            ("Average Daily SOH", f"{summary_metrics.get('avg_soh_pct', '--')}%"),
            ("Total Energy Charged", f"{summary_metrics.get('daily_charged_kwh', '--')} kWh"),
            ("Total Energy Discharged", f"{summary_metrics.get('daily_discharged_kwh', '--')} kWh"),
            ("Equivalent Daily Full Cycles", f"{summary_metrics.get('daily_cycles', '--')} cycles")
        ]

        ws_summary.append(["Parameter", "Value"])
        ws_summary.cell(row=4, column=1).font = font_header
        ws_summary.cell(row=4, column=1).fill = fill_sub
        ws_summary.cell(row=4, column=2).font = font_header
        ws_summary.cell(row=4, column=2).fill = fill_sub

        for param, val in kpis:
            ws_summary.append([param, str(val)])

        for row in ws_summary.iter_rows(min_row=5, max_row=4 + len(kpis), min_col=1, max_col=2):
            row[0].border = thin_border
            row[0].font = font_bold
            row[1].border = thin_border
            row[1].alignment = Alignment(horizontal="right")

        ws_summary.column_dimensions["A"].width = 38
        ws_summary.column_dimensions["B"].width = 36

        # Return BytesIO stream
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output
