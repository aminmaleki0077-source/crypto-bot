#!/usr/bin/env python3
"""Crypto Pump Signal Bot v2 - با ایچیموکو، فاندامنتال، دکمه لغو"""

import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from analyzer import CryptoAnalyzer
from config import BOT_TOKEN, SCAN_INTERVAL_MINUTES

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
analyzer = CryptoAnalyzer()

CANCEL_BTN = [[InlineKeyboardButton("❌ لغو", callback_data="cancel")]]
BACK_BTN = [[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="main_menu")]]

# ── Keyboards ──────────────────────────────────────────────────────────────────

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 اسکن بازار", callback_data="scan_now"),
         InlineKeyboardButton("🔥 برترین سیگنال‌ها", callback_data="top_signals")],
        [InlineKeyboardButton("📊 تحلیل ارز خاص", callback_data="analyze_coin"),
         InlineKeyboardButton("📰 اخبار بازار", callback_data="news")],
        [InlineKeyboardButton("🌐 وضعیت بازار", callback_data="status"),
         InlineKeyboardButton("⚙️ هشدار خودکار", callback_data="set_alert")],
        [InlineKeyboardButton("❓ راهنما", callback_data="help")],
    ])

def cancel_keyboard():
    return InlineKeyboardMarkup(CANCEL_BTN)

def back_keyboard():
    return InlineKeyboardMarkup(BACK_BTN)

# ── Commands ───────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *ربات سیگنال کریپتو v2*\n\n"
        "تحلیل با:\n"
        "• RSI، MACD، Bollinger Bands\n"
        "• ایچیموکو (Ichimoku Cloud)\n"
        "• EMA 20/50\n"
        "• تحلیل فاندامنتال (مارکت‌کپ، کامیونیتی، توسعه)\n\n"
        "⚠️ _مشاوره مالی نیست._",
        parse_mode='Markdown',
        reply_markup=main_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📋 *دستورات:*\n\n"
        "/start — منوی اصلی\n"
        "/scan — اسکن بازار\n"
        "/top — برترین سیگنال‌ها\n"
        "/coin BTC — تحلیل ارز خاص\n"
        "/alert ETH 70 — هشدار پامپ\n"
        "/alerts — لیست هشدارهای من\n"
        "/cancelalerts — حذف همه هشدارها\n"
        "/news — اخبار\n"
        "/status — وضعیت بازار\n"
        "/cancel — لغو عملیات جاری"
    )
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=back_keyboard())

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("✅ عملیات لغو شد.", reply_markup=main_keyboard())

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
        await update.message.reply_text(
            "❗ سیمبل ارز را وارد کن.\nمثال: `/coin BTC`",
            parse_mode='Markdown', reply_markup=back_keyboard())
        return
    symbol = context.args[0].upper()
    msg = await update.message.reply_text(f"⏳ در حال تحلیل *{symbol}*...", parse_mode='Markdown', reply_markup=cancel_keyboard())
    result = await analyzer.analyze_single(symbol)
    await msg.edit_text(format_full_analysis(result), parse_mode='Markdown', reply_markup=back_keyboard())

async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❗ فرمت: `/alert ETH 65`", parse_mode='Markdown', reply_markup=back_keyboard())
        return
    symbol = context.args[0].upper()
    try:
        threshold = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❗ درصد باید عدد باشد.", reply_markup=back_keyboard())
        return
    chat_id = update.message.chat_id
    if 'alerts' not in context.bot_data:
        context.bot_data['alerts'] = {}
    context.bot_data['alerts'].setdefault(chat_id, [])
    context.bot_data['alerts'][chat_id].append({'symbol': symbol, 'threshold': threshold})
    await update.message.reply_text(
        f"✅ هشدار ثبت شد!\n💎 ارز: *{symbol}*\n🎯 حداقل احتمال: *{threshold}%*",
        parse_mode='Markdown', reply_markup=back_keyboard())

async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    alerts = context.bot_data.get('alerts', {}).get(chat_id, [])
    if not alerts:
        await update.message.reply_text("📭 هیچ هشداری ندارید.\n\nبرای تنظیم: `/alert BTC 70`", parse_mode='Markdown', reply_markup=back_keyboard())
        return
    text = "🔔 *هشدارهای فعال شما:*\n\n"
    for i, a in enumerate(alerts, 1):
        text += f"{i}. *{a['symbol']}* — حداقل {a['threshold']}%\n"
    text += "\nبرای حذف همه: /cancelalerts"
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

