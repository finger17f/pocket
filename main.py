import asyncio
import random
import os
from datetime import datetime
import pytz
import yfinance as yf
import ta

from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes
)

# === CONFIG ===
BOT_TOKEN = "8405596682:AAHFDmGX_4hfk5_qIXudfJXC2wK9EpdtnxQ"          # <-- вставь свой токен
CHANNEL_ID = -1002902970702       # <-- вставь ID канала (-100...)
TIMEZONE = "America/Sao_Paulo"

PAIRS = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "JPY=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "CAD=X"
}

# Хранилище
user_pairs = set()       # выбранные пары
bot_running = False      # флаг запуска


# === SIGNAL LOGIC ===
def get_signal(pair_name, pair_code):
    try:
        data = yf.download(pair_code, interval="1m", period="1d", auto_adjust=False, progress=False)
        if len(data) < 20:
            return None

        df = data.tail(50).copy()
        df["ema_fast"] = ta.trend.EMAIndicator(df["Close"], 5).ema_indicator()
        df["ema_slow"] = ta.trend.EMAIndicator(df["Close"], 20).ema_indicator()
        df["rsi"] = ta.momentum.RSIIndicator(df["Close"], 14).rsi()

        last = df.iloc[-1]
        direction = "BUY" if last["ema_fast"] > last["ema_slow"] else "SELL"

        now = datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S")
        return (
            f"✨ {direction} SIGNAL - {pair_name}\n"
            f"Time: {now}\n"
            f"RSI: {last['rsi']:.2f}\n"
            f"EMA: {'Bullish' if direction == 'BUY' else 'Bearish'}"
        )
    except Exception as e:
        print("Ошибка при получении сигнала:", e)
        return None


async def signal_loop(application):
    global bot_running
    while bot_running:
        if user_pairs:
            for pair_name in list(user_pairs):
                pair_code = PAIRS[pair_name]
                signal = get_signal(pair_name, pair_code)
                if signal:
                    await application.bot.send_message(chat_id=CHANNEL_ID, text=signal)

        delay = random.randint(120, 180)  # 2–3 минуты
        await asyncio.sleep(delay)


# === TELEGRAM HANDLERS ===
def build_menu():
    keyboard = [
        [InlineKeyboardButton(p, callback_data=f"pair_{p}")] for p in PAIRS.keys()
    ]
    keyboard.append([InlineKeyboardButton("📋 Мои пары", callback_data="my_pairs")])
    keyboard.append([InlineKeyboardButton("▶️ Запустить сигналы", callback_data="start_bot")])
    keyboard.append([InlineKeyboardButton("⏹ Остановить сигналы", callback_data="stop_bot")])
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет! Управляй ботом через кнопки ниже:", reply_markup=build_menu())


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global bot_running
    query = update.callback_query
    await query.answer()

    if query.data.startswith("pair_"):
        pair = query.data.replace("pair_", "")
        if pair in user_pairs:
            user_pairs.remove(pair)
            await query.message.reply_text(f"❌ {pair} убран.\nТекущие пары: {', '.join(user_pairs) or 'нет'}", reply_markup=build_menu())
        else:
            user_pairs.add(pair)
            await query.message.reply_text(f"✅ {pair} добавлен.\nТекущие пары: {', '.join(user_pairs)}", reply_markup=build_menu())

    elif query.data == "my_pairs":
        pairs_list = ", ".join(user_pairs) if user_pairs else "нет"
        await query.message.reply_text(f"📋 Текущие пары: {pairs_list}", reply_markup=build_menu())

    elif query.data == "start_bot":
        if not user_pairs:
            await query.message.reply_text("⚠️ Сначала выбери хотя бы одну валютную пару!", reply_markup=build_menu())
            return
        if not bot_running:
            bot_running = True
            asyncio.create_task(signal_loop(context.application))
            await query.message.reply_text("🚀 Сигналы запущены! (каждые 2–3 минуты в канал)", reply_markup=build_menu())
        else:
            await query.message.reply_text("⚡ Сигналы уже идут.", reply_markup=build_menu())

    elif query.data == "stop_bot":
        if bot_running:
            bot_running = False
            await query.message.reply_text("⏹ Сигналы остановлены.", reply_markup=build_menu())
        else:
            await query.message.reply_text("⏸ Бот и так остановлен.", reply_markup=build_menu())


# === FLASK STUB ===
app = Flask(__name__)
@app.route("/")
def index():
    return "✅ Bot is running with buttons (channel mode)!"


# === MAIN ===
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))

    # Flask + Telegram бот параллельно
    import threading
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000))),
        daemon=True
    ).start()

    print("📡 Bot started with channel output!")
    application.run_polling()


if __name__ == "__main__":
    main()
