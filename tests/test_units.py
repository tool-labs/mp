"""Unit tests that need no database."""
import datetime as dt
import xml.etree.ElementTree as ET

import pytest
from mpweb import auth, charts, comentors, config, helpers, recentchanges

# ------------------------------------------------------------------ helpers

@pytest.mark.parametrize("value,expected", [
    ("2024-02-29", dt.date(2024, 2, 29)), ("", None), (None, None), ("  ", None),
])
def test_parse_date_valid(value, expected):
    assert helpers.parse_date(value) == expected


@pytest.mark.parametrize("value", ["2023-02-29", "1999-12-31", "24-01-01", "2024-13-01", "heute"])
def test_parse_date_invalid(value):
    with pytest.raises(ValueError, match="Ungültiges Datum"):
        helpers.parse_date(value)


def test_parse_datetime_variants():
    expected = dt.datetime(2024, 5, 6, 7, 8, 9)
    assert helpers.parse_datetime("2024-05-06 07:08:09") == expected
    assert helpers.parse_datetime("2024-05-06T07:08:09") == expected
    assert helpers.parse_datetime("2024-05-06 07:08") == dt.datetime(2024, 5, 6, 7, 8)
    for bad in ("2024-05-06", "2024-05-06 25:00:00", "x"):
        with pytest.raises(ValueError):
            helpers.parse_datetime(bad)


def test_parse_date_or_datetime_end():
    assert helpers.parse_date_or_datetime_end("2020-12-31") == dt.datetime(2020, 12, 31, 23, 59, 59)
    assert helpers.parse_date_or_datetime_end("2020-12-31 10:00:00") == dt.datetime(2020, 12, 31, 10)
    assert helpers.parse_date_or_datetime_end("") is None


def test_parse_mw_timestamp():
    assert helpers.parse_mw_timestamp("20240102030405") == dt.datetime(2024, 1, 2, 3, 4, 5)
    assert helpers.parse_mw_timestamp(None) is None
    with pytest.raises(ValueError):
        helpers.parse_mw_timestamp("2024-01-02")
    with pytest.raises(ValueError):
        helpers.parse_mw_timestamp("20241302030405")


def test_formatting():
    assert helpers.format_date(dt.date(2024, 1, 2)) == "02.01.2024"
    assert helpers.format_date(None) == "–"
    assert helpers.format_date(None, "jetzt") == "jetzt"
    assert helpers.format_datetime(dt.datetime(2024, 1, 2, 3, 4)) == "02.01.2024, 03:04"
    assert helpers.format_datetime(b"20240102030405") == "02.01.2024, 03:04"
    assert helpers.format_datetime(dt.date(2024, 1, 2)) == "02.01.2024"
    assert helpers.format_number(1234567) == "1.234.567"
    assert helpers.format_number(None) == "0"


def test_awards():
    assert helpers.award_name(0) == "keine"
    assert helpers.award_name(7) == "Diamant"
    assert not helpers.next_award_due(0, 9)
    assert helpers.next_award_due(0, 10)
    assert helpers.next_award_due(1, 25)
    assert not helpers.next_award_due(1, 24)
    assert not helpers.next_award_due(8, 5000)   # highest level


def test_mm_type_short():
    assert [helpers.mm_type_short(i) for i in (0, 1, 2)] == ["?", "N", "W"]
    assert "Unbekannt" in helpers.mm_type_short(7)


def test_days_since_and_clamp():
    now = dt.datetime(2024, 1, 31, 12)
    assert helpers.days_since(dt.datetime(2024, 1, 1, 12), now) == 30
    assert helpers.days_since(dt.date(2024, 1, 30), now) == 1
    assert helpers.days_since(None, now) is None
    assert helpers.clamp_int("50", 10, 1, 20) == 20
    assert helpers.clamp_int("abc", 10, 1, 20) == 10
    assert helpers.clamp_int("-5", 10, 1, 20) == 1


def test_wiki_url():
    base = "https://de.wikipedia.org"
    assert helpers.wiki_url(base, "Benutzer:Hans Müller") == "https://de.wikipedia.org/wiki/Benutzer:Hans_M%C3%BCller"
    assert helpers.wiki_url(base, "A&B", action="history") == \
        "https://de.wikipedia.org/w/index.php?title=A%26B&action=history"


# ------------------------------------------------------------------ config

