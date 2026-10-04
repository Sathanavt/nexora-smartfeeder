from flask import Blueprint, jsonify, render_template, request, send_file
from backend.auth.middleware import login_required
from backend.auth.auth_service import AuthService
from backend.data_service import DataService
from backend.engineering_service import EngineeringService
from backend.feeder_service import FeederService
from backend.solar_service import SolarService
from backend.bess_service import BessService
from backend.ems_service import EmsService

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/api/dashboard/live", methods=["GET"])
@login_required
def get_live_dashboard():
    """
    Returns live Home Dashboard telemetry metrics computed from the master dataset.
    """
    try:
        # Load representative operational record from master Excel dataset
        # Supports query param 'latest_raw=true' for pure last row if requested
        use_raw_last = request.args.get("latest_raw", "false").lower() == "true"
        if use_raw_last:
            record = DataService.get_latest_record()
        else:
            record = DataService.get_representative_operational_record()

        metrics = EngineeringService.evaluate_home_metrics(record)
        return jsonify({
            "success": True,
            "data": metrics
        }), 200

    except FileNotFoundError:
        return jsonify({
            "success": False,
            "error": "Dashboard data is currently unavailable."
        }), 503

    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Unable to load dashboard data."
        }), 500


@dashboard_bp.route("/api/bus/1/live", methods=["GET"])
@login_required
def get_live_bus1():
    """
    Returns live BUS-1 detailed telemetry metrics computed from the master dataset.
    """
    try:
        use_raw_last = request.args.get("latest_raw", "false").lower() == "true"
        if use_raw_last:
            record = DataService.get_latest_record()
        else:
            record = DataService.get_representative_operational_record()

        metrics = EngineeringService.evaluate_bus1_metrics(record)
        return jsonify({
            "success": True,
            "data": metrics
        }), 200

    except FileNotFoundError:
        return jsonify({
            "success": False,
            "error": "BUS-1 telemetry data is currently unavailable."
        }), 503

    except Exception:
        return jsonify({
            "success": False,
            "error": "Unable to load BUS-1 data."
        }), 500


# Page 3: BUS-1 Detailed Dashboard
@dashboard_bp.route("/bus/1")
@login_required
def bus1_page():
    """
    Renders Page 3: BUS-1 Detailed Dashboard.
    """
    user = AuthService.get_current_user_info()
    try:
        record = DataService.get_representative_operational_record()
        metrics = EngineeringService.evaluate_bus1_metrics(record)
    except Exception:
        metrics = None

    return render_template("bus1.html",
                           page_title="BUS-1 Detailed Dashboard",
                           user=user,
                           data=metrics)


# Page 4: BUS-2 Live Telemetry API
@dashboard_bp.route("/api/bus/2/live", methods=["GET"])
@login_required
def api_bus2_live():
    """
    Returns real-time or representative operational metrics for BUS-2 Detailed Dashboard.
    Supports query parameter `latest_raw=true` for raw dataset latest row,
    or defaults to representative high-generation operational record for robust UI presentation.
    """
    try:
        use_raw_last = request.args.get("latest_raw", "false").lower() == "true"
        if use_raw_last:
            record = DataService.get_latest_record()
        else:
            record = DataService.get_representative_operational_record()

        metrics = EngineeringService.evaluate_bus2_metrics(record)
        return jsonify({
            "success": True,
            "data": metrics
        }), 200

    except FileNotFoundError:
        return jsonify({
            "success": False,
            "error": "BUS-2 telemetry data is currently unavailable."
        }), 503

    except Exception:
        return jsonify({
            "success": False,
            "error": "Unable to load BUS-2 data."
        }), 500


# Page 4: BUS-2 Detailed Dashboard
@dashboard_bp.route("/bus/2")
@login_required
def bus2_page():
    """
    Renders Page 4: BUS-2 Detailed Dashboard.
    """
    user = AuthService.get_current_user_info()
    try:
        record = DataService.get_representative_operational_record()
        metrics = EngineeringService.evaluate_bus2_metrics(record)
    except Exception:
        metrics = None

    return render_template("bus2.html",
                           page_title="BUS-2 Detailed Dashboard",
                           user=user,
                           data=metrics)


