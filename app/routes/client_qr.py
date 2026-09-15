from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, session, abort)
from app import db
from app.models import (Restaurant, Table, Category, Product,
                        Order, OrderItem, OrderStatus, OrderSource,
                        AuditLog)
from app.sockets import notifier_nouvelle_commande_client
import secrets

client_qr_bp = Blueprint("client_qr", __name__)


def _get_table_ou_404(restaurant_id, token):
    resto = Restaurant.query.get_or_404(restaurant_id)
    if not resto.actif:
        abort(404)
    table = Table.query.filter_by(restaurant_id=resto.id, token=token).first()
    if not table:
        abort(404)
    if not table.qr_actif:
        abort(403)
    return resto, table


def _cle_panier_client(table_id):
    return f"client_panier_{table_id}"


def get_panier_client(table_id):
    return session.get(_cle_panier_client(table_id), [])


def set_panier_client(table_id, panier):
    session[_cle_panier_client(table_id)] = panier
    session.modified = True


def vider_panier_client(table_id):
    session.pop(_cle_panier_client(table_id), None)


def _session_client(table_id):
    cle = f"client_session_{table_id}"
    sid = session.get(cle)
    if not sid:
        sid = secrets.token_urlsafe(16)
        session[cle] = sid
        session.modified = True
    return sid


def _construire_panier_affiche(panier):
    if not panier:
        return [], 0.0
    ids = [item["product_id"] for item in panier]
    produits = {p.id: p for p in Product.query.filter(Product.id.in_(ids)).all()}
    affiches, total = [], 0.0
    for item in panier:
        p = produits.get(item["product_id"])
        if not p:
            continue
        st = p.prix * item["quantite"]
        total += st
        affiches.append({"product_id": p.id, "nom": p.nom, "prix": p.prix,
                         "quantite": item["quantite"], "sous_total": st})
    return affiches, total


def _log_client(action, restaurant_id, cible=None, details=None):
    """Enregistre un log côté client (sans current_user)."""
    try:
        ip = request.remote_addr
    except RuntimeError:
        ip = None
    log = AuditLog(action=action, cible=cible, details=details, ip=ip,
                   restaurant_id=restaurant_id, user_id=None, username="client_qr")
    db.session.add(log)
    db.session.commit()


@client_qr_bp.route("/<int:restaurant_id>/<token>")
def menu(restaurant_id, token):
    resto, table = _get_table_ou_404(restaurant_id, token)
    categories = Category.query.filter_by(restaurant_id=resto.id)                               .order_by(Category.ordre).all()
    produits = Product.query.filter_by(restaurant_id=resto.id, disponible=True)                            .order_by(Product.nom).all()
    par_cat = {}
    for p in produits:
        par_cat.setdefault(p.category_id, []).append(p)
    panier_affiche, total = _construire_panier_affiche(get_panier_client(table.id))
    return render_template("client/menu.html", resto=resto, table=table,
                           categories=categories, par_cat=par_cat,
                           panier=panier_affiche, total=total)


@client_qr_bp.route("/<int:restaurant_id>/<token>/ajouter", methods=["POST"])
def ajouter(restaurant_id, token):
    resto, table = _get_table_ou_404(restaurant_id, token)
    product_id = request.form.get("product_id", type=int)
    produit = Product.query.filter_by(id=product_id, restaurant_id=resto.id,
                                      disponible=True).first()
    if not produit:
        flash("Produit indisponible.", "warning")
        return redirect(url_for("client_qr.menu",
                                restaurant_id=resto.id, token=table.token))
    panier = get_panier_client(table.id)
    for item in panier:
        if item["product_id"] == produit.id:
            item["quantite"] += 1
            break
    else:
        panier.append({"product_id": produit.id, "quantite": 1})
    set_panier_client(table.id, panier)
    return redirect(url_for("client_qr.menu",
                            restaurant_id=resto.id, token=table.token))


@client_qr_bp.route("/<int:restaurant_id>/<token>/retirer", methods=["POST"])
def retirer(restaurant_id, token):
    resto, table = _get_table_ou_404(restaurant_id, token)
    product_id = request.form.get("product_id", type=int)
    panier = get_panier_client(table.id)
    nouveau = []
    for item in panier:
        if item["product_id"] == product_id:
            item["quantite"] -= 1
            if item["quantite"] > 0:
                nouveau.append(item)
        else:
            nouveau.append(item)
    set_panier_client(table.id, nouveau)
    return redirect(url_for("client_qr.menu",
                            restaurant_id=resto.id, token=table.token))


@client_qr_bp.route("/<int:restaurant_id>/<token>/vider", methods=["POST"])
def vider(restaurant_id, token):
    resto, table = _get_table_ou_404(restaurant_id, token)
    vider_panier_client(table.id)
    return redirect(url_for("client_qr.menu",
                            restaurant_id=resto.id, token=table.token))


@client_qr_bp.route("/<int:restaurant_id>/<token>/confirmer")
def confirmer(restaurant_id, token):
    resto, table = _get_table_ou_404(restaurant_id, token)
    panier_affiche, total = _construire_panier_affiche(get_panier_client(table.id))
    if not panier_affiche:
        flash("Votre panier est vide.", "warning")
        return redirect(url_for("client_qr.menu",
                                restaurant_id=resto.id, token=table.token))
    return render_template("client/confirmer.html",
                           resto=resto, table=table,
                           panier=panier_affiche, total=total)


@client_qr_bp.route("/<int:restaurant_id>/<token>/envoyer", methods=["POST"])
def envoyer(restaurant_id, token):
    resto, table = _get_table_ou_404(restaurant_id, token)
    panier_affiche, total = _construire_panier_affiche(get_panier_client(table.id))
    if not panier_affiche:
        flash("Votre panier est vide.", "warning")
        return redirect(url_for("client_qr.menu",
                                restaurant_id=resto.id, token=table.token))

    sid = _session_client(table.id)
    note = request.form.get("note", "").strip()[:255]

    commande = Order(restaurant_id=resto.id, table_id=table.id, serveur_id=None,
                     statut=OrderStatus.PENDING_CONFIRMATION,
                     source=OrderSource.QR_CODE,
                     total=0.0, note=note, client_session_id=sid)
    db.session.add(commande)
    db.session.flush()
    for item in panier_affiche:
        db.session.add(OrderItem(order_id=commande.id,
                                 product_id=item["product_id"],
                                 nom_produit=item["nom"],
                                 prix_unitaire=item["prix"],
                                 quantite=item["quantite"]))
    db.session.flush()
    commande.recalculer_total()
    db.session.commit()
    vider_panier_client(table.id)

    _log_client("QR_ORDER_CREATE", resto.id,
                cible=f"order#{commande.id}",
                details=f"Table {table.numero} | {total:.3f} DT")

    notifier_nouvelle_commande_client(commande)

    return redirect(url_for("client_qr.suivi",
                            restaurant_id=resto.id, token=table.token,
                            order_id=commande.id))


@client_qr_bp.route("/<int:restaurant_id>/<token>/suivi/<int:order_id>")
def suivi(restaurant_id, token, order_id):
    resto, table = _get_table_ou_404(restaurant_id, token)
    sid = _session_client(table.id)
    commande = Order.query.filter_by(id=order_id, restaurant_id=resto.id,
                                     table_id=table.id,
                                     client_session_id=sid).first_or_404()
    return render_template("client/suivi.html",
                           resto=resto, table=table,
                           commande=commande, OrderStatus=OrderStatus)
