import os
from pathlib import Path

# Charge le .env UNIQUEMENT en local (pas sur Render)
if not os.environ.get("RENDER"):
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

from app import create_app, socketio

app = create_app()

if __name__ == "__main__":
    # Init local : si la base SQLite n'existe pas, on la crée
    db_path = Path("instance") / "moncafe.db"
    if not db_path.exists() and not os.environ.get("DATABASE_URL"):
        print("[local] Base absente. Initialisation...")
        from app import db
        from app.models import Restaurant, User
        with app.app_context():
            db.create_all()
            if not Restaurant.query.first():
                resto = Restaurant(nom="EXPRESS", adresse="", telephone="")
                resto.initialiser_abonnement(mois=8)
                db.session.add(resto)
                db.session.flush()
                u = User(prenom="Gérant", nom="Principal",
                         username="admin", role="GERANT",
                         restaurant_id=resto.id)
                u.set_password("admin123")
                db.session.add(u)
                db.session.commit()
                print("[local] Base créée (admin / admin123)")

    debug_mode = os.environ.get("FLASK_DEBUG", "1") == "1"
    if debug_mode:
        socketio.run(app, debug=True, use_reloader=False,
                     host="0.0.0.0", port=5000,
                     allow_unsafe_werkzeug=True)
    else:
        port = int(os.environ.get("PORT", 5000))
        socketio.run(app, host="0.0.0.0", port=port)