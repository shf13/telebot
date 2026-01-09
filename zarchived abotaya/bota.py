# bot.py
import os
import re
import datetime as dt
import logging
import traceback
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

from hijridate import Gregorian
from storage import Storage
# Note: we no longer import load_latest directly here, we use DataLoader
from quran import QuranProvider
from utils import DataLoader  # <--- NEW IMPORT
from telegram.error import BadRequest 

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
MOSCOW_TZ = ZoneInfo("Europe/Moscow")
PRAYER_ORDER = ["Фаджр", "Шурук", "Зухр", "Аср", "Магриб", "Иша"]
TIME_PRESETS = ["06:00", "07:00", "08:00", "09:00", "10:00", "12:00", "18:00", "21:00"]
SUPPORTED_LANGS = ("en", "ar", "ru")

I18N = {
    "en": {
        "intro_short": "Prayer times for Moscow (MSK).",
        "menu_prompt": "Choose an option:",
        "choose_lang": "Choose language:",
        "help": (
            "How to use this bot:\n\n"
            "• /Now — show today's prayer times\n"
            "• /SetTime HH:MM — set daily delivery time (24h, MSK)\n"
            "   Example: /SetTime 08:15\n"
            "• /Time — show your settings (MSK)\n"
            "• /Stop — disable daily messages\n"
            "• /Language — change language\n\n"
            "Tip: You can also use the buttons instead of typing commands."
        ),
        "btn_now": "Now",
        "btn_settings": "My settings",
        "btn_settime": "Set time",
        "btn_stop": "Stop",
        "btn_back": "Back",
        "btn_language": "Language",
        "settime_usage": "Usage: /SetTime HH:MM (24h, MSK), e.g. /SetTime 08:15",
        "settime_pick": "Pick a time (MSK) or type: /SetTime HH:MM\nExample: /SetTime 08:15",
        "invalid_time": "Invalid time format. Use HH:MM (24h, MSK), e.g. /SetTime 08:15",
        "invalid_preset": "Invalid preset time. Please try /SetTime HH:MM (MSK).",
        "ok_daily": "Ok, I will send daily at {time} MSK.",
        "disabled": "Daily messages disabled. Use /SetTime HH:MM (MSK) to enable again.",
        "no_delivery_time": "No delivery time set. Use /SetTime HH:MM (MSK).",
        "no_settings": "No settings found. Send /start",
        "settings": "Enabled: {enabled}\nDaily time (MSK): {time}\n(All times are Moscow time / MSK)",
        "no_data": "Today’s data isn’t available yet, please try again later.",
        "pt_header": "Prayer times (Moscow / MSK)",
        "date_label": "Date:",
        "hijri_label": "Hijri:",
        "source": "Source",
    },
    "ru": {
        "intro_short": "Время намаза для Москвы (MSK).",
        "menu_prompt": "Выберите действие:",
        "choose_lang": "Выберите язык:",
        "help": (
            "Как пользоваться ботом:\n\n"
            "• /Now — показать время намаза на сегодня\n"
            "• /SetTime HH:MM — установить ежедневное время отправки (24ч, MSK)\n"
            "   Пример: /SetTime 08:15\n"
            "• /Time — показать настройки (MSK)\n"
            "• /Stop — отключить ежедневные сообщения\n"
            "• /Language — сменить язык\n\n"
            "Подсказка: можно пользоваться кнопками."
        ),
        "btn_now": "Сейчас",
        "btn_settings": "Мои настройки",
        "btn_settime": "Установить время",
        "btn_stop": "Остановить",
        "btn_back": "Назад",
        "btn_language": "Язык",
        "settime_usage": "Использование: /SetTime HH:MM (24ч, MSK), например /SetTime 08:15",
        "settime_pick": "Выберите время (MSK) или введите: /SetTime HH:MM\nПример: /SetTime 08:15",
        "invalid_time": "Неверный формат. Используйте HH:MM (24ч, MSK), например /SetTime 08:15",
        "invalid_preset": "Неверное время. Попробуйте /SetTime HH:MM (MSK).",
        "ok_daily": "Хорошо, буду отправлять ежедневно в {time} (MSK).",
        "disabled": "Ежедневные сообщения отключены. Используйте /SetTime HH:MM (MSK), чтобы включить снова.",
        "no_delivery_time": "Время не задано. Используйте /SetTime HH:MM (MSK).",
        "no_settings": "Настройки не найдены. Отправьте /start",
        "settings": "Включено: {enabled}\nЕжедневно (MSK): {time}\n(Все времена — московское время / MSK)",
        "no_data": "Сегодняшние данные пока недоступны, попробуйте позже.",
        "pt_header": "Время намаза (Москва / MSK)",
        "date_label": "Дата:",
        "hijri_label": "Хиджри:",
        "source": "Источник",
    },
    "ar": {
        "intro_short": "مواقيت الصلاة لموسكو (MSK).",
        "menu_prompt": "اختر خياراً:",
        "choose_lang": "اختر اللغة:",
        "help": (
            "طريقة استخدام البوت:\n\n"
            "• /Now — عرض مواقيت الصلاة لليوم\n"
            "• /SetTime HH:MM — تحديد وقت الإرسال اليومي (24 ساعة، بتوقيت موسكو MSK)\n"
            "   مثال: /SetTime 08:15\n"
            "• /Time — عرض إعداداتك (MSK)\n"
            "• /Stop — إيقاف الرسائل اليومية\n"
            "• /Language — تغيير اللغة\n\n"
            "ملاحظة: يمكنك استخدام الأزرار بدل كتابة الأوامر."
        ),
        "btn_now": "الآن",
        "btn_settings": "إعداداتي",
        "btn_settime": "تحديد الوقت",
        "btn_stop": "إيقاف",
        "btn_back": "رجوع",
        "btn_language": "اللغة",
        "settime_usage": "الاستخدام: /SetTime HH:MM (24 ساعة، MSK)، مثال: /SetTime 08:15",
        "settime_pick": "اختر وقتاً (MSK) أو اكتب: /SetTime HH:MM\nمثال: /SetTime 08:15",
        "invalid_time": "صيغة الوقت غير صحيحة. استخدم HH:MM (24 ساعة، MSK)، مثال: /SetTime 08:15",
        "invalid_preset": "وقت غير صالح. جرّب /SetTime HH:MM (MSK).",
        "ok_daily": "حسناً، سأرسل يومياً الساعة {time} بتوقيت موسكو (MSK).",
        "disabled": "تم إيقاف الرسائل اليومية. استخدم /SetTime HH:MM (MSK) لتفعيلها مرة أخرى.",
        "no_delivery_time": "لم يتم تحديد وقت. استخدم /SetTime HH:MM (MSK).",
        "no_settings": "لا توجد إعدادات. أرسل /start",
        "settings": "مفعّل: {enabled}\nالوقت اليومي (MSK): {time}\n(كل الأوقات بتوقيت موسكو / MSK)",
        "no_data": "بيانات اليوم غير متوفرة بعد، حاول لاحقاً.",
        "pt_header": "مواقيت الصلاة (موسكو / MSK)",
        "date_label": "التاريخ:",
        "hijri_label": "الهجري:",
        "source": "المصدر",
    },
}

