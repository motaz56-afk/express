from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, session)
from flask_login import login_required, current_user
from app import db
from app.models import (Table, Category, Product, Order, OrderItem,
                        OrderStatus, OrderSource)
from app.utils import role_required, log_action

serveur_bp = Blueprint("serveur", __name__)


def _cle_panier(table_id):
    return f"panier_table_{table_id}"


def get_panier(table_id):
    return session.get(_cle_panier(table_id), [])


def set_panier(table_id, panier):
    session[_cle_panier(table_id)] = panier
    session.modified = True


def vider_panier(table_id):
    session.pop(_cle_panier(table_id), None)


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


def _contexte_tables(rid):
    liste = Table.query.filter_by(restaurant_id=rid).order_by(Table.numero).all()
    actifs = {}
    for t in liste:
        nb = Order.query.filter(Order.table_id == t.id,
                                Order.statut.in_(OrderStatus.ACTIFS)).count()
        if nb:
            actifs[t.id] = nb
    return dict(tables=liste, paniers=actifs)


def _contexte_commandes(rid):
    actives = (Order.query
               .filter(Order.restaurant_id == rid,
                       Order.statut.notin_([OrderStatus.PAID,
                                            OrderStatus.CANCELLED,
                                            OrderStatus.REJECTED]))
               .order_by(Order.cree_le.asc()).all())
    return dict(commandes=actives, OrderStatus=OrderStatus)


# =========================================================
# TABLES
# =========================================================
@serveur_bp.route("/")
@login_required
@role_required("SERVEUR", "GERANT")
def tables():
    rid = current_user.restaurant_id
    return render_template("serveur/tables.html", **_contexte_tables(rid))


@serveur_bp.route("/partial/tables")
@login_required
@role_required("SERVEUR", "GERANT")
def partial_tables():
    rid = current_user.restaurant_id
    return render_template("serveur/_tables_grille.html", **_contexte_tables(rid))


# =========================================================
# DÉTAIL TABLE
# =========================================================
@serveur_bp.route("/table/<int:table_id>")
@login_required
@role_required("SERVEUR", "GERANT")
def table_detail(table_id):
    rid = current_user.restaurant_id
    table = Table.query.filter_by(id=table_id, restaurant_id=rid).first_or_404()

    panier_affiche, total = _construire_panier_affiche(get_panier(table.id))
    commandes = (Order.query
                 .filter(Order.table_id == table.id,
                         Order.statut.notin_([OrderStatus.PAID,
                                              OrderStatus.CANCELLED,
                                              OrderStatus.REJECTED]))
                 .order_by(Order.cree_le.desc()).all())

    return render_template("serveur/table_detail.html",
                           table=table, panier=panier_affiche, total=total,
                           commandes=commandes, OrderStatus=OrderStatus)


@serveur_bp.route("/table/<int:table_id>/partial/panier")
@login_required
@role_required("SERVEUR", "GERANT")
def partial_panier(table_id):
    rid = current_user.restaurant_id
    table = Table.query.filter_by(id=table_id, restaurant_id=rid).first_or_404()
    panier_affiche, total = _construire_panier_affiche(get_panier(table.id))
    return render_template("serveur/_panier.html",
                           table=table, panier=panier_affiche, total=total)


@serveur_bp.route("/table/<int:table_id>/partial/commandes")
@login_required
@role_required("SERVEUR", "GERANT")
def partial_commandes_table(table_id):
    rid = current_user.restaurant_id
    table = Table.query.filter_by(id=table_id, restaurant_id=rid).first_or_404()
    commandes = (Order.query
                 .filter(Order.table_id == table.id,
                         Order.statut.notin_([OrderStatus.PAID,
                                              OrderStatus.CANCELLED,
                                              OrderStatus.REJECTED]))
                 .order_by(Order.cree_le.desc()).all())
    return render_template("serveur/_commandes_table.html",
                           table=table, commandes=commandes,
                           OrderStatus=OrderStatus)


