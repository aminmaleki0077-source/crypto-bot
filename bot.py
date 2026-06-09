#!/usr/bin/env python3
"""
🚀 Crypto Pump Signal Bot
Advanced Telegram bot for cryptocurrency pump detection
"""

import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from analyzer import CryptoAnalyzer
from config import BOT_TOKEN, SCAN_INTERVAL_MINUTES

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

analyzer = CryptoAnalyzer()

# ─── Command Handlers ───────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔍 اسکن بازار الان", callback_data="scan_now")],
        [InlineKeyboardButton("🔥 برترین سیگنال‌ها", callback_data="top_signals")],
        [InlineKeyboardButton("📊 تحلیل یک ارز خاص", callback_data="analyze_coin")],
        [InlineKeyboardButton("⚙️ تنظیم هشدار خودکار", callback_data="set_alert")],
        [InlineKeyboardButton("📰 اخبار بازار", callback_data="news")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🤖 *ربات سیگنال کریپتو*\n\n"
        "این ربات با استفاده از:\n"
        "• تحلیل تکنیکال پیشرفته (RSI, MACD, Bollinger, EMA)\n"
        "• آنالیز حجم معاملات\n"
        "• اخبار و سنتیمنت بازار\n"
        "• داده‌های آنچین\n\n"
        "ارزهایی با احتمال پامپ بالا را شناسایی می‌کند.\n\n"
        "⚠️ *این ربات صرفاً جنبه آموزشی دارد و مشاوره مالی نیست.*",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *راهنمای دستورات:*\n\n"
        "/start - شروع و منوی اصلی\n"
        "/scan - اسکن کامل بازار\n"
        "/top - برترین سیگنال‌های پامپ\n"
        "/coin <symbol> - تحلیل ارز خاص (مثال: /coin BTC)\n"
        "/alert <symbol> <percent> - هشدار پامپ (مثال: /alert BTC 70)\n"
        "/news - آخرین اخبار بازار\n"
        "/status - وضعیت کلی بازار",
        parse_mode='Markdown'
    )


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال اسکن بازار... لطفاً صبر کنید")
    await run_scan(update.message.chat_id, context, msg)


async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال جمع‌آوری برترین سیگنال‌ها...")
    signals = await analyzer.get_top_signals(limit=10)
    await msg.edit_text(format_signals(signals), parse_mode='Markdown')


async def coin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ لطفاً سیمبل ارز را وارد کنید.\nمثال: /coin BTC")
        return
    symbol = context.args[0].upper()
    msg = await update.message.reply_text(f"⏳ در حال تحلیل {symbol}...")
    result = await analyzer.analyze_single(symbol)
    await msg.edit_text(format_single_analysis(result), parse_mode='Markdown')


async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❗ فرمت: /alert <symbol> <min_percent>\nمثال: /alert ETH 65")
        return
    symbol = context.args[0].upper()
    try:
        threshold = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❗ درصد باید یک عدد باشد.")
        return

    chat_id = update.message.chat_id
    if 'alerts' not in context.bot_data:
        context.bot_data['alerts'] = {}
    context.bot_data['alerts'][chat_id] = context.bot_data['alerts'].get(chat_id, [])
    context.bot_data['alerts'][chat_id].append({'symbol': symbol, 'threshold': threshold})

    await update.message.reply_text(
        f"✅ هشدار تنظیم شد!\n"
        f"ارز: *{symbol}*\n"
        f"حداقل احتمال پامپ: *{threshold}%*\n\n"
        f"هر زمان احتمال پامپ از این مقدار بیشتر شود، اطلاع‌رسانی می‌شود.",
        parse_mode='Markdown'
    )


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال دریافت اخبار...")
    news = await analyzer.get_market_news()
    await msg.edit_text(format_news(news), parse_mode='Markdown')


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ در حال بررسی وضعیت بازار...")
    status = await analyzer.get_market_status()
    await msg.edit_text(format_market_status(status), parse_mode='Markdown')


