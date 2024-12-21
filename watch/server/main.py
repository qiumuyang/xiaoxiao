import io
import logging
import os
import sqlite3
from datetime import datetime
from functools import wraps

import qrcode
from flask import Flask, jsonify, request, send_file
from PIL import Image, ImageDraw

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

# Environment variable for API_KEY
API_KEY = os.getenv("API_KEY")
assert API_KEY, "API_KEY must be specified"


# SQLite file-based database setup
def get_db():
    """Connect to the SQLite database (file-based)"""
    conn = sqlite3.connect(
        "app.db", check_same_thread=False
    )  # Added check_same_thread=False for multithreading
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database with a table for login_url and update_time"""
    conn = get_db()
    with conn:
        # Add the update_time column if it doesn't exist
        conn.execute("""
            CREATE TABLE IF NOT EXISTS config (
                id INTEGER PRIMARY KEY,
                login_url TEXT,
                update_time TEXT
            )
        """)
        # Insert a default row with the current time
        conn.execute(
            """
            INSERT OR IGNORE INTO config (id, login_url, update_time)
            VALUES (1, '', ?)
        """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ))
    conn.close()


# Initialize DB
with app.app_context():
    """Call init_db() before the first request is handled"""
    init_db()


def require_api_key(func):
    """Decorator to require API key"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        if request.headers.get("X-API-KEY") != API_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        return func(*args, **kwargs)

    return wrapper


@app.before_request
def log_request_info():
    """Log incoming requests"""
    logging.info(f"Request: {request.method} {request.url}")


@app.route("/update", methods=["POST"])
@require_api_key
def update_login_url():
    """Update the login URL and the update_time in the database"""
    data = request.json
    if not data or "url" not in data:
        return jsonify({"error": "URL is required"}), 400

    login_url = data["url"]
    update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db()
    with conn:
        conn.execute(
            """
            UPDATE config
            SET login_url = ?, update_time = ?
            WHERE id = 1
        """, (login_url, update_time))
    conn.close()

    return jsonify({
        "message": "Login URL updated successfully",
        "url": login_url,
        "update_time": update_time
    }), 200


@app.route("/", methods=["GET"])
def get_qrcode():
    """Generate and return the QR code for the login URL"""
    conn = get_db()
    cursor = conn.execute(
        "SELECT login_url, update_time FROM config WHERE id = 1")
    result = cursor.fetchone()
    conn.close()

    login_url = result["login_url"]
    update_time = result["update_time"]

    if not login_url:
        return jsonify({"error": "Login URL not updated yet."}), 404

    # Generate QR code for the URL
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.ERROR_CORRECT_L,
        box_size=10,
        border=2,
    )
    qr.add_data(login_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").get_image()
    canvas = Image.new("RGB", (img.width, img.height + 10), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    draw.text((0, 0), text=update_time, fill=(0, 0, 0))
    canvas.paste(img, (0, 10))

    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")  # type: ignore
    buffer.seek(0)

    return send_file(buffer, mimetype="image/png")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
