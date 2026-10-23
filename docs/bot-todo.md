# SpBot `mp-helper.py` / `pyapi/dewpmp.py` – improvements for later

Found during the Flask migration (2026-10). The bot was intentionally **not** changed.

## Must do before further schema work

1. **Transactions**: `dewpmp.Database` connects with PyMySQL's default `autocommit=False` and never
   calls `commit()`. Writes only persist because the tables are MyISAM. Set `autocommit=True` (or commit
   explicitly) – then `mentor`, `mentee`, `mentee_mentor` can move to InnoDB/utf8mb4 (transactions,
   crash safety, foreign keys, 4-byte characters in user names).
2. **SQL injection**: `get_all_mentees(mentor_user_name=…)` concatenates the mentor name into the SQL.
   Use parameters.
3. **Python 2 leftovers**: `unicode(e)` in the constructor's error handling raises `NameError` in
   Python 3 – a wrong DB config ends in a confusing traceback. `_fixUTF8problem` is dead code
   (`return` in the first line).

## Bugs

4. `checkForMenteesToBeArchived()` uses the global `db` instead of a parameter and crashes with
   `IndexError` when `get_all_mentors_for_mentee()` returns nothing (e.g. hidden mentee, renamed user).
5. `checkForNewMentees()`: if neither `{{…|Mentor=…}}` nor the Mentorat template is found,
   `mentorName` is `""` and `add_mentee("", …)` raises – one broken user page stops the whole run.
   Skip and report instead.
6. `writeActiveMenteeList()` calls `exit()` on a negative mentoring age (clock/timezone issue) and divides
   by `countAll` (ZeroDivisionError on an empty list).
7. Timezones: `mm_start` is written with `CURRENT_TIMESTAMP` (server time, UTC) but compared with
   `datetime.now()` (local time of the job container). Use UTC consistently.
8. `get_mw_user_id()` compares with `CONVERT(CAST(%s AS BINARY) USING latin1)` – wrong for names
   outside latin1 (e.g. Cyrillic, emoji). The replica columns are binary UTF-8; compare with the
   UTF-8 encoded name directly.
9. `get_mw_user_contribsum()` uses `DATEDIFF(NOW(), rev_timestamp)` – no index use, slow for active
   users. Use `rev_timestamp >= <timestamp>` like the web app.
10. `itIsThreeOClockPM` is actually 03:00–03:19 (AM, local container time) – with a 20-minute schedule it
    can run 0 or 2 times. Use a date check stored in the DB or a separate daily job.

## Clean-up / simplification

11. `Parser` (XML) and `mergesort/merge` are unused or replaceable by `sorted(key=…)`.
12. `sys.path.append('/data/project/mp/mp/pyapi')` – hard-coded path into another tool's home;
    package `pyapi` properly or vendor it into the spbot repo.
13. `mentorenProgrammMeldungen` still points to `Benutzer_Diskussion:Euku`.
14. `writeMenteeArchive()` re-reads all mentees every run; only the current month changes.
15. The bot could also maintain `comentors`/`mentor_pause` – the web app now does that in the job
    `refresh-comentors`; avoid doing it twice.
16. Write the mentee user id instead of the name when looking up mentees (renames are handled
    via id already in `add_mentee`, but `get_all_mentors_for_mentee` uses the name).

## Found while testing (2026-10-23)

17. **Bot crashes on every run** (59× on 2026-10-23 alone): `checkForNewMentees()` calls
    `userPage.get()` on `Benutzer:LingoLink`, which is a redirect → `IsRedirectPageError`, the whole run
    aborts. No new mentees are recorded and nothing is archived while this lasts. Fix: catch
    `IsRedirectPageError`/`NoPageError` per user (follow the redirect or skip and report).
    Short-term without a code change: remove the redirect page from `Kategorie:Benutzer:Mentee` on the wiki.
18. **PyMySQL ≥ 1.2 breaks `dewpmp.py`**: `defer_connect=True` followed by `ping()` raises
    `pymysql.err.Error: Already closed` since PyMySQL 1.2. The spbot venv has 1.1.1 – do not upgrade it
    (`pip install -U`) before fixing the constructor (connect explicitly instead of `ping()`).
