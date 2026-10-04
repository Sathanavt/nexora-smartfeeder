from flask import Blueprint, jsonify, render_template, request, session
from backend.auth.middleware import admin_required
from backend.auth.auth_service import AuthService
from backend.auth.user_model import user_repository

admin_bp = Blueprint("admin", __name__)

@admin_bp.route("/admin", methods=["GET"])
@admin_required
def admin_page():
    """Renders the Admin Control and Credential Management page."""
    user = AuthService.get_current_user_info()
    return render_template("admin.html", user=user)


@admin_bp.route("/api/admin/users", methods=["GET"])
@admin_required
def list_users():
    """Returns list of all registered users without sensitive password hashes."""
    users = user_repository.get_all()
    return jsonify({
        "success": True,
        "users": [u.to_safe_dict() for u in users]
    }), 200


@admin_bp.route("/api/admin/users", methods=["POST"])
@admin_required
def create_user():
    """Creates a new user account."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    confirm_password = data.get("confirm_password", "")
    role = data.get("role", "USER")
    status = data.get("status", "ACTIVE")

    if not username:
        return jsonify({"success": False, "error": "Username is required."}), 400
    if not password:
        return jsonify({"success": False, "error": "Password is required."}), 400
    if password != confirm_password:
        return jsonify({"success": False, "error": "Password confirmation does not match."}), 400

    user, error = user_repository.create_user(username, password, role, status)
    if error:
        return jsonify({"success": False, "error": error}), 400

    return jsonify({
        "success": True,
        "message": "User created successfully.",
        "user": user.to_safe_dict()
    }), 201


@admin_bp.route("/api/admin/users/<user_id>", methods=["PUT"])
@admin_required
def update_user(user_id):
    """Updates user information (username, role, status)."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    role = data.get("role", "USER")
    status = data.get("status", "ACTIVE")

    if not username:
        return jsonify({"success": False, "error": "Username cannot be empty."}), 400

    user, error = user_repository.update_user(user_id, username, role, status)
    if error:
        return jsonify({"success": False, "error": error}), 400

    return jsonify({
        "success": True,
        "message": "User details updated successfully.",
        "user": user.to_safe_dict()
    }), 200


@admin_bp.route("/api/admin/users/<user_id>/status", methods=["PATCH"])
@admin_required
def toggle_user_status(user_id):
    """Enables or disables an account."""
    data = request.get_json(silent=True) or {}
    status = data.get("status", "").upper()
    if status not in ("ACTIVE", "DISABLED"):
        return jsonify({"success": False, "error": "Invalid status value."}), 400

    success, error = user_repository.set_status(user_id, status)
    if not success:
        return jsonify({"success": False, "error": error or "Unable to update status."}), 400

    msg = "Account enabled successfully." if status == "ACTIVE" else "Account disabled successfully."
    return jsonify({"success": True, "message": msg}), 200


@admin_bp.route("/api/admin/users/<user_id>/password", methods=["POST"])
@admin_required
def reset_user_password(user_id):
    """Resets or changes a user's password."""
    data = request.get_json(silent=True) or {}
    new_password = data.get("new_password", "")
    confirm_password = data.get("confirm_password", "")

    if not new_password:
        return jsonify({"success": False, "error": "New password is required."}), 400
    if new_password != confirm_password:
        return jsonify({"success": False, "error": "Password confirmation does not match."}), 400

    success, error = user_repository.reset_password(user_id, new_password)
    if not success:
        return jsonify({"success": False, "error": error or "Unable to reset password."}), 400

    return jsonify({
        "success": True,
        "message": "Password updated successfully."
    }), 200


@admin_bp.route("/api/admin/account/password", methods=["POST"])
@admin_required
def change_admin_password():
    """Changes the current authenticated administrator's password after verifying current credentials."""
    data = request.get_json(silent=True) or {}
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")
    confirm_password = data.get("confirm_password", "")

    if not current_password:
        return jsonify({"success": False, "error": "Current password is required."}), 400
    if not new_password:
        return jsonify({"success": False, "error": "New password is required."}), 400
    if new_password != confirm_password:
        return jsonify({"success": False, "error": "Password confirmation does not match."}), 400

    current_user_id = session.get("user_id")
    admin_user = user_repository.get_by_id(current_user_id)
    if not admin_user:
        return jsonify({"success": False, "error": "User account not found."}), 404

    # Verify current password
    if not admin_user.check_password(current_password):
        return jsonify({"success": False, "error": "Current password is incorrect."}), 400

    success, error = user_repository.reset_password(current_user_id, new_password)
    if not success:
        return jsonify({"success": False, "error": error or "Unable to change password."}), 400

    return jsonify({
        "success": True,
        "message": "Admin password changed successfully."
    }), 200


@admin_bp.route("/api/admin/users/<user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id):
    """Removes a user account with safeguard against deleting the last admin."""
    success, error = user_repository.delete_user(user_id)
    if not success:
        return jsonify({"success": False, "error": error or "Unable to remove user."}), 400

    return jsonify({
        "success": True,
        "message": "User removed successfully."
    }), 200
