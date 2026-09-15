from datetime import datetime, date, timedelta
from flask import (Blueprint, render_template, redirect, url_for, flash,
                   request, send_file, current_app)
from flask_login import login_required, current_user
from app import db
from app.models import (Category, Product, Table, User, Order, OrderStatus,
                        Payment, PaymentMethod, AuditLog)
from app.utils import role_required, log_action, abonnement_required
import secrets, io, qrcode

gerant_bp = Blueprint("gerant", __name__)

# Données par défaut (partagées avec signup)
CATEGORIES_DEFAUT = [
    ("Cafés", "☕", 1), ("Boissons", "🥤", 2), ("Sandwichs", "🥪", 3),
    ("Pizzas", "🍕", 4), ("Plats", "🍔", 5), ("Desserts", "🍰", 6),
]


def _debut_jour():
    auj = date.today()
    return datetime(auj.year, auj.month, auj.day)


def _stats_dashboard(rid):
    debut = _debut_jour()
    paiements = Payment.query.filter(Payment.restaurant_id == rid,
                                     Payment.cree_le >= debut).all()
    ca_jour = sum(p.montant for p in paiements)
    nb_paiements = len(paiements)
    ticket_moyen = (ca_jour / nb_paiements) if nb_paiements else 0.0
    par_methode = {m: 0.0 for m in PaymentMethod.ALL}
    for p in paiements:
        par_methode[p.methode] = par_methode.get(p.methode, 0.0) + p.montant
    commandes_actives = Order.query.filter(
        Order.restaurant_id == rid, Order.statut.in_(OrderStatus.ACTIFS)).count()
    commandes_servies = Order.query.filter_by(
        restaurant_id=rid, statut=OrderStatus.SERVED).count()
    return dict(
        ca_jour=ca_jour, nb_paiements=nb_paiements, ticket_moyen=ticket_moyen,
        par_methode=par_methode, commandes_actives=commandes_actives,
        commandes_servies=commandes_servies,
        nb_produits=Product.query.filter_by(restaurant_id=rid).count(),
        nb_categories=Category.query.filter_by(restaurant_id=rid).count(),
        nb_tables=Table.query.filter_by(restaurant_id=rid).count(),
        nb_users=User.query.filter_by(restaurant_id=rid).count(),
    )


@gerant_bp.route("/")
@login_required
@role_required("GERANT")
@abonnement_required
def dashboard():
    stats = _stats_dashboard(current_user.restaurant_id)
    return render_template("gerant/dashboard.html",
                           PaymentMethod=PaymentMethod, **stats)


@gerant_bp.route("/partial/dashboard")
@login_required
@role_required("GERANT")
def partial_dashboard():
    stats = _stats_dashboard(current_user.restaurant_id)
    return render_template("gerant/_dashboard_zone.html",
                           PaymentMethod=PaymentMethod, **stats)


# =========================================================
# CATÉGORIES
# =========================================================
@gerant_bp.route("/categories")
@login_required
@role_required("GERANT")
@abonnement_required
def categories():
    rid = current_user.restaurant_id
    liste = Category.query.filter_by(restaurant_id=rid).order_by(Category.ordre).all()
    return render_template("gerant/categories.html", categories=liste)


@gerant_bp.route("/categories/nouvelle", methods=["POST"])
@login_required
@role_required("GERANT")
@abonnement_required
def categorie_nouvelle():
    nom = request.form.get("nom", "").strip()
    emoji = request.form.get("emoji", "").strip()
    if not nom:
        flash("Le nom est obligatoire.", "danger")
        return redirect(url_for("gerant.categories"))
    max_ordre = db.session.query(db.func.max(Category.ordre)).filter_by(
        restaurant_id=current_user.restaurant_id).scalar() or 0
    c = Category(nom=nom, emoji=emoji, ordre=max_ordre + 1,
                 restaurant_id=current_user.restaurant_id)
    db.session.add(c); db.session.commit()
    log_action("CATEGORY_CREATE", cible=f"category#{c.id}", details=nom)
    flash(f"Catégorie « {nom} » créée.", "success")
    return redirect(url_for("gerant.categories"))


@gerant_bp.route("/categories/defaut", methods=["POST"])
@login_required
@role_required("GERANT")
@abonnement_required
def categories_defaut():
    """Crée les 6 catégories par défaut (pour les restaurants déjà existants)."""
    rid = current_user.restaurant_id
    existantes = {c.nom.lower() for c in Category.query.filter_by(restaurant_id=rid).all()}
    creees = 0
    for nom, emoji, ordre in CATEGORIES_DEFAUT:
        if nom.lower() not in existantes:
            db.session.add(Category(nom=nom, emoji=emoji, ordre=ordre,
                                    restaurant_id=rid))
            creees += 1
    db.session.commit()
    log_action("CATEGORY_DEFAULT", details=f"{creees} catégories créées")
    flash(f"✅ {creees} catégorie(s) par défaut créée(s).", "success")
    return redirect(url_for("gerant.categories"))


