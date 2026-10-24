"""Unit tests for the mentee sync (no database: fake repositories and a fake MediaWiki API)."""
import contextlib
import datetime as dt
import io
import json
import urllib.parse

import pymysql
import pytest
from mpweb import sync

NOW = dt.datetime(2026, 10, 24, 12, 0, 0)

LINGOLINK = ("#WEITERLEITUNG [[en:User:LingoLink]]\n\n"
             "{{WP:Mentorenprogramm/Hinweis Mentorat |Mentor=AsepTisch}}\n\nich will …")


# ------------------------------------------------------------------ find_mentor

@pytest.mark.parametrize("text,expected", [
    ("{{WP:Mentorenprogramm/Hinweis Mentorat|Mentor=Alice}}", "Alice"),
    ("{{Wikipedia:Mentorenprogramm/Hinweis_Mentorat | Mentor = bob_der_baumeister }}", "Bob der baumeister"),
    ("{{Benutzer:Mentee|Mentor=Carol|Seit=2026}}", "Carol"),
    ("{{X|Mentor=[[Benutzer:Dave|Dave]]}}", "Dave"),
    ("{{X|Mentor=Benutzerin:Eve}}", "Eve"),
    (LINGOLINK, "AsepTisch"),
    ("<!-- {{X|Mentor=Alt}} -->{{X|Mentor=Neu}}", "Neu"),
    ("{{X|Mentor=}}", None), ("kein Mentor", None), ("", None), (None, None),
])
def test_find_mentor(text, expected):
    assert sync.find_mentor(text) == expected


# ------------------------------------------------------------------ fetch_user_pages

class FakeApi:
    """Answers like api.php for a small set of pages (``Benutzer`` → ``Benutzerin`` like for LingoLink)."""

    def __init__(self, pages):
        self.pages = pages          # actual title -> {"text", "redirect": target or None, "iw": bool}
        self.requests = []

    def __call__(self, request, timeout):
        params = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(request.full_url).query))
        self.requests.append(params)
        follow = "redirects" in params
        query = {"normalized": [], "pages": [], "redirects": []}
        for title in params["titles"].split("|"):
            actual = title.replace("Benutzer:LingoLink", "Benutzerin:LingoLink")
            if actual != title:
                query["normalized"].append({"from": title, "to": actual})
            page = self.pages.get(actual)
            if page and follow and page.get("redirect"):
                target = page["redirect"]
                query["redirects"].append({"from": actual, "to": target, **({"tointerwiki": "en"} if page.get("iw")
                                                                         else {})})
                if page.get("iw"):
                    continue
                actual, page = target, self.pages.get(target)
            if page is None:
                query["pages"].append({"ns": 2, "title": actual, "missing": True})
                continue
            entry = {"ns": 2, "title": actual, "revisions": [{"slots": {"main": {"content": page["text"]}}}]}
            if page.get("redirect"):
                entry["redirect"] = True
            query["pages"].append(entry)
        return io.BytesIO(json.dumps({"batchcomplete": True, "query": query}).encode())


def test_fetch_user_pages_redirects():
    api = FakeApi({
        "Benutzerin:LingoLink": {"text": LINGOLINK, "redirect": "en:User:LingoLink", "iw": True},
        "Benutzer:Normal": {"text": "{{X|Mentor=Alice}}"},
        "Benutzer:Umgeleitet": {"text": "#WEITERLEITUNG [[Benutzer:Umgeleitet/Start]]",
                                "redirect": "Benutzer:Umgeleitet/Start"},
        "Benutzer:Umgeleitet/Start": {"text": "{{X|Mentor=Bob}}"},
    })
    pages = sync.fetch_user_pages(["Benutzer:LingoLink", "Benutzer:Normal", "Benutzer:Umgeleitet",
                                   "Benutzer:Fehlt"], opener=api)
    assert pages["Benutzer:LingoLink"] == {"text": LINGOLINK, "redirect": "en:User:LingoLink", "target_text": None}
    assert pages["Benutzer:Normal"]["redirect"] is None
    assert pages["Benutzer:Umgeleitet"]["redirect"] == "Benutzer:Umgeleitet/Start"
    assert pages["Benutzer:Umgeleitet"]["target_text"] == "{{X|Mentor=Bob}}"
    assert pages["Benutzer:Fehlt"] is None
    assert len(api.requests) == 2      # one batch + one for the redirect targets
    assert "redirects" not in api.requests[0]


