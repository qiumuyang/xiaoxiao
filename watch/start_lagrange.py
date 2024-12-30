"""This script starts Lagrange.OneBot and monitors its output.

In case of bot kicked, the script informs the admin and restarts the bot.
"""

import os
import subprocess
import time
from pathlib import Path

import dotenv
from communicate import notify, report

dotenv.load_dotenv()

assert "SUPERUSERS" in os.environ

START = "cd ~/Lagrange.Core/ && dotnet run --project Lagrange.OneBot --framework net8.0"
KICK_KW = "[WtExchangeLogic] [FATAL]: KickNTEvent"
EXPIRE_KW = "QrCode Expired, Please Fetch QrCode Again"
EXPIRE_KW2 = "QrCode State Queried: 49"  # lagrange not handled
CANCEL_KW = "QrCode Canceled, Please Fetch QrCode Again"
SSL_ERROR = "The SSL connection could not be established"


def parse_login_url(proc: subprocess.Popen):
    qr_code_lines = []
    start = False
    tolerance = 100  # lines
    while proc.poll() is None:
        assert proc.stdout is not None
        stdout = proc.stdout.readline()
        print(stdout, end="")
        if "[INFORMATION]: QrCode Fetched" in stdout:
            start = True
        if start:
            qr_code_lines.append(stdout)
        if "Please scan the QR code above" in stdout:
            break
        if SSL_ERROR in stdout:
            break
        time.sleep(0.1)
        tolerance -= 1
        if tolerance == 0:
            break
    if not start:
        return ""
    url = qr_code_lines[-1].split("Url: ")[-1].strip()
    return url


def stop_all_lagrange():
    subprocess.run("pkill -f Lagrange.OneBot", shell=True)


def restart(previous_proc: subprocess.Popen):
    stop_all_lagrange()
    time.sleep(1)
    remove = Path("~/Lagrange.Core/keystore.json").expanduser()
    if remove.exists():
        remove.unlink()
    proc = subprocess.Popen(START,
                            shell=True,
                            stdout=subprocess.PIPE,
                            text=True)
    url = parse_login_url(proc)
    return proc, url


white_list = ["Text", "Mention", "Forward", "VERBOSE"]


def start_and_watch():
    proc = subprocess.Popen(START,
                            shell=True,
                            stdout=subprocess.PIPE,
                            text=True)

    try:
        while proc.poll() is None:
            assert proc.stdout is not None
            stdout = proc.stdout.readline()
            print(stdout, end="")
            if any(w in stdout for w in white_list):
                continue
            if any(err in stdout for err in
                   [KICK_KW, EXPIRE_KW, CANCEL_KW, SSL_ERROR, EXPIRE_KW2]):
                if KICK_KW in stdout:
                    notify()
                proc, url = restart(proc)
                while not url:
                    # raise Exception("Failed to fetch QR code")
                    time.sleep(5)
                    proc, url = restart(proc)
                report(url)
            time.sleep(0.1)
    finally:
        stop_all_lagrange()


if __name__ == "__main__":
    start_and_watch()