@gerant_bp.route("/categories/<int:cid>/modifier", methods=["POST"])
@login_required
@role_required("GERANT")
@abonnement_required
def categorie_modifier(cid):
    c = Category.query.filter_by(id=cid, restaurant_id=current_user.restaurant_id).first_or_404()
    ancien = c.nom
    c.nom = request.form.get("nom", c.nom).strip()
    c.emoji = request.form.get("emoji", c.emoji).strip()
    db.session.commit()
    log_action("CATEGORY_UPDATE", cible=f"category#{c.id}", details=f"{ancien} → {c.nom}")
    flash("Catégorie modifiée.", "success")
    return redirect(url_for("gerant.categories"))


@gerant_bp.route("/categories/<int:cid>/supprimer", methods=["POST"])
@login_required
@role_required("GERANT")
@abonnement_required
def categorie_supprimer(cid):
    c = Category.query.filter_by(id=cid, restaurant_id=current_user.restaurant_id).first_or_404()
    if c.products:
        flash("Impossible : des produits utilisent cette catégorie.", "warning")
        return redirect(url_for("gerant.categories"))
    nom = c.nom
    db.session.delete(c); db.session.commit()
    log_action("CATEGORY_DELETE", cible=f"category#{cid}", details=nom)
    flash("Catégorie supprimée.", "success")
    return redirect(url_for("gerant.categories"))


# =========================================================
# PRODUITS
# =========================================================
@gerant_bp.route("/produits")
@login_required
@role_required("GERANT")
@abonnement_required
def produits():
    rid = current_user.restaurant_id
    liste = (Product.query.filter_by(restaurant_id=rid).join(Category)
             .order_by(Category.ordre, Product.nom).all())
    cats = Category.query.filter_by(restaurant_id=rid).order_by(Category.ordre).all()
    return render_template("gerant/produits.html", produits=liste, categories=cats)


@gerant_bp.route("/produits/nouveau", methods=["POST"])
@login_required
@role_required("GERANT")
@abonnement_required
def produit_nouveau():
    nom = request.form.get("nom", "").strip()
    prix = request.form.get("prix", "0").strip()
    description = request.form.get("description", "").strip()
    category_id = request.form.get("category_id")
    try:
        prix = float(prix.replace(",", "."))
    except ValueError:
        flash("Prix invalide.", "danger")
        return redirect(url_for("gerant.produits"))
    if not nom or not category_id:
        flash("Nom et catégorie sont obligatoires.", "danger")
        return redirect(url_for("gerant.produits"))
    p = Product(nom=nom, prix=prix, description=description,
                category_id=int(category_id),
                restaurant_id=current_user.restaurant_id)
    db.session.add(p); db.session.commit()
    log_action("PRODUCT_CREATE", cible=f"product#{p.id}",
               details=f"{nom} — {prix:.3f} DT")
    flash(f"Produit « {nom} » créé.", "success")
    return redirect(url_for("gerant.produits"))


@gerant_bp.route("/produits/<int:pid>/modifier", methods=["POST"])
@login_required
@role_required("GERANT")
@abonnement_required
def produit_modifier(pid):
    p = Product.query.filter_by(id=pid, restaurant_id=current_user.restaurant_id).first_or_404()
    ancien_prix = p.prix
    p.nom = request.form.get("nom", p.nom).strip()
    p.description = request.form.get("description", p.description or "").strip()
    try:
        p.prix = float(request.form.get("prix", p.prix).replace(",", "."))
    except ValueError:
        flash("Prix invalide.", "danger")
        return redirect(url_for("gerant.produits"))
    p.category_id = int(request.form.get("category_id", p.category_id))
    p.disponible = "disponible" in request.form
    db.session.commit()
    log_action("PRODUCT_UPDATE", cible=f"product#{p.id}",
               details=f"Prix {ancien_prix:.3f} → {p.prix:.3f}")
    flash("Produit modifié.", "success")
    return redirect(url_for("gerant.produits"))


@gerant_bp.route("/produits/<int:pid>/supprimer", methods=["POST"])
@login_required
@role_required("GERANT")
@abonnement_required
def produit_supprimer(pid):
    p = Product.query.filter_by(id=pid, restaurant_id=current_user.restaurant_id).first_or_404()
    nom = p.nom
    db.session.delete(p); db.session.commit()
    log_action("PRODUCT_DELETE", cible=f"product#{pid}", details=nom)
    flash("Produit supprimé.", "success")
    return redirect(url_for("gerant.produits"))