# ------------------------------------------------------------------ plan

def row(mentee_id, mentee, mentor_id=101, mentor="Alice"):
    return {"mentee_user_id": mentee_id, "mentee_user_name": mentee, "mm_start": NOW - dt.timedelta(days=5),
            "mentor_user_id": mentor_id, "mentor_user_name": mentor}


def test_plan():
    members = {"Bleibt": 1, "Neu": 2, "Umbenannt Neu": 3}
    running = [row(1, "Bleibt"), row(3, "Umbenannt Alt"), row(4, "Weg"), row(4, "Weg", 102, "Bob")]
    new, stop, renames = sync.plan(members, running)
    assert new == ["Neu"]
    assert [(r["mentee_user_id"], r["mentor_user_name"]) for r in stop] == [(4, "Alice"), (4, "Bob")]
    assert renames == [(3, "Umbenannt Alt", "Umbenannt Neu")]


# ------------------------------------------------------------------ sync with fake repositories

class FakeWiki:
    def __init__(self, members, users):
        self.members, self.users = set(members), users

    def category_user_names(self, category):
        assert category == "Benutzer:Mentee"
        return set(self.members)

    def user_ids(self, names):
        return {n: self.users[n] for n in names if n in self.users}


class FakeMP:
    def __init__(self, relations, mentees, mentors, fail_insert_for=()):
        self.relations = relations          # dicts: mentor_id, mentee_id, start, stop
        self.mentees, self.mentors = mentees, mentors   # id -> name
        self.logs, self.meta, self.fail_insert_for = [], {}, set(fail_insert_for)
        self.locked = False

    @contextlib.contextmanager
    def transaction(self):
        yield

    def acquire_lock(self, name, timeout=0):
        if self.locked:
            return False
        self.locked = True
        return True

    def release_lock(self, name):
        self.locked = False

    def sync_mentorings(self):
        return [row(r["mentee_id"], self.mentees[r["mentee_id"]], r["mentor_id"], self.mentors[r["mentor_id"]])
                for r in self.relations if r["stop"] is None]

    def ensure_mentor(self, mentor_id, name, today):
        self.mentors[mentor_id] = name

    def ensure_mentee(self, mentee_id, name):
        if mentee_id in self.fail_insert_for:
            raise pymysql.err.DataError(1366, "Incorrect string value")
        self.mentees[mentee_id] = name

    def rename_mentee(self, mentee_id, name):
        self.mentees[mentee_id] = name

    def last_stopped_relation(self, mentee_id, since):
        stopped = [r for r in self.relations if r["mentee_id"] == mentee_id and r["stop"] and r["stop"] >= since]
        if not stopped:
            return None
        r = max(stopped, key=lambda r: r["stop"])
        return {"mm_mentor_id": r["mentor_id"], "mm_mentee_id": mentee_id, "mm_start": r["start"],
                "mm_stop": r["stop"]}

    def reopen_relation(self, mentor_id, mentee_id, start):
        for r in self.relations:
            if (r["mentor_id"], r["mentee_id"], r["start"]) == (mentor_id, mentee_id, start):
                r["stop"] = None

    def stop_mentorings(self, mentee_id, stop):
        for r in self.relations:
            if r["mentee_id"] == mentee_id and r["stop"] is None:
                r["stop"] = stop

    def add_relation(self, mentor_id, mentee_id, start, stop, mm_type):
        self.relations.append({"mentor_id": mentor_id, "mentee_id": mentee_id, "start": start, "stop": stop})

    def log(self, user, comment, action, target=0):
        self.logs.append((user, action, target))

    def set_meta(self, key, value):
        self.meta[key] = value


USERS = {"Alice": 101, "Bob": 102, "AsepTisch": 103, "Bleibt": 1, "Weg": 4, "LingoLink": 5323869,
         "Ohne Vorlage": 6, "Zurück": 7, "Wechsel": 8, "Emoji": 9, "Unbekannter Mentor": 10}

