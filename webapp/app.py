"""WSGI entry point for the Toolforge python3.11 webservice (``~/www/python/src/app.py``)."""
from mpweb import create_app

app = create_app()
