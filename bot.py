#!/usr/bin/env python3
"""Crypto Pump Signal Bot v3 - با DEX Scanner و شت‌کوین‌های جدید"""

import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from analyzer import CryptoAnalyzer
from dex_scanner import DexScanner, CHAINS
from config import BOT_TOKEN, SCAN_INTERVAL_MINUTES

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
analyzer = CryptoAnalyzer()
dex = DexScanner()

CANCEL_BTN = [[InlineKeyboardButton("❌ لغو", callback_data="cancel")]]
BACK_BTN = [[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]]

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 اسکن بازار", callback_data="scan_now"),
         InlineKeyboardButton("🔥 برترین سیگنال‌ها", callback_data="top_signals")],
        [InlineKeyboardButton("📊 تحلیل ارز خاص", callback_data="analyze_coin"),
         InlineKeyboardButton("🧪 شت‌کوین‌های جدید", callback_data="dex_menu")],
        [InlineKeyboardButton("📰 اخبار بازار", callback_data="news"),
         InlineKeyboardButton("🌐 وضعیت بازار", callback_data="status")],
        [InlineKeyboardButton("⚙️ هشدار خودکار", callback_data="set_alert"),
         InlineKeyboardButton("❓ راهنما", callback_data="help")],
    ])

def cancel_keyboard():
    return InlineKeyboardMarkup(CANCEL_BTN)

def back_keyboard():
    return InlineKeyboardMarkup(BACK_BTN)

def dex_chain_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("☀️ Solana", callback_data="dex_solana"),
         InlineKeyboardButton("🟡 BSC", callback_data="dex_bsc")],
        [InlineKeyboardButton("🔷 Ethereum", callback_data="dex_ethereum"),
         InlineKeyboardButton("🔵 Base", callback_data="dex_base")],
        [InlineKeyboardButton("🔵 Arbitrum", callback_data="dex_arbitrum"),
         InlineKeyboardButton("🌐 همه شبکه‌ها", callback_data="dex_all")],
        [InlineKeyboardButton("❌ لغو", callback_data="cancel")],
    ])

# ── Commands ───────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *ربات سیگنال کریپتو v3*\n\n"
        "✅ تحلیل تکنیکال: RSI، MACD، Bollinger، Ichimoku، EMA\n"
        "✅ تحلیل فاندامنتال: مارکت‌کپ، کامیونیتی، توسعه\n"
        "✅ شت‌کوین‌های جدید DEX: Solana، BSC، ETH، Base\n"
        "✅ لینک خرید و آدرس قرارداد\n\n"
        "⚠️ _مشاوره مالی نیست. با دقت استفاده کن._",
        parse_mode='Markdown', reply_markup=main_keyboard())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📋 *دستورات:*\n\n"
        "🔹 *بازار اصلی:*\n"
        "/scan — اسکن بازار\n"
        "/top — برترین سیگنال‌ها\n"
        "/coin BTC — تحلیل ارز\n"
        "/status — وضعیت بازار\n"
        "/news — اخبار\n\n"
        "🔹 *شت‌کوین DEX:*\n"
        "/dex — اسکن توکن‌های جدید\n"
        "/dextoken <address> — تحلیل توکن\n\n"
        "🔹 *هشدار:*\n"
        "/alert ETH 70 — هشدار پامپ\n"
        "/alerts — هشدارهای من\n"
        "/cancelalerts — حذف هشدارها\n\n"
        "/cancel — لغو عملیات"
    )
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=back_keyboard())

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("✅ لغو شد.", reply_markup=main_keyboard())

async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال اسکن بازار...", reply_markup=cancel_keyboard())
    signals = await analyzer.get_top_signals(limit=10)
    await msg.edit_text(format_signals(signals), parse_mode='Markdown', reply_markup=back_keyboard())

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال جمع‌آوری سیگنال‌ها...", reply_markup=cancel_keyboard())
    signals = await analyzer.get_top_signals(limit=10)
    await msg.edit_text(format_signals(signals), parse_mode='Markdown', reply_markup=back_keyboard())

