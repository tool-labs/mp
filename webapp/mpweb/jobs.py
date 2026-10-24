"""Scheduled jobs (run via the Toolforge jobs framework).

    python -m mpweb.jobs update-rc            # copy the mentees' recent changes
    python -m mpweb.jobs refresh-comentors    # co-mentors and pause flags from WP:MP
    python -m mpweb.jobs sync-mentees [--dry-run] [--force]   # mentorings from Kategorie:Benutzer:Mentee
"""
import argparse
import datetime as dt
import logging
import os
import sys

from .comentors import comentor_pairs, fetch_main_page, parse_mentor_templates
from .config import load_config
from .db import connect_from_config
from .helpers import utcnow
from .repository import MPRepository
from .sync import SyncAborted, sync_mentees
from .wiki import WikiRepository, mw_timestamp

log = logging.getLogger("mpweb.jobs")

ANALYTICS_HOST = "dewiki.analytics.db.svc.wikimedia.cloud"
RC_KEEP_DAYS = 30
META_COMENTORS_REVID = "comentors_revid"


def _repos(config):
    return (MPRepository(connect_from_config(config, "mp")),
            WikiRepository(connect_from_config(config, "wiki")))


def update_recent_changes(mp, wiki, now=None):
    """Copy new recent changes of mentees into ``mentees_recentchanges``."""
    now = now or utcnow()
    oldest = mw_timestamp(now - dt.timedelta(days=RC_KEEP_DAYS))
    since = max(mp.latest_rc_timestamp() or oldest, oldest)
    rows = wiki.mentee_recent_changes(since)
    inserted = mp.insert_recent_changes(rows)
    deleted = mp.delete_recent_changes_before(oldest)
    log.info("recent changes: %d fetched, %d new, %d expired", len(rows), inserted, deleted)
    return inserted, deleted


def refresh_comentors(mp, fetch=fetch_main_page, force=False):
    """Update ``comentors`` and ``mentor.mentor_pause`` if WP:MP changed."""
    revid, text = fetch()
    if not force and mp.get_meta(META_COMENTORS_REVID) == str(revid):
        log.info("co-mentors: revision %s already processed", revid)
        return False
    parsed = parse_mentor_templates(text)
    ids = mp.mentor_ids_by_name()
    pairs = comentor_pairs(parsed, ids)
    paused = {ids[name] for name, meta in parsed.items() if meta["pause"] and name in ids}
    mp.replace_comentors(pairs)
    mp.set_paused_mentors(paused)
    mp.set_meta(META_COMENTORS_REVID, revid)
    log.info("co-mentors: revision %s, %d templates, %d pairs, %d paused",
             revid, len(parsed), len(pairs), len(paused))
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["update-rc", "refresh-comentors", "sync-mentees"])
    parser.add_argument("--force", action="store_true",
                        help="refresh even if unchanged / stop more mentorings than the safety limit")
    parser.add_argument("--dry-run", action="store_true", help="sync-mentees: only report, change nothing")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    env = dict(os.environ)
    env.setdefault("WIKI_DB_HOST", ANALYTICS_HOST)  # jobs belong on the analytics replicas
    mp, wiki = _repos(load_config(env))
    try:
        if args.command == "update-rc":
            update_recent_changes(mp, wiki)
        elif args.command == "sync-mentees":
            sync_mentees(mp, wiki, dry_run=args.dry_run, force=args.force)
        else:
            refresh_comentors(mp, force=args.force)
    except SyncAborted as exc:
        log.error("sync-mentees aborted: %s", exc)
        return 1
    finally:
        mp.close()
        wiki.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
