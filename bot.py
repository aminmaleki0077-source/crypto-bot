#!/usr/bin/env python3
"""
🚀 Ultra Crypto Pump Bot - DEX Edition
DexScreener + Binance + همه زنجیره‌ها
Volume + Smart Money Flow + Multi-Timeframe
"""

import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from datetime import datetime
import io, time, logging, json

# ==================== تنظیمات ====================
TELEGRAM_TOKEN = "8286137689:AAEbA-vB41YSHfYj8YIe_MBeymRHqXzu7l4"
CHAT_ID = "767354973"

BINANCE_BASE   = "https://api.binance.com/api/v3"
DEX_BASE       = "https://api.dexscreener.com/latest/dex"
DEX_TOKEN_BASE = "https://api.dexscreener.com/latest/dex/tokens"

# پارامترهای تحلیل
VOLUME_WINDOW        = 20
VOLUME_STD_THRESHOLD = 2.0
SMF_WINDOW           = 10
SCAN_INTERVAL        = 180    # هر 3 دقیقه
PUMP_SCORE_MIN       = 62     # حداقل امتیاز

# زنجیره‌های پشتیبانی‌شده در DexScreener
CHAINS = ["solana", "ethereum", "bsc", "base", "arbitrum", "polygon", "avalanche", "ton"]