# Page 5: EMS Detailed Control & Operating Status
@dashboard_bp.route("/ems")
@login_required
def ems_page():
    """
    Renders the EMS Detailed Control & Operating Status page.
    Central supervisory decision-making and dispatch control interface.
    """
    user = AuthService.get_current_user_info()
    use_raw_last = request.args.get("latest_raw", "false").lower() == "true"
    ems_data = EmsService.get_ems_status(use_raw_last=use_raw_last)
    return render_template("ems.html",
                           page_title="SmartFeeder EMS — Supervisory Control & Dispatch",
                           user=user,
                           ems=ems_data)


@dashboard_bp.route("/api/ems/data", methods=["GET"])
@login_required
def api_ems_data():
    """
    Returns live EMS supervisory metrics, control setpoints, power balance,
    and decision engine telemetry.
    Supports query parameter `latest_raw=true` for absolute last row.
    """
    try:
        use_raw_last = request.args.get("latest_raw", "false").lower() == "true"
        data = EmsService.get_ems_status(use_raw_last=use_raw_last)
        return jsonify({
            "success": True,
            "data": data
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Unable to load EMS supervisory telemetry."
        }), 500


# Page: Feeder Detailed Demand Analysis (Master Template for Feeders 1 to 8)
@dashboard_bp.route("/feeder/<int:feeder_id>")
@login_required
def feeder_page(feeder_id):
    """
    Renders the Feeder Detailed Demand Analysis page.
    Master reusable template for Feeder-1 through Feeder-8.
    """
    user = AuthService.get_current_user_info()
    config = FeederService.get_feeder_config(feeder_id)
    default_date = FeederService.DATASET_END_DATE  # Latest available date: 2026-09-29
    
    # Load initial telemetry
    try:
        initial_telemetry = FeederService.get_feeder_telemetry_for_date(feeder_id, default_date)
    except Exception:
        initial_telemetry = None

    return render_template("feeder.html",
                           page_title=f"{config['name']} Demand Analysis | SmartFeeder EMS",
                           user=user,
                           feeder=config,
                           default_date=default_date,
                           telemetry=initial_telemetry)


@dashboard_bp.route("/api/feeder/<int:feeder_id>/data", methods=["GET"])
@login_required
def api_feeder_data(feeder_id):
    """
    Returns actual and forecasted demand telemetry for the selected feeder and date.
    Query parameters:
      - `date`: YYYY-MM-DD (defaults to latest dataset date 2026-09-29)
    """
    try:
        date_str = request.args.get("date", FeederService.DATASET_END_DATE).strip()
        data = FeederService.get_feeder_telemetry_for_date(feeder_id, date_str)
        return jsonify({
            "success": True,
            "data": data
        }), 200
    except Exception:
        return jsonify({
            "success": False,
            "error": "Unable to load feeder telemetry."
        }), 500


