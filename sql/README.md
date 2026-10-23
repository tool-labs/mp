# Database `s51391__mp`

* `000_initial_schema.sql` – schema as it was before the Flask version.
* `migrations/NNN_*.sql` – applied in order; `schema_migrations` records what is applied.
  Every migration has a `.rollback.sql`.

Apply a migration on Toolforge (after a backup!):

```sh
mariadb-dump --defaults-file=~/replica.my.cnf -h tools.db.svc.wikimedia.cloud s51391__mp | gzip > ~/backups/mp-$(date +%F).sql.gz
mariadb --defaults-file=~/replica.my.cnf -h tools.db.svc.wikimedia.cloud s51391__mp < sql/migrations/001_flask_migration.sql
```

## Tables

| Table | Written by | Notes |
|-------|-----------|-------|
| `mentor` | bot, web | one row per mentor (`mentor_user_id` = dewiki user id); `mentor_out IS NULL` = active |
| `mentee` | bot, web | one row per mentee (dewiki user id) |
| `mentee_mentor` | bot, web | one row per mentoring; `mm_stop IS NULL` = running; `mm_type` 0 = unset, 1 = normal, 2 = wish mentor |
| `comentors` | job `refresh-comentors` | pairs from `{{Mentor}}` on WP:MP |
| `mentor_auth` | web | login hashes (never in public dumps) |
| `logging` | web | change log |
| `mentees_recentchanges` | job `update-rc` | last 30 days of mentees' recent changes |
| `mentee_articles` | – | legacy, empty |
| `mp_meta` | jobs | key/value (e.g. processed WP:MP revision) |

## Compatibility with SpBot

`pyapi/dewpmp.py` opens its connection with autocommit **off** and never commits.
This only works because `mentor`, `mentee` and `mentee_mentor` are **MyISAM**.
Do not convert these three tables to InnoDB (or rename/drop their columns) before the bot
commits its transactions – see `docs/bot-todo.md`. `tests/test_integration.py::test_bot_api_still_works`
runs the real `dewpmp.py` against the migrated schema.
