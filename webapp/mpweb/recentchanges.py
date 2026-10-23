"""Presentation of the mentees' recent changes (like Special:RecentChanges)."""
import datetime as dt
import re
from dataclasses import dataclass, field
from urllib.parse import quote

from markupsafe import Markup, escape

from .helpers import BERLIN, MONTHS_DE, UTC, to_text, wiki_title

NAMESPACES = {
    0: "", 1: "Diskussion", 2: "Benutzer", 3: "Benutzer Diskussion",
    4: "Wikipedia", 5: "Wikipedia Diskussion", 6: "Datei", 7: "Datei Diskussion",
    8: "MediaWiki", 9: "MediaWiki Diskussion", 10: "Vorlage", 11: "Vorlage Diskussion",
    12: "Hilfe", 13: "Hilfe Diskussion", 14: "Kategorie", 15: "Kategorie Diskussion",
    100: "Portal", 101: "Portal Diskussion", 828: "Modul", 829: "Modul Diskussion",
    2300: "Gadget", 2301: "Gadget Diskussion", 2302: "Gadget-Definition",
    2303: "Gadget-Definition Diskussion", -1: "Spezial", -2: "Medium",
}

LOG_PAGES = {
    "move": "Verschiebungs-Logbuch", "upload": "Upload-Logbuch",
    "newusers": "Neuanmeldungs-Logbuch", "delete": "Lösch-Logbuch",
}

_SECTION_RE = re.compile(r"/\*\s*(.*?)\s*\*/")
_PIPED_LINK_RE = re.compile(r"\[\[\s*([^|\]]+?)\s*\|([^\]]+?)\s*\]\]")
_LINK_RE = re.compile(r"\[\[\s*([^|\]]+?)\s*\]\]")
# PHP-serialised move target, e.g. ...s:9:"4::target";s:7:"Foo_Bar";...
_MOVE_TARGET_RE = re.compile(r's:\d+:"4::target";s:\d+:"(.*?)";')


def full_title(namespace, title):
    prefix = NAMESPACES.get(int(namespace), "")
    title = to_text(title)
    return f"{prefix}:{title}" if prefix else title


def _article_url(base, title):
    return f"{base}/wiki/{quote(wiki_title(title), safe=':/')}"


def format_comment(comment, base, page_title):
    """Escape an edit summary and turn section markers and wiki links into links."""
    text = str(escape(to_text(comment) or ""))

    def section(match):
        anchor = quote(match.group(1).replace(" ", "_"), safe="")
        return (f'<a class="autocomment" href="{_article_url(base, page_title)}#{anchor}">'
                f'→\u200e{match.group(1)}</a>')

    text = _SECTION_RE.sub(section, text)
    text = _PIPED_LINK_RE.sub(lambda m: f'<a href="{_article_url(base, m.group(1))}">{m.group(2)}</a>', text)
    text = _LINK_RE.sub(lambda m: f'<a href="{_article_url(base, m.group(1))}">{m.group(1)}</a>', text)
    return Markup(text)


@dataclass
class Change:
    kind: str                     # edit, move, upload, newusers, log
    timestamp: dt.datetime        # local time (Europe/Berlin)
    actor_id: int
    actor_name: str
    title: str
    url: str
    comment: Markup
    rc_id: int = 0
    minor: bool = False
    new: bool = False
    byte_diff: int = 0
    new_length: int = 0
    diff_url: str = ""
    history_url: str = ""
    log_type: str = ""
    log_name: str = ""
    log_url: str = ""
    move_target: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def date_label(self):
        return f"{self.timestamp.day}. {MONTHS_DE[self.timestamp.month - 1]} {self.timestamp.year}"

    @property
    def byte_class(self):
        if self.byte_diff > 0:
            cls = "plus"
        elif self.byte_diff < 0:
            cls = "minus"
        else:
            cls = "null"
        return cls + (" big" if abs(self.byte_diff) > 1000 else "")


def build_change(row, base):
    stamp = dt.datetime.strptime(to_text(row["rc_timestamp"]), "%Y%m%d%H%M%S")
    title = full_title(row["rc_namespace"], row["rc_title"])
    log_type = to_text(row.get("rc_log_type")) or ""
    change = Change(
        kind="edit" if not log_type else (log_type if log_type in LOG_PAGES else "log"),
        timestamp=stamp.replace(tzinfo=UTC).astimezone(BERLIN),
        actor_id=int(row["actor_id"]),
        actor_name=to_text(row["actor_name"]),
        title=title.replace("_", " "),
        url=_article_url(base, title),
        comment=format_comment(row.get("comment_text"), base, title),
        rc_id=int(row.get("rc_id") or 0),
        log_type=log_type,
    )
    if change.kind == "edit":
        change.minor = bool(row.get("rc_minor"))
        change.new = bool(row.get("rc_new"))
        change.new_length = int(row.get("rc_new_len") or 0)
        change.byte_diff = change.new_length - int(row.get("rc_old_len") or 0)
        change.diff_url = (f"{base}/w/index.php?diff={row['rc_this_oldid']}"
                           f"&oldid={row['rc_last_oldid']}")
        change.history_url = f"{base}/w/index.php?title={quote(wiki_title(title), safe=':/')}&action=history"
    else:
        change.log_name = LOG_PAGES.get(log_type, f"Logbuch ({log_type})")
        change.log_url = f"{base}/wiki/Spezial:Logbuch/{quote(log_type)}"
        if log_type == "move":
            match = _MOVE_TARGET_RE.search(to_text(row.get("rc_params")) or "")
            if match:
                change.move_target = match.group(1).replace("_", " ")
    return change


def group_by_day(changes):
    """Group consecutive changes by their local date: ``[(label, [changes])]``."""
    groups = []
    for change in changes:
        if not groups or groups[-1][0] != change.date_label:
            groups.append((change.date_label, []))
        groups[-1][1].append(change)
    return groups
