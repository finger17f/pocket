# === Triple Confirmation Signal Bot + Flask Web Stub ===
# Requirements:
# pip install yfinance ta pandas requests flask pytz

import yfinance as yf
import pandas as pd
import ta
import requests
from datetime import datetime
import pytz
import time
import threading
import os
from flask import Flask

# === Config ===
PAIR = 'EURUSD=X'  # yfinance format
INTERVAL = '1m'    # 1-minute candles
LOOKBACK = 100
RSI_PERIOD = 14
EMA_FAST = 5
EMA_SLOW = 20
BOT_TOKEN = '8405596682:AAHFDmGX_4hfk5_qIXudfJXC2wK9EpdtnxQ'   # <-- замени на свой
CHAT_ID = '7195026649'        # <-- замени на свой
TIMEZONE = 'America/Sao_Paulo'  # UTC-3

# === Telegram ===
def send_telegram_signal(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': message}
    try:
        r = requests.post(url, data=payload)
        if r.status_code == 200:
            print("Signal sent!")
        else:
            print("Telegram error:", r.text)
    except Exception as e:
        print("Error sending message:", e)

# === Signal Logic ===
def check_signal():
    data = yf.download(PAIR, interval=INTERVAL, period='1d', auto_adjust=False)
    if len(data) < EMA_SLOW:
        print("Not enough data")
        return

    df = data.tail(LOOKBACK).copy()
    df['rsi'] = ta.momentum.RSIIndicator(df['Close'], RSI_PERIOD).rsi()
    df['ema_fast'] = ta.trend.EMAIndicator(df['Close'], EMA_FAST).ema_indicator()
    df['ema_slow'] = ta.trend.EMAIndicator(df['Close'], EMA_SLOW).ema_indicator()
    macd = ta.trend.MACD(df['Close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # === BUY Signal ===
    if (
        last['rsi'] < 30 and
        prev['ema_fast'] < prev['ema_slow'] and last['ema_fast'] > last['ema_slow'] and
        last['macd'] > last['macd_signal']
    ):
        send_signal('BUY', last)

    # === SELL Signal ===
    elif (
        last['rsi'] > 70 and
        prev['ema_fast'] > prev['ema_slow'] and last['ema_fast'] < last['ema_slow'] and
        last['macd'] < last['macd_signal']
    ):
        send_signal('SELL', last)

def send_signal(direction, data):
    now = datetime.now(pytz.timezone(TIMEZONE)).strftime('%Y-%m-%d %H:%M:%S')
    msg = (
        f"✨ {direction} SIGNAL - EUR/USD\n"
        f"Time: {now} (UTC-3)\n"
        f"RSI: {data['rsi']:.2f}\n"
        f"EMA: {'Bullish' if direction == 'BUY' else 'Bearish'}\n"
        f"MACD: {'Green Bars' if direction == 'BUY' else 'Red Bars'}"
    )
    send_telegram_signal(msg)

# === Bot Loop ===
def run_bot():
    print("\nSignal bot started...")
    while True:
        try:
            check_signal()
        except Exception as err:
            print("Error in loop:", err)
        time.sleep(60)  # check every minute

# === Flask Web Server (stub for Render) ===
app = Flask(__name__)

@app.route("/")
def index():
    return "✅ Bot is running!"

if __name__ == "__main__":
    # запускаем бота в отдельном потоке
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()

    # запускаем Flask на $PORT (Render требует слушать порт)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
