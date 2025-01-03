"""
This script starts Lagrange.OneBot and monitors its output.

In case of bot kicked, the script notifies the admin and restarts the bot.
"""

import os
import subprocess
import time
from pathlib import Path

import dotenv
from communicate import notify, report

dotenv.load_dotenv()

assert "SUPERUSERS" in os.environ, "SUPERUSERS environment variable is required!"

START_COMMAND = ("cd ~/Lagrange.Core/ && "
                 "dotnet run --project Lagrange.OneBot --framework net8.0")
KEYSTORE_PATH = Path("~/Lagrange.Core/keystore.json").expanduser()
QR_CODE_FETCHED = "[INFORMATION]: QrCode Fetched"
QR_CODE_PROMPT = "Please scan the QR code above"
KICK_EVENT = "[WtExchangeLogic] [FATAL]: KickNTEvent"
ERROR_KEYWORDS = [
    KICK_EVENT,
    "QrCode Expired, Please Fetch QrCode Again",
    "QrCode State Queried: 49",
    "QrCode Canceled, Please Fetch QrCode Again",
]
WHITE_LIST = ["Text", "Mention", "Forward", "VERBOSE"]
RESTART_DELAY = 5


def parse_login_url(proc: subprocess.Popen) -> str:
    """
    Extracts the login URL from the bot's stdout if a QR code is fetched.

    Args:
        proc (subprocess.Popen): The running subprocess for the bot.

    Returns:
        str: The login URL or an empty string if parsing fails.
    """
    qr_code_lines = []
    start = False
    tolerance = 100  # Maximum lines to read for QR code fetching
    while proc.poll() is None:
        line = proc.stdout.readline() if proc.stdout else ""
        print(line, end="")  # Log output
        if QR_CODE_FETCHED in line:
            start = True
        if start:
            qr_code_lines.append(line)
        if QR_CODE_PROMPT in line:
            break
        time.sleep(0.1)
        tolerance -= 1
        if tolerance == 0:
            break
    if not start or not qr_code_lines:
        return ""
    return qr_code_lines[-1].split("Url: ")[-1].strip()


def stop_all_lagrange():
    """Stops all running instances of Lagrange.OneBot."""
    subprocess.run("pkill -f Lagrange.OneBot", shell=True, check=False)


def restart(relogin: bool = True) -> tuple[subprocess.Popen, str]:
    """
    Restarts the bot, optionally clearing the keystore for re-login.

    Args:
        relogin (bool): Whether to clear the keystore for a fresh login.

    Returns:
        tuple: The restarted process and login URL (if applicable).
    """
    stop_all_lagrange()
    time.sleep(1)
    if relogin and KEYSTORE_PATH.exists():
        KEYSTORE_PATH.unlink()
    proc = subprocess.Popen(START_COMMAND,
                            shell=True,
                            stdout=subprocess.PIPE,
                            text=True)
    url = parse_login_url(proc)
    return proc, url


def start_and_watch():
    """
    Starts the bot and monitors its output for specific events.
    Restarts the bot if necessary.
    """
    proc = subprocess.Popen(START_COMMAND,
                            shell=True,
                            stdout=subprocess.PIPE,
                            text=True)
    try:
        while proc.poll() is None:
            line = proc.stdout.readline() if proc.stdout else ""
            print(line, end="")  # Log output
            if any(keyword in line for keyword in WHITE_LIST):
                continue
            if any(error in line for error in ERROR_KEYWORDS):
                if KICK_EVENT in line:
                    notify()  # Notify admin
                proc, url = restart()
                while not url:
                    time.sleep(RESTART_DELAY)
                    proc, url = restart()
                report(url)  # Report login URL
            time.sleep(0.1)
    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        stop_all_lagrange()


if __name__ == "__main__":
    start_and_watch()
