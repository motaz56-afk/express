import os
from datetime import datetime, timedelta
from flask import Flask, session, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_socketio import SocketIO
from config import Config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
socketio = SocketIO()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # ==================== SOCKETIO : async_mode ====================
    # Détection automatique du bon mode :
    #   - "gevent"    → production (Render / Linux où gevent est installé)
    #   - "threading" → développement local (Windows sans gevent)
    #
    # La variable d'environnement SOCKETIO_ASYNC_MODE peut forcer le mode.
    _async_mode = os.environ.get("SOCKETIO_ASYNC_MODE", "").strip().lower()

    if not _async_mode:
        # Aucun mode imposé : on détecte
        try:
            import gevent  # noqa: F401
            _async_mode = "gevent"
        except ImportError:
            _async_mode = "threading"
    else:
        # Mode imposé par l'environnement
        # Si "eventlet" est demandé mais pas dispo, on bascule sur gevent
        if _async_mode == "eventlet":
            try:
                import gevent  # noqa: F401
                _async_mode = "gevent"
            except ImportError:
                _async_mode = "threading"

    print(f"[socketio] async_mode = {_async_mode}")

    socketio.init_app(app, cors_allowed_origins="*", async_mode=_async_mode)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
    login_manager.login_message_category = "warning"

    # ==================== MODELS + USER LOADER ====================
    from app import models  # noqa: F401
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # ==================== SÉCURITÉ : HEADERS HTTP ====================
    @app.after_request
    def ajouter_headers_securite(response):
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if request.path.startswith(("/gerant", "/serveur", "/cuisine", "/caissier")):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        return response

    # ==================== SÉCURITÉ : TIMEOUT SESSION ====================
    @app.before_request
    def rafraichir_session():
        if session.get("_user_id"):
            session.permanent = True
            session.modified = True

    # ==================== BLUEPRINTS ====================
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.signup import signup_bp
    from app.routes.abonnement import abonnement_bp
    from app.routes.gerant import gerant_bp
    from app.routes.serveur import serveur_bp
    from app.routes.cuisine import cuisine_bp
    from app.routes.client_qr import client_qr_bp
    from app.routes.caissier import caissier_bp
    from app.routes.tickets import tickets_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(signup_bp)
    app.register_blueprint(abonnement_bp)
    app.register_blueprint(gerant_bp, url_prefix="/gerant")
    app.register_blueprint(serveur_bp, url_prefix="/serveur")
    app.register_blueprint(cuisine_bp, url_prefix="/cuisine")
    app.register_blueprint(client_qr_bp, url_prefix="/order")
    app.register_blueprint(caissier_bp, url_prefix="/caissier")
    app.register_blueprint(tickets_bp, url_prefix="/ticket")

    # ==================== SOCKET EVENTS ====================
    from app import sockets  # noqa: F401

    # ==================== INIT BASE DE DONNÉES ====================
    with app.app_context():
        from app import models  # noqa

        # 1. Créer les tables manquantes
        try:
            db.create_all()
            print("[init] Tables vérifiées/créées.")
        except Exception as e:
            print(f"[init] Erreur création tables : {e}")

        # 2. Créer le restaurant + admin par défaut si base vide
        try:
            from app.models import Restaurant, User
            if not Restaurant.query.first():
                resto = Restaurant(nom="EXPRESS", adresse="", telephone="")
                resto.initialiser_abonnement(mois=8)
                db.session.add(resto)
                db.session.flush()

                gerant = User(
                    prenom="Gérant",
                    nom="Principal",
                    username="admin",
                    role="GERANT",
                    restaurant_id=resto.id,
                )
                gerant.set_password("admin123")
                db.session.add(gerant)
                db.session.commit()
                print("[init] Restaurant + admin créés (admin / admin123)")
        except Exception as e:
            print(f"[init] Erreur seed : {e}")

    return app