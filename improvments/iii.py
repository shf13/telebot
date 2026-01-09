"""
Prayer Times Bot - Main Application

Features:
- Prayer times with Hijri calendar
- Daily Quranic verses
- Friday reminders
- User feedback system
- Admin broadcast
- Multi-language support
- Habit tracking
"""

import os
import re
import asyncio
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
    MessageHandler,
    filters,
    InlineQueryHandler,
)
from telegram.error import BadRequest
from hijridate import Gregorian

# Import configurations and modules
from config import *
from storage import Storage
from cache import CacheManager
from formatter import load_latest
from quran import QuranManager
from feedback import FeedbackManager
from notification import NotificationManager
from habit_tracker import HabitTracker
from locations import SUPPORTED_LOCATIONS, get_location_name
from logger import setup_logger
from monitoring import SystemMonitor

# Setup logger
logger = setup_logger(__name__)

# Constants
MOSCOW_TZ = ZoneInfo("Europe/Moscow")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

HIJRI_MONTHS = {
    "en": {
        1: "Muharram", 2: "Safar", 3: "Rabi' al-Awwal", 4: "Rabi' al-Thani",
        5: "Jumada al-Ula", 6: "Jumada al-Akhirah", 7: "Rajab", 8: "Sha'ban",
        9: "Ramadan", 10: "Shawwal", 11: "Dhu al-Qi'dah", 12: "Dhu al-Hijjah",
    },
    "ru": {
        1: "Мухаррам", 2: "Сафар", 3: "Раби аль-авваль", 4: "Раби ас-сани",
        5: "Джумада аль-уля", 6: "Джумада ас-сания", 7: "Раджаб", 8: "Шаабан",
        9: "Рамадан", 10: "Шавваль", 11: "Зуль-каада", 12: "Зуль-хиджа",
    },
    "ar": {
        1: "محرم", 2: "صفر", 3: "ربيع الأول", 4: "ربيع الآخر",
        5: "جمادى الأولى", 6: "جمادى الآخرة", 7: "رجب", 8: "شعبان",
        9: "رمضان", 10: "شوال", 11: "ذو القعدة", 12: "ذو الحجة",
    },
}

PRAYER_NAME_MAP = {
    "ru": {
        "Фаджр": "Фаджр",
        "Шурук": "Шурук",
        "Зухр": "Зухр",
        "Аср": "Аср",
        "Магриб": "Магриб",
        "Иша": "Иша",
    },
    "en": {
        "Фаджр": "Fajr",
        "Шурук": "Sunrise",
        "Зухр": "Dhuhr",
        "Аср": "Asr",
        "Магриб": "Maghrib",
        "Иша": "Isha",
    },
    "ar": {
        "Фаджр": "الفجر",
        "Шурук": "الشروق",
        "Зухр": "الظهر",
        "Аср": "العصر",
        "Магриб": "المغرب",
        "Иша": "العشاء",
    },
}

PRAYER_EMOJI = {
    "Фаджр": "🌅",
    "Шурук": "🌄",
    "Зухр": "☀️",
    "Аср": "🌤️",
    "Магриб": "🌆",
    "Иша": "🌙",
}

