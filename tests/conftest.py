"""Shared fixtures.

Unit tests need nothing. Integration tests (marker ``db``) need a MariaDB
server; configure it with environment variables::

    MP_TEST_DB_HOST=127.0.0.1 MP_TEST_DB_USER=root MP_TEST_DB_PASSWORD=root pytest

The databases ``MP_TEST_DB_NAME`` (default ``mp_test``) and
``WIKI_TEST_DB_NAME`` (default ``wiki_test``) are DROPPED and re-created for
every test. Their names must contain ``test``.
"""
import datetime as dt
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "webapp"))
# never pick up real credentials from ~/replica.my.cnf during tests
os.environ["MP_DB_CNF"] = str(ROOT / "tests" / "no-such-file.cnf")
os.environ.setdefault("MP_SECRET_KEY", "test")

from mpweb import create_app  # noqa: E402
from mpweb.auth import legacy_hash  # noqa: E402

NOW = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None, microsecond=0)
LEGACY_SALT = "0123456789abcdef0123456789abcdef01234567"
ALICE_PASSWORD = "geheim123"


def ts(value):
    return value.strftime("%Y%m%d%H%M%S")


def split_sql(text):
    text = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("--"))
    return [stmt.strip() for stmt in re.split(r";\s*$", text, flags=re.M) if stmt.strip()]


def run_sql_file(conn, path):
    with conn.cursor() as cur:
        for stmt in split_sql(Path(path).read_text()):
            cur.execute(stmt)


def db_settings():
    host = os.environ.get("MP_TEST_DB_HOST")
    if not host:
        return None
    settings = {
        "host": host,
        "port": int(os.environ.get("MP_TEST_DB_PORT", "3306")),
        "user": os.environ.get("MP_TEST_DB_USER", "root"),
        "password": os.environ.get("MP_TEST_DB_PASSWORD", ""),
        "mp_db": os.environ.get("MP_TEST_DB_NAME", "mp_test"),
        "wiki_db": os.environ.get("WIKI_TEST_DB_NAME", "wiki_test"),
    }
    for name in (settings["mp_db"], settings["wiki_db"]):
        if "test" not in name:
            raise RuntimeError(f"refusing to use database {name!r}: name must contain 'test'")
    return settings


def pytest_collection_modifyitems(config, items):
    if db_settings():
        return
    skip = pytest.mark.skip(reason="no test database configured (MP_TEST_DB_HOST)")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip)


def _raw_connect(settings, database=None, autocommit=True):
    import pymysql
    return pymysql.connect(host=settings["host"], port=settings["port"], user=settings["user"],
                           password=settings["password"], database=database, charset="utf8mb4",
                           autocommit=autocommit, cursorclass=pymysql.cursors.DictCursor)


def _insert(cur, table, rows):
    for row in rows:
        cols = ", ".join(f"`{c}`" for c in row)
        cur.execute(f"INSERT INTO `{table}` ({cols}) VALUES ({', '.join(['%s'] * len(row))})",
                    list(row.values()))