HIJRI_MONTHS = {
    "en": {1: "Muharram", 2: "Safar", 3: "Rabi' al-Awwal", 4: "Rabi' al-Thani", 5: "Jumada al-Ula", 6: "Jumada al-Akhirah", 7: "Rajab", 8: "Sha'ban", 9: "Ramadan", 10: "Shawwal", 11: "Dhu al-Qi'dah", 12: "Dhu al-Hijjah"},
    "ru": {1: "Мухаррам", 2: "Сафар", 3: "Раби аль-авваль", 4: "Раби ас-сани", 5: "Джумада аль-уля", 6: "Джумада ас-сания", 7: "Раджаб", 8: "Шаабан", 9: "Рамадан", 10: "Шавваль", 11: "Зуль-каада", 12: "Зуль-хиджа"},
    "ar": {1: "محرم", 2: "صفر", 3: "ربيع الأول", 4: "ربيع الآخر", 5: "جمادى الأولى", 6: "جمادى الآخرة", 7: "رجب", 8: "شعبان", 9: "رمضان", 10: "شوال", 11: "ذو القعدة", 12: "ذو الحجة"},
}

PRAYER_NAME_MAP = {
    "ru": {"Фаджр": "Фаджр", "Шурук": "Шурук", "Зухр": "Зухр", "Аср": "Аср", "Магриб": "Магриб", "Иша": "Иша"},
    "en": {"Фаджр": "Fajr", "Шурук": "Sunrise", "Зухр": "Dhuhr", "Аср": "Asr", "Магриб": "Maghrib", "Иша": "Isha"},
    "ar": {"Фаджр": "الفجر", "Шурук": "الشروق", "Зухр": "الظهر", "Аср": "العصر", "Магриб": "المغرب", "Иша": "العشاء"},
}


