# Deployment on Toolforge (tool `mp`)

Webservice type `python3.11`: uwsgi serves `~/www/python/src/app.py` with the venv
`~/www/python/venv`.

1. **Backup** the database (see `sql/README.md`).
2. **Migrate**: `sql/migrations/001_flask_migration.sql`.
3. **Code**: `cd ~/mp && git pull` (branch `master`).
4. **Secret key** (once): `toolforge envvars create MP_SECRET_KEY` (random value, e.g. `python3 -c 'import secrets; print(secrets.token_hex(32))'`).
5. **Webservice**:
   ```sh
   mkdir -p ~/www/python && ln -sfn ~/mp/webapp ~/www/python/src
   toolforge webservice stop                       # old php7.4
   toolforge webservice python3.11 shell -- bash -c \
     'python3 -m venv ~/www/python/venv && ~/www/python/venv/bin/pip install -U pip && ~/www/python/venv/bin/pip install -r ~/www/python/src/requirements.txt'
   toolforge webservice python3.11 start
   ```
6. **Jobs**: `diff <(toolforge jobs dump) ~/toolforge_jobs.yaml`, then `toolforge jobs load ~/toolforge_jobs.yaml`.
7. Check <https://mp.toolforge.org/>, `~/uwsgi.log`, `~/logs/update-mentees-rc.*`.

Rollback: `toolforge webservice stop`, restore the backup (or run the `.rollback.sql`),
check out the previous commit and start `php7.4` again (note: the php7.4 image was
crash-looping on 2026-10-23 anyway).

## Switching SpBot to API v1 and the job `sync-mentees` (2026-10)

The bot (`/data/project/spbot/bot/scripts/userscripts/mp-helper.py`) no longer touches the database;
`sync-mentees` takes over. Order:

1. **Backup** the database (see `sql/README.md`).
2. **Code**: `cd ~/mp && git pull`, then `toolforge webservice python3.11 restart` (API v1).
3. Check `https://mp.toolforge.org/api/v1/mentees`, `/api/v1/counts`, `/api/v1/archive/2026/10`.
4. **Dry run** of the sync: `toolforge jobs run sync-dry-run --image python3.11 --wait
   --command "sh ~/mp/jobs/run-python-job.sh sync-mentees --dry-run"`, read `~/sync-dry-run.out/.err`
   (started/stopped/skipped are listed), then `toolforge jobs delete sync-dry-run`.
5. **Bot** (tool spbot): replace `mp-helper.py`, test with
   `pyvenv/bin/python bot/pwb.py mp-helper.py -simulate` (as a one-off job, not on the bastion).
6. **Switch**: `diff <(toolforge jobs dump) ~/toolforge_jobs.yaml`, then `toolforge jobs load ~/toolforge_jobs.yaml`
   (adds `sync-mentees`). The spbot job `mp-helper` keeps its schedule and command.
7. Watch `~/logs/sync-mentees.*`, `https://mp.toolforge.org/log`, `/api/v1/sync-status` and the wiki lists
   for a day.
8. **Clean-up** (separate commit): remove `pyapi/`, apply `sql/migrations/002_bot_tables_innodb.sql`;
   in spbot ask the maintainer to delete `replica.mp-db.cnf` (the copy of mp's credentials).

Rollback: restore the old `mp-helper.py` in spbot and delete the job `sync-mentees`
(`toolforge jobs delete sync-mentees`); the database is unchanged by the switch.
