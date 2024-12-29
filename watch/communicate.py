import configparser
import os
import smtplib
from ast import literal_eval
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from urllib.parse import urljoin

import requests

API_KEY = os.environ["REPORT_LOGIN_API_KEY"]
REPORT_TO = os.environ["REPORT_LOGIN_HOST"]
EMAIL_CONFIG = Path(__file__).parent / "email.ini"

assert EMAIL_CONFIG.exists(), "Require email.ini in the same directory"


def notify():

    user_id = literal_eval(os.environ["SUPERUSERS"])[0]
    receiver = f"{user_id}@qq.com"

    config = configparser.ConfigParser()
    config.read(EMAIL_CONFIG)
    user = config["mail"]["user"]
    auth = config["mail"]["auth"]
    host = config["mail"]["host"]

    msg = MIMEMultipart()
    msg["From"] = user
    msg["To"] = receiver
    msg["Subject"] = "Lagrange.OneBot kicked"

    # Add text content
    prompt = f"Refer to {REPORT_TO} for updated qr-code."
    text_content = MIMEText(prompt)
    msg.attach(text_content)

    smtp = smtplib.SMTP(host)
    smtp.login(user, auth)
    errs = smtp.sendmail(user, receiver, msg.as_string())
    if errs:
        with open("email_errs.log", "a") as f:
            from datetime import datetime
            f.write(
                f"{datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S')} {errs}\n"
            )
    smtp.quit()


def report(url: str):
    # post to REPORT_TO/update
    target = urljoin(REPORT_TO, "update")
    r = requests.post(target,
                      headers={"X-API-KEY": API_KEY},
                      json={"url": url})
    r.raise_for_status()