def tr(lang: str, key: str) -> str:
    return I18N.get(lang, I18N["en"])[key]


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("English", callback_data="LANG:en"),
            InlineKeyboardButton("العربية", callback_data="LANG:ar"),
            InlineKeyboardButton("Русский", callback_data="LANG:ru"),
        ]]
    )


def _job_name(user_id: int) -> str:
    return f"daily_{user_id}"


def _lang_or_prompt(prefs) -> str | None:
    if prefs and getattr(prefs, "language", None) in SUPPORTED_LANGS:
        return prefs.language
    return None


def _parse_hhmm(s: str, lang: str) -> tuple[int, int]:
    m = TIME_RE.match(s.strip())
    if not m:
        raise ValueError(tr(lang, "invalid_time"))
    return int(m.group(1)), int(m.group(2))


def _main_menu_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(tr(lang, "btn_now"), callback_data="NOW"),
                InlineKeyboardButton(tr(lang, "btn_settings"), callback_data="TIME"),
            ],
            [InlineKeyboardButton(tr(lang, "btn_settime"), callback_data="SETTIME")],
            [
                InlineKeyboardButton(tr(lang, "btn_language"), callback_data="LANGMENU"),
                InlineKeyboardButton(tr(lang, "btn_stop"), callback_data="STOP"),
            ],
        ]
    )