def _mp_legacy_data(cur):
    """Data in the *old* schema, so that the migration is tested as well."""
    _insert(cur, "mentor", [
        {"mentor_user_id": 101, "mentor_user_name": "Alice", "mentor_in": "2010-01-01",
         "mentor_award_level": 1, "mentor_has_barnstar": 1, "mentor_remark": "Erfahren <b>!</b>",
         "mentor_login_password": legacy_hash(ALICE_PASSWORD, LEGACY_SALT), "mentor_pw_salt": LEGACY_SALT,
         "mentor_lastupdate": "2020-02-02 02:02:02"},
        {"mentor_user_id": 102, "mentor_user_name": "Bob", "mentor_in": "2012-03-04"},
        {"mentor_user_id": 103, "mentor_user_name": "Carol", "mentor_in": "2009-01-01", "mentor_out": "2015-05-05"},
        {"mentor_user_id": 104, "mentor_user_name": "Dave", "mentor_in": "2020-06-01"},
    ])
    _insert(cur, "mentee", [
        {"mentee_user_id": 201, "mentee_user_name": "Neuling1"},
        {"mentee_user_id": 202, "mentee_user_name": "Neuling2"},
        {"mentee_user_id": 203, "mentee_user_name": "Kurz"},
        {"mentee_user_id": 204, "mentee_user_name": "Alt Neuling"},
    ])
    _insert(cur, "mentee_mentor", [
        {"mm_mentee_id": 201, "mm_mentor_id": 101, "mm_start": NOW - dt.timedelta(days=20), "mm_type": 2},
        {"mm_mentee_id": 202, "mm_mentor_id": 102, "mm_start": "2020-01-01 10:00:00",
         "mm_stop": "2020-03-01 10:00:00", "mm_type": 1},
        {"mm_mentee_id": 202, "mm_mentor_id": 101, "mm_start": NOW - dt.timedelta(days=50), "mm_type": 0},
        {"mm_mentee_id": 203, "mm_mentor_id": 103, "mm_start": "2014-02-01 10:00:00",
         "mm_stop": "2014-02-01 12:00:00", "mm_type": 0},
        {"mm_mentee_id": 204, "mm_mentor_id": 102, "mm_start": "2025-01-01 08:00:00", "mm_type": 1},
    ])
    _insert(cur, "logging", [{"log_comment": "alt", "log_user_name": "Alice", "log_type": "update_mentor",
                              "log_target": 101}])
    _insert(cur, "mentees_recentchanges", [{
        "rc_id": 1, "rc_timestamp": ts(NOW - dt.timedelta(days=400)), "actor_id": 1201,
        "actor_name": "Neuling1", "rc_namespace": 0, "rc_title": "Uralt", "comment_text": "",
    }])


def _wiki_data(cur):
    users = {101: "Alice", 102: "Bob", 103: "Carol", 104: "Dave", 201: "Neuling1", 202: "Neuling2",
             203: "Kurz", 204: "Alt Neuling", 300: "Neu Mentee"}
    _insert(cur, "user", [{"user_id": i, "user_name": n, "user_editcount": i * 10} for i, n in users.items()])
    _insert(cur, "actor", [{"actor_id": 1000 + i, "actor_user": i, "actor_name": n} for i, n in users.items()])
    _insert(cur, "page", [{"page_id": 5000 + i, "page_namespace": 2, "page_title": n.replace(" ", "_")}
                          for i, n in users.items()]
            + [{"page_id": 9001, "page_namespace": 0, "page_title": "Testartikel"}])
    _insert(cur, "linktarget", [{"lt_id": 1, "lt_namespace": 14, "lt_title": "Benutzer:Mentor"},
                                {"lt_id": 2, "lt_namespace": 14, "lt_title": "Benutzer:Mentee"}])
    _insert(cur, "categorylinks", [{"cl_from": 5000 + i, "cl_target_id": 1} for i in (101, 102)]
            + [{"cl_from": 5000 + i, "cl_target_id": 2} for i in (201, 202, 204, 300)])
    _insert(cur, "category", [{"cat_id": 1, "cat_title": "Benutzer:Mentor", "cat_pages": 2},
                              {"cat_id": 2, "cat_title": "Benutzer:Mentee", "cat_pages": 4}])
    _insert(cur, "comment", [{"comment_id": 1, "comment_text": "MP: Mentor übernommen"},
                             {"comment_id": 2, "comment_text": "Tippfehler"}])
    _insert(cur, "revision_userindex", [
        {"rev_id": 1, "rev_page": 5201, "rev_actor": 1101, "rev_comment_id": 1,
         "rev_timestamp": ts(NOW - dt.timedelta(days=19))},
        {"rev_id": 2, "rev_page": 9001, "rev_actor": 1201, "rev_comment_id": 2,
         "rev_timestamp": ts(NOW - dt.timedelta(days=2))},
        {"rev_id": 3, "rev_page": 9001, "rev_actor": 1202, "rev_comment_id": 2,
         "rev_timestamp": ts(NOW - dt.timedelta(days=45))},
        {"rev_id": 4, "rev_page": 9001, "rev_actor": 1204, "rev_comment_id": 2,
         "rev_timestamp": "20250201120000"},
    ])
    _insert(cur, "comment_recentchanges", [{"comment_id": 1, "comment_text": "/* Abschnitt */ [[Link|Text]] <script>"},
                                           {"comment_id": 2, "comment_text": "verschoben"}])
    move_params = 'a:2:{s:9:"4::target";s:13:"Neuer_Artikel";s:10:"5::noredir";s:1:"0";}'
    _insert(cur, "recentchanges_userindex", [
        {"rc_id": 10, "rc_timestamp": ts(NOW - dt.timedelta(hours=1)), "rc_actor": 1201, "rc_namespace": 0,
         "rc_title": "Testartikel", "rc_comment_id": 1, "rc_source": "mw.edit", "rc_this_oldid": 22,
         "rc_last_oldid": 21, "rc_old_len": 100, "rc_new_len": 1300, "rc_minor": 1},
        {"rc_id": 11, "rc_timestamp": ts(NOW - dt.timedelta(hours=2)), "rc_actor": 1202, "rc_namespace": 2,
         "rc_title": "Neuling2/Entwurf", "rc_comment_id": 2, "rc_source": "mw.new", "rc_this_oldid": 30,
         "rc_new_len": 50},
        {"rc_id": 12, "rc_timestamp": ts(NOW - dt.timedelta(hours=3)), "rc_actor": 1201, "rc_namespace": 0,
         "rc_title": "Alter_Artikel", "rc_comment_id": 2, "rc_source": "mw.log", "rc_log_type": "move",
         "rc_params": move_params},
        {"rc_id": 13, "rc_timestamp": ts(NOW - dt.timedelta(hours=4)), "rc_actor": 1201, "rc_namespace": 14,
         "rc_title": "Irgendwas", "rc_comment_id": 2, "rc_source": "mw.categorize"},
        {"rc_id": 14, "rc_timestamp": ts(NOW - dt.timedelta(hours=5)), "rc_actor": 1101, "rc_namespace": 0,
         "rc_title": "Mentorenartikel", "rc_comment_id": 2, "rc_source": "mw.edit"},
    ])


