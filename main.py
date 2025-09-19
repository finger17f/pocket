#!/usr/bin/env python3
"""
Pocket-like Signal Bot for Render
- Buttons: select pairs, view selected, start/stop
- Signals: EMA_fast(5)/EMA_slow(20) + RSI + MACD confirmation
- Sends signals to CHANNEL_ID (from env)
- Flask stub for Render port binding
- Fix for Python 3.13 imghdr removal
"""

import asyncio
import random
import os
import logging
from datetime import datetime
import pytz
import yfinance as yf
import pandas as pd
import ta

# --- imghdr fix for Python 3.13 ---
try:
    import imghdr
except ImportError:
    # Python 3.13+: модуль удалён, подменяем минимальной заглушкой
    import types
    imghdr = types.SimpleNamespace(what=lambda *a, **k: None)
# -----------------------------------

from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)

# ----------------- CONFIG -----------------
# Prefer environment variables for sensitive values
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8405596682:AAHFDmGX_4hfk5_qIXudfJXC2wK9EpdtnxQ")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "-1002902970702")  # must be string: '-100...'
TIMEZONE = os.environ.get("TIMEZONE", "America/Sao_Paulo")

# Pairs presented to user
PAIRS = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "JPY=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "CAD=X",
    "NZD/USD": "NZDUSD=X"
}

# Strategy params
EMA_FAST = 5
EMA_SLOW = 20
RSI_PERIOD = 14
MIN_BARS = 30

# Runtime state (kept in memory)
selected_pairs = set()    # pairs chosen by user (human-readable names)
bot_running = False
signal_task = None

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
log = logging.getLogger("pocket-like-bot")

