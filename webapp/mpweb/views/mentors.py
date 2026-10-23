"""Mentor list, mentor page and mentor editing."""
import datetime as dt
import logging
from collections import Counter

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from ..auth import login_required
from ..db import get_mp, get_wiki
from ..helpers import AWARD_THRESHOLDS, AWARDS, next_award_due, parse_date, utcnow

bp = Blueprint("mentors", __name__)
log = logging.getLogger(__name__)

ACTIVITY_DAYS = 30


def mentee_activity(user_ids):
    """Set of users who edited in the last month, or ``None`` if the replica fails."""
    if not user_ids:
        return set()
    try:
        since = utcnow() - dt.timedelta(days=ACTIVITY_DAYS)
        return get_wiki().active_users(user_ids, since)
    except Exception:
        log.exception("activity lookup failed")
        return None


@bp.route("/mentoren")
def index():
    include_former = request.args.get("ehemalige") == "1"
    mentors = get_mp().list_mentors(include_former)
    for m in mentors:
        m["award_due"] = next_award_due(m["mentor_award_level"], m["finished_count"])
    return render_template("mentors.html", mentors=mentors, include_former=include_former)


@bp.route("/mentor/<int:mentor_id>")
def detail(mentor_id):
    mp = get_mp()
    mentor = mp.get_mentor(mentor_id)
    if not mentor:
        abort(404, f"Es existiert kein Mentor mit der ID {mentor_id}.")
    mentorings = mp.mentorings_of_mentor(mentor_id)
    times = Counter(row["mentee_user_id"] for row in mentorings)
    active = mentee_activity([row["mentee_user_id"] for row in mentorings])
    for row in mentorings:
        row["times"] = times[row["mentee_user_id"]]
        row["active"] = None if active is None else row["mentee_user_id"] in active
    has_active = any(row["mm_stop"] is None for row in mentorings)
    return render_template("mentor.html", mentor=mentor, counts=mp.mentor_counts(mentor_id),
                           mentorings=mentorings, has_active=has_active,
                           comentors=mp.comentors(mentor_id), comentor_of=mp.comentor_of(mentor_id))


@bp.route("/mentor/<int:mentor_id>/bearbeiten", methods=["GET", "POST"])
@login_required
def edit(mentor_id):
    mp = get_mp()
    mentor = mp.get_mentor(mentor_id)
    if not mentor:
        abort(404, f"Es existiert kein Mentor mit der ID {mentor_id}.")
    form = request.form
    if request.method == "POST":
        errors = []
        name = form.get("user_name", "").strip()
        if not name:
            errors.append("Der Benutzername darf nicht leer sein.")
        try:
            date_in = parse_date(form.get("date_in"))
            date_out = parse_date(form.get("date_out"))
            if date_in and date_out and date_out < date_in:
                errors.append("Der Austritt liegt vor dem Eintritt.")
        except ValueError as exc:
            errors.append(str(exc))
        award = form.get("award", "0")
        if not award.isdigit() or int(award) >= len(AWARDS):
            errors.append("Ungültige Auszeichnung.")
        if not errors:
            mp.update_mentor(mentor_id, name, date_in, date_out, form.get("barnstar") == "1",
                             int(award), form.get("remark", "").strip())
            mp.log(g.user, f"Updated mentor data for {name}", "update_mentor", mentor_id)
            flash(f"Die Daten von {name} wurden gespeichert.", "success")
            return redirect(url_for(".detail", mentor_id=mentor_id))
        for error in errors:
            flash(error, "error")
    return render_template("mentor_edit.html", mentor=mentor, form=form if request.method == "POST" else None,
                           awards=list(zip(AWARDS, AWARD_THRESHOLDS, strict=True)))
