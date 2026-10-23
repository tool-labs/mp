"""Login, logout and password change."""
from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from .. import auth
from ..db import get_mp

bp = Blueprint("auth", __name__)


def _safe_next(target):
    # only allow local paths, never another host
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("main.index")


@bp.route("/anmelden", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("user", "").strip()
        password = request.form.get("password", "")
        mp = get_mp()
        credentials = mp.get_credentials(user) if user else None
        ok, needs_rehash = auth.verify_password(credentials, password)
        if ok:
            if needs_rehash:
                mp.set_password_hash(credentials["mentor_user_id"], auth.hash_password(password))
            auth.login_user(credentials["mentor_user_id"], credentials["mentor_user_name"])
            flash(f"Willkommen, {credentials['mentor_user_name']}! Du bist angemeldet.", "success")
            return redirect(_safe_next(request.args.get("next")))
        flash("Anmeldung fehlgeschlagen. Benutzername oder Passwort sind falsch.", "error")
    return render_template("login.html")


@bp.route("/abmelden", methods=["POST"])
def logout():
    auth.logout_user()
    flash("Du wurdest abgemeldet.", "success")
    return redirect(url_for("main.index"))


@bp.route("/passwort", methods=["GET", "POST"])
@auth.login_required
def change_password():
    if request.method == "POST":
        mp = get_mp()
        form = request.form
        ok, _ = auth.verify_password(mp.get_credentials(g.user), form.get("current", ""))
        new = form.get("new", "")
        if not ok:
            flash("Das aktuelle Passwort ist falsch.", "error")
        elif len(new) < auth.MIN_PASSWORD_LENGTH:
            flash(f"Das neue Passwort muss mindestens {auth.MIN_PASSWORD_LENGTH} Zeichen lang sein.", "error")
        elif new != form.get("repeat", ""):
            flash("Die beiden neuen Passwörter stimmen nicht überein.", "error")
        else:
            mp.set_password_hash(g.user_id, auth.hash_password(new))
            mp.log(g.user, "Changed user password", "change_password", 0)
            flash("Das Passwort wurde geändert.", "success")
            return redirect(url_for("main.index"))
    return render_template("change_password.html", min_length=auth.MIN_PASSWORD_LENGTH)