PAGES = {
    "Benutzer:LingoLink": {"text": LINGOLINK, "redirect": "en:User:LingoLink", "target_text": None},
    "Benutzer:Ohne Vorlage": {"text": "Hallo", "redirect": None, "target_text": None},
    "Benutzer:Zurück": {"text": "{{X|Mentor=Alice}}", "redirect": None, "target_text": None},
    "Benutzer:Wechsel": {"text": "{{X|Mentor=Bob}}", "redirect": None, "target_text": None},
    "Benutzer:Emoji": {"text": "{{X|Mentor=Alice}}", "redirect": None, "target_text": None},
    "Benutzer:Unbekannter Mentor": {"text": "{{X|Mentor=Niemand}}", "redirect": None, "target_text": None},
}


def scenario():
    old = NOW - dt.timedelta(days=30)
    recently = NOW - dt.timedelta(hours=3)
    mp = FakeMP(
        relations=[
            {"mentor_id": 101, "mentee_id": 1, "start": old, "stop": None},
            {"mentor_id": 102, "mentee_id": 4, "start": old, "stop": None},
            {"mentor_id": 101, "mentee_id": 7, "start": old, "stop": recently},    # same mentor → reopen
            {"mentor_id": 101, "mentee_id": 8, "start": old, "stop": recently},    # now Bob → new mentoring
        ],
        mentees={1: "Bleibt", 4: "Weg", 7: "Zurück", 8: "Wechsel"},
        mentors={101: "Alice", 102: "Bob"},
        fail_insert_for={9})
    wiki = FakeWiki(["Bleibt", "LingoLink", "Ohne Vorlage", "Zurück", "Wechsel", "Emoji", "Unbekannter Mentor",
                     "Bleibt/Entwurf", "Gelöscht"], USERS)
    return mp, wiki


def test_sync_mentees():
    mp, wiki = scenario()
    result = sync.sync_mentees(mp, wiki, fetch=lambda titles: {t: PAGES.get(t) for t in titles}, now=NOW)

    assert result.started == [("LingoLink", "AsepTisch"), ("Wechsel", "Bob")]
    assert result.reopened == [("Zurück", "Alice")]
    assert result.stopped == [("Weg", "Bob")]
    reasons = dict(result.skipped)
    assert set(reasons) == {"Benutzer:Bleibt/Entwurf", "Benutzer:Gelöscht", "Benutzer:Ohne Vorlage",
                            "Benutzer:Unbekannter Mentor", "Benutzer:Emoji"}
    assert "Datenbankfehler" in reasons["Benutzer:Emoji"]

    running = {(r["mentee_id"], r["mentor_id"]) for r in mp.relations if r["stop"] is None}
    assert running == {(1, 101), (5323869, 103), (7, 101), (8, 102)}
    assert mp.mentors[103] == "AsepTisch" and mp.mentees[5323869] == "LingoLink"
    assert [a for _, a, _ in mp.logs].count("sync_start") == 2
    assert json.loads(mp.meta[sync.META_REPORT])["stopped"] == [["Weg", "Bob"]]
    assert not mp.locked


def test_sync_dry_run_changes_nothing():
    mp, wiki = scenario()
    before = [dict(r) for r in mp.relations]
    result = sync.sync_mentees(mp, wiki, fetch=lambda titles: {t: PAGES.get(t) for t in titles},
                               dry_run=True, now=NOW)
    assert result.dry_run and result.stopped == [("Weg", "Bob")] and len(result.started) == 3
    assert mp.relations == before and mp.logs == [] and mp.meta == {}


def test_sync_aborts_on_empty_category_or_too_many_stops(monkeypatch):
    mp, wiki = scenario()
    wiki.members = set()
    with pytest.raises(sync.SyncAborted, match="empty"):
        sync.sync_mentees(mp, wiki, fetch=dict, now=NOW)
    assert not mp.locked

    mp, wiki = scenario()
    monkeypatch.setattr(sync, "MAX_STOPS_PER_RUN", 0)
    with pytest.raises(sync.SyncAborted, match="would be stopped"):
        sync.sync_mentees(mp, wiki, fetch=dict, now=NOW)
    assert all(r["stop"] is None for r in mp.relations[:2])
    result = sync.sync_mentees(mp, wiki, fetch=lambda titles: {}, force=True, now=NOW)
    assert result.stopped == [("Weg", "Bob")]


def test_sync_respects_lock():
    mp, wiki = scenario()
    mp.locked = True
    with pytest.raises(sync.SyncAborted, match="still active"):
        sync.sync_mentees(mp, wiki, fetch=dict, now=NOW)
