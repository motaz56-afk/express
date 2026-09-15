from flask import Flask
from config import Config


def create_app():
    """Crée et configure l'application Flask."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Enregistrement des routes (blueprints)
    from app.routes.main import main_bp
    app.register_blueprint(main_bp)

    return app