@dashboard_bp.route("/api/feeder/<int:feeder_id>/download", methods=["GET"])
@login_required
def api_feeder_download(feeder_id):
    """
    Generates and downloads a dynamic Excel report containing hourly demand
    and daily summary statistics for the selected feeder and date.
    Filename: SmartFeeder_Feeder{id}_{date}.xlsx
    """
    try:
        date_str = request.args.get("date", FeederService.DATASET_END_DATE).strip()
        excel_stream = FeederService.generate_excel_report(feeder_id, date_str)
        filename = f"SmartFeeder_Feeder{feeder_id}_{date_str}.xlsx"
        
        return send_file(
            excel_stream,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception:
        return jsonify({
            "success": False,
            "error": "Failed to generate Excel report."
        }), 500


# Page: Solar PV Generation Detailed Analysis (Master Template for Solar-A and Solar-B)
@dashboard_bp.route("/solar/<solar_id>")
@login_required
def solar_page(solar_id):
    """
    Renders the Solar PV Detailed Generation Analysis page.
    Master reusable template for Solar-A (BUS-1, 495 kW) and Solar-B (BUS-2, 420 kW).
    """
    user = AuthService.get_current_user_info()
    config = SolarService.get_solar_config(solar_id)
    default_date = SolarService.DATASET_END_DATE  # Latest available date: 2026-09-29
    
    try:
        initial_telemetry = SolarService.get_solar_telemetry_for_date(solar_id, default_date)
    except Exception:
        initial_telemetry = None

    return render_template("solar.html",
                           page_title=f"{config['name']} PV Generation Analysis | SmartFeeder EMS",
                           user=user,
                           solar=config,
                           default_date=default_date,
                           telemetry=initial_telemetry)


@dashboard_bp.route("/api/solar/<solar_id>/data", methods=["GET"])
@login_required
def api_solar_data(solar_id):
    """
    Returns actual, forecasted, and power balance solar telemetry for the selected plant and date.
    Query parameters:
      - `date`: YYYY-MM-DD (defaults to latest dataset date 2026-09-29)
    """
    try:
        date_str = request.args.get("date", SolarService.DATASET_END_DATE).strip()
        data = SolarService.get_solar_telemetry_for_date(solar_id, date_str)
        return jsonify({
            "success": True,
            "data": data
        }), 200
    except Exception:
        return jsonify({
            "success": False,
            "error": "Unable to load solar data. Please try again."
        }), 500


@dashboard_bp.route("/api/solar/<solar_id>/download", methods=["GET"])
@login_required
def api_solar_download(solar_id):
    """
    Generates and downloads a multi-sheet Excel report containing hourly generation,
    temperature profiles, utilization, and daily summary statistics.
    Filename: Solar-A_YYYY-MM-DD.xlsx or Solar-B_YYYY-MM-DD.xlsx
    """
    try:
        config = SolarService.get_solar_config(solar_id)
        date_str = request.args.get("date", SolarService.DATASET_END_DATE).strip()
        excel_stream = SolarService.generate_excel_report(solar_id, date_str)
        filename = f"{config['name']}_{date_str}.xlsx"
        
        return send_file(
            excel_stream,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception:
        return jsonify({
            "success": False,
            "error": "Failed to generate Excel report."
        }), 500


# Page: BESS Detailed Energy Storage Analysis (Master Template for BESS-A and BESS-B)
@dashboard_bp.route("/bess/<bess_id>")
@login_required
def bess_page(bess_id):
    """
    Renders the BESS Detailed Energy Storage Analysis page.
    Master reusable template for BESS-A (BUS-1, 2 MWh) and BESS-B (BUS-2, 2 MWh).
    """
    user = AuthService.get_current_user_info()
    config = BessService.get_bess_config(bess_id)
    default_date = BessService.DATASET_END_DATE  # Latest available date: 2026-09-29
    
    try:
        initial_telemetry = BessService.get_bess_telemetry_for_date(bess_id, default_date)
    except Exception:
        initial_telemetry = None

    return render_template("bess.html",
                           page_title=f"{config['name']} Energy Storage Analysis | SmartFeeder EMS",
                           user=user,
                           bess=config,
                           default_date=default_date,
                           telemetry=initial_telemetry)


@dashboard_bp.route("/api/bess/<bess_id>/data", methods=["GET"])
@login_required
def api_bess_data(bess_id):
    """
    Returns actual, forecasted, and power balance BESS telemetry for the selected asset and date.
    Query parameters:
      - `date`: YYYY-MM-DD (defaults to latest dataset date 2026-09-29)
    """
    try:
        date_str = request.args.get("date", BessService.DATASET_END_DATE).strip()
        data = BessService.get_bess_telemetry_for_date(bess_id, date_str)
        return jsonify({
            "success": True,
            "data": data
        }), 200
    except Exception:
        return jsonify({
            "success": False,
            "error": "Unable to load BESS data. Please try again."
        }), 500


@dashboard_bp.route("/api/bess/<bess_id>/download", methods=["GET"])
@login_required
def api_bess_download(bess_id):
    """
    Generates and downloads a multi-sheet Excel report containing hourly telemetry,
    SOC, SOH, stored energy, power profiles, and daily summary statistics.
    Filename: BESS-A_YYYY-MM-DD.xlsx or BESS-B_YYYY-MM-DD.xlsx
    """
    try:
        config = BessService.get_bess_config(bess_id)
        date_str = request.args.get("date", BessService.DATASET_END_DATE).strip()
        excel_stream = BessService.generate_excel_report(bess_id, date_str)
        filename = f"{config['name']}_{date_str}.xlsx"
        
        return send_file(
            excel_stream,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception:
        return jsonify({
            "success": False,
            "error": "Failed to generate BESS Excel report."
        }), 500

