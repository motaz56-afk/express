"""
Système de cache en mémoire, ultra-léger.
Évite les requêtes SQL répétées sur les pages fréquentes.
"""

import time
from threading import Lock


class MemoireCache:
    """Cache simple avec expiration basée sur le temps."""

    def __init__(self):
        self._data = {}
        self._lock = Lock()

    def get(self, cle):
        """Renvoie la valeur si non expirée, sinon None."""
        with self._lock:
            item = self._data.get(cle)
            if not item:
                return None
            valeur, expire_a = item
            if time.time() > expire_a:
                del self._data[cle]
                return None
            return valeur

    def set(self, cle, valeur, duree_secondes=60):
        """Stocke une valeur pour une durée donnée."""
        with self._lock:
            self._data[cle] = (valeur, time.time() + duree_secondes)

    def invalider(self, cle=None):
        """Supprime une clé ou tout le cache."""
        with self._lock:
            if cle is None:
                self._data.clear()
            else:
                self._data.pop(cle, None)


cache = MemoireCache()