async def coin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ مثال: `/coin BTC`", parse_mode='Markdown', reply_markup=back_keyboard())
        return
    symbol = context.args[0].upper()
    msg = await update.message.reply_text(f"⏳ تحلیل *{symbol}*...", parse_mode='Markdown', reply_markup=cancel_keyboard())
    result = await analyzer.analyze_single(symbol)
    await msg.edit_text(format_full_analysis(result), parse_mode='Markdown', reply_markup=back_keyboard())

async def dex_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧪 *اسکن شت‌کوین‌های جدید DEX*\n\nکدام شبکه؟",
        parse_mode='Markdown', reply_markup=dex_chain_keyboard())

async def dextoken_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ مثال: `/dextoken <address>`", parse_mode='Markdown')
        return
    query = " ".join(context.args)
    msg = await update.message.reply_text("⏳ در حال جستجو...", reply_markup=cancel_keyboard())
    pairs = await dex.search_token(query)
    if not pairs:
        await msg.edit_text("❌ توکنی یافت نشد.", reply_markup=back_keyboard())
        return
    pair = pairs[0]
    pump_info = dex.calc_shitcoin_pump_score(pair)
    await msg.edit_text(format_dex_token(pair, pump_info), parse_mode='Markdown',
                        disable_web_page_preview=True, reply_markup=back_keyboard())

async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❗ فرمت: `/alert ETH 65`", parse_mode='Markdown', reply_markup=back_keyboard())
        return
    symbol = context.args[0].upper()
    try: threshold = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❗ درصد باید عدد باشد.", reply_markup=back_keyboard())
        return
    chat_id = update.message.chat_id
    if 'alerts' not in context.bot_data:
        context.bot_data['alerts'] = {}
    context.bot_data['alerts'].setdefault(chat_id, [])
    context.bot_data['alerts'][chat_id].append({'symbol': symbol, 'threshold': threshold})
    await update.message.reply_text(
        f"✅ هشدار ثبت شد!\n💎 *{symbol}* — حداقل *{threshold}%*",
        parse_mode='Markdown', reply_markup=back_keyboard())

async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    alerts = context.bot_data.get('alerts', {}).get(chat_id, [])
    if not alerts:
        await update.message.reply_text("📭 هیچ هشداری ندارید.\nمثال: `/alert BTC 70`", parse_mode='Markdown', reply_markup=back_keyboard())
        return
    text = "🔔 *هشدارهای فعال:*\n\n"
    for i, a in enumerate(alerts, 1):
        text += f"{i}. *{a['symbol']}* — {a['threshold']}%\n"
    text += "\n/cancelalerts — حذف همه"
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=back_keyboard())

async def cancel_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if 'alerts' in context.bot_data:
        context.bot_data['alerts'].pop(chat_id, None)
    await update.message.reply_text("✅ تمام هشدارها حذف شدند.", reply_markup=main_keyboard())

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال دریافت اخبار...", reply_markup=cancel_keyboard())
    news = await analyzer.get_market_news()
    await msg.edit_text(format_news(news), parse_mode='Markdown', reply_markup=back_keyboard())

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال بررسی بازار...", reply_markup=cancel_keyboard())
    status = await analyzer.get_market_status()
    await msg.edit_text(format_market_status(status), parse_mode='Markdown', reply_markup=back_keyboard())

