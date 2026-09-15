from datetime import datetime, timedelta
import secrets
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request)
from flask_login import login_required, current_user
from app import db
from app.models import Restaurant, ActivationCode
from app.utils import log_action

abonnement_bp = Blueprint("abonnement", __name__)

# ⚠️ CHANGE CE MOT DE PASSE !
MOT_DE_PASSE_ADMIN = "EXPRESS-ADMIN-2026"


# =========================================================
# Page abonnement (client)
# =========================================================
@abonnement_bp.route("/abonnement", methods=["GET", "POST"])
@login_required
def index():
    resto = current_user.restaurant
    if not resto:
        flash("Erreur : restaurant introuvable.", "danger")
        return redirect("/login")

    if request.method == "POST":
        code = (request.form.get("code") or "").strip().upper().replace(" ", "")
        if not code:
            flash("Veuillez entrer un code.", "warning")
        else:
            ac = ActivationCode.query.filter_by(code=code).first()
            if not ac:
                flash("Code invalide. Vérifiez et réessayez.", "danger")
                log_action("ACTIVATION_FAIL", cible=code, details="Code inconnu")
            else:
                ok, msg = ac.est_utilisable()
                if not ok:
                    flash(msg, "danger")
                    log_action("ACTIVATION_FAIL", cible=code, details=msg)
                else:
                    ac.utilise = True
                    ac.utilise_le = datetime.utcnow()
                    ac.restaurant_id = resto.id
                    resto.prolonger_abonnement(ac.mois)
                    db.session.commit()
                    log_action("ACTIVATION_OK", cible=code,
                               details=f"+{ac.mois} mois pour resto#{resto.id}")
                    flash(f"✅ Abonnement prolongé de {ac.mois} mois ! "
                          f"Expiration : {resto.date_expiration.strftime('%d/%m/%Y')}",
                          "success")
                    return redirect("/gerant/")

    return render_template("abonnement.html", resto=resto)


# =========================================================
# Contact (sans login, page publique)
# =========================================================
@abonnement_bp.route("/contact")
def contact():
    return render_template("contact.html")


# =========================================================
# ADMIN SECRET — Génération de codes
# =========================================================
@abonnement_bp.route("/admin-codes", methods=["GET", "POST"])
def admin_codes():
    """Page secrète pour générer des codes après paiement du client."""
    # Auth par mot de passe simple
    if request.method == "POST" and "mot_de_passe" in request.form:
        if request.form.get("mot_de_passe") == MOT_DE_PASSE_ADMIN:
            session["admin_codes_ok"] = True
            return redirect("/admin-codes")
        flash("Mot de passe incorrect.", "danger")

    if not session.get("admin_codes_ok"):
        return render_template("admin_codes_login.html")

    # Création de code
    if request.method == "POST" and "creer" in request.form:
        mois = request.form.get("mois", "8")
        try:
            mois = int(mois)
        except ValueError:
            mois = 8
        payeur = (request.form.get("payeur") or "").strip()[:120]
        notes = (request.form.get("notes") or "").strip()[:255]

        code = "EXP-" + secrets.token_hex(4).upper()
        ac = ActivationCode(
            code=code, mois=mois, payeur=payeur, notes=notes,
            expire_le=datetime.utcnow() + timedelta(days=30),
        )
        db.session.add(ac)
        db.session.commit()
        flash(f"Code créé : {code} ({mois} mois)", "success")
        return redirect("/admin-codes")

    codes = ActivationCode.query.order_by(ActivationCode.cree_le.desc()).limit(200).all()
    return render_template("admin_codes.html", codes=codes)


@abonnement_bp.route("/admin-codes/logout", methods=["POST"])
def admin_codes_logout():
    session.pop("admin_codes_ok", None)
    flash("Déconnecté.", "info")
    return redirect("/admin-codes")
