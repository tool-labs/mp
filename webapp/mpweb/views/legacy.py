"""Redirects for URLs of the PHP version (``index.php?action=...``).

Many wiki pages link to the old URLs, so they must keep working.
"""
from flask import Blueprint, abort, redirect, request, url_for

bp = Blueprint("legacy", __name__)

SIMPLE = {
    "": "main.index", "info": "main.index", "index": "main.index", "about": "main.about",
    "mentees": "mentees.index", "maintenance": "maintenance.index",
    "maintenance_ex_mentor": "maintenance.former_mentors",
    "maintenance_wm": "maintenance.unset_type", "maintenance_short_mm": "maintenance.short",
    "stat": "main.stats", "log": "main.log", "login": "auth.login", "logout": "main.index",
    "changepw": "auth.change_password",
}


def _id(args, name="id"):
    value = args.get(name, "").strip()
    if not value.isdigit():
        abort(404, "Ungültige oder fehlende ID.")
    return int(value)


def _pick(args, *names):
    return {name: args[name] for name in names if args.get(name)}


def legacy_url(args):
    """Translate the query string of an old URL into the new URL (or abort 404)."""
    action = args.get("action", "").strip()
    if action in SIMPLE:
        return url_for(SIMPLE[action])
    if action in ("mentorlist", "list"):
        former = args.get("no_activity_filter") == "1" or bool(args.get("all"))
        return url_for("mentors.index", **({"ehemalige": "1"} if former else {}))
    if action in ("view", "viewmentor"):
        return url_for("mentors.detail", mentor_id=_id(args))
    if action == "viewmentee":
        return url_for("mentees.detail", mentee_id=_id(args))
    if action == "mentees_rc":
        return url_for("mentees.recent_changes", **_pick(args, "start_time", "end_time", "limit"))
    if action == "maintenance_mm_history":
        return url_for("maintenance.history", **_pick(args, "end_time", "limit"))
    if action == "search":
        params = {"q": args.get("search-content", ""), "where": args.get("search-where", "all"), "s": "1"}
        for old, new in (("search-active", "active"), ("search-inactive", "inactive")):
            if args.get(old):
                params[new] = "on"
        return url_for("main.search", **params)
    if action == "edit":
        what = args.get("what")
        if what == "mentor":
            return url_for("mentors.edit", mentor_id=_id(args))
        if what == "mentee":
            return url_for("mentees.edit", mentee_id=_id(args))
    if action == "editmm":
        if args.get("create") == "new":
            return url_for("relations.create", mentee_id=_id(args, "mentee_id"))
        return url_for("relations.edit", **_pick(args, "mentee_id", "mentor_id", "start"))
    abort(404, f"Die Seite „{action}“ existiert nicht.")


@bp.route("/index.php")
def index_php():
    return redirect(legacy_url(request.args), code=301)


@bp.before_app_request
def root_with_action():
    if request.path == "/" and "action" in request.args:
        return redirect(legacy_url(request.args), code=301)
    return None