def test_load_config_reads_my_cnf(tmp_path):
    cnf = tmp_path / "replica.my.cnf"
    cnf.write_text("[client]\nuser = 's123'\npassword = \"pw%x\"\n")
    key = tmp_path / "key"
    key.write_text("from-file\n")
    cfg = config.load_config({"MP_DB_CNF": str(cnf), "MP_SECRET_KEY_FILE": str(key)})
    assert cfg["DB_USER"] == "s123"
    assert cfg["DB_PASSWORD"] == "pw%x"
    assert cfg["SECRET_KEY"] == "from-file"
    assert cfg["MP_DB_NAME"] == "s51391__mp"
    assert cfg["SESSION_COOKIE_SECURE"] is True


def test_load_config_env_overrides(tmp_path):
    cfg = config.load_config({"MP_DB_CNF": str(tmp_path / "missing"), "MP_DB_USER": "u",
                              "MP_DB_PASSWORD": "p", "MP_SECRET_KEY": "k", "WIKI_DB_HOST": "h",
                              "DB_PORT": "3307", "MP_INSECURE_COOKIES": "1"})
    assert (cfg["DB_USER"], cfg["DB_PASSWORD"], cfg["SECRET_KEY"]) == ("u", "p", "k")
    assert cfg["WIKI_DB_HOST"] == "h" and cfg["DB_PORT"] == 3307
    assert cfg["SESSION_COOKIE_SECURE"] is False


# ------------------------------------------------------------------ auth

def test_legacy_hash_matches_php_algorithm():
    # sha1($salt . sha1($salt . sha1($pw))) computed independently
    import hashlib

    def sha1(s):
        return hashlib.sha1(s.encode()).hexdigest()
    salt = "abc"
    assert auth.legacy_hash("pw", salt) == sha1(salt + sha1(salt + sha1("pw")))
    assert len(auth.legacy_hash("pw", salt)) == 40


def test_verify_password():
    salt = "s" * 40
    legacy = {"ma_password_hash": None, "ma_legacy_hash": auth.legacy_hash("secret", salt), "ma_legacy_salt": salt}
    assert auth.verify_password(legacy, "secret") == (True, True)
    assert auth.verify_password(legacy, "wrong") == (False, True)
    modern = {"ma_password_hash": auth.hash_password("secret")}
    assert auth.verify_password(modern, "secret") == (True, False)
    assert auth.verify_password(modern, "wrong") == (False, False)
    assert auth.verify_password(None, "secret") == (False, False)
    assert auth.verify_password(modern, "") == (False, False)
    assert auth.verify_password({"ma_password_hash": None, "ma_legacy_hash": None}, "x") == (False, False)


# ------------------------------------------------------------------ co-mentors

WIKITEXT = """
<!-- Vorlage zum Kopieren:
{{Mentor
| Mentor = (dein Name)
| Co-Mentor1 = (hier bitte den 1. Co-Mentor angeben)
}}
-->
{{Mentor
| Mentor = Alice
| Pause = ja
| Schwerpunkte = [[Portal:Test|Test]], {{Vorlage|x=1|y}}
| Co-Mentor1 = bob
| Co-Mentor2 =
| Co-Mentor3 = Carol_Smith
}}
{{Mentor|Mentor=Dave|Pause=|Co-Mentor1=Alice|Co-Mentor2=Alice}}
{{Andere Vorlage|Mentor=Eve}}
{{Mentor
| Pause = ja
}}
"""


def test_parse_mentor_templates():
    parsed = comentors.parse_mentor_templates(WIKITEXT)
    assert parsed == {
        "Alice": {"comentors": ["Bob", "Carol Smith"], "pause": True},
        "Dave": {"comentors": ["Alice"], "pause": False},
    }


def test_comentor_pairs():
    parsed = comentors.parse_mentor_templates(WIKITEXT)
    ids = {"Alice": 1, "Bob": 2, "Dave": 4}
    assert comentors.comentor_pairs(parsed, ids) == {(1, 2), (4, 1)}


def test_fetch_main_page_uses_api():
    import io
    import json

    seen = {}

    def opener(request, timeout):
        seen["url"] = request.full_url
        seen["ua"] = request.get_header("User-agent")
        body = {"query": {"pages": [{"revisions": [{"revid": 42, "slots": {"main": {"content": "x"}}}]}]}}
        return io.BytesIO(json.dumps(body).encode())

    assert comentors.fetch_main_page(opener) == (42, "x")
    assert "titles=Wikipedia%3AMentorenprogramm" in seen["url"]
    assert "mp.toolforge.org" in seen["ua"]


