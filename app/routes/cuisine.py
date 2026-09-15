from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Order, OrderStatus
from app.utils import role_required, log_action

cuisine_bp = Blueprint("cuisine", __name__)


def _charger_commande(order_id):
    rid = current_user.restaurant_id
    return Order.query.filter_by(id=order_id, restaurant_id=rid).first_or_404()


def _liste_par_statut(rid, statut):
    return (Order.query
            .filter(Order.restaurant_id == rid, Order.statut == statut)
            .order_by(Order.cree_le.asc()).all())


def _contexte_cuisine(rid):
    return dict(
        a_confirmer=_liste_par_statut(rid, OrderStatus.PENDING_CONFIRMATION),
        nouvelles=_liste_par_statut(rid, OrderStatus.PENDING),
        en_cours=_liste_par_statut(rid, OrderStatus.PREPARING),
        pretes=_liste_par_statut(rid, OrderStatus.READY),
        OrderStatus=OrderStatus,
    )


@cuisine_bp.route("/")
@login_required
@role_required("CUISINE", "GERANT")
def index():
    rid = current_user.restaurant_id
    return render_template("cuisine/index.html", **_contexte_cuisine(rid))


@cuisine_bp.route("/partial/zone")
@login_required
@role_required("CUISINE", "GERANT")
def partial_zone():
    rid = current_user.restaurant_id
    return render_template("cuisine/_zone.html", **_contexte_cuisine(rid))


@cuisine_bp.route("/commande/<int:order_id>/accepter", methods=["POST"])
@login_required
@role_required("CUISINE", "GERANT")
def accepter(order_id):
    commande = _charger_commande(order_id)
    if commande.statut != OrderStatus.PENDING_CONFIRMATION:
        flash("Cette commande n'est plus en attente de confirmation.", "warning")
        return redirect(url_for("cuisine.index"))
    commande.statut = OrderStatus.PENDING
    db.session.commit()
    log_action("ORDER_ACCEPT", cible=f"order#{commande.id}",
               details=f"Table {commande.table.numero}")
    from app.sockets import notifier_commande_acceptee
    notifier_commande_acceptee(commande)
    flash(f"Commande #{commande.id} acceptée.", "success")
    return redirect(url_for("cuisine.index"))


@cuisine_bp.route("/commande/<int:order_id>/refuser", methods=["POST"])
@login_required
@role_required("CUISINE", "GERANT")
def refuser(order_id):
    commande = _charger_commande(order_id)
    if commande.statut != OrderStatus.PENDING_CONFIRMATION:
        flash("Cette commande n'est plus en attente de confirmation.", "warning")
        return redirect(url_for("cuisine.index"))
    raison = request.form.get("raison", "").strip()[:255]
    commande.statut = OrderStatus.REJECTED
    commande.refus_raison = raison or "Refusée par le restaurant"
    db.session.commit()
    log_action("ORDER_REJECT", cible=f"order#{commande.id}",
               details=f"Table {commande.table.numero} | {commande.refus_raison}")
    from app.sockets import notifier_commande_refusee
    notifier_commande_refusee(commande)
    flash(f"Commande #{commande.id} refusée.", "info")
    return redirect(url_for("cuisine.index"))


@cuisine_bp.route("/commande/<int:order_id>/commencer", methods=["POST"])
@login_required
@role_required("CUISINE", "GERANT")
def commencer(order_id):
    commande = _charger_commande(order_id)
    if commande.statut != OrderStatus.PENDING:
        flash("Cette commande n'est plus en attente.", "warning")
        return redirect(url_for("cuisine.index"))
    commande.statut = OrderStatus.PREPARING
    db.session.commit()
    log_action("ORDER_PREPARING", cible=f"order#{commande.id}")
    from app.sockets import notifier_commande_en_preparation
    notifier_commande_en_preparation(commande)
    flash(f"Commande #{commande.id} en préparation.", "info")
    return redirect(url_for("cuisine.index"))


@cuisine_bp.route("/commande/<int:order_id>/prete", methods=["POST"])
@login_required
@role_required("CUISINE", "GERANT")
def prete(order_id):
    commande = _charger_commande(order_id)
    if commande.statut != OrderStatus.PREPARING:
        flash("Cette commande n'est pas en préparation.", "warning")
        return redirect(url_for("cuisine.index"))
    commande.statut = OrderStatus.READY
    db.session.commit()
    log_action("ORDER_READY", cible=f"order#{commande.id}")
    from app.sockets import notifier_commande_prete
    notifier_commande_prete(commande)
    flash(f"Commande #{commande.id} prête à servir !", "success")
    return redirect(url_for("cuisine.index"))
