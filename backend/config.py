import os
from datetime import timedelta
from dotenv import load_dotenv

# Load .env from project root
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(base_dir, ".env"))

class Config:
    """Base application configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "smartfeeder-ems-default-dev-secret-key-32chars")
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@123")
    PORT = int(os.environ.get("PORT", 8000))

    # Session security settings
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "False").lower() in ("true", "1", "t")
    SESSION_COOKIE_NAME = "smartfeeder_session"
