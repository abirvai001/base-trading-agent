"""Convenience launcher for the web dashboard."""
import os
import sys

if __name__ == "__main__":
    # Ensure project root is on the path
    sys.path.insert(0, os.path.dirname(__file__))

    from dotenv import load_dotenv
    load_dotenv()

    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    from web.app import app, socketio, setup_ui_logging
    setup_ui_logging()

    port = int(os.getenv("PORT", 5000))
    print(f"\n  Base Trading Agent dashboard → http://localhost:{port}\n")
    socketio.run(app, host="0.0.0.0", port=port,
                 debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
