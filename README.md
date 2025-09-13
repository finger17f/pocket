# Pocket Option Signal Bot (Triple Confirmation)

This bot sends binary options signals to your Telegram using RSI, EMA, and MACD strategy.

## 🚀 How to Deploy on Render

1. **Upload this folder to a GitHub repo**.
2. **Go to [Render.com](https://render.com)** > Sign up and connect GitHub.
3. Create a new Web Service.
   - Environment: Python 3
   - Build Command: (leave empty)
   - Start Command: `python main.py`
   - Instance type: Free
4. Done! Bot will run 24/7 and send signals to your Telegram.

Make sure to update the `BOT_TOKEN` and `CHAT_ID` in `main.py` if you need.