@serveur_bp.route("/table/<int:table_id>/ajouter", methods=["POST"])
@login_required
@role_required("SERVEUR", "GERANT")
def ajouter(table_id):
    rid = current_user.restaurant_id
    table = Table.query.filter_by(id=table_id, restaurant_id=rid).first_or_404()
    product_id = request.form.get("product_id", type=int)
    produit = Product.query.filter_by(id=product_id, restaurant_id=rid,
                                      disponible=True).first()
    if not produit:
        flash("Produit introuvable ou indisponible.", "warning")
        return redirect(url_for("serveur.table_detail", table_id=table.id))
    panier = get_panier(table.id)
    for item in panier:
        if item["product_id"] == produit.id:
            item["quantite"] += 1
            break
    else:
        panier.append({"product_id": produit.id, "quantite": 1})
    set_panier(table.id, panier)
    return redirect(url_for("serveur.table_detail", table_id=table.id))


@serveur_bp.route("/table/<int:table_id>/retirer", methods=["POST"])
@login_required
@role_required("SERVEUR", "GERANT")
def retirer(table_id):
    rid = current_user.restaurant_id
    table = Table.query.filter_by(id=table_id, restaurant_id=rid).first_or_404()
    product_id = request.form.get("product_id", type=int)
    panier = get_panier(table.id)
    nouveau = []
    for item in panier:
        if item["product_id"] == product_id:
            item["quantite"] -= 1
            if item["quantite"] > 0:
                nouveau.append(item)
        else:
            nouveau.append(item)
    set_panier(table.id, nouveau)
    return redirect(url_for("serveur.table_detail", table_id=table.id))


@serveur_bp.route("/table/<int:table_id>/vider", methods=["POST"])
@login_required
@role_required("SERVEUR", "GERANT")
def vider(table_id):
    rid = current_user.restaurant_id
    table = Table.query.filter_by(id=table_id, restaurant_id=rid).first_or_404()
    vider_panier(table.id)
    flash("Panier vidé.", "info")
    return redirect(url_for("serveur.table_detail", table_id=table.id))


@serveur_bp.route("/table/<int:table_id>/valider", methods=["POST"])
@login_required
@role_required("SERVEUR", "GERANT")
def valider(table_id):
    rid = current_user.restaurant_id
    table = Table.query.filter_by(id=table_id, restaurant_id=rid).first_or_404()
    panier_affiche, total = _construire_panier_affiche(get_panier(table.id))
    if not panier_affiche:
        flash("Le panier est vide.", "warning")
        return redirect(url_for("serveur.table_detail", table_id=table.id))

    commande = Order(restaurant_id=rid, table_id=table.id,
                     serveur_id=current_user.id,
                     statut=OrderStatus.PENDING, source=OrderSource.WAITER,
                     total=0.0)
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
    vider_panier(table.id)
    log_action("ORDER_CREATE", cible=f"order#{commande.id}",
               details=f"Table {table.numero} | {total:.3f} DT")
    from app.sockets import notifier_nouvelle_commande
    notifier_nouvelle_commande(commande)
    flash(f"Commande #{commande.id} envoyée en cuisine ({total:.3f} DT).",
          "success")
    return redirect(url_for("serveur.commandes"))


# =========================================================
# SUIVI COMMANDES
# =========================================================
@serveur_bp.route("/commandes")
@login_required
@role_required("SERVEUR", "GERANT")
def commandes():
    rid = current_user.restaurant_id
    return render_template("serveur/commandes.html", **_contexte_commandes(rid))


@serveur_bp.route("/partial/commandes")
@login_required
@role_required("SERVEUR", "GERANT")
def partial_commandes():
    rid = current_user.restaurant_id
    return render_template("serveur/_commandes_liste.html",
                           **_contexte_commandes(rid))


@serveur_bp.route("/commandes/<int:order_id>/servie", methods=["POST"])
@login_required
@role_required("SERVEUR", "GERANT")
def marquer_servie(order_id):
    rid = current_user.restaurant_id
    commande = Order.query.filter_by(id=order_id, restaurant_id=rid).first_or_404()
    if commande.statut != OrderStatus.READY:
        flash("Seule une commande PRÊTE peut être marquée servie.", "warning")
        return redirect(url_for("serveur.commandes"))
    commande.statut = OrderStatus.SERVED
    db.session.commit()
    log_action("ORDER_SERVED", cible=f"order#{commande.id}",
               details=f"Table {commande.table.numero}")
    from app.sockets import notifier_commande_servie
    notifier_commande_servie(commande)
    flash(f"Commande #{commande.id} marquée comme servie.", "success")
    return redirect(url_for("serveur.commandes"))
