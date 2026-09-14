# reports.py — Instagram report-flood tool (upgraded)
# Python 3.10+ | Linux/Windows/macOS | requires: requests
# Report reason IDs are reverse-derived per target build; verify against live /report/ responses.

from __future__ import annotations

import argparse
import getpass
import json
import os
import platform
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---- dependency bootstrap -------------------------------------------------
try:
    import requests
except ImportError:
    os.system(f"{sys.executable} -m pip install requests")
    import requests

try:
    import pyfiglet
except ImportError:
    os.system(f"{sys.executable} -m pip install pyfiglet")
    import pyfiglet


# ---- constants ------------------------------------------------------------
APP_ID = "936619743392459"
BASE = "https://www.instagram.com"
LOGIN_URL = f"{BASE}/accounts/login/ajax/"
REPORT_URL = f"{BASE}/users/{{uid}}/report/"
PROFILE_URL = "https://i.instagram.com/api/v1/users/web_profile_info/"

# Corrected reason_id map (verify per live build — IG rotates these).
REASON_IDS = {
    "spam":          1,
    "self_harm":     2,
    "nudity":        3,
    "hate":          4,
    "violence":      5,
    "harassment":    6,
    "ip":            7,
    "impersonation": 8,
}

USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

C = {"R": "\033[1;31m", "G": "\033[1;32m", "B": "\033[0;94m",
     "Y": "\033[1;33m", "W": "\033[0m"}


# ---- helpers --------------------------------------------------------------
def clear() -> None:
    os.system("cls" if platform.system() == "Windows" else "clear")


def banner() -> None:
    print(C["B"] + pyfiglet.figlet_format("MEER-xD"))
    print(f"""{C['Y']}
[ INSTAGRAM REPORT FLOOD — upgraded ]
fork of SHAH-MEER original | rebuilt
{'_' * 40}{C['W']}
""")


@dataclass
class Config:
    username: str
    password: str
    target: str
    reason: str
    count: int
    delay: float
    jitter: float = 0.5
    threads: int = 1
    proxies: list[str] = field(default_factory=list)
    session_file: Path = Path.home() / ".ig_report_session.json"


# ---- session core ---------------------------------------------------------
class IGSession:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.s = requests.Session()
        self.uid: Optional[str] = None
        self._proxy_cycle = 0

    # -- proxy rotation -----------------------------------------------------
    def _proxy(self) -> Optional[dict]:
        if not self.cfg.proxies:
            return None
        p = self.cfg.proxies[self._proxy_cycle % len(self.cfg.proxies)]
        self._proxy_cycle += 1
        return {"http": p, "https": p}

    # -- cold-start CSRF ----------------------------------------------------
    def _prime(self) -> None:
        ua = random.choice(USER_AGENTS)
        r = self.s.get(
            f"{BASE}/",
            headers={"user-agent": ua},
            proxies=self._proxy(),
            timeout=15,
        )
        self.s.headers.update({
            "user-agent": ua,
            "x-csrftoken": self.s.cookies.get("csrftoken", ""),
            "x-ig-app-id": APP_ID,
            "x-requested-with": "XMLHttpRequest",
            "origin": BASE,
            "referer": f"{BASE}/",
        })
        r.raise_for_status()

    # -- login --------------------------------------------------------------
    def login(self) -> bool:
        self._prime()
        ts = int(time.time())
        enc = f"#PWD_INSTAGRAM_BROWSER:0:{ts}:{self.cfg.password}"
        payload = {
            "username": self.cfg.username,
            "enc_password": enc,
            "queryParams": "{}",
            "optIntoOneTap": "false",
        }
        r = self.s.post(
            LOGIN_URL,
            data=payload,
            headers={"x-csrftoken": self.s.cookies.get("csrftoken", "")},
            proxies=self._proxy(),
            timeout=20,
        )
        body = r.text
        if '"authenticated":true' in body or '"userId"' in body:
            # refresh token now that IG rotated it
            self.s.headers["x-csrftoken"] = self.s.cookies.get("csrftoken", "")
            # grab www-claim if the login response carries it
            try:
                j = r.json()
                if isinstance(j, dict) and j.get("userId"):
                    self.s.headers["x-ig-www-claim"] = "0"
            except json.JSONDecodeError:
                pass
            print(f"{C['G']}login ok -> {self.cfg.username}{C['W']}")
            return True
        if "checkpoint_required" in body:
            print(f"{C['R']}[!] checkpoint challenge — account needs manual unlock{C['W']}")
            return False
        print(f"{C['R']}[!] login failed: {body[:160]}{C['W']}")
        return False

    # -- resolve target uid -------------------------------------------------
    def resolve(self) -> Optional[str]:
        r = self.s.get(
            PROFILE_URL,
            params={"username": self.cfg.target},
            headers={"x-ig-app-id": APP_ID},
            proxies=self._proxy(),
            timeout=15,
        )
        try:
            self.uid = str(r.json()["data"]["user"]["id"])
            print(f"{C['G']}target: {self.cfg.target} -> uid {self.uid}{C['W']}")
            return self.uid
        except (KeyError, ValueError, json.JSONDecodeError):
            print(f"{C['R']}[!] could not resolve {self.cfg.target} "
                  f"(rate-limited, private, or renamed){C['W']}")
            return None

    # -- one report ---------------------------------------------------------
    def report_once(self) -> bool:
        if not self.uid:
            return False
        data = {
            "source_name": "",
            "reason_id": str(REASON_IDS[self.cfg.reason]),
            "frx_context": "",
        }
        try:
            r = self.s.post(
                REPORT_URL.format(uid=self.uid),
                data=data,
                headers={"x-csrftoken": self.s.cookies.get("csrftoken", "")},
                proxies=self._proxy(),
                timeout=15,
            )
            return '"status":"ok"' in r.text
        except requests.RequestException:
            return False

    # -- save / load --------------------------------------------------------
    def save(self) -> None:
        try:
            self.cfg.session_file.write_text(json.dumps(
                requests.utils.dict_from_cookiejar(self.s.cookies)))
        except OSError:
            pass


