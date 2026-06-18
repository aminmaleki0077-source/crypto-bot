#!/usr/bin/env python3
"""
🚀 Ultra Crypto Pump Bot v3
Moralis On-Chain + DexScreener + Binance
ضد تکرار + دقت بالا
"""

import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from datetime import datetime, timedelta
import io, time, logging, json, os

# ==================== تنظیمات ====================
TELEGRAM_TOKEN = "8286137689:AAEbA-vB41YSHfYj8YIe_MBeymRHqXzu7l4"
CHAT_ID        = "767354973"
MORALIS_KEY    = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJub25jZSI6ImRhZDI2NDI1LTQzMWUtNDEwZS1hOWVkLTQwM2QzYjEzZGQ0NCIsIm9yZ0lkIjoiNTE5OTQxIiwidXNlcklkIjoiNTM1MDY4IiwidHlwZUlkIjoiZWQ2MjI1MTItZTkwOC00OTkzLWIzMzItMDc0MzBhYjk2NGFjIiwidHlwZSI6IlBST0pFQ1QiLCJpYXQiOjE3ODE2MDg5MzIsImV4cCI6NDkzNzM2ODkzMn0.W9DcY-ov9TQq9IXIN7P-6eH3cYQYEpyFn7kP5XyxPjg"

BINANCE_BASE = "https://api.binance.com/api/v3"
DEX_BASE     = "https://api.dexscreener.com/latest/dex"
MORALIS_BASE = "https://deep-index.moralis.io/api/v2.2"

MORALIS_HEADERS = {
    "X-API-Key": MORALIS_KEY,
    "Accept": "application/json"
}

# پارامترها
VOLUME_WINDOW        = 20
SMF_WINDOW           = 10
SCAN_INTERVAL        = 240     # هر 4 دقیقه
PUMP_SCORE_MIN       = 55      # حداقل امتیاز
SIGNAL_COOLDOWN      = 3600    # هر ارز حداقل 1 ساعت دیگر سیگنال نده

# ضد تکرار: ذخیره آخرین زمان ارسال هر سیگنال
sent_signals = {}  # {symbol: timestamp}

