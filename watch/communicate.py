import configparser
import os
import smtplib
from ast import literal_eval
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin

import qrcode
import requests

API_KEY = os.environ["REPORT_LOGIN_API_KEY"]
REPORT_TO = os.environ["REPORT_LOGIN_HOST"]
EMAIL_CONFIG = Path(__file__).parent / "email.ini"

assert EMAIL_CONFIG.exists(), "Require email.ini in the same directory"


def notify(url: str | None):

    user_id = literal_eval(os.environ["SUPERUSERS"])[0]
    receiver = f"{user_id}@qq.com"

    config = configparser.ConfigParser()
    config.read(EMAIL_CONFIG)
    user = config["mail"]["user"]
    auth = config["mail"]["auth"]
    host = config["mail"]["host"]

    if url:
        # Generate QR code image
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        # Save QR code to a BytesIO object
        img_buffer = BytesIO()
        img.save(img_buffer, format="PNG")  # type: ignore
        img_buffer.seek(0)

    msg = MIMEMultipart()
    msg["From"] = user
    msg["To"] = receiver
    msg["Subject"] = "Lagrange.OneBot kicked"

    # Add text content
    prompt = f"Refer to {REPORT_TO} for updated qr-code."
    if url:
        text_content = MIMEText(f"Relogin URL: {url} (Expire in 2 minutes)\n" +
                                prompt)
    else:
        text_content = MIMEText(prompt)
    msg.attach(text_content)

    # Add QR code image
    if url:
        img_part = MIMEImage(
            img_buffer.read(),  # type: ignore
            name="qrcode.png",
        )
        img_part.add_header("Content-ID", "<qrcode>")
        msg.attach(img_part)

    smtp = smtplib.SMTP(host)
    smtp.login(user, auth)
    smtp.sendmail(user, receiver, msg.as_string())
    smtp.quit()


def report(url: str):
    # post to REPORT_TO/update
    target = urljoin(REPORT_TO, "update")
    r = requests.post(target,
                      headers={"X-API-KEY": API_KEY},
                      json={"url": url})
    r.raise_for_status()
