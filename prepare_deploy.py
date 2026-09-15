"""
Vérifie que tous les fichiers nécessaires au déploiement existent.
"""

from pathlib import Path

ROOT = Path(__file__).parent.resolve()

print("=" * 60)
print("  VÉRIFICATION — Préparation au déploiement")
print("=" * 60)

fichiers_requis = [
    "requirements.txt",
    "Procfile",
    ".gitignore",
    "config.py",
    "run.py",
]

manquants = []
for f in fichiers_requis:
    chemin = ROOT / f
    if chemin.exists():
        taille = chemin.stat().st_size
        print(f"✅ {f} ({taille} octets)")
    else:
        print(f"❌ MANQUANT : {f}")
        manquants.append(f)

# Vérifie requirements.txt
print()
req = ROOT / "requirements.txt"
if req.exists():
    contenu = req.read_text(encoding="utf-8")
    requis = ["Flask", "gunicorn", "eventlet", "Flask-SocketIO",
              "Flask-SQLAlchemy", "Flask-Login", "qrcode"]
    for r in requis:
        if r.lower() in contenu.lower():
            print(f"✅ {r} présent dans requirements.txt")
        else:
            print(f"⚠️  {r} ABSENT de requirements.txt")
            manquants.append(r)

# Vérifie Procfile
print()
proc = ROOT / "Procfile"
if proc.exists():
    contenu = proc.read_text(encoding="utf-8")
    if "gunicorn" in contenu and "eventlet" in contenu:
        print("✅ Procfile correct (gunicorn + eventlet)")
    else:
        print("⚠️  Procfile semble incorrect")
        print(f"   Contenu actuel : {contenu}")

print()
if manquants:
    print("=" * 60)
    print("  ⚠️  ÉLÉMENTS MANQUANTS :")
    print("=" * 60)
    for m in manquants:
        print(f"   • {m}")
    print()
    print("Corrige ces éléments avant de continuer.")
else:
    print("=" * 60)
    print("  ✅ TOUT EST PRÊT POUR LE DÉPLOIEMENT")
    print("=" * 60)