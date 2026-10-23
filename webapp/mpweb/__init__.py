"""Mentorenprogramm (dewiki) web interface."""
import gzip
import logging
import os
import time

from flask import Flask, g, render_template, request

from . import auth, helpers
from .config import load_config
from .db import DatabaseError, close_connections, get_mp, get_wiki

log = logging.getLogger(__name__)

SIDEBAR_TTL = 300  # seconds
STATIC_MAX_AGE = 365 * 24 * 3600  # static URLs carry a version parameter
GZIP_MIN_SIZE = 500
GZIP_TYPES = {"text/html", "text/css", "text/plain", "text/xml", "application/json",
              "application/javascript", "text/javascript", "application/xml", "image/svg+xml"}


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


def compress(response):
    """Gzip text responses.

    The Toolforge front proxy does not compress, and transfers from the
    webservice pod stall noticeably for every few KB, so fewer bytes matter.
    """
    if (response.status_code != 200 or "Content-Encoding" in response.headers
            or response.mimetype not in GZIP_TYPES
            or "gzip" not in request.headers.get("Accept-Encoding", "").lower()):
        return response
    response.direct_passthrough = False  # static files are streamed by default
    data = response.get_data()
    if len(data) < GZIP_MIN_SIZE:
        return response
    response.set_data(gzip.compress(data, compresslevel=6))
    response.headers["Content-Encoding"] = "gzip"
    response.vary.add("Accept-Encoding")
    etag, _ = response.get_etag()
    if etag:
        response.set_etag(etag, weak=True)
    return response


def _static_version(app):
    """URL default adding ``v=<mtime>`` to static URLs, so they can be cached long."""
    versions = {}

    def add_version(endpoint, values):
        if endpoint != "static" or "filename" not in values:
            return
        name = values["filename"]
        if name not in versions:
            try:
                versions[name] = int(os.stat(os.path.join(app.static_folder, name)).st_mtime)
            except OSError:
                versions[name] = 0
        values.setdefault("v", versions[name])
    return add_version


def create_app(config=None):
    app = Flask(__name__)
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = STATIC_MAX_AGE
    app.config.update(load_config())
    if config:
        app.config.update(config)
    app.url_defaults(_static_version(app))
    app.after_request(compress)

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
