from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User
from app.utils import log_action

auth_bp = Blueprint("auth", __name__)


def _destination_par_role(role):
    return {
        "GERANT":   "/gerant/",
        "SERVEUR":  "/serveur/",
        "CUISINE":  "/cuisine/",
        "CAISSIER": "/caissier/",
    }.get(role, "/")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(_destination_par_role(current_user.role))

    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            log_action("LOGIN_FAIL", cible=f"username={username}")
            flash("Nom d'utilisateur ou mot de passe incorrect.", "danger")
            return redirect(url_for("auth.login"))

        if not user.actif:
            log_action("LOGIN_FAIL", cible=f"username={username}",
                       details="Compte désactivé")
            flash("Ce compte est désactivé. Contactez le gérant.", "warning")
            return redirect(url_for("auth.login"))

        # 🔐 Vérification de l'abonnement
        resto = user.restaurant
        if resto and resto.est_expire():
            log_action("LOGIN_FAIL", cible=f"username={username}",
                       details="Abonnement expiré")
            # On connecte quand même pour permettre l'accès à /abonnement
            login_user(user)
            flash("⚠️ Votre abonnement EXPRESS a expiré. "
                  "Pour réactiver votre accès, contactez le 52 305 518 "
                  "(paiement 80 DT / 8 mois).", "warning")
            return redirect("/abonnement")

        login_user(user)
        log_action("LOGIN_OK", cible=f"user#{user.id}")
        flash(f"Bienvenue {user.prenom} !", "success")

        # Alerte abonnement bientôt expiré
        if resto and resto.jours_restants() <= 15 and resto.statut_abonnement() == "BIENTOT_EXPIRE":
            flash(f"⏰ Votre abonnement expire dans {resto.jours_restants()} jours. "
                  f"Contactez le 52 305 518 pour le renouveler.", "warning")

        next_page = request.args.get("next")
        if next_page and next_page.startswith("/"):
            return redirect(next_page)
        return redirect(_destination_par_role(user.role))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    log_action("LOGOUT", cible=f"user#{current_user.id}")
    logout_user()
    flash("Vous êtes déconnecté.", "info")
    return redirect("/")
