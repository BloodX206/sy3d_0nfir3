import os
import sys
import time
import random
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import pyfiglet
except ImportError:
    os.system(f"{sys.executable} -m pip install pyfiglet")
    import pyfiglet

R = "\033[1;31m"
G = "\033[1;32m"
B = "\033[0;94m"
Y = "\033[1;33m"
C = "\033[1;36m"
W = "\033[0m"

USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# Report menu -> (label, instagram reason_id)
REASONS = {
    1: ("spam",            1),
    2: ("violence",        5),
    3: ("impersonation",   8),
    4: ("sexual activity", 3),
    5: ("harassment",      7),
    6: ("self-harm",       2),
    7: ("hate",            4),
}


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def build_session(proxy=None):
    s = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.8,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    if proxy:
        s.proxies = {"http": proxy, "https": proxy}
    return s


def get_csrf(session):
    """Fetch a fresh csrftoken from instagram.com before login."""
    r = session.get("https://www.instagram.com/",
                    headers={"User-Agent": random.choice(USER_AGENTS)},
                    timeout=15)
    # Cookie jar is authoritative
    token = session.cookies.get("csrftoken")
    if token:
        return token
    m = re.search(r'csrftoken=([^;]+)', r.headers.get("set-cookie", ""))
    return m.group(1) if m else None


def login(session, username, password):
    """Returns (user_id, None) on success or (None, error_string)."""
    csrf = get_csrf(session)
    if not csrf:
        return None, "could not obtain csrftoken"

    session.headers.update({
        "User-Agent":       random.choice(USER_AGENTS),
        "X-CSRFToken":      csrf,
        "X-IG-App-ID":      "936619743392459",
        "X-Requested-With": "XMLHttpRequest",
        "Referer":          "https://www.instagram.com/",
        "Origin":           "https://www.instagram.com",
    })

    ts = int(time.time())
    enc_password = f"#PWD_INSTAGRAM_BROWSER:0:{ts}:{password}"
    data = {
        "username":           username,
        "enc_password":       enc_password,
        "queryParams":        "{}",
        "optIntoOneTap":      "false",
        "stopDeletionNonce":  "",
        "stopDeletionTS":     "",
    }

    r = session.post(
        "https://www.instagram.com/api/v1/web/accounts/login/ajax/",
        data=data, timeout=20,
    )

    try:
        j = r.json()
    except ValueError:
        return None, f"non-JSON response ({r.status_code})"

    if j.get("authenticated") and j.get("userId"):
        return str(j["userId"]), None
    if j.get("checkpoint_url") or "checkpoint" in r.text.lower():
        return None, "checkpoint_required (verify in browser first)"
    if j.get("two_factor_required"):
        return None, "2FA required — log in manually, reuse session cookie"
    return None, j.get("message", "login failed")


def get_user_id(session, target):
    """
    ?__a=1 is dead. Current working endpoint:
    /api/v1/users/web_profile_info/?username=<handle>
    """
    session.headers.update({
        "X-IG-App-ID":      "936619743392459",
        "X-Requested-With": "XMLHttpRequest",
        "Referer":          f"https://www.instagram.com/{target}/",
    })
    r = session.get(
        f"https://www.instagram.com/api/v1/users/web_profile_info/?username={target}",
        timeout=15,
    )
    try:
        j = r.json()
    except ValueError:
        return None, f"non-JSON ({r.status_code})"
    user = (j.get("data") or {}).get("user")
    if not user:
        return None, "user not found (or blocked/private)"
    return str(user["id"]), None


def report_user(session, user_id, reason_id, max_reports, wait_sec):
    """Fire reports with jittered delay, CSRF refresh, and 429 handling."""
    sent = 0
    failed = 0
    url = f"https://www.instagram.com/api/v1/users/{user_id}/report/"
    payload = {"source_name": "", "reason_id": str(reason_id), "frx_context": ""}

    for i in range(max_reports):
        # Refresh CSRF every few requests
        if i and i % 5 == 0:
            csrf = session.cookies.get("csrftoken")
            if csrf:
                session.headers["X-CSRFToken"] = csrf
            session.headers["User-Agent"] = random.choice(USER_AGENTS)

        try:
            r = session.post(url, data=payload, timeout=15)
            if r.status_code == 429:
                print(f"\n{R}[!] Rate-limited — sleeping 60s{W}")
                time.sleep(60)
                failed += 1
            elif '"status":"ok"' in r.text:
                sent += 1
            else:
                failed += 1
        except requests.RequestException:
            failed += 1

        print(f"\r{G}Sent = {sent}  {R}Error = {failed}{W}",
              end="", flush=True)

        if i < max_reports - 1:
            jitter = random.uniform(-wait_sec * 0.3, wait_sec * 0.3)
            time.sleep(max(0.5, wait_sec + jitter))

    print()
    return sent, failed


def main():
    clear()
    banner = pyfiglet.figlet_format("SYED-MEER-xD")
    print(B + banner)
    print(f"""{C}[INSTAGRAM BANNER BY FT SYED]
Original by : SY3D-MEER / SHAH-MEER
Refactor    : ♡ 𝘐 𝘥𝘰𝘯’𝘵 𝘤𝘩𝘢𝘴𝘦 — 𝘐 𝘢𝘵𝘵𝘳𝘢𝘤𝘵. 𝘞𝘩𝘢𝘵’𝘴 𝘮𝘪𝘯𝘦 𝘸𝘪𝘭𝘭 𝘧𝘪𝘯𝘥 𝘪𝘵𝘴 𝘸𝘢𝘺 𝘣𝘢𝘤𝘬. ♡
{W}""")

    print(Y + "Log in to your Instagram account:")
    username = input(f"{C}Username : {W}").strip()
    password = input(f"{C}Password : {W}").strip()
    target   = input(f"{C}Target username : {W}").strip().lstrip("@")

    # Optional: proxy via env var IG_PROXY=http://host:port
    proxy = os.environ.get("IG_PROXY") or None
    if proxy:
        print(f"{C}[i] Using proxy: {proxy}{W}")

    session = build_session(proxy)

    uid, err = login(session, username, password)
    if err:
        print(f"{R}[!] Login failed: {err}{W}")
        return
    print(f"{G}[+] Logged in (uid={uid}){W}")

    target_id, err = get_user_id(session, target)
    if err:
        print(f"{R}[!] Target lookup failed: {err}{W}")
        return
    print(f"{G}[+] Target: {target} : {target_id}{W}")
    print(G + "*" * 30 + W)

    print(R + "Choose the type of report:")
    for k, (label, _) in REASONS.items():
        print(f"  [{k}] {label}")

    try:
        choice = int(input(f"{Y}Enter number: {W}").strip())
    except ValueError:
        print(f"{R}[!] Invalid input{W}")
        return
    if choice not in REASONS:
        print(f"{R}[!] Unknown reason{W}")
        return

    label, reason_id = REASONS[choice]
    try:
        count = int(input(f"{Y}How many reports: {W}").strip())
        wait  = float(input(f"{Y}Delay between reports (sec): {W}").strip())
    except ValueError:
        print(f"{R}[!] Invalid input{W}")
        return

    print('-' * 30)
    sent, failed = report_user(session, target_id, reason_id, count, wait)
    print(f"\n{G}[+] Done — sent={sent}  failed={failed}{W}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{R}[!] Aborted{W}")
