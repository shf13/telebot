import os
import re
import datetime as dt
from zoneinfo import ZoneInfo
from html import escape

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from storage import Storage
from formatter import load_latest  # we won't use format_message to fully control output


TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

MOSCOW_TZ = ZoneInfo("Europe/Moscow")
PRAYER_ORDER = ["Фаджр", "Шурук", "Зухр", "Аср", "Магриб", "Иша"]


def _job_name(user_id: int) -> str:
    return f"daily_{user_id}"


def _parse_hhmm(s: str) -> tuple[int, int]:
    m = TIME_RE.match(s.strip())
    if not m:
        raise ValueError("Invalid time format. Use HH:MM (24h), e.g. 08:15")
    return int(m.group(1)), int(m.group(2))


def _format_prayer_message(payload: dict) -> str:
    """
    HTML-formatted message including the date + ordered prayer times (MSK).
    """
    if not payload or "prayers" not in payload:
        return "<b>No data found yet.</b>"

    prayers: dict = payload.get("prayers", {})
    date_str = payload.get("date", "")
    source_url = payload.get("source_url", "")

    # Optional: prettier date (YYYY-MM-DD -> DD.MM.YYYY)
    pretty_date = date_str
    try:
        d = dt.date.fromisoformat(date_str)
        pretty_date = d.strftime("%d.%m.%Y")
    except Exception:
        pass

    lines = []
    lines.append(f"<b>Prayer times (Moscow / MSK)</b>")
    if pretty_date:
        lines.append(f"<b>Date:</b> {escape(pretty_date)}")
    lines.append("")

    # Ordered output
    used = set()
    for name in PRAYER_ORDER:
        if name in prayers:
            lines.append(f"• <b>{escape(name)}:</b> {escape(prayers[name])}")
            used.add(name)

    # Anything unexpected (if website adds more items)
    for name, val in prayers.items():
        if name not in used:
            lines.append(f"• <b>{escape(name)}:</b> {escape(val)}")

    if source_url:
        lines.append("")
        lines.append(f"<a href='{escape(source_url)}'>Source</a>")

    return "\n".join(lines)


def _schedule_user(app: Application, storage: Storage, user_id: int) -> str:
    """
    Schedule (or reschedule) the daily job for a user.
    Scheduling is ALWAYS in Moscow time (MSK).
    """
    prefs = storage.get_user(user_id)
    if not prefs or not prefs.enabled:
        return "User is not enabled."

    if not prefs.time_hhmm:
        return "No delivery time set. Use /SetTime HH:MM"

    # remove existing jobs
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
    return f"Scheduled daily message at {prefs.time_hhmm} (MSK)."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Keep DB compatible with your existing Storage: store timezone but fixed to Moscow.
    storage.upsert_user(user_id=user_id, chat_id=chat_id, timezone="Europe/Moscow")

    await update.message.reply_text(
        "I will send you the latest prayer times for Moscow (MSK) once per day.\n\n"
        "Commands:\n"
        "/SetTime HH:MM — set the daily delivery time (in MSK)\n"
        "/Time — show your settings\n"
        "/Now — show latest prayer times now\n"
        "/Stop — disable daily messages\n"
    )


async def settime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text("Usage: /SetTime HH:MM (24h, MSK), e.g. /SetTime 08:15")
        return

    time_hhmm = context.args[0].strip()
    try:
        _parse_hhmm(time_hhmm)
    except ValueError as e:
        await update.message.reply_text(str(e))
        return

    storage.set_time(user_id=user_id, chat_id=chat_id, time_hhmm=time_hhmm)
    msg = _schedule_user(context.application, storage, user_id)
    await update.message.reply_text(msg)


async def time_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]

    user_id = update.effective_user.id
    prefs = storage.get_user(user_id)
    if not prefs:
        await update.message.reply_text("No settings found. Send /start")
        return

    await update.message.reply_text(
        f"Enabled: {prefs.enabled}\n"
        f"Daily time (MSK): {prefs.time_hhmm or '(not set)'}"
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]
    user_id = update.effective_user.id

    storage.set_enabled(user_id, False)

    for job in context.application.job_queue.get_jobs_by_name(_job_name(user_id)):
        job.schedule_removal()

    await update.message.reply_text("Daily messages disabled. Use /SetTime HH:MM to re-enable.")


async def now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data_file: str = context.application.bot_data["data_file"]

    try:
        payload = load_latest(data_file)
        msg = _format_prayer_message(payload)
    except Exception as e:
        msg = f"Failed to load latest data: {e}"

    await update.message.reply_text(msg, parse_mode="HTML", disable_web_page_preview=True)


async def send_daily(context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]
    data_file: str = context.application.bot_data["data_file"]

    user_id = context.job.data["user_id"]
    prefs = storage.get_user(user_id)
    if not prefs or not prefs.enabled:
        return

    try:
        payload = load_latest(data_file)
        msg = _format_prayer_message(payload)
    except Exception as e:
        msg = f"Failed to load latest data: {e}"

    await context.bot.send_message(
        chat_id=prefs.chat_id,
        text=msg,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


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

    # Commands (Telegram is typically case-insensitive, but we support both to be safe)
    app.add_handler(CommandHandler(["start"], start))
    app.add_handler(CommandHandler(["settime", "SetTime"], settime))
    app.add_handler(CommandHandler(["time", "Time"], time_cmd))
    app.add_handler(CommandHandler(["now", "Now"], now))
    app.add_handler(CommandHandler(["stop", "Stop"], stop))

    # schedule all enabled users on startup
    for prefs in storage.list_enabled_users():
        if prefs.time_hhmm:
            try:
                _schedule_user(app, storage, prefs.user_id)
            except Exception:
                pass

    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()