# ── Callbacks ──────────────────────────────────────────────────────────────────

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cancel":
        context.user_data.clear()
        await query.edit_message_text("✅ لغو شد.", reply_markup=main_keyboard())

    elif data == "main_menu":
        await query.edit_message_text("🤖 *منوی اصلی:*", parse_mode='Markdown', reply_markup=main_keyboard())

    elif data == "scan_now":
        await query.edit_message_text("⏳ در حال اسکن بازار...", reply_markup=cancel_keyboard())
        signals = await analyzer.get_top_signals(limit=10)
        await query.edit_message_text(format_signals(signals), parse_mode='Markdown', reply_markup=back_keyboard())

    elif data == "top_signals":
        await query.edit_message_text("⏳ در حال جمع‌آوری سیگنال‌ها...", reply_markup=cancel_keyboard())
        signals = await analyzer.get_top_signals(limit=10)
        await query.edit_message_text(format_signals(signals), parse_mode='Markdown', reply_markup=back_keyboard())

    elif data == "analyze_coin":
        await query.edit_message_text(
            "📊 دستور زیر را ارسال کن:\n\n`/coin BTC`\n`/coin ETH`\n`/coin SOL`",
            parse_mode='Markdown', reply_markup=cancel_keyboard())

    elif data == "dex_menu":
        await query.edit_message_text(
            "🧪 *اسکن شت‌کوین‌های جدید DEX*\n\nکدام شبکه؟",
            parse_mode='Markdown', reply_markup=dex_chain_keyboard())

    elif data.startswith("dex_"):
        chain = data.replace("dex_", "")
        chain_name = "همه شبکه‌ها" if chain == "all" else CHAINS.get(chain, chain)
        await query.edit_message_text(
            f"⏳ در حال اسکن توکن‌های جدید روی *{chain_name}*...\n\n_این ممکنه ۱۵-۳۰ ثانیه طول بکشه_",
            parse_mode='Markdown', reply_markup=cancel_keyboard())
        tokens = await dex.get_top_new_pumps(chain=chain, limit=8)
        text = format_dex_list(tokens, chain_name)
        await query.edit_message_text(text, parse_mode='Markdown',
                                      disable_web_page_preview=True, reply_markup=back_keyboard())

    elif data == "news":
        await query.edit_message_text("⏳ در حال دریافت اخبار...", reply_markup=cancel_keyboard())
        news = await analyzer.get_market_news()
        await query.edit_message_text(format_news(news), parse_mode='Markdown', reply_markup=back_keyboard())

    elif data == "status":
        await query.edit_message_text("⏳ در حال بررسی بازار...", reply_markup=cancel_keyboard())
        status = await analyzer.get_market_status()
        await query.edit_message_text(format_market_status(status), parse_mode='Markdown', reply_markup=back_keyboard())

    elif data == "set_alert":
        await query.edit_message_text(
            "🔔 *تنظیم هشدار:*\n\n`/alert SYMBOL PERCENT`\n\nمثال:\n`/alert BTC 75`",
            parse_mode='Markdown', reply_markup=cancel_keyboard())

    elif data == "help":
        text = (
            "📋 *دستورات:*\n\n"
            "/scan /top /coin BTC\n"
            "/dex — شت‌کوین‌های جدید\n"
            "/dextoken <address>\n"
            "/alert ETH 70\n"
            "/alerts /cancelalerts\n"
            "/news /status /cancel"
        )
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=back_keyboard())

# ── Formatters ─────────────────────────────────────────────────────────────────

def pump_bar(prob):
    filled = int(prob / 10)
    return "█" * filled + "░" * (10 - filled)

def macd_text(sig):
    return {'bullish_strong':'🟢 صعودی قوی','bullish':'🟢 صعودی',
            'neutral':'⚪ خنثی','bearish':'🔴 نزولی','bearish_strong':'🔴 نزولی قوی'}.get(sig, sig)

def bb_text(sig):
    return {'strong_oversold':'🟢 اشباع فروش شدید','oversold':'🟢 اشباع فروش',
            'neutral':'⚪ خنثی','overbought':'🔴 اشباع خرید','strong_overbought':'🔴 اشباع خرید شدید'}.get(sig, sig)

def ichi_text(sig):
    return {'above_cloud':'☁️ بالای ابر ✅','below_cloud':'☁️ زیر ابر ❌',
            'inside_cloud':'☁️ داخل ابر','neutral':'⚪ خنثی'}.get(sig, sig)

def format_signals(signals):
    if not signals:
        return "❌ سیگنالی یافت نشد."
    text = "🔥 *برترین سیگنال‌های پامپ*\n" + "─"*28 + "\n\n"
    for i, s in enumerate(signals[:10], 1):
        p = s['pump_probability']
        em = "🚀" if p >= 75 else "📈" if p >= 60 else "🔶"
        text += f"{em} *{i}. {s['symbol']}* — {s['name']}\n"
        text += f"   💰 `${s['price']:,.4f}` | {s['change_24h']:+.1f}%\n"
        text += f"   🎯 `[{pump_bar(p)}] {p:.1f}%` — {s['pump_verdict']}\n"
        text += f"   🟢 ورود: `${s['buy_zone']:,.4f}` 🔴 هدف: `${s['target1']:,.4f}`\n"
        text += f"   🔗 [CoinGecko](https://www.coingecko.com/en/coins/{s.get('id','')})\n\n"
    text += "─"*28 + "\n⚠️ _مشاوره مالی نیست._"
    return text