# =========================================================
# TABLES
# =========================================================
@gerant_bp.route("/tables")
@login_required
@role_required("GERANT")
@abonnement_required
def tables():
    rid = current_user.restaurant_id
    liste = Table.query.filter_by(restaurant_id=rid).order_by(Table.numero).all()
    return render_template("gerant/tables.html", tables=liste)


@gerant_bp.route("/tables/nouvelle", methods=["POST"])
@login_required
@role_required("GERANT")
@abonnement_required
def table_nouvelle():
    numero = request.form.get("numero", "").strip()
    places = request.form.get("places", "4").strip()
    if not numero:
        flash("Le numéro est obligatoire.", "danger")
        return redirect(url_for("gerant.tables"))
    try:
        places = int(places)
    except ValueError:
        places = 4
    t = Table(numero=numero, places=places, token=secrets.token_urlsafe(16),
              restaurant_id=current_user.restaurant_id)
    db.session.add(t); db.session.commit()
    log_action("TABLE_CREATE", cible=f"table#{t.id}", details=f"N°{numero}")
    flash(f"Table « {numero} » créée.", "success")
    return redirect(url_for("gerant.tables"))


@gerant_bp.route("/tables/defaut", methods=["POST"])
@login_required
@role_required("GERANT")
@abonnement_required
def tables_defaut():
    """Crée 10 tables par défaut (01 à 10) pour les restaurants qui n'en ont pas."""
    rid = current_user.restaurant_id
    existantes = {t.numero for t in Table.query.filter_by(restaurant_id=rid).all()}
    creees = 0
    for i in range(1, 11):
        num = f"{i:02d}"
        if num not in existantes:
            db.session.add(Table(
                numero=num, places=4,
                token=secrets.token_urlsafe(16),
                restaurant_id=rid,
            ))
            creees += 1
    db.session.commit()
    log_action("TABLE_DEFAULT", details=f"{creees} tables créées")
    flash(f"✅ {creees} table(s) par défaut créée(s).", "success")
    return redirect(url_for("gerant.tables"))


@gerant_bp.route("/tables/<int:tid>/modifier", methods=["POST"])
@login_required
@role_required("GERANT")
@abonnement_required
def table_modifier(tid):
    t = Table.query.filter_by(id=tid, restaurant_id=current_user.restaurant_id).first_or_404()
    t.numero = request.form.get("numero", t.numero).strip()
    try:
        t.places = int(request.form.get("places", t.places))
    except ValueError:
        pass
    t.qr_actif = "qr_actif" in request.form
    db.session.commit()
    log_action("TABLE_UPDATE", cible=f"table#{t.id}", details=f"N°{t.numero}")
    flash("Table modifiée.", "success")
    return redirect(url_for("gerant.tables"))


@gerant_bp.route("/tables/<int:tid>/supprimer", methods=["POST"])
@login_required
@role_required("GERANT")
@abonnement_required
def table_supprimer(tid):
    t = Table.query.filter_by(id=tid, restaurant_id=current_user.restaurant_id).first_or_404()
    num = t.numero
    db.session.delete(t); db.session.commit()
    log_action("TABLE_DELETE", cible=f"table#{tid}", details=f"N°{num}")
    flash("Table supprimée.", "success")
    return redirect(url_for("gerant.tables"))


@gerant_bp.route("/tables/<int:tid>/regenerer-token", methods=["POST"])
@login_required
@role_required("GERANT")
@abonnement_required
def table_regenerer_token(tid):
    t = Table.query.filter_by(id=tid, restaurant_id=current_user.restaurant_id).first_or_404()
    t.token = secrets.token_urlsafe(16)
    db.session.commit()
    log_action("QR_REGEN", cible=f"table#{t.id}", details=f"N°{t.numero}")
    flash(f"Nouveau QR généré pour la table {t.numero}.", "success")
    return redirect(url_for("gerant.table_qr", tid=t.id))


@gerant_bp.route("/tables/<int:tid>/qr")
@login_required
@role_required("GERANT")
@abonnement_required
def table_qr(tid):
    t = Table.query.filter_by(id=tid, restaurant_id=current_user.restaurant_id).first_or_404()
    base = current_app.config["BASE_URL"].rstrip("/")
    url = f"{base}/order/{t.restaurant_id}/{t.token}"
    return render_template("gerant/table_qr.html", table=t, url=url)


