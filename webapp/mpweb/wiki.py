"""Read-only queries on the dewiki replica (``dewiki_p``)."""
import datetime as dt

from .db import BaseRepository
from .helpers import to_text

MENTEE_CATEGORY = "Benutzer:Mentee"
MENTOR_CATEGORY = "Benutzer:Mentor"
NS_USER = 2
NS_CATEGORY = 14
CHUNK = 500

# rc_source values we copy into the local table and the legacy rc_type numbers
RC_SOURCES = {"mw.edit": 0, "mw.new": 1, "mw.log": 3}


def mw_timestamp(value):
    return value.strftime("%Y%m%d%H%M%S")


def _chunks(items, size=CHUNK):
    items = list(items)
    for i in range(0, len(items), size):
        yield items[i:i + size]


class WikiRepository(BaseRepository):

    def category_sizes(self):
        rows = self.all("SELECT cat_title, cat_pages FROM category WHERE cat_title IN (%s, %s)",
                        (MENTEE_CATEGORY, MENTOR_CATEGORY))
        sizes = {to_text(row["cat_title"]): int(row["cat_pages"]) for row in rows}
        return {"mentees": sizes.get(MENTEE_CATEGORY), "mentors": sizes.get(MENTOR_CATEGORY)}

    def category_user_names(self, category):
        """User names (with spaces) whose user page is in *category*."""
        rows = self.all("""
            SELECT page_title FROM page
            JOIN categorylinks ON cl_from = page_id
            JOIN linktarget ON lt_id = cl_target_id AND lt_namespace = %s AND lt_title = %s
            WHERE page_namespace = %s""", (NS_CATEGORY, category, NS_USER))
        return {to_text(row["page_title"]).replace("_", " ") for row in rows}

    def user_id(self, user_name):
        return self.scalar("SELECT user_id FROM user WHERE user_name = %s", (user_name,))

    def user_ids(self, user_names):
        """Return ``{user name: user id}`` for the existing users among *user_names*."""
        result = {}
        for chunk in _chunks(set(user_names)):
            for row in self.all("SELECT user_id, user_name FROM user WHERE user_name IN %s", (chunk,)):
                result[to_text(row["user_name"])] = int(row["user_id"])
        return result

    def edit_count(self, user_id):
        return self.scalar("SELECT user_editcount FROM user WHERE user_id = %s", (user_id,))

    def last_edits(self, user_ids):
        """Return ``{user_id: datetime of last edit}`` for the given users."""
        result = {}
        for chunk in _chunks(set(user_ids)):
            # correlated subquery: one index lookup per actor instead of a
            # join over all revisions (~50x faster on dewiki)
            rows = self.all("""
                SELECT actor_user, (SELECT MAX(rev_timestamp) FROM revision_userindex
                                    WHERE rev_actor = actor_id) AS last_edit
                FROM actor WHERE actor_user IN %s""", (chunk,))
            for row in rows:
                if row["last_edit"] is None:
                    continue
                result[int(row["actor_user"])] = dt.datetime.strptime(
                    to_text(row["last_edit"]), "%Y%m%d%H%M%S")
        return result

    def active_users(self, user_ids, since):
        """Subset of *user_ids* with at least one edit after *since*."""
        active = set()
        for chunk in _chunks(set(user_ids)):
            rows = self.all("""
                SELECT actor_user FROM actor
                WHERE actor_user IN %s AND EXISTS (
                    SELECT 1 FROM revision_userindex
                    WHERE rev_actor = actor_id AND rev_timestamp >= %s)""", (chunk, mw_timestamp(since)))
            active.update(int(row["actor_user"]) for row in rows)
        return active

    def user_page_history(self, user_name, limit=50):
        rows = self.all("""
            SELECT rev_timestamp, actor_name, comment_text
            FROM page
            JOIN revision_userindex ON rev_page = page_id
            JOIN actor ON actor_id = rev_actor
            JOIN comment ON comment_id = rev_comment_id
            WHERE page_namespace = %s AND page_title = %s
            ORDER BY rev_timestamp DESC LIMIT %s""",
            (NS_USER, user_name.replace(" ", "_"), limit))
        return [{"rev_timestamp": to_text(r["rev_timestamp"]), "actor_name": to_text(r["actor_name"]),
                 "comment_text": to_text(r["comment_text"]) or ""} for r in rows]

    def page_titles(self, page_ids):
        result = {}
        for chunk in _chunks(set(page_ids)):
            for row in self.all("SELECT page_id, page_title FROM page WHERE page_id IN %s", (chunk,)):
                result[int(row["page_id"])] = to_text(row["page_title"]).replace("_", " ")
        return result

    def mentee_recent_changes(self, since):
        """Recent changes of all users in the mentee category since *since*.

        ``rc_new``/``rc_type`` no longer exist on the replicas (MediaWiki
        1.45); they are derived from ``rc_source`` for the local table.
        """
        rows = self.all("""
            SELECT rc_id, rc_timestamp, actor_id, actor_name, rc_namespace, rc_title, comment_text,
                   rc_minor, rc_source, rc_this_oldid, rc_last_oldid, rc_old_len, rc_new_len,
                   rc_params, rc_log_type
            FROM linktarget
            JOIN categorylinks ON cl_target_id = lt_id
            JOIN page ON page_id = cl_from AND page_namespace = %s
            JOIN actor ON actor_name = REPLACE(page_title, '_', ' ')
            JOIN recentchanges_userindex ON rc_actor = actor_id
            JOIN comment_recentchanges ON comment_id = rc_comment_id
            WHERE lt_namespace = %s AND lt_title = %s
              AND rc_timestamp >= %s AND rc_source IN %s""",
            (NS_USER, NS_CATEGORY, MENTEE_CATEGORY, since, list(RC_SOURCES)))
        for row in rows:
            source = to_text(row["rc_source"])
            row["rc_source"] = source
            row["rc_new"] = int(source == "mw.new")
            row["rc_type"] = RC_SOURCES[source]
            row["rc_log_type"] = row["rc_log_type"] or b""
            row["rc_old_len"] = row["rc_old_len"] or 0
            row["rc_new_len"] = row["rc_new_len"] or 0
        return rows
