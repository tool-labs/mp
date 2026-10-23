"""Integration tests against MariaDB (skipped without MP_TEST_DB_HOST)."""
import datetime as dt

import pytest
from conftest import ALICE_PASSWORD, NOW, csrf_from
from mpweb import auth, jobs
from mpweb.db import connect
from mpweb.repository import MPRepository
from mpweb.wiki import WikiRepository

pytestmark = pytest.mark.db


def query(conn, sql, args=None):
    with conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall()


def text(response):
    return response.get_data(as_text=True)


def repos(databases):
    s = databases["settings"]
    mp = MPRepository(connect(s["host"], s["mp_db"], s["user"], s["password"], s["port"]))
    wiki = WikiRepository(connect(s["host"], s["wiki_db"], s["user"], s["password"], s["port"]))
    return mp, wiki


# ------------------------------------------------------------------ migration

def test_migration_moves_passwords_out_of_mentor(mp_db):
    rows = query(mp_db, "SELECT mentor_login_password, mentor_pw_salt, mentor_lastupdate FROM mentor "
                        "WHERE mentor_user_id = 101")
    assert rows[0]["mentor_login_password"] is None and rows[0]["mentor_pw_salt"] is None
    assert rows[0]["mentor_lastupdate"] == dt.datetime(2020, 2, 2, 2, 2, 2)   # untouched
    auth_rows = query(mp_db, "SELECT * FROM mentor_auth")
    assert [r["ma_mentor_id"] for r in auth_rows] == [101]
    assert auth_rows[0]["ma_legacy_hash"] and auth_rows[0]["ma_password_hash"] is None
    assert query(mp_db, "SELECT version FROM schema_migrations") == [{"version": 1}]


def test_migration_keeps_bot_tables_myisam(mp_db):
    engines = {r["TABLE_NAME"]: r["ENGINE"] for r in query(mp_db, """
        SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()""")}
    for table in ("mentor", "mentee", "mentee_mentor"):
        assert engines[table] == "MyISAM", table
    assert engines["comentors"] == engines["logging"] == engines["mentor_auth"] == "InnoDB"


def test_bot_api_still_works(databases, tmp_path, monkeypatch):
    """Run the unchanged pyapi/dewpmp.py (used by SpBot's mp-helper.py) on the migrated schema."""
    import sys

    from conftest import ROOT
    s = databases["settings"]
    if s["port"] != 3306:
        pytest.skip("dewpmp.py only supports port 3306")
    cnf = tmp_path / "replica.mp-db.cnf"
    cnf.write_text(f"[client]\nuser={s['user']}\npassword={s['password']}\nhost={s['host']}\n"
                   f"database={s['mp_db']}\nwp_host={s['host']}\n")
    monkeypatch.syspath_prepend(str(ROOT / "pyapi"))
    import mp_db_config
    monkeypatch.setattr(mp_db_config, "db_conf_file", str(cnf))
    import dewpmp

    bot = dewpmp.Database(wp_database=s["wiki_db"])
    assert {m["user_name"] for m in bot.get_all_mentors()} == {"Alice", "Bob", "Carol", "Dave"}
    assert {m["mentee_user_name"] for m in bot.get_all_mentees()} == {"Neuling1", "Neuling2", "Alt Neuling"}
    assert {m["item"] for m in bot.get_mw_cat_members("Benutzer:Mentee")} == \
        {"Neuling1", "Neuling2", "Alt_Neuling", "Neu_Mentee"}
    bot.add_mentee("Bob", "Neu Mentee", mentoring_type=1)
    bot.stop_all_current_mentoring(204)
    assert bot.get_overall_mentee_number() == 5
    bot.conn.close()   # the bot never commits; MyISAM must keep the writes anyway

    mp = databases["mp"]
    rows = query(mp, "SELECT mm_mentor_id, mm_stop, mm_type FROM mentee_mentor WHERE mm_mentee_id = 300")
    assert rows == [{"mm_mentor_id": 102, "mm_stop": None, "mm_type": 1}]
    assert query(mp, "SELECT mm_stop IS NOT NULL AS stopped FROM mentee_mentor WHERE mm_mentee_id = 204") == \
        [{"stopped": 1}]
    del sys.modules["dewpmp"]


