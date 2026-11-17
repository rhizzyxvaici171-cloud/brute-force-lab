# Lecturer's Manual — Brute Force Lab

A complete teaching reference for the live Brute Force Lab. This is the
**instructor's** document: it explains every part of the system — how it is
built, how each defense works under the hood, how to run a class on it, the full
answer key, a timed lesson plan, assessment, troubleshooting, and the ethics
framing to deliver.

- **Live lab:** `https://brute-force-lab-m6q2.onrender.com`
- **Class gate:** username `student`, password = the one you set as
  `LAB_GATE_PASSWORD` on Render (currently `brute2026`).
- **Companion docs:** [STUDENT_GUIDE.md](STUDENT_GUIDE.md) (hand to students),
  [LEVEL_MANUAL.md](LEVEL_MANUAL.md) (level-by-level attack walkthrough),
  [README.md](README.md) (setup/hosting).

> ⚠️ This app is **deliberately insecure**. It exists only to be attacked by
> your students in a controlled setting. Keep it behind the class gate, and
> never reuse its code in a real application.

---

## 1. What the lab teaches

### Learning objectives
By the end of the session a student should be able to:

1. **Explain** what an online password brute-force / dictionary attack is and
   how it differs from an offline hash-cracking attack.
2. **Enumerate** valid usernames by reading verbose error messages.
3. **Run** an automated dictionary attack with at least one tool (Hydra, ffuf,
   Burp Suite Intruder, or a Python script).
4. **Describe** four defensive controls — none, throttling, anti-automation
   tokens, account lockout — and evaluate how effective each is.
5. **Argue** which control they would add to a real login form first, and why,
   including the trade-offs (e.g. lockout enabling denial-of-service).

### The core idea you are teaching
A login form is a guessing game. The attacker's success depends on two things:
**how weak the password is**, and **how many guesses per second the defender
allows**. Each level of the lab changes one of those variables so students
*feel* the effect rather than just hearing about it.

| Level | Defense | What variable it changes | Headline lesson |
|-------|---------|--------------------------|-----------------|
| `low` | none | nothing (baseline) | Weak passwords fall instantly. |
| `medium` | 1.5s delay per attempt | guesses per second ↓ | Throttling is a speed bump, not a wall. |
| `high` | per-request token | automation difficulty ↑ | Tokens stop dumb bots, not scripted attackers. |
| `impossible` | lockout after 5 fails / 30s | total guesses allowed ↓↓ | Lockout is what actually defeats online brute force. |

---

## 2. How the system is built (architecture)

You do not need to be a Flask expert to run the class, but understanding the
pieces lets you explain the app, answer "how does it know?" questions, and fix
problems live.

### File map
```
app.py                 The whole application: gate, 4 levels, lockout logic
templates/
  base.html            Page shell (nav, flash messages, styling hook)
  index.html           Home page + difficulty selector
  login.html           The target login form (renders user_token on 'high')
static/style.css       Dark theme
wordlists/
  passwords.txt        ~18 passwords incl. the lab answers (for class use)
  usernames.txt        Candidate usernames
requirements.txt       Flask + gunicorn
render.yaml            Render Blueprint (service definition + env vars)
Procfile / Dockerfile / docker-compose.yml   Alternative hosting
README.md              Setup + hosting
STUDENT_GUIDE.md       Quick attack walkthrough for students
LEVEL_MANUAL.md        Full per-level attack manual for students
INSTRUCTOR_MANUAL.md   This document
```

### Routes (what each URL does)
| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | Home page; shows current level and the difficulty selector. |
| `/set-level/<level>` | GET | Sets the student's difficulty (stored in their session). |
| `/login` | GET/POST | The target. GET shows the form; POST processes a guess. |
| `/logout` | GET | Clears the "logged in" marker. |
| `/reset-lockouts` | GET | **Instructor tool** — clears all lockout counters. |
| `/healthz` | GET | Uptime check; returns `{"status":"ok","commit":"<sha>"}`. |

