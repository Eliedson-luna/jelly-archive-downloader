"""Ponto de entrada WSGI (usado pelo waitress no container)."""

import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8088")),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
