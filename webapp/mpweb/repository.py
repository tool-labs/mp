"""Queries on the tool's own database (ToolsDB ``s51391__mp``).

The tables ``mentor``, ``mentee`` and ``mentee_mentor`` are shared with the
SpBot ``mp-helper.py`` bot (via ``pyapi/dewpmp.py``). Their columns must stay
compatible, see ``sql/README.md``.
"""
import datetime as dt

import pymysql

from .db import BaseRepository

FAR_FUTURE = dt.datetime(9999, 12, 31, 23, 59, 59)

_MENTEE_STATUS = """
    MIN(mm.mm_start) AS mentee_in,
    CASE WHEN SUM(mm.mm_stop IS NULL) > 0 THEN NULL ELSE MAX(mm.mm_stop) END AS mentee_out,
    COALESCE(SUM(mm.mm_stop IS NULL), 0) AS active_count
"""


class InvalidPattern(ValueError):
    """The search pattern is not a valid regular expression."""


def _activity_having(active, inactive):
    if active and not inactive:
        return " HAVING active_count > 0"
    if inactive and not active:
        return " HAVING active_count = 0"
    return ""


class MPRepository(BaseRepository):

    # ------------------------------------------------------------ counts

    def counts_db(self):
        return {
            "mentors": self.scalar("SELECT COUNT(*) FROM mentor WHERE mentor_out IS NULL"),
            "mentees": self.scalar("SELECT COUNT(*) FROM mentee_mentor WHERE mm_stop IS NULL"),
        }

    def counts_all(self):
        return {
            "mentors": self.scalar("SELECT COUNT(*) FROM mentor"),
            "mentees": self.scalar("SELECT COUNT(*) FROM mentee"),
        }

    # ------------------------------------------------------------ mentors

    def list_mentors(self, include_former=False):
        where = "" if include_former else "WHERE m.mentor_out IS NULL"
        return self.all(f"""
            SELECT m.mentor_user_id, m.mentor_user_name, m.mentor_in, m.mentor_out,
                   m.mentor_award_level, m.mentor_has_barnstar, m.mentor_pause,
                   COUNT(DISTINCT CASE WHEN mm.mm_stop IS NULL THEN mm.mm_mentee_id END) AS active_count,
                   COUNT(DISTINCT CASE WHEN mm.mm_stop IS NOT NULL THEN mm.mm_mentee_id END) AS finished_count
            FROM mentor m
            LEFT JOIN mentee_mentor mm ON mm.mm_mentor_id = m.mentor_user_id
            {where}
            GROUP BY m.mentor_user_id, m.mentor_user_name, m.mentor_in, m.mentor_out,
                     m.mentor_award_level, m.mentor_has_barnstar, m.mentor_pause
            ORDER BY m.mentor_user_name""")

    def mentor_choices(self):
        return self.all("""SELECT mentor_user_id, mentor_user_name, mentor_out
                           FROM mentor ORDER BY mentor_user_name""")

    def get_mentor(self, mentor_id):
        return self.one("""SELECT mentor_user_id, mentor_user_name, mentor_in, mentor_out,
                                  mentor_pause, mentor_award_level, mentor_has_barnstar,
                                  mentor_remark, mentor_lastupdate
                           FROM mentor WHERE mentor_user_id = %s""", (mentor_id,))

    def mentor_counts(self, mentor_id):
        return self.one("""SELECT COUNT(*) AS mentorings, COUNT(DISTINCT mm_mentee_id) AS mentees
                           FROM mentee_mentor WHERE mm_mentor_id = %s""", (mentor_id,))

    def mentorings_of_mentor(self, mentor_id):
        return self.all("""
            SELECT me.mentee_user_id, me.mentee_user_name, mm.mm_start, mm.mm_stop, mm.mm_type
            FROM mentee_mentor mm JOIN mentee me ON me.mentee_user_id = mm.mm_mentee_id
            WHERE mm.mm_mentor_id = %s ORDER BY mm.mm_start DESC""", (mentor_id,))

    def comentors(self, mentor_id):
        return self.all("""
            SELECT m.mentor_user_id, m.mentor_user_name FROM comentors c
            JOIN mentor m ON m.mentor_user_id = c.co_comentor_id
            WHERE c.co_mentor_id = %s ORDER BY m.mentor_user_name""", (mentor_id,))

    def comentor_of(self, mentor_id):
        return self.all("""
            SELECT m.mentor_user_id, m.mentor_user_name FROM comentors c
            JOIN mentor m ON m.mentor_user_id = c.co_mentor_id
            WHERE c.co_comentor_id = %s ORDER BY m.mentor_user_name""", (mentor_id,))

    def active_mentors(self):
        return self.all("""SELECT mentor_user_id, mentor_user_name FROM mentor
                           WHERE mentor_out IS NULL ORDER BY mentor_user_name""")

    def mentor_ids_by_name(self):
        return {row["mentor_user_name"]: row["mentor_user_id"]
                for row in self.all("SELECT mentor_user_id, mentor_user_name FROM mentor")}

    def update_mentor(self, mentor_id, user_name, date_in, date_out, barnstar, award, remark):
        return self.execute("""
            UPDATE mentor SET mentor_user_name = %s, mentor_in = %s, mentor_out = %s,
                   mentor_has_barnstar = %s, mentor_award_level = %s, mentor_remark = %s
            WHERE mentor_user_id = %s""",
            (user_name, date_in, date_out, int(bool(barnstar)), award, remark or None, mentor_id))

    # ------------------------------------------------------------ mentees

    def get_mentee(self, mentee_id):
        row = self.one(f"""
            SELECT me.mentee_user_id, me.mentee_user_name, me.mentee_remark, me.mentee_lastupdate,
                   {_MENTEE_STATUS}
            FROM mentee me LEFT JOIN mentee_mentor mm ON mm.mm_mentee_id = me.mentee_user_id
            WHERE me.mentee_user_id = %s
            GROUP BY me.mentee_user_id, me.mentee_user_name, me.mentee_remark, me.mentee_lastupdate""",
            (mentee_id,))
        return row

    def mentors_of_mentee(self, mentee_id):
        return self.all("""
            SELECT mo.mentor_user_id, mo.mentor_user_name, mm.mm_start, mm.mm_stop, mm.mm_type
            FROM mentee_mentor mm JOIN mentor mo ON mo.mentor_user_id = mm.mm_mentor_id
            WHERE mm.mm_mentee_id = %s ORDER BY mm.mm_start""", (mentee_id,))

    def active_mentorings(self):
        return self.all("""
            SELECT me.mentee_user_id, me.mentee_user_name, mm.mm_start, mm.mm_type,
                   mo.mentor_user_id, mo.mentor_user_name
            FROM mentee_mentor mm
            JOIN mentee me ON me.mentee_user_id = mm.mm_mentee_id
            JOIN mentor mo ON mo.mentor_user_id = mm.mm_mentor_id
            WHERE mm.mm_stop IS NULL ORDER BY mm.mm_start""")

    def articles_of_mentee(self, mentee_id):
        return self.all("""SELECT ma_page_id, ma_rev_id, ma_creation_date FROM mentee_articles
                           WHERE ma_mentee_id = %s ORDER BY ma_creation_date DESC""", (mentee_id,))

    def update_mentee(self, mentee_id, user_name, remark):
        return self.execute("""UPDATE mentee SET mentee_user_name = %s, mentee_remark = %s
                               WHERE mentee_user_id = %s""", (user_name, remark or None, mentee_id))

    def all_mentees_with_last_mentor(self):
        return self.all(f"""
            SELECT me.mentee_user_id, me.mentee_user_name, {_MENTEE_STATUS},
                   (SELECT mm2.mm_mentor_id FROM mentee_mentor mm2
                    WHERE mm2.mm_mentee_id = me.mentee_user_id
                    ORDER BY mm2.mm_stop IS NULL DESC, mm2.mm_start DESC LIMIT 1) AS mentor_id
            FROM mentee me LEFT JOIN mentee_mentor mm ON mm.mm_mentee_id = me.mentee_user_id
            GROUP BY me.mentee_user_id, me.mentee_user_name
            ORDER BY me.mentee_user_id""")

    # ------------------------------------------------------------ search

    def _regexp(self, sql, args):
        try:
            return self.all(sql, args)
        except (pymysql.err.OperationalError, pymysql.err.InternalError) as exc:
            if exc.args and exc.args[0] in (1139, 1305, 3685, 3692, 3693, 3695, 3696, 3697):
                raise InvalidPattern(str(exc.args[1] if len(exc.args) > 1 else exc)) from exc
            raise

    def find_mentors(self, pattern, active=True, inactive=True, exact=False):
        if not active and not inactive:
            return []
        cond = "mentor_user_name = %s" if exact else "mentor_user_name REGEXP %s"
        if active and not inactive:
            cond += " AND mentor_out IS NULL"
        elif inactive and not active:
            cond += " AND mentor_out IS NOT NULL"
        return self._regexp(f"""SELECT mentor_user_id, mentor_user_name, mentor_in, mentor_out
                                FROM mentor WHERE {cond} ORDER BY mentor_user_name""", (pattern,))

    def find_mentees(self, pattern, active=True, inactive=True, exact=False):
        if not active and not inactive:
            return []
        cond = "me.mentee_user_name = %s" if exact else "me.mentee_user_name REGEXP %s"
        return self._regexp(f"""
            SELECT me.mentee_user_id, me.mentee_user_name, {_MENTEE_STATUS}
            FROM mentee me LEFT JOIN mentee_mentor mm ON mm.mm_mentee_id = me.mentee_user_id
            WHERE {cond}
            GROUP BY me.mentee_user_id, me.mentee_user_name
            {_activity_having(active, inactive)}
            ORDER BY me.mentee_user_name""", (pattern,))

    def suggest_names(self, prefix, where="all", limit=15):
        like = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        parts, args = [], []
        if where in ("all", "mentor"):
            parts.append("SELECT mentor_user_name AS name FROM mentor WHERE mentor_user_name LIKE %s")
            args.append(like)
        if where in ("all", "mentee"):
            parts.append("SELECT mentee_user_name AS name FROM mentee WHERE mentee_user_name LIKE %s")
            args.append(like)
        if not parts:
            return []
        sql = " UNION ".join(parts) + " ORDER BY name LIMIT %s"
        return [row["name"] for row in self.all(sql, (*args, limit))]

    # ------------------------------------------------------------ relations

    def find_relations(self, mentor_id=None, mentee_id=None, start=None):
        conds, args = [], []
        for column, value in (("mm.mm_mentor_id", mentor_id), ("mm.mm_mentee_id", mentee_id),
                              ("mm.mm_start", start)):
            if value is not None:
                conds.append(f"{column} = %s")
                args.append(value)
        if not conds:
            return []
        return self.all(f"""
            SELECT mm.mm_mentor_id, mm.mm_mentee_id, mm.mm_start, mm.mm_stop, mm.mm_type,
                   mo.mentor_user_name, me.mentee_user_name
            FROM mentee_mentor mm
            JOIN mentor mo ON mo.mentor_user_id = mm.mm_mentor_id
            JOIN mentee me ON me.mentee_user_id = mm.mm_mentee_id
            WHERE {' AND '.join(conds)} ORDER BY mm.mm_start""", args)

    def add_relation(self, mentor_id, mentee_id, start, stop, mm_type):
        return self.execute("""INSERT INTO mentee_mentor (mm_mentor_id, mm_mentee_id, mm_start, mm_stop, mm_type)
                               VALUES (%s, %s, %s, %s, %s)""", (mentor_id, mentee_id, start, stop, mm_type))

    def update_relation(self, key, mentor_id, start, stop, mm_type):
        """*key* is ``(mentor_id, mentee_id, start)`` of the existing relation."""
        old_mentor, mentee_id, old_start = key
        return self.execute("""
            UPDATE mentee_mentor SET mm_mentor_id = %s, mm_start = %s, mm_stop = %s, mm_type = %s
            WHERE mm_mentor_id = %s AND mm_mentee_id = %s AND mm_start = %s""",
            (mentor_id, start, stop, mm_type, old_mentor, mentee_id, old_start))

    def delete_relation(self, mentor_id, mentee_id, start):
        return self.execute("""DELETE FROM mentee_mentor
                               WHERE mm_mentor_id = %s AND mm_mentee_id = %s AND mm_start = %s
                               LIMIT 1""", (mentor_id, mentee_id, start))

    def relations_with_unset_type(self):
        return self.all("""
            SELECT mm.mm_start, mm.mm_stop, me.mentee_user_id, me.mentee_user_name,
                   mo.mentor_user_id, mo.mentor_user_name
            FROM mentee_mentor mm
            JOIN mentee me ON me.mentee_user_id = mm.mm_mentee_id
            JOIN mentor mo ON mo.mentor_user_id = mm.mm_mentor_id
            WHERE mm.mm_type = 0 ORDER BY mm.mm_start""")

    def short_relations(self, max_hours=24):
        return self.all("""
            SELECT mm.mm_start, mm.mm_stop, me.mentee_user_id, me.mentee_user_name,
                   mo.mentor_user_id, mo.mentor_user_name,
                   TIMESTAMPDIFF(SECOND, mm.mm_start, mm.mm_stop) AS seconds
            FROM mentee_mentor mm
            JOIN mentee me ON me.mentee_user_id = mm.mm_mentee_id
            JOIN mentor mo ON mo.mentor_user_id = mm.mm_mentor_id
            WHERE mm.mm_stop IS NOT NULL
              AND TIMESTAMPDIFF(SECOND, mm.mm_start, mm.mm_stop) < %s
            ORDER BY seconds""", (max_hours * 3600,))

    def history(self, end_time=None, limit=200):
        end_time = end_time or FAR_FUTURE
        select = """mm.mm_start, mm.mm_stop, mm.mm_mentee_id, me.mentee_user_name,
                    mm.mm_mentor_id, mo.mentor_user_name
                    FROM mentee_mentor mm
                    JOIN mentee me ON me.mentee_user_id = mm.mm_mentee_id
                    JOIN mentor mo ON mo.mentor_user_id = mm.mm_mentor_id"""
        return self.all(f"""
            SELECT * FROM (
              SELECT mm.mm_start AS event_time, 'start' AS event, {select}
              WHERE mm.mm_start <= %s
              UNION ALL
              SELECT mm.mm_stop AS event_time, 'stop' AS event, {select}
              WHERE mm.mm_stop IS NOT NULL AND mm.mm_stop <= %s
            ) events
            ORDER BY event_time DESC, event DESC, mm_mentee_id
            LIMIT %s""", (end_time, end_time, limit))

    def weekly_stats(self):
        """Return ``{year: {week: [starts, stops]}}`` using ISO weeks."""
        stats = {}
        for column, idx in (("mm_start", 0), ("mm_stop", 1)):
            rows = self.all(f"""SELECT YEARWEEK({column}, 3) AS yw, COUNT(*) AS n
                                FROM mentee_mentor WHERE {column} IS NOT NULL GROUP BY yw""")
            for row in rows:
                year, week = divmod(int(row["yw"]), 100)
                stats.setdefault(year, {}).setdefault(week, [0, 0])[idx] = int(row["n"])
        return stats

    # ------------------------------------------------------------ auth

    def get_credentials(self, user_name):
        return self.one("""
            SELECT m.mentor_user_id, m.mentor_user_name, a.ma_password_hash,
                   a.ma_legacy_hash, a.ma_legacy_salt
            FROM mentor m JOIN mentor_auth a ON a.ma_mentor_id = m.mentor_user_id
            WHERE m.mentor_user_name = %s""", (user_name,))

    def set_password_hash(self, mentor_id, password_hash):
        return self.execute("""
            INSERT INTO mentor_auth (ma_mentor_id, ma_password_hash) VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE ma_password_hash = VALUES(ma_password_hash),
                                    ma_legacy_hash = NULL, ma_legacy_salt = NULL""",
            (mentor_id, password_hash))

    # ------------------------------------------------------------ logging

    def log(self, user, comment, action, target=0):
        self.execute("""INSERT INTO logging (log_comment, log_user_name, log_type, log_target)
                        VALUES (%s, %s, %s, %s)""", (comment, user, action, target or 0))

    def log_entries(self, limit=50, offset=0):
        return self.all("""SELECT log_id, log_date, log_comment, log_user_name, log_type, log_target
                           FROM logging ORDER BY log_id DESC LIMIT %s OFFSET %s""", (limit, offset))

    # ------------------------------------------------------------ recent changes

    def recent_changes(self, start=None, end=None, limit=100):
        conds, args = [], []
        if start:
            conds.append("rc_timestamp >= %s")
            args.append(start)
        if end:
            conds.append("rc_timestamp <= %s")
            args.append(end)
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        return self.all(f"""
            SELECT rc_id, rc_timestamp, actor_id, actor_name, rc_namespace, rc_title, comment_text,
                   rc_minor, rc_new, rc_this_oldid, rc_last_oldid, rc_type, rc_source,
                   rc_old_len, rc_new_len, rc_params, rc_log_type
            FROM mentees_recentchanges {where}
            ORDER BY rc_timestamp DESC, rc_id DESC LIMIT %s""", (*args, limit))

    def latest_rc_timestamp(self):
        value = self.scalar("SELECT MAX(rc_timestamp) FROM mentees_recentchanges")
        return value.decode() if isinstance(value, bytes) else value

    def insert_recent_changes(self, rows):
        if not rows:
            return 0
        with self.conn.cursor() as cur:
            return cur.executemany("""
                INSERT IGNORE INTO mentees_recentchanges
                  (rc_id, rc_timestamp, actor_id, actor_name, rc_namespace, rc_title, comment_text,
                   rc_minor, rc_new, rc_this_oldid, rc_last_oldid, rc_type, rc_source,
                   rc_old_len, rc_new_len, rc_params, rc_log_type)
                VALUES (%(rc_id)s, %(rc_timestamp)s, %(actor_id)s, %(actor_name)s, %(rc_namespace)s,
                        %(rc_title)s, %(comment_text)s, %(rc_minor)s, %(rc_new)s, %(rc_this_oldid)s,
                        %(rc_last_oldid)s, %(rc_type)s, %(rc_source)s, %(rc_old_len)s,
                        %(rc_new_len)s, %(rc_params)s, %(rc_log_type)s)""", rows)

    def delete_recent_changes_before(self, timestamp):
        return self.execute("DELETE FROM mentees_recentchanges WHERE rc_timestamp < %s", (timestamp,))

    # ------------------------------------------------------------ co-mentors / meta

    def replace_comentors(self, pairs):
        """Replace all co-mentor pairs atomically (``comentors`` is InnoDB)."""
        self.conn.begin()
        try:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM comentors")
                if pairs:
                    cur.executemany("""INSERT IGNORE INTO comentors (co_mentor_id, co_comentor_id)
                                       VALUES (%s, %s)""", sorted(pairs))
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def set_paused_mentors(self, mentor_ids):
        ids = sorted(mentor_ids)
        self.execute("UPDATE mentor SET mentor_pause = 0 WHERE mentor_pause <> 0"
                     + (" AND mentor_user_id NOT IN %s" if ids else ""), (ids,) if ids else None)
        if ids:
            self.execute("UPDATE mentor SET mentor_pause = 1 WHERE mentor_pause = 0 "
                         "AND mentor_user_id IN %s", (ids,))

    def get_meta(self, key):
        return self.scalar("SELECT meta_value FROM mp_meta WHERE meta_key = %s", (key,))

    def set_meta(self, key, value):
        self.execute("""INSERT INTO mp_meta (meta_key, meta_value) VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE meta_value = VALUES(meta_value)""", (key, str(value)))