### How per-student state works (important for a shared class)
The lab is **one instance shared by the whole class**, but each student gets
their own experience through a **signed Flask session cookie**:

- The chosen **difficulty level** is stored in each student's cookie, so one
  student on `high` doesn't change another student's level.
- The **`high`-level token** is stored per session too.
- The cookie is cryptographically signed with `LAB_SECRET_KEY` (set on Render),
  so students can't forge it.

The **lockout counters** (`impossible` level) are the exception — they are
shared server-side in a small SQLite file, keyed by the *username being
attacked*. That is deliberate: a lockout must apply to the account no matter who
is attacking it or how many server workers are running (see §4.4).

### The lab accounts (answer key)
Weak on purpose — all present in common wordlists:

| Username | Password |
|----------|----------|
| `admin` | `password` |
| `gordonb` | `abc123` |
| `1337` | `charley` |
| `pablo` | `letmein` |
| `smithy` | `password` |
| `student` | `123456` |

On success the form reveals
`FLAG{brute_force_is_only_as_strong_as_the_weakest_password}`. Students capture
the flag to prove they got in; you can verify screenshots against it.

> **Teaching choice:** share only `admin` and make them enumerate the rest, or
> hand out the whole list. Enumeration-first is the better exercise.

---

## 3. How each defense works under the hood

This is the part you teach from. For each level: the one-line mechanism, the
code behind it, how the attack beats it, and the real-world analogue.

### 3.1 LOW — no protection
- **Mechanism:** none. The POST handler just checks the credentials and returns.
- **Verbose error (applies to all levels):** the app says
  `Password incorrect for that user.` when the username exists but the password
  is wrong, and `Username and/or password incorrect.` when the username doesn't
  exist. **This is a real vulnerability** — it lets an attacker confirm which
  usernames are valid before ever guessing a password.
- **Attack:** fire a wordlist at `/login`; the correct password returns the
  flag. Succeeds in seconds.
- **Real world:** a login form with no rate limiting and weak passwords. Still
  depressingly common.

### 3.2 MEDIUM — rate throttling
- **Mechanism:** the server calls `time.sleep(1.5)` on **every** attempt before
  responding.
- **Attack:** *the exact same attack as LOW* — it just runs slower. Students
  time it and extrapolate: at ~1.5s/guess, a 10,000-word list ≈ 4 hours.
- **Teaching point:** throttling raises the *cost* and buys defenders time (and
  log visibility), but a patient attacker still gets in. It is a speed bump.
- **Real world:** per-IP or per-account rate limits, `fail2ban`-style delays.

### 3.3 HIGH — per-request anti-automation token
- **Mechanism:** the login form embeds a hidden `user_token` (a random hex
  string) that is **unique to each page load**. On POST, the server checks the
  submitted token against the one it issued, then **rotates** it (issues a new
  one) so the same token can never be reused. A POST without a fresh, valid
  token is rejected with `Invalid or missing request token.` *before* the
  password is even checked.
- **Why naive tools fail:** a tool that just replays `username=...&password=...`
  never supplies a valid token, so every guess is rejected — the attacker tests
  zero passwords.
- **Attack (the right way):** a **GET → scrape token → POST with token** loop.
  In Python, regex the token out of the page; in Burp Intruder, use the
  **Recursive grep** payload type to feed each response's token into the next
  request.
- **Teaching point:** per-request tokens (the same idea as anti-CSRF tokens)
  defeat *casual* automation and CSRF, but **not** a determined attacker who
  scripts the token scraping. Tokens are a bar-raiser, not a wall.
- **Real world:** CSRF tokens, some "are you a human" form nonces.

### 3.4 IMPOSSIBLE — account lockout
- **Mechanism:** after **5 failed attempts** on a username, that account is
  **locked for 30 seconds**. While locked, the server refuses the login *before*
  checking the password — so **even the correct password is rejected**. A
  successful login (once unlocked) clears the counter.
- **Attack:** there isn't a working one online. A dictionary attack hits the
  lock at attempt 5, long before reaching the real password. This is the point:
  the students' attack is *supposed to fail here*.