def format_full_analysis(s):
    if 'error' in s:
        return f"❌ خطا: {s['error']}"
    p = s['pump_probability']
    text = f"📊 *تحلیل کامل {s['symbol']}* (#{s.get('market_cap_rank','?')})\n" + "─"*28 + "\n\n"
    text += f"💰 *قیمت:* `${s['price']:,.6f}`\n"
    text += f"📈 `{s['change_1h']:+.2f}%` (۱h) | `{s['change_24h']:+.2f}%` (۲۴h) | `{s['change_7d']:+.2f}%` (۷d)\n\n"
    text += f"🎯 *نتیجه نهایی:*\n`[{pump_bar(p)}] {p:.1f}%`\n"
    text += f"حکم: *{s['pump_verdict']}*\n"
    text += f"• تکنیکال: `{s['pump_technical']:.1f}/60` | فاندامنتال: `{s['pump_fundamental']:.1f}/40`\n\n"
    rsi = s['rsi']
    rsi_lbl = '🟢 اشباع فروش' if rsi < 30 else '🔴 اشباع خرید' if rsi > 70 else '⚪ خنثی'
    text += "📐 *تکنیکال:*\n"
    text += f"• RSI: `{rsi:.1f}` {rsi_lbl}\n"
    text += f"• MACD: {macd_text(s['macd_signal'])}\n"
    text += f"• Bollinger: {bb_text(s['bb_signal'])} (`{s['bb_position']:.0f}%`)\n"
    text += f"• Ichimoku: {ichi_text(s['ichimoku_signal'])} | TK: `{'صعودی✅' if s['ichimoku_tk']=='bullish' else 'نزولی❌' if s['ichimoku_tk']=='bearish' else 'خنثی'}`\n"
    text += f"• EMA: {s['ema_signal']} | حجم: `x{s['volume_ratio']:.1f}` {'🔥' if s['volume_unusual'] else ''}\n\n"
    text += "🏦 *فاندامنتال:*\n"
    text += f"• کل: `{s['fundamental_score']}/100` | نقدینگی: `{s['fund_liquidity']}/25`\n"
    text += f"• کامیونیتی: `{s['fund_community']}/25` | توسعه: `{s['fund_dev']}/25`\n\n"
    text += "🎯 *نقاط معاملاتی:*\n"
    text += f"🟢 ورود: `${s['buy_zone']:,.6f}`\n"
    text += f"🔴 هدف ۱: `${s['target1']:,.6f}` (+10%) | هدف ۲: `${s['target2']:,.6f}` (+22%)\n"
    text += f"⛔ استاپ: `${s['stop_loss']:,.6f}`\n\n"
    text += f"🔗 [CoinGecko](https://www.coingecko.com/en/coins/{s.get('id','')}) | [TradingView](https://www.tradingview.com/chart/?symbol={s['symbol']}USDT)\n\n"
    text += "─"*28 + "\n⚠️ _مشاوره مالی نیست._"
    return text

