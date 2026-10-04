import io
import datetime
import pandas as pd
from typing import Optional, Dict, Any, List
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from backend.data_service import DataService
from backend.forecast_service import ForecastService
from backend.feeder_config import get_feeder_config, FEEDER_REGISTRY

# Keep FEEDER_CONFIG as alias for backwards compatibility
FEEDER_CONFIG = FEEDER_REGISTRY

class FeederService:
    """
    Service for querying and analyzing Feeder demand telemetry.
    Supports dynamic Feeder 1 through 8 analytics, calendar date range rules,
    peak demand duration algorithms, and automated Excel generation.
    """
    DATASET_START_DATE = "2026-08-05"
    DATASET_END_DATE = "2026-09-29"

    @classmethod
    def get_feeder_config(cls, feeder_id: int) -> Dict[str, Any]:
        """Returns metadata for the requested feeder from single source of truth."""
        return get_feeder_config(feeder_id)

    @classmethod
    def format_date_display(cls, date_str: str) -> str:
        """Converts YYYY-MM-DD into DD-Mon-YYYY (e.g. 29-Sep-2026)."""
        try:
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            return dt.strftime("%d-%b-%Y")
        except Exception:
            return date_str

    @classmethod
    def get_feeder_telemetry_for_date(cls, feeder_id: int, date_str: str) -> Dict[str, Any]:
        """
        Retrieves actual and forecasted demand telemetry for a specific feeder on a given date.
        Strictly enforces:
        1. If date < 2026-08-05: return available=False with exact message:
           'Actual feeder data is available from 05-Aug-2026 onwards.'
        2. If date > 2026-09-29: return available=False with 'No actual data available for selected date.'
        3. For valid date in dataset: extracts all hourly records, calculates peak, peak time,
           consecutive duration >= 90% peak, and daily energy.
        """
        config = cls.get_feeder_config(feeder_id)
        date_display = cls.format_date_display(date_str)

        # 1. Date Availability Rule
        if date_str < cls.DATASET_START_DATE:
            return {
                "available": False,
                "feeder": config,
                "date": date_str,
                "date_display": date_display,
                "dataset_start": cls.DATASET_START_DATE,
                "dataset_end": cls.DATASET_END_DATE,
                "message": "DATA NOT AVAILABLE",
                "submessage": f"No actual {config['name']} data is available for {date_display}.",
                "info": "Actual feeder data is available from 05-Aug-2026 onwards."
            }

        df = DataService.load_dataset()
        col = config["column"]

        # Filter rows for date
        # Note: df['Date'] might be stored as datetime or string YYYY-MM-DD
        mask = df["Date"].astype(str).str.startswith(date_str)
        day_df = df[mask]

        if day_df.empty:
            return {
                "available": False,
                "feeder": config,
                "date": date_str,
                "date_display": date_display,
                "dataset_start": cls.DATASET_START_DATE,
                "dataset_end": cls.DATASET_END_DATE,
                "message": "DATA NOT AVAILABLE",
                "submessage": f"No actual {config['name']} data is available for {date_display}.",
                "info": f"Available data spans {cls.format_date_display(cls.DATASET_START_DATE)} to {cls.format_date_display(cls.DATASET_END_DATE)}."
            }

        # 2. Process Hourly Records
        hourly_records: List[Dict[str, Any]] = []
        actual_demands: List[float] = []

        for _, row in day_df.iterrows():
            ts = row.get("Timestamp")
            if hasattr(ts, "strftime"):
                time_label = ts.strftime("%H:%M")
                hour_num = ts.hour
            else:
                # Fallback to Hour_Interval string e.g. "14-15"
                hi = str(row.get("Hour_Interval", "00-01"))
                start_h = hi.split("-")[0].strip()
                time_label = f"{start_h.zfill(2)}:00"
                try:
                    hour_num = int(start_h)
                except ValueError:
                    hour_num = len(hourly_records)

            actual_val = float(row.get(col, 0.0))
            forecast_val = ForecastService.get_hourly_forecast(feeder_id, date_str, hour_num, actual_val)
            error_kw = round(forecast_val - actual_val, 2)
            error_pct = round((abs(error_kw) / actual_val) * 100.0, 2) if actual_val > 0 else 0.0

            actual_demands.append(actual_val)
            hourly_records.append({
                "time": time_label,
                "hour": hour_num,
                "actual_demand_kw": round(actual_val, 2),
                "forecast_demand_kw": forecast_val,
                "error_kw": error_kw,
                "error_pct": error_pct
            })

        # Sort chronologically by hour
        hourly_records.sort(key=lambda r: r["hour"])

        # 3. Peak Demand and Time
        if not hourly_records:
            return {
                "available": False,
                "feeder": config,
                "date": date_str,
                "date_display": date_display,
                "message": "DATA NOT AVAILABLE"
            }

        peak_record = max(hourly_records, key=lambda r: r["actual_demand_kw"])
        peak_demand_kw = peak_record["actual_demand_kw"]
        peak_time = peak_record["time"]

        # 4. Peak Demand Duration Calculation:
        # Consecutive duration where demand >= 90% of the day's peak demand
        peak_threshold_kw = round(peak_demand_kw * 0.90, 2)
        max_duration_hours = 0
        current_streak = 0
        
        for r in hourly_records:
            if r["actual_demand_kw"] >= peak_threshold_kw:
                current_streak += 1
                if current_streak > max_duration_hours:
                    max_duration_hours = current_streak
            else:
                current_streak = 0

        # Guarantee at least 1 hour if peak was non-zero
        if max_duration_hours == 0 and peak_demand_kw > 0:
            max_duration_hours = 1

        duration_text = f"{max_duration_hours} {'hour' if max_duration_hours == 1 else 'hours'}"

        # 5. Daily Energy Calculation:
        # Sum of hourly kW * 1 hour = total kWh for the day
        daily_energy_kwh = round(sum(r["actual_demand_kw"] for r in hourly_records), 1)
        avg_demand_kw = round(sum(r["actual_demand_kw"] for r in hourly_records) / len(hourly_records), 2)

        return {
            "available": True,
            "feeder": config,
            "date": date_str,
            "date_display": date_display,
            "dataset_start": cls.DATASET_START_DATE,
            "dataset_end": cls.DATASET_END_DATE,
            "hourly": hourly_records,
            "summary": {
                "peak_demand_kw": peak_demand_kw,
                "peak_time": peak_time,
                "peak_threshold_kw": peak_threshold_kw,
                "peak_duration_hours": max_duration_hours,
                "peak_duration_text": duration_text,
                "daily_energy_kwh": daily_energy_kwh,
                "avg_demand_kw": avg_demand_kw
            }
        }

    @classmethod
    def generate_excel_report(cls, feeder_id: int, date_str: str) -> io.BytesIO:
        """
        Dynamically generates a professional Excel workbook containing
        Hourly Telemetry and a Daily Summary Report for the selected Feeder and Date.
        """
        telemetry = cls.get_feeder_telemetry_for_date(feeder_id, date_str)
        config = telemetry["feeder"]
        date_display = telemetry.get("date_display", date_str)

        wb = openpyxl.Workbook()
        
        # Styles
        header_fill = PatternFill(start_color="00843D", end_color="00843D", fill_type="solid")
        header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        title_font = Font(name="Arial", size=13, bold=True, color="0F172A")
        sub_font = Font(name="Arial", size=9, italic=True, color="475569")
        bold_font = Font(name="Arial", size=10, bold=True, color="0F172A")
        normal_font = Font(name="Arial", size=10, color="0F172A")
        mono_font = Font(name="Consolas", size=10, color="0F172A")
        
        thin_border = Border(
            left=Side(style='thin', color="E2E8F0"),
            right=Side(style='thin', color="E2E8F0"),
            top=Side(style='thin', color="E2E8F0"),
            bottom=Side(style='thin', color="E2E8F0")
        )
        accent_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

        # -----------------------------------------------------------
        # Sheet 1: Hourly Telemetry
        # -----------------------------------------------------------
        ws_hourly = wb.active
        ws_hourly.title = "Hourly Telemetry"
        ws_hourly.views.sheetView[0].showGridLines = True

        # Header Title
        ws_hourly["A1"] = f"SmartFeeder EMS — {config['name']} Hourly Demand Telemetry"
        ws_hourly["A1"].font = title_font
        ws_hourly["A2"] = f"Report Date: {date_display} | 110/11 kV Substation Feeder Analytics"
        ws_hourly["A2"].font = sub_font

        headers = [
            "Date", "Time", "Feeder ID", "Feeder Name",
            "Actual Demand (kW)", "Forecast Demand (kW)",
            "Forecast Error (kW)", "Forecast Error (%)"
        ]

        row_num = 4
        for col_idx, h in enumerate(headers, 1):
            cell = ws_hourly.cell(row=row_num, column=col_idx, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border

        if telemetry.get("available") and telemetry.get("hourly"):
            for h_record in telemetry["hourly"]:
                row_num += 1
                row_vals = [
                    date_display,
                    h_record["time"],
                    f"ID-{config['source_id']}",
                    config["name"],
                    h_record["actual_demand_kw"],
                    h_record["forecast_demand_kw"],
                    h_record["error_kw"],
                    h_record["error_pct"]
                ]
                for col_idx, val in enumerate(row_vals, 1):
                    c = ws_hourly.cell(row=row_num, column=col_idx, value=val)
                    c.border = thin_border
                    c.font = mono_font if col_idx in [5, 6, 7, 8] else normal_font
                    if col_idx in [5, 6, 7, 8]:
                        c.alignment = Alignment(horizontal="right", vertical="center")
                    else:
                        c.alignment = Alignment(horizontal="center", vertical="center")
        else:
            row_num += 1
            ws_hourly.cell(row=row_num, column=1, value="No actual telemetry available for selected date.")
            ws_hourly.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=len(headers))

        # Auto-fit column widths
        for col in ws_hourly.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws_hourly.column_dimensions[col_letter].width = max(max_len + 3, 14)

        # -----------------------------------------------------------
        # Sheet 2: Daily Summary Report
        # -----------------------------------------------------------
        ws_summary = wb.create_sheet(title="Daily Summary")
        ws_summary.views.sheetView[0].showGridLines = True

        ws_summary["A1"] = f"SmartFeeder EMS — {config['name']} Daily Summary"
        ws_summary["A1"].font = title_font
        ws_summary["A2"] = f"Generated for {date_display} | Powered by Schneider Yuva Yodha EMS"
        ws_summary["A2"].font = sub_font

        summary_data = telemetry.get("summary", {})
        summary_rows = [
            ("Feeder Designation", config["name"]),
            ("Source Identifier", f"ID {config['source_id']}"),
            ("Feeder Classification", config["type"]),
            ("Substation Interconnection", config["bus"]),
            ("Report Date", date_display),
            ("Data Status", "AVAILABLE" if telemetry.get("available") else "UNAVAILABLE"),
            ("Peak Demand (kW)", f"{summary_data.get('peak_demand_kw', '--')} kW"),
            ("Peak Demand Time", summary_data.get("peak_time", "--")),
            ("Peak Demand Duration", summary_data.get("peak_duration_text", "--")),
            ("Peak Duration Threshold (90%)", f"{summary_data.get('peak_threshold_kw', '--')} kW"),
            ("Daily Integrated Energy (kWh)", f"{summary_data.get('daily_energy_kwh', '--')} kWh"),
            ("Daily Average Demand (kW)", f"{summary_data.get('avg_demand_kw', '--')} kW"),
        ]

        row_num = 4
        for label, val in summary_rows:
            c1 = ws_summary.cell(row=row_num, column=1, value=label)
            c2 = ws_summary.cell(row=row_num, column=2, value=val)
            c1.font = bold_font
            c1.fill = accent_fill
            c1.border = thin_border
            c2.font = normal_font
            c2.border = thin_border
            c2.alignment = Alignment(horizontal="left")
            row_num += 1

        ws_summary.column_dimensions["A"].width = 34
        ws_summary.column_dimensions["B"].width = 28

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output