I18N = {
    "en": {
        "intro_short": "🕌 Prayer times for Moscow (MSK).",
        "menu_prompt": "Choose an option:",
        "choose_lang": "Choose language:",
        "help": (
            "How to use this bot:\n\n"
            "• /Now — show today's prayer times\n"
            "• /SetTime HH:MM — set daily delivery time (24h, MSK)\n"
            "   Example: /SetTime 08:15\n"
            "• /Time — show your settings\n"
            "• /Stop — disable daily messages\n"
            "• /Language — change language\n"
            "• /Feedback — send feedback or report bugs\n"
            "• /Stats — view your statistics\n\n"
            "Tip: You can also use the buttons."
        ),
        "btn_now": "Now",
        "btn_settings": "My settings",
        "btn_settime": "Set time",
        "btn_stop": "Stop",
        "btn_back": "Back",
        "btn_language": "Language",
        "btn_feedback": "Feedback",
        "settime_usage": "Usage: /SetTime HH:MM (24h, MSK), e.g. /SetTime 08:15",
        "settime_pick": "Pick a time (MSK) or type: /SetTime HH:MM\nExample: /SetTime 08:15",
        "invalid_time": "Invalid time format. Use HH:MM (24h, MSK), e.g. /SetTime 08:15",
        "invalid_preset": "Invalid preset time. Please try /SetTime HH:MM (MSK).",
        "ok_daily": "✅ I will send daily at {time} MSK.",
        "disabled": "❌ Daily messages disabled. Use /SetTime HH:MM (MSK) to enable again.",
        "no_delivery_time": "❌ No delivery time set. Use /SetTime HH:MM (MSK).",
        "no_settings": "❌ No settings found. Send /start",
        "settings": "⚙️ <b>Your Settings</b>\n\n✅ Notifications: {enabled}\n🕐 Daily time (MSK): {time}\n📍 Location: {location}",
        "no_data": "❌ Today's data isn't available yet, please try again later.",
        "pt_header": "🕌 Prayer times (Moscow / MSK)",
        "date_label": "📅 Date:",
        "hijri_label": "🗓️ Hijri:",
        "source": "🔗 Source",
        "feedback_thanks": "✅ Thank you for your feedback!",
        "feedback_prompt": "📝 Send your feedback:\n\nWhat type?\n🐛 Bug\n💡 Feature\n🎯 Suggestion\n📝 Other",
        "friday_reminder": "📖 Reminder: Read Surah Al-Kahf today (Friday)\n\nReading on Friday is Sunnah and highly recommended. 🕌",
        "error_occurred": "❌ An error occurred. Please try again later.",
        "broadcast_received": "📢 <b>Message from Admin:</b>\n\n{message}",
        "next_prayer": "⏳ Next Prayer:",
        "next_prayer_tomorrow": "⏳ Next prayer is tomorrow",
        "countdown": "⏰ Countdown",
        "location_changed": "✅ Location changed to {location}",
        "stats_title": "📊 <b>Your Statistics</b>",
        "days_active": "📅 Days Active:",
        "feedback_sent": "💬 Feedback Sent:",
        "prayer_streak": "🔥 Prayer Streak:",
    },
    "ru": {
        "intro_short": "🕌 Время намаза для Москвы (MSK).",
        "menu_prompt": "Выберите действие:",
        "choose_lang": "Выберите язык:",
        "help": (
            "Как пользоваться ботом:\n\n"
            "• /Now — показать время намаза на сегодня\n"
            "• /SetTime HH:MM — установить ежедневное время отправки (24ч, MSK)\n"
            "   Пример: /SetTime 08:15\n"
            "• /Time — показать настройки\n"
            "• /Stop — отключить ежедневные сообщения\n"
            "• /Language — сменить язык\n"
            "• /Feedback — отправить отзыв или сообщить об ошибке\n"
            "• /Stats — посмотреть статистику\n\n"
            "Подсказка: можно пользоваться кнопками."
        ),
        "btn_now": "Сейчас",
        "btn_settings": "Мои настройки",
        "btn_settime": "Установить время",
        "btn_stop": "Остановить",
        "btn_back": "Назад",
        "btn_language": "Язык",
        "btn_feedback": "Отзыв",
        "settime_usage": "Использование: /SetTime HH:MM (24ч, MSK), например /SetTime 08:15",
        "settime_pick": "Выберите время (MSK) или введите: /SetTime HH:MM\nПример: /SetTime 08:15",
        "invalid_time": "Неверный формат. Используйте HH:MM (24ч, MSK), например /SetTime 08:15",
        "invalid_preset": "Неверное время. Попробуйте /SetTime HH:MM (MSK).",
        "ok_daily": "✅ Буду отправлять ежедневно в {time} (MSK).",
        "disabled": "❌ Ежедневные сообщения отключены. Используйте /SetTime HH:MM (MSK), чтобы включить снова.",
        "no_delivery_time": "❌ Время не задано. Используйте /SetTime HH:MM (MSK).",
        "no_settings": "❌ Настройки не найдены. Отправьте /start",
        "settings": "⚙️ <b>Ваши настройки</b>\n\n✅ Уведомления: {enabled}\n🕐 Ежедневно (MSK): {time}\n📍 Город: {location}",
        "no_data": "❌ Сегодняшние данные пока недоступны, попробуйте позже.",
        "pt_header": "🕌 Время намаза (Москва / MSK)",
        "date_label": "📅 Дата:",
        "hijri_label": "🗓️ Хиджри:",
        "source": "🔗 Источник",
        "feedback_thanks": "✅ Спасибо за ваш отзыв!",
        "feedback_prompt": "📝 Отправьте ваш отзыв:\n\nКакой тип?\n🐛 Ошибка\n💡 Функция\n🎯 Предложение\n📝 Другое",
        "friday_reminder": "📖 Напоминание: Прочитайте Суру Аль-Кахф сегодня (Пятница)\n\nЧтение в пятницу — Сунна. 🕌",
        "error_occurred": "❌ Произошла ошибка. Попробуйте позже.",
        "broadcast_received": "📢 <b>Сообщение от администратора:</b>\n\n{message}",
        "next_prayer": "⏳ Следующая молитва:",
        "next_prayer_tomorrow": "⏳ Следующая молитва завтра",
        "countdown": "⏰ Обратный отсчет",
        "location_changed": "✅ Город изменен на {location}",
        "stats_title": "📊 <b>Ваша статистика</b>",
        "days_active": "📅 Дней активности:",
        "feedback_sent": "💬 Отзывов отправлено:",
        "prayer_streak": "🔥 Серия молитв:",
    },
    "ar": {
        "intro_short": "🕌 مواقيت الصلاة لموسكو (MSK).",
        "menu_prompt": "اختر خياراً:",
        "choose_lang": "اختر اللغة:",
        "help": (
            "طريقة استخدام البوت:\n\n"
            "• /Now — عرض مواقيت الصلاة لليوم\n"
            "• /SetTime HH:MM — تحديد وقت الإرسال اليومي (24 ساعة، بتوقيت موسكو MSK)\n"
            "   مثال: /SetTime 08:15\n"
            "• /Time — عرض إعداداتك\n"
            "• /Stop — إيقاف الرسائل اليومية\n"
            "• /Language — تغيير اللغة\n"
            "• /Feedback — إرسال تعليق أو إبلاغ عن خطأ\n"
            "• /Stats — عرض إحصائياتك\n\n"
            "ملاحظة: يمكنك استخدام الأزرار."
        ),
        "btn_now": "الآن",
        "btn_settings": "إعداداتي",
        "btn_settime": "تحديد الوقت",
        "btn_stop": "إيقاف",
        "btn_back": "رجوع",
        "btn_language": "اللغة",
        "btn_feedback": "تعليق",
        "settime_usage": "الاستخدام: /SetTime HH:MM (24 ساعة، MSK)، مثال: /SetTime 08:15",
        "settime_pick": "اختر وقتاً (MSK) أو اكتب: /SetTime HH:MM\nمثال: /SetTime 08:15",
        "invalid_time": "صيغة الوقت غير صحيحة. استخدم HH:MM (24 ساعة، MSK)، مثال: /SetTime 08:15",
        "invalid_preset": "وقت غير صالح. جرّب /SetTime HH:MM (MSK).",
        "ok_daily": "✅ سأرسل يومياً الساعة {time} بتوقيت موسكو (MSK).",
        "disabled": "❌ تم إيقاف الرسائل اليومية. استخدم /SetTime HH:MM (MSK) لتفعيلها.",
        "no_delivery_time": "❌ لم يتم تحديد وقت. استخدم /SetTime HH:MM (MSK).",
        "no_settings": "❌ لا توجد إعدادات. أرسل /start",
        "settings": "⚙️ <b>إعداداتك</b>\n\n✅ الإخطارات: {enabled}\n🕐 الوقت اليومي (MSK): {time}\n📍 المدينة: {location}",
        "no_data": "❌ بيانات اليوم غير متوفرة بعد، حاول لاحقاً.",
        "pt_header": "🕌 مواقيت الصلاة (موسكو / MSK)",
        "date_label": "📅 التاريخ:",
        "hijri_label": "🗓️ الهجري:",
        "source": "🔗 المصدر",
        "feedback_thanks": "✅ شكراً على تعليقك!",
        "feedback_prompt": "📝 أرسل تعليقك:\n\nما النوع؟\n🐛 خطأ\n💡 ميزة\n🎯 اقتراح\n📝 أخرى",
        "friday_reminder": "📖 تذكير: اقرأ سورة الكهف اليوم (الجمعة)\n\nالقراءة يوم الجمعة سنة. 🕌",
        "error_occurred": "❌ حدثت خطأ. حاول لاحقاً.",
        "broadcast_received": "📢 <b>رسالة من المسؤول:</b>\n\n{message}",
        "next_prayer": "⏳ الصلاة القادمة:",
        "next_prayer_tomorrow": "⏳ الصلاة القادمة غداً",
        "countdown": "⏰ العد التنازلي",
        "location_changed": "✅ تم تغيير المدينة إلى {location}",
        "stats_title": "📊 <b>إحصائياتك</b>",
        "days_active": "📅 أيام النشاط:",
        "feedback_sent": "💬 التعليقات المرسلة:",
        "prayer_streak": "🔥 سلسلة الصلاة:",
    },
}