BINANCE_SYMBOLS = [
    "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT","DOGEUSDT",
    "AVAXUSDT","DOTUSDT","LINKUSDT","UNIUSDT","ATOMUSDT","NEARUSDT","TRXUSDT",
    "APTUSDT","ARBUSDT","OPUSDT","INJUSDT","SUIUSDT","PEPEUSDT","WIFUSDT",
    "BONKUSDT","FLOKIUSDT","NOTUSDT","WLDUSDT","TIAUSDT","SEIUSDT","JUPUSDT",
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# ==================== ضد تکرار ====================

def is_already_sent(symbol):
    """آیا این سیگنال اخیراً ارسال شده؟"""
    if symbol in sent_signals:
        elapsed = time.time() - sent_signals[symbol]
        if elapsed < SIGNAL_COOLDOWN:
            logger.info(f"⏭ {symbol} قبلاً ارسال شده ({int(elapsed//60)} دقیقه پیش)")
            return True
    return False

def mark_as_sent(symbol):
    """ثبت زمان ارسال سیگنال"""
    sent_signals[symbol] = time.time()

# ==================== Moralis API ====================

def get_moralis_token_price(address, chain="eth"):
    """قیمت و متادیتای توکن از Moralis"""
    try:
        chain_map = {"ethereum":"eth","bsc":"bsc","polygon":"polygon",
                     "arbitrum":"arbitrum","base":"base","avalanche":"avalanche"}
        ch = chain_map.get(chain, "eth")
        r = requests.get(
            f"{MORALIS_BASE}/erc20/{address}/price",
            headers=MORALIS_HEADERS,
            params={"chain": ch},
            timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.error(f"Moralis price error: {e}")
    return None

def get_moralis_token_stats(address, chain="eth"):
    """آمار توکن: holders, transfers"""
    try:
        chain_map = {"ethereum":"eth","bsc":"bsc","polygon":"polygon",
                     "arbitrum":"arbitrum","base":"base","avalanche":"avalanche"}
        ch = chain_map.get(chain, "eth")
        r = requests.get(
            f"{MORALIS_BASE}/erc20/{address}/stats",
            headers=MORALIS_HEADERS,
            params={"chain": ch},
            timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.error(f"Moralis stats error: {e}")
    return None

def get_moralis_top_gainers():
    """توکن‌های برتر در حال رشد از Moralis"""
    try:
        r = requests.get(
            f"{MORALIS_BASE}/market-data/erc20s/top-movers",
            headers=MORALIS_HEADERS,
            timeout=15)
        if r.status_code == 200:
            data = r.json()
            return data.get("gainers", [])
    except Exception as e:
        logger.error(f"Moralis top gainers error: {e}")
    return []

def get_moralis_trending():
    """توکن‌های ترند از Moralis"""
    try:
        r = requests.get(
            f"{MORALIS_BASE}/market-data/erc20s/top-tokens",
            headers=MORALIS_HEADERS,
            timeout=15)
        if r.status_code == 200:
            return r.json() or []
    except Exception as e:
        logger.error(f"Moralis trending error: {e}")
    return []

# ==================== Binance API ====================

def get_klines(symbol, interval="1d", limit=50):
    try:
        r = requests.get(f"{BINANCE_BASE}/klines",
                         params={"symbol": symbol, "interval": interval, "limit": limit},
                         timeout=10)
        r.raise_for_status()
        df = pd.DataFrame(r.json(), columns=[
            "open_time","open","high","low","close","volume",
            "close_time","quote_volume","trades","taker_buy_base","taker_buy_quote","ignore"])
        for c in ["open","high","low","close","volume"]:
            df[c] = df[c].astype(float)
        df["date"] = pd.to_datetime(df["open_time"], unit="ms")
        return df
    except:
        return None

def get_ticker_24h(symbol):
    try:
        r = requests.get(f"{BINANCE_BASE}/ticker/24hr",
                         params={"symbol": symbol}, timeout=10)
        return r.json()
    except:
        return {}

# ==================== DexScreener ====================

def search_dex(query, min_volume=30000, min_liquidity=15000):
    try:
        r = requests.get(f"{DEX_BASE}/search?q={query}", timeout=10)
        if r.status_code == 200:
            pairs = r.json().get("pairs", []) or []
            return [p for p in pairs
                    if float(p.get("volume",{}).get("h24",0) or 0) > min_volume
                    and float(p.get("liquidity",{}).get("usd",0) or 0) > min_liquidity]
    except:
        pass
    return []

def get_dex_pair(chain, pair_address):
    try:
        r = requests.get(f"{DEX_BASE}/pairs/{chain}/{pair_address}", timeout=10)
        if r.status_code == 200:
            pairs = r.json().get("pairs", [])
            return pairs[0] if pairs else None
    except:
        return None

# ==================== محاسبات ====================

def calc_smf(df):
    hl = (df["high"] - df["low"]).replace(0, 0.0001)
    smf = ((df["close"] - df["low"]) / hl) * df["volume"]
    return smf.rolling(SMF_WINDOW).mean() / df["volume"].rolling(SMF_WINDOW).mean() * 100

def calc_vol_z(df):
    vol_mean = df["volume"].rolling(VOLUME_WINDOW).mean()
    vol_std  = df["volume"].rolling(VOLUME_WINDOW).std()
    return (df["volume"] - vol_mean) / vol_std, vol_mean

def calc_rsi(series, period=14):
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, 0.0001)
    return 100 - (100 / (1 + rs))

def calc_macd(series):
    ema12 = series.ewm(span=12).mean()
    ema26 = series.ewm(span=26).mean()
    macd  = ema12 - ema26
    signal= macd.ewm(span=9).mean()
    return macd, signal

def score_binance(df_1d, df_4h, ticker):
    score = 0
    signals = []
    risks = []

    if df_1d is None or len(df_1d) < VOLUME_WINDOW + 5:
        return 0, [], [], 80

    vol_z, vol_mean = calc_vol_z(df_1d)
    smf   = calc_smf(df_1d)
    rsi   = calc_rsi(df_1d["close"])
    macd, macd_sig = calc_macd(df_1d["close"])

    lz   = vol_z.iloc[-1]
    lsmf = smf.iloc[-1] if not pd.isna(smf.iloc[-1]) else 50
    lrsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
    lmacd= macd.iloc[-1] - macd_sig.iloc[-1]

    p24h   = float(ticker.get("priceChangePercent", 0))
    vol24h = float(ticker.get("quoteVolume", 0))
    price  = float(ticker.get("lastPrice", 0))

    # 1. حجم (25pt)
    if lz > 3:
        score += 25; signals.append(f"🔥 حجم انفجاری z={lz:.1f}")
    elif lz > 2:
        score += 18; signals.append(f"📈 حجم بالا z={lz:.1f}")
    elif lz > 1.5:
        score += 10; signals.append(f"📊 حجم بالاتر از معمول")
    elif lz < -1:
        risks.append("⚠️ حجم پایین‌تر از معمول")

    # 2. SMF (20pt)
    if lsmf > 70:
        score += 20; signals.append(f"💰 Smart Money قوی {lsmf:.0f}")
    elif lsmf > 58:
        score += 12; signals.append(f"💰 Smart Money مثبت {lsmf:.0f}")
    elif lsmf < 40:
        risks.append(f"⚠️ Smart Money ضعیف {lsmf:.0f}")

    # 3. RSI (15pt)
    if 45 < lrsi < 65:
        score += 15; signals.append(f"📐 RSI ایده‌آل {lrsi:.0f}")
    elif 35 < lrsi <= 45:
        score += 8;  signals.append(f"📐 RSI ناحیه خرید {lrsi:.0f}")
    elif lrsi > 75:
        score -= 10; risks.append(f"🔴 RSI اشباع خرید {lrsi:.0f}")
    elif lrsi < 30:
        score += 5;  signals.append(f"📐 RSI اشباع فروش {lrsi:.0f} (ریباند احتمالی)")

    # 4. MACD (15pt)
    if lmacd > 0 and macd.iloc[-1] > macd.iloc[-2]:
        score += 15; signals.append("📈 MACD صعودی و بالای سیگنال")
    elif lmacd > 0:
        score += 8;  signals.append("📈 MACD بالای سیگنال")
    elif lmacd < 0 and macd.iloc[-1] < macd.iloc[-2]:
        risks.append("📉 MACD نزولی")

    # 5. تغییر قیمت (15pt)
    if 2 < p24h < 15:
        score += 15; signals.append(f"💹 رشد 24h: +{p24h:.1f}%")
    elif 0.5 < p24h <= 2:
        score += 7;  signals.append(f"💹 رشد کم 24h: +{p24h:.1f}%")
    elif p24h < -8:
        score -= 10; risks.append(f"📉 افت شدید: {p24h:.1f}%")

    # 6. مومنتوم کوتاه‌مدت (10pt) — تحلیل 4H
    if df_4h is not None and len(df_4h) > 10:
        vol_z_4h, _ = calc_vol_z(df_4h)
        rsi_4h = calc_rsi(df_4h["close"])
        p4h = (df_4h["close"].iloc[-1] / df_4h["close"].iloc[-4] - 1) * 100
        if vol_z_4h.iloc[-1] > 2 and p4h > 1:
            score += 10; signals.append(f"⚡ 4H: حجم+قیمت هر دو بالا")
        elif p4h > 2:
            score += 5; signals.append(f"⚡ 4H رشد: +{p4h:.1f}%")

    # محاسبه ریسک
    risk = 30
    if lrsi > 70: risk += 20
    if lz > 3: risk += 10
    if p24h > 15: risk += 20; risks.append(f"⚠️ رشد بیش از حد {p24h:.0f}%")
    if vol24h < 500_000: risk += 15; risks.append("⚠️ حجم دلاری پایین")
    risk += len(risks) * 5
    risk = min(max(risk, 10), 95)

    return min(score, 100), signals, risks, risk

def score_dex(pair):
    score = 0
    signals = []
    risks = []

    try:
        vol_h1  = float(pair.get("volume",{}).get("h1",0) or 0)
        vol_h6  = float(pair.get("volume",{}).get("h6",0) or 0)
        vol_h24 = float(pair.get("volume",{}).get("h24",0) or 0)
        liq     = float(pair.get("liquidity",{}).get("usd",0) or 0)
        mc      = float(pair.get("marketCap",0) or 0)
        p1h     = float(pair.get("priceChange",{}).get("h1",0) or 0)
        p6h     = float(pair.get("priceChange",{}).get("h6",0) or 0)
        p24h    = float(pair.get("priceChange",{}).get("h24",0) or 0)
        txns    = pair.get("txns",{})
        buys_1h = int(txns.get("h1",{}).get("buys",0) or 0)
        sells_1h= int(txns.get("h1",{}).get("sells",0) or 0)
        buys_24h= int(txns.get("h24",{}).get("buys",0) or 0)
        sells_24h=int(txns.get("h24",{}).get("sells",0) or 0)

        # 1. شتاب حجم (25pt)
        if vol_h24 > 0 and vol_h1 > 0:
            accel = (vol_h1 * 24) / vol_h24
            if accel > 4:
                score += 25; signals.append(f"🔥 شتاب حجم {accel:.1f}x")
            elif accel > 2.5:
                score += 17; signals.append(f"📈 رشد حجم {accel:.1f}x")
            elif accel > 1.5:
                score += 9;  signals.append(f"📊 حجم در حال رشد {accel:.1f}x")

        # 2. فشار خرید (20pt)
        total_1h = buys_1h + sells_1h
        total_24h= buys_24h + sells_24h
        if total_1h > 5:
            buy_r = buys_1h / total_1h
            if buy_r > 0.72:
                score += 20; signals.append(f"💚 فشار خرید قوی {buy_r*100:.0f}%")
            elif buy_r > 0.6:
                score += 12; signals.append(f"💚 خریداران غالب {buy_r*100:.0f}%")
            elif buy_r < 0.38:
                risks.append(f"🔴 فشار فروش {(1-buy_r)*100:.0f}%")
        else:
            risks.append("⚠️ تراکنش کم در 1H")

        # 3. تغییر قیمت (20pt)
        if 3 < p1h < 25:
            score += 20; signals.append(f"🚀 پامپ 1H: +{p1h:.1f}%")
        elif 1 < p1h <= 3:
            score += 10; signals.append(f"📈 رشد 1H: +{p1h:.1f}%")
        elif p1h > 50:
            risks.append(f"⚠️ پامپ بیش از حد {p1h:.0f}% (دامپ احتمالی)")
        if 5 < p6h < 40:
            score += 8; signals.append(f"📈 رشد 6H: +{p6h:.1f}%")

        # 4. نقدینگی (15pt)
        if liq > 1_000_000:
            score += 15; signals.append(f"💧 نقدینگی بالا ${liq/1e6:.1f}M")
        elif liq > 200_000:
            score += 10; signals.append(f"💧 نقدینگی خوب ${liq/1e3:.0f}K")
        elif liq > 50_000:
            score += 5;  signals.append(f"💧 نقدینگی متوسط ${liq/1e3:.0f}K")
        else:
            risks.append(f"⚠️ نقدینگی پایین ${liq/1e3:.0f}K")

        # 5. نسبت حجم/MC (10pt)
        if mc > 0:
            ratio = vol_h24 / mc
            if ratio > 0.3:
                score += 10; signals.append(f"⚡ حجم/MC={ratio:.2f} (فعال)")
            elif ratio > 0.1:
                score += 5

        # 6. رشد 24H کلی (10pt)
        if 5 < p24h < 50:
            score += 10; signals.append(f"📊 رشد 24H: +{p24h:.1f}%")
        elif p24h < -15:
            score -= 10; risks.append(f"📉 افت 24H: {p24h:.1f}%")

        # ریسک
        risk = 40
        if liq < 50_000: risk += 25
        if mc > 0 and mc < 50_000: risk += 20; risks.append("⚠️ مارکت‌کپ بسیار کم")
        if p1h > 40: risk += 25; risks.append(f"⚠️ پامپ شدید {p1h:.0f}%")
        if total_1h < 10: risk += 15
        if p24h < -10: risk += 10
        risk += len(risks) * 4
        risk = min(max(risk, 15), 95)

        return min(score, 100), signals, risks, risk

    except Exception as e:
        logger.error(f"خطا در score_dex: {e}")
        return 0, [], [], 90

# ==================== رسم چارت ====================

def create_chart(symbol, df_1d, df_4h, ticker):
    fig = plt.figure(figsize=(16, 11), facecolor='#0d1117')
    gs  = gridspec.GridSpec(3, 2, height_ratios=[3,2,2], hspace=0.1, wspace=0.3)

    vol_z, vol_mean = calc_vol_z(df_1d)
    smf   = calc_smf(df_1d)
    rsi   = calc_rsi(df_1d["close"])
    macd, macd_sig = calc_macd(df_1d["close"])

    def candles(ax, df, title):
        ax.set_facecolor('#0d1117')
        for i in range(len(df)):
            o,h,l,c = df["open"].iloc[i],df["high"].iloc[i],df["low"].iloc[i],df["close"].iloc[i]
            col = '#26a69a' if c>=o else '#ef5350'
            ax.plot([i,i],[l,h], color=col, lw=0.8)
            ax.add_patch(plt.Rectangle((i-0.3,min(o,c)),0.6,abs(c-o),color=col,alpha=0.9))
        cp = float(ticker.get("lastPrice", df["close"].iloc[-1]))
        ax.axhline(cp, color='#00e5ff', ls='--', lw=0.8, alpha=0.7)
        ax.annotate(f'{cp:.5g}', xy=(len(df)-1,cp), fontsize=7, color='white',
                   bbox=dict(boxstyle='round,pad=0.2',facecolor='#00e5ff',alpha=0.85,edgecolor='none'),ha='right')
        ax.set_title(title, color='white', fontsize=9, pad=3)
        ax.set_ylabel('Price', color='#666', fontsize=7)
        ax.tick_params(colors='#666', labelsize=6)
        for sp in ax.spines.values(): sp.set_color('#21262d')
        ax.set_xlim(-1, len(df))
        step = max(1, len(df)//6)
        tks = list(range(0,len(df),step))
        ax.set_xticks(tks)
        ax.set_xticklabels([df["date"].iloc[i].strftime('%m/%d') for i in tks], fontsize=5, color='#666')

    ax1 = fig.add_subplot(gs[0,0])
    candles(ax1, df_1d, f'{symbol} — Daily')

    ax2 = fig.add_subplot(gs[0,1])
    if df_4h is not None and len(df_4h) > 5:
        candles(ax2, df_4h, f'{symbol} — 4H')
    else:
        ax2.set_facecolor('#0d1117')
        ax2.text(0.5,0.5,'No 4H Data',ha='center',va='center',color='#666',transform=ax2.transAxes)

    # Volume
    ax3 = fig.add_subplot(gs[1,0])
    ax3.set_facecolor('#0d1117')
    x = range(len(df_1d))
    bcols = ['#ffd700' if vol_z.iloc[i]>2 else ('#26a69a' if df_1d["close"].iloc[i]>=df_1d["open"].iloc[i] else '#ef5350') for i in x]
    ax3.bar(x, df_1d["volume"], color=bcols, alpha=0.8, width=0.8)
    ax3.plot(x, vol_mean, color='#00e5ff', lw=1.2)
    ax3.set_title('Volume', color='white', fontsize=8, pad=3)
    ax3.tick_params(colors='#666', labelsize=6)
    ax3.yaxis.set_major_formatter(plt.FuncFormatter(lambda v,p: f'{v/1e6:.0f}M' if v>=1e6 else f'{v/1e3:.0f}K'))
    for sp in ax3.spines.values(): sp.set_color('#21262d')

    # RSI
    ax4 = fig.add_subplot(gs[1,1])
    ax4.set_facecolor('#0d1117')
    ax4.plot(range(len(rsi)), rsi, color='#ab47bc', lw=1.5)
    ax4.axhline(70, color='#ef5350', ls='--', lw=0.8, alpha=0.7)
    ax4.axhline(30, color='#26a69a', ls='--', lw=0.8, alpha=0.7)
    ax4.fill_between(range(len(rsi)), rsi, 70, where=(rsi>70), alpha=0.15, color='#ef5350')
    ax4.fill_between(range(len(rsi)), rsi, 30, where=(rsi<30), alpha=0.15, color='#26a69a')
    ax4.annotate(f'RSI: {rsi.iloc[-1]:.0f}', xy=(len(rsi)-1,rsi.iloc[-1]),
                fontsize=8, color='white',
                bbox=dict(boxstyle='round,pad=0.3',facecolor='#ab47bc',alpha=0.9,edgecolor='none'),ha='right')
    ax4.set_ylim(0,100)
    ax4.set_title('RSI (14)', color='white', fontsize=8, pad=3)
    ax4.tick_params(colors='#666', labelsize=6)
    for sp in ax4.spines.values(): sp.set_color('#21262d')

    # MACD + SMF
    ax5 = fig.add_subplot(gs[2,:])
    ax5.set_facecolor('#0d1117')
    x2 = range(len(macd))
    hist = macd - macd_sig
    ax5.bar(x2, hist, color=['#26a69a' if h>=0 else '#ef5350' for h in hist], alpha=0.6, width=0.8, label='Histogram')
    ax5.plot(x2, macd,     color='#00e5ff', lw=1.2, label='MACD')
    ax5.plot(x2, macd_sig, color='#ff7043', lw=1.0, ls='--', label='Signal')

    ax5b = ax5.twinx()
    ax5b.plot(range(len(smf)), smf, color='#ffd700', lw=1.0, alpha=0.7, label='SMF')
    ax5b.tick_params(colors='#666', labelsize=6)
    ax5b.set_ylabel('SMF', color='#ffd700', fontsize=7)

    ax5.set_title('MACD + Smart Money Flow', color='white', fontsize=8, pad=3)
    ax5.tick_params(colors='#666', labelsize=6)
    ax5.legend(facecolor='#0d1117', edgecolor='#21262d', labelcolor='white', fontsize=6, loc='upper left')
    for sp in ax5.spines.values(): sp.set_color('#21262d')

    fig.suptitle(f'📊 {symbol} — Technical Analysis', color='white', fontsize=12, y=0.99)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=110, bbox_inches='tight', facecolor='#0d1117')
    buf.seek(0)
    plt.close(fig)
    return buf

def create_dex_chart(pair):
    fig, axes = plt.subplots(1,2, figsize=(13,5), facecolor='#0d1117')
    sym  = pair.get("baseToken",{}).get("symbol","?")
    p1h  = float(pair.get("priceChange",{}).get("h1",0) or 0)
    p6h  = float(pair.get("priceChange",{}).get("h6",0) or 0)
    p24h = float(pair.get("priceChange",{}).get("h24",0) or 0)
    v1h  = float(pair.get("volume",{}).get("h1",0) or 0)
    v6h  = float(pair.get("volume",{}).get("h6",0) or 0)
    v24h = float(pair.get("volume",{}).get("h24",0) or 0)

    ax1 = axes[0]; ax1.set_facecolor('#0d1117')
    changes = [p1h, p6h, p24h]
    cols    = ['#26a69a' if c>0 else '#ef5350' for c in changes]
    bars = ax1.bar(['1H','6H','24H'], changes, color=cols, alpha=0.85, width=0.5)
    for b,v in zip(bars,changes):
        ax1.text(b.get_x()+b.get_width()/2., b.get_height()+(0.5 if v>=0 else -1.5),
                f'{v:+.1f}%', ha='center', va='bottom' if v>=0 else 'top',
                color='white', fontsize=11, fontweight='bold')
    ax1.axhline(0, color='#444', lw=0.8)
    ax1.set_title(f'{sym} Price Change', color='white', fontsize=10)
    ax1.tick_params(colors='#888', labelsize=9)
    for sp in ax1.spines.values(): sp.set_color('#21262d')

    ax2 = axes[1]; ax2.set_facecolor('#0d1117')
    bars2 = ax2.bar(['1H','6H','24H'], [v1h,v6h,v24h], color=['#ffd700','#42a5f5','#ab47bc'], alpha=0.85, width=0.5)
    for b,v in zip(bars2,[v1h,v6h,v24h]):
        lbl = f'${v/1e6:.2f}M' if v>=1e6 else f'${v/1e3:.1f}K'
        ax2.text(b.get_x()+b.get_width()/2., b.get_height(), lbl,
                ha='center', va='bottom', color='white', fontsize=9)
    ax2.set_title(f'{sym} Volume', color='white', fontsize=10)
    ax2.tick_params(colors='#888', labelsize=9)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda v,p: f'${v/1e6:.1f}M' if v>=1e6 else f'${v/1e3:.0f}K'))
    for sp in ax2.spines.values(): sp.set_color('#21262d')

    chain = pair.get("chainId","")
    price = float(pair.get("priceUsd",0) or 0)
    fig.suptitle(f'{sym} on {chain.upper()} | ${price:.6g}', color='white', fontsize=11, y=1.01)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=110, bbox_inches='tight', facecolor='#0d1117')
    buf.seek(0)
    plt.close(fig)
    return buf

