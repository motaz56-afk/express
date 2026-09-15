from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import (Table, Order, OrderStatus, Payment, PaymentMethod)
from app.utils import role_required, log_action

caissier_bp = Blueprint("caissier", __name__)


def _debut_jour():
    auj = date.today()
    return datetime(auj.year, auj.month, auj.day)


def _stats_jour(rid):
    debut = _debut_jour()
    paiements = Payment.query.filter(Payment.restaurant_id == rid,
                                     Payment.cree_le >= debut).all()
    return paiements, sum(p.montant for p in paiements), len(paiements)


def _a_encaisser(rid):
    tables = Table.query.filter_by(restaurant_id=rid).order_by(Table.numero).all()
    resultat = {}
    for t in tables:
        servies = Order.query.filter_by(restaurant_id=rid, table_id=t.id,
                                        statut=OrderStatus.SERVED).all()
        if servies:
            resultat[t.id] = {"nb": len(servies),
                              "total": sum(o.total for o in servies)}
    return tables, resultat


@caissier_bp.route("/")
@login_required
@role_required("CAISSIER", "GERANT")
def index():
    rid = current_user.restaurant_id
    tables, a_encaisser = _a_encaisser(rid)
    _, ca_jour, nb_paiements = _stats_jour(rid)
    return render_template("caissier/index.html",
                           tables=tables, a_encaisser=a_encaisser,
                           ca_jour=ca_jour, nb_paiements=nb_paiements)


@caissier_bp.route("/partial/zone")
@login_required
@role_required("CAISSIER", "GERANT")
def partial_zone():
    rid = current_user.restaurant_id
    tables, a_encaisser = _a_encaisser(rid)
    _, ca_jour, nb_paiements = _stats_jour(rid)
    return render_template("caissier/_zone.html",
                           tables=tables, a_encaisser=a_encaisser,
                           ca_jour=ca_jour, nb_paiements=nb_paiements)


@caissier_bp.route("/table/<int:table_id>")
@login_required
@role_required("CAISSIER", "GERANT")
def table_detail(table_id):
    rid = current_user.restaurant_id
    table = Table.query.filter_by(id=table_id, restaurant_id=rid).first_or_404()
    servies = Order.query.filter_by(restaurant_id=rid, table_id=table.id,
                                    statut=OrderStatus.SERVED)\
                         .order_by(Order.cree_le.asc()).all()
    total = sum(o.total for o in servies)
    return render_template("caissier/table_detail.html",
                           table=table, commandes=servies, total=total,
                           PaymentMethod=PaymentMethod)


@caissier_bp.route("/table/<int:table_id>/partial/commandes")
@login_required
@role_required("CAISSIER", "GERANT")
def partial_commandes(table_id):
    rid = current_user.restaurant_id
    table = Table.query.filter_by(id=table_id, restaurant_id=rid).first_or_404()
    servies = Order.query.filter_by(restaurant_id=rid, table_id=table.id,
                                    statut=OrderStatus.SERVED)\
                         .order_by(Order.cree_le.asc()).all()
    total = sum(o.total for o in servies)
    return render_template("caissier/_commandes_liste.html",
                           table=table, commandes=servies, total=total)


@caissier_bp.route("/table/<int:table_id>/encaisser", methods=["POST"])
@login_required
@role_required("CAISSIER", "GERANT")
def encaisser(table_id):
    rid = current_user.restaurant_id
    table = Table.query.filter_by(id=table_id, restaurant_id=rid).first_or_404()
    methode = request.form.get("methode", PaymentMethod.ESPECES)
    if methode not in PaymentMethod.ALL:
        methode = PaymentMethod.ESPECES
    notes = request.form.get("notes", "").strip()[:255]

    servies = Order.query.filter_by(restaurant_id=rid, table_id=table.id,
                                    statut=OrderStatus.SERVED).all()
    if not servies:
        flash("Aucune commande à encaisser sur cette table.", "warning")
        return redirect(url_for("caissier.index"))
    total = sum(o.total for o in servies)
    paiement = Payment(montant=total, methode=methode, notes=notes,
                       restaurant_id=rid, table_id=table.id,
                       user_id=current_user.id)
    db.session.add(paiement)
    db.session.flush()
    for o in servies:
        o.statut = OrderStatus.PAID
        o.paye_le = datetime.utcnow()
        o.payment_id = paiement.id
    db.session.commit()
    log_action("PAYMENT", cible=f"payment#{paiement.id}",
               details=f"Table {table.numero} | {total:.3f} DT | {methode}")
    from app.sockets import notifier_paiement
    notifier_paiement(paiement)
    flash(f"Table {table.numero} encaissée : {total:.3f} DT ({methode}).",
          "success")
    return redirect(url_for("caissier.index"))


@caissier_bp.route("/historique")
@login_required
@role_required("CAISSIER", "GERANT")
def historique():
    rid = current_user.restaurant_id
    paiements, total, _ = _stats_jour(rid)
    return render_template("caissier/historique.html",
                           paiements=paiements, total=total,
                           PaymentMethod=PaymentMethod)


@caissier_bp.route("/historique/partial/liste")
@login_required
@role_required("CAISSIER", "GERANT")
def partial_historique():
    rid = current_user.restaurant_id
    paiements, total, _ = _stats_jour(rid)
    return render_template("caissier/_historique_liste.html",
                           paiements=paiements, total=total,
                           PaymentMethod=PaymentMethod)