def _preset_time_kb(lang: str) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for t in TIME_PRESETS:
        row.append(InlineKeyboardButton(t, callback_data=f"PRESET:{t}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(tr(lang, "btn_back"), callback_data="BACK")])
    return InlineKeyboardMarkup(rows)


def _hijri_string_for_date(greg_date: dt.date, lang: str) -> str | None:
    try:
        h = Gregorian(greg_date.year, greg_date.month, greg_date.day).to_hijri()
        month_name = HIJRI_MONTHS.get(lang, HIJRI_MONTHS["en"]).get(int(h.month), str(h.month))
        return f"{int(h.day)} {month_name} {int(h.year)}"
    except Exception:
        return None


def _format_prayer_message(payload: dict, lang: str, ayah: dict | None = None) -> str:
    if not payload or "prayers" not in payload:
        return f"<b>{escape(tr(lang, 'no_data'))}</b>"

    prayers: dict = payload.get("prayers", {})
    date_str = payload.get("date", "")
    source_url = payload.get("source_url", "")

    pretty_date = date_str
    greg_date = None
    try:
        greg_date = dt.date.fromisoformat(date_str)
        pretty_date = greg_date.strftime("%d.%m.%Y")
    except Exception:
        pass

    hijri_str = _hijri_string_for_date(greg_date, lang) if greg_date else None
    name_map = PRAYER_NAME_MAP.get(lang, PRAYER_NAME_MAP["en"])

    lines = []
    lines.append(f"<b>{escape(tr(lang, 'pt_header'))}</b>")
    if pretty_date:
        lines.append(f"<b>{escape(tr(lang, 'date_label'))}</b> {escape(pretty_date)}")
    if hijri_str:
        lines.append(f"<b>{escape(tr(lang, 'hijri_label'))}</b> {escape(hijri_str)}")
    lines.append("")

    used = set()
    for key in PRAYER_ORDER:
        if key in prayers:
            label = name_map.get(key, key)
            lines.append(f"• <b>{escape(label)}:</b> {escape(prayers[key])}")
            used.add(key)

    for key, val in prayers.items():
        if key not in used:
            label = name_map.get(key, key)
            lines.append(f"• <b>{escape(label)}:</b> {escape(val)}")

    # AYAH SECTION
    if ayah:
        lines.append("")
        lines.append("----------------")
        ar_text = ayah.get("ar", "").strip()
        en_text = ayah.get("en", "").strip()
        ru_text = ayah.get("ru", "").strip()
        ref = ayah.get("ref", "").strip()
        
        ayah_content = []
        if ar_text:
            ayah_content.append(escape(ar_text))
        
        if lang == "en" and en_text:
            ayah_content.append(f"<i>{escape(en_text)}</i>")
        elif lang == "ru" and ru_text:
            ayah_content.append(f"<i>{escape(ru_text)}</i>")
            
        if ref:
            ayah_content.append(f"[{escape(ref)}]")
        
        lines.append("\n".join(ayah_content))

    if source_url:
        lines.append("")
        lines.append(f"<a href='{escape(source_url)}'>{escape(tr(lang, 'source'))}</a>")

    return "\n".join(lines)


# --- UPDATED: Uses DataLoader instead of direct file path ---
def _load_today_or_friendly(data_loader: DataLoader, lang: str) -> tuple[dict | None, str | None]:
    try:
        payload = data_loader.get_data()
    except Exception:
        return None, tr(lang, "no_data")

    if not payload or not isinstance(payload, dict):
        return None, tr(lang, "no_data")

    prayers = payload.get("prayers")
    if not prayers:
        return None, tr(lang, "no_data")

    today_msk = dt.datetime.now(MOSCOW_TZ).date().isoformat()
    if payload.get("date") != today_msk:
        return None, tr(lang, "no_data")

    return payload, None


def _schedule_user(app: Application, storage: Storage, user_id: int, lang: str) -> str:
    prefs = storage.get_user(user_id)
    if not prefs or not prefs.enabled:
        return tr(lang, "disabled")

    if not prefs.time_hhmm:
        return tr(lang, "no_delivery_time")

    for job in app.job_queue.get_jobs_by_name(_job_name(user_id)):
        job.schedule_removal()

    hour, minute = _parse_hhmm(prefs.time_hhmm, lang)
    t = dt.time(hour=hour, minute=minute, tzinfo=MOSCOW_TZ)

    app.job_queue.run_daily(
        callback=send_daily,
        time=t,
        name=_job_name(user_id),
        data={"user_id": user_id},
    )
    return tr(lang, "ok_daily").format(time=prefs.time_hhmm)


async def _prompt_language_start(update: Update):
    text = (
        "Prayer times for Moscow (MSK).\n"
        "مواقيت الصلاة لموسكو (MSK).\n"
        "Время намаза для Москвы (MSK).\n\n"
        "Choose language / اختر اللغة / Выберите язык:"
    )
    await update.message.reply_text(text, reply_markup=language_keyboard())


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]
    data_loader: DataLoader = context.application.bot_data["data_loader"] # FIXED: This now exists
    quran: QuranProvider = context.application.bot_data["quran"]

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    storage.upsert_user(user_id=user_id, chat_id=chat_id)
    prefs = storage.get_user(user_id)
    lang = _lang_or_prompt(prefs)

    if not lang:
        await _prompt_language_start(update)
        return

    payload, friendly = _load_today_or_friendly(data_loader, lang)
    if friendly:
        await update.message.reply_text(
            f"{tr(lang, 'intro_short')}\n\n{friendly}",
            reply_markup=_main_menu_kb(lang),
        )
        return

    ayah = quran.get_random_ayah()
    msg = _format_prayer_message(payload, lang, ayah=ayah)
    combined = f"{escape(tr(lang, 'intro_short'))}\n\n{msg}"
    
    await update.message.reply_text(
        combined,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=_main_menu_kb(lang),
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]
    prefs = storage.get_user(update.effective_user.id)
    lang = _lang_or_prompt(prefs) or "en"
    if not getattr(prefs, "language", None):
        await update.message.reply_text("Choose language:", reply_markup=language_keyboard())
        return

    await update.message.reply_text(tr(lang, "help"), reply_markup=_main_menu_kb(lang))


async def language_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]
    storage.upsert_user(user_id=update.effective_user.id, chat_id=update.effective_chat.id)
    await update.message.reply_text(tr("en", "choose_lang"), reply_markup=language_keyboard())


