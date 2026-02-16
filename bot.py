import os
import sys
import logging
import sqlite3
import asyncio
import threading
import time
import json
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, List, Dict, Any, Tuple
from calendar import monthrange

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
from telegram.constants import ParseMode

# Flask uchun
from flask import Flask, request, jsonify
import threading

# ==================== KONFIGURATSIYA ====================
BOT_TOKEN = os.environ.get('BOT_TOKEN', "8250421622:AAHpa6q_RMV1d3QNO4tM3YtT9h2jYJebvjw")
ADMIN_IDS = [int(id.strip()) for id in os.environ.get('ADMIN_IDS', "8014950410").split(',')]
TIMEZONE = ZoneInfo("Asia/Tashkent")

# Render uchun ma'lumotlar bazasi fayli
DB_NAME = 'data/smart_assistant.db'

# Data papkasini yaratish
os.makedirs('data', exist_ok=True)

# Conversation states
(LANG_SELECT, MAIN_MENU, 
 REMINDER_MENU, ADD_REMINDER_NAME, ADD_REMINDER_TYPE, ADD_REMINDER_DAYS, ADD_REMINDER_DATE, ADD_REMINDER_TIME, ADD_REMINDER_DESC, DELETE_REMINDER,
 EXPENSE_MENU, ADD_EXPENSE_AMOUNT, ADD_EXPENSE_CAT, ADD_EXPENSE_DESC,
 INCOME_MENU, ADD_INCOME_AMOUNT, ADD_INCOME_CAT, ADD_INCOME_DESC,
 DEBTS_MENU, ADD_DEBT_NAME, ADD_DEBT_AMOUNT, ADD_DEBT_TYPE, ADD_DEBT_DESC, CLOSE_DEBT,
 REPORT_MENU,
 BUDGET_MENU, BUDGET_ADD_CAT, BUDGET_ADD_LIMIT, BUDGET_EDIT,
 SETTINGS_MENU, SETTINGS_CURRENCY, SETTINGS_TIME, SETTINGS_THRESHOLD, SETTINGS_LANG, SETTINGS_THEME,
 ADMIN_MENU, ADMIN_SEARCH, ADMIN_VIEW, ADMIN_BROADCAST, ADMIN_BLOCK) = range(40)

# ==================== LOG ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('data/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== TILLAR ====================
LANGUAGES = {
    'uz': {
        'name': '🇺🇿 O\'zbek',
        'currency': 'UZS',
        'currency_symbol': 'so\'m',
        'welcome': "Assalomu alaykum, {name}! Smart Assistant botiga xush kelibsiz!",
        'select_lang': "Iltimos, tilni tanlang:",
        'main_menu': "🏠 Asosiy menyu",
        'reminder': "🔔 Eslatma",
        'reminder_list': "📋 Eslatmalarim",
        'reminder_add': "➕ Yangi eslatma",
        'reminder_delete': "🗑️ O'chirish",
        'expense': "💰 Xarajat",
        'expense_add': "➕ Yangi xarajat",
        'expense_list': "📊 Xarajatlarim",
        'expense_stats': "📈 Statistika",
        'expense_trends': "📉 Trendlar",
        'income': "💵 Daromad",
        'income_add': "➕ Yangi daromad",
        'income_list': "📊 Daromadlarim",
        'debts': "💸 Qarzlar",
        'debts_add': "➕ Yangi qarz",
        'debts_list': "📋 Barcha qarzlar",
        'debts_close': "✅ Qarzni yopish",
        'report': "📊 Hisobot",
        'budget': "🎯 Byudjet",
        'budget_status': "📊 Byudjet holati",
        'budget_add': "➕ Limit qo'shish",
        'budget_edit': "✏️ Limit o'zgartirish",
        'budget_delete': "🗑️ Limit o'chirish",
        'budget_stats': "📈 Statistika",
        'budget_alert': "⚙️ Ogohlantirish",
        'settings': "⚙️ Sozlamalar",
        'help': "🆘 Yordam",
        'back': "🔙 Orqaga",
        'cancel': "❌ Bekor qilish",
        'confirm': "✅ Tasdiqlash",
        'yes': "Ha",
        'no': "Yo'q",
        'error': "❌ Xatolik yuz berdi",
        'invalid_input': "❌ Noto'g'ri format",
        'not_found': "❌ Ma'lumot topilmadi",
        'success': "✅ Muvaffaqiyatli",
        'today': "📅 Bugun",
        'daily': "🔄 Har kuni",
        'weekly': "📆 Haftalik",
        'monthly': "📅 Oylik",
        'custom': "📆 Tanlangan kunlar",
        'other_date': "📅 Boshqa sana",
        'amount': "💰 Miqdor",
        'category': "🏷️ Kategoriya",
        'description': "📝 Tavsif",
        'time': "⏰ Vaqt",
        'date': "📅 Sana",
        'person': "👤 Shaxs",
        'gave': "📤 Berdim",
        'took': "📥 Oldim",
        'budget_warning': "Byudjet ogohlantirishi",
        'limit_reached': "Limitga yetdingiz",
        'limit_exceeded': "Limit oshib ketdi",
        'over_by': "Oshgan miqdor",
        # Settings
        'currency_set': "💱 Pul birligi",
        'reminder_time': "🔔 Eslatma vaqti",
        'budget_threshold': "💰 Byudjet chegarasi",
        'language': "🌐 Til",
        'theme': "🎨 Mavzu",
        'profile': "ℹ️ Profil",
        'light_theme': "☀️ Yorug'",
        'dark_theme': "🌙 Qorong'i",
        # Weekdays
        'monday': "Dushanba",
        'tuesday': "Seshanba",
        'wednesday': "Chorshanba",
        'thursday': "Payshanba",
        'friday': "Juma",
        'saturday': "Shanba",
        'sunday': "Yakshanba",
        'mon': "Du",
        'tue': "Se",
        'wed': "Ch",
        'thu': "Pa",
        'fri': "Ju",
        'sat': "Sha",
        'sun': "Ya",
        # Months
        'january': "Yanvar",
        'february': "Fevral",
        'march': "Mart",
        'april': "Aprel",
        'may': "May",
        'june': "Iyun",
        'july': "Iyul",
        'august': "Avgust",
        'september': "Sentabr",
        'october': "Oktabr",
        'november': "Noyabr",
        'december': "Dekabr",
        # Additional texts
        'title': "Nomi",
        'repeat_type': "Takrorlash turi",
        'select_days': "Kunlarni tanlang",
        'select_date': "Sanani tanlang",
        'enter_date': "Sanani kiriting (DD.MM.YYYY)",
        'invalid_date': "❌ Noto'g'ri sana formati",
        'invalid_time': "❌ Noto'g'ri vaqt formati (HH:MM)",
        'or_skip': "O'tkazib yuborish uchun 'no' yozing",
        'select_at_least_one': "Kamida bitta kun tanlang!",
        'reminder_saved': "Eslatma saqlandi",
        'no_reminders': "Eslatmalar yo'q",
        'your_reminders': "Sizning eslatmalaringiz",
        'one_time': "Bir martalik",
        'delete_reminder': "Eslatmani o'chirish",
        'enter_id': "ID sini kiriting",
        'reminder_deleted': "Eslatma o'chirildi",
        'amount_example': "Masalan: 50000, 1.5M, 200k",
        'expense_saved': "Xarajat saqlandi",
        'no_expenses': "Xarajatlar yo'q",
        'income_saved': "Daromad saqlandi",
        'no_income': "Daromadlar yo'q",
        'debt_saved': "Qarz saqlandi",
        'no_debts': "Qarzlar yo'q",
        'total_gave': "Bergan qarz",
        'total_took': "Olgan qarz",
        'balance': "Balans",
        'enter_debt_id': "Qarz ID sini kiriting",
        'debt_closed': "Qarz yopildi",
        'loss': "Zarar",
        'expense_analysis': "Xarajat tahlili",
        'advice': "Maslahat",
        'advice_saving': "Tejashni davom ettiring!",
        'advice_budget': "Byudjetingizni qayta ko'rib chiqing",
        'advice_plan': "Moliyaviy reja tuzing",
        'no_budgets': "Limit o'rnatilmagan",
        'total_limit': "Jami limit",
        'spent': "Sarflangan",
        'remaining': "Qolgan",
        'alerts': "Ogohlantirishlar",
        'exceeded': "ta limit oshgan",
        'threshold_reached': "chegaraga yetgan",
        'select_category': "Kategoriyani tanlang",
        'enter_category': "Kategoriya nomini kiriting",
        'enter_limit': "Limit miqdorini kiriting",
        'budget_saved': "Byudjet saqlandi",
        'alert_at': "Ogohlantirish",
        'no_budgets_to_edit': "O'zgartirish uchun limit yo'q",
        'enter_new_limit': "Yangi limitni kiriting",
        'no_budgets_to_delete': "O'chirish uchun limit yo'q",
        'budget_deleted': "Limit o'chirildi",
        'current_threshold': "Joriy chegara",
        'select_new_threshold': "Yangi chegarani tanlang",
        'name': "Ism",
        'registered': "Ro'yxatdan o'tgan",
        'statistics': "Statistika",
        'how_to_use': "Qanday ishlatish",
        'quick_add': "Tez qo'shish",
        'categories': "Kategoriyalar",
        'by_source': "Manba bo'yicha",
        'monthly_report': "Oylik hisobot",
        'gave_and_took': "Bergan va olgan qarzlar",
        'close_debt': "Qarzni yopish",
        'category_limits': "Kategoriya limitlari",
        'progress_bar': "Progress bar",
        'monthly_summary': "Oylik xulosa",
        'category_analysis': "Kategoriya tahlili",
        'trends': "Trendlar",
        'problems': "Muammo bo'lsa",
        'restart_bot': "Botni qayta ishga tushirish",
        'users': "Foydalanuvchilar",
        'total': "Jami",
        'active_week': "Faol (7 kun)",
        'blocked': "Bloklangan",
        'admins': "Adminlar",
        'activity': "Faollik",
        'finance': "Moliya",
        'total_income': "Jami daromad",
        'total_expense': "Jami xarajat",
        'status': "Holat",
        'working': "Ishlayapti",
        'last_10': "Oxirgi 10",
    },
    'ru': {
        'name': '🇷🇺 Русский',
        'currency': 'RUB',
        'currency_symbol': '₽',
        'welcome': "Здравствуйте, {name}! Добро пожаловать в Smart Assistant!",
        'select_lang': "Пожалуйста, выберите язык:",
        'main_menu': "🏠 Главное меню",
        'reminder': "🔔 Напоминание",
        'reminder_list': "📋 Мои напоминания",
        'reminder_add': "➕ Новое напоминание",
        'reminder_delete': "🗑️ Удалить",
        'expense': "💰 Расход",
        'expense_add': "➕ Новый расход",
        'expense_list': "📊 Мои расходы",
        'expense_stats': "📈 Статистика",
        'expense_trends': "📉 Тренды",
        'income': "💵 Доход",
        'income_add': "➕ Новый доход",
        'income_list': "📊 Мои доходы",
        'debts': "💸 Долги",
        'debts_add': "➕ Новый долг",
        'debts_list': "📋 Все долги",
        'debts_close': "✅ Закрыть долг",
        'report': "📊 Отчет",
        'budget': "🎯 Бюджет",
        'budget_status': "📊 Состояние бюджета",
        'budget_add': "➕ Добавить лимит",
        'budget_edit': "✏️ Изменить лимит",
        'budget_delete': "🗑️ Удалить лимит",
        'budget_stats': "📈 Статистика",
        'budget_alert': "⚙️ Предупреждение",
        'settings': "⚙️ Настройки",
        'help': "🆘 Помощь",
        'back': "🔙 Назад",
        'cancel': "❌ Отмена",
        'confirm': "✅ Подтвердить",
        'yes': "Да",
        'no': "Нет",
        'error': "❌ Ошибка",
        'invalid_input': "❌ Неверный формат",
        'not_found': "❌ Не найдено",
        'success': "✅ Успешно",
        'today': "📅 Сегодня",
        'daily': "🔄 Ежедневно",
        'weekly': "📆 Еженедельно",
        'monthly': "📅 Ежемесячно",
        'custom': "📆 Выбранные дни",
        'other_date': "📅 Другая дата",
        'amount': "💰 Сумма",
        'category': "🏷️ Категория",
        'description': "📝 Описание",
        'time': "⏰ Время",
        'date': "📅 Дата",
        'person': "👤 Человек",
        'gave': "📤 Дал",
        'took': "📥 Взял",
        # Settings
        'currency_set': "💱 Валюта",
        'reminder_time': "🔔 Время напоминания",
        'budget_threshold': "💰 Порог бюджета",
        'language': "🌐 Язык",
        'theme': "🎨 Тема",
        'profile': "ℹ️ Профиль",
        'light_theme': "☀️ Светлая",
        'dark_theme': "🌙 Темная",
        # Weekdays
        'monday': "Понедельник",
        'tuesday': "Вторник",
        'wednesday': "Среда",
        'thursday': "Четверг",
        'friday': "Пятница",
        'saturday': "Суббота",
        'sunday': "Воскресенье",
        'mon': "Пн",
        'tue': "Вт",
        'wed': "Ср",
        'thu': "Чт",
        'fri': "Пт",
        'sat': "Сб",
        'sun': "Вс",
        # Months
        'january': "Январь",
        'february': "Февраль",
        'march': "Март",
        'april': "Апрель",
        'may': "Май",
        'june': "Июнь",
        'july': "Июль",
        'august': "Август",
        'september': "Сентябрь",
        'october': "Октябрь",
        'november': "Ноябрь",
        'december': "Декабрь",
        # Additional texts (same pattern as uz)
        'title': "Название",
        'repeat_type': "Тип повторения",
        'select_days': "Выберите дни",
        'select_date': "Выберите дату",
        'enter_date': "Введите дату (ДД.ММ.ГГГГ)",
        'invalid_date': "❌ Неверный формат даты",
        'invalid_time': "❌ Неверный формат времени (ЧЧ:ММ)",
        'or_skip': "Напишите 'нет' чтобы пропустить",
        'select_at_least_one': "Выберите хотя бы один день!",
        'reminder_saved': "Напоминание сохранено",
        'no_reminders': "Нет напоминаний",
        'your_reminders': "Ваши напоминания",
        'one_time': "Одноразовое",
        'delete_reminder': "Удалить напоминание",
        'enter_id': "Введите ID",
        'reminder_deleted': "Напоминание удалено",
        'amount_example': "Например: 50000, 1.5M, 200k",
        'expense_saved': "Расход сохранен",
        'no_expenses': "Нет расходов",
        'income_saved': "Доход сохранен",
        'no_income': "Нет доходов",
        'debt_saved': "Долг сохранен",
        'no_debts': "Нет долгов",
        'total_gave': "Дал в долг",
        'total_took': "Взял в долг",
        'balance': "Баланс",
        'enter_debt_id': "Введите ID долга",
        'debt_closed': "Долг закрыт",
        'loss': "Убыток",
        'expense_analysis': "Анализ расходов",
        'advice': "Совет",
        'advice_saving': "Продолжайте экономить!",
        'advice_budget': "Пересмотрите бюджет",
        'advice_plan': "Составьте финансовый план",
        'no_budgets': "Лимиты не установлены",
        'total_limit': "Общий лимит",
        'spent': "Потрачено",
        'remaining': "Осталось",
        'alerts': "Предупреждения",
        'exceeded': "превышено",
        'threshold_reached': "достигло порога",
        'select_category': "Выберите категорию",
        'enter_category': "Введите название категории",
        'enter_limit': "Введите сумму лимита",
        'budget_saved': "Бюджет сохранен",
        'alert_at': "Предупреждение при",
        'no_budgets_to_edit': "Нет лимитов для изменения",
        'enter_new_limit': "Введите новый лимит",
        'no_budgets_to_delete': "Нет лимитов для удаления",
        'budget_deleted': "Лимит удален",
        'current_threshold': "Текущий порог",
        'select_new_threshold': "Выберите новый порог",
        'name': "Имя",
        'registered': "Зарегистрирован",
        'statistics': "Статистика",
        'how_to_use': "Как использовать",
        'quick_add': "Быстрое добавление",
        'categories': "Категории",
        'by_source': "По источникам",
        'monthly_report': "Месячный отчет",
        'gave_and_took': "Дал и взял",
        'close_debt': "Закрыть долг",
        'category_limits': "Лимиты категорий",
        'progress_bar': "Прогресс бар",
        'monthly_summary': "Месячный итог",
        'category_analysis': "Анализ категорий",
        'trends': "Тренды",
        'problems': "Проблемы",
        'restart_bot': "Перезапустить бота",
        'users': "Пользователи",
        'total': "Всего",
        'active_week': "Активные (7 дней)",
        'blocked': "Заблокировано",
        'admins': "Админы",
        'activity': "Активность",
        'finance': "Финансы",
        'total_income': "Общий доход",
        'total_expense': "Общий расход",
        'status': "Статус",
        'working': "Работает",
        'last_10': "Последние 10",
    },
    'en': {
        'name': '🇬🇧 English',
        'currency': 'USD',
        'currency_symbol': '$',
        'welcome': "Hello, {name}! Welcome to Smart Assistant!",
        'select_lang': "Please select language:",
        'main_menu': "🏠 Main menu",
        'reminder': "🔔 Reminder",
        'reminder_list': "📋 My reminders",
        'reminder_add': "➕ New reminder",
        'reminder_delete': "🗑️ Delete",
        'expense': "💰 Expense",
        'expense_add': "➕ New expense",
        'expense_list': "📊 My expenses",
        'expense_stats': "📈 Statistics",
        'expense_trends': "📉 Trends",
        'income': "💵 Income",
        'income_add': "➕ New income",
        'income_list': "📊 My income",
        'debts': "💸 Debts",
        'debts_add': "➕ New debt",
        'debts_list': "📋 All debts",
        'debts_close': "✅ Close debt",
        'report': "📊 Report",
        'budget': "🎯 Budget",
        'budget_status': "📊 Budget status",
        'budget_add': "➕ Add limit",
        'budget_edit': "✏️ Edit limit",
        'budget_delete': "🗑️ Delete limit",
        'budget_stats': "📈 Statistics",
        'budget_alert': "⚙️ Alert",
        'settings': "⚙️ Settings",
        'help': "🆘 Help",
        'back': "🔙 Back",
        'cancel': "❌ Cancel",
        'confirm': "✅ Confirm",
        'yes': "Yes",
        'no': "No",
        'error': "❌ Error",
        'invalid_input': "❌ Invalid format",
        'not_found': "❌ Not found",
        'success': "✅ Success",
        'today': "📅 Today",
        'daily': "🔄 Daily",
        'weekly': "📆 Weekly",
        'monthly': "📅 Monthly",
        'custom': "📆 Selected days",
        'other_date': "📅 Other date",
        'amount': "💰 Amount",
        'category': "🏷️ Category",
        'description': "📝 Description",
        'time': "⏰ Time",
        'date': "📅 Date",
        'person': "👤 Person",
        'gave': "📤 Gave",
        'took': "📥 Took",
        # Settings
        'currency_set': "💱 Currency",
        'reminder_time': "🔔 Reminder time",
        'budget_threshold': "💰 Budget threshold",
        'language': "🌐 Language",
        'theme': "🎨 Theme",
        'profile': "ℹ️ Profile",
        'light_theme': "☀️ Light",
        'dark_theme': "🌙 Dark",
        # Weekdays
        'monday': "Monday",
        'tuesday': "Tuesday",
        'wednesday': "Wednesday",
        'thursday': "Thursday",
        'friday': "Friday",
        'saturday': "Saturday",
        'sunday': "Sunday",
        'mon': "Mo",
        'tue': "Tu",
        'wed': "We",
        'thu': "Th",
        'fri': "Fr",
        'sat': "Sa",
        'sun': "Su",
        # Months
        'january': "January",
        'february': "February",
        'march': "March",
        'april': "April",
        'may': "May",
        'june': "June",
        'july': "July",
        'august': "August",
        'september': "September",
        'october': "October",
        'november': "November",
        'december': "December",
        # Additional texts
        'title': "Title",
        'repeat_type': "Repeat type",
        'select_days': "Select days",
        'select_date': "Select date",
        'enter_date': "Enter date (DD.MM.YYYY)",
        'invalid_date': "❌ Invalid date format",
        'invalid_time': "❌ Invalid time format (HH:MM)",
        'or_skip': "Type 'no' to skip",
        'select_at_least_one': "Select at least one day!",
        'reminder_saved': "Reminder saved",
        'no_reminders': "No reminders",
        'your_reminders': "Your reminders",
        'one_time': "One-time",
        'delete_reminder': "Delete reminder",
        'enter_id': "Enter ID",
        'reminder_deleted': "Reminder deleted",
        'amount_example': "Example: 50000, 1.5M, 200k",
        'expense_saved': "Expense saved",
        'no_expenses': "No expenses",
        'income_saved': "Income saved",
        'no_income': "No income",
        'debt_saved': "Debt saved",
        'no_debts': "No debts",
        'total_gave': "Gave",
        'total_took': "Took",
        'balance': "Balance",
        'enter_debt_id': "Enter debt ID",
        'debt_closed': "Debt closed",
        'loss': "Loss",
        'expense_analysis': "Expense analysis",
        'advice': "Advice",
        'advice_saving': "Keep saving!",
        'advice_budget': "Review your budget",
        'advice_plan': "Make a financial plan",
        'no_budgets': "No budgets set",
        'total_limit': "Total limit",
        'spent': "Spent",
        'remaining': "Remaining",
        'alerts': "Alerts",
        'exceeded': "exceeded",
        'threshold_reached': "reached threshold",
        'select_category': "Select category",
        'enter_category': "Enter category name",
        'enter_limit': "Enter limit amount",
        'budget_saved': "Budget saved",
        'alert_at': "Alert at",
        'no_budgets_to_edit': "No budgets to edit",
        'enter_new_limit': "Enter new limit",
        'no_budgets_to_delete': "No budgets to delete",
        'budget_deleted': "Budget deleted",
        'current_threshold': "Current threshold",
        'select_new_threshold': "Select new threshold",
        'name': "Name",
        'registered': "Registered",
        'statistics': "Statistics",
        'how_to_use': "How to use",
        'quick_add': "Quick add",
        'categories': "Categories",
        'by_source': "By source",
        'monthly_report': "Monthly report",
        'gave_and_took': "Gave and took",
        'close_debt': "Close debt",
        'category_limits': "Category limits",
        'progress_bar': "Progress bar",
        'monthly_summary': "Monthly summary",
        'category_analysis': "Category analysis",
        'trends': "Trends",
        'problems': "Problems",
        'restart_bot': "Restart bot",
        'users': "Users",
        'total': "Total",
        'active_week': "Active (7 days)",
        'blocked': "Blocked",
        'admins': "Admins",
        'activity': "Activity",
        'finance': "Finance",
        'total_income': "Total income",
        'total_expense': "Total expense",
        'status': "Status",
        'working': "Working",
        'last_10': "Last 10",
    }
}

