"""
Configuration for Crypto Pump Bot
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ─── Required ────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ─── Optional ────────────────────────────────────────────────────────────────
# CoinGecko Pro API key (optional - improves rate limits)
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")

# How often to check alerts (in minutes)
SCAN_INTERVAL_MINUTES = int(os.getenv("SCAN_INTERVAL_MINUTES", "15"))

# Minimum pump probability to trigger alert
MIN_PUMP_PROBABILITY = float(os.getenv("MIN_PUMP_PROBABILITY", "65.0"))

# Max coins to scan per cycle
MAX_SCAN_COINS = int(os.getenv("MAX_SCAN_COINS", "40"))