# ── Callback ───────────────────────────────────────────────────────────────────

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        context.user_data.clear()
        await query.edit_message_text("✅ عملیات لغو شد.", reply_markup=main_keyboard())

    elif query.data == "main_menu":
        await query.edit_message_text(
            "🤖 *منوی اصلی* — یک گزینه انتخاب کن:",
            parse_mode='Markdown', reply_markup=main_keyboard())

    elif query.data == "scan_now":
        await query.edit_message_text("⏳ در حال اسکن بازار...", reply_markup=cancel_keyboard())
        signals = await analyzer.get_top_signals(limit=10)
        await query.edit_message_text(format_signals(signals), parse_mode='Markdown', reply_markup=back_keyboard())

    elif query.data == "top_signals":
        await query.edit_message_text("⏳ در حال جمع‌آوری سیگنال‌ها...", reply_markup=cancel_keyboard())
        signals = await analyzer.get_top_signals(limit=10)
        await query.edit_message_text(format_signals(signals), parse_mode='Markdown', reply_markup=back_keyboard())

    elif query.data == "analyze_coin":
        await query.edit_message_text(
            "📊 سیمبل ارز را وارد کن:\n\n`/coin BTC`\n`/coin ETH`\n`/coin SOL`",
            parse_mode='Markdown', reply_markup=cancel_keyboard())

    elif query.data == "news":
        await query.edit_message_text("⏳ در حال دریافت اخبار...", reply_markup=cancel_keyboard())
        news = await analyzer.get_market_news()
        await query.edit_message_text(format_news(news), parse_mode='Markdown', reply_markup=back_keyboard())

    elif query.data == "status":
        await query.edit_message_text("⏳ در حال بررسی بازار...", reply_markup=cancel_keyboard())
        status = await analyzer.get_market_status()
        await query.edit_message_text(format_market_status(status), parse_mode='Markdown', reply_markup=back_keyboard())

    elif query.data == "set_alert":
        await query.edit_message_text(
            "🔔 *تنظیم هشدار:*\n\n`/alert SYMBOL PERCENT`\n\nمثال:\n`/alert BTC 75`\n`/alert ETH 60`",
            parse_mode='Markdown', reply_markup=cancel_keyboard())

    elif query.data == "help":
        text = (
            "📋 *دستورات:*\n\n"
            "/scan — اسکن بازار\n"
            "/top — برترین سیگنال‌ها\n"
            "/coin BTC — تحلیل کامل\n"
            "/alert ETH 70 — هشدار\n"
            "/alerts — هشدارهای من\n"
            "/cancelalerts — حذف هشدارها\n"
            "/news — اخبار\n"
            "/status — وضعیت بازار\n"
            "/cancel — لغو عملیات"
        )
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=back_keyboard())

# ── Formatters ─────────────────────────────────────────────────────────────────

def pump_bar(prob):
    filled = int(prob / 10)
    return "█" * filled + "░" * (10 - filled)

def macd_text(sig):
    m = {'bullish_strong':'🟢 صعودی قوی','bullish':'🟢 صعودی',
         'neutral':'⚪ خنثی','bearish':'🔴 نزولی','bearish_strong':'🔴 نزولی قوی'}
    return m.get(sig, sig)

def bb_text(sig):
    m = {'strong_oversold':'🟢 اشباع فروش شدید','oversold':'🟢 اشباع فروش',
         'neutral':'⚪ خنثی','overbought':'🔴 اشباع خرید','strong_overbought':'🔴 اشباع خرید شدید'}
    return m.get(sig, sig)

def ichi_text(sig):
    m = {'above_cloud':'☁️ بالای ابر (صعودی)','below_cloud':'☁️ زیر ابر (نزولی)','inside_cloud':'☁️ داخل ابر (خنثی)','neutral':'⚪ خنثی'}
    return m.get(sig, sig)

def format_signals(signals):
    if not signals:
        return "❌ سیگنال قابل توجهی یافت نشد."
    text = "🔥 *برترین سیگنال‌های پامپ*\n" + "─"*28 + "\n\n"
    for i, s in enumerate(signals[:10], 1):
        p = s['pump_probability']
        em = "🚀" if p >= 75 else "📈" if p >= 60 else "🔶"
        text += f"{em} *{i}. {s['symbol']}* — {s['name']}\n"
        text += f"   💰 `${s['price']:,.4f}` | {s['change_24h']:+.1f}% (۲۴h)\n"
        text += f"   🎯 احتمال پامپ: `[{pump_bar(p)}] {p:.1f}%`\n"
        text += f"   📝 {s['pump_verdict']}\n"
        text += f"   🟢 ورود: `${s['buy_zone']:,.4f}` | 🔴 هدف: `${s['target1']:,.4f}`\n"
        text += f"   🔗 [CoinGecko](https://www.coingecko.com/en/coins/{s.get('id','')})\n\n"
    text += "─"*28 + "\n⚠️ _مشاوره مالی نیست._"
    return text

