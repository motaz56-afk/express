"""
Script de peuplement : crée un restaurant de démo, un gérant,
quelques tables, catégories et produits.

À lancer avec :  python -m app.seed
"""

from app import create_app, db
from app.models import Restaurant, User, Table, Category, Product
import secrets


def run_seed():
    app = create_app()
    with app.app_context():
        # Si un restaurant existe déjà, on ne recommence pas
        if Restaurant.query.first():
            print("⚠️  Des données existent déjà. Seed ignoré.")
            return

        print("🌱 Création du restaurant de démo…")
        resto = Restaurant(
            nom="Café Démo",
            adresse="Avenue Habib Bourguiba, Tunis",
            telephone="+216 71 000 000",
        )
        db.session.add(resto)
        db.session.flush()  # pour obtenir resto.id tout de suite

        # --- Gérant par défaut ---
        print("👤 Création du gérant par défaut…")
        gerant = User(
            prenom="Gérant",
            nom="Démo",
            username="gerant",
            role="GERANT",
            restaurant_id=resto.id,
        )
        gerant.set_password("admin123")
        db.session.add(gerant)

        # --- Tables ---
        print("🪑 Création des tables 01 à 06…")
        for n in range(1, 7):
            t = Table(
                numero=f"{n:02d}",
                token=secrets.token_urlsafe(16),
                restaurant_id=resto.id,
            )
            db.session.add(t)

        # --- Catégories ---
        print("📂 Création des catégories…")
        categories = [
            ("Cafés", "☕", 1),
            ("Boissons", "🥤", 2),
            ("Sandwichs", "🥪", 3),
            ("Pizzas", "🍕", 4),
            ("Plats", "🍔", 5),
            ("Desserts", "🍰", 6),
        ]
        cat_objs = {}
        for nom, emoji, ordre in categories:
            c = Category(nom=nom, emoji=emoji, ordre=ordre, restaurant_id=resto.id)
            db.session.add(c)
            cat_objs[nom] = c
        db.session.flush()

        # --- Produits de démo ---
        print("🍽️  Création des produits de démo…")
        produits = [
            ("Espresso", 1.5, "Cafés"),
            ("Cappuccino", 2.5, "Cafés"),
            ("Café au lait", 2.0, "Cafés"),
            ("Eau minérale 0.5L", 1.0, "Boissons"),
            ("Jus d'orange", 3.0, "Boissons"),
            ("Coca-Cola", 2.5, "Boissons"),
            ("Sandwich Thon", 4.5, "Sandwichs"),
            ("Sandwich Poulet", 5.0, "Sandwichs"),
            ("Pizza Margherita", 8.0, "Pizzas"),
            ("Pizza Thon", 9.0, "Pizzas"),
            ("Escalope grillée", 12.0, "Plats"),
            ("Tajine Poulet", 11.0, "Plats"),
            ("Tiramisu", 5.0, "Desserts"),
            ("Fondant chocolat", 5.5, "Desserts"),
        ]
        for nom, prix, cat_nom in produits:
            p = Product(
                nom=nom,
                prix=prix,
                category_id=cat_objs[cat_nom].id,
                restaurant_id=resto.id,
            )
            db.session.add(p)

        db.session.commit()
        print()
        print("=" * 60)
        print("  ✅ Seed terminé avec succès")
        print("=" * 60)
        print()
        print("🔑 Identifiants du gérant :")
        print("   username : gerant")
        print("   password : admin123")
        print()
        print("🪑 6 tables créées (01 à 06), chacune avec un token unique.")
        print("📂 6 catégories et 14 produits de démo créés.")


if __name__ == "__main__":
    run_seed()
