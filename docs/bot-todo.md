# SpBot `mp-helper.py` / `pyapi/dewpmp.py` – improvements for later

Found during the Flask migration (2026-10). The bot was intentionally **not** changed.

## 0. Replace the `pyapi` interface with an HTTP API (assessed 2026-10-24)

**Status: variant A live since 2026-10-24 22:00 UTC, `pyapi` removed afterwards.** mp: job `sync-mentees`
(`webapp/mpweb/sync.py`) and API v1 (`docs/api.md`); spbot: new `mp-helper.py` that only reads API v1.
Its output was compared with the current wiki pages (list, archive 2026-09/10): byte-identical except
for the status rule (orange now after 152 days as in the web app and the page text, before 365).
The old bot crashed on every run on the redirected user page `Benutzer:LingoLink` (item 17); the
wiki list had not been updated since 2026-10-07 until the first run of the new bot.
Switch-over and clean-up steps: `docs/deployment.md`. Item status after the switch:

| Item | Status |
|------|--------|
| 1, 2, 3, 8, 12, 18 | gone with `pyapi` (clean-up commit, migration 002 → InnoDB/utf8mb4) |
| 4, 5, 16 | solved in `sync-mentees` (matching by user id, broken pages are skipped and reported) |
| 6, 10, 11, 13, 14 | solved in the new bot (no `exit()`, counts at most once a day, dead code removed, current + previous month) |
| 7 | solved: the sync writes UTC (`utcnow()`), the status is computed by the web app |
| 9 | solved: the status uses `WikiRepository.last_edits` |
| 15 | not affected (`refresh-comentors` stays the only writer) |
| 17 | solved: redirected user pages are read without following the redirect (LingoLink: `#WEITERLEITUNG [[en:User:LingoLink]]` + template) |

**Today:** `mp-helper.py` does `sys.path.append('/data/project/mp/mp/pyapi')` and imports
`dewpmp.py`, which opens its own connections to ToolsDB `s51391__mp` and the dewiki replica.
The credentials come from `/data/project/spbot/replica.mp-db.cnf` – a manual copy of the **mp
tool's own** ToolsDB account (same user as `mp/replica.my.cnf`).

Problems of this interface:

- **No privilege separation.** SpBot holds mp's full DB account: it could read `mentor_auth`
  (password hashes), write `logging`, `ALTER`/`DROP` tables. A bug or a leak in spbot affects all of mp.
- **The schema is frozen by a foreign client.** MyISAM, no transactions, no utf8mb4, no renames –
  only because `dewpmp.py` never commits (items 1, 18). Every schema change must be tested against
  code in another repository.
- **Business logic lives twice.** "Start/stop/reopen a mentoring", renames, user-id lookup and the
  traffic-light status exist in `dewpmp.py`/`mp-helper.py` *and* in `webapp/mpweb` – and already
  differ (orange: bot 365 days vs. web 152 days; red: bot "no edit in 60 days" via `DATEDIFF`,
  web via `last_edits`).
- **Bot writes bypass the web app's change log** (`logging`) – corrections in the web interface
  and bot changes are not visible in one history.
- Cross-tool coupling on NFS: hard-coded path, shared `__pycache__` (files owned by
  `tools.spbot` inside mp's repo), credential copy must be re-synced manually on rotation.

**Should we use an HTTP API? Yes.** The web app already has everything the bot needs
(`MPRepository`, `WikiRepository.category_user_names/user_id/last_edits`, read-only `/api/mentees`).
Two variants:

**A – recommended: move the DB sync into mp, bot only reads.**
- New mp job `sync-mentees` (in `mpweb/jobs.py`, like `refresh-comentors`, every 10–20 min):
  compares `Kategorie:Benutzer:Mentee` (replica) with the active mentorings, reads the mentor from
  the user page (`|Mentor=` / `{{WP:Mentorenprogramm/Hinweis Mentorat|Mentor=…}}` via the MW API,
  as `comentors.fetch_main_page` does), and starts/stops/reopens mentorings in **one transaction**,
  logged in `logging` with user `SpBot`/`sync`. Redirect/missing user pages and unknown mentors are
  skipped and listed (fixes 4, 5, 16, 17).
- New **read-only, public** JSON endpoints (no secrets, the data is public anyway):
  - `GET /api/mentees` + `status` (`ok`/`long`/`critical`), `last_edit` – one definition of the status
  - `GET /api/archive/<year>/<month>` – finished mentorings of that month + running number for `<ol start>`
  - `GET /api/counts` – overall mentees, active mentors with mentees
  - `GET /api/events?since=<ts>` – starts/stops since the last run (for the edit summary `+Mentee (Mentor)`)
- `mp-helper.py` shrinks to: `requests.get(...)` → render wikitext → `page.put()` (only SpBot has
  the bot flag; writing the wiki stays in spbot). No DB access, no credentials, no `pyapi`.
- Then: delete `spbot/replica.mp-db.cnf` (ask the maintainer), drop `pyapi/` and
  `test_bot_api_still_works`, convert `mentor`/`mentee`/`mentee_mentor` to InnoDB/utf8mb4.

**B – if the sync must stay in the bot: a narrow write API.**
- `POST /api/v1/mentorings` (start/reopen, body `{mentee, mentor, type}`) and
  `POST /api/v1/mentorings/stop` (`{mentee_id}`), or better one idempotent
  `POST /api/v1/sync` with the complete category list `[{mentee, mentor}]` – the server computes
  the diff in one transaction.
- Auth: random bearer token (≥ 32 bytes), stored as `toolforge envvars create MP_BOT_TOKEN` in
  **spbot**; mp stores only its hash (envvar or `mp_meta`) and compares with `hmac.compare_digest`.
  HTTPS only (`https://mp.toolforge.org`), token never in URLs/logs, rotate by replacing both envvars.
- `auth.check_csrf` rejects every POST without a form token → the API blueprint must be exempt
  from CSRF **only** for requests with a valid `Authorization: Bearer` header (no cookies accepted there).
- Validate input (user names via replica → user id), limit body size, return JSON errors, log to `logging`.
- More attack surface and more code than A (token handling, CSRF exemption, second write path).

**Things to keep in mind for both:**
- Availability: if the webservice is down the bot must log and exit cleanly (next run in 20 min) –
  never write empty/partial lists to the wiki (check HTTP status and that the list is non-empty).
- Use a timeout (e.g. 30 s) and a `User-Agent` (`SpBot mp-helper (https://spbot.toolforge.org)`).
- Version the API (`/api/v1/…`) and cover it with tests in mp's CI; the bot then depends only on
  the documented JSON, not on table columns.
- Migration order: 1) endpoints + tests in mp, 2) run the new bot in `-simulate` and diff the
  generated wikitext with today's pages, 3) switch the job, 4) remove the old path.

Items solved by A: 1, 2, 3, 4, 5, 7, 8, 9, 12, 16, 17, 18 (17 still needs the per-user error
handling, now in mp). Still bot-side: 6, 10, 11, 13, 14.

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
