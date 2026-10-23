"""Read-only API (JSON) and the legacy XML lists of the PHP version."""
import datetime as dt
from xml.etree import ElementTree as ET

from flask import Blueprint, Response, jsonify, request

from ..db import get_mp

bp = Blueprint("api", __name__, url_prefix="/api")


def _iso(value):
    if isinstance(value, dt.datetime):
        return value.isoformat(sep=" ")
    return value.isoformat() if isinstance(value, dt.date) else value


@bp.route("/mentors")
def mentors():
    rows = get_mp().list_mentors(include_former=request.args.get("ehemalige") == "1")
    return jsonify([{
        "id": r["mentor_user_id"], "name": r["mentor_user_name"],
        "in": _iso(r["mentor_in"]), "out": _iso(r["mentor_out"]),
        "paused": bool(r["mentor_pause"]), "award_level": r["mentor_award_level"],
        "active_mentees": r["active_count"], "finished_mentees": r["finished_count"],
    } for r in rows])


@bp.route("/mentees")
def mentees():
    return jsonify([{
        "id": r["mentee_user_id"], "name": r["mentee_user_name"], "mentor_id": r["mentor_user_id"],
        "mentor": r["mentor_user_name"], "since": _iso(r["mm_start"]), "type": r["mm_type"],
    } for r in get_mp().active_mentorings()])


@bp.route("/suggest")
def suggest():
    prefix = request.args.get("q", "").strip()
    where = request.args.get("where", "all")
    if len(prefix) < 2:
        return jsonify([])
    return jsonify(get_mp().suggest_names(prefix, where))


def _xml(root):
    ET.indent(root)
    body = ET.tostring(root, encoding="unicode", xml_declaration=True)
    return Response(body, mimetype="text/xml")


@bp.route("/list_mentors.php")
def legacy_list_mentors():
    root = ET.Element("mentorlist")
    for m in get_mp().mentor_choices():
        node = ET.SubElement(root, "mentor")
        ET.SubElement(node, "name").text = m["mentor_user_name"]
        ET.SubElement(node, "id").text = str(m["mentor_user_id"])
    return _xml(root)


@bp.route("/list_mentees.php")
def legacy_list_mentees():
    root = ET.Element("menteelist")
    for m in get_mp().all_mentees_with_last_mentor():
        node = ET.SubElement(root, "mentee")
        ET.SubElement(node, "name").text = m["mentee_user_name"]
        ET.SubElement(node, "id").text = str(m["mentee_user_id"])
        ET.SubElement(node, "in").text = _iso(m["mentee_in"]) or ""
        if m["mentee_out"]:
            ET.SubElement(node, "out").text = _iso(m["mentee_out"])
        ET.SubElement(node, "mentor_id").text = str(m["mentor_id"] or "")
    return _xml(root)
