"""Parse ``{{Mentor|...}}`` templates on ``Wikipedia:Mentorenprogramm``."""
import json
import re
import urllib.parse
import urllib.request

MAIN_PAGE = "Wikipedia:Mentorenprogramm"
API_URL = "https://de.wikipedia.org/w/api.php"
USER_AGENT = "mp.toolforge.org (https://github.com/tool-labs/mp)"

_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_TEMPLATE_NAME_RE = re.compile(r"^\s*(?:Vorlage:|Template:)?\s*Mentor\s*$", re.I)


def normalize_user(name):
    name = name.replace("_", " ").strip()
    name = re.sub(r"\s+", " ", name)
    return name[:1].upper() + name[1:]


def _top_level_templates(text):
    """Yield the inner text of every top-level ``{{...}}``."""
    depth, start, i = 0, None, 0
    while i < len(text) - 1:
        pair = text[i:i + 2]
        if pair == "{{":
            if depth == 0:
                start = i + 2
            depth += 1
            i += 2
        elif pair == "}}" and depth:
            depth -= 1
            if depth == 0:
                yield text[start:i]
            i += 2
        else:
            i += 1


def _split_params(inner):
    """Split template content at ``|`` that are not nested in ``{{}}``/``[[]]``."""
    parts, depth, current, i = [], 0, [], 0
    while i < len(inner):
        pair = inner[i:i + 2]
        if pair in ("{{", "[["):
            depth += 1
            current.append(pair)
            i += 2
        elif pair in ("}}", "]]") and depth:
            depth -= 1
            current.append(pair)
            i += 2
        elif inner[i] == "|" and depth == 0:
            parts.append("".join(current))
            current = []
            i += 1
        else:
            current.append(inner[i])
            i += 1
    parts.append("".join(current))
    return parts


def parse_mentor_templates(wikitext):
    """Return ``{mentor: {"comentors": [...], "pause": bool}}``."""
    wikitext = _COMMENT_RE.sub("", wikitext)
    result = {}
    for inner in _top_level_templates(wikitext):
        name, *params = _split_params(inner)
        if not _TEMPLATE_NAME_RE.match(name):
            continue
        values = {}
        for param in params:
            if "=" in param:
                key, value = param.split("=", 1)
                values[key.strip().lower()] = value.strip()
        mentor = values.get("mentor")
        if not mentor:
            continue
        comentors = []
        for n in range(1, 5):
            co = values.get(f"co-mentor{n}", "")
            if co and normalize_user(co) not in comentors:
                comentors.append(normalize_user(co))
        result[normalize_user(mentor)] = {
            "comentors": comentors,
            "pause": values.get("pause", "").lower() == "ja",
        }
    return result


def fetch_main_page(opener=urllib.request.urlopen):
    """Return ``(revision id, wikitext)`` of the programme's main page."""
    query = urllib.parse.urlencode({
        "action": "query", "prop": "revisions", "rvprop": "ids|content", "rvslots": "main",
        "titles": MAIN_PAGE, "format": "json", "formatversion": "2",
    })
    request = urllib.request.Request(f"{API_URL}?{query}", headers={"User-Agent": USER_AGENT})
    with opener(request, timeout=30) as response:
        data = json.load(response)
    revision = data["query"]["pages"][0]["revisions"][0]
    return revision["revid"], revision["slots"]["main"]["content"]


def comentor_pairs(parsed, mentor_ids):
    """Translate parsed names to ``{(mentor_id, comentor_id)}`` using *mentor_ids*."""
    pairs = set()
    for mentor, meta in parsed.items():
        mentor_id = mentor_ids.get(mentor)
        if mentor_id is None:
            continue
        for co in meta["comentors"]:
            co_id = mentor_ids.get(co)
            if co_id is not None and co_id != mentor_id:
                pairs.add((mentor_id, co_id))
    return pairs