# ----------------- SIGNAL LOGIC -----------------
def compute_indicators(df):
    # expects df with column 'Close'
    df = df.copy()
    df["ema_fast"] = ta.trend.EMAIndicator(df["Close"], EMA_FAST).ema_indicator()
    df["ema_slow"] = ta.trend.EMAIndicator(df["Close"], EMA_SLOW).ema_indicator()
    macd = ta.trend.MACD(df["Close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["rsi"] = ta.momentum.RSIIndicator(df["Close"], RSI_PERIOD).rsi()
    return df

def evaluate_signal(pair_name, pair_code):
    try:
        data = yf.download(pair_code, interval="1m", period="1d", progress=False)
        if data is None or len(data) < MIN_BARS:
            return None
        df = data.tail(60).copy()
        df = compute_indicators(df)
        last = df.iloc[-1]
        prev = df.iloc[-2]

        # Full confirmation strategy: RSI extreme + EMA crossover + MACD confirmation
        buy_cond = (
            last["rsi"] < 35 and
            prev["ema_fast"] < prev["ema_slow"] and last["ema_fast"] > last["ema_slow"] and
            last["macd"] > last["macd_signal"]
        )
        sell_cond = (
            last["rsi"] > 65 and
            prev["ema_fast"] > prev["ema_slow"] and last["ema_fast"] < last["ema_slow"] and
            last["macd"] < last["macd_signal"]
        )

        if buy_cond:
            direction = "BUY"
        elif sell_cond:
            direction = "SELL"
        else:
            # no confirmed signal
            return None

        now = datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S")
        msg = (
            f"✨ {direction} SIGNAL — {pair_name}\n"
            f"Time: {now} ({TIMEZONE})\n"
            f"RSI: {last['rsi']:.2f}\n"
            f"EMA: {'Bullish' if direction == 'BUY' else 'Bearish'}\n"
            f"MACD: {'Green Bars' if direction == 'BUY' else 'Red Bars'}"
        )
        return msg
    except Exception as e:
        log.exception("Error computing signal for %s: %s", pair_name, e)
        return None

# ----------------- ASYNC LOOP -----------------
async def signals_loop(application: Application):
    global bot_running
    log.info("Signals loop started")
    try:
        while bot_running:
            if selected_pairs:
                for pname in list(selected_pairs):
                    pcode = PAIRS.get(pname)
                    if not pcode:
                        continue
                    msg = evaluate_signal(pname, pcode)
                    if msg:
                        try:
                            # send to channel
                            await application.bot.send_message(chat_id=CHANNEL_ID, text=msg)
                            log.info("Sent signal for %s", pname)
                        except Exception as e:
                            log.exception("Failed to send signal to channel: %s", e)
            else:
                log.debug("No selected pairs; skipping this cycle")

            wait = random.randint(120, 180)
            log.info("Waiting %s seconds until next cycle", wait)
            await asyncio.sleep(wait)
    except asyncio.CancelledError:
        log.info("Signals loop cancelled")
    except Exception:
        log.exception("Signals loop error")
    finally:
        log.info("Signals loop finished")

# ----------------- TELEGRAM UI -----------------
def build_menu():
    keyboard = []
    for p in PAIRS.keys():
        keyboard.append([InlineKeyboardButton(p, callback_data=f"pair|{p}")])
    keyboard.append([InlineKeyboardButton("📋 Мои пары", callback_data="my_pairs"),
                     InlineKeyboardButton("📡 Статус", callback_data="status")])
    keyboard.append([InlineKeyboardButton("▶️ Запустить сигналы", callback_data="start"),
                     InlineKeyboardButton("⏹ Остановить сигналы", callback_data="stop")])
    keyboard.append([InlineKeyboardButton("ℹ️ О боте", callback_data="about")])
    return InlineKeyboardMarkup(keyboard)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 Добро пожаловать! Это бот в стиле @PocketSignalBot.\n\n"
        "Выберите валютные пары для мониторинга и нажмите ▶️ «Запустить сигналы».\n\n"
        "⚠️ Важно: сигналы — информационные, не финансовая рекомендация."
    )
    await update.message.reply_text(text, reply_markup=build_menu())

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_running, signal_task
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("pair|"):
        pair = data.split("|", 1)[1]
        if pair in selected_pairs:
            selected_pairs.remove(pair)
            await query.message.reply_text(f"❌ {pair} убрана. Текущие пары: {', '.join(selected_pairs) or 'нет'}", reply_markup=build_menu())
        else:
            selected_pairs.add(pair)
            await query.message.reply_text(f"✅ {pair} добавлена. Текущие пары: {', '.join(selected_pairs)}", reply_markup=build_menu())
        return

    if data == "my_pairs":
        await query.message.reply_text(f"📋 Текущие пары: {', '.join(selected_pairs) or 'нет'}", reply_markup=build_menu())
        return

    if data == "status":
        status = "🚀 Запущен" if bot_running else "⏸ Остановлен"
        await query.message.reply_text(f"📡 Статус: {status}\nПары: {', '.join(selected_pairs) or 'нет'}", reply_markup=build_menu())
        return

    if data == "about":
        await query.message.reply_text(
            "ℹ️ Бот генерирует сигналы по EMA(5/20)+RSI+MACD.\n"
            "Сигналы отправляются в канал. Не инвестируйте без тестирования.",
            reply_markup=build_menu()
        )
        return

    if data == "start":
        if not selected_pairs:
            await query.message.reply_text("⚠️ Сначала выберите хотя бы одну пару.", reply_markup=build_menu())
            return
        if not bot_running:
            bot_running = True
            # launch background task
            signal_task = asyncio.create_task(signals_loop(context.application))
            await query.message.reply_text("✅ Сигналы запущены! Отправляются в канал.", reply_markup=build_menu())
        else:
            await query.message.reply_text("⚠️ Сигналы уже запущены.", reply_markup=build_menu())
        return

    if data == "stop":
        if bot_running:
            bot_running = False
            if signal_task:
                signal_task.cancel()
            await query.message.reply_text("⏹ Сигналы остановлены.", reply_markup=build_menu())
        else:
            await query.message.reply_text("⚠️ Бот уже остановлен.", reply_markup=build_menu())
        return

# ----------------- FLASK STUB -----------------
app = Flask(__name__)
@app.route("/")
def index():
    return "✅ Pocket-like Signal Bot running"

# ----------------- BOOT -----------------
def main():
    # Build application
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CallbackQueryHandler(handle_button))

    # Start Flask server in background so Render sees a listening port
    import threading
    port = int(os.environ.get("PORT", 5000))
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=port), daemon=True).start()

    log.info("Starting Telegram application (polling)...")
    application.run_polling()

if __name__ == "__main__":
    main()
