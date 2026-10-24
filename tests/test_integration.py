"""Integration tests against MariaDB (skipped without MP_TEST_DB_HOST)."""
import datetime as dt

import pytest
from conftest import ALICE_PASSWORD, NOW, csrf_from
from mpweb import auth, jobs, sync
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
    assert query(mp_db, "SELECT version FROM schema_migrations ORDER BY 1") == [{"version": 1}, {"version": 2}]


def test_migration_converts_bot_tables_to_innodb(mp_db):
    tables = {r["TABLE_NAME"]: r for r in query(mp_db, """
        SELECT TABLE_NAME, ENGINE, TABLE_COLLATION FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE()""")}
    for table in ("mentor", "mentee", "mentee_mentor", "comentors", "logging", "mentor_auth"):
        assert tables[table]["ENGINE"] == "InnoDB", table
    for table in ("mentor", "mentee", "mentee_mentor"):
        assert tables[table]["TABLE_COLLATION"] == "utf8mb4_unicode_ci", table


def test_mentee_names_with_4_byte_characters(databases):
    mp, _ = repos(databases)
    assert mp.ensure_mentee(999, "Neuling 🙂") == "new"
    assert query(databases["mp"], "SELECT mentee_user_name FROM mentee WHERE mentee_user_id = 999") == \
        [{"mentee_user_name": "Neuling 🙂"}]


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


# ------------------------------------------------------------------ mentee sync job and API v1 (SpBot)

def test_sync_mentees(databases):
    mp, wiki = repos(databases)
    with databases["wiki"].cursor() as cur:      # Alt Neuling (204) left the category
        cur.execute("DELETE FROM categorylinks WHERE cl_from = 5204")
    pages = {"Benutzer:Neu Mentee": {"text": "#WEITERLEITUNG [[en:User:Neu Mentee]]\n"
                                             "{{WP:Mentorenprogramm/Hinweis Mentorat|Mentor=Dave}}",
                                     "redirect": "en:User:Neu Mentee", "target_text": None}}
    now = NOW.replace(microsecond=0)
    result = sync.sync_mentees(mp, wiki, fetch=lambda titles: {t: pages.get(t) for t in titles}, now=now)
    assert result.started == [("Neu Mentee", "Dave")] and result.stopped == [("Alt Neuling", "Bob")]
    assert result.skipped == [] and result.reopened == []

    conn = databases["mp"]
    assert query(conn, "SELECT mm_mentor_id, mm_start, mm_stop, mm_type FROM mentee_mentor "
                       "WHERE mm_mentee_id = 300") == [{"mm_mentor_id": 104, "mm_start": now, "mm_stop": None,
                                                        "mm_type": 0}]
    assert query(conn, "SELECT mm_stop FROM mentee_mentor WHERE mm_mentee_id = 204") == [{"mm_stop": now}]
    assert query(conn, "SELECT mentee_user_name FROM mentee WHERE mentee_user_id = 300") == \
        [{"mentee_user_name": "Neu Mentee"}]
    assert {r["log_type"] for r in query(conn, "SELECT log_type FROM logging WHERE log_user_name = %s",
                                         (sync.LOG_USER,))} == {"sync_start", "sync_stop"}

    # Alt Neuling is back within 24 hours with the same mentor: the mentoring is re-opened
    with databases["wiki"].cursor() as cur:
        cur.execute("INSERT INTO categorylinks (cl_from, cl_target_id) VALUES (5204, 2)")
    pages["Benutzer:Alt Neuling"] = {"text": "{{X|Mentor=Bob}}", "redirect": None, "target_text": None}
    result = sync.sync_mentees(mp, wiki, fetch=lambda titles: {t: pages.get(t) for t in titles},
                               now=now + dt.timedelta(hours=1))
    assert result.reopened == [("Alt Neuling", "Bob")] and result.started == result.stopped == []
    assert query(conn, "SELECT mm_stop FROM mentee_mentor WHERE mm_mentee_id = 204") == [{"mm_stop": None}]
    assert sync.sync_mentees(mp, wiki, fetch=dict, now=now).summary().startswith("0 started, 0 reopened, 0 stopped")


def test_sync_mentees_dry_run(databases):
    mp, wiki = repos(databases)
    result = sync.sync_mentees(mp, wiki, fetch=lambda titles: {}, dry_run=True)
    assert result.skipped == [("Benutzer:Neu Mentee", "Benutzerseite nicht gefunden")]
    assert query(databases["mp"], "SELECT COUNT(*) AS n FROM logging WHERE log_user_name = %s",
                 (sync.LOG_USER,)) == [{"n": 0}]


def test_api_v1(client, databases):
    mentees = client.get("/api/v1/mentees").get_json()
    assert [(m["mentee"], m["mentor"], m["status"]) for m in mentees] == [
        ("Alt Neuling", "Bob", "critical"), ("Neuling1", "Alice", "ok"), ("Neuling2", "Alice", "ok")]
    assert mentees[0]["start"] == "2025-01-01 08:00:00" and mentees[0]["last_edit"] == "2025-02-01 12:00:00"

    archive = client.get("/api/v1/archive/2020/3").get_json()
    assert archive["first_number"] == 2
    assert [(m["mentee"], m["mentor"], m["stop"], m["type"]) for m in archive["mentorings"]] == [
        ("Neuling2", "Bob", "2020-03-01 10:00:00", 1)]
    assert client.get("/api/v1/archive/2014/2").get_json()["first_number"] == 1
    assert client.get("/api/v1/archive/2021/1").get_json() == {"year": 2021, "month": 1, "first_number": 3,
                                                               "mentorings": []}
    assert client.get("/api/v1/archive/2020/13").status_code == 404
    assert client.get("/api/v1/archive/1999/1").status_code == 404

    assert client.get("/api/v1/counts").get_json() == {"mentees_total": 4, "active_mentors": 2,
                                                       "active_mentees": 3}
    assert client.get("/api/v1/sync-status").status_code == 404
    with databases["mp"].cursor() as cur:
        cur.execute("UPDATE mentee SET mentee_is_hidden = 1 WHERE mentee_user_id = 201")
        cur.execute("INSERT INTO mp_meta (meta_key, meta_value) VALUES ('sync_report', '{\"skipped\": []}')")
    assert "Neuling1" not in {m["mentee"] for m in client.get("/api/v1/mentees").get_json()}
    assert client.get("/api/v1/sync-status").get_json() == {"skipped": []}
