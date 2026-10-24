# API v1 (read-only, used by SpBot)

Base URL: `https://mp.toolforge.org/api/v1`. All endpoints are public `GET` requests returning JSON;
nothing can be changed through the API. Times are UTC, formatted `YYYY-MM-DD HH:MM:SS`.
Errors are returned as `{"error": "…"}` with status 404 or 503 (database errors: 503 HTML page).

SpBot's `mp-helper.py` writes the wiki lists from these endpoints. The database itself is maintained
by the job `sync-mentees` (`webapp/mpweb/sync.py`) and by mentors in the web interface.

| Endpoint | Content |
|----------|---------|
| `GET /mentees` | running mentorings of non-hidden mentees, ordered by mentee name |
| `GET /archive/<year>/<month>` | mentorings finished in that month (2007 … next year) |
| `GET /counts` | `mentees_total`, `active_mentors` (with ≥ 1 running mentoring), `active_mentees` |
| `GET /sync-status` | report of the last `sync-mentees` run (404 before the first run) |

`/mentees`:

```json
[{"mentee_id": 201, "mentee": "Neuling1", "mentor_id": 101, "mentor": "Alice",
  "start": "2026-10-04 12:00:00", "type": 2, "last_edit": "2026-10-22 08:13:00", "status": "ok"}]
```

* `type`: 0 = not set, 1 = normal ("Zufall"), 2 = wish mentor
* `status`: `critical` (no edit for > 60 days, counted from the start if there is no edit),
  `long` (mentoring for > 152 days), `ok` – the same rule as the web interface.
  If the wiki replica cannot be reached the endpoint answers 503 instead of guessing.

`/archive/<year>/<month>`:

```json
{"year": 2020, "month": 3, "first_number": 2,
 "mentorings": [{"mentee_id": 202, "mentee": "Neuling2", "mentor_id": 102, "mentor": "Bob",
                 "start": "2020-01-01 10:00:00", "stop": "2020-03-01 10:00:00", "type": 1}]}
```

`first_number` is the running number of the month's first entry (`<ol start>` on the archive page):
all finished mentorings of non-hidden mentees, ordered by stop time; the month's entries are ordered by
stop time, mentor id and mentee name.

`/sync-status`:

```json
{"time": "2026-10-24 12:15:00", "started": [["LingoLink", "AsepTisch"]], "reopened": [],
 "stopped": [["Weg", "Bob"]], "renamed": [], "dry_run": false,
 "skipped": [["Benutzer:X", "keine Mentorenvorlage gefunden"]]}
```

## Job `sync-mentees`

```sh
sh ~/mp/jobs/run-python-job.sh sync-mentees --dry-run   # only report
sh ~/mp/jobs/run-python-job.sh sync-mentees             # scheduled every 20 minutes
```

* A user in `Kategorie:Benutzer:Mentee` without a running mentoring gets one; the mentor is read from
  `{{WP:Mentorenprogramm/Hinweis Mentorat|Mentor=…}}` (or any `|Mentor=`) on the user page. **Redirected
  user pages** are supported: the redirect page itself is searched first (e.g.
  `#WEITERLEITUNG [[en:User:X]]` followed by the template), then a local redirect target.
* A mentoring with the same mentor stopped less than 24 hours ago is re-opened instead.
* Running mentorings of users who left the category are stopped; renamed mentees are matched by user id.
* Subpages, users without an account, pages without the template and unknown mentors are skipped and listed
  in the report – one broken page no longer stops the run.
* Safety: empty category or empty database → abort; more than 25 mentorings to stop in one run → abort
  (replica problem?), override with `--force`. A database lock prevents overlapping runs.
* Every change is written to the change log (`/log`, user `sync-mentees`).
