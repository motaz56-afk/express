import re
import secrets
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request)
from flask_login import login_user, current_user
from app import db
from app.models import Restaurant, User, Category, Table
from app.utils import log_action

signup_bp = Blueprint("signup", __name__)

_signups_par_ip = {}
MAX_SIGNUPS_PAR_HEURE = 3


# =========================================================
# Données par défaut
# =========================================================
CATEGORIES_DEFAUT = [
    ("Cafés", "☕", 1),
    ("Boissons", "🥤", 2),
    ("Sandwichs", "🥪", 3),
    ("Pizzas", "🍕", 4),
    ("Plats", "🍔", 5),
    ("Desserts", "🍰", 6),
]

NB_TABLES_DEFAUT = 10
PLACES_PAR_TABLE_DEFAUT = 4


def _rate_limit_ok(ip):
    maintenant = datetime.utcnow()
    seuil = maintenant - timedelta(hours=1)
    _signups_par_ip[ip] = [t for t in _signups_par_ip.get(ip, []) if t > seuil]
    if len(_signups_par_ip[ip]) >= MAX_SIGNUPS_PAR_HEURE:
        return False
    _signups_par_ip[ip].append(maintenant)
    return True


def _valider_champs(data):
    erreurs = []
    resto_nom = (data.get("resto_nom") or "").strip()
    prenom = (data.get("prenom") or "").strip()
    nom = (data.get("nom") or "").strip()
    username = (data.get("username") or "").strip().lower()
    password = data.get("password") or ""
    password2 = data.get("password2") or ""

    if len(resto_nom) < 2:
        erreurs.append("Le nom du restaurant doit faire au moins 2 caractères.")
    if len(resto_nom) > 120:
        erreurs.append("Nom de restaurant trop long.")
    if not prenom or not nom:
        erreurs.append("Votre prénom et votre nom sont obligatoires.")
    if len(username) < 3:
        erreurs.append("Le nom d'utilisateur doit faire au moins 3 caractères.")
    if not re.match(r"^[a-z0-9_.-]+$", username):
        erreurs.append("Le nom d'utilisateur ne peut contenir que des lettres minuscules, chiffres, points, tirets et underscores.")
    if len(password) < 6:
        erreurs.append("Le mot de passe doit faire au moins 6 caractères.")
    if password != password2:
        erreurs.append("Les mots de passe ne correspondent pas.")
    if User.query.filter_by(username=username).first():
        erreurs.append(f"Le nom d'utilisateur « {username} » est déjà utilisé.")
    return erreurs


def _creer_donnees_defaut(resto):
    """Crée les catégories et tables par défaut pour un nouveau restaurant."""
    # Catégories
    for nom, emoji, ordre in CATEGORIES_DEFAUT:
        db.session.add(Category(
            nom=nom, emoji=emoji, ordre=ordre,
            restaurant_id=resto.id,
        ))

    # Tables 01 à 10
    for i in range(1, NB_TABLES_DEFAUT + 1):
        db.session.add(Table(
            numero=f"{i:02d}",
            places=PLACES_PAR_TABLE_DEFAUT,
            token=secrets.token_urlsafe(16),
            restaurant_id=resto.id,
        ))


@signup_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect("/")

    if request.method == "POST":
        ip = request.remote_addr or "?"
        if not _rate_limit_ok(ip):
            flash("Trop de créations de compte récentes. Réessayez dans une heure.", "warning")
            return render_template("signup.html", form=request.form)

        erreurs = _valider_champs(request.form)
        if erreurs:
            for e in erreurs:
                flash(e, "danger")
            return render_template("signup.html", form=request.form)

        # 1) Restaurant + abonnement 8 mois
        resto = Restaurant(
            nom=request.form.get("resto_nom").strip(),
            adresse=(request.form.get("resto_adresse") or "").strip(),
            telephone=(request.form.get("resto_tel") or "").strip(),
        )
        resto.initialiser_abonnement(mois=8)
        db.session.add(resto)
        db.session.flush()

        # 2) Gérant
        username = request.form.get("username").strip().lower()
        gerant = User(
            prenom=request.form.get("prenom").strip(),
            nom=request.form.get("nom").strip(),
            username=username, role="GERANT",
            restaurant_id=resto.id,
        )
        gerant.set_password(request.form.get("password"))
        db.session.add(gerant)

        # 3) Catégories + 10 tables par défaut
        _creer_donnees_defaut(resto)

        db.session.commit()

        login_user(gerant)
        log_action("SIGNUP", cible=f"resto#{resto.id}",
                   details=f"{resto.nom} — {username}")

        flash(f"Bienvenue {gerant.prenom} ! Votre restaurant « {resto.nom} » "
              f"est prêt. {NB_TABLES_DEFAUT} tables et "
              f"{len(CATEGORIES_DEFAUT)} catégories ont été créées. "
              f"Vous bénéficiez de 8 mois d'accès offerts.", "success")
        return redirect("/gerant/tables")

    return render_template("signup.html", form={})
