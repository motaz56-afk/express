"""
Événements WebSocket.
"""

from flask_socketio import join_room
from flask_login import current_user
from app import socketio


@socketio.on("connect")
def handle_connect():
    if current_user.is_authenticated:
        rid = current_user.restaurant_id
        join_room(f"resto_{rid}")
        join_room(f"resto_{rid}_role_{current_user.role}")
        print(f"[socket] {current_user.username} ({current_user.role}) "
              f"connecté au resto {rid}")
    else:
        print("[socket] Client anonyme connecté")


@socketio.on("disconnect")
def handle_disconnect():
    print("[socket] Client déconnecté")


@socketio.on("join_order")
def handle_join_order(data):
    """Un client QR rejoint la room de sa commande."""
    try:
        order_id = int(data.get("order_id"))
        join_room(f"order_{order_id}")
        print(f"[socket] Client rejoint order_{order_id}")
    except (TypeError, ValueError):
        pass


# =========================================================
# Notifications personnel
# =========================================================
def notifier_nouvelle_commande(commande):
    _emit_role(commande, "NEW_ORDER", "CUISINE")
    _emit_role(commande, "NEW_ORDER", "GERANT")


def notifier_nouvelle_commande_client(commande):
    _emit_role(commande, "NEW_QR_ORDER", "CUISINE")
    _emit_role(commande, "NEW_QR_ORDER", "GERANT")
    _emit_role(commande, "NEW_QR_ORDER", "SERVEUR")


def notifier_commande_en_preparation(commande):
    _emit_role(commande, "ORDER_PREPARING", "SERVEUR")
    _emit_role(commande, "ORDER_PREPARING", "GERANT")
    _emit_client(commande, "ORDER_PREPARING")


def notifier_commande_prete(commande):
    _emit_role(commande, "ORDER_READY", "SERVEUR")
    _emit_role(commande, "ORDER_READY", "GERANT")
    _emit_client(commande, "ORDER_READY")


def notifier_commande_servie(commande):
    _emit_role(commande, "ORDER_SERVED", "CUISINE")
    _emit_role(commande, "ORDER_SERVED", "GERANT")
    _emit_role(commande, "ORDER_SERVED", "CAISSIER")
    _emit_client(commande, "ORDER_SERVED")


def notifier_commande_acceptee(commande):
    _emit_role(commande, "ORDER_ACCEPTED", "SERVEUR")
    _emit_role(commande, "ORDER_ACCEPTED", "GERANT")
    _emit_client(commande, "ORDER_ACCEPTED")


def notifier_commande_refusee(commande):
    _emit_role(commande, "ORDER_REJECTED", "SERVEUR")
    _emit_role(commande, "ORDER_REJECTED", "GERANT")
    _emit_client(commande, "ORDER_REJECTED")


def notifier_paiement(paiement):
    """Notifie caissier et gérant d'un paiement."""
    data = {
        "id": paiement.id,
        "montant": paiement.montant,
        "methode": paiement.methode,
        "table_numero": paiement.table.numero if paiement.table else "?",
    }
    rid = paiement.restaurant_id
    socketio.emit("PAYMENT_COMPLETED", data, to=f"resto_{rid}_role_GERANT")
    socketio.emit("PAYMENT_COMPLETED", data, to=f"resto_{rid}_role_CAISSIER")


# =========================================================
# Helpers
# =========================================================
def _emit_role(commande, event, role):
    rid = commande.restaurant_id
    socketio.emit(event, _serialiser(commande),
                  to=f"resto_{rid}_role_{role}")


def _emit_client(commande, event):
    socketio.emit(event, _serialiser(commande),
                  to=f"order_{commande.id}")


def _serialiser(commande):
    return {
        "id": commande.id,
        "table_numero": commande.table.numero if commande.table else "?",
        "statut": commande.statut,
        "total": commande.total,
        "source": commande.source,
        "raison": commande.refus_raison or "",
        "items": [
            {"nom": it.nom_produit, "quantite": it.quantite,
             "prix": it.prix_unitaire}
            for it in commande.items
        ],
    }
