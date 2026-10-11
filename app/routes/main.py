from flask import Blueprint, redirect, render_template, jsonify, current_app
from flask_login import current_user
from app.models import Restaurant, User, Order
from app.cache import cache

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
    """Landing page avec cache 5 min."""
    if current_user.is_authenticated:
        return redirect(_destination_par_role(current_user.role))

    # Cache les stats pendant 5 min (évite 3 COUNT SQL à chaque visite)
    stats = cache.get("landing_stats")
    if stats is None:
        try:
            stats = {
                "nb_restos": Restaurant.query.filter_by(actif=True).count(),
                "nb_users": User.query.count(),
                "nb_commandes": Order.query.count(),
            }
        except Exception as e:
            print(f"[landing] Erreur stats : {e}")
            stats = {"nb_restos": 0, "nb_users": 0, "nb_commandes": 0}

        duree = current_app.config.get("CACHE_DUREE_LANDING", 300)
        cache.set("landing_stats", stats, duree)

    return render_template("landing.html", **stats)


@main_bp.route("/health")
def health():
    """
    Endpoint ultra-léger pour UptimeRobot.
    NE touche PAS à la base de données.
    Réponse instantanée (< 5 ms).
    """
    return jsonify({"status": "ok"}), 200


@main_bp.route("/dashboard")
def dashboard():
    if current_user.is_authenticated:
        return redirect(_destination_par_role(current_user.role))
    return redirect("/login")


@main_bp.route("/test")
def test():
    return "Route de test — la structure fonctionne !"
