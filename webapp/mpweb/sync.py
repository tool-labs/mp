"""Synchronise the mentorings with ``Kategorie:Benutzer:Mentee`` (job ``sync-mentees``).

This replaces the database part of SpBot's ``mp-helper.py``:

* a user page in the category without a running mentoring starts one; the
  mentor is taken from ``{{WP:Mentorenprogramm/Hinweis Mentorat|Mentor=…}}``
  (or any ``|Mentor=``) on the user page. A mentoring with the same mentor that
  was stopped less than 24 hours ago is re-opened instead;
* a running mentoring whose mentee left the category is stopped;
* renamed mentees and mentors are updated (matched by user id).

User pages that are redirects are supported: the template is searched on the
redirect page itself first (e.g. ``#WEITERLEITUNG [[en:User:X]]`` followed by
the template) and then on a local redirect target. Pages that cannot be
processed are skipped and reported instead of stopping the run.
"""
import dataclasses
import datetime as dt
import json
import logging
import re
import urllib.parse
import urllib.request

import pymysql

from .comentors import API_URL, USER_AGENT, normalize_user
from .helpers import utcnow
from .wiki import MENTEE_CATEGORY

log = logging.getLogger(__name__)

LOG_USER = "sync-mentees"
LOCK_NAME = "mp-sync-mentees"
META_REPORT = "sync_report"
REOPEN_WITHIN = dt.timedelta(hours=24)
MAX_STOPS_PER_RUN = 25   # more is most likely a replica problem; override with --force
API_BATCH = 50

# the same patterns as the old bot: any "|Mentor=" first, then the Mentorat template
_MENTOR_PARAM_RE = re.compile(r"\|\s*Mentor\s*=\s*([^\r\n|}]+)")
_MENTORAT_RE = re.compile(r"\{\{\s*(?:WP|Wikipedia)\s*:\s*Mentorenprogramm/Hinweis[ _]Mentorat\s*"
                          r"\|\s*Mentor\s*=\s*([^\r\n|}]+?)\s*\}\}", re.I)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_USER_PREFIX_RE = re.compile(r"^\s*\[*\s*(?:Benutzer(?:in)?|User)\s*:\s*", re.I)


class SyncAborted(RuntimeError):
    """The run was stopped before changing anything."""


@dataclasses.dataclass
class SyncResult:
    started: list = dataclasses.field(default_factory=list)    # (mentee, mentor)
    reopened: list = dataclasses.field(default_factory=list)   # (mentee, mentor)
    stopped: list = dataclasses.field(default_factory=list)    # (mentee, mentor)
    renamed: list = dataclasses.field(default_factory=list)    # (old name, new name)
    skipped: list = dataclasses.field(default_factory=list)    # (page/user, reason)
    dry_run: bool = False

    def as_dict(self):
        return {key: [list(item) for item in value] if isinstance(value, list) else value
                for key, value in dataclasses.asdict(self).items()}

    def summary(self):
        return (f"{len(self.started)} started, {len(self.reopened)} reopened, {len(self.stopped)} stopped, "
                f"{len(self.renamed)} renamed, {len(self.skipped)} skipped"
                + (" (dry run)" if self.dry_run else ""))


# ------------------------------------------------------------------ wikitext

def find_mentor(wikitext):
    """Return the normalised mentor name from a user page, or ``None``."""
    if not wikitext:
        return None
    text = _COMMENT_RE.sub("", wikitext)
    for regex in (_MENTOR_PARAM_RE, _MENTORAT_RE):
        match = regex.search(text)
        if match:
            name = _USER_PREFIX_RE.sub("", match.group(1)).split("|")[0].strip(" ]")
            if name:
                return normalize_user(name)
    return None


def _api_query(params, opener):
    query = urllib.parse.urlencode({"action": "query", "format": "json", "formatversion": "2", **params})
    request = urllib.request.Request(f"{API_URL}?{query}", headers={"User-Agent": USER_AGENT})
    with opener(request, timeout=30) as response:
        return json.load(response)["query"]