# ارزهای بزرگ Binance (تحلیل دقیق‌تر با کندل)
BINANCE_SYMBOLS = [
    "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT","DOGEUSDT",
    "AVAXUSDT","DOTUSDT","MATICUSDT","LINKUSDT","UNIUSDT","ATOMUSDT","LTCUSDT",
    "NEARUSDT","TRXUSDT","APTUSDT","ARBUSDT","OPUSDT","INJUSDT","SUIUSDT",
    "PEPEUSDT","WLDUSDT","TIAUSDT","SEIUSDT","JUPUSDT","WIFUSDT","BONKUSDT",
    "MEMEUSDT","FLOKIUSDT","1000SHIBUSDT","NOTUSDT","HMSTRUSDT",
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# ==================== دریافت داده Binance ====================

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
        r = requests.get(f"{BINANCE_BASE}/ticker/24hr", params={"symbol": symbol}, timeout=10)
        return r.json()
    except:
        return {}

# ==================== دریافت داده DexScreener ====================

def get_dex_trending():
    """دریافت توکن‌های ترند از DexScreener"""
    tokens = []
    try:
        # جستجوی ترند برای هر زنجیره
        for chain in CHAINS:
            try:
                r = requests.get(f"{DEX_BASE}/search?q=pump", timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    pairs = data.get("pairs", []) or []
                    for p in pairs:
                        if p.get("chainId") == chain:
                            tokens.append(p)
                time.sleep(0.2)
            except:
                continue
    except:
        pass
    return tokens

def get_dex_boosted():
    """توکن‌های boosted (تبلیغ‌شده و پرحجم)"""
    try:
        r = requests.get("https://api.dexscreener.com/token-boosts/top/v1", timeout=10)
        if r.status_code == 200:
            return r.json() or []
    except:
        pass
    return []

def get_dex_new_tokens():
    """توکن‌های جدید با حجم بالا"""
    results = []
    try:
        for chain in CHAINS[:4]:  # فقط زنجیره‌های اصلی
            r = requests.get(f"https://api.dexscreener.com/token-profiles/latest/v1", timeout=10)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    results.extend([d for d in data if d.get("chainId") == chain])
            time.sleep(0.2)
    except:
        pass
    return results

def get_pair_details(pair_address, chain):
    """جزئیات کامل یک جفت معاملاتی"""
    try:
        r = requests.get(f"{DEX_BASE}/pairs/{chain}/{pair_address}", timeout=10)
        if r.status_code == 200:
            data = r.json()
            pairs = data.get("pairs", [])
            return pairs[0] if pairs else None
    except:
        return None

def search_dex_token(query):
    """جستجوی توکن در DexScreener"""
    try:
        r = requests.get(f"{DEX_BASE}/search?q={query}", timeout=10)
        if r.status_code == 200:
            data = r.json()
            pairs = data.get("pairs", []) or []
            # فیلتر: حجم بالا و liquidity کافی
            filtered = [p for p in pairs
                       if float(p.get("volume", {}).get("h24", 0) or 0) > 50000
                       and float(p.get("liquidity", {}).get("usd", 0) or 0) > 10000]
            filtered.sort(key=lambda x: float(x.get("volume", {}).get("h24", 0) or 0), reverse=True)
            return filtered[:3]
    except:
        pass
    return []

# ==================== محاسبات تحلیلی ====================

def calculate_smart_money_flow(df):
    hl = (df["high"] - df["low"]).replace(0, 0.0001)
    smf = ((df["close"] - df["low"]) / hl) * df["volume"]
    return smf.rolling(SMF_WINDOW).mean() / df["volume"].rolling(SMF_WINDOW).mean() * 100

def calculate_volume_analysis(df):
    vol_mean  = df["volume"].rolling(VOLUME_WINDOW).mean()
    vol_std   = df["volume"].rolling(VOLUME_WINDOW).std()
    vol_z     = (df["volume"] - vol_mean) / vol_std
    low_thr   = vol_mean - VOLUME_STD_THRESHOLD * vol_std
    return vol_mean, vol_std, vol_z, low_thr

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, 0.0001)
    return 100 - (100 / (1 + rs))

def calculate_pump_score_binance(df, ticker):
    """امتیاز پامپ برای ارزهای Binance"""
    score = 0
    signals = []
    risk_factors = []

    if len(df) < VOLUME_WINDOW + 5:
        return 0, [], [], 50

    vol_mean, vol_std, vol_z, _ = calculate_volume_analysis(df)
    smf     = calculate_smart_money_flow(df)
    rsi     = calculate_rsi(df["close"])
    last_z  = vol_z.iloc[-1]
    last_smf = smf.iloc[-1] if not pd.isna(smf.iloc[-1]) else 50
    last_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50

    price_change_24h = float(ticker.get("priceChangePercent", 0))
    volume_24h       = float(ticker.get("quoteVolume", 0))

    # --- امتیازدهی ---
    # 1. حجم (30pt)
    if last_z > 3:
        score += 30; signals.append(f"🔥 حجم انفجاری (z={last_z:.1f})")
    elif last_z > 2:
        score += 22; signals.append(f"📈 حجم بالا (z={last_z:.1f})")
    elif last_z > 1.5:
        score += 14; signals.append(f"📊 حجم بالاتر از معمول")

    # 2. Smart Money (20pt)
    if last_smf > 72:
        score += 20; signals.append(f"💰 Smart Money قوی ({last_smf:.1f})")
    elif last_smf > 58:
        score += 12; signals.append(f"💰 Smart Money مثبت ({last_smf:.1f})")

    # 3. RSI (15pt)
    if 45 < last_rsi < 65:
        score += 15; signals.append(f"📐 RSI ایده‌آل ({last_rsi:.0f})")
    elif 35 < last_rsi <= 45:
        score += 10; signals.append(f"📐 RSI در ناحیه خرید ({last_rsi:.0f})")
    elif last_rsi > 75:
        score -= 10; risk_factors.append(f"⚠️ RSI اشباع خرید ({last_rsi:.0f})")

    # 4. تغییر قیمت (20pt)
    if 3 < price_change_24h < 20:
        score += 20; signals.append(f"💹 رشد قیمت: +{price_change_24h:.1f}%")
    elif 1 < price_change_24h <= 3:
        score += 10; signals.append(f"💹 رشد قیمت: +{price_change_24h:.1f}%")
    elif price_change_24h < -8:
        score -= 15; risk_factors.append(f"📉 افت شدید: {price_change_24h:.1f}%")

    # 5. مومنتوم قیمت (15pt)
    if len(df) >= 5:
        momentum = (df["close"].iloc[-1] / df["close"].iloc[-5] - 1) * 100
        if momentum > 5:
            score += 15; signals.append(f"🚀 مومنتوم 5 روزه: +{momentum:.1f}%")
        elif momentum > 2:
            score += 8; signals.append(f"📈 مومنتوم مثبت: +{momentum:.1f}%")

    # --- محاسبه ریسک ---
    risk = 50
    if last_rsi > 70: risk += 20
    if last_z > 3: risk += 10
    if price_change_24h > 15: risk += 15
    if volume_24h < 1_000_000: risk += 10
    if len(risk_factors) > 0: risk += 10 * len(risk_factors)
    risk = min(max(risk, 10), 95)

    return min(score, 100), signals, risk_factors, risk

def calculate_pump_score_dex(pair):
    """امتیاز پامپ برای توکن‌های DEX"""
    score = 0
    signals = []
    risk_factors = []

    try:
        vol_h1  = float(pair.get("volume", {}).get("h1", 0) or 0)
        vol_h6  = float(pair.get("volume", {}).get("h6", 0) or 0)
        vol_h24 = float(pair.get("volume", {}).get("h24", 0) or 0)
        liq     = float(pair.get("liquidity", {}).get("usd", 0) or 0)
        mc      = float(pair.get("marketCap", 0) or 0)
        p1h     = float(pair.get("priceChange", {}).get("h1", 0) or 0)
        p6h     = float(pair.get("priceChange", {}).get("h6", 0) or 0)
        p24h    = float(pair.get("priceChange", {}).get("h24", 0) or 0)
        txns_h1 = pair.get("txns", {}).get("h1", {})
        buys_h1 = int(txns_h1.get("buys", 0) or 0)
        sells_h1= int(txns_h1.get("sells", 0) or 0)

        # 1. رشد حجم (25pt)
        if vol_h24 > 0:
            vol_accel = (vol_h1 * 24) / vol_h24  # شتاب حجم
            if vol_accel > 3:
                score += 25; signals.append(f"🔥 شتاب حجم: {vol_accel:.1f}x")
            elif vol_accel > 2:
                score += 18; signals.append(f"📈 رشد حجم: {vol_accel:.1f}x")
            elif vol_accel > 1.5:
                score += 10; signals.append(f"📊 حجم در حال رشد")

        # 2. نسبت buy/sell (20pt)
        total_txns = buys_h1 + sells_h1
        if total_txns > 0:
            buy_ratio = buys_h1 / total_txns
            if buy_ratio > 0.7:
                score += 20; signals.append(f"💚 فشار خرید: {buy_ratio*100:.0f}%")
            elif buy_ratio > 0.6:
                score += 12; signals.append(f"💚 خریداران غالب: {buy_ratio*100:.0f}%")
            elif buy_ratio < 0.4:
                risk_factors.append(f"🔴 فشار فروش: {(1-buy_ratio)*100:.0f}%")

        # 3. تغییر قیمت (25pt)
        if 5 < p1h < 30:
            score += 25; signals.append(f"🚀 پامپ 1h: +{p1h:.1f}%")
        elif 2 < p1h <= 5:
            score += 15; signals.append(f"📈 رشد 1h: +{p1h:.1f}%")
        if p6h > 10:
            score += 10; signals.append(f"📈 رشد 6h: +{p6h:.1f}%")

        # 4. نقدینگی کافی (15pt)
        if liq > 500_000:
            score += 15; signals.append(f"💧 نقدینگی بالا: ${liq:,.0f}")
        elif liq > 100_000:
            score += 8; signals.append(f"💧 نقدینگی متوسط: ${liq:,.0f}")
        elif liq < 20_000:
            risk_factors.append(f"⚠️ نقدینگی پایین: ${liq:,.0f}")

        # 5. نسبت حجم به مارکت‌کپ (15pt)
        if mc > 0:
            vol_mc = vol_h24 / mc
            if vol_mc > 0.5:
                score += 15; signals.append(f"⚡ حجم/MC: {vol_mc:.2f} (بسیار بالا)")
            elif vol_mc > 0.2:
                score += 8; signals.append(f"⚡ حجم/MC: {vol_mc:.2f}")

        # --- ریسک ---
        risk = 50
        if liq < 50_000: risk += 25
        if mc > 0 and mc < 100_000: risk += 20
        if p1h > 50: risk += 30; risk_factors.append(f"⚠️ پامپ شدید {p1h:.0f}% (احتمال دامپ)")
        if p24h < -10: risk += 15
        if buys_h1 + sells_h1 < 10: risk += 20; risk_factors.append("⚠️ تعداد تراکنش کم")
        risk = min(max(risk, 15), 95)

        return min(score, 100), signals, risk_factors, risk

    except Exception as e:
        logger.error(f"خطا در محاسبه امتیاز DEX: {e}")
        return 0, [], [], 80

# ==================== رسم چارت ====================

def create_binance_chart(symbol, df_1d, df_4h, ticker):
    """چارت حرفه‌ای با دو تایم‌فریم"""
    fig = plt.figure(figsize=(16, 12), facecolor='#0d1117')
    gs = gridspec.GridSpec(3, 2, height_ratios=[3, 2, 2], hspace=0.08, wspace=0.3)

    vol_mean, _, vol_z, low_thr = calculate_volume_analysis(df_1d)
    smf_1d = calculate_smart_money_flow(df_1d)
    smf_4h = calculate_smart_money_flow(df_4h) if df_4h is not None else None
    rsi_1d = calculate_rsi(df_1d["close"])

    def draw_candles(ax, df, title):
        ax.set_facecolor('#0d1117')
        x = range(len(df))
        for i in x:
            o,h,l,c = df["open"].iloc[i],df["high"].iloc[i],df["low"].iloc[i],df["close"].iloc[i]
            col = '#26a69a' if c >= o else '#ef5350'
            ax.plot([i,i],[l,h], color=col, linewidth=0.8)
            ax.add_patch(plt.Rectangle((i-0.3, min(o,c)), 0.6, abs(c-o), color=col, alpha=0.9))
        cp = float(ticker.get("lastPrice", df["close"].iloc[-1]))
        ax.axhline(y=cp, color='#00e5ff', linestyle='--', linewidth=0.8, alpha=0.7)
        ax.annotate(f'{cp:.5g}', xy=(len(df)-1, cp), fontsize=7, color='white',
                   bbox=dict(boxstyle='round,pad=0.2', facecolor='#00e5ff', alpha=0.85, edgecolor='none'), ha='right')
        ax.set_title(title, color='white', fontsize=9, pad=4)
        ax.set_ylabel('Price', color='#666', fontsize=7)
        ax.tick_params(colors='#666', labelsize=6)
        for sp in ax.spines.values(): sp.set_color('#21262d')
        ax.set_xlim(-1, len(df))
        step = max(1, len(df)//6)
        ticks = list(range(0, len(df), step))
        ax.set_xticks(ticks)
        ax.set_xticklabels([df["date"].iloc[i].strftime('%m/%d') for i in ticks], fontsize=5, color='#666')

    # کندل 1D
    ax1 = fig.add_subplot(gs[0, 0])
    draw_candles(ax1, df_1d, f'{symbol} — Daily')

    # کندل 4H
    ax2 = fig.add_subplot(gs[0, 1])
    if df_4h is not None and len(df_4h) > 5:
        draw_candles(ax2, df_4h, f'{symbol} — 4H')
    else:
        ax2.set_facecolor('#0d1117')
        ax2.text(0.5, 0.5, 'No 4H Data', ha='center', va='center', color='#666', transform=ax2.transAxes)

    # Volume 1D
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.set_facecolor('#0d1117')
    x1d = range(len(df_1d))
    bar_colors = ['#ffd700' if vol_z.iloc[i] > 2 else ('#26a69a' if df_1d["close"].iloc[i] >= df_1d["open"].iloc[i] else '#ef5350') for i in x1d]
    ax3.bar(x1d, df_1d["volume"], color=bar_colors, alpha=0.8, width=0.8)
    ax3.plot(x1d, vol_mean, color='#00e5ff', linewidth=1.2, label='Mean')
    ax3.plot(x1d, low_thr,  color='#ffd700', linewidth=0.8, linestyle='--', label='Low 2σ')
    ax3.set_title('Volume (Daily)', color='white', fontsize=8, pad=3)
    ax3.set_ylabel('Vol', color='#666', fontsize=7)
    ax3.tick_params(colors='#666', labelsize=6)
    ax3.yaxis.set_major_formatter(plt.FuncFormatter(lambda v,p: f'{v/1e6:.0f}M' if v>=1e6 else f'{v/1e3:.0f}K'))
    for sp in ax3.spines.values(): sp.set_color('#21262d')

    # RSI
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.set_facecolor('#0d1117')
    ax4.plot(range(len(rsi_1d)), rsi_1d, color='#ab47bc', linewidth=1.5)
    ax4.axhline(70, color='#ef5350', linestyle='--', linewidth=0.8, alpha=0.7)
    ax4.axhline(30, color='#26a69a', linestyle='--', linewidth=0.8, alpha=0.7)
    ax4.axhline(50, color='#555', linestyle='-', linewidth=0.5, alpha=0.5)
    ax4.fill_between(range(len(rsi_1d)), rsi_1d, 50,
                    where=(rsi_1d > 50), alpha=0.1, color='#26a69a')
    ax4.fill_between(range(len(rsi_1d)), rsi_1d, 50,
                    where=(rsi_1d < 50), alpha=0.1, color='#ef5350')
    ax4.annotate(f'RSI: {rsi_1d.iloc[-1]:.0f}', xy=(len(rsi_1d)-1, rsi_1d.iloc[-1]),
                fontsize=8, color='white',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#ab47bc', alpha=0.9, edgecolor='none'), ha='right')
    ax4.set_ylim(0, 100)
    ax4.set_title('RSI (14)', color='white', fontsize=8, pad=3)
    ax4.tick_params(colors='#666', labelsize=6)
    for sp in ax4.spines.values(): sp.set_color('#21262d')

    # Smart Money Flow
    ax5 = fig.add_subplot(gs[2, :])
    ax5.set_facecolor('#0d1117')
    x1d_smf = range(len(smf_1d))
    ax5.plot(x1d_smf, smf_1d, color='#ff7043', linewidth=1.5, label='SMF Daily')
    if smf_4h is not None and df_4h is not None:
        x4h_norm = [i * len(df_1d) / len(df_4h) for i in range(len(smf_4h))]
        ax5.plot(x4h_norm, smf_4h, color='#42a5f5', linewidth=1, alpha=0.7, label='SMF 4H')

    smf_prev = smf_1d.iloc[-SMF_WINDOW] if len(smf_1d) >= SMF_WINDOW else smf_1d.iloc[0]
    smf_trend_val = ((smf_1d.iloc[-1] - smf_prev) / abs(smf_prev) * 100) if smf_prev != 0 else 0
    trend_x = list(range(max(0, len(df_1d)-SMF_WINDOW), len(df_1d)))
    trend_y = smf_1d.iloc[-SMF_WINDOW:].values
    if len(trend_x) > 1:
        z = np.polyfit(trend_x, trend_y, 1)
        p = np.poly1d(z)
        tcol = '#26a69a' if z[0] > 0 else '#ef5350'
        ax5.plot(trend_x, p(trend_x), color=tcol, linewidth=1.5, linestyle='--')
    trend_lbl = f'{"↑ Uptrend" if smf_trend_val > 0 else "↓ Downtrend"}: {smf_trend_val:+.1f}%'
    trend_bg  = '#26a69a' if smf_trend_val > 0 else '#ef5350'
    ax5.annotate(trend_lbl, xy=(len(df_1d)-1, smf_1d.iloc[-1]), fontsize=8, color='white',
                bbox=dict(boxstyle='round,pad=0.3', facecolor=trend_bg, alpha=0.9, edgecolor='none'), ha='right')
    ax5.set_title('Smart Money Flow', color='white', fontsize=8, pad=3)
    ax5.set_ylabel('Ratio', color='#666', fontsize=7)
    ax5.tick_params(colors='#666', labelsize=6)
    ax5.legend(facecolor='#0d1117', edgecolor='#21262d', labelcolor='white', fontsize=7, loc='upper left')
    for sp in ax5.spines.values(): sp.set_color('#21262d')

    fig.suptitle(f'📊 {symbol} — Volume & Smart Money Analysis', color='white', fontsize=12, y=0.99)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=110, bbox_inches='tight', facecolor='#0d1117')
    buf.seek(0)
    plt.close(fig)
    return buf

def create_dex_chart(pair):
    """چارت ساده برای توکن‌های DEX"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), facecolor='#0d1117')

    name    = pair.get("baseToken", {}).get("symbol", "TOKEN")
    chain   = pair.get("chainId", "")
    price   = float(pair.get("priceUsd", 0) or 0)
    liq     = float(pair.get("liquidity", {}).get("usd", 0) or 0)
    mc      = float(pair.get("marketCap", 0) or 0)
    vol_h1  = float(pair.get("volume", {}).get("h1", 0) or 0)
    vol_h6  = float(pair.get("volume", {}).get("h6", 0) or 0)
    vol_h24 = float(pair.get("volume", {}).get("h24", 0) or 0)
    p1h  = float(pair.get("priceChange", {}).get("h1", 0) or 0)
    p6h  = float(pair.get("priceChange", {}).get("h6", 0) or 0)
    p24h = float(pair.get("priceChange", {}).get("h24", 0) or 0)

    # نمودار تغییر قیمت
    ax1 = axes[0]
    ax1.set_facecolor('#0d1117')
    timeframes = ['1H', '6H', '24H']
    changes    = [p1h, p6h, p24h]
    colors     = ['#26a69a' if c > 0 else '#ef5350' for c in changes]
    bars = ax1.bar(timeframes, changes, color=colors, alpha=0.85, width=0.5)
    for bar, val in zip(bars, changes):
        ax1.text(bar.get_x() + bar.get_width()/2., bar.get_height() + (0.5 if val >= 0 else -1.5),
                f'{val:+.1f}%', ha='center', va='bottom' if val >= 0 else 'top',
                color='white', fontsize=10, fontweight='bold')
    ax1.axhline(0, color='#444', linewidth=0.8)
    ax1.set_title(f'{name} — Price Change %', color='white', fontsize=10)
    ax1.tick_params(colors='#888', labelsize=9)
    ax1.set_facecolor('#0d1117')
    for sp in ax1.spines.values(): sp.set_color('#21262d')

    # نمودار حجم
    ax2 = axes[1]
    ax2.set_facecolor('#0d1117')
    vols   = [vol_h1, vol_h6, vol_h24]
    vlabels= ['1H', '6H', '24H']
    vcols  = ['#ffd700', '#42a5f5', '#ab47bc']
    bars2  = ax2.bar(vlabels, vols, color=vcols, alpha=0.85, width=0.5)
    for bar, val in zip(bars2, vols):
        label = f'${val/1e6:.2f}M' if val >= 1e6 else f'${val/1e3:.1f}K'
        ax2.text(bar.get_x() + bar.get_width()/2., bar.get_height(),
                label, ha='center', va='bottom', color='white', fontsize=9)
    ax2.set_title(f'{name} — Volume (USD)', color='white', fontsize=10)
    ax2.tick_params(colors='#888', labelsize=9)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda v,p: f'${v/1e6:.1f}M' if v>=1e6 else f'${v/1e3:.0f}K'))
    for sp in ax2.spines.values(): sp.set_color('#21262d')

    chain_icon = {"solana":"◎","ethereum":"Ξ","bsc":"⬡","base":"🔵","arbitrum":"🔷"}.get(chain,"🔗")
    fig.suptitle(f'{chain_icon} {name}/{pair.get("quoteToken",{}).get("symbol","?")} on {chain.upper()} | 💰 ${price:.6g}',
                color='white', fontsize=11, y=1.01)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=110, bbox_inches='tight', facecolor='#0d1117')
    buf.seek(0)
    plt.close(fig)
    return buf

# ==================== تلگرام ====================

def send_photo(buf, caption):
    buf.seek(0)
    r = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
        files={"photo": ("chart.png", buf, "image/png")},
        data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"},
        timeout=30)
    return r.status_code == 200

def send_msg(text):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
        timeout=10)

def risk_bar(risk):
    filled = round(risk / 10)
    bar = "🟥" * filled + "⬜" * (10 - filled)
    return bar

def pump_bar(score):
    filled = round(score / 10)
    bar = "🟩" * filled + "⬜" * (10 - filled)
    return bar

def format_binance_signal(symbol, score, signals, risk_factors, risk, ticker, df_1d):
    price      = float(ticker.get("lastPrice", 0))
    change_24h = float(ticker.get("priceChangePercent", 0))
    vol_24h    = float(ticker.get("quoteVolume", 0))
    high_24h   = float(ticker.get("highPrice", 0))
    low_24h    = float(ticker.get("lowPrice", 0))

    if score >= 80:   emoji, strength = "🚨🚀", "بسیار قوی"
    elif score >= 65: emoji, strength = "🟢🔥", "قوی"
    else:             emoji, strength = "🟡📊", "متوسط"

    # تخمین درصد پامپ بر اساس امتیاز و مومنتوم
    pump_est = round(score * 0.4 + (change_24h if change_24h > 0 else 0) * 0.3, 1)

    buy_link = f"https://www.binance.com/en/trade/{symbol.replace('USDT','_USDT')}"

    msg = f"""{emoji} <b>سیگنال Binance: #{symbol}</b>

💰 قیمت: <code>{price:.6g} USDT</code>
📈 تغییر 24h: <b>{change_24h:+.2f}%</b>
🔺 High: <code>{high_24h:.6g}</code> | 🔻 Low: <code>{low_24h:.6g}</code>
📦 حجم 24h: <code>${vol_24h:,.0f}</code>

━━━━━━━━━━━━━━━━━━
🎯 <b>امتیاز پامپ: {score}/100</b>
{pump_bar(score)}

⚡ <b>پتانسیل پامپ: ~{pump_est:.1f}%</b>
⚠️ <b>درصد ریسک: {risk}%</b>
{risk_bar(risk)}
━━━━━━━━━━━━━━━━━━

✅ <b>سیگنال‌ها:</b>
"""
    for s in signals:
        msg += f"  • {s}\n"

    if risk_factors:
        msg += "\n🚩 <b>عوامل ریسک:</b>\n"
        for r in risk_factors:
            msg += f"  • {r}\n"

    msg += f"""
🛒 <b>لینک خرید:</b>
<a href="{buy_link}">Binance — {symbol}</a>

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC
⚠️ <i>تحلیل الگوریتمی — نه توصیه مالی</i>"""
    return msg

def format_dex_signal(pair, score, signals, risk_factors, risk):
    base    = pair.get("baseToken", {})
    quote   = pair.get("quoteToken", {})
    chain   = pair.get("chainId", "")
    name    = base.get("name", "")
    symbol  = base.get("symbol", "")
    ca      = base.get("address", "N/A")
    price   = float(pair.get("priceUsd", 0) or 0)
    p1h     = float(pair.get("priceChange", {}).get("h1", 0) or 0)
    p24h    = float(pair.get("priceChange", {}).get("h24", 0) or 0)
    vol_24h = float(pair.get("volume", {}).get("h24", 0) or 0)
    liq     = float(pair.get("liquidity", {}).get("usd", 0) or 0)
    mc      = float(pair.get("marketCap", 0) or 0)
    dex_url = pair.get("url", "")
    pair_addr = pair.get("pairAddress", "")

    if score >= 80:   emoji, strength = "🚨🚀", "بسیار قوی"
    elif score >= 65: emoji, strength = "🟢🔥", "قوی"
    else:             emoji, strength = "🟡📊", "متوسط"

    pump_est = round(score * 0.45 + max(p1h, 0) * 0.3, 1)

    chain_icon = {"solana":"◎ Solana","ethereum":"Ξ Ethereum","bsc":"⬡ BSC",
                  "base":"🔵 Base","arbitrum":"🔷 Arbitrum","polygon":"🟣 Polygon",
                  "avalanche":"🔺 Avalanche","ton":"💎 TON"}.get(chain, f"🔗 {chain.upper()}")

    # لینک‌های خرید بر اساس زنجیره
    buy_links = {
        "solana":   f"https://raydium.io/swap/?inputCurrency=sol&outputCurrency={ca}",
        "ethereum": f"https://app.uniswap.org/swap?outputCurrency={ca}",
        "bsc":      f"https://pancakeswap.finance/swap?outputCurrency={ca}",
        "base":     f"https://app.uniswap.org/swap?chain=base&outputCurrency={ca}",
        "arbitrum": f"https://app.uniswap.org/swap?chain=arbitrum&outputCurrency={ca}",
        "polygon":  f"https://app.uniswap.org/swap?chain=polygon&outputCurrency={ca}",
    }
    buy_url = buy_links.get(chain, dex_url)

    msg = f"""{emoji} <b>سیگنال DEX: #{symbol}</b> ({name})
🔗 زنجیره: <b>{chain_icon}</b>

💰 قیمت: <code>${price:.8g}</code>
📈 تغییر 1h: <b>{p1h:+.2f}%</b> | 24h: <b>{p24h:+.2f}%</b>
📦 حجم 24h: <code>${vol_24h:,.0f}</code>
💧 نقدینگی: <code>${liq:,.0f}</code>
🏦 Market Cap: <code>${mc:,.0f}</code>

━━━━━━━━━━━━━━━━━━
🎯 <b>امتیاز پامپ: {score}/100</b>
{pump_bar(score)}

⚡ <b>پتانسیل پامپ: ~{pump_est:.1f}%</b>
⚠️ <b>درصد ریسک: {risk}%</b>
{risk_bar(risk)}
━━━━━━━━━━━━━━━━━━

📋 <b>آدرس قرارداد:</b>
<code>{ca}</code>

✅ <b>سیگنال‌ها:</b>
"""
    for s in signals:
        msg += f"  • {s}\n"

    if risk_factors:
        msg += "\n🚩 <b>عوامل ریسک:</b>\n"
        for r in risk_factors:
            msg += f"  • {r}\n"

    msg += f"""
🛒 <b>لینک خرید:</b>
<a href="{buy_url}">خرید روی DEX</a>

📊 <b>DexScreener:</b>
<a href="{dex_url}">مشاهده چارت</a>

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC
⚠️ <i>تحلیل الگوریتمی — نه توصیه مالی</i>"""
    return msg

# ==================== اسکنر ====================

def scan_binance():
    results = []
    logger.info(f"اسکن {len(BINANCE_SYMBOLS)} ارز Binance...")
    for symbol in BINANCE_SYMBOLS:
        try:
            df_1d = get_klines(symbol, "1d", 50)
            df_4h = get_klines(symbol, "4h", 60)
            if df_1d is None or len(df_1d) < VOLUME_WINDOW + 5:
                continue
            ticker = get_ticker_24h(symbol)
            score, signals, risk_factors, risk = calculate_pump_score_binance(df_1d, ticker)
            if score >= PUMP_SCORE_MIN:
                smf = calculate_smart_money_flow(df_1d)
                smf_prev = smf.iloc[-SMF_WINDOW] if len(smf) >= SMF_WINDOW else smf.iloc[0]
                results.append({
                    "type": "binance", "symbol": symbol, "score": score,
                    "signals": signals, "risk_factors": risk_factors, "risk": risk,
                    "df_1d": df_1d, "df_4h": df_4h, "ticker": ticker
                })
                logger.info(f"✅ Binance {symbol}: score={score} risk={risk}%")
            time.sleep(0.15)
        except Exception as e:
            logger.error(f"خطا {symbol}: {e}")
    return sorted(results, key=lambda x: x["score"], reverse=True)

def scan_dex():
    results = []
    logger.info("اسکن توکن‌های DEX...")

    # جستجوهای مختلف
    queries = ["trending", "pump", "moon", "gem", "new", "hot"]
    seen_addresses = set()

    for query in queries:
        try:
            pairs = search_dex_token(query)
            for pair in pairs:
                ca = pair.get("baseToken", {}).get("address", "")
                if ca in seen_addresses or not ca:
                    continue
                seen_addresses.add(ca)

                score, signals, risk_factors, risk = calculate_pump_score_dex(pair)
                if score >= PUMP_SCORE_MIN:
                    results.append({
                        "type": "dex", "pair": pair, "score": score,
                        "signals": signals, "risk_factors": risk_factors, "risk": risk
                    })
                    sym = pair.get("baseToken", {}).get("symbol", "?")
                    logger.info(f"✅ DEX {sym}: score={score} risk={risk}%")
            time.sleep(0.3)
        except Exception as e:
            logger.error(f"خطا در DEX query '{query}': {e}")

    return sorted(results, key=lambda x: x["score"], reverse=True)

def run_bot():
    send_msg(f"""🤖 <b>Ultra Crypto Pump Bot فعال شد</b>

📊 منابع: Binance + DexScreener (همه زنجیره‌ها)
🔍 تعداد ارز: {len(BINANCE_SYMBOLS)} Binance + DEX Scan
⏱ بازه اسکن: هر {SCAN_INTERVAL//60} دقیقه
🎯 حداقل امتیاز: {PUMP_SCORE_MIN}/100
🔗 زنجیره‌ها: {', '.join(CHAINS)}

✅ شروع اسکن...""")

    while True:
        try:
            # اسکن Binance
            binance_results = scan_binance()
            # اسکن DEX
            dex_results = scan_dex()

            all_results = binance_results + dex_results
            all_results.sort(key=lambda x: x["score"], reverse=True)

            if all_results:
                # خلاصه
                summary = f"🔍 <b>نتایج اسکن — {datetime.now().strftime('%H:%M')}</b>\n\n"
                summary += f"🟢 Binance: {len(binance_results)} سیگنال\n"
                summary += f"🔗 DEX: {len(dex_results)} سیگنال\n\n"
                summary += "<b>برترین سیگنال‌ها:</b>\n"
                for r in all_results[:6]:
                    if r["type"] == "binance":
                        sym = r["symbol"]
                    else:
                        sym = r["pair"].get("baseToken", {}).get("symbol", "?")
                        chain = r["pair"].get("chainId", "")[:3].upper()
                        sym = f"{sym}[{chain}]"
                    bar = "█" * (r["score"]//10) + "░" * (10 - r["score"]//10)
                    summary += f"• <b>{sym}</b>: {r['score']}/100 [{bar}] ⚠️{r['risk']}%\n"
                send_msg(summary)
                time.sleep(1)

                # ارسال جزئیات برترین‌ها
                for result in all_results[:4]:
                    try:
                        if result["type"] == "binance":
                            chart = create_binance_chart(result["symbol"], result["df_1d"], result["df_4h"], result["ticker"])
                            caption = format_binance_signal(result["symbol"], result["score"],
                                                            result["signals"], result["risk_factors"],
                                                            result["risk"], result["ticker"], result["df_1d"])
                        else:
                            chart = create_dex_chart(result["pair"])
                            caption = format_dex_signal(result["pair"], result["score"],
                                                        result["signals"], result["risk_factors"], result["risk"])
                        # تلگرام max caption = 1024
                        if len(caption) > 1020:
                            caption = caption[:1020] + "..."
                        send_photo(chart, caption)
                        time.sleep(2)
                    except Exception as e:
                        logger.error(f"خطا در ارسال سیگنال: {e}")
            else:
                logger.info("هیچ سیگنالی پیدا نشد")

        except Exception as e:
            logger.error(f"خطای کلی: {e}")
            send_msg(f"⚠️ خطا: {str(e)[:150]}")

        logger.info(f"⏳ انتظار {SCAN_INTERVAL}s...")
        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    run_bot()
