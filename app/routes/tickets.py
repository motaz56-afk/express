from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user
from app.models import Order, OrderStatus, OrderSource
from app.utils import role_required

tickets_bp = Blueprint("tickets", __name__)


@tickets_bp.route("/<int:order_id>")
@login_required
@role_required("CUISINE", "SERVEUR", "CAISSIER", "GERANT")
def imprimer(order_id):
    """Affiche le ticket d'une commande, prêt pour l'impression."""
    rid = current_user.restaurant_id
    commande = Order.query.filter_by(id=order_id, restaurant_id=rid).first_or_404()
    resto = current_user.restaurant

    # Libellés
    source_label = "QR CLIENT" if commande.source == OrderSource.QR_CODE else "SERVEUR"
    serveur_nom = "—"
    if commande.serveur:
        serveur_nom = f"{commande.serveur.prenom} {commande.serveur.nom}"

    return render_template(
        "ticket.html",
        commande=commande,
        resto=resto,
        source_label=source_label,
        serveur_nom=serveur_nom,
        OrderStatus=OrderStatus,
    )
