"""
Fonctions et décorateurs utilitaires.
"""

from functools import wraps
from flask import abort, request
from flask_login import current_user


def role_required(*roles_autorises):
    """Décorateur : restreint l'accès aux rôles listés."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles_autorises:
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator


def log_action(action, cible=None, details=None):
    """
    Enregistre une action dans la table audit_logs.
    À appeler après chaque action importante.

    Ne lève JAMAIS d'exception : si le log échoue, on ne bloque pas l'app.
    """
    try:
        from app import db
        from app.models import AuditLog

        # Récupération sécurisée du contexte
        user_id = None
        username = None
        restaurant_id = None
        if current_user and current_user.is_authenticated:
            user_id = current_user.id
            username = current_user.username
            restaurant_id = current_user.restaurant_id

        ip = None
        try:
            ip = request.remote_addr
        except RuntimeError:
            # Pas de contexte de requête (ex: test unitaire)
            pass

        log = AuditLog(
            action=action,
            cible=cible,
            details=details,
            ip=ip,
            username=username,
            restaurant_id=restaurant_id,
            user_id=user_id,
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        # On n'empêche jamais l'app de fonctionner à cause d'un log raté
        try:
            from app import db
            db.session.rollback()
        except Exception:
            pass
        print(f"[audit] Erreur lors de l'enregistrement du log : {e}")