CURRENCY_SYMBOLS = {
    "UZS": "so'm",
    "USD": "$",
    "EUR": "€",
    "RUB": "₽"
}

WEEKDAYS_UZ = {
    0: "Dushanba",
    1: "Seshanba", 
    2: "Chorshanba",
    3: "Payshanba",
    4: "Juma",
    5: "Shanba",
    6: "Yakshanba"
}

WEEKDAYS_SHORT = {
    0: "Du",
    1: "Se",
    2: "Ch",
    3: "Pa",
    4: "Ju",
    5: "Sha",
    6: "Ya"
}

MONTHS_UZ = {
    1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel",
    5: "May", 6: "Iyun", 7: "Iyul", 8: "Avgust",
    9: "Sentabr", 10: "Oktabr", 11: "Noyabr", 12: "Dekabr"
}

EXPENSE_CATEGORIES = {
    'uz': ["🍔 Taom", "🚕 Transport", "👕 Kiyim", "🏠 Uy-joy", "📱 Telefon", "🌐 Internet", "📚 O'qish", "⚕️ Sog'liq", "🎉 Ko'ngilochar", "🛍 Xarid", "💼 Ish", "📦 Boshqa"],
    'ru': ["🍔 Еда", "🚕 Транспорт", "👕 Одежда", "🏠 Жилье", "📱 Телефон", "🌐 Интернет", "📚 Учеба", "⚕️ Здоровье", "🎉 Развлечения", "🛍 Покупки", "💼 Работа", "📦 Другое"],
    'en': ["🍔 Food", "🚕 Transport", "👕 Clothing", "🏠 Housing", "📱 Phone", "🌐 Internet", "📚 Education", "⚕️ Health", "🎉 Entertainment", "🛍 Shopping", "💼 Work", "📦 Other"]
}

INCOME_CATEGORIES = {
    'uz': ["💼 Maosh", "📈 Loyiha", "🏪 Sotuv", "🎁 Sovg'a", "📊 Freelance", "🏦 Investitsiya", "💰 Boshqa"],
    'ru': ["💼 Зарплата", "📈 Проект", "🏪 Продажа", "🎁 Подарок", "📊 Фриланс", "🏦 Инвестиции", "💰 Другое"],
    'en': ["💼 Salary", "📈 Project", "🏪 Sale", "🎁 Gift", "📊 Freelance", "🏦 Investment", "💰 Other"]
}