def tr(lang: str, key: str) -> str:
    """Translate key to language."""
    if lang not in I18N:
        lang = "en"
    return I18N[lang].get(key, f"[{key}]")


def language_keyboard() -> InlineKeyboardMarkup:
    """Language selection keyboard."""
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("English", callback_data="LANG:en"),
            InlineKeyboardButton("العربية", callback_data="LANG:ar"),
            InlineKeyboardButton("Русский", callback_data="LANG:ru"),
        ]]
    )


def _job_name(user_id: int) -> str:
    """Get job name for user."""
    return f"daily_{user_id}"


def _lang_or_prompt(prefs) -> str | None:
    """Get language from preferences."""
    if prefs and getattr(prefs, "language", None) in SUPPORTED_LANGS:
        return prefs.language
    return None


def _parse_hhmm(s: str, lang: str) -> tuple[int, int]:
    """Parse time string HH:MM."""
    m = TIME_RE.match(s.strip())
    if not m:
        raise ValueError(tr(lang, "invalid_time"))
    return int(m.group(1)), int(m.group(2))


def _main_menu_kb(lang: str) -> InlineKeyboardMarkup:
    """Main menu keyboard."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🕐 " + tr(lang, "btn_now"), callback_data="NOW"),
                InlineKeyboardButton("⚙️ " + tr(lang, "btn_settings"), callback_data="TIME"),
            ],
            [
                InlineKeyboardButton("🔔 " + tr(lang, "btn_settime"), callback_data="SETTIME"),
                InlineKeyboardButton("🌍 " + tr(lang, "btn_language"), callback_data="LANGMENU"),
            ],
            [
                InlineKeyboardButton("📝 " + tr(lang, "btn_feedback"), callback_data="FEEDBACK"),
                InlineKeyboardButton("⏹️ " + tr(lang, "btn_stop"), callback_data="STOP"),
            ],
        ]
    )


def _preset_time_kb(lang: str) -> InlineKeyboardMarkup:
    """Preset time selection keyboard."""
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


def _feedback_type_kb(lang: str) -> InlineKeyboardMarkup:
    """Feedback type selection keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🐛 Bug", callback_data="FEEDBACK_TYPE:bug")],
        [InlineKeyboardButton("💡 Feature", callback_data="FEEDBACK_TYPE:feature")],
        [InlineKeyboardButton("🎯 Suggestion", callback_data="FEEDBACK_TYPE:suggestion")],
        [InlineKeyboardButton("📝 Other", callback_data="FEEDBACK_TYPE:other")],
        [InlineKeyboardButton(tr(lang, "btn_back"), callback_data="BACK")],
    ])


