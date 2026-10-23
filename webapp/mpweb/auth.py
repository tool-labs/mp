"""Login, password hashing and CSRF protection."""
import functools
import hashlib
import hmac
import secrets

from flask import abort, flash, g, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

MIN_PASSWORD_LENGTH = 8


def legacy_hash(password, salt):
    """The PHP application's ``sha1(salt . sha1(salt . sha1(pw)))``."""
    def sha1(text):
        return hashlib.sha1(text.encode("utf-8")).hexdigest()
    return sha1(salt + sha1(salt + sha1(password)))


def hash_password(password):
    return generate_password_hash(password)


def verify_password(credentials, password):
    """Check *password* against a ``mentor_auth`` row.

    Returns ``(ok, needs_rehash)``; legacy SHA1 hashes are accepted once and
    should then be replaced by a modern hash.
    """
    if not credentials or not password:
        return False, False
    if credentials.get("ma_password_hash"):
        return check_password_hash(credentials["ma_password_hash"], password), False
    legacy, salt = credentials.get("ma_legacy_hash"), credentials.get("ma_legacy_salt")
    if legacy and salt is not None:
        return hmac.compare_digest(legacy_hash(password, salt), legacy.strip()), True
    return False, False


def login_user(mentor_id, user_name):
    session.clear()
    session.permanent = True
    session["user_id"] = mentor_id
    session["user"] = user_name


def logout_user():
    session.clear()


def load_user():
    g.user = session.get("user")
    g.user_id = session.get("user_id")


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not g.get("user"):
            flash("Du musst angemeldet sein, um diese Seite zu nutzen.", "error")
            return redirect(url_for("auth.login", next=request.full_path))
        return view(*args, **kwargs)
    return wrapped


# ------------------------------------------------------------------ CSRF

def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def check_csrf():
    if request.method != "POST":
        return
    sent = request.form.get("csrf_token", "")
    if not sent or not hmac.compare_digest(sent, session.get("csrf", "")):
        abort(400, "Ungültiges oder abgelaufenes Formular. Bitte lade die Seite neu.")