# ─── Callback Handlers ───────────────────────────────────────────────────────

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "scan_now":
        await query.edit_message_text("⏳ در حال اسکن بازار...")
        signals = await analyzer.get_top_signals(limit=15)
        await query.edit_message_text(format_signals(signals), parse_mode='Markdown')

    elif query.data == "top_signals":
        await query.edit_message_text("⏳ در حال جمع‌آوری برترین سیگنال‌ها...")
        signals = await analyzer.get_top_signals(limit=10)
        await query.edit_message_text(format_signals(signals), parse_mode='Markdown')

    elif query.data == "analyze_coin":
        await query.edit_message_text(
            "📊 برای تحلیل یک ارز خاص، دستور زیر را وارد کنید:\n\n"
            "`/coin SYMBOL`\n\nمثال: `/coin SOL`",
            parse_mode='Markdown'
        )

    elif query.data == "set_alert":
        await query.edit_message_text(
            "🔔 برای تنظیم هشدار:\n\n"
            "`/alert SYMBOL PERCENT`\n\nمثال: `/alert BTC 75`",
            parse_mode='Markdown'
        )

    elif query.data == "news":
        await query.edit_message_text("⏳ در حال دریافت اخبار بازار...")
        news = await analyzer.get_market_news()
        await query.edit_message_text(format_news(news), parse_mode='Markdown')


# ─── Formatters ──────────────────────────────────────────────────────────────

def format_signals(signals: list) -> str:
    if not signals:
        return "❌ هیچ سیگنال قابل توجهی یافت نشد."

    text = "🔥 *برترین سیگنال‌های پامپ*\n"
    text += "─" * 30 + "\n\n"

    for i, s in enumerate(signals[:10], 1):
        pump_emoji = "🚀" if s['pump_probability'] >= 75 else "📈" if s['pump_probability'] >= 60 else "🔶"
        trend_emoji = "⬆️" if s['trend'] == 'bullish' else "⬇️" if s['trend'] == 'bearish' else "➡️"

        text += f"{pump_emoji} *{i}. {s['symbol']}* ({s['name']})\n"
        text += f"   💰 قیمت: `${s['price']:,.4f}`\n"
        text += f"   🎯 احتمال پامپ: `{s['pump_probability']:.1f}%`\n"
        text += f"   📊 تغییر ۲۴ساعته: `{s['change_24h']:+.2f}%`\n"
        text += f"   📦 حجم: `${s['volume_24h']:,.0f}`\n"
        text += f"   {trend_emoji} روند: `{s['trend']}`\n"
        text += f"   🟢 نقطه خرید: `${s['buy_zone']:,.4f}`\n"
        text += f"   🔴 نقطه فروش: `${s['sell_zone']:,.4f}`\n"
        text += f"   🔗 [CoinGecko](https://www.coingecko.com/en/coins/{s.get('id', s['symbol'].lower())})\n"
        text += "\n"

    text += "─" * 30 + "\n"
    text += "⚠️ _این سیگنال‌ها مشاوره مالی نیستند._"
    return text


def format_single_analysis(result: dict) -> str:
    if 'error' in result:
        return f"❌ خطا: {result['error']}"

    s = result
    pump_bar = "█" * int(s['pump_probability'] / 10) + "░" * (10 - int(s['pump_probability'] / 10))

    text = f"📊 *تحلیل کامل {s['symbol']}*\n"
    text += "─" * 30 + "\n\n"
    text += f"💰 *قیمت فعلی:* `${s['price']:,.6f}`\n"
    text += f"📈 *تغییر ۲۴ساعته:* `{s['change_24h']:+.2f}%`\n"
    text += f"📦 *حجم معاملات:* `${s['volume_24h']:,.0f}`\n"
    text += f"🏦 *مارکت کپ:* `${s['market_cap']:,.0f}`\n\n"

    text += f"🎯 *احتمال پامپ:*\n`[{pump_bar}] {s['pump_probability']:.1f}%`\n\n"

    text += "📐 *اندیکاتورهای تکنیکال:*\n"
    text += f"   • RSI: `{s['rsi']:.1f}` {'🟢 اشباع فروش' if s['rsi'] < 30 else '🔴 اشباع خرید' if s['rsi'] > 70 else '🟡 خنثی'}\n"
    text += f"   • MACD: `{'صعودی ✅' if s['macd_signal'] == 'bullish' else 'نزولی ❌'}`\n"
    text += f"   • Bollinger: `{s['bb_signal']}`\n"
    text += f"   • EMA ۲۰/۵۰: `{s['ema_signal']}`\n"
    text += f"   • حجم غیرمعمول: `{'بله 🔥' if s['volume_unusual'] else 'خیر'}`\n\n"

    text += "🎯 *نقاط معاملاتی:*\n"
    text += f"   🟢 ورود (خرید): `${s['buy_zone']:,.6f}`\n"
    text += f"   🔴 هدف ۱ (فروش): `${s['target1']:,.6f}` (+{s['target1_pct']:.1f}%)\n"
    text += f"   🔴 هدف ۲: `${s['target2']:,.6f}` (+{s['target2_pct']:.1f}%)\n"
    text += f"   ⛔ استاپ لاس: `${s['stop_loss']:,.6f}` ({s['stop_loss_pct']:.1f}%)\n\n"

    text += f"🔗 *لینک‌ها:*\n"
    text += f"   [CoinGecko](https://www.coingecko.com/en/coins/{s.get('id', '')}) | "
    text += f"[TradingView](https://www.tradingview.com/chart/?symbol={s['symbol']}USDT)\n\n"

    text += "─" * 30 + "\n"
    text += "⚠️ _این تحلیل مشاوره مالی نیست._"
    return text


