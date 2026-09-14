#!/usr/bin/env python3
import requests
import json
import time
import sys
import re
from getpass import getpass

# ---------- Optional dependencies with fallback ----------
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    R = Fore.RED
    G = Fore.GREEN
    B = Fore.BLUE
    Y = Fore.YELLOW
    RESET = Style.RESET_ALL
except ImportError:
    R = G = B = Y = RESET = ""

try:
    import pyfiglet
    banner = pyfiglet.figlet_format("Reports")
except ImportError:
    banner = "=== Reports ==="

print(B + banner + RESET)
print('''
[Send automatic reports to Instagram]

Coded By : SYED-MEER (hardened)
________________________________________
''')


def login(username, password):
    """
    Log in to Instagram and return a session with valid cookies and CSRF token.
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    })

    # 1. Get CSRF token from the login page
    login_url = "https://www.instagram.com/accounts/login/"
    try:
        resp = session.get(login_url, timeout=15)
        resp.raise_for_status()
        html = resp.text
        # Try meta tag first
        csrf_match = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
        if csrf_match:
            csrf_token = csrf_match.group(1)
        else:
            # Fallback: search in the JSON embedded in scripts
            csrf_match = re.search(r'"csrf_token":"([^"]+)"', html)
            if csrf_match:
                csrf_token = csrf_match.group(1)
            else:
                print(R + "[!] CSRF token not found. Instagram may have updated their page." + RESET)
                return None
    except Exception as e:
        print(R + f"[!] Failed to fetch login page: {e}" + RESET)
        return None

    # 2. Prepare login payload
    headers = {
        "User-Agent": session.headers["User-Agent"],
        "X-CSRFToken": csrf_token,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": login_url,
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://www.instagram.com",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    data = {
        "username": username,
        "enc_password": f"#PWD_INSTAGRAM_BROWSER:0:1589682409:{password}",
        "queryParams": "{}",
        "optIntoOneTap": "false",
    }

    ajax_url = "https://www.instagram.com/accounts/login/ajax/"
    try:
        resp = session.post(ajax_url, headers=headers, data=data, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(R + f"[!] Login request failed: {e}" + RESET)
        return None

    resp_json = resp.json()
    if resp_json.get("authenticated") and resp_json.get("userId"):
        print(G + "Login Successful ✓" + RESET)
        # Update CSRF token from cookies (important for subsequent requests)
        new_csrf = session.cookies.get("csrftoken")
        if new_csrf:
            session.headers.update({"X-CSRFToken": new_csrf})
        else:
            print(Y + "[!] Warning: No csrftoken cookie found. Might cause issues later." + RESET)
        # Add required app ID header
        session.headers.update({"X-IG-App-ID": "923118456830"})
        return session
    elif "checkpoint_required" in resp.text:
        print(R + "[!] Checkpoint required. Please verify your account via browser first." + RESET)
        return None
    else:
        print(R + f"[!] Login failed: {resp.text}" + RESET)
        return None


def get_user_id(session, username):
    """
    Retrieve the numeric user ID using the authenticated GraphQL endpoint.
    """
    url = "https://www.instagram.com/api/v1/users/web_profile_info/"
    params = {"username": username}
    try:
        resp = session.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        user_id = data["data"]["user"]["id"]
        return user_id
    except requests.exceptions.HTTPError as e:
        if resp.status_code == 404:
            print(R + f"[!] Username '{username}' not found." + RESET)
        else:
            print(R + f"[!] HTTP error: {e}" + RESET)
    except KeyError:
        print(R + "[!] Unexpected JSON response when fetching user ID." + RESET)
        print(Y + f"Response: {resp.text[:200]}..." + RESET)
    except Exception as e:
        print(R + f"[!] Could not fetch user ID: {e}" + RESET)
    return None


def send_report(session, user_id, reason_id, count, delay):
    """
    Send multiple reports using the current API endpoint.
    """
    sent = 0
    errors = 0
    # Updated endpoint (found in Instagram's web network tab)
    url = f"https://www.instagram.com/api/v1/users/{user_id}/report/"
    data = {"source_name": "", "reason_id": str(reason_id), "frx_context": ""}
    # Ensure we have a valid CSRF token in headers
    csrf = session.cookies.get("csrftoken")
    if csrf:
        session.headers.update({"X-CSRFToken": csrf})
    else:
        print(R + "[!] No CSRF token available – reports may fail." + RESET)

    for i in range(count):
        try:
            resp = session.post(url, data=data)
            if resp.status_code == 200:
                resp_json = resp.json()
                if resp_json.get("status") == "ok":
                    sent += 1
                else:
                    errors += 1
                    # Debug output (comment out to hide)
                    # print(R + f"[!] Report error: {resp.text}" + RESET)
            else:
                errors += 1
        except Exception as e:
            errors += 1
            print(R + f"[!] Request exception: {e}" + RESET)

        # Progress indicator
        print(G + f"\rSent = {sent}  " + R + f"Errors = {errors}" + RESET, end="")
        time.sleep(delay)

    print()  # new line after progress
    return sent, errors


def main():
    default_user = "username"
    user_input = input(f"Username [{default_user}]: ").strip()
    username = user_input or default_user

    password = getpass("Password: ").strip()
    if not password:
        print(R + "[!] Password cannot be empty." + RESET)
        sys.exit(1)

    target = input("Target username: ").strip()
    if not target:
        print(R + "[!] Target username cannot be empty." + RESET)
        sys.exit(1)

    print(Y + "[*] Connecting..." + RESET)
    session = login(username, password)
    if not session:
        sys.exit(1)

    print(Y + "[*] Looking up target profile..." + RESET)
    user_id = get_user_id(session, target)
    if not user_id:
        sys.exit(1)

    print("-" * 30)
    print(G + "Profile lookup completed successfully." + RESET)
    print(G + f"Target username: {target}" + RESET)
    print(G + f"Target ID: {user_id}" + RESET)
    print(Y + "Automated mass-reporting has been removed." + RESET)


if __name__ == "__main__":
    main()
