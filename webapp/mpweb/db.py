"""Database connections.

Two connections are used: the tool's own database on ToolsDB (``mp``) and the
read-only dewiki replica (``wiki``). Both are opened lazily per request and
closed when the application context ends.
"""
import pymysql
import pymysql.cursors
from flask import current_app, g
from pymysql.constants import CLIENT


class DatabaseError(Exception):
    """Raised when a database cannot be reached."""


def connect(host, database, user, password, port=3306):
    try:
        return pymysql.connect(
            host=host, port=port, user=user, password=password,
            database=database, charset="utf8mb4", autocommit=True,
            cursorclass=pymysql.cursors.DictCursor, connect_timeout=10,
            # UPDATE returns matched instead of changed rows (unchanged save ≠ conflict)
            client_flag=CLIENT.FOUND_ROWS,
        )
    except pymysql.err.OperationalError as exc:
        raise DatabaseError(f"Verbindung zu {database}@{host} fehlgeschlagen: {exc}") from exc


def connect_from_config(config, which):
    prefix = "MP" if which == "mp" else "WIKI"
    return connect(config[f"{prefix}_DB_HOST"], config[f"{prefix}_DB_NAME"],
                   config["DB_USER"], config["DB_PASSWORD"], config["DB_PORT"])


def get_mp():
    from .repository import MPRepository
    if "mp_repo" not in g:
        g.mp_repo = MPRepository(connect_from_config(current_app.config, "mp"))
    return g.mp_repo


def get_wiki():
    from .wiki import WikiRepository
    if "wiki_repo" not in g:
        g.wiki_repo = WikiRepository(connect_from_config(current_app.config, "wiki"))
    return g.wiki_repo


def close_connections(_exc=None):
    for name in ("mp_repo", "wiki_repo"):
        repo = g.pop(name, None)
        if repo is not None:
            repo.close()


class BaseRepository:
    def __init__(self, conn):
        self.conn = conn

    def close(self):
        try:
            self.conn.close()
        except pymysql.err.Error:
            pass

    def all(self, sql, args=None):
        with self.conn.cursor() as cur:
            cur.execute(sql, args)
            return list(cur.fetchall())

    def one(self, sql, args=None):
        with self.conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchone()

    def scalar(self, sql, args=None):
        row = self.one(sql, args)
        return None if row is None else next(iter(row.values()))

    def execute(self, sql, args=None):
        with self.conn.cursor() as cur:
            return cur.execute(sql, args)
