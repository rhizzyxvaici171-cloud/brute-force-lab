"""
Brute Force Lab — an intentionally vulnerable login application for teaching
password brute-force attacks and defenses in a controlled classroom setting.

Inspired by the DVWA "Brute Force" module. This app is DELIBERATELY insecure.
Never deploy it on a network you do not fully control, and never reuse its code
in a real application.

Four difficulty levels let students see how each defensive control changes the
attack:

    low        - no protection at all
    medium     - a small artificial delay per attempt
    high       - a per-session CSRF-style token required on every attempt
    impossible - account lockout after too many failures

Author: built for a cybersecurity instructor's live student lab.
"""

import os
import time
import secrets
import sqlite3

from flask import (
    Flask,
    request,
    session,
    redirect,
    url_for,
    render_template,
    flash,
    Response,
)

app = Flask(__name__)
# Fixed-ish secret is fine for a lab; override with env var in hosting.
app.secret_key = os.environ.get("LAB_SECRET_KEY", "brute-force-lab-not-secret")

# ---------------------------------------------------------------------------
# Class gate (HTTP basic auth)
# ---------------------------------------------------------------------------
# When this lab is hosted on the public internet it must not be an open
# brute-force target for strangers. If LAB_GATE_USER and LAB_GATE_PASSWORD are
# BOTH set (e.g. in the hosting provider's env vars), every page except the
# health check requires that shared class password first. Hand the one
# username/password to your students. Locally, leave them unset and the gate
# is off.
GATE_USER = os.environ.get("LAB_GATE_USER")
GATE_PASSWORD = os.environ.get("LAB_GATE_PASSWORD")


@app.before_request
def class_gate():
    if not (GATE_USER and GATE_PASSWORD):
        return  # gate disabled (local use)
    if request.path == "/healthz":
        return  # let uptime checks through
    auth = request.authorization
    if (
        auth
        and secrets.compare_digest(auth.username or "", GATE_USER)
        and secrets.compare_digest(auth.password or "", GATE_PASSWORD)
    ):
        return  # class credential accepted
    return Response(
        "This lab is restricted to students. Enter the class password.",
        401,
        {"WWW-Authenticate": 'Basic realm="Brute Force Lab - class access"'},
    )

# ---------------------------------------------------------------------------
# Lab users. These credentials are intentionally weak so students can crack
# them with common wordlists (e.g. rockyou). This is the whole point of the lab.
# ---------------------------------------------------------------------------
USERS = {
    "admin": "password",
    "gordonb": "abc123",
    "1337": "charley",
    "pablo": "letmein",
    "smithy": "password",
    "student": "123456",
}

# A "flag" shown only after a successful login, so instructors can verify a
# student actually got in.
FLAG = "FLAG{brute_force_is_only_as_strong_as_the_weakest_password}"

# Levels supported by the lab.
LEVELS = ("low", "medium", "high", "impossible")

# Lockout tuning for the "impossible" level.
LOCKOUT_THRESHOLD = 5      # failed attempts before lock
LOCKOUT_SECONDS = 30       # how long the account stays locked

# ---------------------------------------------------------------------------
# Lockout store for the "impossible" level.
#
# This is kept in a tiny SQLite file rather than a Python dict on purpose: a
# production server runs several worker processes, and an in-memory dict would
# give each worker its own private counter, so the lockout would never trigger
# reliably. A SQLite file on the instance is shared by all workers, so the
# count is correct no matter how many workers run.
# ---------------------------------------------------------------------------
LOCKOUT_DB = os.environ.get("LOCKOUT_DB", os.path.join(
    os.environ.get("TMPDIR", "/tmp"), "bruteforce_lockouts.db"
))


def _lock_db():
    conn = sqlite3.connect(LOCKOUT_DB, timeout=5)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS lockouts "
        "(username TEXT PRIMARY KEY, fails INTEGER, locked_until REAL)"
    )
    return conn


def lockout_remaining(username):
    """Seconds left on an active lock for this user, else 0."""
    with _lock_db() as conn:
        row = conn.execute(
            "SELECT locked_until FROM lockouts WHERE username=?", (username,)
        ).fetchone()
    if row and row[0] > time.time():
        return int(row[0] - time.time()) + 1
    return 0


