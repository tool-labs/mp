"""Mentorenprogramm (dewiki) web interface."""
import logging
import time

from flask import Flask, g, render_template

from . import auth, helpers
from .config import load_config
from .db import DatabaseError, close_connections, get_mp, get_wiki

log = logging.getLogger(__name__)

SIDEBAR_TTL = 300  # seconds


def _sidebar_counts(app):
    cache = app.extensions.setdefault("mp_sidebar", {"time": 0, "data": None})
    if cache["data"] is not None and time.monotonic() - cache["time"] < SIDEBAR_TTL:
        return cache["data"]
    data = {"db": None, "wp": None}
    try:
        data["db"] = get_mp().counts_db()
    except Exception:  # sidebar must never break a page
        log.exception("sidebar: mp database")
    try:
        data["wp"] = get_wiki().category_sizes()
    except Exception:
        log.exception("sidebar: wiki replica")
    cache.update(time=time.monotonic(), data=data)
    return data


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(load_config())
    if config:
        app.config.update(config)

    from .views import api, legacy, main, maintenance, mentees, mentors, relations
    from .views import auth as auth_views
    for module in (main, mentors, mentees, relations, maintenance, auth_views, api, legacy):
        app.register_blueprint(module.bp)

    app.before_request(auth.load_user)
    app.before_request(auth.check_csrf)
    app.teardown_appcontext(close_connections)

    app.add_template_filter(helpers.format_date, "date")
    app.add_template_filter(helpers.format_datetime, "datetime")
    app.add_template_filter(helpers.format_number, "number")
    app.add_template_filter(helpers.award_name, "award")
    app.add_template_filter(helpers.mm_type_short, "mm_type")

    @app.context_processor
    def inject():
        base = app.config["WIKI_BASE_URL"]
        return {
            "csrf_token": auth.csrf_token,
            "wiki_url": lambda title, **params: helpers.wiki_url(base, title, **params),
            "user_url": lambda name: helpers.wiki_url(base, f"Benutzer:{name}"),
            "contribs_url": lambda name: helpers.wiki_url(base, f"Spezial:Beiträge/{name}"),
            "sidebar": lambda: _sidebar_counts(app),
            "is_editor": bool(g.get("user")),
        }

    @app.errorhandler(DatabaseError)
    def database_error(exc):
        log.error("database error: %s", exc)
        return render_template("error.html", code=503, title="Datenbank nicht erreichbar",
                               message="Die Datenbank ist zurzeit nicht erreichbar. "
                                       "Bitte versuche es später noch einmal."), 503

    for code, title in ((400, "Ungültige Anfrage"), (404, "Seite nicht gefunden"),
                        (405, "Methode nicht erlaubt")):
        app.register_error_handler(code, _error_page(code, title))

    return app


def _error_page(code, title):
    def handler(exc):
        message = getattr(exc, "description", None) or title
        return render_template("error.html", code=code, title=title, message=message), code
    return handler
