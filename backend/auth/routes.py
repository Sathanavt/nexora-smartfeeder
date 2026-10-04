from flask import Blueprint, request, jsonify
from backend.auth.auth_service import AuthService
from backend.auth.middleware import login_required

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Real backend authentication endpoint.
    Expects JSON: { "username": "...", "password": "..." }
    """
    try:
        data = request.get_json(silent=True) or {}
        username = data.get("username", "")
        password = data.get("password", "")

        # Strict validation
        if not username or not str(username).strip():
            return jsonify({
                "success": False,
                "error": "Username is required."
            }), 400

        if not password or not str(password).strip():
            return jsonify({
                "success": False,
                "error": "Password is required."
            }), 400

        # Backend credential verification
        user, error = AuthService.authenticate(str(username), str(password))
        if error or not user:
            return jsonify({
                "success": False,
                "error": error or "Invalid username or password."
            }), 401

        # Establish secure HTTP-only session
        AuthService.create_session(user)

        return jsonify({
            "success": True,
            "message": "Authentication successful.",
            "user": user.to_safe_dict(),
            "redirect": "/"
        }), 200

    except Exception:
        # Prevent any internal details or stack traces from leaking
        return jsonify({
            "success": False,
            "error": "An authentication error occurred. Please try again."
        }), 500


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """
    Backend logout endpoint.
    Invalidates session and clears cookies.
    """
    try:
        AuthService.terminate_session()
        return jsonify({
            "success": True,
            "message": "Logged out successfully."
        }), 200
    except Exception:
        return jsonify({
            "success": False,
            "error": "Unable to complete logout."
        }), 500


@auth_bp.route("/me", methods=["GET"])
@login_required
def get_current_user():
    """Returns currently authenticated user information."""
    user_info = AuthService.get_current_user_info()
    return jsonify({
        "success": True,
        "user": user_info
    }), 200