def fetch_user_pages(titles, opener=urllib.request.urlopen):
    """Return ``{title: {"text", "redirect", "target_text"}}`` for the given titles.

    *title* is the requested title (``Benutzer:X``). Redirects are **not**
    followed for ``text``; for a redirect ``redirect`` is the target title and
    ``target_text`` its wikitext if the target is a local page (``None`` for
    interwiki targets such as ``en:User:X``). Missing pages give ``None``.
    """
    result = {}
    titles = list(dict.fromkeys(titles))
    revisions = {"prop": "revisions|info", "rvprop": "content", "rvslots": "main"}
    for i in range(0, len(titles), API_BATCH):
        batch = titles[i:i + API_BATCH]
        data = _api_query({**revisions, "titles": "|".join(batch)}, opener)
        normalized = {n["to"]: n["from"] for n in data.get("normalized", [])}
        redirects = []
        for page in data.get("pages", []):
            title = normalized.get(page["title"], page["title"])
            if page.get("missing") or page.get("invalid") or not page.get("revisions"):
                result[title] = None
                continue
            result[title] = {"text": page["revisions"][0]["slots"]["main"]["content"],
                             "redirect": None, "target_text": None}
            if page.get("redirect"):
                redirects.append((title, page["title"]))
        if not redirects:
            continue
        data = _api_query({**revisions, "titles": "|".join(t for _, t in redirects), "redirects": "1"}, opener)
        targets = {r["from"]: r for r in data.get("redirects", [])}
        texts = {p["title"]: p["revisions"][0]["slots"]["main"]["content"]
                 for p in data.get("pages", []) if p.get("revisions")}
        for title, actual in redirects:
            target = targets.get(actual)
            if target:
                result[title]["redirect"] = target["to"]
                if not target.get("tointerwiki"):
                    result[title]["target_text"] = texts.get(target["to"])
    return result


# ------------------------------------------------------------------ planning

def plan(member_ids, mentorings):
    """Compare category members with the running mentorings.

    *member_ids* is ``{user name: user id}`` of the category members,
    *mentorings* the rows of ``MPRepository.sync_mentorings()``. Returns
    ``(new, stop, renames)``: user names without a running mentoring, mentorings
    to stop, and ``(mentee_id, old, new)`` for renamed mentees.
    """
    running = {}
    for row in mentorings:
        running.setdefault(row["mentee_user_id"], []).append(row)
    ids = set(member_ids.values())
    new = sorted(name for name, user_id in member_ids.items() if user_id not in running)
    stop = [row for mentee_id, rows in running.items() if mentee_id not in ids for row in rows]
    by_id = {user_id: name for name, user_id in member_ids.items()}
    renames = sorted({(mentee_id, rows[0]["mentee_user_name"], by_id[mentee_id])
                      for mentee_id, rows in running.items()
                      if mentee_id in by_id and rows[0]["mentee_user_name"] != by_id[mentee_id]})
    return new, stop, renames


# ------------------------------------------------------------------ run

def sync_mentees(mp, wiki, fetch=fetch_user_pages, dry_run=False, force=False, now=None):
    """Run one synchronisation; see the module docstring."""
    now = (now or utcnow()).replace(microsecond=0)
    if not mp.acquire_lock(LOCK_NAME):
        raise SyncAborted("another sync-mentees run is still active")
    try:
        result = _sync(mp, wiki, fetch, dry_run, force, now)
    finally:
        mp.release_lock(LOCK_NAME)
    if not dry_run:
        mp.set_meta(META_REPORT, json.dumps({"time": now.isoformat(sep=" "), **result.as_dict()},
                                            ensure_ascii=False))
    return result


