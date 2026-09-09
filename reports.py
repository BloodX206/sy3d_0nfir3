#!/usr/bin/env python3
import requests
import json
import time
import sys
import re
from getpass import getpass

# Optional: colorful output (works on most terminals)
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

# Try to import pyfiglet for banner, fallback to plain text
try:
    import pyfiglet
    banner = pyfiglet.figlet_format("Reports")
except ImportError:
    banner = "=== Reports ==="

print(B + banner + RESET)
print('''
[Send automatic reports to Instagram]

Coded By : SYED-MEER (upgraded)
________________________________________
''')

def login(username, password):
    """Log in to Instagram and return a requests session with valid cookies."""
    session = requests.Session()
    
    # 1. Get initial CSRF token from the login page
    login_url = "https://www.instagram.com/accounts/login/"
    try:
        resp = session.get(login_url)
        csrf_token = re.search('"csrf_token":"([^"]+)"', resp.text)
        if csrf_token:
            csrf_token = csrf_token.group(1)
        else:
            print(R + "[!] Could not extract CSRF token. The page structure may have changed." + RESET)
            return None
    except Exception as e:
        print(R + f"[!] Failed to fetch login page: {e}" + RESET)
        return None

    # 2. Prepare login payload
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Mobile Safari/537.36",
        "X-CSRFToken": csrf_token,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.instagram.com/accounts/login/",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://www.instagram.com",
    }
    data = {
        "username": username,
        "enc_password": f"#PWD_INSTAGRAM_BROWSER:0:1589682409:{password}",
        "queryParams": "{}",
        "optIntoOneTap": "false",
    }

    # 3. Perform login
    ajax_url = "https://www.instagram.com/accounts/login/ajax/"
    try:
        resp = session.post(ajax_url, headers=headers, data=data)
    except Exception as e:
        print(R + f"[!] Login request failed: {e}" + RESET)
        return None

    # 4. Check response
    if resp.status_code != 200:
        print(R + f"[!] Login returned status {resp.status_code}" + RESET)
        return None

    resp_json = resp.json()
    if resp_json.get("authenticated") and resp_json.get("userId"):
        print(G + "Login Successful ✓" + RESET)
        # Update session headers with new CSRF token from cookies
        session.headers.update({"X-CSRFToken": session.cookies.get("csrftoken")})
        return session
    elif "checkpoint_required" in resp.text:
        print(R + "[!] Checkpoint required. Please verify your account via browser first." + RESET)
        return None
    else:
        print(R + f"[!] Login failed: {resp.text}" + RESET)
        return None


def get_user_id(session, username):
    """Retrieve the numeric user ID for a given Instagram username."""
    url = f"https://www.instagram.com/{username}/?__a=1"
    try:
        resp = session.get(url)
        data = resp.json()
        user_id = data["graphql"]["user"]["id"]
        return user_id
    except Exception as e:
        print(R + f"[!] Could not fetch user ID: {e}" + RESET)
        return None


def send_report(session, user_id, reason_id, count, delay):
    """
    Send multiple reports for a given reason.
    Returns (sent, errors) tuple.
    """
    sent = 0
    errors = 0
    url = f"https://www.instagram.com/users/{user_id}/report/"
    data = {"source_name": "", "reason_id": str(reason_id), "frx_context": ""}

    for i in range(count):
        try:
            resp = session.post(url, data=data)
            if resp.status_code == 200 and '"status":"ok"' in resp.text:
                sent += 1
            else:
                errors += 1
                # Optionally print error details (debug)
                # print(R + f"[!] Report error: {resp.text}" + RESET)
        except Exception as e:
            errors += 1
            print(R + f"[!] Request exception: {e}" + RESET)

        # Progress update on the same line
        print(G + f"\rSent = {sent}  " + R + f"Errors = {errors}" + RESET, end="")
        time.sleep(delay)

    print()  # newline after progress
    return sent, errors