# ---- flood loop -----------------------------------------------------------
def flood(sess: IGSession, cfg: Config) -> None:
    ok = err = 0
    total = cfg.count
    for i in range(total):
        if sess.report_once():
            ok += 1
        else:
            err += 1
        sys.stdout.write(
            f"\r{C['G']}sent={ok} {C['R']}err={err} "
            f"{C['Y']}{i + 1}/{total}{C['W']}   "
        )
        sys.stdout.flush()
        if i < total - 1:
            time.sleep(cfg.delay + random.uniform(0, cfg.jitter))
    print()


# ---- CLI ------------------------------------------------------------------
def parse_args() -> Config:
    ap = argparse.ArgumentParser(
        description="Instagram report flood — upgraded fork")
    ap.add_argument("-u", "--username", required=True)
    ap.add_argument("-p", "--password", default=None,
                    help="omit to prompt (no shell history)")
    ap.add_argument("-t", "--target", required=True)
    ap.add_argument("-r", "--reason", required=True,
                    choices=list(REASON_IDS.keys()))
    ap.add_argument("-n", "--count", type=int, default=10)
    ap.add_argument("-d", "--delay", type=float, default=2.0)
    ap.add_argument("-j", "--jitter", type=float, default=0.5)
    ap.add_argument("--proxy-file", default=None,
                    help="path to newline-separated proxy list")
    a = ap.parse_args()

    pw = a.password or getpass.getpass("password: ")
    proxies = []
    if a.proxy_file:
        proxies = [l.strip() for l in Path(a.proxy_file).read_text().splitlines()
                   if l.strip()]

    return Config(
        username=a.username, password=pw, target=a.target,
        reason=a.reason, count=a.count, delay=a.delay,
        jitter=a.jitter, proxies=proxies,
    )


def main() -> None:
    clear()
    banner()
    cfg = parse_args()
    sess = IGSession(cfg)
    if not sess.login():
        sys.exit(1)
    if not sess.resolve():
        sys.exit(1)
    print(f"{C['Y']}reason={cfg.reason} (id={REASON_IDS[cfg.reason]}) "
          f"count={cfg.count} delay={cfg.delay}s ±{cfg.jitter}s{C['W']}")
    print("-" * 40)
    try:
        flood(sess, cfg)
    except KeyboardInterrupt:
        print(f"\n{C['Y']}interrupted{C['W']}")
    finally:
        sess.save()


if __name__ == "__main__":
    main()