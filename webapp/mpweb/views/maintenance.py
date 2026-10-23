"""Maintenance pages."""
import logging

from flask import Blueprint, abort, render_template, request

from ..db import get_mp, get_wiki
from ..helpers import clamp_int, parse_date_or_datetime_end
from ..wiki import MENTOR_CATEGORY

bp = Blueprint("maintenance", __name__, url_prefix="/wartung")
log = logging.getLogger(__name__)

HISTORY_DEFAULT_LIMIT, HISTORY_MAX_LIMIT = 200, 5000


@bp.route("")
def index():
    return render_template("maintenance.html")


@bp.route("/ex-mentoren")
def former_mentors():
    """Active mentors in the database whose user page left the mentor category."""
    mentors = get_mp().active_mentors()
    in_category = get_wiki().category_user_names(MENTOR_CATEGORY)
    missing = [m for m in mentors if m["mentor_user_name"] not in in_category]
    return render_template("maintenance_former.html", mentors=missing, category=MENTOR_CATEGORY)


@bp.route("/aufnahmetyp")
def unset_type():
    return render_template("maintenance_unset_type.html", relations=get_mp().relations_with_unset_type())


@bp.route("/kurze-betreuungen")
def short():
    relations = get_mp().short_relations()
    for rel in relations:
        hours, rest = divmod(int(rel["seconds"]), 3600)
        rel["duration"] = f"{hours:02d}:{rest // 60:02d}:{rest % 60:02d}"
    return render_template("maintenance_short.html", relations=relations)


@bp.route("/verlauf")
def history():
    try:
        end_time = parse_date_or_datetime_end(request.args.get("end_time"))
    except ValueError as exc:
        abort(400, str(exc))
    limit = clamp_int(request.args.get("limit"), HISTORY_DEFAULT_LIMIT, 1, HISTORY_MAX_LIMIT)
    events = get_mp().history(end_time, limit + 1)
    next_end = None
    if len(events) > limit:
        next_end = events[limit]["event_time"]
        events = events[:limit]
    return render_template("maintenance_history.html", events=events, limit=limit,
                           end_time=end_time, next_end=next_end)
