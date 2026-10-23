"""Routing tests that do not need a database: legacy redirects and error pages."""
import pytest


@pytest.mark.parametrize("query,location", [
    ("action=", "/"),
    ("action=about", "/info"),
    ("action=index", "/"),
    ("action=mentorlist", "/mentoren"),
    ("action=mentorlist&no_activity_filter=1", "/mentoren?ehemalige=1"),
    ("action=mentorlist&all=1", "/mentoren?ehemalige=1"),
    ("action=list", "/mentoren"),
    ("action=viewmentor&id=12", "/mentor/12"),
    ("action=view&id=12", "/mentor/12"),
    ("action=viewmentee&id=34", "/mentee/34"),
    ("action=mentees", "/mentees"),
    ("action=mentees_rc&end_time=20240101000000&limit=50", "/mentees/aenderungen?end_time=20240101000000&limit=50"),
    ("action=maintenance", "/wartung"),
    ("action=maintenance_ex_mentor", "/wartung/ex-mentoren"),
    ("action=maintenance_wm", "/wartung/aufnahmetyp"),
    ("action=maintenance_short_mm", "/wartung/kurze-betreuungen"),
    ("action=maintenance_mm_history&end_time=2020-12-31+23:59:59&limit=10",
     "/wartung/verlauf?end_time=2020-12-31+23:59:59&limit=10"),
    ("action=stat", "/statistik"),
    ("action=log", "/log"),
    ("action=login", "/anmelden"),
    ("action=logout", "/"),
    ("action=changepw", "/passwort"),
    ("action=edit&what=mentor&id=5", "/mentor/5/bearbeiten"),
    ("action=edit&what=mentee&id=6", "/mentee/6/bearbeiten"),
    ("action=editmm&mentee_id=6&create=new", "/betreuung/neu?mentee_id=6"),
    ("action=editmm&mentee_id=6&mentor_id=5", "/betreuung?mentee_id=6&mentor_id=5"),
])
def test_legacy_redirects(offline_client, query, location):
    for path in ("/index.php", "/"):
        response = offline_client.get(f"{path}?{query}")
        assert response.status_code == 301, (path, query)
        assert response.headers["Location"] == location


def test_legacy_search_redirect(offline_client):
    response = offline_client.get("/index.php?action=search&search-content=Al&search-where=mentor"
                                  "&search-active=on")
    assert response.status_code == 301
    assert response.headers["Location"] == "/suche?q=Al&where=mentor&s=1&active=on"


@pytest.mark.parametrize("query", ["action=doesnotexist", "action=viewmentor", "action=viewmentee&id=abc",
                                   "action=edit&what=foo&id=1"])
def test_legacy_unknown_gives_404(offline_client, query):
    response = offline_client.get(f"/index.php?{query}")
    assert response.status_code == 404
    assert "Seite nicht gefunden" in response.get_data(as_text=True)


def test_static_pages_render_without_database(offline_client):
    for path in ("/", "/info", "/wartung", "/anmelden"):
        response = offline_client.get(path)
        assert response.status_code == 200, path
        body = response.get_data(as_text=True)
        assert "Mentorenprogramm" in body
        assert "?" in body   # sidebar counts unknown


def test_database_down_gives_503(offline_client):
    response = offline_client.get("/mentoren")
    assert response.status_code == 503
    assert "Datenbank" in response.get_data(as_text=True)


def test_protected_pages_redirect_to_login(offline_client):
    for path in ("/passwort", "/mentor/1/bearbeiten", "/mentee/1/bearbeiten", "/betreuung?mentee_id=1",
                 "/betreuung/neu?mentee_id=1"):
        response = offline_client.get(path)
        assert response.status_code == 302, path
        assert response.headers["Location"].startswith("/anmelden?next=")


def test_post_without_csrf_is_rejected(offline_client):
    assert offline_client.post("/anmelden", data={"user": "a", "password": "b"}).status_code == 400
    assert offline_client.post("/abmelden").status_code == 400


def test_suggest_short_prefix_needs_no_database(offline_client):
    assert offline_client.get("/api/suggest?q=a").get_json() == []


def test_sql_dumps(tmp_path):
    from mpweb import create_app
    for name in ("wpmp-2026-10-20.sql.bz2", "wpmp-2026-10-24.sql.bz2", "wpmp-2026-10-25.sql.bz2", "other.txt"):
        (tmp_path / name).write_bytes(b"BZh" + b"x" * 2048)
    app = create_app({"TESTING": True, "DUMP_DIR": str(tmp_path), "DUMPS_NOT_BEFORE": "2026-10-24",
                      "MP_DB_HOST": "127.0.0.1", "WIKI_DB_HOST": "127.0.0.1", "DB_PORT": 9})
    client = app.test_client()
    body = client.get("/sql-dumps/").get_data(as_text=True)
    assert body.index("wpmp-2026-10-25") < body.index("wpmp-2026-10-24")
    assert "wpmp-2026-10-20" not in body and "other.txt" not in body
    response = client.get("/sql-dumps/wpmp-2026-10-25.sql.bz2")
    assert response.status_code == 200 and response.data.startswith(b"BZh")
    for name in ("wpmp-2026-10-20.sql.bz2", "other.txt", "..%2Fsecret"):
        assert client.get(f"/sql-dumps/{name}").status_code == 404
