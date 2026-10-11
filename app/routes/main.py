from flask import Blueprint, redirect, render_template, request
from flask_login import current_user
from app.models import Restaurant, User, Order

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
    """Landing page publique (ou redirection si connecté)."""
    if current_user.is_authenticated:
        return redirect(_destination_par_role(current_user.role))

    # Statistiques publiques (preuve sociale)
    nb_restos = Restaurant.query.filter_by(actif=True).count()
    nb_users = User.query.count()
    nb_commandes = Order.query.count()

    return render_template("landing.html",
                           nb_restos=nb_restos,
                           nb_users=nb_users,
                           nb_commandes=nb_commandes)


@main_bp.route("/dashboard")
def dashboard():
    if current_user.is_authenticated:
        return redirect(_destination_par_role(current_user.role))
    return redirect("/login")


@main_bp.route("/test")
def test():
    return "Route de test — la structure fonctionne !"