- **The catch (great discussion):** lockout lets an attacker **deny service** —
  deliberately lock out legitimate users by feeding wrong passwords. Mitigations
  to raise: lock by IP+account, exponential backoff instead of hard lock,
  CAPTCHA after N fails, or MFA so the password alone isn't enough.
- **Thresholds are tunable** via env vars (`LOCKOUT_THRESHOLD`,
  `LOCKOUT_SECONDS`) — see §7.
- **Real world:** account lockout, exponential backoff, CAPTCHA, MFA — the
  controls that genuinely stop *online* brute force.

> **Why "impossible"?** It's DVWA's naming. It means "impossible to beat with a
> naive online dictionary attack," *not* "perfectly secure." Make that
> distinction explicitly — it's a teachable nuance.

---

## 4. Running the lab (operations)

### 4.1 Before class — pre-flight checklist
1. **Wake the service.** Render's free tier sleeps after ~15 min idle and takes
   ~30–50s to cold-start. Hit the URL (or `/healthz`) a minute before class so
   the first student doesn't wait.
2. **Confirm what's live.** Visit `https://brute-force-lab-m6q2.onrender.com/healthz`
   — it returns `{"status":"ok","commit":"<sha>"}`. The `commit` field tells you
   exactly which code version is running.
3. **Reset lockouts.** Visit `/reset-lockouts` (you'll need the class gate) to
   clear any leftover `impossible` counters from testing.
4. **Have the class gate password ready** to give students.

### 4.2 The class gate (access control)
Because this is a live, intentionally-vulnerable target on the public internet,
every page (except `/healthz`) sits behind **HTTP basic auth**:

- Controlled by env vars `LAB_GATE_USER` (default `student`) and
  `LAB_GATE_PASSWORD` (currently `brute2026`), set on Render.
- Students get a browser popup; they enter the gate username + password **once**
  per browser session, then use the lab normally.
- **The gate is not the target.** Make this crystal clear or students will try
  to brute-force the popup. The gate just keeps strangers out; the *lab login
  form* is what they attack.
- Command-line tools pass the gate with basic auth, e.g.
  `curl -u student:brute2026 ...`. Burp inherits it from the browser.

To **change the gate password:** Render dashboard → the service →
**Environment** → edit `LAB_GATE_PASSWORD` → save (triggers a redeploy).

### 4.3 Instructor controls during class
- **Reset all lockouts:** `GET /reset-lockouts` (e.g. between the `impossible`
  exercise and a re-run, or if a student locks `admin` for everyone).
- **Levels are per student**, so you don't need to coordinate — each student
  sets their own via the home page or `/set-level/<level>`.
- **Check the running version any time:** `/healthz` → `commit` field.

### 4.4 A note you may be asked about: multi-worker lockout
The lockout counters live in a shared SQLite file, **not** a Python variable.
Here's why, in case a sharp student asks: a production server runs several
worker processes; an in-memory counter would give each worker its *own* count,
so "5 strikes" would effectively never trigger. A shared file (with atomic
increments and WAL mode) makes every worker agree on the count. This is itself a
nice real-world lesson about **shared state in distributed systems**. (It was
also a real bug we fixed while building this — see §8.)

---

## 5. Suggested lesson plan (≈ 90 minutes)

Adjust to your slot. This assumes students have laptops and either a browser +
Burp, or Python/`curl`.

| Time | Segment | What happens |
|------|---------|--------------|
| 0:00–0:10 | **Framing & ethics** | Define online brute force. Deliver the legality/ethics talk (§9). Everyone enters the class gate. |
| 0:10–0:20 | **Manual exploration (LOW)** | Students log in by hand with `admin`/`wrongpass`, read the **verbose error**, discover username enumeration. |
| 0:20–0:35 | **Automate (LOW)** | Each student runs one tool against `admin`, captures the flag. Circulate and help. |
| 0:35–0:45 | **MEDIUM** | Same attack, switch level, **time it**. Compute cost of a big wordlist. Discuss: speed bump vs wall. |
| 0:45–1:05 | **HIGH** | Naive attack fails. Introduce token scraping (Python regex or Burp Recursive grep). Students get a working GET→POST loop. |
| 1:05–1:20 | **IMPOSSIBLE** | Attack a user whose password is deep in the list (`1337`). Watch it lock at attempt 5. Discuss lockout's DoS downside. |
| 1:20–1:30 | **Debrief & worksheet** | Fill the comparison table (§6). Final question: one control to add first, and why. |

**Shorter 50-min version:** do LOW + MEDIUM + IMPOSSIBLE manually, demo HIGH
yourself, skip the deep Burp setup.

---

## 6. Answer key & worksheet solutions

### Per-level answer key
| Level | Does the attack succeed? | Why |
|-------|--------------------------|-----|
| low | **Yes**, in seconds | No controls; weak password in the wordlist. |
| medium | **Yes**, but slow | Only throttled; still fully brute-forceable. |
| high | **Yes**, with token scraping | Token stops naive tools, not a scripted GET→POST loop. |
| impossible | **No** (online) | Locks at 5 attempts before the password is reached. |

### Fastest credential to crack
`admin` / `password` — `password` is near the top of `wordlists/passwords.txt`,
so LOW/MEDIUM crack it in the first few guesses. Good for a quick demo.

### The worksheet's final question
There is no single "right" answer — grade the **reasoning**. A strong answer
picks **lockout/backoff or MFA** as most impactful against online brute force,
*and* acknowledges a trade-off (lockout → DoS risk; MFA → user friction).
Picking "strong passwords" is also defensible (it attacks the root cause) if
they note you can't force users to choose well without policy + a check.

### Full attack solutions
The copy-paste commands for every level (Python, ffuf, Hydra, Burp) live in
[LEVEL_MANUAL.md](LEVEL_MANUAL.md). That file is written *for students*; as the
lecturer, skim it so you can unblock anyone. Key reminders:

- Every command-line tool needs the gate: `-u student:brute2026` (curl/ffuf) or
  the equivalent basic-auth header; Burp inherits it from the browser.
- Success detection: response contains `FLAG{` (or simply lacks `incorrect`).
- On HIGH, you **must** GET a fresh `user_token` before each POST.

---

## 7. Tuning & maintenance

### Change lockout difficulty (no code edit needed)
Set these env vars on Render (**Environment** tab) and redeploy:

| Variable | Default | Effect |
|----------|---------|--------|
| `LOCKOUT_THRESHOLD` | `5` | Failed attempts before lock. |
| `LOCKOUT_SECONDS` | `30` | How long the lock lasts. |

Lower the threshold to make `impossible` bite sooner; raise `LOCKOUT_SECONDS`
for a more dramatic demo.

### Change / add lab accounts
Edit the `USERS` dictionary in [app.py](app.py) and the `FLAG` string if you
want a different flag, then commit and deploy (§8). To make the lab harder,
remove the weakest passwords from `wordlists/passwords.txt` or use a longer
real-world list.

### Change the class gate
See §4.2 — it's just the `LAB_GATE_PASSWORD` env var.

### Other env vars
| Variable | Purpose |
|----------|---------|
| `LAB_SECRET_KEY` | Signs session cookies. Render generates one automatically. |
| `LAB_GATE_USER` / `LAB_GATE_PASSWORD` | The class gate (both must be set to enable it). |
| `LOCKOUT_DB` | Path to the lockout SQLite file (defaults to a temp dir). |

---

## 8. Deploying changes

The lab is hosted on **Render**, deployed from GitHub.

1. Make your edit locally (e.g. change `USERS` in `app.py`).
2. Commit and push to the repo's `main` branch.
3. **Deploy:**
   - If **Auto-Deploy** is on (Render → service → **Settings → Build &
     Deploy**), the push deploys itself.
   - If not, Render → service → **Manual Deploy** (top right) → **Deploy latest
     commit**.
4. **Verify** it went live: `GET /healthz` and check the `commit` field matches
   your new commit's short SHA.

> **render.yaml changes are different.** Editing `render.yaml` (the Blueprint —
> start command, env var definitions) needs a **Blueprint sync**, not just a
> push. Plain code changes (`app.py`, templates) deploy normally.

---

## 9. Ethics & legal framing (deliver this to students)

Say this out loud before any attacking starts. It is the most important part.

- **Only attack this lab.** Brute-forcing, scanning, or otherwise testing any
  system you do not **own** or have **explicit written authorization** to test
  is a crime in most jurisdictions (e.g. the Computer Misuse Act, the CFAA, and
  equivalents). "I was just learning" is not a defense.
- **Authorization is specific.** Permission to test one system is not permission
  to test another. Real penetration testers work from a signed scope document.
- **The techniques are dual-use.** The exact skills in this lab are what
  defenders use to test their own systems and what attackers use to break in.
  The difference is **authorization**, full stop.
- **Why we teach it anyway:** you can't defend against what you don't
  understand. Seeing how trivially a weak password falls is the fastest way to
  understand why strong passwords, lockout, and MFA matter.
- **Take the defensive lesson home:** use a password manager, unique passwords,
  and MFA on your own accounts.

---

## 10. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| First request hangs ~30–50s | Free-tier cold start (service was asleep) | Normal. Pre-warm before class by hitting the URL. |
| Students can't load the page at all | They haven't passed the class gate | Give them the gate username (`student`) + password; it's the browser popup. |
| A student says "the popup won't accept my password" | They're trying to *attack* the gate | Clarify: the gate is the door; the **login form** inside is the target. |
| `impossible` never locks | Old code deployed | Check `/healthz` `commit`; redeploy the latest commit (§8). (This is fixed in current code.) |
| Lock seems stuck / students locked each other out | Shared counters by username | Visit `/reset-lockouts` to clear all. |
| HIGH attack rejects every guess | No fresh `user_token` sent | Use a GET→scrape→POST loop / Burp Recursive grep (§3.3). |
| Command-line tool gets a `401` | Missing class-gate auth | Add `-u student:brute2026` (curl/ffuf) or the basic-auth header. |
| Not sure what version is live | — | `GET /healthz` → read the `commit` field. |

### Verify the whole lab quickly (instructor smoke test)
From any machine with `curl` (replace the password if you changed it):

```bash
BASE=https://brute-force-lab-m6q2.onrender.com
AUTH=student:brute2026
# version check
curl -s -u $AUTH $BASE/healthz
# low: crack admin (should return a page containing FLAG{)
curl -s -u $AUTH -c j.txt "$BASE/set-level/low" -o /dev/null
curl -s -u $AUTH -b j.txt -d "username=admin&password=password" "$BASE/login" | grep -o "FLAG{[^}]*}"
# impossible: should lock after 5 (reset first)
curl -s -u $AUTH -b j.txt "$BASE/set-level/impossible" -o /dev/null
curl -s -u $AUTH -b j.txt "$BASE/reset-lockouts" -o /dev/null
for i in 1 2 3 4 5; do curl -s -u $AUTH -b j.txt -d "username=admin&password=x$i" "$BASE/login" | grep -o "locked for [0-9]*s" ; done
rm -f j.txt
```
You should see the flag from the LOW step and a "locked for 30s" message on the
5th impossible attempt.

---

## 11. One-page cheat sheet

- **URL:** `https://brute-force-lab-m6q2.onrender.com`
- **Gate:** `student` / `brute2026` (the door, not the target)
- **Target:** the lab's `/login` form
- **Reset locks:** `/reset-lockouts`
- **Check live version:** `/healthz` → `commit`
- **Levels:** `/set-level/low | medium | high | impossible`
- **Fastest crack:** `admin` / `password`
- **Flag:** `FLAG{brute_force_is_only_as_strong_as_the_weakest_password}`
- **Lesson in one line:** weak passwords fall; throttling slows; tokens annoy
  bots; **lockout/backoff/MFA is what actually stops online brute force.**
