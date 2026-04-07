import re
import requests
import time
import threading
import os
import sys
from flask import Flask, jsonify

# Completely suppress all output
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')

# 🔐 Your credentials
BOT_TOKEN = "7783590119:AAGScPFVEreH-fvwSQNTuamGlFOGI-VDK7w"
SUPABASE_URL = "https://uizrpckqnproauqllono.supabase.co"
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVpenJwY2txbnByb2F1cWxsb25vIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUwNDc0NjQsImV4cCI6MjA5MDYyMzQ2NH0.qKVaCbH2NiksMuh85guJiRySQxykwSx-MkbWNuE-PdE"

app = Flask(__name__)
last_id = 0

def poll():
    global last_id
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            response = requests.get(url, params={"offset": last_id + 1, "timeout": 25}, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        last_id = update["update_id"]
                        text = update.get("message", {}).get("text", "")
                        
                        if text:
                            try:
                                country = (re.search(r'Country:\s*(.+)', text) or [None, None])[1]
                                country = country.strip() if country else None
                                
                                phone_full = (re.search(r'Number:\s*(.+)', text) or [None, None])[1]
                                phone_full = phone_full.strip() if phone_full else None
                                phone_last3 = re.sub(r'\D', '', phone_full)[-3:] if phone_full else None
                                
                                sender = (re.search(r'Sender:\s*(.+)', text) or [None, None])[1]
                                sender = sender.strip() if sender else None
                                
                                time_raw = (re.search(r'Date/Time:\s*(.+)', text) or [None, None])[1]
                                time_raw = time_raw.strip() if time_raw else None
                                
                                range_val = (re.search(r'Range:\s*(.+)', text) or [None, None])[1]
                                range_val = range_val.strip() if range_val else None
                                
                                msg_match = re.search(r'Message:\s*(.+)', text, re.DOTALL)
                                message_clean = msg_match.group(1).strip() if msg_match else None
                                
                                final_message = f"""Country: {country}
Number: {phone_full}
Sender: {sender}
Date/Time: {time_raw}
Range: {range_val}
Message:
{message_clean}"""
                                
                                payload = {
                                    "country": country,
                                    "phone_full": phone_full,
                                    "phone_last3": phone_last3,
                                    "sender": sender,
                                    "range": range_val,
                                    "time_raw": time_raw,
                                    "message": final_message
                                }
                                
                                requests.post(
                                    f"{SUPABASE_URL}/rest/v1/otp_logs",
                                    headers={
                                        "apikey": API_KEY,
                                        "Authorization": f"Bearer {API_KEY}",
                                        "Content-Type": "application/json"
                                    },
                                    json=payload,
                                    timeout=5
                                )
                            except:
                                pass
            else:
                time.sleep(5)
        except:
            pass
        
        time.sleep(2)

@app.route('/')
def home():
    return jsonify({"status": "ok"})

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    import logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    
    # Start bot thread
    threading.Thread(target=poll, daemon=True).start()
    
    # Get port from environment or use 8080
    port = int(os.environ.get("PORT", 8080))
    
    # Run Flask
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
