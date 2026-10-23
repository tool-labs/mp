"""Editing, creating and deleting mentee–mentor relations (``mentee_mentor``)."""
import logging

import pymysql
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from ..auth import login_required
from ..db import get_mp, get_wiki
from ..helpers import MM_TYPES, parse_datetime

bp = Blueprint("relations", __name__, url_prefix="/betreuung")
log = logging.getLogger(__name__)

HIGHLIGHT_WORDS = ("mp", "übernomm", "mentor")


def _int_arg(name, source=None):
    value = (source or request.args).get(name, "").strip()
    if not value:
        return None
    if not value.isdigit():
        abort(400, f"Ungültiger Parameter {name}.")
    return int(value)


def _datetime_arg(name, source=None):
    try:
        return parse_datetime((source or request.args).get(name))
    except ValueError as exc:
        abort(400, str(exc))


def _validate(form, mentor_ids):
    errors, values = [], {}
    try:
        values["start"] = parse_datetime(form.get("start"))
        if values["start"] is None:
            errors.append("Der Beginn muss angegeben werden.")
    except ValueError as exc:
        errors.append(f"Beginn: {exc}")
    try:
        values["stop"] = parse_datetime(form.get("stop"))
    except ValueError as exc:
        errors.append(f"Ende: {exc}")
    if not errors and values["stop"] and values["stop"] < values["start"]:
        errors.append("Das Ende liegt vor dem Beginn.")
    mentor = form.get("mentor_id", "")
    if not mentor.isdigit() or int(mentor) not in mentor_ids:
        errors.append("Bitte wähle einen gültigen Mentor.")
    else:
        values["mentor_id"] = int(mentor)
    mm_type = form.get("mm_type", "")
    if not mm_type.isdigit() or int(mm_type) not in MM_TYPES:
        errors.append("Ungültiger Aufnahmetyp.")
    else:
        values["mm_type"] = int(mm_type)
    return errors, values


def _page_history(mentee_name, mentor_name):
    try:
        history = get_wiki().user_page_history(mentee_name)
    except Exception:
        log.exception("user page history failed")
        return None
    for edit in history:
        comment = edit["comment_text"].lower()
        edit["highlight_comment"] = any(word in comment for word in HIGHLIGHT_WORDS)
        edit["highlight_user"] = edit["actor_name"] == mentor_name
        ts = edit["rev_timestamp"]
        edit["iso"] = f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]} {ts[8:10]}:{ts[10:12]}:{ts[12:14]}"
    return history


@bp.route("", methods=["GET", "POST"])
@login_required
def edit():
    mp = get_mp()
    mentee_id, mentor_id = _int_arg("mentee_id"), _int_arg("mentor_id")
    start = _datetime_arg("start")
    if mentee_id is None and mentor_id is None:
        abort(400, "Du musst mindestens die ID des Mentees oder des Mentors angeben.")
    relations = mp.find_relations(mentor_id, mentee_id, start)
    if not relations:
        abort(404, "Es existiert keine Betreuung mit diesen Eigenschaften.")
    if len(relations) > 1:
        return render_template("relation_choose.html", relations=relations)

    rel = relations[0]
    mentors = mp.mentor_choices()
    if request.method == "POST":
        errors, values = _validate(request.form, {m["mentor_user_id"] for m in mentors})
        if not errors:
            try:
                changed = mp.update_relation((rel["mm_mentor_id"], rel["mm_mentee_id"], rel["mm_start"]),
                                             values["mentor_id"], values["start"], values["stop"],
                                             values["mm_type"])
            except pymysql.err.IntegrityError:
                changed, errors = None, ["Es gibt bereits eine Betreuung mit diesem Mentor und Beginn."]
            if changed == 0:
                errors = ["Die Betreuung wurde inzwischen geändert. Bitte lade die Seite neu."]
            elif changed:
                mp.log(g.user, f"Updated mentee-mentor relation between '{rel['mentor_user_name']}' "
                               f"and '{rel['mentee_user_name']}'", "update_menteementor", rel["mm_mentee_id"])
                flash("Die Betreuung wurde gespeichert.", "success")
                return redirect(url_for("mentees.detail", mentee_id=rel["mm_mentee_id"]))
        for error in errors:
            flash(error, "error")
    return render_template("relation_edit.html", rel=rel, mentors=mentors, mm_types=MM_TYPES,
                           form=request.form if request.method == "POST" else None, new=False,
                           history=_page_history(rel["mentee_user_name"], rel["mentor_user_name"]))


@bp.route("/neu", methods=["GET", "POST"])
@login_required
def create():
    mp = get_mp()
    mentee_id = _int_arg("mentee_id")
    mentee = mp.get_mentee(mentee_id) if mentee_id else None
    if not mentee:
        abort(404, "Es existiert kein Mentee mit dieser ID.")
    mentors = mp.mentor_choices()
    rel = {"mm_mentor_id": None, "mm_mentee_id": mentee_id, "mm_start": None, "mm_stop": None,
           "mm_type": 0, "mentee_user_name": mentee["mentee_user_name"], "mentor_user_name": None}
    if request.method == "POST":
        errors, values = _validate(request.form, {m["mentor_user_id"] for m in mentors})
        if not errors:
            try:
                mp.add_relation(values["mentor_id"], mentee_id, values["start"], values["stop"],
                                values["mm_type"])
            except pymysql.err.IntegrityError:
                errors = ["Es gibt bereits eine Betreuung mit diesem Mentor und Beginn."]
            else:
                mentor_name = next(m["mentor_user_name"] for m in mentors
                                   if m["mentor_user_id"] == values["mentor_id"])
                mp.log(g.user, f"Added mentee-mentor relation between '{mentor_name}' and "
                               f"'{mentee['mentee_user_name']}'", "add_menteementor", mentee_id)
                flash("Die Betreuung wurde angelegt.", "success")
                return redirect(url_for("mentees.detail", mentee_id=mentee_id))
        for error in errors:
            flash(error, "error")
    return render_template("relation_edit.html", rel=rel, mentors=mentors, mm_types=MM_TYPES,
                           form=request.form if request.method == "POST" else None, new=True,
                           history=_page_history(mentee["mentee_user_name"], None))


@bp.route("/loeschen", methods=["POST"])
@login_required
def delete():
    mp = get_mp()
    mentee_id = _int_arg("mentee_id", request.form)
    mentor_id = _int_arg("mentor_id", request.form)
    start = _datetime_arg("start", request.form)
    if mentee_id is None or mentor_id is None or start is None:
        abort(400, "Die Parameter sind unvollständig.")
    if not mp.delete_relation(mentor_id, mentee_id, start):
        abort(404, "Die Betreuung existiert nicht (mehr).")
    mp.log(g.user, f"Relation gelöscht {mentor_id} -> {mentee_id} ({start})", "delete_mm", mentee_id)
    flash("Die Betreuung wurde gelöscht.", "success")
    return redirect(url_for("mentees.detail", mentee_id=mentee_id))
