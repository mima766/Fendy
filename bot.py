import asyncio
import re
import requests
import threading
import time
import sys
import os
from datetime import datetime
from flask import Flask, jsonify, request
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import logging

# Suppress output
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')

logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('telethon').setLevel(logging.ERROR)
logging.getLogger('requests').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)

app = Flask(__name__)

# ENV VARIABLES (Render)
API_ID = int(os.environ.get('API_ID'))
API_HASH = os.environ.get('API_HASH')
SESSION_STRING = os.environ.get('SESSION_STRING')
CHANNEL_ID = int(os.environ.get('CHANNEL_ID'))

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

recent_messages = []
last_processed_id = 0
processed_ids = set()

# =========================
# EXTRACT DATA FROM MESSAGE
# =========================
def extract_fields(text):
    try:
        country = re.search(r'Country:\s*(.+)', text)
        number = re.search(r'Number:\s*(.+)', text)
        sender = re.search(r'Sender:\s*(.+)', text)
        time_match = re.search(r'Date/Time:\s*(.+)', text)
        range_match = re.search(r'Range:\s*(.+)', text)
        message_match = re.search(r'Message:\s*(.+?)(?:\n━━|$)', text, re.DOTALL)

        phone_full = number.group(1).strip() if number else None

        phone_last3 = None
        if phone_full:
            digits = re.sub(r'\D', '', phone_full)
            if len(digits) >= 3:
                phone_last3 = digits[-3:]

        return {
            "country": country.group(1).strip() if country else None,
            "phone_full": phone_full,
            "phone_last3": phone_last3,
            "sender": sender.group(1).strip() if sender else None,
            "time_raw": time_match.group(1).strip() if time_match else None,
            "range": range_match.group(1).strip() if range_match else None,
            "message": message_match.group(1).strip() if message_match else None
        }
    except:
        return None

# =========================
# SAVE TO SUPABASE
# =========================
def save_to_supabase(text):
    try:
        extracted = extract_fields(text)
        if not extracted:
            return False

        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/otp_logs",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json"
            },
            json=extracted,
            timeout=5
        )
        return response.status_code == 201
    except:
        return False

# =========================
# TELEGRAM LISTENER
# =========================
async def telegram_listener():
    global last_processed_id, processed_ids

    if not SESSION_STRING:
        raise Exception("SESSION_STRING missing in Render ENV")

    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

    await client.connect()

    if not await client.is_user_authorized():
        raise Exception("Session not authorized")

    # Get last messages
    try:
        latest = await client.get_messages(CHANNEL_ID, limit=1)
        if latest:
            last_processed_id = latest[0].id
            async for msg in client.iter_messages(CHANNEL_ID, limit=500):
                processed_ids.add(msg.id)
    except:
        pass

    @client.on(events.NewMessage(chats=CHANNEL_ID))
    async def handler(event):
        global last_processed_id, processed_ids

        try:
            msg = event.message

            if msg.id in processed_ids or msg.id <= last_processed_id:
                return

            processed_ids.add(msg.id)
            last_processed_id = msg.id

            text = msg.text

            if text and "Country:" in text and "Number:" in text:
                age = datetime.now().timestamp() - msg.date.timestamp()
                if age > 120:
                    return

                save_to_supabase(text)

                extracted = extract_fields(text)

                recent_messages.insert(0, {
                    "id": msg.id,
                    "phone": extracted.get("phone_full") if extracted else "Unknown",
                    "time": str(msg.date)
                })

                if len(recent_messages) > 100:
                    recent_messages.pop()

        except:
            pass

    await client.run_until_disconnected()

# =========================
# THREAD STARTER
# =========================
def run_telegram():
    asyncio.run(telegram_listener())

# =========================
# FLASK ROUTES
# =========================
@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "processed": len(processed_ids)
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "messages": len(recent_messages)
    })

@app.route('/latest')
def latest():
    limit = request.args.get('limit', 10, type=int)
    return jsonify(recent_messages[:limit])

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    t = threading.Thread(target=run_telegram, daemon=True)
    t.start()

    time.sleep(5)

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