def format_dex_list(tokens, chain_name):
    if not tokens:
        return f"❌ توکن جدید قابل توجهی روی {chain_name} یافت نشد.\n\nدوباره امتحان کن یا شبکه دیگری انتخاب کن."
    text = f"🧪 *شت‌کوین‌های جدید — {chain_name}*\n" + "─"*28 + "\n\n"
    for i, token in enumerate(tokens, 1):
        base = token.get('baseToken') or {}
        pump_info = token.get('pump_info', {})
        score = pump_info.get('score', 0)
        em = "🚀" if score >= 75 else "📈" if score >= 55 else "🔶"
        name = base.get('name', 'Unknown')[:20]
        symbol = base.get('symbol', '?')
        address = base.get('address', '')
        chain = token.get('chainId', '')
        price = token.get('priceUsd', '0')
        ch_1h = float((token.get('priceChange') or {}).get('h1', 0) or 0)
        ch_24h = float((token.get('priceChange') or {}).get('h24', 0) or 0)
        vol = float((token.get('volume') or {}).get('h24', 0) or 0)
        liq = float((token.get('liquidity') or {}).get('usd', 0) or 0)
        age = pump_info.get('age_hours', 0)
        buy_link = dex.get_buy_link(chain, address)
        explorer_link = dex.get_explorer_link(chain, address)
        dex_url = token.get('url', f"https://dexscreener.com/{chain}/{address}")

        text += f"{em} *{i}. {symbol}* — {name}\n"
        text += f"   💰 `${float(price):.8f}` | {ch_1h:+.1f}% (1h) | {ch_24h:+.1f}% (24h)\n"
        text += f"   🎯 امتیاز پامپ: `[{pump_bar(score)}] {score}/100`\n"
        text += f"   📦 حجم: `${vol:,.0f}` | 💧 نقدینگی: `${liq:,.0f}`\n"
        text += f"   ⏱ سن: `{age:.1f} ساعت`\n"
        text += f"   🛒 فشار خرید: `{pump_info.get('buy_pressure_pct',0):.0f}%`\n"

        if pump_info.get('risks'):
            text += f"   ⚠️ ریسک: `{' | '.join(pump_info['risks'])}`\n"

        # آدرس قرارداد
        short_addr = f"{address[:6]}...{address[-4:]}" if len(address) > 10 else address
        text += f"   📋 CA: `{address}`\n"

        # لینک‌ها
        links = f"[DexScreener]({dex_url})"
        if explorer_link: links += f" | [Explorer]({explorer_link})"
        if buy_link: links += f" | [🛒 خرید]({buy_link})"
        text += f"   🔗 {links}\n\n"

    text += "─"*28 + "\n"
    text += "⚠️ _شت‌کوین‌ها ریسک بسیار بالا دارند.\nمشاوره مالی نیست._"
    return text

def format_dex_token(pair, pump_info):
    base = pair.get('baseToken') or {}
    chain = pair.get('chainId', '')
    address = base.get('address', '')
    name = base.get('name', 'Unknown')
    symbol = base.get('symbol', '?')
    price = float(pair.get('priceUsd', 0) or 0)
    score = pump_info.get('score', 0)
    ch_1h = float((pair.get('priceChange') or {}).get('h1', 0) or 0)
    ch_6h = float((pair.get('priceChange') or {}).get('h6', 0) or 0)
    ch_24h = float((pair.get('priceChange') or {}).get('h24', 0) or 0)
    vol = float((pair.get('volume') or {}).get('h24', 0) or 0)
    liq = float((pair.get('liquidity') or {}).get('usd', 0) or 0)
    mcap = float(pair.get('marketCap', 0) or 0)
    buy_link = dex.get_buy_link(chain, address)
    explorer_link = dex.get_explorer_link(chain, address)
    dex_url = pair.get('url', f"https://dexscreener.com/{chain}/{address}")

    text = f"🧪 *تحلیل توکن: {symbol}*\n" + "─"*28 + "\n\n"
    text += f"📌 نام: *{name}*\n"
    text += f"🔗 شبکه: `{chain.upper()}`\n"
    text += f"💰 قیمت: `${price:.10f}`\n"
    text += f"📈 تغییرات: `{ch_1h:+.1f}%` (1h) | `{ch_6h:+.1f}%` (6h) | `{ch_24h:+.1f}%` (24h)\n\n"

    text += f"🎯 *امتیاز پامپ: `[{pump_bar(score)}] {score}/100`*\n"
    text += f"حکم: *{pump_info.get('verdict', '')}*\n\n"

    text += "📊 *آمار بازار:*\n"
    text += f"• حجم ۲۴h: `${vol:,.0f}`\n"
    text += f"• نقدینگی: `${liq:,.0f}`\n"
    if mcap: text += f"• مارکت‌کپ: `${mcap:,.0f}`\n"
    text += f"• سن: `{pump_info.get('age_hours', 0):.1f} ساعت`\n"
    text += f"• خرید/فروش (۱h): `{pump_info.get('buys_1h',0)} / {pump_info.get('sells_1h',0)}`\n"
    text += f"• فشار خرید: `{pump_info.get('buy_pressure_pct',0):.0f}%`\n\n"

    if pump_info.get('risks'):
        text += f"⚠️ *ریسک‌ها:* {' | '.join(pump_info['risks'])}\n\n"

    text += f"📋 *آدرس قرارداد:*\n`{address}`\n\n"
    text += "🔗 *لینک‌ها:*\n"
    text += f"[DexScreener]({dex_url})"
    if explorer_link: text += f" | [Explorer]({explorer_link})"
    if buy_link: text += f"\n[🛒 خرید مستقیم]({buy_link})"
    text += "\n\n─"*28 + "\n⚠️ _ریسک بسیار بالا. مشاوره مالی نیست._"
    return text

