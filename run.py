import os
from app import create_app, socketio

app = create_app()

if __name__ == "__main__":
    # En développement local : mode threading (compatible Windows)
    # En production (Render) : gunicorn + eventlet s'occupe de tout.
    debug_mode = os.environ.get("FLASK_DEBUG", "1") == "1"

    if debug_mode:
        # Mode local
        socketio.run(
            app,
            debug=True,
            use_reloader=False,
            host="0.0.0.0",
            port=5000,
            allow_unsafe_werkzeug=True,
        )
    else:
        # Mode production (si lancé directement)
        port = int(os.environ.get("PORT", 5000))
        socketio.run(app, host="0.0.0.0", port=port)