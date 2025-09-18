# === Multi-Pair Signal Bot (every 2-3 minutes) + Flask Stub ===
import yfinance as yf
import pandas as pd
import ta
import requests
from datetime import datetime
import pytz
import time
import threading
import os
import random
from flask import Flask

# === Config ===
PAIRS = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "JPY=X"
}

INTERVAL = '1m'
LOOKBACK = 50
RSI_PERIOD = 14
EMA_FAST = 5
EMA_SLOW = 20
BOT_TOKEN = '8405596682:AAHFDmGX_4hfk5_qIXudfJXC2wK9EpdtnxQ'   # <-- замени на свой
CHAT_ID = '-1002902970702'        # <-- замени на свой
TIMEZONE = 'America/Sao_Paulo'

# === Telegram ===
def send_telegram_signal(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': message}
    try:
        r = requests.post(url, data=payload)
        if r.status_code == 200:
            print("✅ Signal sent to Telegram!")
        else:
            print(f"❌ Telegram error {r.status_code}: {r.text}")
    except Exception as e:
        print("⚠️ Error sending message:", e)

# === Signal Logic ===
def check_signal(pair_name, pair_code):
    data = yf.download(pair_code, interval=INTERVAL, period='1d', auto_adjust=False)
    if len(data) < EMA_SLOW:
        print(f"Not enough data for {pair_name}")
        return

    df = data.tail(LOOKBACK).copy()
    df['rsi'] = ta.momentum.RSIIndicator(df['Close'], RSI_PERIOD).rsi()
    df['ema_fast'] = ta.trend.EMAIndicator(df['Close'], EMA_FAST).ema_indicator()
    df['ema_slow'] = ta.trend.EMAIndicator(df['Close'], EMA_SLOW).ema_indicator()
    macd = ta.trend.MACD(df['Close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()

    last = df.iloc[-1]

    # Простая логика: направление по EMA
    direction = "BUY" if last['ema_fast'] > last['ema_slow'] else "SELL"

    send_signal(pair_name, direction, last)

def send_signal(pair_name, direction, data):
    now = datetime.now(pytz.timezone(TIMEZONE)).strftime('%Y-%m-%d %H:%M:%S')
    msg = (
        f"✨ {direction} SIGNAL - {pair_name}\n"
        f"Time: {now} (UTC-3)\n"
        f"RSI: {data['rsi']:.2f}\n"
        f"EMA: {'Bullish' if direction == 'BUY' else 'Bearish'}\n"
        f"MACD: {data['macd']:.4f} vs {data['macd_signal']:.4f}"
    )
    send_telegram_signal(msg)

# === Bot Loop ===
def run_bot():
    print("\n📡 Multi-pair signal bot started (2–3 min mode)...")
    while True:
        try:
            for pair_name, pair_code in PAIRS.items():
                check_signal(pair_name, pair_code)
        except Exception as err:
            print("⚠️ Error in loop:", err)

        # Случайный интервал 2–3 минуты
        delay = random.randint(120, 180)
        print(f"⏳ Waiting {delay} seconds before next cycle...\n")
        time.sleep(delay)

# === Flask Stub ===
app = Flask(__name__)

@app.route("/")
def index():
    return "✅ Multi-pair Bot is running!"

if __name__ == "__main__":
    send_telegram_signal("🚀 Multi-pair bot started! Signals every 2–3 minutes.")

    t = threading.Thread(target=run_bot, daemon=True)
    t.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