@pytest.fixture
def databases():
    settings = db_settings()
    if not settings:
        pytest.skip("no test database configured")
    conn = _raw_connect(settings)
    with conn.cursor() as cur:
        for name in (settings["mp_db"], settings["wiki_db"]):
            cur.execute(f"DROP DATABASE IF EXISTS `{name}`")
            cur.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4")
    conn.close()

    mp = _raw_connect(settings, settings["mp_db"])
    run_sql_file(mp, ROOT / "sql" / "000_initial_schema.sql")
    with mp.cursor() as cur:
        _mp_legacy_data(cur)
    for migration in sorted((ROOT / "sql" / "migrations").glob("[0-9][0-9][0-9]_*.sql")):
        if not migration.name.endswith(".rollback.sql"):
            run_sql_file(mp, migration)

    wiki = _raw_connect(settings, settings["wiki_db"])
    run_sql_file(wiki, ROOT / "tests" / "fixtures" / "wiki_schema.sql")
    with wiki.cursor() as cur:
        _wiki_data(cur)
    yield {"settings": settings, "mp": mp, "wiki": wiki}
    mp.close()
    wiki.close()


@pytest.fixture
def app(databases):
    s = databases["settings"]
    return create_app({
        "TESTING": True,
        "SECRET_KEY": "test",
        "SESSION_COOKIE_SECURE": False,
        "MP_DB_HOST": s["host"], "WIKI_DB_HOST": s["host"], "DB_PORT": s["port"],
        "MP_DB_NAME": s["mp_db"], "WIKI_DB_NAME": s["wiki_db"],
        "DB_USER": s["user"], "DB_PASSWORD": s["password"],
    })


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def offline_client():
    """App without any reachable database (connections are refused at once)."""
    app = create_app({"TESTING": True, "MP_DB_HOST": "127.0.0.1", "WIKI_DB_HOST": "127.0.0.1",
                      "DB_PORT": 9, "DB_USER": "x", "DB_PASSWORD": "x"})
    return app.test_client()


@pytest.fixture
def mp_db(databases):
    return databases["mp"]


def csrf_from(response):
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
    assert match, "no CSRF token in page"
    return match.group(1)


@pytest.fixture
def login(client):
    def do_login(user="Alice", password=ALICE_PASSWORD):
        token = csrf_from(client.get("/anmelden"))
        return client.post("/anmelden", data={"user": user, "password": password, "csrf_token": token})
    return do_login


@pytest.fixture
def logged_in(client, login):
    response = login()
    assert response.status_code == 302
    return client
