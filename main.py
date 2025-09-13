# === Triple Confirmation Signal Bot ===
# Requirements: pip install yfinance ta pandas requests

import yfinance as yf
import pandas as pd
import ta
import requests
from datetime import datetime
import pytz
import time

# === Config ===
PAIR = 'EURUSD=X'  # yfinance format
INTERVAL = '1m'    # 1-minute candles
LOOKBACK = 100
RSI_PERIOD = 14
EMA_FAST = 5
EMA_SLOW = 20
BOT_TOKEN = '7514100441:AAGwTNelH27hR5z7yJE0aS1wT_m8fz8eG0g'
CHAT_ID = '7356833637'
TIMEZONE = 'America/Sao_Paulo'  # UTC-3

# === Function: Send Message to Telegram ===
def send_telegram_signal(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': message}
    try:
        r = requests.post(url, data=payload)
        print("Signal sent!")
    except Exception as e:
        print("Error sending message:", e)

# === Function: Check Signal ===
def check_signal():
    data = yf.download(PAIR, interval=INTERVAL, period='1d')
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

# === Format and Send Signal ===
def send_signal(direction, data):
    now = datetime.now(pytz.timezone(TIMEZONE)).strftime('%Y-%m-%d %H:%M:%S')
    msg = f"✨ {direction} SIGNAL - EUR/USD\nTime: {now} (UTC-3)\nRSI: {data['rsi']:.2f}\nEMA: {'Bullish' if direction == 'BUY' else 'Bearish'}\nMACD: {'Green Bars' if direction == 'BUY' else 'Red Bars'}"
    send_telegram_signal(msg)

# === Run Forever ===
print("\nSignal bot started...")
while True:
    try:
        check_signal()
    except Exception as err:
        print("Error in loop:", err)
    time.sleep(60)  # Check every 1 minute
