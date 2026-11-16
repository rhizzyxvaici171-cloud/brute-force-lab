# Brute Force Lab

An intentionally vulnerable login web app for teaching **password brute-force
attacks and defenses**, modeled on the DVWA "Brute Force" module. Students
attack a live login form; instructors control the difficulty.

> ⚠️ **This app is deliberately insecure.** Host it only on a network you
> control (a classroom LAN, a private VM, or an isolated cloud instance behind
> access control). Never expose it as a general-purpose public site and never
> reuse its code in production.

---

## What students practice

- Enumerating valid usernames from verbose error messages
- Running an online dictionary attack with tools like **Hydra**, **Burp
  Suite Intruder**, **ffuf**, or **wfuzz**
- Seeing how four defensive controls change the attack:

| Level | Defense | Lesson |
|-------|---------|--------|
| `low` | none | Baseline. Unlimited guesses, verbose errors. |
| `medium` | 1.5s delay per attempt | Throttling slows but doesn't stop an attack. |
| `high` | per-request anti-automation token | Tools must parse a fresh token each request. |
| `impossible` | lockout after 5 fails (30s) | Lockout defeats naive online brute force. |

Each student session keeps its own difficulty and its own `high`/`impossible`
state, so one class shares one instance without stepping on each other.

## Lab accounts

Weak credentials on purpose (present in common wordlists):

| Username | Password |
|----------|----------|
| admin | password |
| gordonb | abc123 |
| 1337 | charley |
| pablo | letmein |
| smithy | password |
| student | 123456 |

Share **only `admin`** with students and let them discover the rest, or hand
out the full list — your call.

---

## Run it

### Option A — Python directly (quickest)

```bash
pip install -r requirements.txt
python app.py
```

Then open <http://localhost:5000>.

### Option B — Production server (for a shared class instance)

```bash
pip install -r requirements.txt
gunicorn app:app --bind 0.0.0.0:5000 --workers 2 --threads 4
```

### Option C — Docker

```bash
docker compose up --build
```

---

## Host it live for students

The app reads `$PORT` and binds `0.0.0.0`, and ships a `Procfile`, so it drops
onto most hosts unchanged. Pick whichever fits:

- **A private VM** (AWS EC2 / DigitalOcean / Azure): run Option B behind a
  security group that only allows your students' IP range. Simplest to lock down.
- **Render / Railway / Fly.io**: point them at this repo; the `Procfile` (or
  `Dockerfile`) is picked up automatically. Set env var `LAB_SECRET_KEY`.
- **Classroom LAN**: run Option A/B on your machine and give students your
  LAN IP (e.g. `http://192.168.1.50:5000`).

**Access control matters.** A live brute-force target is noisy and abusable.
This lab has a built-in **class gate**: set the env vars `LAB_GATE_USER` and
`LAB_GATE_PASSWORD`, and every page (except `/healthz`) then requires that
shared password via an HTTP basic-auth prompt. Hand the one username/password
to your students. Leave the vars unset for local use and the gate is off.
`/healthz` returns `200` for uptime checks.

### Deploy to Render (step by step)

1. Push this project to a GitHub repo (a **private** repo is fine — Render can
   deploy from it).
2. In Render: **New + → Blueprint**, pick the repo. Render reads
   [`render.yaml`](render.yaml) and creates the service.
3. When prompted (or afterwards, under the service's **Environment** tab), set
   **`LAB_GATE_PASSWORD`** to a password you'll give students. `LAB_GATE_USER`
   defaults to `student`; change it if you like.
4. Deploy. Render gives you a URL like `https://brute-force-lab.onrender.com`.
   Students open it, enter the class password once, then attack the lab login.

> Render's free tier sleeps after inactivity and wakes on the next request
> (first hit takes ~30s). Fine for a class; upgrade the plan if you want it
> always-on.

### Instructor endpoints

- `/reset-lockouts` — clears all `impossible`-level lockout counters between
  exercises.

---

## Files

```
app.py                 Flask application (all four levels)
templates/             HTML (base, index, login)
static/style.css       Styling
wordlists/             Sample username + password lists for class
requirements.txt       Flask + gunicorn
Procfile               For Render/Railway/Heroku-style hosts
Dockerfile             Container image
docker-compose.yml     One-command local container
STUDENT_GUIDE.md       Hand this to students
```

See **[STUDENT_GUIDE.md](STUDENT_GUIDE.md)** for the attack walkthrough.
