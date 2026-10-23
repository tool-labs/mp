# Mentorenprogramm – Mentorendatenbank

Web interface of the mentor programme ([WP:MP](https://de.wikipedia.org/wiki/Wikipedia:Mentorenprogramm))
of the German Wikipedia: mentors, their mentees and the history of all mentorings since 2007.
Runs on Toolforge as <https://mp.toolforge.org/>.

New mentees and finished mentorings are written by the bot
[SpBot](https://de.wikipedia.org/wiki/Benutzer:SpBot) (`mp-helper.py`, in the
[spbot repository](https://github.com/euku/spbot/tree/spbot/scripts/userscripts)), which uses
`pyapi/dewpmp.py` from this repository. Logged-in mentors can correct data in the web interface.

## Layout

| Path | Content |
|------|---------|
| `webapp/` | Flask app (`app.py` = WSGI entry point, package `mpweb`) |
| `webapp/mpweb/jobs.py` | scheduled jobs: mentees' recent changes, co-mentors from WP:MP |
| `sql/` | schema (`000_initial_schema.sql`) and migrations (`migrations/`) – see `sql/README.md` |
| `jobs/` | Toolforge jobs (`toolforge_jobs.yaml`) and shell scripts |
| `pyapi/` | database API used by SpBot – **do not change without checking the bot** |
| `tests/` | pytest suite (unit tests + integration tests against MariaDB) |
| `docs/` | deployment notes and the list of planned bot improvements |

## Development

```sh
python3.11 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest                      # unit tests; integration tests are skipped
```

The integration tests need a MariaDB server. They create (and drop!) the databases
`mp_test` and `wiki_test`:

```sh
docker run -d --rm -p 3306:3306 -e MARIADB_ROOT_PASSWORD=root mariadb:10.6
MP_TEST_DB_HOST=127.0.0.1 MP_TEST_DB_USER=root MP_TEST_DB_PASSWORD=root pytest
```

Run the app locally against such a database:

```sh
cd webapp
MP_DB_HOST=127.0.0.1 WIKI_DB_HOST=127.0.0.1 MP_DB_NAME=mp_test WIKI_DB_NAME=wiki_test \
MP_DB_USER=root MP_DB_PASSWORD=root MP_SECRET_KEY=dev MP_INSECURE_COOKIES=1 flask --app app run
```

GitHub Actions (`.github/workflows/ci.yml`) runs ruff, the full test suite against MariaDB 10.6
and a smoke test of the running app on every push and pull request.

## Configuration

On Toolforge everything is read from `~/replica.my.cnf`; environment variables override it:
`MP_DB_HOST`, `MP_DB_NAME`, `WIKI_DB_HOST`, `WIKI_DB_NAME`, `DB_PORT`, `MP_DB_USER`, `MP_DB_PASSWORD`,
`MP_SECRET_KEY` (or the file `~/.mp_secret_key`), `MP_DUMP_DIR`, `MP_DUMPS_NOT_BEFORE`.

## License

MIT and LGPL, see `LICENSE`. Original PHP version by Robin Krahl (ireas), Merlissimo and others.
