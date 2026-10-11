import os


class Config:
    """Configuration principale de l'application."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-moi-en-production-12345")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///moncafe.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:5000")
    ADSENSE_CLIENT_ID = os.environ.get("ADSENSE_CLIENT_ID", "")
    ADSENSE_ENABLED = os.environ.get("ADSENSE_ENABLED", "0") == "1"
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    from datetime import timedelta
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=60)
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024