async def settime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]
    user_id = update.effective_user.id
    prefs = storage.get_user(user_id)
    lang = _lang_or_prompt(prefs)
    
    if not lang:
        await update.message.reply_text("Choose language:", reply_markup=language_keyboard())
        return

    if not context.args:
        await update.message.reply_text(tr(lang, "settime_usage"), reply_markup=_preset_time_kb(lang))
        return

    time_hhmm = context.args[0].strip()
    try:
        _parse_hhmm(time_hhmm, lang)
    except ValueError as e:
        await update.message.reply_text(str(e), reply_markup=_preset_time_kb(lang))
        return

    storage.set_time(user_id=user_id, chat_id=update.effective_chat.id, time_hhmm=time_hhmm)
    msg = _schedule_user(context.application, storage, user_id, lang)
    await update.message.reply_text(msg, reply_markup=_main_menu_kb(lang))


async def time_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]
    prefs = storage.get_user(update.effective_user.id)
    lang = _lang_or_prompt(prefs)
    if not lang:
        await update.message.reply_text("Choose language:", reply_markup=language_keyboard())
        return

    if not prefs:
        await update.message.reply_text(tr(lang, "no_settings"), reply_markup=_main_menu_kb(lang))
        return

    await update.message.reply_text(
        tr(lang, "settings").format(enabled=prefs.enabled, time=(prefs.time_hhmm or "(not set)")),
        reply_markup=_main_menu_kb(lang),
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]
    user_id = update.effective_user.id
    prefs = storage.get_user(user_id)
    lang = _lang_or_prompt(prefs) or "en"

    storage.set_enabled(user_id, False)
    for job in context.application.job_queue.get_jobs_by_name(_job_name(user_id)):
        job.schedule_removal()

    await update.message.reply_text(tr(lang, "disabled"), reply_markup=_main_menu_kb(lang))


