import os


class Config:
    """Configuration principale de l'application."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-moi-en-production-12345")

    _db_url = os.environ.get("DATABASE_URL", "sqlite:///moncafe.db")
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ==================== POOL DE CONNEXIONS OPTIMISÉ ====================
    # Réutilise les connexions DB au lieu d'en ouvrir une nouvelle à chaque requête
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 2,          # Max 2 connexions en pool (0.1 CPU)
        "max_overflow": 3,       # +3 connexions temporaires si besoin
        "pool_pre_ping": True,   # Vérifie que la connexion est vivante
        "pool_recycle": 300,     # Renouvelle après 5 min (évite timeouts)
        "pool_timeout": 30,      # Attend max 30s une connexion libre
    }

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

    # ==================== CACHE EN MÉMOIRE ====================
    # Durées de cache (en secondes)
    CACHE_DUREE_LANDING = 300     # 5 min
    CACHE_DUREE_DASHBOARD = 30    # 30 s
    CACHE_DUREE_MENU = 60         # 1 min
