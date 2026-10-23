"""Constants, formatting filters and input validation."""
import datetime as dt
import re
from urllib.parse import quote
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")
UTC = dt.timezone.utc

AWARDS = ["keine", "Bronze", "Silber", "Gold", "Platin", "Smaragd", "Rubin",
          "Diamant", "Unobtainium"]
# number of finished mentorings needed for the award with the same index
AWARD_THRESHOLDS = [0, 10, 25, 50, 100, 250, 500, 750, 1000]

MM_TYPES = {0: ("?", "nicht gesetzt"), 1: ("N", "Normal"), 2: ("W", "Wunschmentor")}

MONTHS_DE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
             "August", "September", "Oktober", "November", "Dezember"]

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?$")
_MW_TS_RE = re.compile(r"^\d{14}$")


def next_award_due(level, finished):
    """Whether *finished* mentorings already qualify for a higher award."""
    level = int(level or 0)
    return level + 1 < len(AWARD_THRESHOLDS) and finished >= AWARD_THRESHOLDS[level + 1]


def award_name(level):
    level = int(level or 0)
    return AWARDS[level] if 0 <= level < len(AWARDS) else f"Stufe {level}"


def mm_type_short(mm_type):
    return MM_TYPES.get(int(mm_type), (f"Unbekannter Status: {mm_type}",))[0]


# ---------------------------------------------------------------- validation

def parse_date(value):
    """Parse ``YYYY-MM-DD``; empty input gives ``None``.

    Raises ``ValueError`` on invalid input or dates before 2000 (the mentor
    programme did not exist before).
    """
    value = (value or "").strip()
    if not value:
        return None
    if not _DATE_RE.match(value):
        raise ValueError(f"Ungültiges Datum: {value!r} (erwartet JJJJ-MM-TT)")
    try:
        date = dt.date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"Ungültiges Datum: {value!r}") from None
    if date.year < 2000:
        raise ValueError(f"Ungültiges Datum: {value!r} (vor dem Jahr 2000)")
    return date


def parse_datetime(value):
    """Parse ``YYYY-MM-DD HH:MM[:SS]`` (also with ``T``); empty gives ``None``."""
    value = (value or "").strip()
    if not value:
        return None
    if not _DATETIME_RE.match(value):
        raise ValueError(f"Ungültiger Zeitpunkt: {value!r} (erwartet JJJJ-MM-TT hh:mm:ss)")
    try:
        result = dt.datetime.fromisoformat(value.replace("T", " "))
    except ValueError:
        raise ValueError(f"Ungültiger Zeitpunkt: {value!r}") from None
    if result.year < 2000:
        raise ValueError(f"Ungültiger Zeitpunkt: {value!r} (vor dem Jahr 2000)")
    return result


def parse_date_or_datetime_end(value):
    """Accept a date (meaning end of that day) or a full date-time."""
    value = (value or "").strip()
    if _DATE_RE.match(value):
        return dt.datetime.combine(parse_date(value), dt.time(23, 59, 59))
    return parse_datetime(value)


def parse_mw_timestamp(value):
    """Parse a MediaWiki timestamp ``YYYYMMDDHHMMSS``; empty gives ``None``."""
    value = (value or "").strip()
    if not value:
        return None
    if not _MW_TS_RE.match(value):
        raise ValueError(f"Ungültiger Zeitstempel: {value!r} (erwartet JJJJMMTThhmmss)")
    try:
        return dt.datetime.strptime(value, "%Y%m%d%H%M%S")
    except ValueError:
        raise ValueError(f"Ungültiger Zeitstempel: {value!r}") from None


def to_text(value):
    """Decode binary columns from the wiki replicas."""
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    return value


def clamp_int(value, default, minimum, maximum):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


# ---------------------------------------------------------------- formatting

def _as_datetime(value):
    value = to_text(value)
    if value in (None, "", 0):
        return None
    if isinstance(value, str):
        if _MW_TS_RE.match(value):
            return dt.datetime.strptime(value, "%Y%m%d%H%M%S")
        return dt.datetime.fromisoformat(value)
    return value


def format_date(value, default="–"):
    value = _as_datetime(value)
    return value.strftime("%d.%m.%Y") if value else default


def format_datetime(value, default="–"):
    value = _as_datetime(value)
    if not value:
        return default
    if isinstance(value, dt.datetime):
        return value.strftime("%d.%m.%Y, %H:%M")
    return value.strftime("%d.%m.%Y")


def format_number(value):
    return f"{int(value or 0):,}".replace(",", ".")


def utcnow():
    """Current UTC time as naive datetime (the databases store naive UTC)."""
    return dt.datetime.now(UTC).replace(tzinfo=None)


def days_since(value, now=None):
    value = _as_datetime(value)
    if value is None:
        return None
    if not isinstance(value, dt.datetime):
        value = dt.datetime.combine(value, dt.time())
    now = now or utcnow()
    return (now - value).days


def wiki_title(title):
    return to_text(title).replace(" ", "_")


def wiki_url(base, title, **params):
    url = f"{base}/wiki/{quote(wiki_title(title), safe=':/')}"
    if params:
        url = f"{base}/w/index.php?title={quote(wiki_title(title), safe=':/')}"
        url += "".join(f"&{k}={quote(str(v))}" for k, v in params.items())
    return url