def format_news(news: list) -> str:
    if not news:
        return "❌ اخباری یافت نشد."
    text = "📰 *آخرین اخبار بازار کریپتو*\n"
    text += "─" * 30 + "\n\n"
    for item in news[:8]:
        sentiment_emoji = "🟢" if item['sentiment'] == 'positive' else "🔴" if item['sentiment'] == 'negative' else "⚪"
        text += f"{sentiment_emoji} *{item['title'][:60]}...*\n"
        text += f"   📌 {item['source']} | {item['time']}\n"
        text += f"   🔗 [بیشتر بخوانید]({item['url']})\n\n"
    return text


def format_market_status(status: dict) -> str:
    fear_emoji = "😱" if status['fear_greed'] < 25 else "😨" if status['fear_greed'] < 45 else "😐" if status['fear_greed'] < 55 else "😊" if status['fear_greed'] < 75 else "🤑"
    text = "🌐 *وضعیت کلی بازار*\n"
    text += "─" * 30 + "\n\n"
    text += f"💰 *مارکت کپ کل:* `${status['total_market_cap']:,.0f}`\n"
    text += f"📊 *سهم بیتکوین:* `{status['btc_dominance']:.1f}%`\n"
    text += f"💧 *حجم ۲۴ساعته:* `${status['total_volume']:,.0f}`\n"
    text += f"😱 *شاخص ترس/طمع:* {fear_emoji} `{status['fear_greed']}/100`\n"
    text += f"📈 *روند کلی:* `{status['overall_trend']}`\n"
    text += f"🟢 *ارزهای صعودی:* `{status['gainers']}%`\n"
    text += f"🔴 *ارزهای نزولی:* `{status['losers']}%`\n"
    return text


# ─── Auto Alert Job ───────────────────────────────────────────────────────────

async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    if 'alerts' not in context.bot_data:
        return
    for chat_id, alert_list in context.bot_data['alerts'].items():
        for alert in alert_list:
            result = await analyzer.analyze_single(alert['symbol'])
            if 'error' not in result and result['pump_probability'] >= alert['threshold']:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🚨 *هشدار پامپ!*\n\n"
                         f"ارز *{alert['symbol']}* با احتمال *{result['pump_probability']:.1f}%* در آستانه پامپ است!\n\n"
                         f"💰 قیمت: `${result['price']:,.4f}`\n"
                         f"🟢 نقطه ورود: `${result['buy_zone']:,.4f}`\n"
                         f"🔴 هدف: `${result['target1']:,.4f}`",
                    parse_mode='Markdown'
                )


async def run_scan(chat_id, context, msg=None):
    signals = await analyzer.get_top_signals(limit=15)
    text = format_signals(signals)
    if msg:
        await msg.edit_text(text, parse_mode='Markdown')
    else:
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode='Markdown')


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ لطفاً BOT_TOKEN را در فایل config.py یا .env تنظیم کنید!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("scan", scan_command))
    app.add_handler(CommandHandler("top", top_command))
    app.add_handler(CommandHandler("coin", coin_command))
    app.add_handler(CommandHandler("alert", alert_command))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CallbackQueryHandler(button_callback))

    # Auto scan every N minutes
    job_queue = app.job_queue
    job_queue.run_repeating(check_alerts, interval=SCAN_INTERVAL_MINUTES * 60, first=60)

    print("✅ ربات در حال اجرا است...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
