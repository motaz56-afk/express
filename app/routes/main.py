from flask import Blueprint, redirect
from flask_login import current_user

main_bp = Blueprint("main", __name__)


def _destination_par_role(role):
    return {
        "GERANT":   "/gerant/",
        "SERVEUR":  "/serveur/",
        "CUISINE":  "/cuisine/",
        "CAISSIER": "/caissier/",
    }.get(role, "/login")


@main_bp.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(_destination_par_role(current_user.role))
    return redirect("/login")


@main_bp.route("/dashboard")
def dashboard():
    """Conservé pour compatibilité — redirige."""
    if current_user.is_authenticated:
        return redirect(_destination_par_role(current_user.role))
    return redirect("/login")


@main_bp.route("/test")
def test():
    return "Route de test — la structure fonctionne !"