def main():
    # Get credentials with defaults
    default_user = "shazy8690"
    default_pass = "muhibahmed206"
    user_input = input(f"Username [{default_user}]: ").strip()
    username = user_input if user_input else default_user
    pass_input = getpass(f"Password [{default_pass}]: ").strip()  # hidden input
    password = pass_input if pass_input else default_pass

    target = input("Target Id (Jatoii_shb): ").strip()
    if not target:
        print(R + "[!] Target username cannot be empty." + RESET)
        sys.exit(1)

    # Login
    session = login(username, password)
    if not session:
        sys.exit(1)

    # Get target user ID
    user_id = get_user_id(session, target)
    if not user_id:
        sys.exit(1)

    print(G + f"Target: {target} (ID: {user_id})" + RESET)
    print(G + "*" * 25 + RESET)

    # Report reasons (mapped from the original list)
    reasons = {
        1: "Spam",
        2: "Violence",
        3: "Impersonation",
        4: "Sexual activity",
        5: "Harassment",
        6: "Self-harm",
        7: "Hate speech"
    }
    print(R + "Choose the type of report:" + RESET)
    for key, val in reasons.items():
        print(f"[{key}] - {val}")
    print()

    try:
        choice = int(input("Enter the report number: "))
        if choice not in reasons:
            print(R + "[!] Invalid choice." + RESET)
            sys.exit(1)
    except ValueError:
        print(R + "[!] Please enter a number." + RESET)
        sys.exit(1)

    try:
        count = int(input(Y + "How many reports: " + RESET))
        delay = int(input(Y + "Time wait between reports (seconds): " + RESET))
    except ValueError:
        print(R + "[!] Please enter valid numbers." + RESET)
        sys.exit(1)

    print("-" * 30)
    print(G + f"Sending {count} reports for reason: {reasons[choice]} ..." + RESET)

    sent, errors = send_report(session, user_id, choice, count, delay)

    print(G + f"\nFinished. Sent: {sent}, Errors: {errors}" + RESET)


if __name__ == "__main__":
    main()    		print(G+f"\rSent = {nu}  {R}Error ={n}",end="")
    		time.sleep(tu)
    		
    elif xx == 2:
    	P2 = int(input(Y+"How many reports :"))
    	tu = int(input("time wait (sec ):"))
    	print('-'*30)
    	for i_2 in range(P2):
    		url_2=f'https://www.instagram.com/users/{id}/report/'
    		data_2={'source_name':'','reason_id':'5','frx_context':''}
    		report_2=rs.post(url_2,data=data_2)
    		if '"status":"ok"' in report_2.text:
    			nu += 1
    		else:
    			n += 1
    		print(G+f"\rSent = {nu}  {R}Error ={n}",end="")
    		time.sleep(tu)
    elif xx == 3:
    	P3 = int(input(Y+"How many reports :"))
    	tu = int(input("time wait :"))
    	print('-'*30)
    	for i_3 in range(P3):
    		url_3=f'https://www.instagram.com/users/{id}/report/'
    		data_3={'source_name':'','reason_id':'8','frx_context':''}
    		report_3=rs.post(url_3,data=data_3)
    		if '"status":"ok"' in report_3.text:
    			nu += 1
    		else:
    			n += 1
    		print(G+f"\rSent = {nu}  {R}Error ={n}",end="")
    		time.sleep(tu)
    elif xx == 4:
    	P4 = int(input(Y+"How many reports :"))
    	tu = int(input("time wait :"))
    	print('-'*30)
    	for i_4 in range(P4):
    		url_4=f'https://www.instagram.com/users/{id}/report/'
    		data_4={'source_name':'','reason_id':'4','frx_context':''}
    		report_4=rs.post(url_4,data=data_4)
    		if '"status":"ok"' in report_4.text:
    			nu += 1
    		else:
    			n += 1
    		print(G+f"\rSent = {nu}  {R}Error ={n}",end="")
    		time.sleep(tu)	
    elif xx == 5:
    	P5 = int(input(Y+"How many reports :"))
    	tu = int(input("time wait :"))
    	print('-'*30)
    	for i_5 in range(P5):
    		url_5=f'https://www.instagram.com/users/{id}/report/'
    		data_5={'source_name':'','reason_id':'7','frx_context':''}
    		report_5=rs.post(url_5,data=data_5)
    		if '"status":"ok"' in report_5.text:
    			nu += 1
    		else:
    			n += 1
    		print(G+f"\rSent = {nu}  {R}Error ={n}",end="")
    		time.sleep(tu)    		
    elif xx == 6:
    	P6 = int(input(Y+"How many reports :"))
    	tu = int(input("time wait :"))
    	print('-'*30)
    	for i_6 in range(P6):
    		url_6=f'https://www.instagram.com/users/{id}/report/'
    		data_6={'source_name':'','reason_id':'2','frx_context':''}
    		report_6=rs.post(url_6,data=data_6)
    		if '"status":"ok"' in report_6.text:
    			nu += 1
    		else:
    			n += 1
    		print(G+f"\rSent = {nu}  {R}Error ={n}",end="")
    		time.sleep(tu)
    elif xx == 7:
    	P7 = int(input(Y+"How many reports :"))
    	tu = int(input("time wait :"))
    	print('-'*30)
    	for i_7 in range(P7):
    		url_7=f'https://www.instagram.com/users/{id}/report/'
    		data_7={'source_name':'','reason_id':'6','frx_context':''}
    		report_7=rs.post(url_7,data=data_7)
    		if '"status":"ok"' in report_7.text:
    			nu += 1
    		else:
    			n += 1
    		print(G+f"\rSent = {nu}  {R}Error ={n}",end="")
    		time.sleep(tu)		
elif ('{"message":"checkpoint_required"') in r.text:
	print(R+"[!]checkpoint")
else:
	print(R+"Error, Try again")
