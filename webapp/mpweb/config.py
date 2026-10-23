"""Configuration loading.

On Toolforge the credentials come from ``~/replica.my.cnf``; every value can be
overridden with an environment variable (used by the tests and the CI).
"""
import configparser
import logging
import os
import secrets
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULTS = {
    "MP_DB_HOST": "tools.db.svc.wikimedia.cloud",
    "MP_DB_NAME": "s51391__mp",
    "WIKI_DB_HOST": "dewiki.web.db.svc.wikimedia.cloud",
    "WIKI_DB_NAME": "dewiki_p",
    "DB_PORT": "3306",
    "WIKI_BASE_URL": "https://de.wikipedia.org",
}


def read_my_cnf(path):
    """Return the ``[client]`` section of a MySQL option file as a dict."""
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(path)
    if not parser.has_section("client"):
        return {}
    return {key: value.strip("'\"") for key, value in parser.items("client")}


def _secret_key(env):
    if env.get("MP_SECRET_KEY"):
        return env["MP_SECRET_KEY"]
    key_file = Path(env.get("MP_SECRET_KEY_FILE", Path.home() / ".mp_secret_key"))
    if key_file.is_file():
        return key_file.read_text().strip()
    log.warning("No MP_SECRET_KEY configured, using a random key; sessions "
                "will not survive a restart and are not shared between workers.")
    return secrets.token_hex(32)


def load_config(env=None):
    """Build the Flask config dict from defaults, ``replica.my.cnf`` and *env*."""
    env = os.environ if env is None else env
    cnf_path = env.get("MP_DB_CNF", str(Path.home() / "replica.my.cnf"))
    creds = read_my_cnf(cnf_path) if os.path.isfile(cnf_path) else {}

    def get(name):
        return env.get(name, DEFAULTS.get(name))

    return {
        "MP_DB_HOST": get("MP_DB_HOST"),
        "MP_DB_NAME": get("MP_DB_NAME"),
        "WIKI_DB_HOST": get("WIKI_DB_HOST"),
        "WIKI_DB_NAME": get("WIKI_DB_NAME"),
        "DB_PORT": int(get("DB_PORT")),
        "DB_USER": env.get("MP_DB_USER", creds.get("user")),
        "DB_PASSWORD": env.get("MP_DB_PASSWORD", creds.get("password")),
        "WIKI_BASE_URL": get("WIKI_BASE_URL"),
        "DUMP_DIR": env.get("MP_DUMP_DIR", str(Path.home() / "public_html" / "sql-dumps")),
        # older dumps still contain the legacy password hashes and are not served
        "DUMPS_NOT_BEFORE": env.get("MP_DUMPS_NOT_BEFORE", "2026-10-24"),
        "SECRET_KEY": _secret_key(env),
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": env.get("MP_INSECURE_COOKIES") != "1",
        "PERMANENT_SESSION_LIFETIME": 86400,
    }