# ==================== DATABASE ====================
class Database:
    def __init__(self):
        sqlite3.register_adapter(datetime, self._adapt_datetime)
        sqlite3.register_adapter(date, self._adapt_date)
        sqlite3.register_converter("DATETIME", self._convert_datetime)
        sqlite3.register_converter("DATE", self._convert_date)
        sqlite3.register_adapter(dict, json.dumps)
        sqlite3.register_converter("JSON", json.loads)
        
        self.conn = sqlite3.connect(
            DB_NAME,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            check_same_thread=False,
            timeout=30,
            isolation_level=None  # Autocommit mode
        )
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._init_tables()
        self._add_columns_if_not_exists()
        logger.info("Database initialized")
    
    def _adapt_datetime(self, dt):
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TIMEZONE)
        return dt.isoformat()
    
    def _adapt_date(self, d):
        if d is None:
            return None
        return d.isoformat()
    
    def _convert_datetime(self, val):
        try:
            if val is None:
                return None
            if isinstance(val, bytes):
                val = val.decode('utf-8')
            if isinstance(val, str):
                if 'T' in val:
                    dt = datetime.fromisoformat(val)
                elif ' ' in val:
                    dt = datetime.strptime(val, '%Y-%m-%d %H:%M:%S')
                else:
                    dt = datetime.strptime(val, '%Y-%m-%d')
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=TIMEZONE)
                return dt
        except Exception as e:
            logger.error(f"Datetime conversion error: {e}")
        return None
    
    def _convert_date(self, val):
        try:
            if val is None:
                return None
            if isinstance(val, bytes):
                val = val.decode('utf-8')
            if isinstance(val, str):
                return datetime.strptime(val, '%Y-%m-%d').date()
        except Exception as e:
            logger.error(f"Date conversion error: {e}")
        return None
    
    def _init_tables(self):
        """Jadvallarni yaratish"""
        
        # USERS jadvali
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                username TEXT,
                full_name TEXT,
                phone TEXT,
                language TEXT DEFAULT "uz",
                currency TEXT DEFAULT "UZS",
                is_admin BOOLEAN DEFAULT 0,
                is_blocked BOOLEAN DEFAULT 0,
                registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                total_expenses REAL DEFAULT 0,
                total_income REAL DEFAULT 0,
                reminder_count INTEGER DEFAULT 0
            )
        """)
        
        # REMINDERS jadvali
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                reminder_time DATETIME NOT NULL,
                repeat_type TEXT DEFAULT "none",
                repeat_days TEXT,
                status TEXT DEFAULT "active",
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                next_reminder DATETIME,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # REMINDER HISTORY jadvali
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminder_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reminder_id INTEGER,
                user_id INTEGER,
                sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (reminder_id) REFERENCES reminders(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # EXPENSES jadvali
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                expense_date DATE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # INCOME jadvali
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS income (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                income_date DATE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # DEBTS jadvali
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS debts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                person_name TEXT NOT NULL,
                amount REAL NOT NULL,
                debt_type TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                due_date DATE,
                return_date DATETIME,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # BUDGETS jadvali
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                category TEXT NOT NULL,
                monthly_limit REAL NOT NULL,
                current_spent REAL DEFAULT 0,
                month_year TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, category, month_year),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # BUDGET ALERTS jadvali
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS budget_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                category TEXT,
                alert_type TEXT,
                sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                month_year TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # USER SETTINGS jadvali
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                currency TEXT DEFAULT "UZS",
                reminder_time TEXT DEFAULT "09:00",
                notifications BOOLEAN DEFAULT 1,
                budget_alert_threshold INTEGER DEFAULT 80,
                language TEXT DEFAULT "uz",
                theme TEXT DEFAULT "light",
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # ADMIN ACTIONS jadvali
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                action TEXT,
                target_user INTEGER,
                details TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (admin_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        self.conn.commit()
    
    def _add_columns_if_not_exists(self):
        """Mavjud jadvallarga yangi ustunlar qo'shish"""
        try:
            # users jadvali
            self.cursor.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in self.cursor.fetchall()]
            
            if 'phone' not in columns:
                self.cursor.execute("ALTER TABLE users ADD COLUMN phone TEXT")
                logger.info("Added phone column to users table")
            
            if 'total_expenses' not in columns:
                self.cursor.execute("ALTER TABLE users ADD COLUMN total_expenses REAL DEFAULT 0")
                logger.info("Added total_expenses column to users table")
            
            if 'total_income' not in columns:
                self.cursor.execute("ALTER TABLE users ADD COLUMN total_income REAL DEFAULT 0")
                logger.info("Added total_income column to users table")
            
            if 'reminder_count' not in columns:
                self.cursor.execute("ALTER TABLE users ADD COLUMN reminder_count INTEGER DEFAULT 0")
                logger.info("Added reminder_count column to users table")
            
            if 'is_blocked' not in columns:
                self.cursor.execute("ALTER TABLE users ADD COLUMN is_blocked BOOLEAN DEFAULT 0")
                logger.info("Added is_blocked column to users table")
            
            # reminders jadvali
            self.cursor.execute("PRAGMA table_info(reminders)")
            columns = [col[1] for col in self.cursor.fetchall()]
            
            if 'repeat_days' not in columns:
                self.cursor.execute("ALTER TABLE reminders ADD COLUMN repeat_days TEXT")
                logger.info("Added repeat_days column to reminders table")
            
            if 'next_reminder' not in columns:
                self.cursor.execute("ALTER TABLE reminders ADD COLUMN next_reminder DATETIME")
                logger.info("Added next_reminder column to reminders table")
            
            # budgets jadvali
            self.cursor.execute("PRAGMA table_info(budgets)")
            columns = [col[1] for col in self.cursor.fetchall()]
            
            if 'updated_at' not in columns:
                self.cursor.execute("ALTER TABLE budgets ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP")
                logger.info("Added updated_at column to budgets table")
            
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"Error adding columns: {e}")
    
    # ==================== USER METHODS ====================
    def get_or_create_user(self, telegram_id: int, username: str, full_name: str, language: str = 'uz', phone: str = None) -> dict:
        """Foydalanuvchini olish yoki yaratish"""
        now = datetime.now(TIMEZONE)
        is_admin = 1 if telegram_id in ADMIN_IDS else 0
        
        try:
            self.cursor.execute(
                "SELECT * FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            user = self.cursor.fetchone()
            
            if user:
                # Mavjud foydalanuvchini yangilash
                self.cursor.execute(
                    """UPDATE users SET 
                    username = ?, 
                    full_name = ?, 
                    is_admin = ?, 
                    last_seen = ?,
                    phone = COALESCE(?, phone),
                    language = COALESCE(?, language)
                    WHERE telegram_id = ?""",
                    (username, full_name, is_admin, now, phone, language, telegram_id)
                )
                user = dict(user)
            else:
                # Yangi foydalanuvchi yaratish
                self.cursor.execute(
                    """INSERT INTO users 
                    (telegram_id, username, full_name, is_admin, last_seen, phone, language) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (telegram_id, username, full_name, is_admin, now, phone, language)
                )
                
                user_id = self.cursor.lastrowid
                self.cursor.execute(
                    "SELECT * FROM users WHERE id = ?",
                    (user_id,)
                )
                user = dict(self.cursor.fetchone())
                
                # Foydalanuvchi sozlamalarini yaratish
                self.cursor.execute(
                    "INSERT OR IGNORE INTO user_settings (user_id, currency, language) VALUES (?, ?, ?)",
                    (user_id, LANGUAGES[language]['currency'], language)
                )
            
            self.conn.commit()
            return user
            
        except Exception as e:
            logger.error(f"Get or create user error: {e}")
            return {
                'id': None,
                'telegram_id': telegram_id,
                'username': username,
                'full_name': full_name,
                'is_admin': is_admin,
                'is_blocked': 0,
                'language': language
            }
    
    def get_user_id(self, telegram_id: int) -> Optional[int]:
        """Telegram ID dan foydalanuvchi ID sini olish"""
        try:
            self.cursor.execute(
                "SELECT id FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = self.cursor.fetchone()
            return row['id'] if row else None
        except:
            return None
    
    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[dict]:
        """Telegram ID orqali foydalanuvchini olish"""
        try:
            self.cursor.execute(
                "SELECT * FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = self.cursor.fetchone()
            return dict(row) if row else None
        except:
            return None
    
    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        """ID orqali foydalanuvchini olish"""
        try:
            self.cursor.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,)
            )
            row = self.cursor.fetchone()
            return dict(row) if row else None
        except:
            return None
    
    def get_user_settings(self, user_id: int) -> dict:
        """Foydalanuvchi sozlamalarini olish"""
        try:
            self.cursor.execute(
                "SELECT * FROM user_settings WHERE user_id = ?",
                (user_id,)
            )
            row = self.cursor.fetchone()
            if row:
                return dict(row)
            else:
                # Foydalanuvchi tilini olish
                user = self.get_user_by_id(user_id)
                lang = user.get('language', 'uz') if user else 'uz'
                
                self.cursor.execute(
                    "INSERT INTO user_settings (user_id, currency, language) VALUES (?, ?, ?)",
                    (user_id, LANGUAGES[lang]['currency'], lang)
                )
                self.conn.commit()
                self.cursor.execute(
                    "SELECT * FROM user_settings WHERE user_id = ?",
                    (user_id,)
                )
                return dict(self.cursor.fetchone())
        except Exception as e:
            logger.error(f"Error getting user settings: {e}")
            return {
                'user_id': user_id,
                'currency': 'UZS',
                'reminder_time': '09:00',
                'notifications': 1,
                'budget_alert_threshold': 80,
                'language': 'uz',
                'theme': 'light'
            }
    
    def update_user_setting(self, user_id: int, setting: str, value: any) -> bool:
        """Foydalanuvchi sozlamalarini yangilash"""
        try:
            allowed_settings = ['currency', 'reminder_time', 'notifications', 'budget_alert_threshold', 'language', 'theme']
            if setting not in allowed_settings:
                return False
            
            query = f"UPDATE user_settings SET {setting} = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?"
            self.cursor.execute(query, (value, user_id))
            
            # Agar til o'zgarsa, users jadvalida ham yangilash
            if setting == 'language':
                self.cursor.execute(
                    "UPDATE users SET language = ? WHERE id = ?",
                    (value, user_id)
                )
            
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Update user setting error: {e}")
            return False
    
    def get_user_language(self, user_id: int) -> str:
        """Foydalanuvchi tilini olish"""
        try:
            self.cursor.execute(
                "SELECT language FROM users WHERE id = ?",
                (user_id,)
            )
            row = self.cursor.fetchone()
            return row['language'] if row else 'uz'
        except:
            return 'uz'
    
    def get_user_full_profile(self, user_id: int) -> dict:
        """Foydalanuvchining to'liq profilini olish"""
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        
        settings = self.get_user_settings(user_id)
        
        # Statistika
        today = date.today()
        month_start = date(today.year, today.month, 1)
        
        stats = {
            'active_reminders': 0,
            'total_reminders': 0,
            'monthly_expense': 0,
            'monthly_income': 0,
            'monthly_balance': 0,
            'active_debts': 0,
            'total_gave': 0,
            'total_took': 0
        }
        
        try:
            self.cursor.execute(
                "SELECT COUNT(*) as count FROM reminders WHERE user_id = ? AND status = 'active'",
                (user_id,)
            )
            stats['active_reminders'] = self.cursor.fetchone()['count']
        except: pass
        
        try:
            self.cursor.execute(
                "SELECT COUNT(*) as count FROM reminders WHERE user_id = ?",
                (user_id,)
            )
            stats['total_reminders'] = self.cursor.fetchone()['count']
        except: pass
        
        try:
            self.cursor.execute(
                "SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE user_id = ? AND expense_date >= ?",
                (user_id, month_start)
            )
            stats['monthly_expense'] = float(self.cursor.fetchone()['total'])
        except: pass
        
        try:
            self.cursor.execute(
                "SELECT COALESCE(SUM(amount), 0) as total FROM income WHERE user_id = ? AND income_date >= ?",
                (user_id, month_start)
            )
            stats['monthly_income'] = float(self.cursor.fetchone()['total'])
        except: pass
        
        stats['monthly_balance'] = stats['monthly_income'] - stats['monthly_expense']
        
        try:
            self.cursor.execute(
                "SELECT COUNT(*) as count FROM debts WHERE user_id = ? AND status = 'active'",
                (user_id,)
            )
            stats['active_debts'] = self.cursor.fetchone()['count']
        except: pass
        
        try:
            self.cursor.execute(
                "SELECT COALESCE(SUM(amount), 0) as total FROM debts WHERE user_id = ? AND status = 'active' AND debt_type = 'gave'",
                (user_id,)
            )
            stats['total_gave'] = float(self.cursor.fetchone()['total'])
        except: pass
        
        try:
            self.cursor.execute(
                "SELECT COALESCE(SUM(amount), 0) as total FROM debts WHERE user_id = ? AND status = 'active' AND debt_type = 'took'",
                (user_id,)
            )
            stats['total_took'] = float(self.cursor.fetchone()['total'])
        except: pass
        
        return {
            'user': user,
            'settings': settings,
            'stats': stats
        }
    
    # ==================== REMINDER METHODS ====================
    def add_reminder(self, user_id: int, title: str, reminder_time: datetime, 
                    description: str = "", repeat_type: str = "none", 
                    repeat_days: List[int] = None) -> bool:
        """Yangi eslatma qo'shish"""
        try:
            next_reminder = self._calculate_next_reminder(reminder_time, repeat_type, repeat_days)
            
            # repeat_days ni JSON stringga o'tkazish
            repeat_days_json = None
            if repeat_days:
                try:
                    repeat_days_json = json.dumps(repeat_days)
                    logger.info(f"Saving repeat_days: {repeat_days} -> {repeat_days_json}")
                except Exception as e:
                    logger.error(f"Error serializing repeat_days: {e}")
            
            self.cursor.execute(
                """INSERT INTO reminders 
                (user_id, title, description, reminder_time, repeat_type, repeat_days, next_reminder) 
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, title, description, reminder_time, repeat_type, repeat_days_json, next_reminder)
            )
            
            try:
                self.cursor.execute(
                    "UPDATE users SET reminder_count = reminder_count + 1 WHERE id = ?",
                    (user_id,)
                )
            except: pass
            
            self.conn.commit()
            logger.info(f"Reminder added successfully with repeat_days: {repeat_days}")
            return True
        except Exception as e:
            logger.error(f"Add reminder error: {e}")
            return False
    
    def _calculate_next_reminder(self, base_time: datetime, repeat_type: str, repeat_days: List[int] = None) -> datetime:
        """Keyingi eslatma vaqtini hisoblash"""
        now = datetime.now(TIMEZONE)
        
        if repeat_type == "none":
            return base_time
        
        elif repeat_type == "daily":
            next_time = datetime.combine(
                now.date(),
                base_time.time(),
                tzinfo=TIMEZONE
            )
            if next_time <= now:
                next_time += timedelta(days=1)
            return next_time
        
        elif repeat_type == "weekly":
            next_time = base_time
            while next_time <= now:
                next_time += timedelta(days=7)
            return next_time
        
        elif repeat_type == "monthly":
            next_time = base_time
            while next_time <= now:
                if next_time.month == 12:
                    next_time = next_time.replace(year=next_time.year + 1, month=1)
                else:
                    next_time = next_time.replace(month=next_time.month + 1)
            return next_time
        
        elif repeat_type == "custom" and repeat_days:
            current_weekday = now.weekday()
            current_time = now.time()
            base_time_time = base_time.time()
            
            today_in_days = current_weekday in repeat_days
            time_passed = current_time >= base_time_time if today_in_days else False
            
            days_ahead = 0
            if today_in_days and not time_passed:
                days_ahead = 0
            else:
                for i in range(1, 8):
                    next_day = (current_weekday + i) % 7
                    if next_day in repeat_days:
                        days_ahead = i
                        break
            
            next_time = datetime.combine(
                now.date() + timedelta(days=days_ahead),
                base_time_time,
                tzinfo=TIMEZONE
            )
            return next_time
        
        return base_time
    
    def get_user_reminders(self, user_id: int) -> List[dict]:
        """Foydalanuvchi eslatmalarini olish"""
        try:
            self.cursor.execute(
                """SELECT * FROM reminders 
                WHERE user_id = ? AND status = 'active' 
                ORDER BY 
                    CASE 
                        WHEN repeat_type != 'none' AND next_reminder IS NOT NULL THEN next_reminder 
                        ELSE reminder_time 
                    END
                """,
                (user_id,)
            )
            reminders = []
            for row in self.cursor.fetchall():
                reminder = dict(row)
                # repeat_days ni JSON dan o'qish
                if reminder.get('repeat_days'):
                    try:
                        if isinstance(reminder['repeat_days'], str):
                            reminder['repeat_days'] = json.loads(reminder['repeat_days'])
                        elif isinstance(reminder['repeat_days'], bytes):
                            reminder['repeat_days'] = json.loads(reminder['repeat_days'].decode('utf-8'))
                        else:
                            reminder['repeat_days'] = []
                    except:
                        reminder['repeat_days'] = []
                
                # next_reminder ni datetime ga o'tkazish
                if reminder.get('next_reminder') and isinstance(reminder['next_reminder'], str):
                    try:
                        reminder['next_reminder'] = datetime.fromisoformat(reminder['next_reminder'].replace(' ', 'T'))
                    except:
                        pass
                
                # reminder_time ni datetime ga o'tkazish
                if reminder.get('reminder_time') and isinstance(reminder['reminder_time'], str):
                    try:
                        reminder['reminder_time'] = datetime.fromisoformat(reminder['reminder_time'].replace(' ', 'T'))
                    except:
                        pass
                
                reminders.append(reminder)
            return reminders
        except Exception as e:
            logger.error(f"Get user reminders error: {e}")
            return []
    
    def delete_reminder(self, reminder_id: int, user_id: int) -> bool:
        """Eslatmani o'chirish"""
        try:
            self.cursor.execute(
                "DELETE FROM reminders WHERE id = ? AND user_id = ?",
                (reminder_id, user_id)
            )
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Delete reminder error: {e}")
            return False
    
    def update_reminder_next_time(self, reminder_id: int):
        """Eslatmaning keyingi vaqtini yangilash"""
        try:
            self.cursor.execute(
                "SELECT * FROM reminders WHERE id = ?",
                (reminder_id,)
            )
            reminder = self.cursor.fetchone()
            if not reminder:
                return
            
            repeat_type = reminder['repeat_type']
            
            if repeat_type == 'none':
                self.cursor.execute(
                    "UPDATE reminders SET status = 'completed' WHERE id = ?",
                    (reminder_id,)
                )
            else:
                repeat_days = None
                if reminder['repeat_days']:
                    try:
                        repeat_days = json.loads(reminder['repeat_days'])
                    except:
                        pass
                
                reminder_time = reminder['reminder_time']
                if isinstance(reminder_time, str):
                    reminder_time = datetime.fromisoformat(reminder_time.replace(' ', 'T'))
                
                next_time = self._calculate_next_reminder(
                    reminder_time,
                    repeat_type,
                    repeat_days
                )
                
                self.cursor.execute(
                    "UPDATE reminders SET next_reminder = ? WHERE id = ?",
                    (next_time, reminder_id)
                )
            
            self.conn.commit()
        except Exception as e:
            logger.error(f"Update reminder next time error: {e}")
    
    def log_reminder_sent(self, reminder_id: int, user_id: int):
        """Eslatma yuborilganligini log qilish"""
        try:
            self.cursor.execute(
                "INSERT INTO reminder_history (reminder_id, user_id) VALUES (?, ?)",
                (reminder_id, user_id)
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"Log reminder sent error: {e}")
    
    def get_due_reminders(self) -> List[dict]:
        """Yuborilishi kerak bo'lgan eslatmalarni olish"""
        try:
            now = datetime.now(TIMEZONE)
            
            # Bir martalik eslatmalar
            self.cursor.execute(
                """SELECT r.*, u.telegram_id, u.is_blocked, u.id as user_db_id
                FROM reminders r 
                JOIN users u ON r.user_id = u.id 
                WHERE r.status = 'active' 
                AND u.is_blocked = 0
                AND r.repeat_type = 'none'
                AND date(r.reminder_time) = date(?)
                AND strftime('%H:%M', r.reminder_time) = strftime('%H:%M', ?)""",
                (now, now)
            )
            
            reminders = []
            for row in self.cursor.fetchall():
                reminder = dict(row)
                if reminder.get('repeat_days'):
                    try:
                        reminder['repeat_days'] = json.loads(reminder['repeat_days'])
                    except:
                        reminder['repeat_days'] = []
                reminders.append(reminder)
            
            # Takrorlanuvchi eslatmalar
            self.cursor.execute(
                """SELECT r.*, u.telegram_id, u.is_blocked, u.id as user_db_id
                FROM reminders r 
                JOIN users u ON r.user_id = u.id 
                WHERE r.status = 'active' 
                AND u.is_blocked = 0
                AND r.repeat_type != 'none'
                AND date(r.next_reminder) = date(?)
                AND strftime('%H:%M', r.next_reminder) = strftime('%H:%M', ?)""",
                (now, now)
            )
            
            for row in self.cursor.fetchall():
                reminder = dict(row)
                if reminder.get('repeat_days'):
                    try:
                        reminder['repeat_days'] = json.loads(reminder['repeat_days'])
                    except:
                        reminder['repeat_days'] = []
                reminders.append(reminder)
            
            return reminders
        except Exception as e:
            logger.error(f"Get due reminders error: {e}")
            return []
    
    # ==================== EXPENSE METHODS ====================
    def add_expense(self, user_id: int, amount: float, category: str, 
                   description: str = "", expense_date: date = None) -> bool:
        """Xarajat qo'shish"""
        try:
            if expense_date is None:
                expense_date = date.today()
            
            self.cursor.execute(
                """INSERT INTO expenses (user_id, amount, category, description, expense_date) 
                VALUES (?, ?, ?, ?, ?)""",
                (user_id, amount, category, description, expense_date)
            )
            
            month_year = expense_date.strftime("%Y-%m")
            self.cursor.execute(
                """INSERT OR IGNORE INTO budgets (user_id, category, monthly_limit, month_year) 
                VALUES (?, ?, 0, ?)""",
                (user_id, category, month_year)
            )
            self.cursor.execute(
                """UPDATE budgets SET current_spent = current_spent + ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND category = ? AND month_year = ?""",
                (amount, user_id, category, month_year)
            )
            
            try:
                self.cursor.execute(
                    "UPDATE users SET total_expenses = total_expenses + ? WHERE id = ?",
                    (amount, user_id)
                )
            except: pass
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Add expense error: {e}")
            return False
    
    def get_expense_statistics(self, user_id: int, period: str = "month") -> dict:
        """Xarajatlar statistikasi"""
        today = date.today()
        
        if period == "week":
            start_date = today - timedelta(days=today.weekday())
        elif period == "month":
            start_date = date(today.year, today.month, 1)
        elif period == "year":
            start_date = date(today.year, 1, 1)
        else:
            start_date = today - timedelta(days=30)
        
        result = {
            'period': period,
            'start_date': start_date,
            'end_date': today,
            'general': {'count': 0, 'total': 0, 'average': 0, 'max': 0, 'min': 0},
            'categories': [],
            'daily': [],
            'top_category': None
        }
        
        try:
            # Umumiy statistika
            self.cursor.execute(
                """SELECT 
                    COALESCE(COUNT(*), 0) as count,
                    COALESCE(SUM(amount), 0) as total,
                    COALESCE(AVG(amount), 0) as average,
                    COALESCE(MAX(amount), 0) as max,
                    COALESCE(MIN(amount), 0) as min
                FROM expenses 
                WHERE user_id = ? AND expense_date >= ?""",
                (user_id, start_date)
            )
            general = dict(self.cursor.fetchone())
            result['general'] = {
                'count': int(general['count']),
                'total': float(general['total']),
                'average': float(general['average']),
                'max': float(general['max']),
                'min': float(general['min']) if general['min'] else 0
            }
            
            # Kategoriyalar bo'yicha
            self.cursor.execute(
                """SELECT category, COALESCE(SUM(amount), 0) as total, COUNT(*) as count
                FROM expenses 
                WHERE user_id = ? AND expense_date >= ?
                GROUP BY category
                ORDER BY total DESC""",
                (user_id, start_date)
            )
            result['categories'] = [dict(row) for row in self.cursor.fetchall()]
            
            # Kunlik xarajatlar
            self.cursor.execute(
                """SELECT expense_date, COALESCE(SUM(amount), 0) as total
                FROM expenses 
                WHERE user_id = ? AND expense_date >= ?
                GROUP BY expense_date
                ORDER BY expense_date DESC
                LIMIT 7""",
                (user_id, start_date)
            )
            result['daily'] = [dict(row) for row in self.cursor.fetchall()]
            
            result['top_category'] = result['categories'][0] if result['categories'] else None
            
        except Exception as e:
            logger.error(f"Get expense statistics error: {e}")
        
        return result
    
    def get_expense_trends(self, user_id: int, months: int = 6) -> dict:
        """Xarajatlar trendi"""
        today = date.today()
        trends = {}
        
        for i in range(months):
            month_date = today.replace(day=1) - timedelta(days=1)
            month_str = month_date.strftime("%Y-%m")
            month_name = MONTHS_UZ.get(month_date.month, str(month_date.month))
            key = f"{month_name} {month_date.year}"
            
            try:
                self.cursor.execute(
                    """SELECT COALESCE(SUM(amount), 0) as total
                    FROM expenses 
                    WHERE user_id = ? AND strftime('%Y-%m', expense_date) = ?""",
                    (user_id, month_str)
                )
                total = self.cursor.fetchone()['total']
                trends[key] = float(total)
            except:
                trends[key] = 0
            
            today = month_date
        
        return trends
    
    # ==================== INCOME METHODS ====================
    def add_income(self, user_id: int, amount: float, category: str,
                  description: str = "", income_date: date = None) -> bool:
        """Daromad qo'shish"""
        try:
            if income_date is None:
                income_date = date.today()
            
            self.cursor.execute(
                """INSERT INTO income (user_id, amount, category, description, income_date) 
                VALUES (?, ?, ?, ?, ?)""",
                (user_id, amount, category, description, income_date)
            )
            
            try:
                self.cursor.execute(
                    "UPDATE users SET total_income = total_income + ? WHERE id = ?",
                    (amount, user_id)
                )
            except: pass
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Add income error: {e}")
            return False
    
    def get_income_statistics(self, user_id: int) -> dict:
        """Daromadlar statistikasi"""
        month_year = date.today().strftime("%Y-%m")
        
        try:
            self.cursor.execute(
                """SELECT 
                    COALESCE(COUNT(*), 0) as count,
                    COALESCE(SUM(amount), 0) as total,
                    COALESCE(AVG(amount), 0) as average
                FROM income 
                WHERE user_id = ? AND strftime('%Y-%m', income_date) = ?""",
                (user_id, month_year)
            )
            stats = dict(self.cursor.fetchone())
            
            self.cursor.execute(
                """SELECT category, COALESCE(SUM(amount), 0) as total
                FROM income 
                WHERE user_id = ? AND strftime('%Y-%m', income_date) = ?
                GROUP BY category
                ORDER BY total DESC""",
                (user_id, month_year)
            )
            categories = [dict(row) for row in self.cursor.fetchall()]
            
            return {
                'count': int(stats['count']),
                'total': float(stats['total']),
                'average': float(stats['average']),
                'categories': categories
            }
        except Exception as e:
            logger.error(f"Get income statistics error: {e}")
            return {'count': 0, 'total': 0, 'average': 0, 'categories': []}
    
    # ==================== DEBT METHODS ====================
    def add_debt(self, user_id: int, person_name: str, amount: float,
                debt_type: str, description: str = "", due_date: date = None) -> bool:
        """Qarz qo'shish"""
        try:
            self.cursor.execute(
                """INSERT INTO debts (user_id, person_name, amount, debt_type, description, due_date) 
                VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, person_name, amount, debt_type, description, due_date)
            )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Add debt error: {e}")
            return False
    
    def get_user_debts(self, user_id: int) -> List[dict]:
        """Foydalanuvchi qarzlarini olish"""
        try:
            self.cursor.execute(
                """SELECT * FROM debts WHERE user_id = ? AND status = 'active' 
                ORDER BY due_date ASC, created_at DESC""",
                (user_id,)
            )
            return [dict(row) for row in self.cursor.fetchall()]
        except Exception as e:
            logger.error(f"Get user debts error: {e}")
            return []
    
    def close_debt(self, debt_id: int, user_id: int) -> bool:
        """Qarzni yopish"""
        try:
            return_date = datetime.now(TIMEZONE)
            self.cursor.execute(
                """UPDATE debts SET status = 'returned', return_date = ? 
                WHERE id = ? AND user_id = ?""",
                (return_date, debt_id, user_id)
            )
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Close debt error: {e}")
            return False
    
    # ==================== BUDGET METHODS ====================
    def set_budget_limit(self, user_id: int, category: str, limit: float) -> bool:
        """Byudjet limitini belgilash"""
        try:
            month_year = date.today().strftime("%Y-%m")
            
            self.cursor.execute(
                "SELECT * FROM budgets WHERE user_id = ? AND category = ? AND month_year = ?",
                (user_id, category, month_year)
            )
            existing = self.cursor.fetchone()
            
            if existing:
                self.cursor.execute(
                    """UPDATE budgets SET monthly_limit = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND category = ? AND month_year = ?""",
                    (limit, user_id, category, month_year)
                )
            else:
                # Joriy oydagi xarajatni hisoblash
                self.cursor.execute(
                    "SELECT COALESCE(SUM(amount), 0) as total FROM expenses WHERE user_id = ? AND category = ? AND strftime('%Y-%m', expense_date) = ?",
                    (user_id, category, month_year)
                )
                current_spent = self.cursor.fetchone()['total']
                
                self.cursor.execute(
                    """INSERT INTO budgets (user_id, category, monthly_limit, month_year, current_spent) 
                    VALUES (?, ?, ?, ?, ?)""",
                    (user_id, category, limit, month_year, current_spent)
                )
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Set budget error: {e}")
            return False
    
    def get_user_budgets(self, user_id: int) -> List[dict]:
        """Foydalanuvchi byudjetlarini olish"""
        try:
            month_year = date.today().strftime("%Y-%m")
            self.cursor.execute(
                "SELECT * FROM budgets WHERE user_id = ? AND month_year = ? ORDER BY category",
                (user_id, month_year)
            )
            budgets = [dict(row) for row in self.cursor.fetchall()]
            
            expenses_by_category = self.get_expenses_by_category(user_id, month_year)
            
            for category, spent in expenses_by_category.items():
                exists = False
                for budget in budgets:
                    if budget['category'] == category:
                        exists = True
                        if budget['current_spent'] != spent:
                            self.cursor.execute(
                                "UPDATE budgets SET current_spent = ? WHERE id = ?",
                                (spent, budget['id'])
                            )
                            budget['current_spent'] = spent
                        break
                
                if not exists:
                    self.cursor.execute(
                        """INSERT OR IGNORE INTO budgets (user_id, category, monthly_limit, month_year, current_spent) 
                        VALUES (?, ?, 0, ?, ?)""",
                        (user_id, category, month_year, spent)
                    )
                    self.conn.commit()
                    
                    self.cursor.execute(
                        "SELECT * FROM budgets WHERE user_id = ? AND category = ? AND month_year = ?",
                        (user_id, category, month_year)
                    )
                    row = self.cursor.fetchone()
                    if row:
                        budgets.append(dict(row))
            
            return budgets
        except Exception as e:
            logger.error(f"Get user budgets error: {e}")
            return []
    
    def get_budget_summary(self, user_id: int) -> dict:
        """Byudjet xulosasi"""
        budgets = self.get_user_budgets(user_id)
        
        total_limit = 0
        total_spent = 0
        categories_count = 0
        exceeded_count = 0
        warning_count = 0
        
        for budget in budgets:
            if budget['monthly_limit'] > 0:
                total_limit += budget['monthly_limit']
                total_spent += budget['current_spent']
                categories_count += 1
                
                percentage = (budget['current_spent'] / budget['monthly_limit'] * 100) if budget['monthly_limit'] > 0 else 0
                if percentage >= 100:
                    exceeded_count += 1
                elif percentage >= 80:
                    warning_count += 1
        
        return {
            'total_limit': float(total_limit),
            'total_spent': float(total_spent),
            'remaining': float(total_limit - total_spent),
            'categories_count': categories_count,
            'exceeded_count': exceeded_count,
            'warning_count': warning_count,
            'budgets': budgets
        }
    
    def check_budget_alerts(self, user_id: int, category: str, spent: float, limit: float) -> List[str]:
        """Byudjet ogohlantirishlarini tekshirish"""
        alerts = []
        percentage = (spent / limit * 100) if limit > 0 else 0
        
        settings = self.get_user_settings(user_id)
        threshold = settings.get('budget_alert_threshold', 80)
        
        month_year = date.today().strftime("%Y-%m")
        
        try:
            # Threshold dan o'tganligini tekshirish
            if percentage >= threshold:
                self.cursor.execute(
                    """SELECT COUNT(*) as count FROM budget_alerts 
                    WHERE user_id = ? AND category = ? AND alert_type = 'threshold' 
                    AND month_year = ? AND date(sent_at) = date('now')""",
                    (user_id, category, month_year)
                )
                sent_today = self.cursor.fetchone()['count'] > 0
                
                if not sent_today:
                    alerts.append(f"threshold:{percentage:.0f}")
                    self.cursor.execute(
                        """INSERT INTO budget_alerts (user_id, category, alert_type, month_year) 
                        VALUES (?, ?, 'threshold', ?)""",
                        (user_id, category, month_year)
                    )
            
            # Limit oshib ketganligini tekshirish
            if percentage >= 100:
                self.cursor.execute(
                    """SELECT COUNT(*) as count FROM budget_alerts 
                    WHERE user_id = ? AND category = ? AND alert_type = 'exceeded' 
                    AND month_year = ?""",
                    (user_id, category, month_year)
                )
                already_alerted = self.cursor.fetchone()['count'] > 0
                
                if not already_alerted:
                    alerts.append(f"exceeded:{spent - limit:,.0f}")
                    self.cursor.execute(
                        """INSERT INTO budget_alerts (user_id, category, alert_type, month_year) 
                        VALUES (?, ?, 'exceeded', ?)""",
                        (user_id, category, month_year)
                    )
            
            self.conn.commit()
        except Exception as e:
            logger.error(f"Check budget alerts error: {e}")
        
        return alerts
    
    def delete_budget(self, user_id: int, category: str) -> bool:
        """Byudjet limitini o'chirish"""
        try:
            month_year = date.today().strftime("%Y-%m")
            self.cursor.execute(
                "DELETE FROM budgets WHERE user_id = ? AND category = ? AND month_year = ?",
                (user_id, category, month_year)
            )
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Delete budget error: {e}")
            return False
    
    def get_expenses_by_category(self, user_id: int, month_year: str = None) -> dict:
        """Kategoriyalar bo'yicha xarajatlar"""
        if month_year is None:
            month_year = date.today().strftime("%Y-%m")
        
        try:
            self.cursor.execute(
                """SELECT category, COALESCE(SUM(amount), 0) as total FROM expenses 
                WHERE user_id = ? AND strftime('%Y-%m', expense_date) = ?
                GROUP BY category""",
                (user_id, month_year)
            )
            
            result = {}
            for row in self.cursor.fetchall():
                result[row['category']] = float(row['total'])
            return result
        except Exception as e:
            logger.error(f"Get expenses by category error: {e}")
            return {}
    
    # ==================== FINANCIAL SUMMARY ====================
    def get_financial_summary(self, user_id: int) -> dict:
        """Moliyaviy hisobot"""
        month_year = date.today().strftime("%Y-%m")
        
        try:
            self.cursor.execute(
                """SELECT COALESCE(SUM(amount), 0) as total FROM expenses 
                WHERE user_id = ? AND strftime('%Y-%m', expense_date) = ?""",
                (user_id, month_year)
            )
            total_expense = self.cursor.fetchone()['total']
            
            self.cursor.execute(
                """SELECT COALESCE(SUM(amount), 0) as total FROM income 
                WHERE user_id = ? AND strftime('%Y-%m', income_date) = ?""",
                (user_id, month_year)
            )
            total_income = self.cursor.fetchone()['total']
            
            return {
                'total_expense': float(total_expense),
                'total_income': float(total_income),
                'balance': float(total_income - total_expense),
                'month': month_year
            }
        except Exception as e:
            logger.error(f"Get financial summary error: {e}")
            return {
                'total_expense': 0,
                'total_income': 0,
                'balance': 0,
                'month': month_year
            }
    
    # ==================== ADMIN METHODS ====================
    def get_all_users(self) -> List[dict]:
        """Barcha foydalanuvchilarni olish"""
        try:
            self.cursor.execute(
                """SELECT * FROM users ORDER BY 
                CASE WHEN is_admin = 1 THEN 0 ELSE 1 END,
                registered_at DESC"""
            )
            return [dict(row) for row in self.cursor.fetchall()]
        except Exception as e:
            logger.error(f"Get all users error: {e}")
            return []
    
    def get_recent_users(self, days: int = 7) -> List[dict]:
        """Yangi foydalanuvchilar"""
        try:
            since = datetime.now(TIMEZONE) - timedelta(days=days)
            self.cursor.execute(
                "SELECT * FROM users WHERE registered_at >= ? ORDER BY registered_at DESC",
                (since,)
            )
            return [dict(row) for row in self.cursor.fetchall()]
        except Exception as e:
            logger.error(f"Get recent users error: {e}")
            return []
    
    def get_active_users(self, days: int = 7) -> List[dict]:
        """Faol foydalanuvchilar"""
        try:
            since = datetime.now(TIMEZONE) - timedelta(days=days)
            self.cursor.execute(
                "SELECT * FROM users WHERE last_seen >= ? ORDER BY last_seen DESC",
                (since,)
            )
            return [dict(row) for row in self.cursor.fetchall()]
        except Exception as e:
            logger.error(f"Get active users error: {e}")
            return []
    
    def get_bot_stats(self) -> dict:
        """Bot statistikasi"""
        stats = {
            'total_users': 0,
            'admins': 0,
            'blocked_users': 0,
            'new_users_today': 0,
            'active_week': 0,
            'active_reminders': 0,
            'active_debts': 0,
            'budgets': 0,
            'total_income': 0,
            'total_expense': 0,
            'total_balance': 0
        }
        
        try:
            self.cursor.execute("SELECT COUNT(*) as count FROM users")
            stats['total_users'] = self.cursor.fetchone()['count']
        except: pass
        
        try:
            self.cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_admin = 1")
            stats['admins'] = self.cursor.fetchone()['count']
        except: pass
        
        try:
            self.cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_blocked = 1")
            stats['blocked_users'] = self.cursor.fetchone()['count']
        except: pass
        
        try:
            self.cursor.execute("SELECT COUNT(*) as count FROM users WHERE date(registered_at) = date('now')")
            stats['new_users_today'] = self.cursor.fetchone()['count']
        except: pass
        
        try:
            week_ago = datetime.now(TIMEZONE) - timedelta(days=7)
            self.cursor.execute("SELECT COUNT(*) as count FROM users WHERE last_seen >= ?", (week_ago,))
            stats['active_week'] = self.cursor.fetchone()['count']
        except: pass
        
        try:
            self.cursor.execute("SELECT COUNT(*) as count FROM reminders WHERE status = 'active'")
            stats['active_reminders'] = self.cursor.fetchone()['count']
        except: pass
        
        try:
            self.cursor.execute("SELECT COUNT(*) as count FROM debts WHERE status = 'active'")
            stats['active_debts'] = self.cursor.fetchone()['count']
        except: pass
        
        try:
            self.cursor.execute("SELECT COUNT(*) as count FROM budgets")
            stats['budgets'] = self.cursor.fetchone()['count']
        except: pass
        
        try:
            self.cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM income")
            stats['total_income'] = float(self.cursor.fetchone()['total'])
        except: pass
        
        try:
            self.cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM expenses")
            stats['total_expense'] = float(self.cursor.fetchone()['total'])
        except: pass
        
        stats['total_balance'] = stats['total_income'] - stats['total_expense']
        
        return stats
    
    def block_user(self, telegram_id: int, admin_id: int = None) -> bool:
        """Foydalanuvchini bloklash"""
        try:
            self.cursor.execute(
                "UPDATE users SET is_blocked = 1 WHERE telegram_id = ?",
                (telegram_id,)
            )
            
            if admin_id and self.cursor.rowcount > 0:
                try:
                    self.cursor.execute(
                        """INSERT INTO admin_actions (admin_id, action, target_user) 
                        VALUES (?, 'block', ?)""",
                        (admin_id, telegram_id)
                    )
                except: pass
            
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Block user error: {e}")
            return False
    
    def unblock_user(self, telegram_id: int, admin_id: int = None) -> bool:
        """Foydalanuvchi blokini ochish"""
        try:
            self.cursor.execute(
                "UPDATE users SET is_blocked = 0 WHERE telegram_id = ?",
                (telegram_id,)
            )
            
            if admin_id and self.cursor.rowcount > 0:
                try:
                    self.cursor.execute(
                        """INSERT INTO admin_actions (admin_id, action, target_user) 
                        VALUES (?, 'unblock', ?)""",
                        (admin_id, telegram_id)
                    )
                except: pass
            
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Unblock user error: {e}")
            return False
    
    def get_admin_actions(self, limit: int = 50) -> List[dict]:
        """Admin harakatlarini olish"""
        try:
            self.cursor.execute(
                """SELECT a.*, u1.full_name as admin_name, u2.full_name as target_name
                FROM admin_actions a
                LEFT JOIN users u1 ON a.admin_id = u1.telegram_id
                LEFT JOIN users u2 ON a.target_user = u2.telegram_id
                ORDER BY a.created_at DESC
                LIMIT ?""",
                (limit,)
            )
            return [dict(row) for row in self.cursor.fetchall()]
        except Exception as e:
            logger.error(f"Get admin actions error: {e}")
            return []
    
    def search_users(self, query: str) -> List[dict]:
        """Foydalanuvchilarni qidirish"""
        try:
            search = f"%{query}%"
            self.cursor.execute(
                """SELECT * FROM users 
                WHERE telegram_id LIKE ? OR username LIKE ? OR full_name LIKE ? OR phone LIKE ?
                ORDER BY registered_at DESC
                LIMIT 20""",
                (search, search, search, search)
            )
            return [dict(row) for row in self.cursor.fetchall()]
        except Exception as e:
            logger.error(f"Search users error: {e}")
            return []
    
    def close(self):
        """Database ni yopish"""
        try:
            if hasattr(self, 'conn') and self.conn:
                self.conn.close()
                logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database: {e}")

# ==================== BOT HANDLER ====================
# ==================== BOT HANDLER ====================
class BotHandler:
    def __init__(self, db: Database):
        self.db = db
        self.selected_days = {}
        self.user_data = {}
    
    def get_text(self, user_id: int, key: str, **kwargs) -> str:
        """Foydalanuvchi tilidagi matnni qaytarish"""
        # Agar user_id mavjud bo'lmasa, o'zbek tilini ishlatish
        if not user_id:
            text = LANGUAGES['uz'].get(key, key)
            if kwargs:
                try:
                    text = text.format(**kwargs)
                except:
                    pass
            return text
            
        lang = self.db.get_user_language(user_id)
        text = LANGUAGES.get(lang, LANGUAGES['uz']).get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except:
                pass
        return text
    
    def get_main_keyboard(self, user_id: int):
        """Asosiy menyu keyboard"""
        keyboard = [
            [self.get_text(user_id, 'reminder'), self.get_text(user_id, 'expense'), self.get_text(user_id, 'income')],
            [self.get_text(user_id, 'debts'), self.get_text(user_id, 'report'), self.get_text(user_id, 'budget')],
            [self.get_text(user_id, 'settings'), self.get_text(user_id, 'help')]
        ]
        
        user = self.db.get_user_by_id(user_id)
        if user and user.get('is_admin'):
            keyboard.append(["👑 ADMIN PANEL"])
        
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_back_keyboard(self, user_id: int):
        """Orqaga keyboard"""
        return ReplyKeyboardMarkup([[self.get_text(user_id, 'back')]], resize_keyboard=True)
    
    def get_cancel_keyboard(self, user_id: int):
        """Bekor qilish keyboard"""
        return ReplyKeyboardMarkup([[self.get_text(user_id, 'cancel')]], resize_keyboard=True)
    
    def get_language_keyboard(self):
        """Til tanlash keyboard"""
        keyboard = []
        # To'g'ri tillar nomlari bilan
        languages = [
            ('🇺🇿 Uzbek', 'uz'),
            ('🇬🇧 English', 'en'),
            ('🇷🇺 Русский', 'ru')
        ]
        for lang_name, lang_code in languages:
            keyboard.append([InlineKeyboardButton(lang_name, callback_data=f"lang_{lang_code}")])
        return InlineKeyboardMarkup(keyboard)
    
    def get_reminder_type_keyboard(self, user_id: int):
        """Eslatma turi keyboard"""
        keyboard = [
            [self.get_text(user_id, 'today'), self.get_text(user_id, 'daily')],
            [self.get_text(user_id, 'weekly'), self.get_text(user_id, 'custom')],
            [self.get_text(user_id, 'other_date'), self.get_text(user_id, 'cancel')],
            [self.get_text(user_id, 'back')]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_weekdays_selection_keyboard(self, user_id: int, telegram_id: int):
        """Hafta kunlarini tanlash uchun inline keyboard"""
        selected = self.selected_days.get(telegram_id, set())
        
        keyboard = []
        row = []
        
        for i in range(7):
            day_name = self.get_text(user_id, WEEKDAYS_SHORT[i].lower())
            if i in selected:
                button = InlineKeyboardButton(f"✅ {day_name}", callback_data=f"wday_{i}")
            else:
                button = InlineKeyboardButton(f"⬜ {day_name}", callback_data=f"wday_{i}")
            
            row.append(button)
            
            if len(row) == 4:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton(self.get_text(user_id, 'confirm'), callback_data="weekday_done")])
        keyboard.append([InlineKeyboardButton(self.get_text(user_id, 'cancel'), callback_data="weekday_cancel")])
        
        return InlineKeyboardMarkup(keyboard)
    
    def get_date_selection_keyboard(self, user_id: int):
        """Sana tanlash uchun keyboard"""
        today = date.today()
        keyboard = [
            [f"📅 {today.strftime('%d.%m.%Y')}"],
            [f"📅 {(today + timedelta(days=1)).strftime('%d.%m.%Y')}", f"📅 {(today + timedelta(days=2)).strftime('%d.%m.%Y')}"],
            [f"📅 {(today + timedelta(days=3)).strftime('%d.%m.%Y')}", f"📅 {(today + timedelta(days=4)).strftime('%d.%m.%Y')}"],
            [self.get_text(user_id, 'other_date'), self.get_text(user_id, 'cancel')],
            [self.get_text(user_id, 'back')]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_expense_categories_keyboard(self, user_id: int):
        """Xarajat kategoriyalari keyboard"""
        lang = self.db.get_user_language(user_id)
        categories = EXPENSE_CATEGORIES.get(lang, EXPENSE_CATEGORIES['uz'])
        
        keyboard = []
        row = []
        
        for i, category in enumerate(categories):
            if i % 2 == 0 and row:
                keyboard.append(row)
                row = []
            row.append(InlineKeyboardButton(category, callback_data=f"expense_cat_{category}"))
        
        if row:
            keyboard.append(row)
        
        return InlineKeyboardMarkup(keyboard)
    
    def get_income_categories_keyboard(self, user_id: int):
        """Daromad kategoriyalari keyboard"""
        lang = self.db.get_user_language(user_id)
        categories = INCOME_CATEGORIES.get(lang, INCOME_CATEGORIES['uz'])
        
        keyboard = []
        row = []
        
        for i, category in enumerate(categories):
            if i % 2 == 0 and row:
                keyboard.append(row)
                row = []
            row.append(InlineKeyboardButton(category, callback_data=f"income_cat_{category}"))
        
        if row:
            keyboard.append(row)
        
        return InlineKeyboardMarkup(keyboard)
    
    def get_budget_categories_keyboard(self, user_id: int):
        """Byudjet kategoriyalari keyboard"""
        lang = self.db.get_user_language(user_id)
        categories = EXPENSE_CATEGORIES.get(lang, EXPENSE_CATEGORIES['uz'])
        
        keyboard = []
        row = []
        
        for i, category in enumerate(categories[:8]):
            button = InlineKeyboardButton(category, callback_data=f"budget_cat_{category}")
            row.append(button)
            
            if len(row) == 2:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton(self.get_text(user_id, 'other_date'), callback_data="budget_cat_other")])
        keyboard.append([InlineKeyboardButton(self.get_text(user_id, 'cancel'), callback_data="budget_cancel")])
        
        return InlineKeyboardMarkup(keyboard)
    
    def get_settings_keyboard(self, user_id: int):
        """Sozlamalar keyboard"""
        keyboard = [
            [self.get_text(user_id, 'currency_set'), self.get_text(user_id, 'reminder_time')],
            [self.get_text(user_id, 'budget_threshold'), self.get_text(user_id, 'language')],
            [self.get_text(user_id, 'theme'), self.get_text(user_id, 'profile')],
            [self.get_text(user_id, 'back')]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_currency_keyboard(self, user_id: int):
        """Pul birligi keyboard"""
        keyboard = [
            ["💵 UZS (so'm)"],
            ["💵 USD ($)"],
            ["💶 EUR (€)"],
            ["💷 RUB (₽)"],
            [self.get_text(user_id, 'back')]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_threshold_keyboard(self, user_id: int):
        """Ogohlantirish chegarasi keyboard"""
        keyboard = [
            ["50%", "60%", "70%"],
            ["80%", "90%", "95%"],
            [self.get_text(user_id, 'back')]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_theme_keyboard(self, user_id: int):
        """Mavzu keyboard"""
        keyboard = [
            [self.get_text(user_id, 'light_theme')],
            [self.get_text(user_id, 'dark_theme')],
            [self.get_text(user_id, 'back')]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_language_select_keyboard(self, user_id: int):
        """Til tanlash keyboard"""
        keyboard = []
        # To'g'ri tillar nomlari bilan
        languages = [
            ('Uzbek', 'uz'),
            ('English', 'en'),
            ('Russian', 'ru')
        ]
        for lang_name, lang_code in languages:
            keyboard.append([InlineKeyboardButton(lang_name, callback_data=f"lang_{lang_code}")])
        keyboard.append([InlineKeyboardButton(self.get_text(user_id, 'back'), callback_data="lang_back")])
        return InlineKeyboardMarkup(keyboard)
    
    def get_debts_keyboard(self, user_id: int):
        """Qarzlar keyboard"""
        keyboard = [
            [self.get_text(user_id, 'debts_add'), self.get_text(user_id, 'debts_list')],
            [self.get_text(user_id, 'debts_close'), self.get_text(user_id, 'back')]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_admin_keyboard(self, user_id: int):
        """Admin panel keyboard"""
        keyboard = [
            ["📊 UMUMIY STATISTIKA", "👥 FOYDALANUVCHILAR"],
            ["🔍 QIDIRUV", "👤 PROFIL KO'RISH"],
            ["📢 XABAR YUBORISH", "🚫 BLOKLASH/OCHISH"],
            ["📋 ADMIN LOGLAR", self.get_text(user_id, 'back')]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    # ==================== START (TIL TANLASH) ====================
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command - til tanlash bilan boshlanadi"""
        user = update.effective_user
        
        # Callback query dan kelganini tekshirish
        if update.callback_query:
            await update.callback_query.answer()
            message = update.callback_query.message
        else:
            message = update.message
        
        if not message:
            return ConversationHandler.END
        
        # Foydalanuvchini tekshirish (bloklanganmi?)
        db_user = self.db.get_user_by_telegram_id(user.id)
        if db_user and db_user.get('is_blocked'):
            await message.reply_text(
                "❌ Siz botdan foydalanish imkoniyatidan mahrum qilingansiz.\n"
                "Batafsil ma'lumot uchun admin bilan bog'lanishingiz mumkin."
            )
            return ConversationHandler.END
        
        # Agar foydalanuvchi allaqachon til tanlagan bo'lsa, to'g'ridan-to'g'ri menyuga o'tish
        if db_user and db_user.get('language'):
            user_id = db_user['id']
            welcome_text = self.get_text(user_id, 'welcome', name=user.full_name)
            await message.reply_text(
                welcome_text,
                reply_markup=self.get_main_keyboard(user_id),
                parse_mode=ParseMode.MARKDOWN
            )
            return MAIN_MENU
        
        # Yangi foydalanuvchi - til tanlash
        await message.reply_text(
            "🇺🇿 Iltimos, tilni tanlang:\n"
            "🇷🇺 Пожалуйста, выберите язык:\n"
            "🇬🇧 Please select language:",
            reply_markup=self.get_language_keyboard()
        )
        return LANG_SELECT
    
    async def language_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Til tanlangandan keyin"""
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        lang_code = query.data.replace("lang_", "")
        
        # Foydalanuvchini yaratish
        db_user = self.db.get_or_create_user(
            telegram_id=user.id,
            username=user.username or "",
            full_name=user.full_name or "",
            language=lang_code
        )
        
        user_id = db_user['id']
        
        # Sozlamalarni yangilash
        self.db.update_user_setting(user_id, 'language', lang_code)
        self.db.update_user_setting(user_id, 'currency', LANGUAGES[lang_code]['currency'])
        
        welcome_text = self.get_text(user_id, 'welcome', name=user.full_name)
        
        await query.message.delete()
        await query.message.reply_text(
            welcome_text,
            reply_markup=self.get_main_keyboard(user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        return MAIN_MENU
    
    # ==================== MAIN MENU HANDLER ====================
    async def main_menu_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Asosiy menyu handler"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if not user_id:
            return await self.start(update, context)
        
        # Orqaga
        if text == self.get_text(user_id, 'back'):
            await update.message.reply_text(
                self.get_text(user_id, 'main_menu'),
                reply_markup=self.get_main_keyboard(user_id)
            )
            return MAIN_MENU
        
        # Menu tanlash
        if text == self.get_text(user_id, 'reminder'):
            return await self.reminder_menu(update, user_id)
        elif text == self.get_text(user_id, 'expense'):
            return await self.expense_menu(update, user_id)
        elif text == self.get_text(user_id, 'income'):
            return await self.income_menu(update, user_id)
        elif text == self.get_text(user_id, 'debts'):
            return await self.debts_menu(update, user_id)
        elif text == self.get_text(user_id, 'report'):
            return await self.show_report(update, user_id)
        elif text == self.get_text(user_id, 'budget'):
            return await self.budget_menu(update, user_id)
        elif text == self.get_text(user_id, 'settings'):
            return await self.settings_menu(update, user_id)
        elif text == self.get_text(user_id, 'help'):
            return await self.show_help(update, user_id)
        elif text == "👑 ADMIN PANEL" and user.id in ADMIN_IDS:
            return await self.admin_menu(update, user_id)
        
        await update.message.reply_text(
            self.get_text(user_id, 'invalid_input'),
            reply_markup=self.get_main_keyboard(user_id)
        )
        return MAIN_MENU
    
    # ==================== CALLBACK HANDLER ====================
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Callback query handler"""
        query = update.callback_query
        await query.answer()
    
        user = update.effective_user
        data = query.data
    
    # Foydalanuvchi ID sini olish
        db_user = self.db.get_user_by_telegram_id(user.id)
        
        # Agar foydalanuvchi topilmasa, yangi yaratish
        if not db_user:
            # Yangi foydalanuvchini yaratish
            db_user = self.db.get_or_create_user(
                telegram_id=user.id,
                username=user.username or "",
                full_name=user.full_name or "",
                language='uz'  # Default
            )
        
        user_id = db_user['id']
    
    # Til tanlash
        if data.startswith("lang_"):
            if data == "lang_back":
                await query.message.delete()
                return await self.start(update, context)
                
            lang_code = data.replace("lang_", "")
        
        # Foydalanuvchini yangilash
            self.db.get_or_create_user(
                telegram_id=user.id,
                username=user.username or "",
                full_name=user.full_name or "",
                language=lang_code
            )
        
            self.db.update_user_setting(user_id, 'language', lang_code)
            self.db.update_user_setting(user_id, 'currency', LANGUAGES[lang_code]['currency'])
        
            welcome_text = self.get_text(user_id, 'welcome', name=user.full_name)
        
            await query.message.delete()
            await query.message.reply_text(
                welcome_text,
                reply_markup=self.get_main_keyboard(user_id),
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
    
    # Hafta kunlari tanlash
        elif data.startswith("wday_") or data in ["weekday_done", "weekday_cancel"]:
        # Bu yerda update ni qaytarish kerak, context emas
            return await self.add_reminder_days_callback(update, context)
    
    # Xarajat kategoriya tanlash
        elif data.startswith("expense_cat_"):
            return await self.add_expense_cat_callback(update, context)
    
    # Daromad kategoriya tanlash
        elif data.startswith("income_cat_"):
            return await self.add_income_cat_callback(update, context)
    
    # Byudjet kategoriya tanlash
        elif data.startswith("budget_cat_"):
            return await self.add_budget_cat_callback(update, context)
    
    # Byudjet tahrirlash
        elif data.startswith("budget_edit_"):
            return await self.edit_budget_callback(update, context)
    
    # Byudjet o'chirish
        elif data.startswith("budget_del_"):
            return await self.delete_budget_callback(update, context)
    
        elif data == "budget_cancel":
            await query.message.delete()
            return await self.budget_menu(update, user_id)
    
        return MAIN_MENU
    
    # ==================== REMINDER METHODS ====================
    async def reminder_menu(self, update: Update, user_id: int):
        """Eslatmalar menyusi"""
        keyboard = [
            [self.get_text(user_id, 'reminder_list'), self.get_text(user_id, 'reminder_add')],
            [self.get_text(user_id, 'reminder_delete'), self.get_text(user_id, 'back')]
        ]
        await update.message.reply_text(
            "🔔 *ESLATMALAR*",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        return REMINDER_MENU
    
    async def reminder_menu_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Eslatmalar menyusi handler"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            await update.message.reply_text(
                self.get_text(user_id, 'main_menu'),
                reply_markup=self.get_main_keyboard(user_id)
            )
            return MAIN_MENU
        
        if text == self.get_text(user_id, 'reminder_list'):
            return await self.show_reminders(update, user_id)
        elif text == self.get_text(user_id, 'reminder_add'):
            return await self.add_reminder_step1(update, user_id)
        elif text == self.get_text(user_id, 'reminder_delete'):
            return await self.delete_reminder_start(update, user_id)
        
        return REMINDER_MENU
    
    async def add_reminder_step1(self, update: Update, user_id: int):
        """1-qadam: Eslatma nomi"""
        await update.message.reply_text(
            f"📝 *{self.get_text(user_id, 'reminder_add')}*\n\n"
            f"1️⃣ *{self.get_text(user_id, 'title')}:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard(user_id)
        )
        return ADD_REMINDER_NAME
    
    async def add_reminder_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Eslatma nomini qabul qilish"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            return await self.reminder_menu(update, user_id)
        
        context.user_data['reminder_title'] = text
        
        await update.message.reply_text(
            f"2️⃣ *{self.get_text(user_id, 'repeat_type')}:*",
            reply_markup=self.get_reminder_type_keyboard(user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        return ADD_REMINDER_TYPE
    
    async def add_reminder_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Eslatma turini qabul qilish"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        telegram_id = user.id
        
        if text == self.get_text(user_id, 'back'):
            return await self.reminder_menu(update, user_id)
        elif text == self.get_text(user_id, 'cancel'):
            context.user_data.clear()
            return await self.reminder_menu(update, user_id)
        
        if text == self.get_text(user_id, 'today'):
            context.user_data['reminder_repeat'] = 'none'
            context.user_data['reminder_date'] = date.today()
            await update.message.reply_text(
                f"3️⃣ *{self.get_text(user_id, 'time')} (HH:MM):*",
                reply_markup=self.get_back_keyboard(user_id),
                parse_mode=ParseMode.MARKDOWN
            )
            return ADD_REMINDER_TIME
        elif text == self.get_text(user_id, 'daily'):
            context.user_data['reminder_repeat'] = 'daily'
            context.user_data['reminder_date'] = date.today()
            await update.message.reply_text(
                f"3️⃣ *{self.get_text(user_id, 'time')} (HH:MM):*",
                reply_markup=self.get_back_keyboard(user_id),
                parse_mode=ParseMode.MARKDOWN
            )
            return ADD_REMINDER_TIME
        elif text == self.get_text(user_id, 'weekly'):
            context.user_data['reminder_repeat'] = 'weekly'
            context.user_data['reminder_date'] = date.today()
            await update.message.reply_text(
                f"3️⃣ *{self.get_text(user_id, 'time')} (HH:MM):*",
                reply_markup=self.get_back_keyboard(user_id),
                parse_mode=ParseMode.MARKDOWN
            )
            return ADD_REMINDER_TIME
        elif text == self.get_text(user_id, 'custom'):
            self.selected_days[telegram_id] = set()
            await update.message.reply_text(
                f"📆 *{self.get_text(user_id, 'select_days')}:*",
                reply_markup=self.get_weekdays_selection_keyboard(user_id, telegram_id),
                parse_mode=ParseMode.MARKDOWN
            )
            return ADD_REMINDER_DAYS
        elif text == self.get_text(user_id, 'other_date'):
            await update.message.reply_text(
                f"📅 *{self.get_text(user_id, 'select_date')}:*",
                reply_markup=self.get_date_selection_keyboard(user_id),
                parse_mode=ParseMode.MARKDOWN
            )
            return ADD_REMINDER_DATE
        
        return ADD_REMINDER_TYPE
    
    async def add_reminder_days_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Hafta kunlarini tanlash callback"""
        query = update.callback_query
        user = update.effective_user
        user_id = self.db.get_user_id(user.id)
        telegram_id = user.id
        data = query.data
    
        if data.startswith("wday_"):
            try:
                day = int(data.split("_")[1])
            
                if telegram_id not in self.selected_days:
                    self.selected_days[telegram_id] = set()
            
                if day in self.selected_days[telegram_id]:
                    self.selected_days[telegram_id].remove(day)
                else:
                    self.selected_days[telegram_id].add(day)
            
                await query.message.edit_reply_markup(
                    reply_markup=self.get_weekdays_selection_keyboard(user_id, telegram_id)
                )
            except:
                pass
            return ADD_REMINDER_DAYS
    
        elif data == "weekday_done":
            days = self.selected_days.get(telegram_id, set())
        
            if not days:
                await query.answer(self.get_text(user_id, 'select_at_least_one'), show_alert=True)
                return ADD_REMINDER_DAYS
        
            context.user_data['reminder_repeat'] = 'custom'
            context.user_data['reminder_days'] = list(days)
            context.user_data['reminder_date'] = date.today()
        
            self.selected_days.pop(telegram_id, None)
        
            await query.message.delete()
            await query.message.reply_text(
                f"3️⃣ *{self.get_text(user_id, 'time')} (HH:MM):*",
                reply_markup=self.get_back_keyboard(user_id),
                parse_mode=ParseMode.MARKDOWN
            )
            return ADD_REMINDER_TIME
    
        elif data == "weekday_cancel":
            self.selected_days.pop(telegram_id, None)
            context.user_data.clear()
            await query.message.delete()
        # reminder_menu ga qaytish
            keyboard = [
                [self.get_text(user_id, 'reminder_list'), self.get_text(user_id, 'reminder_add')],
                [self.get_text(user_id, 'reminder_delete'), self.get_text(user_id, 'back')]
            ]
            await query.message.reply_text(
                "🔔 *ESLATMALAR*",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
                parse_mode=ParseMode.MARKDOWN
            )
            return REMINDER_MENU
    
        return ADD_REMINDER_DAYS
    
    async def add_reminder_date(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Sanani qabul qilish"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            return await self.reminder_menu(update, user_id)
        elif text == self.get_text(user_id, 'cancel'):
            context.user_data.clear()
            return await self.reminder_menu(update, user_id)
        
        if text.startswith("📅 "):
            try:
                date_str = text.replace("📅 ", "")
                reminder_date = datetime.strptime(date_str, '%d.%m.%Y').date()
                context.user_data['reminder_date'] = reminder_date
                context.user_data['reminder_repeat'] = 'none'
                await update.message.reply_text(
                    f"3️⃣ *{self.get_text(user_id, 'time')} (HH:MM):*",
                    reply_markup=self.get_back_keyboard(user_id),
                    parse_mode=ParseMode.MARKDOWN
                )
                return ADD_REMINDER_TIME
            except:
                await update.message.reply_text(
                    self.get_text(user_id, 'invalid_date'),
                    reply_markup=self.get_date_selection_keyboard(user_id)
                )
        elif text == self.get_text(user_id, 'other_date'):
            await update.message.reply_text(
                f"📅 *{self.get_text(user_id, 'enter_date')} (DD.MM.YYYY):*",
                reply_markup=self.get_back_keyboard(user_id),
                parse_mode=ParseMode.MARKDOWN
            )
            return ADD_REMINDER_DATE
        
        return ADD_REMINDER_DATE
    
    async def add_reminder_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Vaqtni qabul qilish"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            # Hafta kunlarini tanlashdan keyin orqaga qaytish
            if context.user_data.get('reminder_repeat') == 'custom' and 'reminder_days' in context.user_data:
                telegram_id = user.id
                self.selected_days[telegram_id] = set(context.user_data['reminder_days'])
                await update.message.reply_text(
                    f"📆 *{self.get_text(user_id, 'select_days')}:*",
                    reply_markup=self.get_weekdays_selection_keyboard(user_id, telegram_id),
                    parse_mode=ParseMode.MARKDOWN
                )
                return ADD_REMINDER_DAYS
            return await self.reminder_menu(update, user_id)
        
        try:
            time_obj = datetime.strptime(text, "%H:%M").time()
            context.user_data['reminder_time'] = text
            
            await update.message.reply_text(
                f"4️⃣ *{self.get_text(user_id, 'description')}* (ixtiyoriy):\n"
                f"{self.get_text(user_id, 'or_skip')}",
                reply_markup=self.get_back_keyboard(user_id),
                parse_mode=ParseMode.MARKDOWN
            )
            return ADD_REMINDER_DESC
        except ValueError:
            await update.message.reply_text(
                self.get_text(user_id, 'invalid_time'),
                reply_markup=self.get_back_keyboard(user_id)
            )
            return ADD_REMINDER_TIME
    
    async def add_reminder_desc(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Tavsifni qabul qilish va eslatmani saqlash"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            return await self.reminder_menu(update, user_id)
        
        description = "" if text.lower() in [self.get_text(user_id, 'no').lower(), 'no', 'yo\'q', 'net'] else text
        
        # Eslatmani saqlash
        title = context.user_data.get('reminder_title')
        repeat_type = context.user_data.get('reminder_repeat', 'none')
        repeat_days = context.user_data.get('reminder_days')
        reminder_date = context.user_data.get('reminder_date', date.today())
        time_str = context.user_data.get('reminder_time')
        
        # Validatsiya
        if not title or not time_str:
            await update.message.reply_text(
                self.get_text(user_id, 'error') + " - Ma'lumotlar yetarli emas",
                reply_markup=self.get_main_keyboard(user_id)
            )
            context.user_data.clear()
            return MAIN_MENU
        
        try:
            time_obj = datetime.strptime(time_str, "%H:%M").time()
            reminder_time = datetime.combine(reminder_date, time_obj, tzinfo=TIMEZONE)
            
            success = self.db.add_reminder(
                user_id=user_id,
                title=title,
                reminder_time=reminder_time,
                description=description,
                repeat_type=repeat_type,
                repeat_days=repeat_days
            )
            
            if success:
                await update.message.reply_text(
                    f"✅ *{self.get_text(user_id, 'reminder_saved')}!*\n\n"
                    f"📌 *{title}*\n"
                    f"⏰ {reminder_time.strftime('%d.%m.%Y %H:%M')}",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=self.get_main_keyboard(user_id)
                )
            else:
                await update.message.reply_text(
                    self.get_text(user_id, 'error'),
                    reply_markup=self.get_main_keyboard(user_id)
                )
        except Exception as e:
            logger.error(f"Reminder save error: {e}")
            await update.message.reply_text(
                self.get_text(user_id, 'error'),
                reply_markup=self.get_main_keyboard(user_id)
            )
        
        context.user_data.clear()
        return MAIN_MENU
    
    async def show_reminders(self, update: Update, user_id: int):
        """Eslatmalarni ko'rsatish"""
        reminders = self.db.get_user_reminders(user_id)
        
        if not reminders:
            await update.message.reply_text(
                f"📭 *{self.get_text(user_id, 'no_reminders')}*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.get_main_keyboard(user_id)
            )
            return MAIN_MENU
        
        message = f"🔔 *{self.get_text(user_id, 'your_reminders')}:*\n\n"
        
        for i, reminder in enumerate(reminders[:10], 1):
            try:
                if reminder.get('repeat_type') != 'none':
                    next_time = reminder.get('next_reminder', reminder['reminder_time'])
                    if isinstance(next_time, datetime):
                        time_str = next_time.strftime('%d.%m.%Y %H:%M')
                    else:
                        time_str = "Noma'lum"
                    
                    if reminder['repeat_type'] == 'daily':
                        repeat = self.get_text(user_id, 'daily')
                    elif reminder['repeat_type'] == 'weekly':
                        repeat = self.get_text(user_id, 'weekly')
                    elif reminder['repeat_type'] == 'custom':
                        repeat = self.get_text(user_id, 'custom')
                    else:
                        repeat = reminder['repeat_type']
                else:
                    if isinstance(reminder['reminder_time'], datetime):
                        time_str = reminder['reminder_time'].strftime('%d.%m.%Y %H:%M')
                    else:
                        time_str = "Noma'lum"
                    repeat = "⏰ " + self.get_text(user_id, 'one_time')
                
                message += f"{i}. *{reminder['title']}*\n"
                message += f"   🕐 {time_str}\n"
                message += f"   {repeat}\n"
                message += f"   🆔 ID: `{reminder['id']}`\n"
                
                if reminder.get('description'):
                    message += f"   📝 {reminder['description']}\n"
                
                message += "\n"
            except Exception as e:
                logger.error(f"Error formatting reminder: {e}")
                continue
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_main_keyboard(user_id)
        )
        return MAIN_MENU
    
    async def delete_reminder_start(self, update: Update, user_id: int):
        """Eslatma o'chirish boshlash"""
        await update.message.reply_text(
            f"🗑️ *{self.get_text(user_id, 'delete_reminder')}*\n\n"
            f"{self.get_text(user_id, 'enter_id')}:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard(user_id)
        )
        return DELETE_REMINDER
    
    async def delete_reminder(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Eslatmani o'chirish"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            return await self.reminder_menu(update, user_id)
        
        try:
            reminder_id = int(text.strip())
            if self.db.delete_reminder(reminder_id, user_id):
                await update.message.reply_text(
                    f"✅ {self.get_text(user_id, 'reminder_deleted')}",
                    reply_markup=self.get_main_keyboard(user_id)
                )
            else:
                await update.message.reply_text(
                    self.get_text(user_id, 'not_found'),
                    reply_markup=self.get_main_keyboard(user_id)
                )
        except ValueError:
            await update.message.reply_text(
                self.get_text(user_id, 'invalid_input'),
                reply_markup=self.get_back_keyboard(user_id)
            )
            return DELETE_REMINDER
        
        return MAIN_MENU
    
    # ==================== EXPENSE METHODS ====================
    async def expense_menu(self, update: Update, user_id: int):
        """Xarajatlar menyusi"""
        keyboard = [
            [self.get_text(user_id, 'expense_add'), self.get_text(user_id, 'expense_list')],
            [self.get_text(user_id, 'expense_stats'), self.get_text(user_id, 'expense_trends')],
            [self.get_text(user_id, 'back')]
        ]
        await update.message.reply_text(
            "💰 *XARAJATLAR*",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        return EXPENSE_MENU
    
    async def expense_menu_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Xarajatlar menyusi handler"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            await update.message.reply_text(
                self.get_text(user_id, 'main_menu'),
                reply_markup=self.get_main_keyboard(user_id)
            )
            return MAIN_MENU
        
        if text == self.get_text(user_id, 'expense_add'):
            return await self.add_expense_step1(update, user_id)
        elif text == self.get_text(user_id, 'expense_list'):
            return await self.show_expenses(update, user_id)
        elif text == self.get_text(user_id, 'expense_stats'):
            return await self.show_expense_stats(update, user_id)
        elif text == self.get_text(user_id, 'expense_trends'):
            return await self.show_expense_trends(update, user_id)
        
        return EXPENSE_MENU
    
    async def add_expense_step1(self, update: Update, user_id: int):
        """1-qadam: Xarajat miqdori"""
        await update.message.reply_text(
            f"💰 *{self.get_text(user_id, 'expense_add')}*\n\n"
            f"1️⃣ *{self.get_text(user_id, 'amount')}:*\n"
            f"{self.get_text(user_id, 'amount_example')}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard(user_id)
        )
        return ADD_EXPENSE_AMOUNT
    
    async def add_expense_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Xarajat miqdorini qabul qilish"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            return await self.expense_menu(update, user_id)
        
        try:
            amount_str = text.replace(',', '.').upper()
            multiplier = 1
            
            if 'M' in amount_str:
                multiplier = 1000000
                amount_str = amount_str.replace('M', '')
            elif 'K' in amount_str:
                multiplier = 1000
                amount_str = amount_str.replace('K', '')
            
            amount = float(amount_str) * multiplier
            context.user_data['expense_amount'] = amount
            
            await update.message.reply_text(
                f"2️⃣ *{self.get_text(user_id, 'category')}:*",
                reply_markup=self.get_expense_categories_keyboard(user_id),
                parse_mode=ParseMode.MARKDOWN
            )
            return ADD_EXPENSE_CAT
        except ValueError:
            await update.message.reply_text(
                self.get_text(user_id, 'invalid_input'),
                reply_markup=self.get_back_keyboard(user_id)
            )
            return ADD_EXPENSE_AMOUNT
    
    async def add_expense_cat_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Xarajat kategoriyasini tanlash callback"""
        query = update.callback_query
        await query.answer()
    
        user = update.effective_user
        user_id = self.db.get_user_id(user.id)
        data = query.data
    
        if data.startswith("expense_cat_"):
            category = data.replace("expense_cat_", "")
            context.user_data['expense_category'] = category
        
            await query.message.delete()
            await query.message.reply_text(
                f"3️⃣ *{self.get_text(user_id, 'description')}* (ixtiyoriy):\n"
                f"{self.get_text(user_id, 'or_skip')}",
                reply_markup=self.get_back_keyboard(user_id),
                parse_mode=ParseMode.MARKDOWN
            )
            return ADD_EXPENSE_DESC
    
        return EXPENSE_MENU
    
    async def add_expense_desc(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Xarajat tavsifini qabul qilish va saqlash"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
    
        if text == self.get_text(user_id, 'back'):
            return await self.expense_menu(update, user_id)
    
        # Tavsifni aniqlash - agar foydalanuvchi "no" yozsa yoki tavsif bo'sh bo'lsa
        description = ""
        if text.lower() not in [self.get_text(user_id, 'no').lower(), 'no', 'yo\'q', 'net', '']:
            description = text
    
        amount = context.user_data.get('expense_amount')
        category = context.user_data.get('expense_category')
    
        # Validatsiya
        if not amount or not category:
            await update.message.reply_text(
                self.get_text(user_id, 'error') + " - Ma'lumotlar yetarli emas",
                reply_markup=self.get_main_keyboard(user_id)
            )
            context.user_data.clear()
            return MAIN_MENU
    
        success = self.db.add_expense(
            user_id=user_id,
            amount=amount,
            category=category,
            description=description
        )

        if success:
            settings = self.db.get_user_settings(user_id)
            symbol = CURRENCY_SYMBOLS.get(settings.get('currency', 'UZS'), 'so\'m')
        
            await update.message.reply_text(
                f"✅ *{self.get_text(user_id, 'expense_saved')}!*\n\n"
                f"💰 {amount:,.0f} {symbol}\n"
                f"🏷️ {category}\n"
                f"{'📝 ' + description if description else ''}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.get_main_keyboard(user_id)
            )
        
        # Byudjetni tekshirish
            budgets = self.db.get_user_budgets(user_id)
            for budget in budgets:
                if budget['category'] == category and budget['monthly_limit'] > 0:
                    alerts = self.db.check_budget_alerts(
                        user_id, category, 
                        budget['current_spent'], 
                        budget['monthly_limit']
                    )
                
                    for alert in alerts:
                        if alert.startswith('threshold'):
                            percentage = alert.split(':')[1]
                            await update.message.reply_text(
                                f"⚠️ *{self.get_text(user_id, 'budget_warning')}!*\n\n"
                                f"📂 {category}\n"
                                f"{self.get_text(user_id, 'limit_reached')} {percentage}%!\n"
                                f"💰 {budget['current_spent']:,.0f} / {budget['monthly_limit']:,.0f} {symbol}",
                                parse_mode=ParseMode.MARKDOWN
                            )
                        elif alert.startswith('exceeded'):
                            over = alert.split(':')[1]
                            await update.message.reply_text(
                                f"🔴 *{self.get_text(user_id, 'limit_exceeded')}!*\n\n"
                                f"📂 {category}\n"
                                f"{self.get_text(user_id, 'over_by')} {over} {symbol}!\n"
                                f"💰 {budget['current_spent']:,.0f} / {budget['monthly_limit']:,.0f} {symbol}",
                                parse_mode=ParseMode.MARKDOWN
                            )
        else:
            await update.message.reply_text(
                self.get_text(user_id, 'error'),
                reply_markup=self.get_main_keyboard(user_id)
            )
    
        context.user_data.clear()
        return MAIN_MENU
    
    async def show_expenses(self, update: Update, user_id: int):
        """Xarajatlarni ko'rsatish"""
        stats = self.db.get_expense_statistics(user_id, "month")
        settings = self.db.get_user_settings(user_id)
        symbol = CURRENCY_SYMBOLS.get(settings.get('currency', 'UZS'), 'so\'m')
        
        if stats['general']['total'] == 0:
            await update.message.reply_text(
                f"📭 {self.get_text(user_id, 'no_expenses')}",
                reply_markup=self.get_main_keyboard(user_id)
            )
            return MAIN_MENU
        
        message = f"📊 *{self.get_text(user_id, 'expense_list')}*\n\n"
        
        for cat in stats['categories']:
            message += f"• {cat['category']}: *{cat['total']:,.0f}* {symbol} ({cat['count']} ta)\n"
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_main_keyboard(user_id)
        )
        return MAIN_MENU
    
    async def show_expense_stats(self, update: Update, user_id: int):
        """Xarajatlar statistikasi"""
        stats = self.db.get_expense_statistics(user_id, "month")
        settings = self.db.get_user_settings(user_id)
        symbol = CURRENCY_SYMBOLS.get(settings.get('currency', 'UZS'), 'so\'m')
        
        month_name = MONTHS_UZ.get(date.today().month, str(date.today().month))
        
        message = f"""
📊 *{self.get_text(user_id, 'expense_stats')}*
📅 *{month_name} {date.today().year}*

💰 *{self.get_text(user_id, 'general')}:*
• {self.get_text(user_id, 'total')}: *{stats['general']['total']:,.0f}* {symbol}
• {self.get_text(user_id, 'count')}: *{stats['general']['count']}* ta
• {self.get_text(user_id, 'average')}: *{stats['general']['average']:,.0f}* {symbol}
• {self.get_text(user_id, 'max')}: *{stats['general']['max']:,.0f}* {symbol}
• {self.get_text(user_id, 'min')}: *{stats['general']['min']:,.0f}* {symbol}

📂 *{self.get_text(user_id, 'categories')}:*\n
"""
        
        for cat in stats['categories'][:5]:
            percentage = (cat['total'] / stats['general']['total'] * 100) if stats['general']['total'] > 0 else 0
            bar = "█" * int(percentage / 10) + "░" * (10 - int(percentage / 10))
            message += f"• {cat['category']}\n"
            message += f"  `{bar}` {percentage:.1f}%\n"
            message += f"  💰 {cat['total']:,.0f} {symbol} ({cat['count']} ta)\n\n"
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_main_keyboard(user_id)
        )
        return MAIN_MENU
    
    async def show_expense_trends(self, update: Update, user_id: int):
        """Xarajatlar trendlari"""
        trends = self.db.get_expense_trends(user_id, 6)
        settings = self.db.get_user_settings(user_id)
        symbol = CURRENCY_SYMBOLS.get(settings.get('currency', 'UZS'), 'so\'m')
        
        message = f"📈 *{self.get_text(user_id, 'expense_trends')}*\n\n"
        
        for month, amount in trends.items():
            if amount > 0:
                bar_length = min(int(amount / 100000), 20)
                bar = "█" * bar_length if bar_length > 0 else "░"
                message += f"• {month}: *{amount:,.0f}* {symbol}\n"
                message += f"  `{bar}`\n\n"
            else:
                message += f"• {month}: *0* {symbol}\n"
                message += "  `░`\n\n"
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_main_keyboard(user_id)
        )
        return MAIN_MENU
    
    # ==================== INCOME METHODS ====================
    async def income_menu(self, update: Update, user_id: int):
        """Daromadlar menyusi"""
        keyboard = [
            [self.get_text(user_id, 'income_add'), self.get_text(user_id, 'income_list')],
            [self.get_text(user_id, 'back')]
        ]
        await update.message.reply_text(
            "💵 *DAROMADLAR*",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        return INCOME_MENU
    
    async def income_menu_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Daromadlar menyusi handler"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            await update.message.reply_text(
                self.get_text(user_id, 'main_menu'),
                reply_markup=self.get_main_keyboard(user_id)
            )
            return MAIN_MENU
        
        if text == self.get_text(user_id, 'income_add'):
            return await self.add_income_step1(update, user_id)
        elif text == self.get_text(user_id, 'income_list'):
            return await self.show_income(update, user_id)
        
        return INCOME_MENU
    
    async def add_income_step1(self, update: Update, user_id: int):
        """1-qadam: Daromad miqdori"""
        await update.message.reply_text(
            f"💵 *{self.get_text(user_id, 'income_add')}*\n\n"
            f"1️⃣ *{self.get_text(user_id, 'amount')}:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard(user_id)
        )
        return ADD_INCOME_AMOUNT
    
    async def add_income_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Daromad miqdorini qabul qilish"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            return await self.income_menu(update, user_id)
        
        try:
            amount_str = text.replace(',', '.').upper()
            multiplier = 1
            
            if 'M' in amount_str:
                multiplier = 1000000
                amount_str = amount_str.replace('M', '')
            elif 'K' in amount_str:
                multiplier = 1000
                amount_str = amount_str.replace('K', '')
            
            amount = float(amount_str) * multiplier
            context.user_data['income_amount'] = amount
            
            await update.message.reply_text(
                f"2️⃣ *{self.get_text(user_id, 'category')}:*",
                reply_markup=self.get_income_categories_keyboard(user_id),
                parse_mode=ParseMode.MARKDOWN
            )
            return ADD_INCOME_CAT
        except ValueError:
            await update.message.reply_text(
                self.get_text(user_id, 'invalid_input'),
                reply_markup=self.get_back_keyboard(user_id)
            )
            return ADD_INCOME_AMOUNT
    
    async def add_income_cat_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Daromad kategoriyasini tanlash callback"""
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        user_id = self.db.get_user_id(user.id)
        data = query.data
        
        if data.startswith("income_cat_"):
            category = data.replace("income_cat_", "")
            context.user_data['income_category'] = category
            
            await query.message.delete()
            await query.message.reply_text(
                f"3️⃣ *{self.get_text(user_id, 'description')}* (ixtiyoriy):\n"
                f"{self.get_text(user_id, 'or_skip')}",
                reply_markup=self.get_back_keyboard(user_id),
                parse_mode=ParseMode.MARKDOWN
            )
            return ADD_INCOME_DESC
        
        return INCOME_MENU
    
    async def add_income_desc(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Daromad tavsifini qabul qilish va saqlash"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            return await self.income_menu(update, user_id)
        
        # Tavsifni aniqlash - agar foydalanuvchi "no" yozsa yoki tavsif bo'sh bo'lsa
        description = ""
        if text.lower() not in [self.get_text(user_id, 'no').lower(), 'no', 'yo\'q', 'net', '']:
            description = text
        
        amount = context.user_data.get('income_amount')
        category = context.user_data.get('income_category')
        
        # Validatsiya
        if not amount or not category:
            await update.message.reply_text(
                self.get_text(user_id, 'error') + " - Ma'lumotlar yetarli emas",
                reply_markup=self.get_main_keyboard(user_id)
            )
            context.user_data.clear()
            return MAIN_MENU
        
        success = self.db.add_income(
            user_id=user_id,
            amount=amount,
            category=category,
            description=description
        )
        
        if success:
            settings = self.db.get_user_settings(user_id)
            symbol = CURRENCY_SYMBOLS.get(settings.get('currency', 'UZS'), 'so\'m')
            
            await update.message.reply_text(
                f"✅ *{self.get_text(user_id, 'income_saved')}!*\n\n"
                f"💵 +{amount:,.0f} {symbol}\n"
                f"🏷️ {category}\n"
                f"{'📝 ' + description if description else ''}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.get_main_keyboard(user_id)
            )
        else:
            await update.message.reply_text(
                self.get_text(user_id, 'error'),
                reply_markup=self.get_main_keyboard(user_id)
            )
        
        context.user_data.clear()
        return MAIN_MENU
    
    async def show_income(self, update: Update, user_id: int):
        """Daromadlarni ko'rsatish"""
        stats = self.db.get_income_statistics(user_id)
        settings = self.db.get_user_settings(user_id)
        symbol = CURRENCY_SYMBOLS.get(settings.get('currency', 'UZS'), 'so\'m')
        
        if stats['total'] == 0:
            await update.message.reply_text(
                f"📭 {self.get_text(user_id, 'no_income')}",
                reply_markup=self.get_main_keyboard(user_id)
            )
            return MAIN_MENU
        
        message = f"📊 *{self.get_text(user_id, 'income_list')}*\n\n"
        
        for cat in stats['categories']:
            message += f"• {cat['category']}: *{cat['total']:,.0f}* {symbol}\n"
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_main_keyboard(user_id)
        )
        return MAIN_MENU
    
    # ==================== DEBT METHODS ====================
    async def debts_menu(self, update: Update, user_id: int):
        """Qarzlar menyusi"""
        await update.message.reply_text(
            "💸 *QARZLAR*",
            reply_markup=self.get_debts_keyboard(user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        return DEBTS_MENU
    
    async def debts_menu_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Qarzlar menyusi handler"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            await update.message.reply_text(
                self.get_text(user_id, 'main_menu'),
                reply_markup=self.get_main_keyboard(user_id)
            )
            return MAIN_MENU
        
        if text == self.get_text(user_id, 'debts_add'):
            return await self.add_debt_step1(update, user_id)
        elif text == self.get_text(user_id, 'debts_list'):
            return await self.show_debts(update, user_id)
        elif text == self.get_text(user_id, 'debts_close'):
            return await self.close_debt_start(update, user_id)
        
        return DEBTS_MENU
    
    async def add_debt_step1(self, update: Update, user_id: int):
        """1-qadam: Qarz olgan/bergan odam ismi"""
        await update.message.reply_text(
            f"💸 *{self.get_text(user_id, 'debts_add')}*\n\n"
            f"1️⃣ *{self.get_text(user_id, 'person')}:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard(user_id)
        )
        return ADD_DEBT_NAME
    
    async def add_debt_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Qarz olgan/bergan odam ismini qabul qilish"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            return await self.debts_menu(update, user_id)
        
        context.user_data['debt_person'] = text
        
        await update.message.reply_text(
            f"2️⃣ *{self.get_text(user_id, 'amount')}:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard(user_id)
        )
        return ADD_DEBT_AMOUNT
    
    async def add_debt_amount(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Qarz miqdorini qabul qilish"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            return await self.debts_menu(update, user_id)
        
        try:
            amount = float(text.replace(',', '.'))
            context.user_data['debt_amount'] = amount
            
            keyboard = [
                [self.get_text(user_id, 'gave'), self.get_text(user_id, 'took')],
                [self.get_text(user_id, 'back')]
            ]
            
            await update.message.reply_text(
                f"3️⃣ *{self.get_text(user_id, 'debt_type')}:*",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
                parse_mode=ParseMode.MARKDOWN
            )
            return ADD_DEBT_TYPE
        except ValueError:
            await update.message.reply_text(
                self.get_text(user_id, 'invalid_input'),
                reply_markup=self.get_back_keyboard(user_id)
            )
            return ADD_DEBT_AMOUNT
    
    async def add_debt_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Qarz turini qabul qilish"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            return await self.debts_menu(update, user_id)
        
        if text == self.get_text(user_id, 'gave'):
            context.user_data['debt_type'] = 'gave'
        elif text == self.get_text(user_id, 'took'):
            context.user_data['debt_type'] = 'took'
        else:
            await update.message.reply_text(
                self.get_text(user_id, 'invalid_input'),
                reply_markup=self.get_back_keyboard(user_id)
            )
            return ADD_DEBT_TYPE
        
        await update.message.reply_text(
            f"4️⃣ *{self.get_text(user_id, 'description')}* (ixtiyoriy):\n"
            f"{self.get_text(user_id, 'or_skip')}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard(user_id)
        )
        return ADD_DEBT_DESC
    
    async def add_debt_desc(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Qarz tavsifini qabul qilish va saqlash"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
    
        if text == self.get_text(user_id, 'back'):
            return await self.debts_menu(update, user_id)
    
        # Tavsifni aniqlash - agar foydalanuvchi "no" yozsa yoki tavsif bo'sh bo'lsa
        description = ""
        if text.lower() not in [self.get_text(user_id, 'no').lower(), 'no', 'yo\'q', 'net', '']:
            description = text
    
        person = context.user_data.get('debt_person')
        amount = context.user_data.get('debt_amount')
        debt_type = context.user_data.get('debt_type')
    
        # Validatsiya
        if not person or not amount or not debt_type:
            await update.message.reply_text(
                self.get_text(user_id, 'error') + " - Ma'lumotlar yetarli emas",
                reply_markup=self.get_main_keyboard(user_id)
            )
            context.user_data.clear()
            return MAIN_MENU
    
        success = self.db.add_debt(
            user_id=user_id,
            person_name=person,
            amount=amount,
            debt_type=debt_type,
            description=description
        )
    
        if success:
            type_text = self.get_text(user_id, 'gave') if debt_type == 'gave' else self.get_text(user_id, 'took')
            await update.message.reply_text(
                f"✅ *{self.get_text(user_id, 'debt_saved')}!*\n\n"
                f"👤 {person}\n"
                f"💰 {amount:,.0f} so'm\n"
                f"📋 {type_text}\n"
                f"{'📝 ' + description if description else ''}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.get_main_keyboard(user_id)
            )
        else:
            await update.message.reply_text(
                self.get_text(user_id, 'error'),
                reply_markup=self.get_main_keyboard(user_id)
            )
    
        context.user_data.clear()
        return MAIN_MENU
    
    async def show_debts(self, update: Update, user_id: int):
        """Barcha qarzlarni ko'rsatish"""
        debts = self.db.get_user_debts(user_id)
        
        if not debts:
            await update.message.reply_text(
                f"📭 {self.get_text(user_id, 'no_debts')}",
                reply_markup=self.get_main_keyboard(user_id)
            )
            return MAIN_MENU
        
        message = f"💸 *{self.get_text(user_id, 'debts_list')}:*\n\n"
        total_gave = 0
        total_took = 0
        
        for debt in debts:
            if debt['debt_type'] == 'gave':
                type_text = f"📤 *{self.get_text(user_id, 'gave')}:*"
                total_gave += debt['amount']
            else:
                type_text = f"📥 *{self.get_text(user_id, 'took')}:*"
                total_took += debt['amount']
            
            message += f"{type_text}\n"
            message += f"👤 {debt['person_name']}\n"
            message += f"💰 {debt['amount']:,.0f} so'm\n"
            message += f"🆔 ID: `{debt['id']}`\n"
            if debt.get('description'):
                message += f"📝 {debt['description']}\n"
            message += "─" * 20 + "\n\n"
        
        message += f"📤 *{self.get_text(user_id, 'total_gave')}:* {total_gave:,.0f} so'm\n"
        message += f"📥 *{self.get_text(user_id, 'total_took')}:* {total_took:,.0f} so'm\n"
        message += f"⚖️ *{self.get_text(user_id, 'balance')}:* {total_gave - total_took:,.0f} so'm"
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_main_keyboard(user_id)
        )
        return MAIN_MENU
    
    async def close_debt_start(self, update: Update, user_id: int):
        """Qarzni yopish boshlash"""
        await update.message.reply_text(
            f"✅ *{self.get_text(user_id, 'debts_close')}*\n\n"
            f"{self.get_text(user_id, 'enter_debt_id')}:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard(user_id)
        )
        return CLOSE_DEBT
    
    async def close_debt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Qarzni yopish"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            return await self.debts_menu(update, user_id)
        
        try:
            debt_id = int(text.strip())
            if self.db.close_debt(debt_id, user_id):
                await update.message.reply_text(
                    f"✅ {self.get_text(user_id, 'debt_closed')}",
                    reply_markup=self.get_main_keyboard(user_id)
                )
            else:
                await update.message.reply_text(
                    self.get_text(user_id, 'not_found'),
                    reply_markup=self.get_main_keyboard(user_id)
                )
        except ValueError:
            await update.message.reply_text(
                self.get_text(user_id, 'invalid_input'),
                reply_markup=self.get_back_keyboard(user_id)
            )
            return CLOSE_DEBT
        
        return MAIN_MENU
    
    # ==================== REPORT METHODS ====================
    async def show_report(self, update: Update, user_id: int):
        """Moliyaviy hisobot"""
        summary = self.db.get_financial_summary(user_id)
        expenses_by_category = self.db.get_expenses_by_category(user_id)
        settings = self.db.get_user_settings(user_id)
        symbol = CURRENCY_SYMBOLS.get(settings.get('currency', 'UZS'), 'so\'m')
        
        month_parts = summary['month'].split('-')
        month_name = MONTHS_UZ.get(int(month_parts[1]), month_parts[1])
        
        message = f"""
📊 *{self.get_text(user_id, 'report')}*
📅 *{month_name} {month_parts[0]}*

💵 *{self.get_text(user_id, 'income')}:* +{summary['total_income']:,.0f} {symbol}
💰 *{self.get_text(user_id, 'expense')}:* -{summary['total_expense']:,.0f} {symbol}
"""
        
        if summary['balance'] >= 0:
            message += f"🟢 *{self.get_text(user_id, 'balance')}:* {summary['balance']:,.0f} {symbol}"
        else:
            message += f"🔴 *{self.get_text(user_id, 'loss')}:* {abs(summary['balance']):,.0f} {symbol}"
        
        if expenses_by_category:
            message += f"\n\n📂 *{self.get_text(user_id, 'expense_analysis')}:*\n"
            
            for category, amount in sorted(expenses_by_category.items(), key=lambda x: x[1], reverse=True)[:5]:
                percentage = (amount / summary['total_expense'] * 100) if summary['total_expense'] > 0 else 0
                bar = "█" * int(percentage / 10) + "░" * (10 - int(percentage / 10))
                message += f"• {category}\n"
                message += f"  `{bar}` {percentage:.1f}%\n"
                message += f"  💰 {amount:,.0f} {symbol}\n\n"
        
        message += f"\n💡 *{self.get_text(user_id, 'advice')}:* "
        if summary['balance'] > 0:
            message += self.get_text(user_id, 'advice_saving')
        elif summary['balance'] < 0:
            message += self.get_text(user_id, 'advice_budget')
        else:
            message += self.get_text(user_id, 'advice_plan')
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_main_keyboard(user_id)
        )
        return MAIN_MENU
    
    # ==================== BUDGET METHODS ====================
    async def budget_menu(self, update: Update, user_id: int):
        """Byudjet menyusi"""
        keyboard = [
            [self.get_text(user_id, 'budget_status'), self.get_text(user_id, 'budget_add')],
            [self.get_text(user_id, 'budget_edit'), self.get_text(user_id, 'budget_delete')],
            [self.get_text(user_id, 'budget_alert'), self.get_text(user_id, 'back')]
        ]
        await update.message.reply_text(
            "🎯 *BYUDJET*",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        return BUDGET_MENU
    
    async def budget_menu_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Byudjet menyusi handler"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            await update.message.reply_text(
                self.get_text(user_id, 'main_menu'),
                reply_markup=self.get_main_keyboard(user_id)
            )
            return MAIN_MENU
        
        if text == self.get_text(user_id, 'budget_status'):
            return await self.show_budget_status(update, user_id)
        elif text == self.get_text(user_id, 'budget_add'):
            return await self.add_budget_start(update, user_id)
        elif text == self.get_text(user_id, 'budget_edit'):
            return await self.edit_budget_start(update, user_id)
        elif text == self.get_text(user_id, 'budget_delete'):
            return await self.delete_budget_start(update, user_id)
        elif text == self.get_text(user_id, 'budget_alert'):
            return await self.budget_alert_settings(update, user_id)
        
        return BUDGET_MENU
    
    async def show_budget_status(self, update: Update, user_id: int):
        """Byudjet holatini ko'rsatish"""
        summary = self.db.get_budget_summary(user_id)
        settings = self.db.get_user_settings(user_id)
        symbol = CURRENCY_SYMBOLS.get(settings.get('currency', 'UZS'), 'so\'m')
        threshold = settings.get('budget_alert_threshold', 80)
        
        if summary['categories_count'] == 0:
            await update.message.reply_text(
                f"🎯 *{self.get_text(user_id, 'budget_status')}*\n\n"
                f"{self.get_text(user_id, 'no_budgets')}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.get_main_keyboard(user_id)
            )
            return MAIN_MENU
        
        month_name = MONTHS_UZ.get(date.today().month, str(date.today().month))
        
        message = f"""
📊 *{self.get_text(user_id, 'budget_status')} - {month_name}*

💳 *{self.get_text(user_id, 'general')}:*
• {self.get_text(user_id, 'total_limit')}: *{summary['total_limit']:,.0f}* {symbol}
• {self.get_text(user_id, 'spent')}: *{summary['total_spent']:,.0f}* {symbol}
• {self.get_text(user_id, 'remaining')}: *{summary['remaining']:,.0f}* {symbol}
• {self.get_text(user_id, 'categories')}: *{summary['categories_count']}* ta

⚠️ *{self.get_text(user_id, 'alerts')}:*
• {summary['exceeded_count']} {self.get_text(user_id, 'exceeded')}
• {summary['warning_count']} {threshold}% {self.get_text(user_id, 'threshold_reached')}

📂 *{self.get_text(user_id, 'categories')}:*\n
"""
        
        for budget in summary['budgets']:
            if budget['monthly_limit'] > 0:
                percentage = (budget['current_spent'] / budget['monthly_limit'] * 100) if budget['monthly_limit'] > 0 else 0
                
                if percentage >= 100:
                    status = "🔴"
                elif percentage >= threshold:
                    status = "🟠"
                elif percentage >= 50:
                    status = "🟡"
                else:
                    status = "🟢"
                
                bar_length = 10
                filled = min(int(percentage / 10), bar_length)
                bar = "█" * filled + "░" * (bar_length - filled)
                
                message += f"{status} *{budget['category']}*\n"
                message += f"`{bar}` {percentage:.0f}%\n"
                message += f"💰 {budget['current_spent']:,.0f} / {budget['monthly_limit']:,.0f} {symbol}\n\n"
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_main_keyboard(user_id)
        )
        return MAIN_MENU
    
    async def add_budget_start(self, update: Update, user_id: int):
        """Byudjet qo'shish boshlash"""
        await update.message.reply_text(
            f"🎯 *{self.get_text(user_id, 'budget_add')}*\n\n"
            f"{self.get_text(user_id, 'select_category')}:",
            reply_markup=self.get_budget_categories_keyboard(user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        return BUDGET_ADD_CAT
    
    async def add_budget_cat_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Byudjet kategoriyasini tanlash callback"""
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        user_id = self.db.get_user_id(user.id)
        data = query.data
        
        if data.startswith("budget_cat_"):
            category = data.replace("budget_cat_", "")
            
            if category == "other":
                await query.message.delete()
                await query.message.reply_text(
                    f"✏️ {self.get_text(user_id, 'enter_category')}:",
                    reply_markup=self.get_back_keyboard(user_id)
                )
                context.user_data['budget_custom_cat'] = True
                return BUDGET_ADD_CAT
            else:
                context.user_data['budget_category'] = category
                await query.message.delete()
                await query.message.reply_text(
                    f"✅ {self.get_text(user_id, 'category')}: {category}\n\n"
                    f"💰 {self.get_text(user_id, 'enter_limit')}:",
                    reply_markup=self.get_back_keyboard(user_id)
                )
                return BUDGET_ADD_LIMIT
        
        elif data == "budget_cancel":
            await query.message.delete()
            return await self.budget_menu(update, user_id)
        
        return BUDGET_MENU
    
    async def add_budget_category(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Byudjet kategoriyasini qabul qilish"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            return await self.budget_menu(update, user_id)
        
        if context.user_data.get('budget_custom_cat'):
            context.user_data['budget_category'] = text
            context.user_data.pop('budget_custom_cat', None)
            await update.message.reply_text(
                f"💰 {self.get_text(user_id, 'enter_limit')}:",
                reply_markup=self.get_back_keyboard(user_id)
            )
            return BUDGET_ADD_LIMIT
        
        return BUDGET_MENU
    
    async def add_budget_limit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Byudjet limitini qabul qilish va saqlash"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            return await self.budget_menu(update, user_id)
        
        try:
            limit = float(text.replace(',', '.'))
            category = context.user_data.get('budget_category')
            
            success = self.db.set_budget_limit(user_id, category, limit)
            
            if success:
                settings = self.db.get_user_settings(user_id)
                symbol = CURRENCY_SYMBOLS.get(settings.get('currency', 'UZS'), 'so\'m')
                
                await update.message.reply_text(
                    f"✅ *{self.get_text(user_id, 'budget_saved')}!*\n\n"
                    f"🏷️ {category}\n"
                    f"💰 {limit:,.0f} {symbol}\n\n"
                    f"{self.get_text(user_id, 'alert_at')} {settings.get('budget_alert_threshold', 80)}%",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=self.get_main_keyboard(user_id)
                )
            else:
                await update.message.reply_text(
                    self.get_text(user_id, 'error'),
                    reply_markup=self.get_main_keyboard(user_id)
                )
        except ValueError:
            await update.message.reply_text(
                self.get_text(user_id, 'invalid_input'),
                reply_markup=self.get_back_keyboard(user_id)
            )
            return BUDGET_ADD_LIMIT
        
        context.user_data.clear()
        return MAIN_MENU
    
    async def edit_budget_start(self, update: Update, user_id: int):
        """Limitni o'zgartirish boshlash"""
        budgets = self.db.get_user_budgets(user_id)
        active_budgets = [b for b in budgets if b['monthly_limit'] > 0]
        
        if not active_budgets:
            await update.message.reply_text(
                f"❌ {self.get_text(user_id, 'no_budgets_to_edit')}",
                reply_markup=self.get_main_keyboard(user_id)
            )
            return MAIN_MENU
        
        keyboard = []
        for budget in active_budgets[:8]:
            keyboard.append([InlineKeyboardButton(
                f"✏️ {budget['category']} - {budget['monthly_limit']:,.0f}",
                callback_data=f"budget_edit_{budget['category']}"
            )])
        
        keyboard.append([InlineKeyboardButton(self.get_text(user_id, 'cancel'), callback_data="budget_cancel")])
        
        await update.message.reply_text(
            f"✏️ *{self.get_text(user_id, 'budget_edit')}*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return BUDGET_EDIT
    
    async def edit_budget_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Limitni o'zgartirish callback"""
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        user_id = self.db.get_user_id(user.id)
        data = query.data
        
        if data.startswith("budget_edit_"):
            category = data.replace("budget_edit_", "")
            context.user_data['edit_category'] = category
            
            await query.message.delete()
            await query.message.reply_text(
                f"✏️ {category} - {self.get_text(user_id, 'enter_new_limit')}:",
                reply_markup=self.get_back_keyboard(user_id)
            )
            return BUDGET_ADD_LIMIT
        
        elif data == "budget_cancel":
            await query.message.delete()
            return await self.budget_menu(update, user_id)
        
        return BUDGET_MENU
    
    async def delete_budget_start(self, update: Update, user_id: int):
        """Limitni o'chirish boshlash"""
        budgets = self.db.get_user_budgets(user_id)
        active_budgets = [b for b in budgets if b['monthly_limit'] > 0]
        
        if not active_budgets:
            await update.message.reply_text(
                f"❌ {self.get_text(user_id, 'no_budgets_to_delete')}",
                reply_markup=self.get_main_keyboard(user_id)
            )
            return MAIN_MENU
        
        keyboard = []
        for budget in active_budgets[:8]:
            keyboard.append([InlineKeyboardButton(
                f"🗑️ {budget['category']} - {budget['monthly_limit']:,.0f}",
                callback_data=f"budget_del_{budget['category']}"
            )])
        
        keyboard.append([InlineKeyboardButton(self.get_text(user_id, 'cancel'), callback_data="budget_cancel")])
        
        await update.message.reply_text(
            f"🗑️ *{self.get_text(user_id, 'budget_delete')}*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return BUDGET_EDIT
    
    async def delete_budget_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Limitni o'chirish callback"""
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        user_id = self.db.get_user_id(user.id)
        data = query.data
        
        if data.startswith("budget_del_"):
            category = data.replace("budget_del_", "")
            
            success = self.db.delete_budget(user_id, category)
            
            if success:
                await query.message.edit_text(
                    f"✅ {self.get_text(user_id, 'budget_deleted')}",
                    reply_markup=None
                )
            else:
                await query.message.edit_text(
                    self.get_text(user_id, 'error'),
                    reply_markup=None
                )
            
            return await self.budget_menu(update, user_id)
        
        elif data == "budget_cancel":
            await query.message.delete()
            return await self.budget_menu(update, user_id)
        
        return BUDGET_MENU
    
    async def budget_alert_settings(self, update: Update, user_id: int):
        """Ogohlantirish sozlamalari"""
        settings = self.db.get_user_settings(user_id)
        threshold = settings.get('budget_alert_threshold', 80)
        
        await update.message.reply_text(
            f"⚙️ *{self.get_text(user_id, 'budget_alert')}*\n\n"
            f"{self.get_text(user_id, 'current_threshold')}: {threshold}%\n\n"
            f"{self.get_text(user_id, 'select_new_threshold')}:",
            reply_markup=self.get_threshold_keyboard(user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        return SETTINGS_THRESHOLD
    
    # ==================== SETTINGS METHODS ====================
    async def settings_menu(self, update: Update, user_id: int):
        """Sozlamalar menyusi"""
        settings = self.db.get_user_settings(user_id)
        lang = settings.get('language', 'uz')
        
        message = f"""
⚙️ *{self.get_text(user_id, 'settings')}*

💱 *{self.get_text(user_id, 'currency_set')}:* {settings.get('currency', 'UZS')}
🔔 *{self.get_text(user_id, 'reminder_time')}:* {settings.get('reminder_time', '09:00')}
💰 *{self.get_text(user_id, 'budget_threshold')}:* {settings.get('budget_alert_threshold', 80)}%
🌐 *{self.get_text(user_id, 'language')}:* {LANGUAGES[lang]['name']}
🎨 *{self.get_text(user_id, 'theme')}:* {self.get_text(user_id, 'light_theme') if settings.get('theme') == 'light' else self.get_text(user_id, 'dark_theme')}
        """
        
        await update.message.reply_text(
            message,
            reply_markup=self.get_settings_keyboard(user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        return SETTINGS_MENU
    
    async def settings_menu_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Sozlamalar menyusi handler"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            await update.message.reply_text(
                self.get_text(user_id, 'main_menu'),
                reply_markup=self.get_main_keyboard(user_id)
            )
            return MAIN_MENU
        
        if text == self.get_text(user_id, 'currency_set'):
            await update.message.reply_text(
                self.get_text(user_id, 'currency_set'),
                reply_markup=self.get_currency_keyboard(user_id)
            )
            return SETTINGS_CURRENCY
        elif text == self.get_text(user_id, 'reminder_time'):
            await update.message.reply_text(
                f"{self.get_text(user_id, 'reminder_time')} (HH:MM):",
                reply_markup=self.get_back_keyboard(user_id)
            )
            return SETTINGS_TIME
        elif text == self.get_text(user_id, 'budget_threshold'):
            await update.message.reply_text(
                self.get_text(user_id, 'budget_threshold'),
                reply_markup=self.get_threshold_keyboard(user_id)
            )
            return SETTINGS_THRESHOLD
        elif text == self.get_text(user_id, 'language'):
            await update.message.reply_text(
                self.get_text(user_id, 'language'),
                reply_markup=self.get_language_select_keyboard(user_id)
            )
            return SETTINGS_LANG
        elif text == self.get_text(user_id, 'theme'):
            await update.message.reply_text(
                self.get_text(user_id, 'theme'),
                reply_markup=self.get_theme_keyboard(user_id)
            )
            return SETTINGS_THEME
        elif text == self.get_text(user_id, 'profile'):
            return await self.show_profile(update, user_id)
        
        return SETTINGS_MENU
    
    async def settings_currency_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Pul birligini o'zgartirish"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            return await self.settings_menu(update, user_id)
        
        currency_map = {
            "💵 UZS (so'm)": "UZS",
            "💵 USD ($)": "USD",
            "💶 EUR (€)": "EUR",
            "💷 RUB (₽)": "RUB"
        }
        
        currency = currency_map.get(text)
        if currency:
            self.db.update_user_setting(user_id, 'currency', currency)
            await update.message.reply_text(
                f"✅ {self.get_text(user_id, 'currency_set')}: {text}",
                reply_markup=self.get_main_keyboard(user_id)
            )
            return MAIN_MENU
        
        await update.message.reply_text(
            self.get_text(user_id, 'invalid_input'),
            reply_markup=self.get_back_keyboard(user_id)
        )
        return SETTINGS_CURRENCY
    
    async def settings_time_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Eslatma vaqtini o'zgartirish"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            return await self.settings_menu(update, user_id)
        
        try:
            datetime.strptime(text, "%H:%M")
            self.db.update_user_setting(user_id, 'reminder_time', text)
            await update.message.reply_text(
                f"✅ {self.get_text(user_id, 'reminder_time')}: {text}",
                reply_markup=self.get_main_keyboard(user_id)
            )
            return MAIN_MENU
        except ValueError:
            await update.message.reply_text(
                self.get_text(user_id, 'invalid_input'),
                reply_markup=self.get_back_keyboard(user_id)
            )
            return SETTINGS_TIME
    
    async def settings_threshold_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Byudjet chegarasini o'zgartirish"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            return await self.settings_menu(update, user_id)
        
        try:
            threshold = int(text.replace('%', ''))
            if 1 <= threshold <= 100:
                self.db.update_user_setting(user_id, 'budget_alert_threshold', threshold)
                await update.message.reply_text(
                    f"✅ {self.get_text(user_id, 'budget_threshold')}: {threshold}%",
                    reply_markup=self.get_main_keyboard(user_id)
                )
                return MAIN_MENU
        except ValueError:
            pass
        
        await update.message.reply_text(
            self.get_text(user_id, 'invalid_input'),
            reply_markup=self.get_back_keyboard(user_id)
        )
        return SETTINGS_THRESHOLD
    
    async def settings_language_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Tilni o'zgartirish"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            return await self.settings_menu(update, user_id)
        
        # Tilni aniqlash
        for lang_code, lang_data in LANGUAGES.items():
            if text == lang_data['name']:
                self.db.update_user_setting(user_id, 'language', lang_code)
                self.db.update_user_setting(user_id, 'currency', lang_data['currency'])
                
                await update.message.reply_text(
                    f"✅ {self.get_text(user_id, 'language')}: {text}",
                    reply_markup=self.get_main_keyboard(user_id)
                )
                return MAIN_MENU
        
        await update.message.reply_text(
            self.get_text(user_id, 'invalid_input'),
            reply_markup=self.get_back_keyboard(user_id)
        )
        return SETTINGS_LANG
    
    async def settings_theme_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mavzuni o'zgartirish"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            return await self.settings_menu(update, user_id)
        
        theme_map = {
            self.get_text(user_id, 'light_theme'): 'light',
            self.get_text(user_id, 'dark_theme'): 'dark'
        }
        
        theme = theme_map.get(text)
        if theme:
            self.db.update_user_setting(user_id, 'theme', theme)
            await update.message.reply_text(
                f"✅ {self.get_text(user_id, 'theme')}: {text}",
                reply_markup=self.get_main_keyboard(user_id)
            )
            return MAIN_MENU
        
        await update.message.reply_text(
            self.get_text(user_id, 'invalid_input'),
            reply_markup=self.get_back_keyboard(user_id)
        )
        return SETTINGS_THEME
    
    async def show_profile(self, update: Update, user_id: int):
        """Profil ma'lumotlari"""
        user = self.db.get_user_by_id(user_id)
        settings = self.db.get_user_settings(user_id)
        
        if not user:
            return MAIN_MENU
        
        message = f"""
👤 *{self.get_text(user_id, 'profile')}*

🆔 *ID:* `{user['telegram_id']}`
👤 *{self.get_text(user_id, 'name')}:* {user['full_name']}
📱 *Username:* @{user['username'] if user['username'] else 'yoʻq'}
📅 *{self.get_text(user_id, 'registered')}:* {user['registered_at'][:10]}

📊 *{self.get_text(user_id, 'statistics')}:*
• {self.get_text(user_id, 'reminder')}: {user.get('reminder_count', 0)} ta
• {self.get_text(user_id, 'expense')}: {user.get('total_expenses', 0):,.0f} {settings.get('currency', 'UZS')}
• {self.get_text(user_id, 'income')}: {user.get('total_income', 0):,.0f} {settings.get('currency', 'UZS')}

⚙️ *{self.get_text(user_id, 'settings')}:*
• {self.get_text(user_id, 'currency_set')}: {settings.get('currency', 'UZS')}
• {self.get_text(user_id, 'reminder_time')}: {settings.get('reminder_time', '09:00')}
• {self.get_text(user_id, 'budget_threshold')}: {settings.get('budget_alert_threshold', 80)}%
• {self.get_text(user_id, 'language')}: {LANGUAGES[settings.get('language', 'uz')]['name']}
        """
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_main_keyboard(user_id)
        )
        return MAIN_MENU
    
    # ==================== HELP ====================
    async def show_help(self, update: Update, user_id: int):
        """Yordam"""
        help_text = f"""
🆘 *{self.get_text(user_id, 'help')}*

🤖 *Smart Assistant Bot*

📌 *{self.get_text(user_id, 'how_to_use')}:*

🔔 *{self.get_text(user_id, 'reminder')}:*
• {self.get_text(user_id, 'one_time')} - {self.get_text(user_id, 'today')}
• {self.get_text(user_id, 'daily')}
• {self.get_text(user_id, 'custom')}
• {self.get_text(user_id, 'other_date')}

💰 *{self.get_text(user_id, 'expense')}:*
• {self.get_text(user_id, 'quick_add')} (1.5M, 500k)
• {self.get_text(user_id, 'categories')}
• {self.get_text(user_id, 'statistics')}

💵 *{self.get_text(user_id, 'income')}:*
• {self.get_text(user_id, 'by_source')}
• {self.get_text(user_id, 'monthly_report')}

💸 *{self.get_text(user_id, 'debts')}:*
• {self.get_text(user_id, 'gave_and_took')}
• {self.get_text(user_id, 'close_debt')}

🎯 *{self.get_text(user_id, 'budget')}:*
• {self.get_text(user_id, 'category_limits')}
• {self.get_text(user_id, 'progress_bar')}
• {self.get_text(user_id, 'alerts')}

📊 *{self.get_text(user_id, 'report')}:*
• {self.get_text(user_id, 'monthly_summary')}
• {self.get_text(user_id, 'category_analysis')}
• {self.get_text(user_id, 'trends')}

⚙️ *{self.get_text(user_id, 'settings')}:*
• {self.get_text(user_id, 'currency_set')}
• {self.get_text(user_id, 'reminder_time')}
• {self.get_text(user_id, 'budget_threshold')}
• {self.get_text(user_id, 'language')}
• {self.get_text(user_id, 'theme')}

📞 *{self.get_text(user_id, 'problems')}:*
/start - {self.get_text(user_id, 'restart_bot')}
        """
        
        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_main_keyboard(user_id)
        )
        return MAIN_MENU
    
    # ==================== ADMIN METHODS ====================
    async def admin_menu(self, update: Update, user_id: int):
        """Admin panel"""
        await update.message.reply_text(
            "👑 *ADMIN PANEL*",
            reply_markup=self.get_admin_keyboard(user_id),
            parse_mode=ParseMode.MARKDOWN
        )
        return ADMIN_MENU
    
    async def admin_menu_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin panel handler"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            await update.message.reply_text(
                self.get_text(user_id, 'main_menu'),
                reply_markup=self.get_main_keyboard(user_id)
            )
            return MAIN_MENU
        
        if text == "📊 UMUMIY STATISTIKA":
            return await self.admin_stats(update, user_id)
        elif text == "👥 FOYDALANUVCHILAR":
            return await self.admin_users(update, user_id)
        elif text == "🔍 QIDIRUV":
            return await self.admin_search_start(update, user_id)
        elif text == "👤 PROFIL KO'RISH":
            return await self.admin_view_profile_start(update, user_id)
        elif text == "📢 XABAR YUBORISH":
            return await self.admin_broadcast_start(update, user_id)
        elif text == "🚫 BLOKLASH/OCHISH":
            return await self.admin_block_start(update, user_id)
        elif text == "📋 ADMIN LOGLAR":
            return await self.admin_logs(update, user_id)
        
        return ADMIN_MENU
    
    async def admin_stats(self, update: Update, user_id: int):
        """Kengaytirilgan statistika"""
        stats = self.db.get_bot_stats()
        
        message = f"""
📊 *BOT STATISTIKASI*

👥 *{self.get_text(user_id, 'users')}:*
• {self.get_text(user_id, 'total')}: *{stats['total_users']}* ta
• {self.get_text(user_id, 'today')}: *+{stats['new_users_today']}* ta
• {self.get_text(user_id, 'active_week')}: *{stats['active_week']}* ta
• {self.get_text(user_id, 'blocked')}: *{stats['blocked_users']}* ta
• {self.get_text(user_id, 'admins')}: *{stats['admins']}* ta

📱 *{self.get_text(user_id, 'activity')}:*
• {self.get_text(user_id, 'reminder')}: *{stats['active_reminders']}* ta
• {self.get_text(user_id, 'debts')}: *{stats['active_debts']}* ta
• {self.get_text(user_id, 'budget')}: *{stats['budgets']}* ta

💰 *{self.get_text(user_id, 'finance')}:*
• {self.get_text(user_id, 'total_income')}: *{stats['total_income']:,.0f}* so'm
• {self.get_text(user_id, 'total_expense')}: *{stats['total_expense']:,.0f}* so'm
• {self.get_text(user_id, 'balance')}: *{stats['total_balance']:,.0f}* so'm

⚡️ *{self.get_text(user_id, 'status')}:* ✅ {self.get_text(user_id, 'working')}
        """
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_admin_keyboard(user_id)
        )
        return ADMIN_MENU
    
    async def admin_users(self, update: Update, user_id: int):
        """Foydalanuvchilar ro'yxati"""
        users = self.db.get_all_users()
    
        message = f"""
👥 *{self.get_text(user_id, 'users')}*

📊 *{self.get_text(user_id, 'total')}:* {len(users)} ta

📋 *{self.get_text(user_id, 'last_10')}:*
"""
    
        for user_data in users:  # Barcha foydalanuvchilarni ko'rsatish
            admin = "👑 " if user_data.get('is_admin') else ""
            block = "🚫 " if user_data.get('is_blocked') else ""
            username = f"@{user_data['username']}" if user_data['username'] else "no username"
        
            # registered_at datetime obyektini string ga aylantirish
            registered_at = user_data['registered_at']
            if isinstance(registered_at, datetime):
                registered_str = registered_at.strftime('%Y-%m-%d')
            else:
                registered_str = str(registered_at)[:10]
        
            message += f"\n{admin}{block}*{user_data['full_name']}*\n"
            message += f"   📱 {username}\n"
            message += f"   🆔 `{user_data['telegram_id']}`\n"
            message += f"   📅 {registered_str}\n"
    
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_admin_keyboard(user_id)
        )
        return ADMIN_MENU
    
    async def admin_search_start(self, update: Update, user_id: int):
        """Foydalanuvchi qidiruv boshlash"""
        await update.message.reply_text(
            "🔍 *Qidiruv*\n\n"
            "Ism, username yoki Telegram ID kiriting:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard(user_id)
        )
        return ADMIN_SEARCH
    
    async def admin_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Foydalanuvchi qidirish"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(user_id, 'back'):
            return await self.admin_menu(update, user_id)
        
        users = self.db.search_users(text)
        
        if not users:
            await update.message.reply_text(
                "❌ Hech narsa topilmadi.",
                reply_markup=self.get_admin_keyboard(user_id)
            )
            return ADMIN_MENU
        
        message = f"🔍 *Qidiruv natijalari:*\n\n"
        
        for user_data in users[:10]:
            block = "🚫 " if user_data.get('is_blocked') else ""
            admin = "👑 " if user_data.get('is_admin') else ""
            username = f"@{user_data['username']}" if user_data['username'] else "no username"
            
            message += f"{admin}{block}*{user_data['full_name']}*\n"
            message += f"   📱 {username}\n"
            message += f"   🆔 `{user_data['telegram_id']}`\n\n"
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_admin_keyboard(user_id)
        )
        return ADMIN_MENU
    
    async def admin_view_profile_start(self, update: Update, user_id: int):
        """Profil ko'rish boshlash"""
        await update.message.reply_text(
            "👤 *Profil ko'rish*\n\n"
            "Foydalanuvchi Telegram ID sini yuboring:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard(user_id)
        )
        return ADMIN_VIEW
    
    async def admin_view_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Foydalanuvchi profilini ko'rish"""
        user = update.effective_user
        text = update.message.text
        admin_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(admin_id, 'back'):
            return await self.admin_menu(update, admin_id)
        
        try:
            target_id = int(text.strip())
            target_user = self.db.get_user_by_telegram_id(target_id)
            
            if not target_user:
                await update.message.reply_text(
                    "❌ Foydalanuvchi topilmadi.",
                    reply_markup=self.get_admin_keyboard(admin_id)
                )
                return ADMIN_MENU
            
            profile = self.db.get_user_full_profile(target_user['id'])
            
            if not profile:
                await update.message.reply_text(
                    "❌ Profil ma'lumotlarini olishda xatolik.",
                    reply_markup=self.get_admin_keyboard(admin_id)
                )
                return ADMIN_MENU
            
            user_data = profile['user']
            stats = profile['stats']
            settings = profile['settings']
            
            message = f"""
👤 *FOYDALANUVCHI PROFILI*

🆔 *Telegram ID:* `{user_data['telegram_id']}`
👤 *Ism:* {user_data['full_name']}
📱 *Username:* @{user_data['username'] if user_data['username'] else 'yoʻq'}

📊 *Holat:*
{"👑 Admin" if user_data['is_admin'] else "👤 Foydalanuvchi"}
{"🚫 Bloklangan" if user_data.get('is_blocked') else "✅ Faol"}

📅 *Roʻyxatdan oʻtgan:* {user_data['registered_at'].strftime('%Y-%m-%d %H:%M') if isinstance(user_data['registered_at'], datetime) else str(user_data['registered_at'])[:16]}
⏰ *Oxirgi faollik:* {user_data['last_seen'].strftime('%Y-%m-%d %H:%M') if isinstance(user_data['last_seen'], datetime) else str(user_data['last_seen'])[:16]}

📊 *Statistika:*
• Eslatmalar: {stats['total_reminders']} ta (faol: {stats['active_reminders']})
• Xarajat (oylik): {stats['monthly_expense']:,.0f} so'm
• Daromad (oylik): {stats['monthly_income']:,.0f} so'm
• Balans (oylik): {stats['monthly_balance']:,.0f} so'm
• Qarzlar: {stats['active_debts']} ta
  📤 Bergan: {stats['total_gave']:,.0f} so'm
  📥 Olgan: {stats['total_took']:,.0f} so'm

⚙️ *Sozlamalar:*
• Pul birligi: {settings.get('currency', 'UZS')}
• Eslatma vaqti: {settings.get('reminder_time', '09:00')}
• Chegara: {settings.get('budget_alert_threshold', 80)}%
            """
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.get_admin_keyboard(admin_id)
            )
        except ValueError:
            await update.message.reply_text(
                "❌ Noto'g'ri format.",
                reply_markup=self.get_back_keyboard(admin_id)
            )
            return ADMIN_VIEW
        
        return ADMIN_MENU
    
    async def admin_broadcast_start(self, update: Update, user_id: int):
        """Xabar yuborish boshlash"""
        await update.message.reply_text(
            "📢 *XABAR YUBORISH*\n\n"
            "Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yozing:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard(user_id)
        )
        return ADMIN_BROADCAST
    
    async def admin_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Xabarni barchaga yuborish"""
        user = update.effective_user
        text = update.message.text
        admin_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(admin_id, 'back'):
            return await self.admin_menu(update, admin_id)
        
        users = self.db.get_all_users()
        success_count = 0
        blocked_count = 0
        error_count = 0
        
        status_msg = await update.message.reply_text(
            f"⏳ Xabar yuborilmoqda... 0/{len(users)}",
            reply_markup=self.get_main_keyboard(admin_id)
        )
        
        for i, user_data in enumerate(users):
            try:
                if user_data.get('is_blocked'):
                    blocked_count += 1
                    continue
                
                await context.bot.send_message(
                    chat_id=user_data['telegram_id'],
                    text=f"📢 *Admin xabari*\n\n{text}",
                    parse_mode=ParseMode.MARKDOWN
                )
                success_count += 1
                
                if i % 10 == 0:
                    try:
                        await status_msg.edit_text(
                            f"⏳ Xabar yuborilmoqda... {i}/{len(users)}"
                        )
                    except Exception:
                        pass  # Xabar o'zgartirilmasa ham davom etish
                
                await asyncio.sleep(0.05)
                
            except Exception as e:
                error_count += 1
                logger.error(f"Broadcast error to {user_data['telegram_id']}: {e}")
        
        try:
            await status_msg.edit_text(
                f"✅ *Xabar yuborildi!*\n\n"
                f"📊 *Natija:*\n"
                f"• Yuborildi: {success_count}\n"
                f"• Bloklangan: {blocked_count}\n"
                f"• Xatolik: {error_count}\n"
                f"• Jami: {len(users)}",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            # Agar status xabari o'zgartirilmasa, yangi xabar yuborish
            await update.message.reply_text(
                f"✅ *Xabar yuborildi!*\n\n"
                f"📊 *Natija:*\n"
                f"• Yuborildi: {success_count}\n"
                f"• Bloklangan: {blocked_count}\n"
                f"• Xatolik: {error_count}\n"
                f"• Jami: {len(users)}",
                parse_mode=ParseMode.MARKDOWN
            )
        
        # Menyuga qaytish
        await update.message.reply_text(
            "👑 *ADMIN PANEL*",
            reply_markup=self.get_admin_keyboard(admin_id)
        )
        context.user_data.clear()  # State ni tozalash
        return ADMIN_MENU
    
    async def admin_block_start(self, update: Update, user_id: int):
        """Bloklash boshlash"""
        await update.message.reply_text(
            "🚫 *BLOKLASH/OCHISH*\n\n"
            "Foydalanuvchi Telegram ID sini yuboring:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard(user_id)
        )
        return ADMIN_BLOCK
    
    async def admin_block(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Foydalanuvchini bloklash yoki blokdan ochish"""
        user = update.effective_user
        text = update.message.text
        admin_id = self.db.get_user_id(user.id)
        
        if text == self.get_text(admin_id, 'back'):
            return await self.admin_menu(update, admin_id)
        
        try:
            target_id = int(text.strip())
            
            target_user = self.db.get_user_by_telegram_id(target_id)
            if not target_user:
                await update.message.reply_text(
                    "❌ Foydalanuvchi topilmadi.",
                    reply_markup=self.get_admin_keyboard(admin_id)
                )
                return ADMIN_MENU
            
            if target_user.get('is_blocked'):
                success = self.db.unblock_user(target_id, user.id)
                action = "blokdan ochildi"
            else:
                success = self.db.block_user(target_id, user.id)
                action = "bloklandi"
            
            if success:
                await update.message.reply_text(
                    f"✅ Foydalanuvchi {target_id} {action}!",
                    reply_markup=self.get_admin_keyboard(admin_id)
                )
            else:
                await update.message.reply_text(
                    "❌ Xatolik yuz berdi.",
                    reply_markup=self.get_admin_keyboard(admin_id)
                )
        except ValueError:
            await update.message.reply_text(
                "❌ Noto'g'ri format.",
                reply_markup=self.get_back_keyboard(admin_id)
            )
            return ADMIN_BLOCK
        
        return ADMIN_MENU
    
    async def admin_logs(self, update: Update, user_id: int):
        """Admin action loglari"""
        logs = self.db.get_admin_actions(20)
        
        message = "📋 *ADMIN HARAKATLARI*\n\n"
        
        for log in logs[:10]:
            date = log['created_at'].strftime('%Y-%m-%d %H:%M') if isinstance(log['created_at'], datetime) else str(log['created_at'])[:16]
            admin = log['admin_name'] or str(log['admin_id'])
            
            action_text = {
                'block': '🚫 Bloklash',
                'unblock': '✅ Blokni ochish',
                'broadcast': '📢 Xabar yuborish'
            }.get(log['action'], log['action'])
            
            target = f" → {log['target_name'] or log['target_user']}" if log['target_user'] else ""
            
            message += f"• {date} - {admin}\n"
            message += f"  {action_text}{target}\n\n"
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_admin_keyboard(user_id)
        )
        return ADMIN_MENU
    
    # ==================== FALLBACK ====================
    async def fallback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Fallback handler"""
        user = update.effective_user
        user_id = self.db.get_user_id(user.id)
        
        if user_id:
            await update.message.reply_text(
                self.get_text(user_id, 'invalid_input'),
                reply_markup=self.get_main_keyboard(user_id)
            )
        else:
            await update.message.reply_text(
                "Iltimos, /start buyrug'ini yuboring."
            )
        
        return MAIN_MENU

# ==================== CONVERSATION HANDLER ====================
def get_conversation_handler(bot_handler: BotHandler):
    """ConversationHandler ni yaratish"""
    return ConversationHandler(
        entry_points=[CommandHandler('start', bot_handler.start)],
        states={
            LANG_SELECT: [CallbackQueryHandler(bot_handler.handle_callback)],
            
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.main_menu_handler)],
            
            # Reminder states
            REMINDER_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.reminder_menu_handler)],
            ADD_REMINDER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.add_reminder_name)],
            ADD_REMINDER_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.add_reminder_type)],
            ADD_REMINDER_DAYS: [CallbackQueryHandler(bot_handler.handle_callback)],
            ADD_REMINDER_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.add_reminder_date)],
            ADD_REMINDER_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.add_reminder_time)],
            ADD_REMINDER_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.add_reminder_desc)],
            DELETE_REMINDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.delete_reminder)],
            
            # Expense states
            EXPENSE_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.expense_menu_handler)],
            ADD_EXPENSE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.add_expense_amount)],
            ADD_EXPENSE_CAT: [CallbackQueryHandler(bot_handler.handle_callback)],
            ADD_EXPENSE_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.add_expense_desc)],
            
            # Income states
            INCOME_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.income_menu_handler)],
            ADD_INCOME_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.add_income_amount)],
            ADD_INCOME_CAT: [CallbackQueryHandler(bot_handler.handle_callback)],
            ADD_INCOME_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.add_income_desc)],
            
            # Debt states
            DEBTS_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.debts_menu_handler)],
            ADD_DEBT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.add_debt_name)],
            ADD_DEBT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.add_debt_amount)],
            ADD_DEBT_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.add_debt_type)],
            ADD_DEBT_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.add_debt_desc)],
            CLOSE_DEBT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.close_debt)],
            
            # Budget states
            BUDGET_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.budget_menu_handler)],
            BUDGET_ADD_CAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.add_budget_category)],
            BUDGET_ADD_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.add_budget_limit)],
            BUDGET_EDIT: [CallbackQueryHandler(bot_handler.handle_callback)],
            
            # Settings states
            SETTINGS_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.settings_menu_handler)],
            SETTINGS_CURRENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.settings_currency_handler)],
            SETTINGS_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.settings_time_handler)],
            SETTINGS_THRESHOLD: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.settings_threshold_handler)],
            SETTINGS_LANG: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.settings_language_handler)],
            SETTINGS_THEME: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.settings_theme_handler)],
            
            # Admin states
            ADMIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.admin_menu_handler)],
            ADMIN_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.admin_search)],
            ADMIN_VIEW: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.admin_view_profile)],
            ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.admin_broadcast)],
            ADMIN_BLOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.admin_block)],
        },
        fallbacks=[
            CommandHandler('start', bot_handler.start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.fallback)
        ],
        allow_reentry=True,
        per_message=False
    )

# ==================== SCHEDULER ====================
class ReminderScheduler:
    def __init__(self, db: Database, bot_token: str):
        self.db = db
        self.bot_token = bot_token
        self.running = False
        self.sent_reminders = set()
    
    def start(self):
        self.running = True
        thread = threading.Thread(target=self._run_scheduler, daemon=True)
        thread.start()
        logger.info("✅ Reminder scheduler started")
    
    def _run_scheduler(self):
        while self.running:
            try:
                now = datetime.now(TIMEZONE)
                
                # Har kuni yarim tunda sent_reminders setini tozalash
                if now.hour == 0 and now.minute == 0:
                    self.sent_reminders.clear()
                
                self._check_reminders(now)
                
                if now.minute % 15 == 0:
                    self._check_budgets()
                
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(60)
    
    def _check_reminders(self, now: datetime):
        """Eslatmalarni tekshirish va yuborish"""
        try:
            reminders = self.db.get_due_reminders()
            
            for reminder in reminders:
                try:
                    if reminder.get('is_blocked'):
                        continue
                    
                    reminder_key = f"{reminder['id']}_{now.strftime('%Y-%m-%d')}"
                    if reminder_key in self.sent_reminders:
                        continue
                    
                    telegram_id = reminder['telegram_id']
                    title = reminder['title']
                    
                    if reminder.get('next_reminder'):
                        reminder_time = reminder['next_reminder']
                    else:
                        reminder_time = reminder['reminder_time']
                    
                    if isinstance(reminder_time, str):
                        reminder_time = datetime.fromisoformat(reminder_time.replace(' ', 'T'))
                    
                    now_rounded = now.replace(second=0, microsecond=0)
                    reminder_rounded = reminder_time.replace(second=0, microsecond=0)
                    
                    if now_rounded == reminder_rounded:
                        message = f"🔔 *ESLATMA: {title}*\n"
                        message += f"⏰ {reminder_time.strftime('%H:%M')}"
                        
                        if reminder.get('description'):
                            message += f"\n📝 {reminder['description']}"
                        
                        if reminder['repeat_type'] == 'daily':
                            message += f"\n🔄 Har kuni"
                        elif reminder['repeat_type'] == 'custom' and reminder.get('repeat_days'):
                            message += f"\n📆 Tanlangan kunlar"
                        
                        self._send_reminder(telegram_id, message, reminder['id'])
                        self.sent_reminders.add(reminder_key)
                        self.db.log_reminder_sent(reminder['id'], reminder['user_db_id'])
                        self.db.update_reminder_next_time(reminder['id'])
                    
                except Exception as e:
                    logger.error(f"Reminder send error: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Check reminders error: {e}")
    
    def _check_budgets(self):
        """Byudjetlarni tekshirish"""
        try:
            month_year = date.today().strftime("%Y-%m")
            
            self.db.cursor.execute(
                """SELECT b.*, u.telegram_id, u.is_blocked, s.budget_alert_threshold
                FROM budgets b
                JOIN users u ON b.user_id = u.id
                LEFT JOIN user_settings s ON u.id = s.user_id
                WHERE b.month_year = ? AND b.monthly_limit > 0 
                AND u.is_blocked = 0""",
                (month_year,)
            )
            
            budgets = self.db.cursor.fetchall()
            
            for budget in budgets:
                try:
                    spent = budget['current_spent']
                    limit = budget['monthly_limit']
                    percentage = (spent / limit * 100) if limit > 0 else 0
                    threshold = budget['budget_alert_threshold'] or 80
                    
                    alerts = self.db.check_budget_alerts(
                        budget['user_id'],
                        budget['category'],
                        spent,
                        limit
                    )
                    
                    for alert in alerts:
                        if alert.startswith('threshold'):
                            percentage_val = alert.split(':')[1]
                            self._send_budget_warning(
                                budget['telegram_id'],
                                budget['category'],
                                spent,
                                limit,
                                float(percentage_val)
                            )
                        elif alert.startswith('exceeded'):
                            over = alert.split(':')[1]
                            self._send_budget_exceeded(
                                budget['telegram_id'],
                                budget['category'],
                                spent,
                                limit,
                                over
                            )
                            
                except Exception as e:
                    logger.error(f"Budget check error: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Check budgets error: {e}")
    
    def _send_reminder(self, chat_id: int, message: str, reminder_id: int):
        """Eslatma yuborish"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            from telegram import Bot
            bot = Bot(token=self.bot_token)
            
            loop.run_until_complete(
                bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN
                )
            )
            
            loop.close()
        except Exception as e:
            logger.error(f"Send reminder error: {e}")
    
    def _send_budget_warning(self, chat_id: int, category: str, spent: float, limit: float, percentage: float):
        """Byudjet ogohlantirish yuborish"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            from telegram import Bot
            bot = Bot(token=self.bot_token)
            
            message = f"⚠️ *Ogohlantirish!*\n\n📂 {category}\n💰 Sarflangan: {spent:,.0f} so'm\n🎯 Limit: {limit:,.0f} so'm\n📊 Limitning {percentage:.0f}% ga yetdingiz!"
            
            loop.run_until_complete(
                bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN
                )
            )
            
            loop.close()
        except Exception as e:
            logger.error(f"Send budget warning error: {e}")
    
    def _send_budget_exceeded(self, chat_id: int, category: str, spent: float, limit: float, over: str):
        """Limit oshganligi haqida xabar yuborish"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            from telegram import Bot
            bot = Bot(token=self.bot_token)
            
            message = f"🔴 *Limit oshib ketdi!*\n\n📂 {category}\n💰 Sarflangan: {spent:,.0f} so'm\n🎯 Limit: {limit:,.0f} so'm\n⚠️ Limit {over} so'mga oshib ketdi!"
            
            loop.run_until_complete(
                bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN
                )
            )
            
            loop.close()
        except Exception as e:
            logger.error(f"Send budget exceeded error: {e}")

# ==================== ASOSIY ====================
def main():
    print("=" * 60)
    print("🤖 Smart Assistant Bot - RENDER VERSIYA")
    print("=" * 60)
    print(f"👑 Admin ID: {ADMIN_IDS}")
    print(f"⏰ Timezone: {TIMEZONE}")
    print(f"📁 Database: {DB_NAME}")
    print("=" * 60)
    
    db = None
    try:
        db = Database()
        bot_handler = BotHandler(db)
        
        # Application yaratish
        application = Application.builder().token(BOT_TOKEN).build()
        
        # ConversationHandler qo'shish
        conv_handler = get_conversation_handler(bot_handler)
        application.add_handler(conv_handler)
        
        # Qolgan handlerlar
        application.add_handler(CallbackQueryHandler(bot_handler.handle_callback))
        
        # Scheduler ishga tushirish
        scheduler = ReminderScheduler(db, BOT_TOKEN)
        scheduler.start()
        
        print("✅ Bot muvaffaqiyatli yuklandi!")
        print("🔄 Polling ishga tushmoqda...")
        print("=" * 60)
        print("⚠️  Botni to'xtatish uchun: Ctrl+C bosing")
        print("=" * 60)
        
        # Polling rejimida ishga tushirish
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        print(f"❌ Xatolik: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if db:
            db.close()
        print("🤖 Bot to'xtatildi.")

# ==================== FLASK WEBHOOK ====================
# ==================== FLASK HEALTH CHECK ====================
app = Flask(__name__)

@app.route('/')
def index():
    """Asosiy sahifa - health check"""
    return jsonify({
        'status': 'running',
        'mode': 'polling',
        'time': datetime.now().isoformat(),
        'bot': 'Smart Assistant Bot is working!'
    })

@app.route('/health')
def health():
    """Health check endpoint - Render uchun"""
    return jsonify({'status': 'healthy'}), 200

@app.route('/ping')
def ping():
    """Ping endpoint"""
    return 'pong'

# Bot thread funksiyasi
def run_bot():
    """Botni alohida threadda ishga tushirish"""
    try:
        logger.info("🚀 Starting bot thread...")
        
        # Database yaratish
        db = Database()
        bot_handler = BotHandler(db)
        
        # Application yaratish
        application = Application.builder().token(BOT_TOKEN).build()
        
        # ConversationHandler qo'shish
        conv_handler = get_conversation_handler(bot_handler)
        application.add_handler(conv_handler)
        
        # Qolgan handlerlar
        application.add_handler(CallbackQueryHandler(bot_handler.handle_callback))
        
        # Scheduler ishga tushirish
        scheduler = ReminderScheduler(db, BOT_TOKEN)
        scheduler.start()
        
        logger.info("✅ Bot muvaffaqiyatli yuklandi!")
        logger.info("🔄 Polling ishga tushmoqda...")
        
        # Polling rejimida ishga tushirish
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"❌ Bot thread xatolik: {e}")
        import traceback
        traceback.print_exc()

# ==================== ASOSIY ====================
def main():
    print("=" * 60)
    print("🤖 Smart Assistant Bot - RENDER WEB SERVICE (POLLING MODE)")
    print("=" * 60)
    print(f"👑 Admin ID: {ADMIN_IDS}")
    print(f"⏰ Timezone: {TIMEZONE}")
    print(f"📁 Database: {DB_NAME}")
    print("=" * 60)
    
    # Botni alohida threadda ishga tushirish
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    logger.info("✅ Bot thread started")
    
    # Flask ni ishga tushirish (health check uchun)
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 Flask server starting on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)

if __name__ == '__main__':
    main()