async def now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]
    data_loader: DataLoader = context.application.bot_data["data_loader"] # FIXED
    quran: QuranProvider = context.application.bot_data["quran"]

    prefs = storage.get_user(update.effective_user.id)
    lang = _lang_or_prompt(prefs)
    if not lang:
        await update.message.reply_text("Choose language:", reply_markup=language_keyboard())
        return

    payload, friendly = _load_today_or_friendly(data_loader, lang)
    if friendly:
        await update.message.reply_text(friendly, reply_markup=_main_menu_kb(lang))
        return

    ayah = quran.get_random_ayah()
    msg = _format_prayer_message(payload, lang, ayah=ayah)
    await update.message.reply_text(
        msg, parse_mode="HTML", disable_web_page_preview=True, reply_markup=_main_menu_kb(lang)
    )


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin Only: Show bot statistics."""
    admin_id = os.getenv("ADMIN_ID")
    user_id = update.effective_user.id

    if str(user_id) != str(admin_id):
        return  # Ignore non-admins

    storage: Storage = context.application.bot_data["storage"]
    
    # Simple count logic (You can optimize this in storage.py if needed)
    with storage._connect() as con:
        total = con.execute("SELECT COUNT(*) FROM user_prefs").fetchone()[0]
        enabled = con.execute("SELECT COUNT(*) FROM user_prefs WHERE enabled=1").fetchone()[0]
        
        # Count languages
        rows = con.execute("SELECT language, COUNT(*) FROM user_prefs GROUP BY language").fetchall()
        langs = {r[0]: r[1] for r in rows}

    msg = (
        f"📊 <b>Bot Statistics</b>\n\n"
        f"👥 Total Users: {total}\n"
        f"✅ Active: {enabled}\n"
        f"❌ Stopped: {total - enabled}\n\n"
        f"<b>Languages:</b>\n"
        f"🇷🇺 RU: {langs.get('ru', 0)}\n"
        f"🇬🇧 EN: {langs.get('en', 0)}\n"
        f"🇸🇦 AR: {langs.get('ar', 0)}\n"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


async def send_daily(context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.application.bot_data["storage"]
    data_loader: DataLoader = context.application.bot_data["data_loader"] # FIXED
    quran: QuranProvider = context.application.bot_data["quran"]

    user_id = context.job.data["user_id"]
    prefs = storage.get_user(user_id)
    if not prefs or not prefs.enabled:
        return

    lang = getattr(prefs, "language", None) or "en"
    payload, friendly = _load_today_or_friendly(data_loader, lang)
    if friendly:
        await context.bot.send_message(chat_id=prefs.chat_id, text=friendly)
        return

    ayah = quran.get_random_ayah()
    msg = _format_prayer_message(payload, lang, ayah=ayah)
    try:
        await context.bot.send_message(
            chat_id=prefs.chat_id, text=msg, parse_mode="HTML", disable_web_page_preview=True
        )
    except Exception as e:
        print(f"Failed to send daily to {user_id}: {e}")
        # Optionally disable user if bot was blocked


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    storage: Storage = context.application.bot_data["storage"]
    data_loader: DataLoader = context.application.bot_data["data_loader"] # FIXED
    quran: QuranProvider = context.application.bot_data["quran"]

    user_id = query.from_user.id
    chat_id = query.message.chat_id
    data = query.data

    if data == "LANGMENU":
        prefs = storage.get_user(user_id)
        lang = _lang_or_prompt(prefs) or "en"
        await query.edit_message_text(tr(lang, "choose_lang"), reply_markup=language_keyboard())
        return

    if data.startswith("LANG:"):
        lang = data.split(":", 1)[1].strip()
        if lang not in SUPPORTED_LANGS:
            lang = "en"
        storage.set_language(user_id=user_id, chat_id=chat_id, language=lang)
        
        payload, friendly = _load_today_or_friendly(data_loader, lang)
        if friendly:
            combined = f"{escape(tr(lang, 'intro_short'))}\n\n{escape(friendly)}"
            await query.edit_message_text(combined, reply_markup=_main_menu_kb(lang))
            return

        ayah = quran.get_random_ayah()
        msg = _format_prayer_message(payload, lang, ayah=ayah)
        combined = f"{escape(tr(lang, 'intro_short'))}\n\n{msg}"
        await query.edit_message_text(combined, parse_mode="HTML", disable_web_page_preview=True, reply_markup=_main_menu_kb(lang))
        return

    prefs = storage.get_user(user_id)
    lang = _lang_or_prompt(prefs)
    if not lang:
        await query.edit_message_text("Choose language:", reply_markup=language_keyboard())
        return

    if data == "BACK":
        await query.edit_message_text(tr(lang, "menu_prompt"), reply_markup=_main_menu_kb(lang))
        return
    
    if data == "SETTIME":
        await query.edit_message_text(tr(lang, "settime_pick"), reply_markup=_preset_time_kb(lang))
        return

    if data == "TIME":
        txt = tr(lang, "settings").format(enabled=prefs.enabled, time=(prefs.time_hhmm or "(not set)"))
        await query.edit_message_text(txt, reply_markup=_main_menu_kb(lang))
        return

    if data == "STOP":
        storage.set_enabled(user_id, False)
        for job in context.application.job_queue.get_jobs_by_name(_job_name(user_id)):
            job.schedule_removal()
        await query.edit_message_text(tr(lang, "disabled"), reply_markup=_main_menu_kb(lang))
        return

    if data == "NOW":
        payload, friendly = _load_today_or_friendly(data_loader, lang)
        if friendly:
            await query.edit_message_text(friendly, reply_markup=_main_menu_kb(lang))
            return
        
        ayah = quran.get_random_ayah()
        msg = _format_prayer_message(payload, lang, ayah=ayah)
        await query.edit_message_text(msg, parse_mode="HTML", disable_web_page_preview=True, reply_markup=_main_menu_kb(lang))
        return

    if data.startswith("PRESET:"):
        time_hhmm = data.split(":", 1)[1].strip()
        try:
            _parse_hhmm(time_hhmm, lang)
        except ValueError:
            await query.edit_message_text(tr(lang, "invalid_preset"), reply_markup=_preset_time_kb(lang))
            return
        storage.upsert_user(user_id=user_id, chat_id=chat_id)
        storage.set_time(user_id=user_id, chat_id=chat_id, time_hhmm=time_hhmm)
        msg = _schedule_user(context.application, storage, user_id, lang)
        await query.edit_message_text(msg, reply_markup=_main_menu_kb(lang))
        return


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""

    # --- NEW: Filter out "Message not modified" errors ---
    if isinstance(context.error, BadRequest):
        if "Message is not modified" in str(context.error):
            # This happens when a user clicks a button (like "Now") twice
            # and the text/buttons haven't changed. We can safely ignore it.
            return
    # -----------------------------------------------------
    
    logger.error("Exception while handling an update:", exc_info=context.error)
    admin_id = os.getenv("ADMIN_ID")
    if not admin_id:
        return

    # Format the traceback    
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)
    
    # Send error to Admin
    message = (
        f"An exception was raised while handling an update\n"
        f"<pre>{escape(tb_string[-4000:])}</pre>"
    )
    
    try:
        await context.bot.send_message(chat_id=admin_id, text=message, parse_mode="HTML")
    except Exception:
        # Fallback if the error message itself fails
        pass

def main():
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set.")
    
    # Check Admin ID
    if not os.getenv("ADMIN_ID"):
        print("WARNING: ADMIN_ID not set in .env")

    data_file = os.getenv("DATA_FILE", os.path.abspath("data/latest.json"))
    db_file = os.getenv("DB_FILE", os.path.abspath("data/bot.sqlite3"))
    quran_file = os.getenv("QURAN_FILE", os.path.abspath("data/ayahs.csv"))

    storage = Storage(db_file)
    quran_provider = QuranProvider(quran_file)
    data_loader = DataLoader(data_file)  # <--- Initialize DataLoader

    app = Application.builder().token(token).build()
    
    # <--- Add DataLoader to bot_data so handlers can find it
    app.bot_data["storage"] = storage
    app.bot_data["data_loader"] = data_loader 
    app.bot_data["quran"] = quran_provider

    app.add_handler(CommandHandler(["start"], start))
    app.add_handler(CommandHandler(["help", "Help"], help_cmd))
    app.add_handler(CommandHandler(["language", "Language"], language_cmd))
    app.add_handler(CommandHandler(["settime", "SetTime"], settime))
    app.add_handler(CommandHandler(["time", "Time"], time_cmd))
    app.add_handler(CommandHandler(["now", "Now"], now))
    app.add_handler(CommandHandler(["stop", "Stop"], stop))
    app.add_handler(CommandHandler(["stats", "Stats"], stats_cmd)) # Stats

    app.add_handler(CallbackQueryHandler(on_button))
    app.add_error_handler(error_handler) # Error reporting

    # Restore Jobs
    for prefs in storage.list_enabled_users():
        if prefs.time_hhmm:
            try:
                lang = getattr(prefs, "language", None) or "en"
                _schedule_user(app, storage, prefs.user_id, lang)
            except Exception:
                pass

    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()