def record_failure(username):
    """Count a failed attempt. Returns True if the account is now locked."""
    now = time.time()
    with _lock_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT fails FROM lockouts WHERE username=?", (username,)
        ).fetchone()
        fails = (row[0] if row else 0) + 1
        if fails >= LOCKOUT_THRESHOLD:
            conn.execute(
                "INSERT OR REPLACE INTO lockouts VALUES (?,?,?)",
                (username, 0, now + LOCKOUT_SECONDS),
            )
            conn.commit()
            return True
        conn.execute(
            "INSERT OR REPLACE INTO lockouts VALUES (?,?,?)",
            (username, fails, 0.0),
        )
        conn.commit()
        return False


def clear_lockout(username):
    with _lock_db() as conn:
        conn.execute("DELETE FROM lockouts WHERE username=?", (username,))
        conn.commit()


def clear_all_lockouts():
    with _lock_db() as conn:
        conn.execute("DELETE FROM lockouts")
        conn.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def current_level():
    """Return the active difficulty level, defaulting to 'low'."""
    level = session.get("level", "low")
    return level if level in LEVELS else "low"


def check_credentials(username, password):
    """Constant-ish credential check. Returns True on a correct match."""
    expected = USERS.get(username)
    return expected is not None and secrets.compare_digest(expected, password)


def issue_token():
    """Create and store a one-request token for the 'high' level."""
    token = secrets.token_hex(16)
    session["login_token"] = token
    return token


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template(
        "index.html",
        level=current_level(),
        levels=LEVELS,
    )


@app.route("/set-level/<level>")
def set_level(level):
    """Let a student pick which difficulty they are attacking."""
    if level in LEVELS:
        session["level"] = level
        flash(f"Difficulty set to '{level}'.", "info")
    else:
        flash("Unknown level.", "error")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    level = current_level()
    error = None
    success = None
    token = None

    if level == "high":
        # A fresh token is required for each attempt. The previous token (if
        # any) was consumed below. Students must parse this out of the HTML,
        # which is what tools like Hydra/Burp do with the http-form-get module.
        token = session.get("login_token") or issue_token()

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if level == "medium":
            # A crude defense: slow every attempt down a little. Students see
            # their attack rate drop but it is still fully brute-forceable.
            time.sleep(1.5)

        if level == "high":
            submitted = request.form.get("user_token", "")
            valid_token = session.get("login_token")
            # Always rotate the token so each request needs a fresh one.
            issue_token()
            if not valid_token or not secrets.compare_digest(
                valid_token, submitted
            ):
                error = "Invalid or missing request token."
                return render_template(
                    "login.html",
                    level=level,
                    levels=LEVELS,
                    error=error,
                    success=success,
                    token=session.get("login_token"),
                    flag=FLAG,
                )
            time.sleep(0.5)

        if level == "impossible":
            remaining = lockout_remaining(username)
            if remaining:
                error = (
                    f"Account '{username}' is locked. "
                    f"Try again in {remaining}s."
                )
                return render_template(
                    "login.html",
                    level=level,
                    levels=LEVELS,
                    error=error,
                    success=success,
                    token=token,
                    flag=FLAG,
                )

        if check_credentials(username, password):
            if level == "impossible":
                clear_lockout(username)
            success = username
            session["logged_in_as"] = username
        else:
            # DVWA-style verbose error — it even confirms the username exists,
            # which is a real vulnerability students should learn to spot.
            if username in USERS:
                error = "Password incorrect for that user."
            else:
                error = "Username and/or password incorrect."

            if level == "impossible" and record_failure(username):
                error = (
                    f"Too many failed attempts. '{username}' locked "
                    f"for {LOCKOUT_SECONDS}s."
                )

    return render_template(
        "login.html",
        level=level,
        levels=LEVELS,
        error=error,
        success=success,
        token=token if level == "high" else None,
        flag=FLAG,
    )


@app.route("/logout")
def logout():
    session.pop("logged_in_as", None)
    flash("Logged out.", "info")
    return redirect(url_for("login"))


@app.route("/reset-lockouts")
def reset_lockouts():
    """Instructor convenience: clear all lockout state."""
    clear_all_lockouts()
    flash("All lockout counters cleared.", "info")
    return redirect(url_for("login"))


@app.route("/healthz")
def healthz():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    # 0.0.0.0 so it is reachable when hosted. debug off for shared use.
    app.run(host="0.0.0.0", port=port, debug=False)
