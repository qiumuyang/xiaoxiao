"""This script starts Lagrange.OneBot and monitors its output.

In case of bot kicked, the script informs the admin and restarts the bot.
"""

import configparser
import os
import smtplib
import subprocess
import time
from ast import literal_eval
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from io import BytesIO
from pathlib import Path

import dotenv
import qrcode

dotenv.load_dotenv()

config_file = Path(__file__).parent / "email.ini"

assert "SUPERUSERS" in os.environ
assert config_file.exists()

START = "cd ~/Lagrange.Core/ && dotnet run --project Lagrange.OneBot --framework net8.0"


def notify(url: str):
    user_id = literal_eval(os.environ["SUPERUSERS"])[0]
    receiver = f"{user_id}@qq.com"

    config = configparser.ConfigParser()
    config.read(config_file)
    user = config["mail"]["user"]
    auth = config["mail"]["auth"]
    host = config["mail"]["host"]

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
    text_content = MIMEText(f"Relogin URL: {url}")
    msg.attach(text_content)

    # Add QR code image
    img_part = MIMEImage(img_buffer.read(), name="qrcode.png")
    img_part.add_header("Content-ID", "<qrcode>")
    msg.attach(img_part)

    smtp = smtplib.SMTP(host)
    smtp.login(user, auth)
    smtp.sendmail(user, receiver, msg.as_string())
    smtp.quit()


def analyase(proc: subprocess.Popen):
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
        if "Please scan the QR code above, Url" in stdout:
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
    url = analyase(proc)
    return proc, url


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
                proc, qr_code = restart(proc)
                notify(qr_code or "Failed to fetch QR code")
                # TODO: in case qr_code expire?
                if not qr_code:
                    raise Exception("Failed to fetch QR code")
            time.sleep(0.1)
    finally:
        stop_all_lagrange()


if __name__ == "__main__":
    start_and_watch()