# ==================== تلگرام ====================

def send_photo(buf, caption):
    buf.seek(0)
    if len(caption) > 1024: caption = caption[:1021] + "..."
    r = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
        files={"photo": ("chart.png", buf, "image/png")},
        data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"},
        timeout=30)
    return r.status_code == 200

def send_msg(text):
    if len(text) > 4096: text = text[:4093] + "..."
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
        timeout=10)

def pump_bar(s):  return "🟩"*(s//10) + "⬜"*(10-s//10)
def risk_bar(r):  return "🟥"*(r//10) + "⬜"*(10-r//10)

def fmt_binance(sym, score, signals, risks, risk, ticker):
    price  = float(ticker.get("lastPrice",0))
    p24h   = float(ticker.get("priceChangePercent",0))
    vol24h = float(ticker.get("quoteVolume",0))
    pump   = round(score * 0.35 + max(p24h,0)*0.2, 1)
    e = "🚨🚀" if score>=80 else ("🟢🔥" if score>=70 else "🟡📊")
    buy = f"https://www.binance.com/en/trade/{sym.replace('USDT','_USDT')}"
    msg = f"""{e} <b>سیگنال Binance: #{sym}</b>

💰 قیمت: <code>{price:.6g} USDT</code>
{'▲' if p24h>0 else '▼'} تغییر 24H: <b>{p24h:+.2f}%</b>
📦 حجم 24H: <code>${vol24h:,.0f}</code>

━━━━━━━━━━━━━━━━━━
🎯 امتیاز پامپ: <b>{score}/100</b>
{pump_bar(score)}
⚡ پتانسیل پامپ: ~<b>{pump:.1f}%</b>
⚠️ درصد ریسک: <b>{risk}%</b>
{risk_bar(risk)}
━━━━━━━━━━━━━━━━━━
✅ <b>سیگنال‌ها:</b>\n"""
    for s in signals: msg += f"  • {s}\n"
    if risks:
        msg += "\n🚩 <b>ریسک‌ها:</b>\n"
        for r in risks: msg += f"  • {r}\n"
    msg += f"\n🛒 <a href='{buy}'>خرید روی Binance</a>"
    msg += f"\n⏰ {datetime.now().strftime('%H:%M')} | ⚠️ <i>تحلیل الگوریتمی</i>"
    return msg

def fmt_dex(pair, score, signals, risks, risk):
    base   = pair.get("baseToken",{})
    chain  = pair.get("chainId","")
    sym    = base.get("symbol","?")
    name   = base.get("name","")
    ca     = base.get("address","N/A")
    price  = float(pair.get("priceUsd",0) or 0)
    p1h    = float(pair.get("priceChange",{}).get("h1",0) or 0)
    p24h   = float(pair.get("priceChange",{}).get("h24",0) or 0)
    vol24h = float(pair.get("volume",{}).get("h24",0) or 0)
    liq    = float(pair.get("liquidity",{}).get("usd",0) or 0)
    mc     = float(pair.get("marketCap",0) or 0)
    dex_url= pair.get("url","")
    pump   = round(score*0.4 + max(p1h,0)*0.25, 1)

    buy_map = {
        "solana":   f"https://raydium.io/swap/?outputCurrency={ca}",
        "ethereum": f"https://app.uniswap.org/swap?outputCurrency={ca}",
        "bsc":      f"https://pancakeswap.finance/swap?outputCurrency={ca}",
        "base":     f"https://app.uniswap.org/swap?chain=base&outputCurrency={ca}",
        "arbitrum": f"https://app.uniswap.org/swap?chain=arbitrum&outputCurrency={ca}",
        "polygon":  f"https://app.uniswap.org/swap?chain=polygon&outputCurrency={ca}",
    }
    buy_url = buy_map.get(chain, dex_url)
    chain_icon = {"solana":"◎","ethereum":"Ξ","bsc":"⬡","base":"🔵","arbitrum":"🔷","polygon":"🟣","ton":"💎"}.get(chain,"🔗")
    e = "🚨🚀" if score>=80 else ("🟢🔥" if score>=70 else "🟡📊")

    msg = f"""{e} <b>سیگنال DEX: #{sym}</b> ({name})
{chain_icon} <b>{chain.upper()}</b>

💰 قیمت: <code>${price:.8g}</code>
📈 1H: <b>{p1h:+.1f}%</b> | 24H: <b>{p24h:+.1f}%</b>
📦 حجم 24H: <code>${vol24h:,.0f}</code>
💧 نقدینگی: <code>${liq:,.0f}</code>
🏦 MarketCap: <code>${mc:,.0f}</code>

━━━━━━━━━━━━━━━━━━
🎯 امتیاز پامپ: <b>{score}/100</b>
{pump_bar(score)}
⚡ پتانسیل پامپ: ~<b>{pump:.1f}%</b>
⚠️ درصد ریسک: <b>{risk}%</b>
{risk_bar(risk)}
━━━━━━━━━━━━━━━━━━
📋 <b>آدرس قرارداد:</b>
<code>{ca}</code>

✅ <b>سیگنال‌ها:</b>\n"""
    for s in signals: msg += f"  • {s}\n"
    if risks:
        msg += "\n🚩 <b>ریسک‌ها:</b>\n"
        for r in risks: msg += f"  • {r}\n"
    msg += f"\n🛒 <a href='{buy_url}'>خرید روی DEX</a>"
    msg += f"\n📊 <a href='{dex_url}'>DexScreener</a>"
    msg += f"\n⏰ {datetime.now().strftime('%H:%M')} | ⚠️ <i>تحلیل الگوریتمی</i>"
    return msg

# ==================== اسکنر ====================

def scan_binance():
    results = []
    logger.info(f"اسکن {len(BINANCE_SYMBOLS)} ارز Binance...")
    for sym in BINANCE_SYMBOLS:
        if is_already_sent(sym):
            continue
        try:
            df_1d = get_klines(sym,"1d",50)
            df_4h = get_klines(sym,"4h",60)
            if df_1d is None or len(df_1d) < VOLUME_WINDOW+5:
                continue
            ticker = get_ticker_24h(sym)
            score, sigs, risks, risk = score_binance(df_1d, df_4h, ticker)
            if score >= PUMP_SCORE_MIN:
                results.append({"type":"binance","symbol":sym,"score":score,
                                 "signals":sigs,"risks":risks,"risk":risk,
                                 "df_1d":df_1d,"df_4h":df_4h,"ticker":ticker})
                logger.info(f"✅ {sym}: {score}/100 ریسک={risk}%")
            time.sleep(0.15)
        except Exception as e:
            logger.error(f"خطا {sym}: {e}")
    return sorted(results, key=lambda x: x["score"], reverse=True)

def get_dex_latest_boosted():
    """توکن‌های boosted از DexScreener"""
    try:
        r = requests.get("https://api.dexscreener.com/token-boosts/latest/v1", timeout=10)
        if r.status_code == 200:
            return r.json() or []
    except:
        pass
    return []

def get_dex_top_boosted():
    """توکن‌های top boosted"""
    try:
        r = requests.get("https://api.dexscreener.com/token-boosts/top/v1", timeout=10)
        if r.status_code == 200:
            return r.json() or []
    except:
        pass
    return []

def get_pair_from_token(ca, chain):
    """گرفتن جفت معاملاتی از آدرس توکن"""
    try:
        r = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{ca}", timeout=10)
        if r.status_code == 200:
            pairs = r.json().get("pairs", []) or []
            # بهترین جفت بر اساس حجم
            pairs = [p for p in pairs if p.get("chainId") == chain]
            if pairs:
                return max(pairs, key=lambda x: float(x.get("volume",{}).get("h24",0) or 0))
    except:
        pass
    return None

def scan_dex():
    results = []
    seen = set()
    logger.info("اسکن DEX...")

    # منبع 1: توکن‌های boosted (واقعی‌ترین سیگنال)
    all_boosted = []
    try:
        all_boosted += get_dex_latest_boosted()
        all_boosted += get_dex_top_boosted()
    except:
        pass

    for item in all_boosted:
        try:
            ca    = item.get("tokenAddress","")
            chain = item.get("chainId","")
            if not ca or not chain: continue
            key = f"{chain}_{ca}"
            if key in seen: continue
            seen.add(key)

            signal_key = f"DEX_{key}"
            if is_already_sent(signal_key): continue

            pair = get_pair_from_token(ca, chain)
            if not pair: continue

            vol24h = float(pair.get("volume",{}).get("h24",0) or 0)
            liq    = float(pair.get("liquidity",{}).get("usd",0) or 0)
            if vol24h < 20000 or liq < 10000: continue

            score, sigs, risks, risk = score_dex(pair)
            sym = pair.get("baseToken",{}).get("symbol","?")
            if score >= PUMP_SCORE_MIN:
                results.append({"type":"dex","pair":pair,"score":score,
                                "signals":sigs,"risks":risks,"risk":risk,
                                "signal_key":signal_key})
                logger.info(f"✅ DEX Boosted {sym}/{chain}: {score}/100 ریسک={risk}%")
            time.sleep(0.2)
        except Exception as e:
            logger.error(f"خطا boosted item: {e}")

    # منبع 2: جستجوی مستقیم با کلمات کلیدی پرمعنا
    keywords = ["usdt","sol","eth","bnb","pepe","doge","shib","ai","btc"]
    for kw in keywords:
        try:
            pairs = search_dex(kw, min_volume=30000, min_liquidity=15000)
            for pair in pairs[:5]:
                ca    = pair.get("baseToken",{}).get("address","")
                chain = pair.get("chainId","")
                key   = f"{chain}_{ca}"
                sym   = pair.get("baseToken",{}).get("symbol","?")
                signal_key = f"DEX_{key}"

                if key in seen or not ca: continue
                if is_already_sent(signal_key): continue
                seen.add(key)

                # فیلتر: فقط پامپ‌های اخیر
                p1h = float(pair.get("priceChange",{}).get("h1",0) or 0)
                if p1h < 1: continue  # حداقل 1% رشد در 1 ساعت

                score, sigs, risks, risk = score_dex(pair)
                if score >= PUMP_SCORE_MIN:
                    results.append({"type":"dex","pair":pair,"score":score,
                                    "signals":sigs,"risks":risks,"risk":risk,
                                    "signal_key":signal_key})
                    logger.info(f"✅ DEX Search {sym}/{chain}: {score}/100 ریسک={risk}%")
            time.sleep(0.25)
        except Exception as e:
            logger.error(f"خطا DEX '{kw}': {e}")

    # منبع 3: Moralis top gainers
    try:
        gainers = get_moralis_top_gainers()
        for g in gainers[:15]:
            try:
                ca    = g.get("tokenAddress","") or g.get("address","")
                chain = g.get("chain","ethereum").lower()
                if not ca: continue
                key = f"{chain}_{ca}"
                if key in seen: continue
                seen.add(key)
                signal_key = f"DEX_{key}"
                if is_already_sent(signal_key): continue

                pair = get_pair_from_token(ca, chain)
                if not pair: continue

                vol24h = float(pair.get("volume",{}).get("h24",0) or 0)
                liq    = float(pair.get("liquidity",{}).get("usd",0) or 0)
                if vol24h < 20000 or liq < 10000: continue

                score, sigs, risks, risk = score_dex(pair)
                sym = pair.get("baseToken",{}).get("symbol","?")
                if score >= PUMP_SCORE_MIN:
                    results.append({"type":"dex","pair":pair,"score":score,
                                    "signals":sigs,"risks":risks,"risk":risk,
                                    "signal_key":signal_key})
                    logger.info(f"✅ Moralis Gainer {sym}: {score}/100 ریسک={risk}%")
                time.sleep(0.2)
            except Exception as e:
                logger.error(f"خطا moralis gainer: {e}")
    except Exception as e:
        logger.error(f"خطا moralis gainers: {e}")

    return sorted(results, key=lambda x: x["score"], reverse=True)

# ==================== اجرا ====================

def run_bot():
    send_msg(f"""🤖 <b>Ultra Crypto Pump Bot v3.1 فعال شد</b>

📊 منابع:
  • Binance ({len(BINANCE_SYMBOLS)} ارز)
  • DexScreener (Boosted + Search)
  • Moralis (Top Gainers)
🛡 ضد تکرار: هر سیگنال حداقل 1 ساعت فاصله
🎯 حداقل امتیاز: {PUMP_SCORE_MIN}/100
⏱ اسکن: هر {SCAN_INTERVAL//60} دقیقه
✅ آماده...""")

    while True:
        try:
            b_results = scan_binance()
            d_results = scan_dex()
            all_res   = (b_results + d_results)
            all_res.sort(key=lambda x: x["score"], reverse=True)

            if all_res:
                summary = f"🔍 <b>اسکن {datetime.now().strftime('%H:%M')}</b>\n\n"
                summary += f"🟢 Binance: {len(b_results)} | 🔗 DEX: {len(d_results)}\n\n"
                for r in all_res[:5]:
                    sym = r["symbol"] if r["type"]=="binance" else r["pair"].get("baseToken",{}).get("symbol","?")
                    bar = "█"*(r["score"]//10) + "░"*(10-r["score"]//10)
                    summary += f"• <b>{sym}</b>: {r['score']}/100 [{bar}] ⚠️{r['risk']}%\n"
                send_msg(summary)
                time.sleep(1)

                for res in all_res[:3]:
                    try:
                        if res["type"] == "binance":
                            chart   = create_chart(res["symbol"],res["df_1d"],res["df_4h"],res["ticker"])
                            caption = fmt_binance(res["symbol"],res["score"],res["signals"],res["risks"],res["risk"],res["ticker"])
                            mark_as_sent(res["symbol"])
                        else:
                            chart   = create_dex_chart(res["pair"])
                            caption = fmt_dex(res["pair"],res["score"],res["signals"],res["risks"],res["risk"])
                            mark_as_sent(res["signal_key"])
                        send_photo(chart, caption)
                        time.sleep(3)
                    except Exception as e:
                        logger.error(f"خطا در ارسال: {e}")
            else:
                logger.info("سیگنالی پیدا نشد")

        except Exception as e:
            logger.error(f"خطای کلی: {e}")
            send_msg(f"⚠️ خطا: {str(e)[:100]}")

        logger.info(f"⏳ انتظار {SCAN_INTERVAL}s...")
        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    run_bot()