# ------------------------------------------------------------------ recent changes

BASE = "https://de.wikipedia.org"


def rc_row(**kw):
    row = {"rc_id": 1, "rc_timestamp": b"20240115120000", "actor_id": 7, "actor_name": b"Neu Ling",
           "rc_namespace": 0, "rc_title": b"Foo_Bar", "comment_text": b"", "rc_minor": 0, "rc_new": 0,
           "rc_this_oldid": 5, "rc_last_oldid": 4, "rc_old_len": 100, "rc_new_len": 50,
           "rc_params": None, "rc_log_type": b""}
    row.update(kw)
    return row


def test_build_change_edit():
    change = recentchanges.build_change(rc_row(rc_minor=1), BASE)
    assert change.kind == "edit"
    assert change.title == "Foo Bar"
    assert change.byte_diff == -50 and change.byte_class == "minus"
    assert change.minor and not change.new
    assert change.diff_url == f"{BASE}/w/index.php?diff=5&oldid=4"
    # UTC 12:00 in January is 13:00 in Berlin
    assert change.timestamp.hour == 13
    assert change.date_label == "15. Januar 2024"


def test_build_change_namespaces_and_big_diff():
    change = recentchanges.build_change(rc_row(rc_namespace=3, rc_title=b"Neu_Ling", rc_old_len=0,
                                               rc_new_len=5000, rc_new=1), BASE)
    assert change.title == "Benutzer Diskussion:Neu Ling"
    assert change.url == f"{BASE}/wiki/Benutzer_Diskussion:Neu_Ling"
    assert change.byte_class == "plus big" and change.new


def test_build_change_move():
    params = b'a:2:{s:9:"4::target";s:13:"Neuer_Artikel";s:10:"5::noredir";s:1:"0";}'
    change = recentchanges.build_change(rc_row(rc_log_type=b"move", rc_params=params), BASE)
    assert change.kind == "move"
    assert change.move_target == "Neuer Artikel"
    assert change.log_url.endswith("Spezial:Logbuch/move")


def test_build_change_unknown_log_type():
    change = recentchanges.build_change(rc_row(rc_log_type=b"block"), BASE)
    assert change.kind == "log" and "block" in change.log_name


def test_format_comment_escapes_and_links():
    html = str(recentchanges.format_comment(b"/* Leben */ siehe [[Foo|bar]] und [[Baz]] <script>", BASE, "Seite"))
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert f'href="{BASE}/wiki/Seite#Leben"' in html
    assert f'<a href="{BASE}/wiki/Foo">bar</a>' in html
    assert f'<a href="{BASE}/wiki/Baz">Baz</a>' in html


def test_group_by_day():
    rows = [rc_row(rc_timestamp=b"20240115120000"), rc_row(rc_timestamp=b"20240115080000"),
            rc_row(rc_timestamp=b"20240114230000")]   # 00:00 on the 15th in Berlin
    groups = recentchanges.group_by_day([recentchanges.build_change(r, BASE) for r in rows])
    assert [(label, len(items)) for label, items in groups] == [("15. Januar 2024", 3)]


# ------------------------------------------------------------------ charts

def test_yearly_stats_fills_weeks():
    years = charts.yearly_stats({2020: {1: [3, 1], 53: [1, 0]}, 2021: {10: [0, 2]}})
    assert [y.year for y in years] == [2021, 2020]
    y2020 = years[1]
    assert len(y2020.weeks) == 53 and y2020.weeks[0] == (1, 3, 1) and y2020.weeks[1] == (2, 0, 0)
    assert (y2020.starts, y2020.stops) == (4, 1)
    assert len(years[0].weeks) == 52


def test_line_chart_is_valid_svg():
    svg = charts.line_chart({"Anfänge": [0, 5, 12], "Enden <x>": [1, 2, 3]}, ["1", "2", "3"], title="2024")
    root = ET.fromstring(str(svg))
    assert root.tag.endswith("svg")
    lines = root.findall("{http://www.w3.org/2000/svg}polyline")
    assert len(lines) == 2
    assert "Enden <x>" in "".join(root.itertext())   # escaped in markup, intact as text


def test_line_chart_all_zero():
    root = ET.fromstring(str(charts.line_chart({"a": [0, 0]}, ["1", "2"])))
    assert root.findall("{http://www.w3.org/2000/svg}polyline")