def format_news(news):
    if not news: return "❌ اخباری یافت نشد."
    text = "📰 *اخبار بازار*\n" + "─"*28 + "\n\n"
    for item in news[:8]:
        em = "🟢" if item['sentiment']=='positive' else "🔴" if item['sentiment']=='negative' else "⚪"
        text += f"{em} *{item['title'][:55]}...*\n   {item['source']} | 🔗 [بیشتر]({item['url']})\n\n"
    return text

def format_market_status(s):
    fg = s['fear_greed']
    em = "😱" if fg < 25 else "😨" if fg < 45 else "😐" if fg < 55 else "😊" if fg < 75 else "🤑"
    text = "🌐 *وضعیت کلی بازار*\n" + "─"*28 + "\n\n"
    text += f"💰 مارکت کپ: `${s['total_market_cap']:,.0f}`\n"
    text += f"📊 سهم BTC: `{s['btc_dominance']:.1f}%`\n"
    text += f"💧 حجم ۲۴h: `${s['total_volume']:,.0f}`\n"
    text += f"{em} ترس/طمع: `{fg}/100`\n"
    text += f"📈 روند: {s['overall_trend']}\n"
    return text

# ── Alert Job ──────────────────────────────────────────────────────────────────

async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    if 'alerts' not in context.bot_data:
        return
    if 'alerted' not in context.bot_data:
        context.bot_data['alerted'] = {}
    import time
    now = time.time()
    for chat_id, alert_list in list(context.bot_data['alerts'].items()):
        for alert in alert_list:
            key = f"{chat_id}_{alert['symbol']}"
            last = context.bot_data['alerted'].get(key, 0)
            if now - last < 3600:  # هر ۱ ساعت یک بار
                continue
            result = await analyzer.analyze_single(alert['symbol'])
            if 'error' not in result and result['pump_probability'] >= alert['threshold']:
                context.bot_data['alerted'][key] = now
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🚨 *هشدار پامپ!*\n\n"
                         f"*{alert['symbol']}* — احتمال `{result['pump_probability']:.1f}%`\n"
                         f"حکم: {result['pump_verdict']}\n\n"
                         f"💰 `${result['price']:,.4f}`\n"
                         f"🟢 ورود: `${result['buy_zone']:,.4f}`\n"
                         f"🔴 هدف: `${result['target1']:,.4f}`\n\n"
                         f"⚠️ _مشاوره مالی نیست._",
                    parse_mode='Markdown')

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ BOT_TOKEN را تنظیم کنید!")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("scan", scan_command))
    app.add_handler(CommandHandler("top", top_command))
    app.add_handler(CommandHandler("coin", coin_command))
    app.add_handler(CommandHandler("dex", dex_command))
    app.add_handler(CommandHandler("dextoken", dextoken_command))
    app.add_handler(CommandHandler("alert", alert_command))
    app.add_handler(CommandHandler("alerts", alerts_command))
    app.add_handler(CommandHandler("cancelalerts", cancel_alerts_command))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.job_queue.run_repeating(check_alerts, interval=SCAN_INTERVAL_MINUTES * 60, first=60)
    print("✅ ربات v3 در حال اجرا...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
