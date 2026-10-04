import os
from flask import Flask, render_template, redirect, url_for
from backend.config import Config
from backend.auth.routes import auth_bp
from backend.dashboard_routes import dashboard_bp
from backend.admin_routes import admin_bp
from backend.auth.middleware import login_required
from backend.auth.auth_service import AuthService

def create_app(config_class=Config):
    """Application factory for SmartFeeder EMS."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    template_dir = os.path.join(base_dir, "frontend", "templates")
    static_dir = os.path.join(base_dir, "frontend", "static")

    app = Flask(
        __name__,
        template_folder=template_dir,
        static_folder=static_dir
    )
    app.config.from_object(config_class)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp)

    @app.route("/home")
    @app.route("/")
    @login_required
    def home_dashboard():
        """
        Home Dashboard route - primary overview and control screen of SmartFeeder EMS.
        Protected by login_required.
        """
        user = AuthService.get_current_user_info()
        return render_template("home.html", user=user)

    @app.route("/login")
    def login_page():
        """Public authentication page."""
        if AuthService.is_authenticated():
            return redirect(url_for("home_dashboard"))
        return render_template("login.html")

    # Global security response headers
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    return app
