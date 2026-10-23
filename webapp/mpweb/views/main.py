"""Start page, about, statistics, log, SQL dumps and search."""
import re
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for

from ..charts import line_chart, yearly_stats
from ..db import get_mp, get_wiki
from ..helpers import clamp_int
from ..repository import InvalidPattern

bp = Blueprint("main", __name__)

SEARCH_WHERE = {"all": "Mentor oder Mentee", "mentor": "Mentor", "mentee": "Mentee"}
LOG_PAGE_SIZE = 50
DUMP_RE = re.compile(r"^wpmp-(\d{4}-\d{2}-\d{2})\.sql\.bz2$")


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/info")
def about():
    return render_template("about.html")


@bp.route("/statistik")
def stats():
    mp = get_mp()
    try:
        wp = get_wiki().category_sizes()
    except Exception:
        wp = {"mentors": None, "mentees": None}
    years = yearly_stats(mp.weekly_stats())
    charts = [
        (y, line_chart({"Anfänge": [s for _, s, _ in y.weeks], "Enden": [e for _, _, e in y.weeks]},
                       [str(w) for w, _, _ in y.weeks], title=str(y.year)))
        for y in years
    ]
    return render_template("stats.html", db=mp.counts_db(), total=mp.counts_all(), wp=wp,
                           charts=charts)


@bp.route("/log")
def log():
    page = clamp_int(request.args.get("seite"), 1, 1, 10_000)
    entries = get_mp().log_entries(LOG_PAGE_SIZE + 1, (page - 1) * LOG_PAGE_SIZE)
    return render_template("log.html", entries=entries[:LOG_PAGE_SIZE], page=page,
                           has_next=len(entries) > LOG_PAGE_SIZE)


def _public_dumps():
    folder = Path(current_app.config["DUMP_DIR"])
    if not folder.is_dir():
        return folder, []
    since = current_app.config["DUMPS_NOT_BEFORE"]
    names = [p.name for p in folder.glob("wpmp-*.sql.bz2")
             if DUMP_RE.match(p.name) and DUMP_RE.match(p.name).group(1) >= since]
    return folder, sorted(names, reverse=True)


@bp.route("/sql-dumps/")
def dumps():
    folder, names = _public_dumps()
    files = [(name, (folder / name).stat().st_size) for name in names]
    return render_template("dumps.html", files=files)


@bp.route("/sql-dumps/<name>")
def dump_file(name):
    folder, names = _public_dumps()
    if name not in names:
        abort(404, "Diese Sicherung gibt es nicht.")
    return send_from_directory(folder, name, as_attachment=True, mimetype="application/x-bzip2")


@bp.route("/suche")
def search():
    args = request.args
    query = args.get("q", "").strip()
    where = args.get("where", "all")
    if where not in SEARCH_WHERE:
        where = "all"
    # the full form sends s=1, unchecked boxes are missing then
    detailed = args.get("s") == "1"
    active = "active" in args if detailed else True
    inactive = "inactive" in args if detailed else True
    context = {"query": query, "where": where, "active": active, "inactive": inactive,
               "choices": SEARCH_WHERE, "mentors": None, "mentees": None}
    if not query:
        return render_template("search.html", **context)

    mp = get_mp()
    exact_mentors = mp.find_mentors(query, active, inactive, exact=True) if where != "mentee" else []
    exact_mentees = mp.find_mentees(query, active, inactive, exact=True) if where != "mentor" else []
    if exact_mentors and not exact_mentees:
        return redirect(url_for("mentors.detail", mentor_id=exact_mentors[0]["mentor_user_id"]))
    if exact_mentees and not exact_mentors:
        return redirect(url_for("mentees.detail", mentee_id=exact_mentees[0]["mentee_user_id"]))
    if exact_mentors and exact_mentees:
        context.update(mentors=exact_mentors, mentees=exact_mentees, exact=True)
        return render_template("search.html", **context)

    try:
        if where != "mentee":
            context["mentors"] = mp.find_mentors(query, active, inactive)
        if where != "mentor":
            context["mentees"] = mp.find_mentees(query, active, inactive)
    except InvalidPattern as exc:
        flash(f"Ungültiger regulärer Ausdruck: {exc}", "error")
    return render_template("search.html", **context)
