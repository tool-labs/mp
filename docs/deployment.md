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
