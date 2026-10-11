"""
Fonctions et décorateurs utilitaires.
"""

from functools import wraps
from flask import abort, request, session
from flask_login import current_user


def role_required(*roles_autorises):
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


def abonnement_required(f):
    """
    Décorateur : bloque l'accès si l'abonnement du restaurant est expiré.
    Redirige vers /abonnement (sauf pour la page abonnement elle-même).
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        resto = current_user.restaurant
        if resto and resto.est_expire():
            # Autoriser uniquement la page /abonnement et les routes de contact
            from flask import request, redirect, url_for
            allowed = ("/abonnement", "/logout", "/static")
            if not any(request.path.startswith(p) for p in allowed):
                return redirect("/abonnement")
        return f(*args, **kwargs)
    return wrapper


def log_action(action, cible=None, details=None):
    try:
        from app import db
        from app.models import AuditLog
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
            pass
        log = AuditLog(action=action, cible=cible, details=details,
                       ip=ip, username=username,
                       restaurant_id=restaurant_id, user_id=user_id)
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        try:
            from app import db
            db.session.rollback()
        except Exception:
            pass
        print(f"[audit] Erreur : {e}")
