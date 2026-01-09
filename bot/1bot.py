import os
import re
import datetime as dt
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from storage import Storage
from formatter import load_latest, format_message


TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _job_name(user_id: int) -> str:
    return f"daily_{user_id}"


def _parse_hhmm(s: str) -> tuple[int, int]:
    m = TIME_RE.match(s.strip())
    if not m:
        raise ValueError("Invalid time format. Use HH:MM (24h), e.g. 08:15")
    return int(m.group(1)), int(m.group(2))


def _schedule_user(app: Application, storage: Storage, user_id: int) -> str:
    """
    Schedule (or reschedule) the daily job for a user.
    Returns a human-readable status message.
    """
    prefs = storage.get_user(user_id)
    if not prefs or not prefs.enabled:
        return "User is not enabled."

    if not prefs.time_hhmm:
        return "No delivery time set. Use /settime HH:MM"

    # remove existing jobs
    for job in app.job_queue.get_jobs_by_name(_job_name(user_id)):
        job.schedule_removal()

    hour, minute = _parse_hhmm(prefs.time_hhmm)
    tz = ZoneInfo(prefs.timezone)
    t = dt.time(hour=hour, minute=minute, tzinfo=tz)

    app.job_queue.run_daily(
        callback=send_daily,
        time=t,
        name=_job_name(user_id),
        data={"user_id": user_id},
    )
    return f"Scheduled daily message at {prefs.time_hhmm} ({prefs.timezone})."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]
    default_tz: str = context.application.bot_data["default_tz"]

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # ensure user exists in DB
    storage.upsert_user(user_id=user_id, chat_id=chat_id, timezone=default_tz)

    await update.message.reply_text(
        "I will send you the latest prayer times of Moscow once per day.\n\n"
        "Commands:\n"
        "/setTZ <Timezone>  (e.g. /setTZ Europe/Moscow)\n"
        "/settime HH:MM 24    (e.g. /settime 08:15)\n"
        "/time              (show your settings)\n"
        "/now               (send latest now)\n"
        "/stop              (disable daily messages)\n"
    )


async def setTZ(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text("Usage: /setTZ Europe/Berlin")
        return

    tz = context.args[0].strip()
    try:
        ZoneInfo(tz)
    except Exception:
        await update.message.reply_text(
            "Unknown timezone. Use an IANA name like Europe/Berlin, UTC, Asia/Tashkent."
        )
        return

    storage.set_timezone(user_id=user_id, chat_id=chat_id, timezone=tz)
    msg = _schedule_user(context.application, storage, user_id)
    await update.message.reply_text(f"Timezone set to {tz}.\n{msg}")


async def settime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text("Usage: /settime HH:MM (24h), e.g. /settime 08:15")
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
        f"Timezone: {prefs.timezone}\n"
        f"Time: {prefs.time_hhmm or '(not set)'}"
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]
    user_id = update.effective_user.id

    storage.set_enabled(user_id, False)

    # remove job
    for job in context.application.job_queue.get_jobs_by_name(_job_name(user_id)):
        job.schedule_removal()

    await update.message.reply_text("Daily messages disabled. Use /settime HH:MM to re-enable.")


async def now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data_file: str = context.application.bot_data["data_file"]
    try:
        payload = load_latest(data_file)
        msg = format_message(payload, data_file)
    except Exception as e:
        msg = f"Failed to load latest data: {e}"

    await update.message.reply_text(msg)


async def send_daily(context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]
    data_file: str = context.application.bot_data["data_file"]

    user_id = context.job.data["user_id"]
    prefs = storage.get_user(user_id)
    if not prefs or not prefs.enabled:
        return

    try:
        payload = load_latest(data_file)
        msg = format_message(payload, data_file)
    except Exception as e:
        msg = f"Failed to load latest data: {e}"

    await context.bot.send_message(chat_id=prefs.chat_id, text=msg)


def main():
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set.")

    data_file = os.getenv("DATA_FILE", os.path.abspath("data/latest.json"))
    db_file = os.getenv("DB_FILE", os.path.abspath("data/bot.sqlite3"))
    default_tz = os.getenv("DEFAULT_TIMEZONE", "UTC")

    storage = Storage(db_file)

    app = Application.builder().token(token).build()
    app.bot_data["storage"] = storage
    app.bot_data["data_file"] = data_file
    app.bot_data["default_tz"] = default_tz

    # commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setTZ", setTZ))
    app.add_handler(CommandHandler("settime", settime))
    app.add_handler(CommandHandler("time", time_cmd))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("now", now))

    # schedule all enabled users on startup
    for prefs in storage.list_enabled_users():
        if prefs.time_hhmm:
            try:
                _schedule_user(app, storage, prefs.user_id)
            except Exception:
                # ignore scheduling errors on startup; user can fix via /settime or /setTZ
                pass

    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()