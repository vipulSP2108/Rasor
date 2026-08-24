"""Root entrypoint launching the frontend Streamlit application."""

import runpy
import os

frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "app.py")
runpy.run_path(frontend_path, run_name="__main__")