def _location_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Location selection keyboard."""
    buttons = []
    for loc_code in SUPPORTED_LOCATIONS.keys():
        name = get_location_name(loc_code, lang)
        buttons.append([InlineKeyboardButton(f"📍 {name}", callback_data=f"LOC:{loc_code}")])
    
    buttons.append([InlineKeyboardButton(tr(lang, "btn_back"), callback_data="BACK")])
    return InlineKeyboardMarkup(buttons)


def _hijri_string_for_date(greg_date: dt.date, lang: str) -> str | None:
    """Convert Gregorian date to Hijri string."""
    try:
        h = Gregorian(greg_date.year, greg_date.month, greg_date.day).to_hijri()
        month_name = HIJRI_MONTHS.get(lang, HIJRI_MONTHS["en"]).get(int(h.month), str(h.month))
        return f"{int(h.day)} {month_name} {int(h.year)}"
    except Exception:
        return None


def _is_ramadan(hijri_month: int) -> bool:
    """Check if month is Ramadan."""
    return hijri_month == 9


def _get_next_prayer_countdown(payload: dict, lang: str) -> str:
    """Calculate countdown to next prayer."""
    if not payload or "prayers" not in payload:
        return ""
    
    prayers = payload.get("prayers", {})
    now = dt.datetime.now(MOSCOW_TZ)
    current_time = now.time()
    
    # Prayer times
    prayer_times = []
    for prayer_name in PRAYER_ORDER:
        if prayer_name in prayers:
            try:
                time_obj = dt.datetime.strptime(prayers[prayer_name], "%H:%M").time()
                prayer_times.append((prayer_name, time_obj))
            except:
                pass
    
    next_prayer = None
    next_time = None
    
    for prayer_name, prayer_time in prayer_times:
        if prayer_time > current_time:
            next_prayer = prayer_name
            next_time = prayer_time
            break
    
    if not next_prayer:
        return f"\n{tr(lang, 'next_prayer_tomorrow')}"
    
    # Time difference
    next_dt = dt.datetime.combine(now.date(), next_time)
    diff = next_dt - now
    hours = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60
    
    name_map = PRAYER_NAME_MAP.get(lang, PRAYER_NAME_MAP["en"])
    prayer_label = name_map.get(next_prayer, next_prayer)
    
    return f"\n{tr(lang, 'next_prayer')}: {prayer_label} in {hours}h {minutes}m"


def _format_prayer_message_enhanced(payload: dict, lang: str, quran_manager=None) -> str:
    """Enhanced prayer times message formatting."""
    if not payload or "prayers" not in payload:
        return f"❌ {escape(tr(lang, 'no_data'))}"

    prayers: dict = payload.get("prayers", {})
    date_str = payload.get("date", "")
    source_url = payload.get("source_url", "")

    pretty_date = date_str
    greg_date = None
    try:
        greg_date = dt.date.fromisoformat(date_str)
        pretty_date = greg_date.strftime("%d.%m.%Y")
    except Exception:
        greg_date = None

    hijri_str = _hijri_string_for_date(greg_date, lang) if greg_date else None
    name_map = PRAYER_NAME_MAP.get(lang, PRAYER_NAME_MAP["en"])

    lines = []
    lines.append("━" * 40)
    lines.append(f"<b>{escape(tr(lang, 'pt_header'))}</b>")
    lines.append("━" * 40)
    
    if pretty_date:
        lines.append(f"<b>{escape(tr(lang, 'date_label'))}</b> {escape(pretty_date)}")
    if hijri_str:
        lines.append(f"<b>{escape(tr(lang, 'hijri_label'))}</b> {escape(hijri_str)}")
    
    lines.append("")

    used = set()
    for key in PRAYER_ORDER:
        if key in prayers:
            emoji = PRAYER_EMOJI.get(key, "•")
            label = name_map.get(key, key)
            lines.append(f"{emoji} <b>{escape(label)}:</b> <code>{escape(prayers[key])}</code>")
            used.add(key)

    for key, val in prayers.items():
        if key not in used:
            label = name_map.get(key, key)
            lines.append(f"• <b>{escape(label)}:</b> <code>{escape(val)}</code>")

    lines.append("━" * 40)

    if source_url:
        lines.append(f"<a href='{escape(source_url)}'>{escape(tr(lang, 'source'))}</a>")

    # Add countdown
    countdown = _get_next_prayer_countdown(payload, lang)
    if countdown:
        lines.append(countdown)

    # Add Ayah
    if quran_manager:
        try:
            ayah = quran_manager.get_random_ayah()
            if ayah:
                lines.append("")
                lines.append(quran_manager.format_ayah(ayah, lang))
        except Exception:
            pass

    return "\n".join(lines)


def _load_today_or_friendly(data_file: str, lang: str) -> tuple[dict | None, str | None]:
    """Load today's prayer data or return friendly error."""
    try:
        payload = load_latest(data_file)
    except Exception:
        return None, tr(lang, "no_data")

    if not payload or not isinstance(payload, dict):
        return None, tr(lang, "no_data")

    prayers = payload.get("prayers")
    if not prayers or not isinstance(prayers, dict) or len(prayers) == 0:
        return None, tr(lang, "no_data")

    today_msk = dt.datetime.now(MOSCOW_TZ).date().isoformat()
    if payload.get("date") != today_msk:
        return None, tr(lang, "no_data")

    return payload, None


def _schedule_user(app: Application, storage: Storage, user_id: int, lang: str) -> str:
    """Schedule daily message for user."""
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


async def safe_edit_message(query, text: str, **kwargs):
    """Safely edit message, ignoring 'not modified' errors."""
    try:
        await query.edit_message_text(text, **kwargs)
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise


async def _prompt_language_start(update: Update):
    """Prompt user to choose language."""
    text = (
        "🕌 Prayer times for Moscow (MSK).\n"
        "مواقيت الصلاة لموسكو (MSK).\n"
        "Время намаза для Москвы (MSK).\n\n"
        "Choose language / اختر اللغة / Выберите язык:"
    )
    await update.message.reply_text(text, reply_markup=language_keyboard())


# ============ COMMAND HANDLERS ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command."""
    try:
        storage: Storage = context.application.bot_data.get("storage")
        data_file: str = context.application.bot_data.get("data_file")
        quran_manager = context.application.bot_data.get("quran_manager")

        if not storage or not data_file:
            await update.message.reply_text("❌ Configuration error.")
            return

        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        storage.upsert_user(user_id=user_id, chat_id=chat_id)
        prefs = storage.get_user(user_id)
        lang = _lang_or_prompt(prefs)

        if not lang:
            await _prompt_language_start(update)
            return

        payload, friendly = _load_today_or_friendly(data_file, lang)
        if friendly:
            await update.message.reply_text(
                f"{tr(lang, 'intro_short')}\n\n{friendly}",
                reply_markup=_main_menu_kb(lang),
                parse_mode="HTML",
            )
            return

        msg = _format_prayer_message_enhanced(payload, lang, quran_manager)
        combined = f"{escape(tr(lang, 'intro_short'))}\n\n{msg}"
        await update.message.reply_text(
            combined,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=_main_menu_kb(lang),
        )
    except Exception as e:
        logger.error(f"Error in start: {e}")
        await update.message.reply_text(tr("en", "error_occurred"))


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command."""
    try:
        storage: Storage = context.application.bot_data.get("storage")
        prefs = storage.get_user(update.effective_user.id) if storage else None
        lang = _lang_or_prompt(prefs) or "en"

        await update.message.reply_text(tr(lang, "help"), reply_markup=_main_menu_kb(lang))
    except Exception as e:
        logger.error(f"Error in help_cmd: {e}")
        await update.message.reply_text("❌ Error")


async def language_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Language command."""
    try:
        storage: Storage = context.application.bot_data.get("storage")
        if not storage:
            await update.message.reply_text("Configuration error")
            return

        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        storage.upsert_user(user_id=user_id, chat_id=chat_id)
        prefs = storage.get_user(user_id)
        lang = _lang_or_prompt(prefs)

        if lang:
            await update.message.reply_text(tr(lang, "choose_lang"), reply_markup=language_keyboard())
        else:
            await _prompt_language_start(update)
    except Exception as e:
        logger.error(f"Error in language_cmd: {e}")
        await update.message.reply_text("❌ Error")


