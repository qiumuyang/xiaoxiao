"""This script starts Lagrange.OneBot and monitors its output.

In case of bot kicked, the script informs the admin.
"""

import configparser
import os
import smtplib
import subprocess
import time
from ast import literal_eval
from pathlib import Path

import dotenv

dotenv.load_dotenv()

config_file = Path(__file__).parent / "email.ini"

assert "SUPERUSERS" in os.environ
assert config_file.exists()

START = "cd ~/Lagrange.Core/ && dotnet run --project Lagrange.OneBot --framework net8.0"


def notify():
    user_id = literal_eval(os.environ["SUPERUSERS"])[0]
    receiver = f"{user_id}@qq.com"

    config = configparser.ConfigParser()
    config.read(config_file)
    user = config["mail"]["user"]
    auth = config["mail"]["auth"]
    host = config["mail"]["host"]

    smtp = smtplib.SMTP(host)
    smtp.login(user, auth)

    mail = f"From: {user}\nTo: {receiver}\nSubject: Lagrange.OneBot kicked\n\n"
    smtp.sendmail(user, receiver, mail)
    smtp.quit()


white_list = [
    "Text",
    "Mention",
    "Forward",
    "VERBOSE",
]


def start_and_watch():
    print(literal_eval(os.environ["SUPERUSERS"])[0])
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
            if "[WtExchangeLogic] [FATAL]: KickNTEvent" in stdout:
                notify()
                break
            time.sleep(0.1)
    finally:
        proc.terminate()


if __name__ == "__main__":
    start_and_watch()
