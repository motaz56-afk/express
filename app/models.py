from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db


class OrderStatus:
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    PREPARING = "PREPARING"
    READY = "READY"
    SERVED = "SERVED"
    PAID = "PAID"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    ALL = [PENDING_CONFIRMATION, PENDING, ACCEPTED, PREPARING,
           READY, SERVED, PAID, REJECTED, CANCELLED]
    LABELS = {
        PENDING_CONFIRMATION: "⏳ À confirmer", PENDING: "🕐 En attente",
        ACCEPTED: "✅ Acceptée", PREPARING: "👨‍🍳 En préparation",
        READY: "🟢 Prête", SERVED: "🍽️ Servie",
        PAID: "💰 Payée", REJECTED: "❌ Refusée", CANCELLED: "❌ Annulée",
    }
    COLORS = {
        PENDING_CONFIRMATION: "warning", PENDING: "warning",
        ACCEPTED: "info", PREPARING: "primary",
        READY: "success", SERVED: "secondary",
        PAID: "dark", REJECTED: "danger", CANCELLED: "danger",
    }
    ACTIFS = [PENDING_CONFIRMATION, PENDING, ACCEPTED, PREPARING, READY]


class OrderSource:
    WAITER = "WAITER"
    QR_CODE = "QR_CODE"


class PaymentMethod:
    ESPECES = "ESPECES"
    CARTE = "CARTE"
    AUTRE = "AUTRE"
    ALL = [ESPECES, CARTE, AUTRE]
    LABELS = {ESPECES: "💵 Espèces", CARTE: "💳 Carte", AUTRE: "🔹 Autre"}


# =========================================================
# RESTAURANT — avec abonnement
# =========================================================
class Restaurant(db.Model):
    __tablename__ = "restaurants"

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(120), nullable=False)
    adresse = db.Column(db.String(255))
    telephone = db.Column(db.String(30))
    logo = db.Column(db.String(255))
    actif = db.Column(db.Boolean, default=True)
    cree_le = db.Column(db.DateTime, default=datetime.utcnow)

    # ---- Abonnement ----
    date_expiration = db.Column(db.DateTime)
    bloque = db.Column(db.Boolean, default=False)
    notes_admin = db.Column(db.String(255))

    users = db.relationship("User", backref="restaurant", lazy=True)
    tables = db.relationship("Table", backref="restaurant", lazy=True)
    categories = db.relationship("Category", backref="restaurant", lazy=True)
    products = db.relationship("Product", backref="restaurant", lazy=True)
    orders = db.relationship("Order", backref="restaurant", lazy=True)

    # ---------- Méthodes abonnement ----------
    def initialiser_abonnement(self, mois=8):
        """Donne un accès initial."""
        self.date_expiration = datetime.utcnow() + timedelta(days=30 * mois)
        self.bloque = False

    def prolonger_abonnement(self, mois=8):
        """Ajoute N mois à partir de la date actuelle (ou d'aujourd'hui si déjà expiré)."""
        base = self.date_expiration or datetime.utcnow()
        if base < datetime.utcnow():
            base = datetime.utcnow()
        self.date_expiration = base + timedelta(days=30 * mois)
        self.bloque = False

    def est_expire(self):
        if self.bloque:
            return True
        if not self.date_expiration:
            return False
        return datetime.utcnow() > self.date_expiration

    def jours_restants(self):
        if not self.date_expiration:
            return 0
        delta = self.date_expiration - datetime.utcnow()
        return max(0, delta.days)

    def statut_abonnement(self):
        if self.bloque:
            return "BLOQUE"
        if not self.date_expiration:
            return "ILLIMITE"
        jours = self.jours_restants()
        if jours <= 0:
            return "EXPIRE"
        if jours <= 15:
            return "BIENTOT_EXPIRE"
        return "ACTIF"

    def __repr__(self):
        return f"<Restaurant {self.id} - {self.nom}>"