def _sync(mp, wiki, fetch, dry_run, force, now):
    result = SyncResult(dry_run=dry_run)
    names = wiki.category_user_names(MENTEE_CATEGORY)
    mentorings = mp.sync_mentorings()
    if not names or not mentorings:
        raise SyncAborted(f"empty list (category: {len(names)}, running mentorings: {len(mentorings)})")

    members = {}
    for name in sorted(names):
        if "/" in name:
            result.skipped.append((f"Benutzer:{name}", "Unterseite, kein Benutzer"))
        else:
            members[name] = None
    user_ids = wiki.user_ids(members)
    for name in members:
        if name not in user_ids:
            result.skipped.append((f"Benutzer:{name}", "kein Benutzerkonto mit diesem Namen"))
    new, stop, renames = plan(user_ids, mentorings)

    if len(stop) > MAX_STOPS_PER_RUN and not force:
        raise SyncAborted(f"{len(stop)} mentorings would be stopped (limit {MAX_STOPS_PER_RUN}); "
                          "check the replica or run with --force")

    for mentee_id, old, new_name in renames:
        if not dry_run:
            try:
                with mp.transaction():
                    mp.rename_mentee(mentee_id, new_name)
                    mp.log(LOG_USER, f"Renamed mentee '{old}' to '{new_name}'", "sync_rename", mentee_id)
            except pymysql.MySQLError as exc:
                result.skipped.append((f"Benutzer:{new_name}", f"Umbenennung fehlgeschlagen: {exc}"))
                continue
        result.renamed.append((old, new_name))

    for row in stop:
        mentee, mentor = row["mentee_user_name"], row["mentor_user_name"]
        if not dry_run:
            with mp.transaction():
                mp.stop_mentorings(row["mentee_user_id"], now)
                mp.log(LOG_USER, f"Stopped mentoring of '{mentee}' by '{mentor}' (left the category)",
                       "sync_stop", row["mentee_user_id"])
        result.stopped.append((mentee, mentor))

    if new:
        pages = fetch([f"Benutzer:{name}" for name in new])
        mentor_names = {}
        for name in new:
            page = pages.get(f"Benutzer:{name}")
            if page is None:
                result.skipped.append((f"Benutzer:{name}", "Benutzerseite nicht gefunden"))
                continue
            mentor = find_mentor(page["text"]) or find_mentor(page["target_text"])
            if not mentor:
                where = f" (Weiterleitung auf {page['redirect']})" if page["redirect"] else ""
                result.skipped.append((f"Benutzer:{name}", f"keine Mentorenvorlage gefunden{where}"))
                continue
            mentor_names[name] = mentor
        mentor_ids = wiki.user_ids(set(mentor_names.values())) if mentor_names else {}
        for name, mentor in mentor_names.items():
            if mentor not in mentor_ids:
                result.skipped.append((f"Benutzer:{name}", f"Mentor „{mentor}“ ist kein Benutzerkonto"))
                continue
            if mentor == name:
                result.skipped.append((f"Benutzer:{name}", "Mentee ist als eigener Mentor eingetragen"))
                continue
            try:
                kind = _start(mp, user_ids[name], name, mentor_ids[mentor], mentor, now, dry_run)
            except pymysql.MySQLError as exc:
                log.exception("sync: %s", name)
                result.skipped.append((f"Benutzer:{name}", f"Datenbankfehler: {exc}"))
                continue
            (result.reopened if kind == "reopened" else result.started).append((name, mentor))

    for page, reason in result.skipped:
        log.warning("sync: skipped %s: %s", page, reason)
    log.info("sync: %s", result.summary())
    return result


def _start(mp, mentee_id, mentee, mentor_id, mentor, now, dry_run):
    """Start (or re-open) the mentoring; returns ``"started"`` or ``"reopened"``."""
    last = mp.last_stopped_relation(mentee_id, now - REOPEN_WITHIN)
    kind = "reopened" if last and last["mm_mentor_id"] == mentor_id else "started"
    if dry_run:
        return kind
    with mp.transaction():
        mp.ensure_mentor(mentor_id, mentor, now.date())
        mp.ensure_mentee(mentee_id, mentee)
        if kind == "reopened":
            mp.reopen_relation(last["mm_mentor_id"], mentee_id, last["mm_start"])
            mp.log(LOG_USER, f"Re-opened mentoring of '{mentee}' by '{mentor}'", "sync_reopen", mentee_id)
        else:
            mp.add_relation(mentor_id, mentee_id, now, None, 0)
            mp.log(LOG_USER, f"Started mentoring of '{mentee}' by '{mentor}'", "sync_start", mentee_id)
    return kind
