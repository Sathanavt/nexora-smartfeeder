"""
SmartFeeder EMS — Solar Service
Business logic and analytics for Solar-A (495 kW, BUS-1, ID 114) and Solar-B (420 kW, BUS-2, ID 166).
Provides Generation vs Time, Generation vs Temperature, Power Balance & Utilization,
and dynamic multi-sheet Excel reporting.
"""
import io
import datetime
from typing import Dict, Any, List, Optional
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from backend.data_service import DataService
from backend.forecast_service import ForecastService
from backend.solar_config import get_solar_config, SOLAR_REGISTRY

class SolarService:
    """
    Service for querying and analyzing Solar PV telemetry.
    Supports dynamic Solar-A and Solar-B analytics, calendar availability rules,
    solar power balance logic, and automated Excel generation.
    """
    DATASET_START_DATE = "2026-08-05"
    DATASET_END_DATE = "2026-09-29"
    SOLAR_THRESHOLD_KW = 8.0

    @classmethod
    def get_solar_config(cls, solar_id: Any) -> Dict[str, Any]:
        """Returns metadata for the requested solar plant from single source of truth."""
        return get_solar_config(solar_id)

    @classmethod
    def format_date_display(cls, date_str: str) -> str:
        """Converts YYYY-MM-DD into DD-Mon-YYYY (e.g. 29-Sep-2026)."""
        try:
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            return dt.strftime("%d-%b-%Y")
        except Exception:
            return date_str

    @classmethod
    def get_solar_telemetry_for_date(cls, solar_id: Any, date_str: str) -> Dict[str, Any]:
        """
        Retrieves actual, forecasted, temperature-linked, and power balance telemetry
        for a specific solar plant on a given date.
        Strictly enforces:
        1. If date < 2026-08-05: return available=False with exact guidance:
           'Historical solar data is available from 05-Aug-2026.'
        2. If date > 2026-09-29 or not in dataset: return available=False.
        3. For valid date in dataset: extracts all hourly records, calculates peak, daily energy,
           solar utilization, grid export, BESS import, and temperature profiles.
        """
        config = cls.get_solar_config(solar_id)
        date_display = cls.format_date_display(date_str)
        capacity_kw = float(config["capacity_kw"])

        # 1. Date Availability Rule
        if date_str < cls.DATASET_START_DATE:
            return {
                "available": False,
                "solar": config,
                "date": date_str,
                "date_display": date_display,
                "dataset_start": cls.DATASET_START_DATE,
                "dataset_end": cls.DATASET_END_DATE,
                "message": "DATA NOT AVAILABLE",
                "submessage": f"No solar data available for {date_display}.",
                "info": "Historical solar data is available from 05-Aug-2026."
            }

        df = DataService.load_dataset()
        col = config["column"]

        # Filter rows for date
        mask = df["Date"].astype(str).str.startswith(date_str)
        day_df = df[mask]

        if day_df.empty:
            return {
                "available": False,
                "solar": config,
                "date": date_str,
                "date_display": date_display,
                "dataset_start": cls.DATASET_START_DATE,
                "dataset_end": cls.DATASET_END_DATE,
                "message": "DATA NOT AVAILABLE",
                "submessage": f"No solar data available for {date_display}.",
                "info": f"Available data spans {cls.format_date_display(cls.DATASET_START_DATE)} to {cls.format_date_display(cls.DATASET_END_DATE)}."
            }

        # 2. Process Hourly Records
        hourly_records: List[Dict[str, Any]] = []
        feeder_cols = config.get("feeder_columns", [])
        bess_col = config.get("bess_column", "")
        bess_status_col = config.get("bess_status_column", "")

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

            # Actual Solar Generation (clamped strictly: 0 <= actual <= capacity)
            raw_gen = float(row.get(col, 0.0))
            actual_kw = max(0.0, min(capacity_kw, raw_gen))

            # Ambient Temperature (°C)
            temp_c = float(row.get("Temperature_C", 25.0))

            # Feeder Load on this bus (kW)
            feeder_load_kw = sum(float(row.get(fc, 0.0)) for fc in feeder_cols)
            feeder_load_kw = max(0.0, feeder_load_kw)

            # BESS Charging Power (kW)
            bess_status = str(row.get(bess_status_col, "IDLE")).strip().upper()
            raw_bess_power = float(row.get(bess_col, 0.0))
            bess_charge_kw = abs(raw_bess_power) if bess_status == "CHARGING" else 0.0

            # Power Balance & Utilization Logic (Section 19 & 20):
            # Solar Generation -> Feeder Load -> BESS Charging -> Grid Export
            # Total local consumption capacity = feeder_load_kw + bess_charge_kw
            local_capacity_kw = feeder_load_kw + bess_charge_kw
            utilized_kw = min(actual_kw, local_capacity_kw)

            # Surplus solar after feeder load
            surplus_after_feeders = max(0.0, actual_kw - feeder_load_kw)
            # Portion of surplus absorbed by BESS charging
            solar_to_bess_kw = min(surplus_after_feeders, bess_charge_kw)
            # Remaining surplus exported to 110 kV grid
            solar_to_grid_kw = max(0.0, surplus_after_feeders - bess_charge_kw)

            # Forecast generation
            forecast_kw = ForecastService.get_solar_hourly_forecast(
                config["id"], date_str, hour_num, actual_kw, temp_c, capacity_kw
            )
            forecast_utilized_kw = min(forecast_kw, local_capacity_kw)

            # Active / Inactive Status
            solar_status = "ACTIVE" if actual_kw >= cls.SOLAR_THRESHOLD_KW else "INACTIVE"

            # Bus-level Net Grid Import (kW)
            bess_discharge_kw = abs(raw_bess_power) if bess_status == "DISCHARGING" else 0.0
            bus_net_grid_import = max(0.0, feeder_load_kw - actual_kw - bess_discharge_kw + bess_charge_kw)

            hourly_records.append({
                "time": time_label,
                "hour": hour_num,
                "actual_generation_kw": round(actual_kw, 2),
                "forecast_generation_kw": round(forecast_kw, 2),
                "temperature_c": round(temp_c, 1),
                "feeder_demand_kw": round(feeder_load_kw, 2),
                "bess_charge_kw": round(bess_charge_kw, 2),
                "bess_power_kw": round(raw_bess_power, 2),
                "bess_status": bess_status,
                "utilized_kw": round(utilized_kw, 2),
                "forecast_utilized_kw": round(forecast_utilized_kw, 2),
                "grid_import_kw": round(solar_to_grid_kw, 2),  # Export to grid from solar
                "bess_import_kw": round(solar_to_bess_kw, 2),  # Import to BESS from solar
                "bus_grid_import_kw": round(bus_net_grid_import, 2),
                "status": solar_status
            })

        # Sort chronologically by hour
        hourly_records.sort(key=lambda r: r["hour"])

        if not hourly_records:
            return {
                "available": False,
                "solar": config,
                "date": date_str,
                "date_display": date_display,
                "message": "DATA NOT AVAILABLE"
            }

        # 3. Peak Generation & Time
        peak_record = max(hourly_records, key=lambda r: r["actual_generation_kw"])
        peak_generation_kw = peak_record["actual_generation_kw"]
        peak_time = peak_record["time"]

        # 4. Energy Calculations (Daily kWh = Sum of hourly kW * 1 h)
        daily_generation_kwh = round(sum(r["actual_generation_kw"] for r in hourly_records), 1)
        daily_forecast_kwh = round(sum(r["forecast_generation_kw"] for r in hourly_records), 1)
        daily_utilized_kwh = round(sum(r["utilized_kw"] for r in hourly_records), 1)
        
        utilization_rate_pct = (
            round((daily_utilized_kwh / daily_generation_kwh) * 100.0, 1)
            if daily_generation_kwh > 0.0 else 100.0
        )

        # 5. Temperature Summary
        temps = [r["temperature_c"] for r in hourly_records]
        avg_temp_c = round(sum(temps) / len(temps), 1) if temps else 0.0
        max_temp_c = round(max(temps), 1) if temps else 0.0
        min_temp_c = round(min(temps), 1) if temps else 0.0

        # 6. Current / Representative Snapshot for Live Telemetry Strip
        # Use latest hour record or peak daytime record
        last_record = hourly_records[-1]
        # Find latest record that has generation, or the last hour of day
        active_records = [r for r in hourly_records if r["actual_generation_kw"] >= cls.SOLAR_THRESHOLD_KW]
        sample_live = active_records[-1] if active_records else last_record

        current_telemetry = {
            "generation_kw": sample_live["actual_generation_kw"],
            "installed_capacity_kw": capacity_kw,
            "installed_capacity_text": config["installed_capacity_text"],
            "temperature_c": sample_live["temperature_c"],
            "grid_import_kw": sample_live["grid_import_kw"],
            "bess_import_kw": sample_live["bess_import_kw"],
            "status": sample_live["status"]
        }

        return {
            "available": True,
            "solar": config,
            "date": date_str,
            "date_display": date_display,
            "dataset_start": cls.DATASET_START_DATE,
            "dataset_end": cls.DATASET_END_DATE,
            "current_telemetry": current_telemetry,
            "hourly": hourly_records,
            "summary": {
                "peak_generation_kw": peak_generation_kw,
                "peak_time": peak_time,
                "daily_generation_kwh": daily_generation_kwh,
                "daily_forecast_kwh": daily_forecast_kwh,
                "daily_utilized_kwh": daily_utilized_kwh,
                "utilization_rate_pct": utilization_rate_pct,
                "avg_temperature_c": avg_temp_c,
                "max_temperature_c": max_temp_c,
                "min_temperature_c": min_temp_c
            }
        }

    @classmethod
    def generate_excel_report(cls, solar_id: Any, date_str: str) -> io.BytesIO:
        """
        Dynamically generates a professional multi-sheet Excel workbook containing
        Hourly Telemetry and Daily Summary Statistics for the selected Solar Asset and Date.
        Filename: Solar-A_2026-09-29.xlsx or Solar-B_2026-09-29.xlsx
        """
        telemetry = cls.get_solar_telemetry_for_date(solar_id, date_str)
        config = telemetry["solar"]
        date_display = telemetry.get("date_display", date_str)

        wb = openpyxl.Workbook()

        # Styles
        header_fill = PatternFill(start_color="00843D", end_color="00843D", fill_type="solid")
        header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        title_font = Font(name="Arial", size=13, bold=True, color="0F172A")
        sub_font = Font(name="Arial", size=9, italic=True, color="475569")
        bold_font = Font(name="Arial", size=10, bold=True, color="0F172A")
        regular_font = Font(name="Arial", size=10, color="1E293B")
        summary_label_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        
        thin_border = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )

        # -------------------------------------------------------------
        # SHEET 1: Hourly Telemetry
        # -------------------------------------------------------------
        ws1 = wb.active
        ws1.title = "Hourly Telemetry"
        ws1.views.sheetView[0].showGridLines = True

        # Header Title Block
        ws1["A1"] = f"SmartFeeder EMS — {config['name']} Generation Telemetry"
        ws1["A1"].font = title_font
        ws1["A2"] = f"Asset: {config['name']} | Bus: {config['bus']} | Installed Capacity: {config['installed_capacity_text']} | Date: {date_display}"
        ws1["A2"].font = sub_font

        headers = [
            "Date", "Time", "Solar Asset", "Installed Capacity (kW)",
            "Actual Generation (kW)", "Forecast Generation (kW)", "Temperature (°C)",
            "Utilized Solar (kW)", "Export to Grid (kW)", "Import to BESS (kW)", "Solar Status"
        ]

        # Write Header Row
        for col_idx, h_text in enumerate(headers, start=1):
            cell = ws1.cell(row=4, column=col_idx, value=h_text)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = thin_border
        ws1.row_dimensions[4].height = 28

        # Data Rows
        row_idx = 5
        if telemetry.get("available") and "hourly" in telemetry:
            for record in telemetry["hourly"]:
                ws1.cell(row=row_idx, column=1, value=date_display).alignment = Alignment(horizontal="center")
                ws1.cell(row=row_idx, column=2, value=record["time"]).alignment = Alignment(horizontal="center")
                ws1.cell(row=row_idx, column=3, value=config["name"]).alignment = Alignment(horizontal="center")
                ws1.cell(row=row_idx, column=4, value=config["capacity_kw"]).alignment = Alignment(horizontal="right")
                ws1.cell(row=row_idx, column=5, value=record["actual_generation_kw"]).alignment = Alignment(horizontal="right")
                ws1.cell(row=row_idx, column=6, value=record["forecast_generation_kw"]).alignment = Alignment(horizontal="right")
                ws1.cell(row=row_idx, column=7, value=record["temperature_c"]).alignment = Alignment(horizontal="right")
                ws1.cell(row=row_idx, column=8, value=record["utilized_kw"]).alignment = Alignment(horizontal="right")
                ws1.cell(row=row_idx, column=9, value=record["grid_import_kw"]).alignment = Alignment(horizontal="right")
                ws1.cell(row=row_idx, column=10, value=record["bess_import_kw"]).alignment = Alignment(horizontal="right")
                ws1.cell(row=row_idx, column=11, value=record["status"]).alignment = Alignment(horizontal="center")

                for c in range(1, len(headers) + 1):
                    cell = ws1.cell(row=row_idx, column=c)
                    cell.font = regular_font
                    cell.border = thin_border
                ws1.row_dimensions[row_idx].height = 20
                row_idx += 1
        else:
            ws1.cell(row=5, column=1, value="No solar data available for the selected date.").font = regular_font

        # Auto-fit columns
        for col in ws1.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws1.column_dimensions[col_letter].width = max(max_len + 3, 12)

        # -------------------------------------------------------------
        # SHEET 2: Daily Summary Report
        # -------------------------------------------------------------
        ws2 = wb.create_sheet(title="Daily Summary Report")
        ws2.views.sheetView[0].showGridLines = True

        ws2["A1"] = f"SmartFeeder EMS — {config['name']} Daily Summary Analysis"
        ws2["A1"].font = title_font
        ws2["A2"] = f"Generated by Team Nexora • Telemetry Date: {date_display}"
        ws2["A2"].font = sub_font

        summary_metrics = []
        if telemetry.get("available") and "summary" in telemetry:
            summ = telemetry["summary"]
            summary_metrics = [
                ("Solar Asset Name", config["name"]),
                ("Connected 11 kV Bus", config["bus"]),
                ("Installed Solar Capacity", config["installed_capacity_text"]),
                ("Telemetry Data ID", f"ID {config['source_id']}"),
                ("Analysis Date", date_display),
                ("Peak Solar Generation", f"{summ['peak_generation_kw']:.2f} kW"),
                ("Peak Generation Time", summ["peak_time"]),
                ("Total Daily Solar Energy Generated", f"{summ['daily_generation_kwh']:.1f} kWh"),
                ("Forecasted Daily Solar Energy", f"{summ['daily_forecast_kwh']:.1f} kWh"),
                ("Total Daily Solar Energy Utilized", f"{summ['daily_utilized_kwh']:.1f} kWh"),
                ("Solar Energy Utilization Rate", f"{summ['utilization_rate_pct']:.1f} %"),
                ("Average Ambient Temperature", f"{summ['avg_temperature_c']:.1f} °C"),
                ("Maximum Ambient Temperature", f"{summ['max_temperature_c']:.1f} °C"),
                ("Minimum Ambient Temperature", f"{summ['min_temperature_c']:.1f} °C"),
            ]
        else:
            summary_metrics = [
                ("Solar Asset Name", config["name"]),
                ("Connected 11 kV Bus", config["bus"]),
                ("Status", "No historical data available for selected date.")
            ]

        ws2.cell(row=4, column=1, value="Metric Parameter").fill = header_fill
        ws2.cell(row=4, column=1).font = header_font
        ws2.cell(row=4, column=1).border = thin_border

        ws2.cell(row=4, column=2, value="Engineering Telemetry Value").fill = header_fill
        ws2.cell(row=4, column=2).font = header_font
        ws2.cell(row=4, column=2).border = thin_border
        ws2.row_dimensions[4].height = 24

        s_row = 5
        for param, val in summary_metrics:
            c1 = ws2.cell(row=s_row, column=1, value=param)
            c1.font = bold_font
            c1.fill = summary_label_fill
            c1.border = thin_border

            c2 = ws2.cell(row=s_row, column=2, value=val)
            c2.font = regular_font
            c2.border = thin_border

            ws2.row_dimensions[s_row].height = 20
            s_row += 1

        ws2.column_dimensions["A"].width = 38
        ws2.column_dimensions["B"].width = 36

        stream = io.BytesIO()
        wb.save(stream)
        stream.seek(0)
        return stream