# =========================================================
# CODE D'ACTIVATION
# =========================================================
class ActivationCode(db.Model):
    __tablename__ = "activation_codes"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    mois = db.Column(db.Integer, nullable=False, default=8)
    utilise = db.Column(db.Boolean, default=False)
    utilise_le = db.Column(db.DateTime)
    cree_le = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    expire_le = db.Column(db.DateTime)  # date max d'utilisation

    # Trace qui l'a utilisé
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=True)
    restaurant = db.relationship("Restaurant", foreign_keys=[restaurant_id])

    # Notes admin
    notes = db.Column(db.String(255))
    # Qui a payé (tel ou nom)
    payeur = db.Column(db.String(120))

    def est_utilisable(self):
        if self.utilise:
            return False, "Ce code a déjà été utilisé."
        if self.expire_le and datetime.utcnow() > self.expire_le:
            return False, "Ce code a expiré."
        return True, ""

    def __repr__(self):
        return f"<ActivationCode {self.code} - {'utilisé' if self.utilise else 'valide'}>"


# =========================================================
# UTILISATEUR
# =========================================================
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    prenom = db.Column(db.String(60), nullable=False)
    nom = db.Column(db.String(60), nullable=False)
    username = db.Column(db.String(60), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="SERVEUR")
    actif = db.Column(db.Boolean, default=True)
    cree_le = db.Column(db.DateTime, default=datetime.utcnow)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)

    def set_password(self, mot_de_passe):
        self.password_hash = generate_password_hash(mot_de_passe)

    def check_password(self, mot_de_passe):
        return check_password_hash(self.password_hash, mot_de_passe)

    @property
    def is_active(self):
        return self.actif

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class Table(db.Model):
    __tablename__ = "tables"
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    qr_actif = db.Column(db.Boolean, default=True)
    places = db.Column(db.Integer, default=4)
    cree_le = db.Column(db.DateTime, default=datetime.utcnow)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)
    orders = db.relationship("Order", backref="table", lazy=True)

    def __repr__(self):
        return f"<Table {self.numero}>"


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(80), nullable=False)
    emoji = db.Column(db.String(10))
    ordre = db.Column(db.Integer, default=0)
    cree_le = db.Column(db.DateTime, default=datetime.utcnow)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)
    products = db.relationship("Product", backref="category", lazy=True)

    def __repr__(self):
        return f"<Category {self.nom}>"


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255))
    prix = db.Column(db.Float, nullable=False, default=0.0)
    disponible = db.Column(db.Boolean, default=True)
    cree_le = db.Column(db.DateTime, default=datetime.utcnow)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)

    def __repr__(self):
        return f"<Product {self.nom}>"


class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    statut = db.Column(db.String(30), nullable=False,
                       default=OrderStatus.PENDING, index=True)
    source = db.Column(db.String(20), nullable=False, default=OrderSource.WAITER)
    total = db.Column(db.Float, nullable=False, default=0.0)
    note = db.Column(db.String(255))
    refus_raison = db.Column(db.String(255))
    client_session_id = db.Column(db.String(64), index=True)
    cree_le = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    paye_le = db.Column(db.DateTime)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)
    table_id = db.Column(db.Integer, db.ForeignKey("tables.id"), nullable=False)
    serveur_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), nullable=True)

    serveur = db.relationship("User", foreign_keys=[serveur_id])
    items = db.relationship("OrderItem", backref="order", lazy=True,
                            cascade="all, delete-orphan")

    def recalculer_total(self):
        self.total = sum(item.prix_unitaire * item.quantite for item in self.items)


class OrderItem(db.Model):
    __tablename__ = "order_items"
    id = db.Column(db.Integer, primary_key=True)
    nom_produit = db.Column(db.String(120), nullable=False)
    prix_unitaire = db.Column(db.Float, nullable=False)
    quantite = db.Column(db.Integer, nullable=False, default=1)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)

    def sous_total(self):
        return self.prix_unitaire * self.quantite


class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    montant = db.Column(db.Float, nullable=False)
    methode = db.Column(db.String(20), nullable=False, default=PaymentMethod.ESPECES)
    notes = db.Column(db.String(255))
    cree_le = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"), nullable=False)
    table_id = db.Column(db.Integer, db.ForeignKey("tables.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    table = db.relationship("Table")
    user = db.relationship("User")
    orders = db.relationship("Order", backref="payment", lazy=True,
                             foreign_keys="Order.payment_id")


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(50), nullable=False, index=True)
    cible = db.Column(db.String(120))
    details = db.Column(db.Text)
    ip = db.Column(db.String(45))
    username = db.Column(db.String(60))
    cree_le = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurants.id"),
                              nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    user = db.relationship("User")