def format_full_analysis(s):
    if 'error' in s:
        return f"❌ خطا: {s['error']}"
    p = s['pump_probability']
    text = f"📊 *تحلیل کامل {s['symbol']}* (#{s.get('market_cap_rank','?')})\n"
    text += "─"*28 + "\n\n"
    text += f"💰 *قیمت:* `${s['price']:,.6f}`\n"
    text += f"📈 تغییرات: `{s['change_1h']:+.2f}%` (۱h) | `{s['change_24h']:+.2f}%` (۲۴h) | `{s['change_7d']:+.2f}%` (۷d)\n\n"

    text += f"🎯 *نتیجه نهایی:*\n"
    text += f"`[{pump_bar(p)}] {p:.1f}%`\n"
    text += f"حکم: *{s['pump_verdict']}*\n"
    text += f"• تکنیکال: `{s['pump_technical']:.1f}/60`\n"
    text += f"• فاندامنتال: `{s['pump_fundamental']:.1f}/40`\n\n"

    text += "📐 *تحلیل تکنیکال:*\n"
    rsi = s['rsi']
    rsi_lbl = '🟢 اشباع فروش' if rsi < 30 else '🔴 اشباع خرید' if rsi > 70 else '⚪ خنثی'
    text += f"• RSI: `{rsi:.1f}` — {rsi_lbl}\n"
    text += f"• MACD: {macd_text(s['macd_signal'])}\n"
    text += f"• Bollinger: {bb_text(s['bb_signal'])} (`{s['bb_position']:.0f}%`)\n"
    text += f"• Ichimoku: {ichi_text(s['ichimoku_signal'])}\n"
    text += f"  TK Cross: `{'صعودی ✅' if s['ichimoku_tk']=='bullish' else 'نزولی ❌' if s['ichimoku_tk']=='bearish' else 'خنثی'}`\n"
    text += f"• EMA 20/50: {s['ema_signal']}\n"
    text += f"• حجم: `x{s['volume_ratio']:.1f}` — `{'🔥 غیرمعمول' if s['volume_unusual'] else 'عادی'}`\n\n"

    text += "🏦 *تحلیل فاندامنتال:*\n"
    text += f"• امتیاز کل: `{s['fundamental_score']}/100`\n"
    text += f"• نقدینگی: `{s['fund_liquidity']}/25`\n"
    text += f"• رنک بازار: `{s['fund_rank']}/25`\n"
    text += f"• کامیونیتی: `{s['fund_community']}/25`\n"
    text += f"• فعالیت توسعه: `{s['fund_dev']}/25`\n\n"

    text += "🎯 *نقاط معاملاتی:*\n"
    text += f"🟢 ورود: `${s['buy_zone']:,.6f}`\n"
    text += f"🔴 هدف ۱: `${s['target1']:,.6f}` (+10%)\n"
    text += f"🔴 هدف ۲: `${s['target2']:,.6f}` (+22%)\n"
    text += f"🔴 هدف ۳: `${s['target3']:,.6f}` (+40%)\n"
    text += f"⛔ استاپ لاس: `${s['stop_loss']:,.6f}`\n\n"

    text += f"🔗 [CoinGecko](https://www.coingecko.com/en/coins/{s.get('id','')}) | "
    text += f"[TradingView](https://www.tradingview.com/chart/?symbol={s['symbol']}USDT)\n\n"
    text += "─"*28 + "\n⚠️ _مشاوره مالی نیست._"
    return text

def format_news(news):
    if not news:
        return "❌ اخباری یافت نشد."
    text = "📰 *اخبار بازار*\n" + "─"*28 + "\n\n"
    for item in news[:8]:
        em = "🟢" if item['sentiment']=='positive' else "🔴" if item['sentiment']=='negative' else "⚪"
        text += f"{em} *{item['title'][:55]}...*\n"
        text += f"   {item['source']} | 🔗 [بیشتر]({item['url']})\n\n"
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
    text += f"🟢 صعودی: `{s['gainers']:.0f}%` | 🔴 نزولی: `{s['losers']:.0f}%`\n"
    return text

# ── Alert Job ──────────────────────────────────────────────────────────────────

async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    if 'alerts' not in context.bot_data:
        return
    for chat_id, alert_list in list(context.bot_data['alerts'].items()):
        for alert in alert_list:
            result = await analyzer.analyze_single(alert['symbol'])
            if 'error' not in result and result['pump_probability'] >= alert['threshold']:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🚨 *هشدار پامپ!*\n\n"
                         f"*{alert['symbol']}* احتمال `{result['pump_probability']:.1f}%`\n"
                         f"حکم: {result['pump_verdict']}\n\n"
                         f"💰 قیمت: `${result['price']:,.4f}`\n"
                         f"🟢 ورود: `${result['buy_zone']:,.4f}`\n"
                         f"🔴 هدف: `${result['target1']:,.4f}`\n\n"
                         f"⚠️ _مشاوره مالی نیست._",
                    parse_mode='Markdown'
                )

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
    app.add_handler(CommandHandler("alert", alert_command))
    app.add_handler(CommandHandler("alerts", alerts_command))
    app.add_handler(CommandHandler("cancelalerts", cancel_alerts_command))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.job_queue.run_repeating(check_alerts, interval=SCAN_INTERVAL_MINUTES * 60, first=60)
    print("✅ ربات v2 در حال اجرا...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
