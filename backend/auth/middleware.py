from functools import wraps
from flask import request, redirect, url_for, jsonify
from backend.auth.auth_service import AuthService

def login_required(f):
    """
    Reusable authentication guard for views and endpoints.
    Redirects unauthenticated browser requests to /login.
    Returns 401 JSON for unauthenticated API requests.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not AuthService.is_authenticated() or not AuthService.get_current_user_info():
            # Check if request is expecting JSON or is under /api/
            if request.path.startswith("/api/") or request.is_json or request.accept_mimetypes.best == "application/json":
                return jsonify({
                    "success": False,
                    "error": "Authentication required.",
                    "authenticated": False
                }), 401
            
            # Browser navigation redirect to /login
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    Role-Based Access Control decorator.
    Only allows access to users with role 'ADMIN'.
    Returns 401 if unauthenticated, 403 if authenticated but not an ADMIN.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not AuthService.is_authenticated():
            if request.path.startswith("/api/") or request.is_json or request.accept_mimetypes.best == "application/json":
                return jsonify({
                    "success": False,
                    "error": "Authentication required.",
                    "authenticated": False
                }), 401
            return redirect(url_for("login_page"))

        user_info = AuthService.get_current_user_info()
        if not user_info:
            return redirect(url_for("login_page"))

        role = str(user_info.get("role", "")).upper()
        if role != "ADMIN":
            if request.path.startswith("/api/") or request.is_json or request.accept_mimetypes.best == "application/json":
                return jsonify({
                    "success": False,
                    "error": "Access denied. Administrator privileges required.",
                    "authorized": False
                }), 403
            # Browser navigation redirect to home dashboard
            return redirect(url_for("home_dashboard"))

        return f(*args, **kwargs)
    return decorated_function
