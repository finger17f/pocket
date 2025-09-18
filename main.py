import asyncio
import random
from datetime import datetime
import pytz
import yfinance as yf
import pandas as pd
import ta
from flask import Flask
from telegram import Bot

# === CONFIG ===
BOT_TOKEN = "8405596682:AAHFDmGX_4hfk5_qIXudfJXC2wK9EpdtnxQ"
CHANNEL_ID = "-1002902970702"  # твой канал
TIMEZONE = "America/Sao_Paulo"

PAIRS = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "JPY=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "CAD=X"
}

bot = Bot(token=BOT_TOKEN)

# === SIGNAL LOGIC ===
def get_signal(pair_name, pair_code):
    try:
        data = yf.download(pair_code, interval="1m", period="1d", progress=False)
        if len(data) < 20:
            return None

        df = data.tail(50).copy()
        df["ema_fast"] = ta.trend.EMAIndicator(df["Close"], 5).ema_indicator()
        df["ema_slow"] = ta.trend.EMAIndicator(df["Close"], 20).ema_indicator()
        df["rsi"] = ta.momentum.RSIIndicator(df["Close"], 14).rsi()
        macd = ta.trend.MACD(df["Close"])
        df["macd"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()

        last = df.iloc[-1]
        prev = df.iloc[-2]

        # BUY signal
        if last["rsi"] < 30 and prev["ema_fast"] < prev["ema_slow"] and last["ema_fast"] > last["ema_slow"] and last["macd"] > last["macd_signal"]:
            direction = "BUY"
        # SELL signal
        elif last["rsi"] > 70 and prev["ema_fast"] > prev["ema_slow"] and last["ema_fast"] < last["ema_slow"] and last["macd"] < last["macd_signal"]:
            direction = "SELL"
        else:
            return None

        now = datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S")
        return (
            f"✨ {direction} SIGNAL - {pair_name}\n"
            f"Time: {now} (UTC-3)\n"
            f"RSI: {last['rsi']:.2f}\n"
            f"EMA: {'Bullish' if direction == 'BUY' else 'Bearish'}\n"
            f"MACD: {'Green Bars' if direction == 'BUY' else 'Red Bars'}"
        )
    except Exception as e:
        print("Ошибка при получении сигнала:", e)
        return None

# === ASYNC SIGNAL LOOP ===
async def signal_loop():
    while True:
        for pair_name, pair_code in PAIRS.items():
            signal = get_signal(pair_name, pair_code)
            if signal:
                try:
                    bot.send_message(chat_id=CHANNEL_ID, text=signal)
                    print(f"Sent signal: {pair_name}")
                except Exception as e:
                    print("Ошибка отправки в канал:", e)
        await asyncio.sleep(random.randint(120, 180))  # 2–3 минуты

# === FLASK STUB ===
app = Flask(__name__)
@app.route("/")
def index():
    return "✅ Bot is running on Render!"

# === RUN BOT + FLASK ===
def main():
    import threading
    # Flask в отдельном потоке
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000))), daemon=True).start()
    print("📡 Bot started, sending signals to channel!")

    asyncio.run(signal_loop())

if __name__ == "__main__":
    import os
    main()
