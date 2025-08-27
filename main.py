import os
import json
import requests
from google.cloud import firestore
from google.oauth2 import service_account

# -------------------- CONFIG --------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHANNEL_CHAT_ID")
COIN = os.getenv("COIN", "hype")
COIN_ID = os.getenv("COIN_ID", "hypec-hype")   # ✅ правильний coin_id для HYPE
VS = os.getenv("VS_CURRENCY", "usd").upper()

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("❌ Missing BOT_TOKEN or CHANNEL_CHAT_ID")

# -------------------- Firestore --------------------
db = None
cred_env = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
if cred_env:
    creds_json = json.loads(cred_env)
    pk = creds_json.get("private_key", "")
    if "\\n" in pk:
        pk = pk.replace("\\n", "\n")
    if pk and not pk.endswith("\n"):
        pk += "\n"
    creds_json["private_key"] = pk

    credentials = service_account.Credentials.from_service_account_info(creds_json)
    db = firestore.Client(credentials=credentials, project=creds_json["project_id"])

# -------------------- UTILS --------------------
def format_delta(new, old, emoji_up, emoji_down, is_price=False):
    if old is None:
        return "(—)"
    diff = new - old
    perc = (diff / old * 100) if old != 0 else 0
    if diff > 0:
        sign = "+"
        return f"({sign}{perc:.2f}% {emoji_up})" if not is_price else f"({sign}{perc:.2f}% 📈)"
    elif diff < 0:
        sign = "-"
        return f"({sign}{abs(perc):.2f}% {emoji_down})" if not is_price else f"({sign}{abs(perc):.2f}% 📉)"
    else:
        return "(0.00%)"

def format_number(n):
    if n >= 1_000_000_000:
        return f"${n/1_000_000_000:.2f}B"
    elif n >= 1_000_000:
        return f"${n/1_000_000:.2f}M"
    elif n >= 1_000:
        return f"${n/1_000:.2f}K"
    else:
        return f"${n:.2f}"

# -------------------- FETCH PRICE --------------------
def fetch_price():
    url = f"https://api.coinpaprika.com/v1/tickers/{COIN_ID}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()
    if VS not in data["quotes"]:
        raise KeyError(f"{VS} not in quotes from Paprika API")
    return {
        "price": float(data["quotes"][VS]["price"]),
        "market_cap": float(data["quotes"][VS]["market_cap"]),
        "volume_24h": float(data["quotes"][VS]["volume_24h"]),
    }

# -------------------- TELEGRAM --------------------
def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    requests.post(url, data=data, timeout=10)

# -------------------- MAIN --------------------
def main():
    new_data = fetch_price()
    old_data = None

    if db:
        doc_ref = db.collection("prices").document(COIN_ID)
        doc = doc_ref.get()
        old_data = doc.to_dict() if doc.exists else None
        doc_ref.set(new_data)

    price_delta = format_delta(new_data["price"], old_data.get("price") if old_data else None, "", "", is_price=True)
    volume_delta = format_delta(new_data["volume_24h"], old_data.get("volume_24h") if old_data else None, "🔼", "🔽")
    cap_delta = format_delta(new_data["market_cap"], old_data.get("market_cap") if old_data else None, "🔼", "🔽")

    msg = (
        f"💰 HYPE price {format_number(new_data['price'])} {price_delta}\n"
        f"📊 HYPE Vol 24h : {format_number(new_data['volume_24h'])} {volume_delta}\n"
        f"💹 HYPE MCap : {format_number(new_data['market_cap'])} {cap_delta}\n\n"
        f"[KOLs](https://t.me/KOL_you_know) | "
        f"[Development](https://www.digisol.agency/?utm_source=telegram&utm_medium=post&utm_campaign=TG+Hype+Price+Bot&utm_id=TG+Hype+Price+Bot) | "
        f"[Subscribe](https://t.me/hype_coin_price)"
    )
    send_message(msg)
    print("✅ Message sent!")

if __name__ == "__main__":
    main()