async def settime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set time command."""
    try:
        storage: Storage = context.application.bot_data.get("storage")
        if not storage:
            await update.message.reply_text("Configuration error")
            return

        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        prefs = storage.get_user(user_id)
        lang = _lang_or_prompt(prefs)
        if not lang:
            await update.message.reply_text(
                "Choose language / اختر اللغة / Выберите язык:",
                reply_markup=language_keyboard(),
            )
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

        storage.set_time(user_id=user_id, chat_id=chat_id, time_hhmm=time_hhmm)
        msg = _schedule_user(context.application, storage, user_id, lang)
        await update.message.reply_text(msg, reply_markup=_main_menu_kb(lang))
    except Exception as e:
        logger.error(f"Error in settime: {e}")
        await update.message.reply_text("❌ Error")


async def time_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Settings command."""
    try:
        storage: Storage = context.application.bot_data.get("storage")
        if not storage:
            await update.message.reply_text("Configuration error")
            return

        user_id = update.effective_user.id

        prefs = storage.get_user(user_id)
        lang = _lang_or_prompt(prefs)
        if not lang:
            await update.message.reply_text(
                "Choose language / اختر اللغة / Выберите язык:",
                reply_markup=language_keyboard(),
            )
            return

        if not prefs:
            await update.message.reply_text(tr(lang, "no_settings"), reply_markup=_main_menu_kb(lang))
            return

        await update.message.reply_text(
            tr(lang, "settings").format(
                enabled="✅ Enabled" if prefs.enabled else "❌ Disabled",
                time=(prefs.time_hhmm or "(not set)"),
                location=get_location_name(prefs.location or "moscow", lang),
            ),
            reply_markup=_main_menu_kb(lang),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Error in time_cmd: {e}")
        await update.message.reply_text("❌ Error")


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop command."""
    try:
        storage: Storage = context.application.bot_data.get("storage")
        if not storage:
            await update.message.reply_text("Configuration error")
            return

        user_id = update.effective_user.id

        prefs = storage.get_user(user_id)
        lang = _lang_or_prompt(prefs) or "en"

        storage.set_enabled(user_id, False)
        for job in context.application.job_queue.get_jobs_by_name(_job_name(user_id)):
            job.schedule_removal()

        await update.message.reply_text(tr(lang, "disabled"), reply_markup=_main_menu_kb(lang))
    except Exception as e:
        logger.error(f"Error in stop: {e}")
        await update.message.reply_text("❌ Error")


async def now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Now command - show prayer times."""
    try:
        storage: Storage = context.application.bot_data.get("storage")
        data_file: str = context.application.bot_data.get("data_file")
        quran_manager = context.application.bot_data.get("quran_manager")
        cache: CacheManager = context.application.bot_data.get("cache")

        if not storage or not data_file:
            await update.message.reply_text("Configuration error")
            return

        prefs = storage.get_user(update.effective_user.id)
        lang = _lang_or_prompt(prefs)
        if not lang:
            await update.message.reply_text(
                "Choose language / اختر اللغة / Выберите язык:",
                reply_markup=language_keyboard(),
            )
            return

        cache_key = f"prayer_msg_{lang}"
        msg = cache.get(cache_key) if cache else None

        if not msg:
            payload, friendly = _load_today_or_friendly(data_file, lang)
            if friendly:
                await update.message.reply_text(friendly, reply_markup=_main_menu_kb(lang))
                return

            msg = _format_prayer_message_enhanced(payload, lang, quran_manager)

            if cache:
                cache.set(cache_key, msg, ttl_seconds=CACHE_PRAYERS_MINUTES * 60)

        await update.message.reply_text(
            msg,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=_main_menu_kb(lang),
        )
    except Exception as e:
        logger.error(f"Error in now: {e}")
        await update.message.reply_text(tr("en", "error_occurred"))


async def feedback_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Feedback command."""
    try:
        storage: Storage = context.application.bot_data.get("storage")
        if not storage:
            await update.message.reply_text("Configuration error")
            return

        user_id = update.effective_user.id
        prefs = storage.get_user(user_id)
        lang = _lang_or_prompt(prefs) or "en"

        context.user_data["feedback_step"] = "select_type"

        await update.message.reply_text(
            tr(lang, "feedback_prompt"),
            reply_markup=_feedback_type_kb(lang),
        )
    except Exception as e:
        logger.error(f"Error in feedback_cmd: {e}")
        await update.message.reply_text("❌ Error")


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stats command."""
    try:
        storage: Storage = context.application.bot_data.get("storage")
        feedback_manager: FeedbackManager = context.application.bot_data.get("feedback_manager")
        habit_tracker: HabitTracker = context.application.bot_data.get("habit_tracker")

        if not storage:
            await update.message.reply_text("Configuration error")
            return

        user_id = update.effective_user.id
        prefs = storage.get_user(user_id)
        lang = _lang_or_prompt(prefs) or "en"

        # Calculate days active
        days_active = 0
        if prefs and prefs.created_at:
            created = dt.datetime.fromisoformat(prefs.created_at)
            days_active = (dt.datetime.now() - created).days

        # Count user's feedback
        all_feedback = feedback_manager.get_all_feedback(limit=1000)
        user_feedback = [f for f in all_feedback if f.user_id == user_id]

        # Get streak
        streak = habit_tracker.get_streak(user_id)

        msg = tr(lang, "stats_title") + "\n\n"
        msg += f"{tr(lang, 'days_active')}: {days_active}\n"
        msg += f"{tr(lang, 'feedback_sent')}: {len(user_feedback)}\n"
        msg += f"{tr(lang, 'prayer_streak')}: {streak}\n"

        await update.message.reply_text(msg, reply_markup=_main_menu_kb(lang), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in stats_cmd: {e}")
        await update.message.reply_text("❌ Error")


async def admin_dashboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin dashboard command."""
    try:
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Unauthorized")
            return
        
        storage: Storage = context.application.bot_data.get("storage")
        feedback_manager: FeedbackManager = context.application.bot_data.get("feedback_manager")
        
        stats = storage.get_stats()
        feedback_stats = feedback_manager.get_stats()
        
        msg = """
<b>📊 Admin Dashboard</b>

<b>👥 Users:</b>
  • Total: {total}
  • Active: {active}
  • Activity Rate: {rate}%

<b>🗣️ Languages:</b>
""".format(
            total=stats['total_users'],
            active=stats['active_users'],
            rate=round(stats['active_users']/max(stats['total_users'], 1)*100, 1)
        )
        
        for lang_code, count in stats['by_language'].items():
            msg += f"\n  • {lang_code}: {count}"
        
        msg += f"""

<b>📍 Locations:</b>
"""
        for loc, count in stats['by_location'].items():
            msg += f"\n  • {get_location_name(loc, 'en')}: {count}"
        
        msg += f"""

<b>📝 Feedback:</b>
  • Total: {total_fb}
""".format(total_fb=feedback_stats['total'])
        
        for ftype, count in feedback_stats['by_type'].items():
            msg += f"\n  • {ftype}: {count}"
        
        msg += f"""

<b>Status:</b>
  • {new_fb} new feedback
  • {read_fb} read
  • {resolved_fb} resolved
""".format(
            new_fb=feedback_stats['by_status'].get('new', 0),
            read_fb=feedback_stats['by_status'].get('read', 0),
            resolved_fb=feedback_stats['by_status'].get('resolved', 0)
        )
        
        await update.message.reply_text(msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in admin_dashboard_cmd: {e}")
        await update.message.reply_text("❌ Error")


async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast command."""
    try:
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Unauthorized")
            return

        if not context.args:
            await update.message.reply_text("Usage: /broadcast <message>")
            return

        storage: Storage = context.application.bot_data.get("storage")
        if not storage:
            await update.message.reply_text("Configuration error")
            return

        message = " ".join(context.args)

        # Schedule broadcast
        context.application.create_task(
            execute_broadcast(context, message, update.effective_user.id)
        )

        await update.message.reply_text(
            f"📢 Broadcasting message to all users...\n\nMessage: {message}"
        )
    except Exception as e:
        logger.error(f"Error in broadcast_cmd: {e}")
        await update.message.reply_text("❌ Error")


async def execute_broadcast(context: ContextTypes.DEFAULT_TYPE, message: str, admin_id: int):
    """Execute broadcast."""
    try:
        storage: Storage = context.application.bot_data.get("storage")
        if not storage:
            return

        sent_count = 0
        failed_count = 0
        total = 0

        for prefs in storage.list_enabled_users():
            total += 1
            try:
                broadcast_msg = tr(prefs.language or "en", "broadcast_received").format(message=message)
                await context.bot.send_message(
                    chat_id=prefs.chat_id,
                    text=broadcast_msg,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send broadcast to {prefs.user_id}: {e}")
                failed_count += 1

            if total % 10 == 0:
                progress = (total / max(len(list(storage.list_enabled_users())), 1)) * 100
                logger.info(f"Broadcast progress: {progress:.0f}%")

            await asyncio.sleep(BATCH_SEND_DELAY)

        # Notify admin
        summary = f"✅ Broadcast complete!\n✓ Sent: {sent_count}\n✗ Failed: {failed_count}"
        try:
            await context.bot.send_message(chat_id=admin_id, text=summary)
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Error in execute_broadcast: {e}")


async def handle_feedback_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle feedback message."""
    try:
        storage: Storage = context.application.bot_data.get("storage")
        feedback_manager: FeedbackManager = context.application.bot_data.get("feedback_manager")

        if not storage or not feedback_manager:
            await update.message.reply_text("Configuration error")
            return

        user_id = update.effective_user.id
        prefs = storage.get_user(user_id)
        lang = _lang_or_prompt(prefs) or "en"

        feedback_type = context.user_data.get("feedback_type", "other")
        message = update.message.text

        # Save feedback
        feedback_manager.add_feedback(
            user_id=user_id,
            username=update.effective_user.username,
            message=message,
            feedback_type=feedback_type,
        )

        # Clear state
        context.user_data.pop("feedback_step", None)
        context.user_data.pop("feedback_type", None)

        await update.message.reply_text(
            tr(lang, "feedback_thanks"),
            reply_markup=_main_menu_kb(lang),
        )
    except Exception as e:
        logger.error(f"Error in handle_feedback_message: {e}")
        await update.message.reply_text("❌ Error")


# ============ JOB HANDLERS ============

async def send_daily(context: ContextTypes.DEFAULT_TYPE):
    """Daily job - send prayer times."""
    try:
        storage: Storage = context.application.bot_data.get("storage")
        data_file: str = context.application.bot_data.get("data_file")
        quran_manager = context.application.bot_data.get("quran_manager")
        cache: CacheManager = context.application.bot_data.get("cache")
        notification_manager: NotificationManager = context.application.bot_data.get("notification_manager")

        if not storage or not data_file:
            return

        user_id = context.job.data["user_id"]
        prefs = storage.get_user(user_id)
        if not prefs or not prefs.enabled:
            return

        # Check notification settings
        if notification_manager:
            notif_settings = notification_manager.get_settings(user_id)
            if not notif_settings.enable_prayer_times:
                return

        lang = getattr(prefs, "language", None) or "en"

        # Try cache
        cache_key = f"prayer_msg_{lang}"
        msg = cache.get(cache_key) if cache else None

        if not msg:
            payload, friendly = _load_today_or_friendly(data_file, lang)
            if friendly:
                await context.bot.send_message(chat_id=prefs.chat_id, text=friendly)
                return

            msg = _format_prayer_message_enhanced(payload, lang, quran_manager)

            if cache:
                cache.set(cache_key, msg, ttl_seconds=CACHE_PRAYERS_MINUTES * 60)

        await context.bot.send_message(
            chat_id=prefs.chat_id,
            text=msg,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(f"Error in send_daily: {e}")


async def friday_reminder_job(context: ContextTypes.DEFAULT_TYPE):
    """Friday reminder - Surah Al-Kahf."""
    try:
        storage: Storage = context.application.bot_data.get("storage")
        notification_manager: NotificationManager = context.application.bot_data.get("notification_manager")

        if not storage:
            return

        for prefs in storage.list_enabled_users():
            lang = getattr(prefs, "language", None) or "en"
            
            # Check notification settings
            if notification_manager:
                notif_settings = notification_manager.get_settings(prefs.user_id)
                if not notif_settings.enable_friday_reminder:
                    continue
            
            try:
                await context.bot.send_message(
                    chat_id=prefs.chat_id,
                    text=tr(lang, "friday_reminder"),
                )
                await asyncio.sleep(BATCH_SEND_DELAY)
            except Exception as e:
                logger.error(f"Error sending Friday reminder to {prefs.user_id}: {e}")
    except Exception as e:
        logger.error(f"Error in friday_reminder_job: {e}")


async def db_maintenance_job(context: ContextTypes.DEFAULT_TYPE):
    """Database maintenance."""
    try:
        storage: Storage = context.application.bot_data.get("storage")
        feedback_manager: FeedbackManager = context.application.bot_data.get("feedback_manager")
        
        # Cleanup inactive users
        storage.cleanup_inactive_users(days=DB_CLEANUP_DAYS)
        
        # Cleanup old feedback
        feedback_manager.delete_old_feedback(days=180)
        
        logger.info("✅ Database maintenance completed")
    except Exception as e:
        logger.error(f"Error in db_maintenance_job: {e}")


# ============ BUTTON HANDLERS ============

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks."""
    try:
        query = update.callback_query
        await query.answer()

        storage: Storage = context.application.bot_data.get("storage")
        data_file: str = context.application.bot_data.get("data_file")
        quran_manager = context.application.bot_data.get("quran_manager")
        cache: CacheManager = context.application.bot_data.get("cache")

        if not storage or not data_file:
            await safe_edit_message(query, "Configuration error")
            return

        user_id = query.from_user.id
        chat_id = query.message.chat_id
        data = query.data

        # Feedback type selection
        if data.startswith("FEEDBACK_TYPE:"):
            feedback_type = data.split(":", 1)[1].strip()
            context.user_data["feedback_step"] = "enter_message"
            context.user_data["feedback_type"] = feedback_type

            prefs = storage.get_user(user_id)
            lang = _lang_or_prompt(prefs) or "en"

            await query.delete_message()
            await query.from_user.send_message(
                f"Please send your {feedback_type} feedback message:"
            )
            return

        # Location selection
        if data.startswith("LOC:"):
            location = data.split(":", 1)[1].strip()
            if location not in SUPPORTED_LOCATIONS:
                location = "moscow"
            
            storage.set_location(user_id, location)
            
            prefs = storage.get_user(user_id)
            lang = _lang_or_prompt(prefs) or "en"
            location_name = get_location_name(location, lang)
            
            await safe_edit_message(
                query,
                tr(lang, "location_changed").format(location=location_name),
                reply_markup=_main_menu_kb(lang)
            )
            return

        if data == "LANGMENU":
            prefs = storage.get_user(user_id)
            lang = _lang_or_prompt(prefs) or "en"
            await safe_edit_message(query, tr(lang, "choose_lang"), reply_markup=language_keyboard())
            return

        # Language selection
        if data.startswith("LANG:"):
            lang = data.split(":", 1)[1].strip()
            if lang not in SUPPORTED_LANGS:
                lang = "en"

            storage.set_language(user_id=user_id, chat_id=chat_id, language=lang)

            payload, friendly = _load_today_or_friendly(data_file, lang)
            if friendly:
                combined = f"{escape(tr(lang, 'intro_short'))}\n\n{escape(friendly)}"
                await safe_edit_message(query, combined, reply_markup=_main_menu_kb(lang))
                return

            msg = _format_prayer_message_enhanced(payload, lang, quran_manager)
            combined = f"{escape(tr(lang, 'intro_short'))}\n\n{msg}"
            await safe_edit_message(
                query,
                combined,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=_main_menu_kb(lang),
            )
            return

        prefs = storage.get_user(user_id)
        lang = _lang_or_prompt(prefs)
        if not lang:
            text = (
                "Prayer times for Moscow (MSK).\n"
                "مواقيت الصلاة لموسكو (MSK).\n"
                "Время намаза для Москвы (MSK).\n\n"
                "Choose language / اختر اللغة / Выберите язык:"
            )
            await safe_edit_message(query, text, reply_markup=language_keyboard())
            return

        if data == "BACK":
            await safe_edit_message(query, tr(lang, "menu_prompt"), reply_markup=_main_menu_kb(lang))
            return

        if data == "SETTIME":
            await safe_edit_message(query, tr(lang, "settime_pick"), reply_markup=_preset_time_kb(lang))
            return

        if data == "FEEDBACK":
            context.user_data["feedback_step"] = "select_type"
            await safe_edit_message(query, tr(lang, "feedback_prompt"), reply_markup=_feedback_type_kb(lang))
            return

        if data == "TIME":
            prefs = storage.get_user(user_id)
            txt = tr(lang, "settings").format(
                enabled="✅ Enabled" if (prefs and prefs.enabled) else "❌ Disabled",
                time=(prefs.time_hhmm if prefs and prefs.time_hhmm else "(not set)"),
                location=get_location_name(prefs.location if prefs else "moscow", lang),
            )
            await safe_edit_message(query, txt, reply_markup=_main_menu_kb(lang), parse_mode="HTML")
            return

        if data == "STOP":
            storage.set_enabled(user_id, False)
            for job in context.application.job_queue.get_jobs_by_name(_job_name(user_id)):
                job.schedule_removal()
            await safe_edit_message(query, tr(lang, "disabled"), reply_markup=_main_menu_kb(lang))
            return

        if data == "NOW":
            cache_key = f"prayer_msg_{lang}"
            msg = cache.get(cache_key) if cache else None

            if not msg:
                payload, friendly = _load_today_or_friendly(data_file, lang)
                if friendly:
                    await safe_edit_message(query, friendly, reply_markup=_main_menu_kb(lang))
                    return

                msg = _format_prayer_message_enhanced(payload, lang, quran_manager)

                if cache:
                    cache.set(cache_key, msg, ttl_seconds=CACHE_PRAYERS_MINUTES * 60)

            await safe_edit_message(
                query,
                msg,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=_main_menu_kb(lang),
            )
            return

        if data.startswith("PRESET:"):
            time_hhmm = data.split(":", 1)[1].strip()
            try:
                _parse_hhmm(time_hhmm, lang)
            except ValueError:
                await safe_edit_message(query, tr(lang, "invalid_preset"), reply_markup=_preset_time_kb(lang))
                return

            storage.upsert_user(user_id=user_id, chat_id=chat_id)
            storage.set_time(user_id=user_id, chat_id=chat_id, time_hhmm=time_hhmm)

            msg = _schedule_user(context.application, storage, user_id, lang)
            await safe_edit_message(query, msg, reply_markup=_main_menu_kb(lang))
            return
    except Exception as e:
        logger.error(f"Error in on_button: {e}")


# ============ MAIN FUNCTION ============

def main():
    """Main function."""
    load_dotenv()

    token = TELEGRAM_BOT_TOKEN
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set.")

    # Initialize managers
    storage = Storage(DB_FILE)
    quran_manager = QuranManager(QURAN_CSV_FILE, max_ayahs=CACHE_QURAN_COUNT)
    cache = CacheManager()
    feedback_manager = FeedbackManager(DB_FILE)
    notification_manager = NotificationManager(DB_FILE)
    habit_tracker = HabitTracker(DB_FILE)
    monitor = SystemMonitor(storage, cache)

    # Log startup
    stats = storage.get_stats()
    logger.info(f"Starting Prayer Times Bot v2.0")
    logger.info(f"Loaded {stats['total_users']} total users, {stats['active_users']} active")

    # Create application
    app = Application.builder().token(token).build()
    app.bot_data["storage"] = storage
    app.bot_data["data_file"] = DATA_FILE
    app.bot_data["quran_manager"] = quran_manager
    app.bot_data["cache"] = cache
    app.bot_data["feedback_manager"] = feedback_manager
    app.bot_data["notification_manager"] = notification_manager
    app.bot_data["habit_tracker"] = habit_tracker
    app.bot_data["monitor"] = monitor

    # Command handlers
    app.add_handler(CommandHandler(["start"], start))
    app.add_handler(CommandHandler(["help", "Help"], help_cmd))
    app.add_handler(CommandHandler(["language", "Language"], language_cmd))
    app.add_handler(CommandHandler(["settime", "SetTime"], settime))
    app.add_handler(CommandHandler(["time", "Time"], time_cmd))
    app.add_handler(CommandHandler(["now", "Now"], now))
    app.add_handler(CommandHandler(["stop", "Stop"], stop))
    app.add_handler(CommandHandler(["feedback", "Feedback"], feedback_cmd))
    app.add_handler(CommandHandler(["stats", "Stats"], stats_cmd))
    app.add_handler(CommandHandler(["admin"], admin_dashboard_cmd))
    app.add_handler(CommandHandler(["broadcast"], broadcast_cmd))

    # Message handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_feedback_message))

    # Button handler
    app.add_handler(CallbackQueryHandler(on_button))

    # Schedule jobs
    for prefs in storage.list_enabled_users():
        if prefs.time_hhmm:
            try:
                lang = getattr(prefs, "language", None) or "en"
                _schedule_user(app, storage, prefs.user_id, lang)
            except Exception as e:
                logger.error(f"Error scheduling user {prefs.user_id}: {e}")

    # Friday reminder (Friday is 4 in Python's weekday)
    app.job_queue.run_daily(
        friday_reminder_job,
        time=dt.time(hour=8, minute=0, tzinfo=MOSCOW_TZ),
        days=(4,),
        name="friday_reminder",
    )

    # Database maintenance (daily at 2 AM)
    app.job_queue.run_daily(
        db_maintenance_job,
        time=dt.time(hour=2, minute=0, tzinfo=MOSCOW_TZ),
        name="db_maintenance",
    )

    logger.info("=" * 60)
    logger.info("🤖 Prayer Times Bot v2.0")
    logger.info("=" * 60)
    logger.info("✅ Features enabled:")
    logger.info("  • 🕌 Prayer Times with Hijri Calendar")
    logger.info("  • 📖 Daily Quranic Verses")
    logger.info("  • 🔔 Friday Reminders (Surah Al-Kahf)")
    logger.info("  • 💬 User Feedback System")
    logger.info("  • 📢 Admin Broadcast")
    logger.info("  • 📊 Statistics & Analytics")
    logger.info("  • 🌍 Multi-Language Support (EN/AR/RU)")
    logger.info("  • 📍 Multiple Locations")
    logger.info("  • 🔥 Prayer Habit Tracking")
    logger.info("  • 🎨 Rich Message Formatting")
    logger.info("=" * 60)
    logger.info("✨ Starting polling...\n")

    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()