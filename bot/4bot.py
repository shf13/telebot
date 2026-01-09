import os
import re
import datetime as dt
from zoneinfo import ZoneInfo
from html import escape

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from storage import Storage
from formatter import load_latest


TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

MOSCOW_TZ = ZoneInfo("Europe/Moscow")
PRAYER_ORDER = ["Фаджр", "Шурук", "Зухр", "Аср", "Магриб", "Иша"]

# Preset times shown as buttons (edit as you like)
TIME_PRESETS = ["06:00", "07:00", "08:00", "09:00", "10:00", "12:00", "18:00", "21:00"]


def _job_name(user_id: int) -> str:
    return f"daily_{user_id}"


def _parse_hhmm(s: str) -> tuple[int, int]:
    m = TIME_RE.match(s.strip())
    if not m:
        # Reminder about MSK included
        raise ValueError("Invalid time format. Use HH:MM (24h, MSK), e.g. /SetTime 08:15")
    return int(m.group(1)), int(m.group(2))


def _main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Now", callback_data="NOW"),
                InlineKeyboardButton("My settings", callback_data="TIME"),
            ],
            [InlineKeyboardButton("Set time", callback_data="SETTIME")],
            [InlineKeyboardButton("Stop", callback_data="STOP")],
        ]
    )


def _preset_time_kb() -> InlineKeyboardMarkup:
    rows = []
    row = []
    for t in TIME_PRESETS:
        row.append(InlineKeyboardButton(t, callback_data=f"PRESET:{t}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton("Back", callback_data="BACK")])
    return InlineKeyboardMarkup(rows)


def _format_prayer_message(payload: dict) -> str:
    if not payload or "prayers" not in payload:
        return "<b>Today’s data isn’t available yet, please try again later.</b>"

    prayers: dict = payload.get("prayers", {})
    date_str = payload.get("date", "")
    source_url = payload.get("source_url", "")

    pretty_date = date_str
    try:
        d = dt.date.fromisoformat(date_str)
        pretty_date = d.strftime("%d.%m.%Y")
    except Exception:
        pass

    lines = []
    lines.append("<b>Prayer times (Moscow / MSK)</b>")
    if pretty_date:
        lines.append(f"<b>Date:</b> {escape(pretty_date)}")
    lines.append("")

    used = set()
    for name in PRAYER_ORDER:
        if name in prayers:
            lines.append(f"• <b>{escape(name)}:</b> {escape(prayers[name])}")
            used.add(name)

    for name, val in prayers.items():
        if name not in used:
            lines.append(f"• <b>{escape(name)}:</b> {escape(val)}")

    if source_url:
        lines.append("")
        lines.append(f"<a href='{escape(source_url)}'>Source</a>")

    return "\n".join(lines)


def _load_today_or_friendly(data_file: str) -> tuple[dict | None, str | None]:
    """
    Returns (payload, None) if today's data exists.
    Returns (None, friendly_message) if file missing/empty/stale/wrong date.
    Date comparison is done in Moscow time.
    """
    try:
        payload = load_latest(data_file)
    except Exception:
        return None, "Today’s data isn’t available yet, please try again later."

    if not payload or not isinstance(payload, dict):
        return None, "Today’s data isn’t available yet, please try again later."

    prayers = payload.get("prayers")
    if not prayers or not isinstance(prayers, dict) or len(prayers) == 0:
        return None, "Today’s data isn’t available yet, please try again later."

    today_msk = dt.datetime.now(MOSCOW_TZ).date().isoformat()
    if payload.get("date") != today_msk:
        return None, "Today’s data isn’t available yet, please try again later."

    return payload, None


def _schedule_user(app: Application, storage: Storage, user_id: int) -> str:
    prefs = storage.get_user(user_id)
    if not prefs or not prefs.enabled:
        return "Daily messages are disabled. Use /SetTime HH:MM (MSK) to enable again."

    if not prefs.time_hhmm:
        return "No delivery time set. Use /SetTime HH:MM (MSK)."

    for job in app.job_queue.get_jobs_by_name(_job_name(user_id)):
        job.schedule_removal()

    hour, minute = _parse_hhmm(prefs.time_hhmm)
    t = dt.time(hour=hour, minute=minute, tzinfo=MOSCOW_TZ)

    app.job_queue.run_daily(
        callback=send_daily,
        time=t,
        name=_job_name(user_id),
        data={"user_id": user_id},
    )
    return f"Ok, I will send daily at {prefs.time_hhmm} MSK."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Keep DB compatible: store timezone, but fixed to Moscow (never shown/asked).
    storage.upsert_user(user_id=user_id, chat_id=chat_id)

    await update.message.reply_text(
        "Prayer times for Moscow (MSK). Choose an option:",
        reply_markup=_main_menu_kb(),
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "How to use this bot:\n\n"
        "• /Now — show today's prayer times\n"
        "• /SetTime HH:MM — set daily delivery time (24h, Moscow time / MSK)\n"
        "   Example: /SetTime 08:15\n"
        "• /Time — show your settings (all times in MSK)\n"
        "• /Stop — disable daily messages\n\n"
        "Tip: You can also use the buttons instead of typing commands."
    )
    await update.message.reply_text(text, reply_markup=_main_menu_kb())


async def settime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text(
            "Usage: /SetTime HH:MM (24h, MSK), e.g. /SetTime 08:15",
            reply_markup=_preset_time_kb(),
        )
        return

    time_hhmm = context.args[0].strip()
    try:
        _parse_hhmm(time_hhmm)
    except ValueError as e:
        await update.message.reply_text(str(e), reply_markup=_preset_time_kb())
        return

    storage.set_time(user_id=user_id, chat_id=chat_id, time_hhmm=time_hhmm)

    # Make sure enabled is effectively true (your Storage sets enabled=1 on set_time already)
    msg = _schedule_user(context.application, storage, user_id)
    await update.message.reply_text(msg, reply_markup=_main_menu_kb())


async def time_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]
    user_id = update.effective_user.id

    prefs = storage.get_user(user_id)
    if not prefs:
        await update.message.reply_text("No settings found. Send /start", reply_markup=_main_menu_kb())
        return

    await update.message.reply_text(
        f"Enabled: {prefs.enabled}\n"
        f"Daily time (MSK): {prefs.time_hhmm or '(not set)'}\n"
        f"(All times are Moscow time / MSK)",
        reply_markup=_main_menu_kb(),
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]
    user_id = update.effective_user.id

    storage.set_enabled(user_id, False)
    for job in context.application.job_queue.get_jobs_by_name(_job_name(user_id)):
        job.schedule_removal()

    await update.message.reply_text(
        "Daily messages disabled. Use /SetTime HH:MM (MSK) to enable again.",
        reply_markup=_main_menu_kb(),
    )


async def now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data_file: str = context.application.bot_data["data_file"]

    payload, friendly = _load_today_or_friendly(data_file)
    if friendly:
        await update.message.reply_text(friendly, reply_markup=_main_menu_kb())
        return

    msg = _format_prayer_message(payload)
    await update.message.reply_text(
        msg,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=_main_menu_kb(),
    )


async def send_daily(context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]
    data_file: str = context.application.bot_data["data_file"]

    user_id = context.job.data["user_id"]
    prefs = storage.get_user(user_id)
    if not prefs or not prefs.enabled:
        return

    payload, friendly = _load_today_or_friendly(data_file)
    if friendly:
        await context.bot.send_message(chat_id=prefs.chat_id, text=friendly)
        return

    msg = _format_prayer_message(payload)
    await context.bot.send_message(
        chat_id=prefs.chat_id,
        text=msg,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    storage: Storage = context.application.bot_data["storage"]
    data_file: str = context.application.bot_data["data_file"]

    user_id = query.from_user.id
    chat_id = query.message.chat_id

    data = query.data

    if data == "BACK":
        await query.edit_message_text("Choose an option:", reply_markup=_main_menu_kb())
        return

    if data == "SETTIME":
        await query.edit_message_text(
            "Pick a time (MSK) or type: /SetTime HH:MM\nExample: /SetTime 08:15",
            reply_markup=_preset_time_kb(),
        )
        return

    if data == "TIME":
        prefs = storage.get_user(user_id)
        txt = (
            f"Enabled: {prefs.enabled if prefs else False}\n"
            f"Daily time (MSK): {(prefs.time_hhmm if prefs and prefs.time_hhmm else '(not set)')}\n"
            f"(All times are Moscow time / MSK)"
        )
        await query.edit_message_text(txt, reply_markup=_main_menu_kb())
        return

    if data == "STOP":
        storage.set_enabled(user_id, False)
        for job in context.application.job_queue.get_jobs_by_name(_job_name(user_id)):
            job.schedule_removal()
        await query.edit_message_text(
            "Daily messages disabled. Use /SetTime HH:MM (MSK) to enable again.",
            reply_markup=_main_menu_kb(),
        )
        return

    if data == "NOW":
        payload, friendly = _load_today_or_friendly(data_file)
        if friendly:
            await query.edit_message_text(friendly, reply_markup=_main_menu_kb())
            return
        msg = _format_prayer_message(payload)
        await query.edit_message_text(
            msg,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=_main_menu_kb(),
        )
        return

    if data.startswith("PRESET:"):
        time_hhmm = data.split(":", 1)[1].strip()
        try:
            _parse_hhmm(time_hhmm)
        except ValueError:
            await query.edit_message_text(
                "Invalid preset time. Please try /SetTime HH:MM (MSK).",
                reply_markup=_preset_time_kb(),
            )
            return

        # Ensure user exists; store fixed Moscow tz for DB compatibility
        storage.upsert_user(user_id=user_id, chat_id=chat_id)
        storage.set_time(user_id=user_id, chat_id=chat_id, time_hhmm=time_hhmm)

        msg = _schedule_user(context.application, storage, user_id)
        await query.edit_message_text(msg, reply_markup=_main_menu_kb())
        return


def main():
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set.")

    data_file = os.getenv("DATA_FILE", os.path.abspath("data/latest.json"))
    db_file = os.getenv("DB_FILE", os.path.abspath("data/bot.sqlite3"))

    storage = Storage(db_file)

    app = Application.builder().token(token).build()
    app.bot_data["storage"] = storage
    app.bot_data["data_file"] = data_file

    # Commands (accept both cases)
    app.add_handler(CommandHandler(["start"], start))
    app.add_handler(CommandHandler(["help", "Help"], help_cmd))
    app.add_handler(CommandHandler(["settime", "SetTime"], settime))
    app.add_handler(CommandHandler(["time", "Time"], time_cmd))
    app.add_handler(CommandHandler(["now", "Now"], now))
    app.add_handler(CommandHandler(["stop", "Stop"], stop))

    # Inline buttons
    app.add_handler(CallbackQueryHandler(on_button))

    # schedule enabled users on startup
    for prefs in storage.list_enabled_users():
        if prefs.time_hhmm:
            try:
                _schedule_user(app, storage, prefs.user_id)
            except Exception:
                pass

    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()