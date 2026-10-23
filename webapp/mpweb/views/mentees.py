"""Active mentees, mentee page, mentee editing and the mentees' recent changes."""
import logging

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for

from ..auth import login_required
from ..db import get_mp, get_wiki
from ..helpers import clamp_int, days_since, parse_mw_timestamp, utcnow
from ..recentchanges import build_change, group_by_day
from .mentors import mentee_activity

bp = Blueprint("mentees", __name__)
log = logging.getLogger(__name__)

CRITICAL_DAYS = 60       # last edit longer ago → red
LONG_MENTORING_DAYS = 152  # about five months → orange
RC_DEFAULT_LIMIT, RC_MAX_LIMIT = 100, 500


def classify(mm_start, last_edit, now):
    """Traffic-light status of an active mentoring: ``critical``, ``long`` or ``ok``."""
    reference = last_edit or mm_start
    if (now - reference).days > CRITICAL_DAYS:
        return "critical"
    if (now - mm_start).days > LONG_MENTORING_DAYS:
        return "long"
    return "ok"


@bp.route("/mentees")
def index():
    rows = get_mp().active_mentorings()
    try:
        last_edits = get_wiki().last_edits([r["mentee_user_id"] for r in rows])
    except Exception:
        log.exception("last edit lookup failed")
        last_edits = None
    now = utcnow()
    for row in rows:
        last = None if last_edits is None else last_edits.get(row["mentee_user_id"])
        row["last_edit"] = last
        row["last_edit_days"] = days_since(last, now)
        row["since_days"] = days_since(row["mm_start"], now)
        row["status"] = classify(row["mm_start"], last, now) if last_edits is not None else "unknown"
    return render_template("mentees.html", mentees=rows, critical_days=CRITICAL_DAYS,
                           long_days=LONG_MENTORING_DAYS)


@bp.route("/mentee/<int:mentee_id>")
def detail(mentee_id):
    mp = get_mp()
    mentee = mp.get_mentee(mentee_id)
    if not mentee:
        abort(404, f"Es existiert kein Mentee mit der ID {mentee_id}.")
    articles = mp.articles_of_mentee(mentee_id)
    edit_count = None
    try:
        wiki = get_wiki()
        titles = wiki.page_titles([a["ma_page_id"] for a in articles if a["ma_page_id"]])
        for a in articles:
            a["title"] = titles.get(a["ma_page_id"], f"Seite {a['ma_page_id']}")
        edit_count = wiki.edit_count(mentee_id)
    except Exception:
        log.exception("replica lookup failed")
    active = mentee_activity([mentee_id])
    return render_template("mentee.html", mentee=mentee, mentors=mp.mentors_of_mentee(mentee_id),
                           articles=articles, edit_count=edit_count,
                           active=None if active is None else mentee_id in active)


@bp.route("/mentee/<int:mentee_id>/bearbeiten", methods=["GET", "POST"])
@login_required
def edit(mentee_id):
    mp = get_mp()
    mentee = mp.get_mentee(mentee_id)
    if not mentee:
        abort(404, f"Es existiert kein Mentee mit der ID {mentee_id}.")
    if request.method == "POST":
        name = request.form.get("user_name", "").strip()
        if not name:
            flash("Der Benutzername darf nicht leer sein.", "error")
        else:
            mp.update_mentee(mentee_id, name, request.form.get("remark", "").strip())
            mp.log(g.user, f"Updated mentee data for {name}", "update_mentee", mentee_id)
            flash(f"Die Daten von {name} wurden gespeichert.", "success")
            return redirect(url_for(".detail", mentee_id=mentee_id))
    return render_template("mentee_edit.html", mentee=mentee,
                           form=request.form if request.method == "POST" else None)


@bp.route("/mentees/aenderungen")
def recent_changes():
    args = request.args
    try:
        start = parse_mw_timestamp(args.get("start_time"))
        end = parse_mw_timestamp(args.get("end_time"))
    except ValueError as exc:
        abort(400, str(exc))
    limit = clamp_int(args.get("limit"), RC_DEFAULT_LIMIT, 1, RC_MAX_LIMIT)
    fmt = "%Y%m%d%H%M%S"
    rows = get_mp().recent_changes(start and start.strftime(fmt), end and end.strftime(fmt), limit + 1)
    next_end = None
    if len(rows) > limit:
        next_end = rows[limit]["rc_timestamp"]
        next_end = next_end.decode() if isinstance(next_end, bytes) else next_end
        rows = rows[:limit]
    base = current_app.config["WIKI_BASE_URL"]
    changes = [build_change(row, base) for row in rows]
    return render_template("recentchanges.html", groups=group_by_day(changes), count=len(changes),
                           limit=limit, start=start, end=end, next_end=next_end)
