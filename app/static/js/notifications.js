/* =========================================================
   MON CAFÉ APP — Notifications sonores + vibration + FAB
   ========================================================= */

(function () {
    "use strict";

    // ============================================================
    // 1. SON — généré via Web Audio API (aucun fichier à héberger)
    // ============================================================
    let audioCtx = null;

    function initialiserAudio() {
        if (audioCtx) return;
        try {
            const Ctx = window.AudioContext || window.webkitAudioContext;
            if (Ctx) audioCtx = new Ctx();
        } catch (e) {
            console.warn("[notif] Audio non disponible", e);
        }
    }

    // Certains navigateurs exigent une interaction avant de jouer du son
    document.addEventListener("click", initialiserAudio, { once: true });
    document.addEventListener("touchstart", initialiserAudio, { once: true });

    /**
     * Joue un son de notification.
     * @param {string} type - "nouveau" | "pret" | "info"
     */
    function jouerSon(type) {
        initialiserAudio();
        if (!audioCtx) return;
        if (audioCtx.state === "suspended") audioCtx.resume();

        const maintenant = audioCtx.currentTime;

        // Mélodies différentes selon le type
        let notes = [];
        if (type === "nouveau") {
            // Ding ! Ding ! (2 tons aigus, urgents)
            notes = [
                { freq: 880, debut: 0,    duree: 0.15 },
                { freq: 1175, debut: 0.18, duree: 0.15 },
                { freq: 880, debut: 0.36, duree: 0.15 },
                { freq: 1175, debut: 0.54, duree: 0.25 },
            ];
        } else if (type === "pret") {
            // Ding clair (aigu puis plus aigu)
            notes = [
                { freq: 1046, debut: 0,    duree: 0.12 },
                { freq: 1568, debut: 0.15, duree: 0.25 },
            ];
        } else {
            // Notification discrète
            notes = [{ freq: 660, debut: 0, duree: 0.12 }];
        }

        notes.forEach(({ freq, debut, duree }) => {
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();

            osc.type = "sine";
            osc.frequency.value = freq;

            gain.gain.setValueAtTime(0, maintenant + debut);
            gain.gain.linearRampToValueAtTime(0.35, maintenant + debut + 0.01);
            gain.gain.exponentialRampToValueAtTime(
                0.001, maintenant + debut + duree
            );

            osc.connect(gain);
            gain.connect(audioCtx.destination);

            osc.start(maintenant + debut);
            osc.stop(maintenant + debut + duree + 0.05);
        });
    }

    // ============================================================
    // 2. VIBRATION
    // ============================================================
    function vibrer(type) {
        if (!("vibrate" in navigator)) return;
        try {
            if (type === "nouveau") {
                // 3 vibrations courtes + pause + 1 longue
                navigator.vibrate([200, 100, 200, 100, 200, 300, 400]);
            } else if (type === "pret") {
                // 2 vibrations courtes
                navigator.vibrate([150, 80, 150]);
            } else {
                navigator.vibrate(120);
            }
        } catch (e) {
            // Silencieux
        }
    }

    // ============================================================
    // 3. NOTIFICATION (son + vibration + toast visuel)
    // ============================================================
    function notifier(message, options) {
        options = options || {};
        const type = options.type || "info";       // "nouveau" | "pret" | "info"
        const couleur = options.couleur || "warning";

        // Son + vibration
        jouerSon(type);
        vibrer(type);

        // Toast visuel
        const toast = document.createElement("div");
        toast.className = "toast-luxe " + couleur;
        toast.innerHTML = message;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.transition = "opacity 0.3s";
            toast.style.opacity = "0";
            setTimeout(() => toast.remove(), 300);
        }, 6000);

        // Mise à jour du compteur FAB
        ajouterNotificationCompteur(message, couleur);
    }

    // Exposé globalement pour les autres scripts
    window.notifier = notifier;

    // ============================================================
    // 4. BOUTON FLOTTANT + PANNEAU DE NOTIFICATIONS
    // ============================================================
    const notifications = [];
    let nonLues = 0;

    function creerFAB() {
        const fab = document.createElement("button");
        fab.id = "notif-fab";
        fab.className = "notif-fab";
        fab.setAttribute("aria-label", "Notifications");
        fab.innerHTML = '🔔<span class="notif-badge" id="notif-badge">0</span>';
        document.body.appendChild(fab);

        const panel = document.createElement("div");
        panel.id = "notif-panel";
        panel.className = "notif-panel";
        panel.innerHTML = `
            <div class="notif-panel-header">
                <span>Notifications</span>
                <button class="close-btn" aria-label="Fermer">✕</button>
            </div>
            <div class="notif-list" id="notif-list">
                <div class="notif-empty">Aucune notification pour le moment.</div>
            </div>
        `;
        document.body.appendChild(panel);

        // Events
        fab.addEventListener("click", () => {
            panel.classList.toggle("open");
            if (panel.classList.contains("open")) {
                nonLues = 0;
                majBadge();
            }
        });

        panel.querySelector(".close-btn").addEventListener("click", () => {
            panel.classList.remove("open");
        });

        // Fermer si clic ailleurs
        document.addEventListener("click", (e) => {
            if (!panel.classList.contains("open")) return;
            if (panel.contains(e.target) || fab.contains(e.target)) return;
            panel.classList.remove("open");
        });
    }

    function majBadge() {
        const badge = document.getElementById("notif-badge");
        if (!badge) return;
        if (nonLues > 0) {
            badge.textContent = nonLues > 99 ? "99+" : nonLues;
            badge.classList.add("visible");
        } else {
            badge.classList.remove("visible");
        }
    }

    function ajouterNotificationCompteur(message, couleur) {
        // Nettoyer le message HTML pour l'affichage dans la liste
        const tmp = document.createElement("div");
        tmp.innerHTML = message;
        const texte = tmp.textContent || tmp.innerText || "";

        const maintenant = new Date();
        const heure = maintenant.getHours().toString().padStart(2, "0")
            + ":" + maintenant.getMinutes().toString().padStart(2, "0");

        notifications.unshift({
            message: texte,
            couleur: couleur,
            heure: heure,
            lue: false,
        });

        // Limiter à 50 entrées
        if (notifications.length > 50) notifications.pop();

        nonLues++;
        majBadge();
        rendreListeNotifications();
    }

    function rendreListeNotifications() {
        const liste = document.getElementById("notif-list");
        if (!liste) return;

        if (notifications.length === 0) {
            liste.innerHTML =
                '<div class="notif-empty">Aucune notification pour le moment.</div>';
            return;
        }

        liste.innerHTML = notifications.map((n) => `
            <div class="notif-item">
                <div class="notif-titre">
                    <span>${n.message}</span>
                    <span class="notif-heure">${n.heure}</span>
                </div>
            </div>
        `).join("");
    }

    // Initialiser le FAB dès que le DOM est prêt
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", creerFAB);
    } else {
        creerFAB();
    }

})();
