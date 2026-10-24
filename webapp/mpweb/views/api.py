"""Read-only API (JSON) and the legacy XML lists of the PHP version.

``/api/v1/…`` is the documented interface for SpBot's ``mp-helper.py``, which
writes the wiki lists from it (see ``docs/api.md``).
"""
import datetime as dt
import json
import logging
from xml.etree import ElementTree as ET

from flask import Blueprint, Response, jsonify, request

from ..db import get_mp, get_wiki
from ..helpers import utcnow
from ..sync import META_REPORT
from .mentees import classify

bp = Blueprint("api", __name__, url_prefix="/api")
log = logging.getLogger(__name__)
FIRST_ARCHIVE_YEAR = 2007


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


# ------------------------------------------------------------------ v1 (SpBot)

def _error(code, message):
    response = jsonify({"error": message})
    response.status_code = code
    return response


def _mentoring(row):
    return {"mentee_id": row["mentee_user_id"], "mentee": row["mentee_user_name"],
            "mentor_id": row["mentor_user_id"], "mentor": row["mentor_user_name"],
            "start": _iso(row["mm_start"]), "type": row["mm_type"]}


@bp.route("/v1/mentees")
def v1_mentees():
    """Running mentorings of non-hidden mentees with the traffic-light status."""
    rows = get_mp().visible_active_mentorings()
    try:
        last_edits = get_wiki().last_edits([r["mentee_user_id"] for r in rows])
    except Exception:
        log.exception("api v1: last edit lookup failed")
        return _error(503, "last edits unavailable (wiki replica)")
    now = utcnow()
    result = []
    for row in rows:
        last = last_edits.get(row["mentee_user_id"])
        result.append({**_mentoring(row), "last_edit": _iso(last),
                       "status": classify(row["mm_start"], last, now)})
    return jsonify(result)


@bp.route("/v1/archive/<int:year>/<int:month>")
def v1_archive(year, month):
    """Mentorings finished in a month, as on the monthly archive pages."""
    if not (FIRST_ARCHIVE_YEAR <= year <= utcnow().year + 1 and 1 <= month <= 12):
        return _error(404, "no such month")
    first_number, rows = get_mp().finished_in_month(year, month)
    return jsonify({"year": year, "month": month, "first_number": first_number,
                    "mentorings": [{**_mentoring(r), "stop": _iso(r["mm_stop"])} for r in rows]})


@bp.route("/v1/counts")
def v1_counts():
    mp = get_mp()
    return jsonify({"mentees_total": mp.counts_all()["mentees"],
                    "active_mentors": mp.active_mentor_number(),
                    "active_mentees": mp.counts_db()["mentees"]})


@bp.route("/v1/sync-status")
def v1_sync_status():
    """Result of the last ``sync-mentees`` run, including skipped user pages."""
    report = get_mp().get_meta(META_REPORT)
    if not report:
        return _error(404, "no sync run recorded yet")
    return jsonify(json.loads(report))