@gerant_bp.route("/tables/<int:tid>/qr.png")
@login_required
@role_required("GERANT")
@abonnement_required
def table_qr_png(tid):
    t = Table.query.filter_by(id=tid, restaurant_id=current_user.restaurant_id).first_or_404()
    base = current_app.config["BASE_URL"].rstrip("/")
    url = f"{base}/order/{t.restaurant_id}/{t.token}"
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png",
                     download_name=f"table_{t.numero}_qr.png")


# =========================================================
# UTILISATEURS
# =========================================================
@gerant_bp.route("/utilisateurs")
@login_required
@role_required("GERANT")
@abonnement_required
def utilisateurs():
    rid = current_user.restaurant_id
    liste = User.query.filter_by(restaurant_id=rid).order_by(User.role, User.nom).all()
    return render_template("gerant/utilisateurs.html", utilisateurs=liste)


@gerant_bp.route("/utilisateurs/nouveau", methods=["POST"])
@login_required
@role_required("GERANT")
@abonnement_required
def utilisateur_nouveau():
    prenom = request.form.get("prenom", "").strip()
    nom = request.form.get("nom", "").strip()
    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "")
    role = request.form.get("role", "SERVEUR")
    if not (prenom and nom and username and password):
        flash("Tous les champs sont obligatoires.", "danger")
        return redirect(url_for("gerant.utilisateurs"))
    if User.query.filter_by(username=username).first():
        flash("Ce nom d'utilisateur existe déjà.", "danger")
        return redirect(url_for("gerant.utilisateurs"))
    u = User(prenom=prenom, nom=nom, username=username, role=role,
             restaurant_id=current_user.restaurant_id)
    u.set_password(password)
    db.session.add(u); db.session.commit()
    log_action("USER_CREATE", cible=f"user#{u.id}", details=f"{username} ({role})")
    flash(f"Utilisateur « {username} » créé.", "success")
    return redirect(url_for("gerant.utilisateurs"))


@gerant_bp.route("/utilisateurs/<int:uid>/modifier", methods=["POST"])
@login_required
@role_required("GERANT")
@abonnement_required
def utilisateur_modifier(uid):
    u = User.query.filter_by(id=uid, restaurant_id=current_user.restaurant_id).first_or_404()
    u.prenom = request.form.get("prenom", u.prenom).strip()
    u.nom = request.form.get("nom", u.nom).strip()
    u.role = request.form.get("role", u.role)
    u.actif = "actif" in request.form
    nouveau_mdp = request.form.get("password", "").strip()
    change_mdp = bool(nouveau_mdp)
    if change_mdp:
        u.set_password(nouveau_mdp)
    db.session.commit()
    log_action("USER_UPDATE", cible=f"user#{u.id}",
               details=f"{u.username} | rôle={u.role} | actif={u.actif} | mdp={change_mdp}")
    flash("Utilisateur modifié.", "success")
    return redirect(url_for("gerant.utilisateurs"))


# =========================================================
# AUDIT
# =========================================================
def _logs_filtres(rid):
    action_f = request.args.get("action", "").strip()
    user_f = request.args.get("user", "").strip()
    jours_f = request.args.get("jours", "7").strip()
    query = AuditLog.query.filter_by(restaurant_id=rid)
    if action_f:
        query = query.filter(AuditLog.action == action_f)
    if user_f:
        query = query.filter(AuditLog.username == user_f)
    try:
        jours = int(jours_f)
        debut = datetime.utcnow() - timedelta(days=jours)
        query = query.filter(AuditLog.cree_le >= debut)
    except ValueError:
        pass
    logs = query.order_by(AuditLog.cree_le.desc()).limit(500).all()
    return logs, action_f, user_f, jours_f


@gerant_bp.route("/audit")
@login_required
@role_required("GERANT")
@abonnement_required
def audit():
    rid = current_user.restaurant_id
    logs, action_f, user_f, jours_f = _logs_filtres(rid)
    actions_dispo = [r[0] for r in db.session.query(AuditLog.action)
                     .filter_by(restaurant_id=rid).distinct().all()]
    users_dispo = [r[0] for r in db.session.query(AuditLog.username)
                   .filter_by(restaurant_id=rid).distinct().all() if r[0]]
    return render_template("gerant/audit.html",
                           logs=logs, actions=actions_dispo, users=users_dispo,
                           action_f=action_f, user_f=user_f, jours_f=jours_f)


@gerant_bp.route("/partial/audit")
@login_required
@role_required("GERANT")
def partial_audit():
    rid = current_user.restaurant_id
    logs, _, _, _ = _logs_filtres(rid)
    return render_template("gerant/_audit_liste.html", logs=logs)