# ------------------------------------------------------------------ public pages

def test_all_public_pages(client):
    for path in ("/", "/info", "/mentoren", "/mentoren?ehemalige=1", "/mentor/101", "/mentee/201",
                 "/mentees", "/mentees/aenderungen", "/wartung", "/wartung/ex-mentoren",
                 "/wartung/aufnahmetyp", "/wartung/kurze-betreuungen", "/wartung/verlauf",
                 "/statistik", "/log", "/suche", "/suche?q=xyz"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert "Traceback" not in text(response)


def test_sidebar_counts(client):
    body = text(client.get("/info"))
    # DB: 3 active mentorings, 3 active mentors (Alice, Bob, Dave); WP: 4 mentees, 2 mentors
    assert '<td class="num">3</td>\n            <td class="num">4</td>' in body
    assert '<td class="num">3</td>\n            <td class="num">2</td>' in body


def test_mentor_list(client):
    body = text(client.get("/mentoren"))
    assert "Alice" in body and "Bob" in body and "Dave" in body and "Carol" not in body
    assert "Carol" in text(client.get("/mentoren?ehemalige=1"))
    assert "OoM" in body and "Bronze" in body


def test_mentor_page(client, mp_db):
    query(mp_db, "INSERT INTO comentors VALUES (101, 102)")
    body = text(client.get("/mentor/101"))
    assert "Mentor <em>Alice</em>" in body
    assert "Erfahren &lt;b&gt;!&lt;/b&gt;" in body   # escaped remark
    assert "Neuling1" in body and "Neuling2" in body
    assert "aktiv" in body
    assert "/mentor/102" in body                        # co-mentor link
    assert "Mentor bearbeiten" not in body              # not logged in
    assert "bereits" not in body
    assert client.get("/mentor/999").status_code == 404


def test_former_mentor_with_active_mentees_warning(client, mp_db):
    query(mp_db, "UPDATE mentor SET mentor_out = '2026-01-01' WHERE mentor_user_id = 102")
    assert "Es gibt noch betreute Mentees!" in text(client.get("/mentor/102"))


def test_mentee_page(client):
    body = text(client.get("/mentee/202"))
    assert "Mentee <em>Neuling2</em>" in body
    assert "Mentoren" in body and "/mentor/101" in body and "/mentor/102" in body
    assert "2.020" in body                              # edit count 202 * 10
    assert "noch in Betreuung" in body
    finished = text(client.get("/mentee/203"))
    assert "01.02.2014" in finished
    assert client.get("/mentee/999").status_code == 404


def test_mentees_status(client):
    body = text(client.get("/mentees"))
    assert 'class="status-ok"><a href="/mentee/201"' in body
    assert 'class="status-critical"><a href="/mentee/204"' in body
    assert "Kurz" not in body


def test_recent_changes_job_and_page(client, databases):
    mp, wiki = repos(databases)
    inserted, deleted = jobs.update_recent_changes(mp, wiki)
    assert (inserted, deleted) == (3, 1)
    assert jobs.update_recent_changes(mp, wiki) == (0, 0)     # idempotent
    rows = query(databases["mp"], "SELECT rc_id, rc_new, rc_type FROM mentees_recentchanges ORDER BY rc_id")
    assert rows == [{"rc_id": 10, "rc_new": 0, "rc_type": 0}, {"rc_id": 11, "rc_new": 1, "rc_type": 1},
                    {"rc_id": 12, "rc_new": 0, "rc_type": 3}]
    body = text(client.get("/mentees/aenderungen"))
    assert "3 Änderungen" in body
    assert "Testartikel" in body and "Neuling2/Entwurf" in body
    assert "verschob die Seite" in body and "Neuer Artikel" in body
    assert "&lt;script&gt;" in body and "<script>" not in body.split("</header>")[1]
    assert "(+1.200)" in body
    paged = text(client.get("/mentees/aenderungen?limit=1"))
    assert "1 Änderungen" in paged and "frühere Änderungen" in paged
    assert client.get("/mentees/aenderungen?end_time=kaputt").status_code == 400


def test_maintenance_pages(client):
    assert "/mentor/104" in text(client.get("/wartung/ex-mentoren"))        # Dave not in category
    assert "/mentor/101\"" not in text(client.get("/wartung/ex-mentoren"))
    unset = text(client.get("/wartung/aufnahmetyp"))
    assert "Kurz" in unset and "Neuling2" in unset and "Neuling1" not in unset
    short = text(client.get("/wartung/kurze-betreuungen"))
    assert "Kurz" in short and "02:00:00" in short
    history = text(client.get("/wartung/verlauf?limit=2"))
    assert "2 Ereignisse" in history and "frühere Ereignisse" in history
    old = text(client.get("/wartung/verlauf?end_time=2014-12-31"))
    assert "Kurz" in old and "Neuling1" not in old
    assert client.get("/wartung/verlauf?end_time=gestern").status_code == 400


def test_stats(client):
    body = text(client.get("/statistik"))
    assert "<svg" in body
    assert "4</strong> Benutzer" in body
    assert "Abweichung" in body
    assert str(NOW.year) in body


def test_search(client):
    response = client.get("/suche?q=Alice")
    assert response.status_code == 302 and response.headers["Location"] == "/mentor/101"
    response = client.get("/suche?q=Kurz")
    assert response.headers["Location"] == "/mentee/203"
    body = text(client.get("/suche?q=^Neu"))
    assert "Neuling1" in body and "Neuling2" in body
    body = text(client.get("/suche?q=^Neu&s=1&inactive=on"))     # only finished mentees
    assert "Keine Treffer" in body
    body = text(client.get("/suche?q=(&where=mentee"))
    assert "Ungültiger regulärer Ausdruck" in body
    assert client.get("/suche?q=Carol&where=mentor&s=1&active=on").status_code == 200   # not redirected


def test_api(client):
    mentors = client.get("/api/mentors").get_json()
    assert {m["name"] for m in mentors} == {"Alice", "Bob", "Dave"}
    alice = next(m for m in mentors if m["name"] == "Alice")
    assert alice["active_mentees"] == 2 and alice["award_level"] == 1
    mentees = client.get("/api/mentees").get_json()
    assert {m["name"] for m in mentees} == {"Neuling1", "Neuling2", "Alt Neuling"}
    assert client.get("/api/suggest?q=Neu&where=mentee").get_json() == ["Neuling1", "Neuling2"]
    assert client.get("/api/suggest?q=Al").get_json() == ["Alice", "Alt Neuling"]
    xml = text(client.get("/api/list_mentees.php"))
    assert "<name>Kurz</name>" in xml and "<mentor_id>103</mentor_id>" in xml
    assert "<name>Carol</name>" in text(client.get("/api/list_mentors.php"))


# ------------------------------------------------------------------ login & editing

def test_login_upgrades_legacy_hash(client, login, mp_db):
    assert login(password="falsch").status_code == 200
    response = login()
    assert response.status_code == 302
    row = query(mp_db, "SELECT * FROM mentor_auth WHERE ma_mentor_id = 101")[0]
    assert row["ma_legacy_hash"] is None and row["ma_password_hash"].startswith(("scrypt:", "pbkdf2:"))
    body = text(client.get("/mentor/101"))
    assert "Mentor bearbeiten" in body
    client.post("/abmelden", data={"csrf_token": csrf_from(client.get("/info"))})
    assert login().status_code == 302                       # new hash works too


def test_unknown_user_or_without_password_cannot_login(login):
    assert login(user="Bob").status_code == 200
    assert login(user="Niemand").status_code == 200


def test_login_redirects_to_next(client):
    token = csrf_from(client.get("/anmelden"))
    response = client.post("/anmelden?next=/mentor/102", data={"user": "Alice", "password": ALICE_PASSWORD,
                                                               "csrf_token": token})
    assert response.headers["Location"] == "/mentor/102"
    token = csrf_from(client.get("/info"))
    client.post("/abmelden", data={"csrf_token": token})
    token = csrf_from(client.get("/anmelden"))
    response = client.post("/anmelden?next=//evil.example", data={"user": "Alice", "password": ALICE_PASSWORD,
                                                                  "csrf_token": token})
    assert response.headers["Location"] == "/"


def test_change_password(logged_in, mp_db):
    token = csrf_from(logged_in.get("/passwort"))
    assert "zu kurz" not in text(logged_in.post("/passwort", data={
        "current": "falsch", "new": "neuespasswort", "repeat": "neuespasswort", "csrf_token": token}))
    response = logged_in.post("/passwort", data={"current": ALICE_PASSWORD, "new": "kurz", "repeat": "kurz",
                                                 "csrf_token": token})
    assert "mindestens 8 Zeichen" in text(response)
    response = logged_in.post("/passwort", data={"current": ALICE_PASSWORD, "new": "neuespasswort",
                                                 "repeat": "neuespasswort", "csrf_token": token})
    assert response.status_code == 302
    row = query(mp_db, "SELECT ma_password_hash FROM mentor_auth WHERE ma_mentor_id = 101")[0]
    assert auth.verify_password(row, "neuespasswort") == (True, False)
    assert query(mp_db, "SELECT log_type FROM logging ORDER BY log_id DESC LIMIT 1")[0]["log_type"] == "change_password"


def test_edit_mentor(logged_in, mp_db):
    page = logged_in.get("/mentor/102/bearbeiten")
    token = csrf_from(page)
    bad = logged_in.post("/mentor/102/bearbeiten", data={"user_name": "Bob", "date_in": "2012-13-01",
                                                         "award": "0", "csrf_token": token})
    assert "Ungültiges Datum" in text(bad)
    response = logged_in.post("/mentor/102/bearbeiten", data={
        "user_name": "Bob", "date_in": "2012-03-04", "date_out": "2026-10-01", "barnstar": "1",
        "award": "3", "remark": "Neu", "csrf_token": token})
    assert response.status_code == 302
    row = query(mp_db, "SELECT * FROM mentor WHERE mentor_user_id = 102")[0]
    assert (row["mentor_out"], row["mentor_award_level"], row["mentor_has_barnstar"], row["mentor_remark"]) == \
        (dt.date(2026, 10, 1), 3, 1, "Neu")
    log = query(mp_db, "SELECT * FROM logging ORDER BY log_id DESC LIMIT 1")[0]
    assert (log["log_user_name"], log["log_type"], log["log_target"]) == ("Alice", "update_mentor", 102)


def test_edit_mentee(logged_in, mp_db):
    token = csrf_from(logged_in.get("/mentee/201/bearbeiten"))
    response = logged_in.post("/mentee/201/bearbeiten", data={"user_name": "Neuling1", "remark": "Hallo",
                                                              "csrf_token": token})
    assert response.status_code == 302
    assert query(mp_db, "SELECT mentee_remark FROM mentee WHERE mentee_user_id = 201")[0]["mentee_remark"] == "Hallo"


def test_relation_edit_flow(logged_in, mp_db):
    # several relations for mentee 202 -> choice page
    assert "Betreuung auswählen" in text(logged_in.get("/betreuung?mentee_id=202"))
    page = logged_in.get("/betreuung?mentee_id=201&mentor_id=101")
    body = text(page)
    assert "Betreuung bearbeiten" in body and "MP: Mentor übernommen" in body and 'class="highlight"' in body
    token = csrf_from(page)
    start = (NOW - dt.timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S")
    url = f"/betreuung?mentee_id=201&mentor_id=101&start={start}"
    bad = logged_in.post(url, data={"mentor_id": "101", "start": start, "stop": "2000-01-01 00:00:00",
                                    "mm_type": "1", "csrf_token": token})
    assert "Das Ende liegt vor dem Beginn" in text(bad)
    stop = NOW.strftime("%Y-%m-%d %H:%M:%S")
    response = logged_in.post(url, data={"mentor_id": "101", "start": start, "stop": stop, "mm_type": "1",
                                         "csrf_token": token})
    assert response.status_code == 302
    row = query(mp_db, "SELECT mm_stop, mm_type FROM mentee_mentor WHERE mm_mentee_id = 201")[0]
    assert row == {"mm_stop": NOW, "mm_type": 1}

    # unchanged save is not a conflict
    response = logged_in.post(url, data={"mentor_id": "101", "start": start, "stop": stop, "mm_type": "1",
                                         "csrf_token": token})
    assert response.status_code == 302

    # create a new relation and delete it again
    new = logged_in.get("/betreuung/neu?mentee_id=201")
    assert "Neue Betreuung" in text(new)
    response = logged_in.post("/betreuung/neu?mentee_id=201", data={
        "mentor_id": "102", "start": stop, "stop": "", "mm_type": "2", "csrf_token": token})
    assert response.status_code == 302
    duplicate = logged_in.post("/betreuung/neu?mentee_id=201", data={
        "mentor_id": "102", "start": stop, "stop": "", "mm_type": "2", "csrf_token": token})
    assert "bereits eine Betreuung" in text(duplicate)
    assert len(query(mp_db, "SELECT * FROM mentee_mentor WHERE mm_mentee_id = 201")) == 2
    response = logged_in.post("/betreuung/loeschen", data={"mentee_id": "201", "mentor_id": "102", "start": stop,
                                                           "csrf_token": token})
    assert response.status_code == 302
    assert len(query(mp_db, "SELECT * FROM mentee_mentor WHERE mm_mentee_id = 201")) == 1
    assert logged_in.post("/betreuung/loeschen", data={"mentee_id": "201", "mentor_id": "102", "start": stop,
                                                       "csrf_token": token}).status_code == 404
    types = [r["log_type"] for r in query(mp_db, "SELECT log_type FROM logging ORDER BY log_id")]
    assert types[-4:] == ["update_menteementor", "update_menteementor", "add_menteementor", "delete_mm"]


def test_relation_invalid_mentor(logged_in):
    page = logged_in.get("/betreuung/neu?mentee_id=201")
    response = logged_in.post("/betreuung/neu?mentee_id=201", data={
        "mentor_id": "999", "start": "2024-01-01 00:00:00", "mm_type": "1", "csrf_token": csrf_from(page)})
    assert "gültigen Mentor" in text(response)
    assert logged_in.get("/betreuung/neu?mentee_id=999").status_code == 404
    assert logged_in.get("/betreuung?mentee_id=201&start=kaputt").status_code == 400


# ------------------------------------------------------------------ co-mentor job

def test_refresh_comentors(databases):
    mp, _ = repos(databases)
    text_ = """{{Mentor|Mentor=Alice|Pause=ja|Co-Mentor1=Bob|Co-Mentor2=Unbekannt}}
               {{Mentor|Mentor=Bob|Co-Mentor1=Alice|Co-Mentor2=Dave}}"""
    assert jobs.refresh_comentors(mp, fetch=lambda: (7, text_)) is True
    assert jobs.refresh_comentors(mp, fetch=lambda: (7, text_)) is False      # same revision
    conn = databases["mp"]
    assert query(conn, "SELECT co_mentor_id, co_comentor_id FROM comentors ORDER BY 1, 2") == [
        {"co_mentor_id": 101, "co_comentor_id": 102}, {"co_mentor_id": 102, "co_comentor_id": 101},
        {"co_mentor_id": 102, "co_comentor_id": 104}]
    assert query(conn, "SELECT mentor_user_id FROM mentor WHERE mentor_pause = 1") == [{"mentor_user_id": 101}]
    assert jobs.refresh_comentors(mp, fetch=lambda: (8, "{{Mentor|Mentor=Bob}}")) is True
    assert query(conn, "SELECT COUNT(*) AS n FROM comentors") == [{"n": 0}]
    assert query(conn, "SELECT COUNT(*) AS n FROM mentor WHERE mentor_pause = 1") == [{"n": 0}]
