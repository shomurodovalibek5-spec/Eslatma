# bot.py - SQLITE DATETIME XATOSI TUZATILGAN

import os
import logging
import sqlite3
import asyncio
from datetime import datetime, timedelta, date
from decimal import Decimal, InvalidOperation
import threading
import time
from flask import Flask, request
from zoneinfo import ZoneInfo

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# ==================== KONFIGURATSIYA ====================
BOT_TOKEN = "8250421622:AAHpa6q_RMV1d3QNO4tM3YtT9h2jYJebvjw" 
ADMIN_IDS = [8014950410]
TIMEZONE = ZoneInfo("Asia/Tashkent")

# ==================== LOG SOZLAMALARI ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== DATABASE FIX ====================
DB_NAME = 'smart_assistant.db'

# SQLite datetime converter ni to'g'ri sozlash
def adapt_datetime(dt):
    return dt.isoformat()

def convert_datetime(val):
    try:
        # Agar val bytes bo'lsa, stringga o'tkazish
        if isinstance(val, bytes):
            val = val.decode('utf-8')
        
        # Agar allaqachon string bo'lsa
        if isinstance(val, str):
            # Sanani to'g'ri parse qilish
            if ' ' in val:
                # "2024-02-07 12:30:00" format
                return datetime.fromisoformat(val.replace(' ', 'T'))
            else:
                # "2024-02-07T12:30:00" format
                return datetime.fromisoformat(val)
        return None
    except Exception as e:
        logger.error(f"Datetime conversion error: {e}, val: {val}")
        return datetime.now()

sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("datetime", convert_datetime)
sqlite3.register_converter("timestamp", convert_datetime)

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(
            DB_NAME, 
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            check_same_thread=False
        )
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.init_tables()
        logger.info(f"Database ochildi: {DB_NAME}")
    
    def init_tables(self):
        # Users - datetime ustunlarini TEXT ga o'zgartirish
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                username TEXT,
                full_name TEXT,
                language TEXT DEFAULT "uz",
                currency TEXT DEFAULT "UZS",
                is_admin BOOLEAN DEFAULT 0,
                registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_seen TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Reminders
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                reminder_time TEXT NOT NULL,
                status TEXT DEFAULT "active",
                repeat_type TEXT DEFAULT "none",
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Expenses - DATE ustunlarini TEXT ga
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount DECIMAL(10, 2) NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                expense_date TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Income
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS income (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount DECIMAL(10, 2) NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                income_date TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Activities
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                activity_name TEXT NOT NULL,
                activity_time TEXT,
                activity_date TEXT NOT NULL,
                status TEXT DEFAULT "pending",
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Budgets
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                category TEXT NOT NULL,
                monthly_limit DECIMAL(10, 2) NOT NULL,
                current_spent DECIMAL(10, 2) DEFAULT 0,
                month_year TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE(user_id, category, month_year)
            )
        ''')
        
        # Debts
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS debts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                person_name TEXT NOT NULL,
                amount DECIMAL(10, 2) NOT NULL,
                debt_type TEXT NOT NULL, 
                description TEXT,
                status TEXT DEFAULT 'active', 
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                return_date TEXT,
                due_date TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        self.conn.commit()
        logger.info("Database initialized successfully")
    
    # --- HELPER FUNCTIONS ---
    def parse_datetime(self, dt_str):
        """Stringni datetime ga o'tkazish"""
        if not dt_str:
            return None
        try:
            if isinstance(dt_str, datetime):
                return dt_str
            
            # Turli formatlarni qo'llab-quvvatlash
            formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%d',
                '%d.%m.%Y %H:%M',
                '%d.%m.%Y'
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(dt_str, fmt)
                except:
                    continue
            
            # Agar hech qaysi format ishlamasa
            return datetime.fromisoformat(dt_str.replace(' ', 'T'))
        except Exception as e:
            logger.error(f"Datetime parse error: {e}, dt_str: {dt_str}")
            return datetime.now()
    
    def format_datetime(self, dt):
        """Datetimeni string ga formatlash"""
        if not dt:
            return None
        if isinstance(dt, str):
            return dt
        return dt.isoformat().replace('T', ' ')
    
    def format_date(self, d):
        """Dateni string ga formatlash"""
        if not d:
            return None
        if isinstance(d, str):
            return d
        return d.strftime('%Y-%m-%d')
    
    # --- USER METHODS ---
    def add_user(self, telegram_id: int, username: str, full_name: str):
        try:
            is_admin = 1 if telegram_id in ADMIN_IDS else 0
            
            now_str = datetime.now(TIMEZONE).isoformat().replace('T', ' ')
            
            self.cursor.execute('''
                INSERT OR IGNORE INTO users (telegram_id, username, full_name, is_admin, last_seen) 
                VALUES (?, ?, ?, ?, ?)
            ''', (telegram_id, username, full_name, is_admin, now_str))
            
            if telegram_id in ADMIN_IDS:
                self.cursor.execute('''
                    UPDATE users 
                    SET username = ?, full_name = ?, is_admin = 1, last_seen = ? 
                    WHERE telegram_id = ?
                ''', (username, full_name, now_str, telegram_id))
            else:
                self.cursor.execute('''
                    UPDATE users 
                    SET username = ?, full_name = ?, last_seen = ? 
                    WHERE telegram_id = ?
                ''', (username, full_name, now_str, telegram_id))
            
            self.conn.commit()
            return is_admin
        except Exception as e:
            logger.error(f"User add error: {e}")
            return 0

    def get_user_id(self, telegram_id: int):
        self.cursor.execute('SELECT id FROM users WHERE telegram_id = ?', (telegram_id,))
        res = self.cursor.fetchone()
        return res['id'] if res else None

    def get_user_info(self, telegram_id: int):
        self.cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
        res = self.cursor.fetchone()
        if res:
            user_dict = dict(res)
            # Datetime larni parse qilish
            if user_dict.get('registered_at'):
                user_dict['registered_at'] = self.parse_datetime(user_dict['registered_at'])
            if user_dict.get('last_seen'):
                user_dict['last_seen'] = self.parse_datetime(user_dict['last_seen'])
            return user_dict
        return None

    def update_user_settings(self, user_id: int, lang=None, currency=None):
        if lang:
            self.cursor.execute('UPDATE users SET language = ? WHERE id = ?', (lang, user_id))
        if currency:
            self.cursor.execute('UPDATE users SET currency = ? WHERE id = ?', (currency, user_id))
        self.conn.commit()

    def clear_all_user_data(self, user_id: int):
        self.cursor.execute('DELETE FROM reminders WHERE user_id = ?', (user_id,))
        self.cursor.execute('DELETE FROM expenses WHERE user_id = ?', (user_id,))
        self.cursor.execute('DELETE FROM income WHERE user_id = ?', (user_id,))
        self.cursor.execute('DELETE FROM daily_activities WHERE user_id = ?', (user_id,))
        self.cursor.execute('DELETE FROM budgets WHERE user_id = ?', (user_id,))
        self.cursor.execute('DELETE FROM debts WHERE user_id = ?', (user_id,))
        self.conn.commit()

    # --- REMINDERS ---
    def add_reminder(self, user_id: int, title: str, description: str, reminder_time: datetime, repeat_type="none"):
        try:
            if reminder_time.tzinfo is None:
                reminder_time = reminder_time.replace(tzinfo=TIMEZONE)
            
            time_str = reminder_time.isoformat().replace('T', ' ')
            self.cursor.execute('INSERT INTO reminders (user_id, title, description, reminder_time, repeat_type) VALUES (?, ?, ?, ?, ?)', 
                             (user_id, title, description, time_str, repeat_type))
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            logger.error(f"Reminder add error: {e}")
            return None

    def get_all_reminders(self, user_id: int):
        self.cursor.execute('SELECT * FROM reminders WHERE user_id = ? ORDER BY reminder_time DESC', (user_id,))
        rows = self.cursor.fetchall()
        result = []
        for row in rows:
            item = dict(row)
            if item.get('reminder_time'):
                item['reminder_time'] = self.parse_datetime(item['reminder_time'])
            if item.get('created_at'):
                item['created_at'] = self.parse_datetime(item['created_at'])
            result.append(item)
        return result

    def get_user_reminders(self, user_id: int):
        self.cursor.execute('SELECT * FROM reminders WHERE user_id = ? AND status = "active" ORDER BY reminder_time ASC', (user_id,))
        rows = self.cursor.fetchall()
        result = []
        for row in rows:
            item = dict(row)
            if item.get('reminder_time'):
                item['reminder_time'] = self.parse_datetime(item['reminder_time'])
            if item.get('created_at'):
                item['created_at'] = self.parse_datetime(item['created_at'])
            result.append(item)
        return result

    def delete_reminder(self, reminder_id: int, user_id: int):
        self.cursor.execute('DELETE FROM reminders WHERE id = ? AND user_id = ?', (reminder_id, user_id))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def delete_all_reminders(self, user_id: int):
        self.cursor.execute('DELETE FROM reminders WHERE user_id = ?', (user_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def update_reminder_time(self, rid: int, new_time: datetime):
        try:
            time_str = new_time.isoformat().replace('T', ' ')
            self.cursor.execute('UPDATE reminders SET reminder_time = ?, status = "active" WHERE id = ?', (time_str, rid))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Reminder update error: {e}")

    # --- INCOME ---
    def add_income(self, user_id: int, amount: float, category: str, description: str, inc_date=None):
        try:
            if not inc_date: inc_date = date.today()
            date_str = self.format_date(inc_date)
            self.cursor.execute('INSERT INTO income (user_id, amount, category, description, income_date) VALUES (?, ?, ?, ?, ?)', 
                             (user_id, amount, category, description, date_str))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Income add error: {e}")
            return False

    def get_all_income(self, user_id: int):
        self.cursor.execute('SELECT * FROM income WHERE user_id = ? ORDER BY income_date DESC', (user_id,))
        rows = self.cursor.fetchall()
        result = []
        for row in rows:
            item = dict(row)
            if item.get('income_date'):
                item['income_date'] = self.parse_datetime(item['income_date'])
            if item.get('created_at'):
                item['created_at'] = self.parse_datetime(item['created_at'])
            result.append(item)
        return result

    def get_user_income(self, user_id: int, days=30):
        start_date = (date.today() - timedelta(days=days)).strftime('%Y-%m-%d')
        self.cursor.execute('SELECT * FROM income WHERE user_id = ? AND income_date >= ? ORDER BY income_date DESC', (user_id, start_date))
        rows = self.cursor.fetchall()
        result = []
        for row in rows:
            item = dict(row)
            if item.get('income_date'):
                item['income_date'] = self.parse_datetime(item['income_date'])
            if item.get('created_at'):
                item['created_at'] = self.parse_datetime(item['created_at'])
            result.append(item)
        return result

    def get_income_summary(self, user_id: int):
        self.cursor.execute('''
            SELECT 
                strftime("%Y-%m", income_date) as month,
                category,
                SUM(amount) as total,
                COUNT(*) as count
            FROM income 
            WHERE user_id = ?
            GROUP BY strftime("%Y-%m", income_date), category
            ORDER BY month DESC, total DESC
        ''', (user_id,))
        return [dict(row) for row in self.cursor.fetchall()]

    # --- EXPENSES ---
    def add_expense(self, user_id: int, amount: float, category: str, description: str, exp_date=None):
        try:
            if not exp_date: exp_date = date.today()
            date_str = self.format_date(exp_date)
            self.cursor.execute('INSERT INTO expenses (user_id, amount, category, description, expense_date) VALUES (?, ?, ?, ?, ?)', 
                             (user_id, amount, category, description, date_str))
            
            month_year = exp_date.strftime("%Y-%m")
            self.cursor.execute('INSERT OR IGNORE INTO budgets (user_id, category, monthly_limit, current_spent, month_year) VALUES (?, ?, 0, 0, ?)', 
                             (user_id, category, month_year))
            self.cursor.execute('UPDATE budgets SET current_spent = current_spent + ? WHERE user_id = ? AND category = ? AND month_year = ?', 
                             (amount, user_id, category, month_year))
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Expense add error: {e}")
            return False

    def get_all_expenses(self, user_id: int):
        self.cursor.execute('SELECT * FROM expenses WHERE user_id = ? ORDER BY expense_date DESC', (user_id,))
        rows = self.cursor.fetchall()
        result = []
        for row in rows:
            item = dict(row)
            if item.get('expense_date'):
                item['expense_date'] = self.parse_datetime(item['expense_date'])
            if item.get('created_at'):
                item['created_at'] = self.parse_datetime(item['created_at'])
            result.append(item)
        return result

    def get_user_expenses(self, user_id: int, days=30):
        start_date = (date.today() - timedelta(days=days)).strftime('%Y-%m-%d')
        self.cursor.execute('SELECT * FROM expenses WHERE user_id = ? AND expense_date >= ? ORDER BY expense_date DESC', (user_id, start_date))
        rows = self.cursor.fetchall()
        result = []
        for row in rows:
            item = dict(row)
            if item.get('expense_date'):
                item['expense_date'] = self.parse_datetime(item['expense_date'])
            if item.get('created_at'):
                item['created_at'] = self.parse_datetime(item['created_at'])
            result.append(item)
        return result

    def get_expense_summary(self, user_id: int):
        self.cursor.execute('''
            SELECT 
                strftime("%Y-%m", expense_date) as month,
                category,
                SUM(amount) as total,
                COUNT(*) as count
            FROM expenses 
            WHERE user_id = ?
            GROUP BY strftime("%Y-%m", expense_date), category
            ORDER BY month DESC, total DESC
        ''', (user_id,))
        return [dict(row) for row in self.cursor.fetchall()]

    # --- DEBTS ---
    def add_debt(self, user_id: int, person_name: str, amount: float, debt_type: str, description="", due_date=None):
        try:
            due_date_str = self.format_date(due_date) if due_date else None
            
            self.cursor.execute('''
                INSERT INTO debts (user_id, person_name, amount, debt_type, description, due_date) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, person_name, amount, debt_type, description, due_date_str))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Debt add error: {e}")
            return False

    def get_user_debts(self, user_id: int):
        self.cursor.execute('''
            SELECT * FROM debts 
            WHERE user_id = ? AND status = "active" 
            ORDER BY 
                CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,
                due_date ASC,
                created_at DESC
        ''', (user_id,))
        rows = self.cursor.fetchall()
        result = []
        for row in rows:
            item = dict(row)
            if item.get('due_date'):
                item['due_date'] = self.parse_datetime(item['due_date'])
            if item.get('return_date'):
                item['return_date'] = self.parse_datetime(item['return_date'])
            if item.get('created_at'):
                item['created_at'] = self.parse_datetime(item['created_at'])
            result.append(item)
        return result

    def get_all_debts(self, user_id: int):
        self.cursor.execute('SELECT * FROM debts WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
        rows = self.cursor.fetchall()
        result = []
        for row in rows:
            item = dict(row)
            if item.get('due_date'):
                item['due_date'] = self.parse_datetime(item['due_date'])
            if item.get('return_date'):
                item['return_date'] = self.parse_datetime(item['return_date'])
            if item.get('created_at'):
                item['created_at'] = self.parse_datetime(item['created_at'])
            result.append(item)
        return result

    def close_debt(self, debt_id: int, user_id: int):
        return_date_str = datetime.now(TIMEZONE).isoformat().replace('T', ' ')
        self.cursor.execute('UPDATE debts SET status = "returned", return_date = ? WHERE id = ? AND user_id = ?', 
                         (return_date_str, debt_id, user_id))
        self.conn.commit()

    def get_debt_summary(self, user_id: int):
        self.cursor.execute('''
            SELECT 
                debt_type,
                person_name,
                SUM(amount) as total_amount,
                COUNT(*) as count,
                MIN(due_date) as earliest_due,
                MAX(due_date) as latest_due
            FROM debts 
            WHERE user_id = ? AND status = "active"
            GROUP BY debt_type, person_name
        ''', (user_id,))
        return [dict(row) for row in self.cursor.fetchall()]

    # --- ACTIVITIES ---
    def add_activity(self, user_id: int, name: str, time_str: str = None):
        try:
            date_str = date.today().strftime('%Y-%m-%d')
            self.cursor.execute('INSERT INTO daily_activities (user_id, activity_name, activity_time, activity_date) VALUES (?, ?, ?, ?)', 
                             (user_id, name, time_str, date_str))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Activity add error: {e}")
            return False

    def get_activities(self, user_id: int):
        today = date.today().strftime('%Y-%m-%d')
        self.cursor.execute('SELECT * FROM daily_activities WHERE user_id = ? AND activity_date = ? ORDER BY activity_time ASC', (user_id, today))
        rows = self.cursor.fetchall()
        result = []
        for row in rows:
            item = dict(row)
            if item.get('activity_date'):
                item['activity_date'] = self.parse_datetime(item['activity_date'])
            if item.get('created_at'):
                item['created_at'] = self.parse_datetime(item['created_at'])
            result.append(item)
        return result
    
    def complete_activity(self, act_id: int, user_id: int):
        self.cursor.execute('UPDATE daily_activities SET status = "completed" WHERE id = ? AND user_id = ?', (act_id, user_id))
        self.conn.commit()

    # --- BUDGET & STATS ---
    def get_budgets(self, user_id: int):
        month_year = date.today().strftime("%Y-%m")
        self.cursor.execute('SELECT * FROM budgets WHERE user_id = ? AND month_year = ?', (user_id, month_year))
        return [dict(row) for row in self.cursor.fetchall()]

    def set_budget_limit(self, user_id: int, category: str, limit: float):
        month_year = date.today().strftime("%Y-%m")
        self.cursor.execute('''
            INSERT OR REPLACE INTO budgets (user_id, category, monthly_limit, current_spent, month_year) 
            VALUES (?, ?, ?, COALESCE((SELECT current_spent FROM budgets WHERE user_id=? AND category=? AND month_year=?), 0), ?)
        ''', (user_id, category, limit, user_id, category, month_year, month_year))
        self.conn.commit()

    def get_financial_summary(self, user_id: int):
        month_year = date.today().strftime("%Y-%m")
        
        # Xarajatlar kategoriya bo'yicha
        self.cursor.execute('''
            SELECT category, SUM(amount) as total 
            FROM expenses 
            WHERE user_id = ? AND strftime("%Y-%m", expense_date) = ? 
            GROUP BY category 
            ORDER BY total DESC
        ''', (user_id, month_year))
        expense_by_category = [dict(row) for row in self.cursor.fetchall()]
        
        # Daromadlar kategoriya bo'yicha
        self.cursor.execute('''
            SELECT category, SUM(amount) as total 
            FROM income 
            WHERE user_id = ? AND strftime("%Y-%m", income_date) = ? 
            GROUP BY category 
            ORDER BY total DESC
        ''', (user_id, month_year))
        income_by_category = [dict(row) for row in self.cursor.fetchall()]
        
        # Jami summalar
        self.cursor.execute('SELECT SUM(amount) as total FROM expenses WHERE user_id = ? AND strftime("%Y-%m", expense_date) = ?', (user_id, month_year))
        exp_data = self.cursor.fetchone()
        total_exp = float(exp_data['total']) if exp_data['total'] else 0
        
        self.cursor.execute('SELECT SUM(amount) as total FROM income WHERE user_id = ? AND strftime("%Y-%m", income_date) = ?', (user_id, month_year))
        inc_data = self.cursor.fetchone()
        total_inc = float(inc_data['total']) if inc_data['total'] else 0

        # Oy davomida kunlik xarajatlar
        self.cursor.execute('''
            SELECT 
                expense_date,
                SUM(amount) as daily_total
            FROM expenses 
            WHERE user_id = ? AND strftime("%Y-%m", expense_date) = ?
            GROUP BY expense_date
            ORDER BY expense_date
        ''', (user_id, month_year))
        daily_expenses = []
        for row in self.cursor.fetchall():
            item = dict(row)
            if item.get('expense_date'):
                item['expense_date'] = self.parse_datetime(item['expense_date'])
            daily_expenses.append(item)
        
        return {
            'total_expense': total_exp,
            'total_income': total_inc,
            'balance': total_inc - total_exp,
            'expense_by_category': expense_by_category,
            'income_by_category': income_by_category,
            'daily_expenses': daily_expenses
        }

    # --- ADMIN SPECIFIC ---
    def get_all_users(self):
        self.cursor.execute('SELECT * FROM users ORDER BY registered_at DESC')
        rows = self.cursor.fetchall()
        result = []
        for row in rows:
            item = dict(row)
            if item.get('registered_at'):
                item['registered_at'] = self.parse_datetime(item['registered_at'])
            if item.get('last_seen'):
                item['last_seen'] = self.parse_datetime(item['last_seen'])
            result.append(item)
        return result

    def get_recent_logins(self, limit=10):
        self.cursor.execute('SELECT * FROM users ORDER BY last_seen DESC LIMIT ?', (limit,))
        rows = self.cursor.fetchall()
        result = []
        for row in rows:
            item = dict(row)
            if item.get('registered_at'):
                item['registered_at'] = self.parse_datetime(item['registered_at'])
            if item.get('last_seen'):
                item['last_seen'] = self.parse_datetime(item['last_seen'])
            result.append(item)
        return result

    def get_user_stats_by_id(self, user_id: int):
        self.cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user_row = self.cursor.fetchone()
        if not user_row: 
            return None
        
        user = dict(user_row)
        if user.get('registered_at'):
            user['registered_at'] = self.parse_datetime(user['registered_at'])
        if user.get('last_seen'):
            user['last_seen'] = self.parse_datetime(user['last_seen'])
        
        summary = self.get_financial_summary(user_id)
        debts = self.get_user_debts(user_id)
        return {'user': user, 'finance': summary, 'debts': debts}

    def get_bot_stats(self):
        self.cursor.execute('SELECT COUNT(*) as c FROM users')
        users = self.cursor.fetchone()['c']
        self.cursor.execute('SELECT COUNT(*) as c FROM reminders WHERE status="active"')
        rems = self.cursor.fetchone()['c']
        self.cursor.execute('SELECT COUNT(*) as c FROM debts WHERE status="active"')
        debts = self.cursor.fetchone()['c']
        self.cursor.execute('SELECT SUM(amount) as t FROM income')
        total_inc = self.cursor.fetchone()['t'] or 0
        self.cursor.execute('SELECT SUM(amount) as t FROM expenses')
        total_exp = self.cursor.fetchone()['t'] or 0
        return {
            'users': users, 
            'reminders': rems, 
            'debts': debts, 
            'total_income': float(total_inc) if total_inc else 0,
            'total_expense': float(total_exp) if total_exp else 0,
            'total_balance': float(total_inc - total_exp) if total_inc and total_exp else 0
        }

    def close(self):
        self.conn.close()

# ==================== SCHEDULER ====================
class ReminderScheduler:
    def __init__(self, db):
        self.db = db
        self.running = False

    def start(self):
        self.running = True
        thread = threading.Thread(target=self._check, daemon=True)
        thread.start()
        logger.info("Schedulers started")

    def _check(self):
        while self.running:
            try:
                now = datetime.now(TIMEZONE)
                now_str = now.isoformat().replace('T', ' ')
                
                logger.info(f"[SCHEDULER] Xorazm vaqti: {now.strftime('%Y-%m-%d %H:%M:%S')} → tekshiruv boshlandi")

                self.db.cursor.execute('''
                    SELECT r.*, u.telegram_id FROM reminders r
                    JOIN users u ON r.user_id = u.id
                    WHERE r.status="active" AND r.reminder_time <= ?
                ''', (now_str,))
                rows = self.db.cursor.fetchall()
                
                logger.info(f"[SCHEDULER] Topildi: {len(rows)} ta eslatma")
                
                for row in rows:
                    r = dict(row)
                    reminder_time = self.db.parse_datetime(r['reminder_time'])
                    msg = f"🔔 *ESLATMA: {r['title']}*\n📝 {r['description']}\n⏰ {reminder_time.strftime('%d.%m.%Y %H:%M')} (Xorazm)"
                    logger.info(f" → Yuborilishi kerak: {r['title']} | vaqt: {r['reminder_time']} | chat_id: {r['telegram_id']}")
                    self._send_in_thread(r['telegram_id'], msg, r['id'], r['repeat_type'])
                
                if now.hour == 20 and now.minute == 0:
                    self._send_daily_report_reminder(now)

                time.sleep(30)
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(60)

    def _send_daily_report_reminder(self, now):
        try:
            self.db.cursor.execute('SELECT telegram_id FROM users')
            users = self.db.cursor.fetchall()
            for u in users:
                chat_id = u['telegram_id']
                msg = "⏰ *Kechki Hisobot (20:00)*\n\nIltimos, bugungi kiritilgan xarajatlar va daromadlaringizni botga yozib qo'ying."
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._send_simple(chat_id, msg))
                    time.sleep(0.5)
                except: pass
                finally: loop.close()
            logger.info("Daily report sent to all users")
        except Exception as e:
            logger.error(f"Daily report error: {e}")

    def _send_in_thread(self, chat_id, text, rid, repeat_type):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._send(chat_id, text, rid, repeat_type))
        except Exception as e:
            logger.error(f"Send reminder failed: {e}")
        finally:
            loop.close()

    async def _send_simple(self, chat_id, text):
        from telegram import Bot
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN)

    async def _send(self, chat_id, text, rid, repeat_type):
        from telegram import Bot
        bot = Bot(token=BOT_TOKEN)
        try:
            await bot.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN)
            logger.info(f"[SUCCESS] {chat_id} ga yuborildi: {text}")
        except Exception as e:
            logger.error(f"[SEND ERROR] {chat_id} → {e}")
        
        if repeat_type == 'daily':
            self.db.cursor.execute('SELECT reminder_time FROM reminders WHERE id = ?', (rid,))
            old_time_res = self.db.cursor.fetchone()
            if old_time_res:
                old_time_str = old_time_res['reminder_time']
                old_time = self.db.parse_datetime(old_time_str)
                next_time = old_time + timedelta(days=1)
                self.db.update_reminder_time(rid, next_time)
        else:
            self.db.cursor.execute('UPDATE reminders SET status="sent" WHERE id=?', (rid,))
            self.db.conn.commit()

# ==================== MATNLI DIAGRAMMA FUNKSIYALARI ====================
def create_text_chart(data, title, total_amount):
    """Matnli diagramma yaratish"""
    if not data:
        return "📭 Ma'lumot yo'q"
    
    chart = f"📊 *{title}*\n\n"
    
    for item in data:
        percentage = (item['total'] / total_amount * 100) if total_amount > 0 else 0
        bar_length = int(percentage / 5)  # 20 belgi maksimal
        
        bar = "█" * bar_length + "░" * (20 - bar_length)
        
        chart += f"🏷️ *{item['category']}*\n"
        chart += f"{bar} {percentage:.1f}%\n"
        chart += f"💰 {item['total']:,.0f} so'm\n\n"
    
    return chart

def create_comparison_chart(income, expense, balance):
    """Daromad va xarajatni taqqoslash"""
    chart = "💰 *DAROMAD vs XARAJAT*\n\n"
    
    total = income + expense + abs(balance)
    
    # Daromad
    income_pct = (income / total * 100) if total > 0 else 0
    income_bar = "🟢" * int(income_pct / 5) + "⚪" * (20 - int(income_pct / 5))
    chart += f"💵 *Daromad:* {income:,.0f} so'm\n{income_bar} {income_pct:.1f}%\n\n"
    
    # Xarajat
    expense_pct = (expense / total * 100) if total > 0 else 0
    expense_bar = "🔴" * int(expense_pct / 5) + "⚪" * (20 - int(expense_pct / 5))
    chart += f"💰 *Xarajat:* {expense:,.0f} so'm\n{expense_bar} {expense_pct:.1f}%\n\n"
    
    # Qoldiq
    balance_icon = "🟢" if balance >= 0 else "🔴"
    balance_pct = (abs(balance) / total * 100) if total > 0 else 0
    balance_bar = balance_icon * int(balance_pct / 5) + "⚪" * (20 - int(balance_pct / 5))
    chart += f"{balance_icon} *Qoldiq:* {balance:,.0f} so'm\n{balance_bar} {balance_pct:.1f}%\n"
    
    return chart

# ==================== BOT LOGIC ====================
class SmartAssistantBot:
    def __init__(self):
        self.db = Database()
    
    def is_user_admin(self, telegram_id: int) -> bool:
        if telegram_id in ADMIN_IDS:
            return True
        
        user_info = self.db.get_user_info(telegram_id)
        if user_info and user_info.get('is_admin') == 1:
            return True
        
        return False

    def get_main_keyboard(self, telegram_id: int = None):
        base = [
            ["➕ ESLATMA", "💰 XARAJAT", "💵 DAROMAD"],
            ["📅 VAZIFA", "💸 QARZLARIM", "🎯 BYUDJET"],
            ["📊 HISOBOT", "⚙️ SOZLAMALAR", "🆘 YORDAM"]
        ]
        
        if telegram_id and self.is_user_admin(telegram_id):
            base.append(["👑 ADMIN PANEL"])
        
        return ReplyKeyboardMarkup(base, resize_keyboard=True)

    def get_settings_keyboard(self):
        return ReplyKeyboardMarkup([
            ["🇺🇿 O'zbek tili", "🇬🇧 English"],
            ["💱 Valyuta: UZS", "🗑️ Barchasini o'chirish"],
            ["🔙 ORQAGA"]
        ], resize_keyboard=True)

    def get_reminders_keyboard(self):
        return ReplyKeyboardMarkup([
            ["📋 BARCHA ESLATMALAR", "🗑️ O'CHIRISH"],
            ["🔙 ORQAGA"]
        ], resize_keyboard=True)

    def get_finance_keyboard(self):
        return ReplyKeyboardMarkup([
            ["📊 MATNLI DIAGRAMMALAR", "📋 BARCHA XARAJATLAR", "📋 BARCHA DAROMADLAR"],
            ["🔙 ORQAGA"]
        ], resize_keyboard=True)

    def get_debts_keyboard(self):
        return ReplyKeyboardMarkup([
            ["➕ QARZ QO'SHISH", "📋 BARCHA QARZLAR"],
            ["📊 QARZ STATISTIKASI", "🔙 ORQAGA"]
        ], resize_keyboard=True)

    def create_financial_report(self, user_id: int):
        """Matnli moliyaviy hisobot"""
        summary = self.db.get_financial_summary(user_id)
        
        report = "📊 *MOLIYAVIY HISOBOT*\n\n"
        
        # Umumiy statistika
        bal_color = "🟢" if summary['balance'] >= 0 else "🔴"
        report += f"💰 *UMUMIY STATISTIKA:*\n"
        report += f"💵 Jami daromad: *{summary['total_income']:,.0f}* so'm\n"
        report += f"💰 Jami xarajat: *{summary['total_expense']:,.0f}* so'm\n"
        report += f"{bal_color} Qoldiq: *{summary['balance']:,.0f}* so'm\n\n"
        
        # Daromad vs Xarajat diagrammasi
        report += create_comparison_chart(
            summary['total_income'], 
            summary['total_expense'], 
            summary['balance']
        )
        
        report += "\n" + "─" * 30 + "\n\n"
        
        # Xarajatlar taqsimoti
        if summary['expense_by_category']:
            report += create_text_chart(
                summary['expense_by_category'],
                "📉 XARAJATLAR TAQSIMOTI",
                summary['total_expense']
            )
        
        # Daromadlar taqsimoti
        if summary['income_by_category']:
            report += create_text_chart(
                summary['income_by_category'],
                "📈 DAROMADLAR TAQSIMOTI",
                summary['total_income']
            )
        
        # Top 5 xarajatlar
        if summary['expense_by_category']:
            top_expenses = sorted(summary['expense_by_category'], 
                                key=lambda x: x['total'], reverse=True)[:5]
            report += "🏆 *TOP 5 XARAJATLAR:*\n\n"
            for i, item in enumerate(top_expenses):
                medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i]
                report += f"{medal} *{item['category']}*: {item['total']:,.0f} so'm\n"
        
        return report

    async def start(self, update, context):
        user = update.effective_user
        is_admin = self.db.add_user(user.id, user.username, user.full_name)
        
        txt = f"👋 Salom, {user.full_name}!\n\n🤖 *Smart Assistant Bot* ga xush kelibsiz."
        if is_admin: 
            txt += "\n\n👑 Siz Admin sifatida tizimga kirdingiz."
            user_info = self.db.get_user_info(user.id)
            if user_info:
                self.db.cursor.execute('UPDATE users SET is_admin = 1 WHERE telegram_id = ?', (user.id,))
                self.db.conn.commit()
        
        await update.message.reply_text(
            txt, 
            reply_markup=self.get_main_keyboard(user.id), 
            parse_mode=ParseMode.MARKDOWN
        )

    async def force_admin(self, update, context):
        uid = update.effective_user.id
        if uid in ADMIN_IDS:
            self.db.cursor.execute('UPDATE users SET is_admin = 1 WHERE telegram_id = ?', (uid,))
            self.db.conn.commit()
            await update.message.reply_text("✅ Admin statusi o'rnatildi! Endi /start buyrug'ini yuboring.")
        else:
            await update.message.reply_text("❌ Siz admin emassiz.")

    async def handle_message(self, update, context):
        text = update.message.text
        uid = update.effective_user.id
        user_id = self.db.get_user_id(uid)
        
        if not user_id:
            await update.message.reply_text("Xatolik. Iltimos /start bosing.")
            return

        is_admin_status = self.is_user_admin(uid)
        
        logger.info(f"[MESSAGE] Foydalanuvchi: {uid}, Matn: {text}, User_data: {context.user_data}")
        
        if text == "🔙 ORQAGA":
            context.user_data.clear()
            await update.message.reply_text("Asosiy menyu", reply_markup=self.get_main_keyboard(uid))
            return

        if text == "⚙️ SOZLAMALAR":
            context.user_data.clear()
            await update.message.reply_text("⚙️ *SOZLAMALAR*", reply_markup=self.get_settings_keyboard(), parse_mode=ParseMode.MARKDOWN)
            return

        # ================= ESLATMALAR =================
        elif text == "➕ ESLATMA":
            context.user_data.clear()
            await update.message.reply_text(
                "📝 *ESLATMALAR MENYUSI*",
                reply_markup=ReplyKeyboardMarkup([
                    ["➕ YANGI ESLATMA", "📋 BARCHA ESLATMALAR"],
                    ["🗑️ O'CHIRISH", "🔙 ORQAGA"]
                ], resize_keyboard=True),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        elif text == "📋 BARCHA ESLATMALAR":
            reminders = self.db.get_all_reminders(user_id)
            if not reminders:
                await update.message.reply_text("📭 Hech qanday eslatma yo'q.", reply_markup=self.get_reminders_keyboard())
            else:
                res = "📋 *BARCHA ESLATMALAR:*\n\n"
                for r in reminders:
                    status_icon = "🟢" if r['status'] == 'active' else "🔴"
                    repeat_icon = "🔁" if r['repeat_type'] == 'daily' else "📅"
                    time_str = r['reminder_time'].strftime('%d.%m.%Y %H:%M') if r['reminder_time'] else "Noma'lum"
                    res += f"{status_icon} *{r['title']}*\n"
                    if r['description']:
                        res += f"📝 {r['description']}\n"
                    res += f"⏰ {time_str} {repeat_icon} (Xorazm)\n"
                    res += f"🆔 ID: `{r['id']}`\n"
                    res += "─" * 20 + "\n"
                
                res += "\n🗑️ *O'chirish uchun ID raqamini yuboring*"
                await update.message.reply_text(res, parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_reminders_keyboard())
                context.user_data['action'] = 'DELETE_REMINDER'
            return
        
        elif text == "🗑️ O'CHIRISH" and context.user_data.get('action') == 'DELETE_REMINDER':
            await update.message.reply_text(
                "🗑️ *ESLATMA O'CHIRISH*\n\n"
                "1️⃣ *1 ta eslatmani o'chirish:* ID raqamini yuboring\n"
                "2️⃣ *Barcha eslatmalarni o'chirish:* `HAMMASI` deb yozing\n\n"
                "⚠️ *Diqqat:* Bu amalni qaytarib bo'lmaydi!",
                reply_markup=ReplyKeyboardMarkup([["🔙 BEKOR QILISH"]], resize_keyboard=True),
                parse_mode=ParseMode.MARKDOWN
            )
            context.user_data['action'] = 'DELETE_REMINDER_CONFIRM'
            return
        
        elif text == "➕ YANGI ESLATMA":
            context.user_data.clear()
            context.user_data['rem_step'] = 1
            await update.message.reply_text("🔔 *Yangi eslatma qo'shish*\n\n1-qadam. Eslatma *nomini* yozing:",
                reply_markup=ReplyKeyboardMarkup([["🔙 Bekor qilish"]], resize_keyboard=True), parse_mode=ParseMode.MARKDOWN)
            return

        # ================= MOLIYAVIY HISOBOT =================
        elif text == "📊 HISOBOT":
            await update.message.reply_text(
                "📊 *MOLIYAVIY HISOBOT MENYUSI*",
                reply_markup=self.get_finance_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # ================= MATNLI DIAGRAMMALAR =================
        elif text == "📊 MATNLI DIAGRAMMALAR":
            try:
                report = self.create_financial_report(user_id)
                await update.message.reply_text(
                    report,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=self.get_finance_keyboard()
                )
            except Exception as e:
                logger.error(f"Matnli hisobotda xato: {e}")
                await update.message.reply_text(
                    "❌ Hisobot yaratishda xatolik yuz berdi.",
                    reply_markup=self.get_finance_keyboard()
                )
            return
        
        elif text == "📋 BARCHA XARAJATLAR":
            expenses = self.db.get_all_expenses(user_id)
            if not expenses:
                await update.message.reply_text("📭 Xarajatlar yo'q.", reply_markup=self.get_finance_keyboard())
            else:
                res = "💰 *BARCHA XARAJATLAR:*\n\n"
                total = 0
                for exp in expenses:
                    total += exp['amount']
                    date_str = exp['expense_date'].strftime('%Y-%m-%d') if exp['expense_date'] else "Noma'lum"
                    res += f"📅 *{date_str}*\n"
                    res += f"🏷️ Kategoriya: {exp['category']}\n"
                    res += f"💸 Miqdor: {exp['amount']:,.0f} so'm\n"
                    if exp['description']:
                        res += f"📝 Tavsif: {exp['description']}\n"
                    res += f"🆔 ID: `{exp['id']}`\n"
                    res += "─" * 20 + "\n"
                
                res += f"\n💰 *Jami xarajat: {total:,.0f} so'm*"
                await update.message.reply_text(res, parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_finance_keyboard())
            return
        
        elif text == "📋 BARCHA DAROMADLAR":
            incomes = self.db.get_all_income(user_id)
            if not incomes:
                await update.message.reply_text("📭 Daromadlar yo'q.", reply_markup=self.get_finance_keyboard())
            else:
                res = "💵 *BARCHA DAROMADLAR:*\n\n"
                total = 0
                for inc in incomes:
                    total += inc['amount']
                    date_str = inc['income_date'].strftime('%Y-%m-%d') if inc['income_date'] else "Noma'lum"
                    res += f"📅 *{date_str}*\n"
                    res += f"🏷️ Manba: {inc['category']}\n"
                    res += f"💰 Miqdor: {inc['amount']:,.0f} so'm\n"
                    if inc['description']:
                        res += f"📝 Tavsif: {inc['description']}\n"
                    res += f"🆔 ID: `{inc['id']}`\n"
                    res += "─" * 20 + "\n"
                
                res += f"\n💰 *Jami daromad: {total:,.0f} so'm*"
                await update.message.reply_text(res, parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_finance_keyboard())
            return

        # ================= QARZLAR =================
        elif text == "💸 QARZLARIM":
            await update.message.reply_text(
                "💸 *QARZLAR MENYUSI*",
                reply_markup=self.get_debts_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        elif text == "📋 BARCHA QARZLAR":
            debts = self.db.get_all_debts(user_id)
            if not debts:
                await update.message.reply_text("📭 Qarzlar yo'q.", reply_markup=self.get_debts_keyboard())
            else:
                res = "💸 *BARCHA QARZLAR:*\n\n"
                active_total = 0
                returned_total = 0
                
                for d in debts:
                    status_icon = "🟢" if d['status'] == 'active' else "✅"
                    type_icon = "📤" if d['debt_type'] == 'gave' else "📥"
                    type_text = "Berdingiz" if d['debt_type'] == 'gave' else "Oldingiz"
                    
                    res += f"{status_icon} {type_icon} *{d['person_name']}*\n"
                    res += f"💰 Miqdor: {d['amount']:,.0f} so'm\n"
                    res += f"📋 Turi: {type_text}\n"
                    
                    if d['due_date']:
                        due_str = d['due_date'].strftime('%d.%m.%Y') if d['due_date'] else "Noma'lum"
                        res += f"📅 Muddat: {due_str}\n"
                    
                    if d['status'] == 'returned' and d['return_date']:
                        return_str = d['return_date'].strftime('%d.%m.%Y %H:%M') if d['return_date'] else "Noma'lum"
                        res += f"✅ Qaytarildi: {return_str}\n"
                    
                    if d['description']:
                        res += f"📝 Izoh: {d['description']}\n"
                    
                    res += f"🆔 ID: `{d['id']}`\n"
                    res += "─" * 20 + "\n"
                    
                    if d['status'] == 'active':
                        active_total += d['amount']
                    else:
                        returned_total += d['amount']
                
                res += f"\n📊 *Statistika:*\n"
                res += f"🟢 Faol qarzlar: {active_total:,.0f} so'm\n"
                res += f"✅ Qaytarilgan: {returned_total:,.0f} so'm\n"
                res += f"💰 Jami: {(active_total + returned_total):,.0f} so'm\n\n"
                res += "🔐 *Qaytarish uchun ID raqamini yuboring*"
                
                await update.message.reply_text(res, parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_debts_keyboard())
                context.user_data['action'] = 'RETURN_DEBT'
            return
        
        elif text == "📊 QARZ STATISTIKASI":
            summary = self.db.get_debt_summary(user_id)
            if not summary:
                await update.message.reply_text("📭 Qarz statistikasi yo'q.", reply_markup=self.get_debts_keyboard())
            else:
                res = "📊 *QARZ STATISTIKASI:*\n\n"
                
                gave_total = 0
                took_total = 0
                
                for item in summary:
                    if item['debt_type'] == 'gave':
                        gave_total += item['total_amount']
                        icon = "📤"
                        type_text = "Berilgan"
                    else:
                        took_total += item['total_amount']
                        icon = "📥"
                        type_text = "Olingan"
                    
                    res += f"{icon} *{item['person_name']}* ({type_text})\n"
                    res += f"💰 Miqdor: {item['total_amount']:,.0f} so'm\n"
                    res += f"📋 Qarzlar soni: {item['count']}\n"
                    
                    if item['earliest_due']:
                        earliest = self.db.parse_datetime(item['earliest_due'])
                        latest = self.db.parse_datetime(item['latest_due'])
                        earliest_str = earliest.strftime('%d.%m') if earliest else "Noma'lum"
                        latest_str = latest.strftime('%d.%m') if latest else "Noma'lum"
                        res += f"📅 Muddat: {earliest_str} - {latest_str}\n"
                    
                    res += "─" * 15 + "\n"
                
                res += f"\n📈 *UMUMIY:*\n"
                res += f"📤 Berilgan: {gave_total:,.0f} so'm\n"
                res += f"📥 Olingan: {took_total:,.0f} so'm\n"
                res += f"⚖️ Farq: {(took_total - gave_total):,.0f} so'm\n"
                
                await update.message.reply_text(res, parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_debts_keyboard())
            return
        
        elif text == "➕ QARZ QO'SHISH":
            await update.message.reply_text(
                "🆕 *QARZ QO'SHISH*\n\n"
                "📝 *Format:* `Ism | Miqdor | Turi | Muddat | Izoh`\n"
                "📋 *Namuna 1:* `Ali | 500000 | berdim | 15.12.2024 | Mahsulot uchun`\n"
                "📋 *Namuna 2:* `Vali | 300000 | oldim | 20.12.2024 | Qarz berdi`\n\n"
                "ℹ️ *Eslatma:*\n"
                "- Turi: `berdim` yoki `oldim`\n"
                "- Muddat: `DD.MM.YYYY` (ixtiyoriy)\n"
                "- Izoh: (ixtiyoriy)",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=ReplyKeyboardRemove()
            )
            context.user_data['action'] = 'ADD_DEBT'
            return

        # ================= ADMIN PANEL =================
        if text == "👑 ADMIN PANEL":
            if is_admin_status:
                stats = self.db.get_bot_stats()
                msg = f"👑 *ADMIN PANEL*\n\n"
                msg += f"👥 Foydalanuvchilar: {stats['users']}\n"
                msg += f"🔔 Faol eslatmalar: {stats['reminders']}\n"
                msg += f"💸 Faol qarzlar: {stats['debts']}\n"
                msg += f"💰 Bot balansi: {stats['total_balance']:,.0f} so'm\n\n"
                msg += "Boshqaruv bo'limini tanlang:"
                
                await update.message.reply_text(
                    msg, parse_mode=ParseMode.MARKDOWN,
                    reply_markup=ReplyKeyboardMarkup([
                        ["👥 FOYDALANUVCHILAR", "🕒 SO'NGGI KIRISHLAR"],
                        ["📢 XABAR YUBORISH", "📊 GLOBAL STATISTIKA"],
                        ["🔙 ASOSIY MENYU"]
                    ], resize_keyboard=True)
                )
                context.user_data['admin_mode'] = True
            else:
                await update.message.reply_text("❌ Bu funksiya faqat adminlar uchun!")
            return

        # Admin Panel ichidagi harakatlar
        if context.user_data.get('admin_mode'):
            if text == "👥 FOYDALANUVCHILAR":
                users = self.db.get_all_users()
                if not users: 
                    await update.message.reply_text("Foydalanuvchilar yo'q.")
                else:
                    res = "👥 *BARCHA FOYDALANUVCHILAR (Ro'yxat)*\n\n"
                    for u in users[:10]:
                        admin_badge = "👑 " if u['is_admin'] else ""
                        registered = u['registered_at'].strftime('%Y-%m-%d %H:%M') if u['registered_at'] else "Noma'lum"
                        res += f"• {admin_badge}*{u['full_name']}*\n  ID: {u['id']} | @{u['username'] or 'no_user'}\n  📅 {registered}\n\n"
                    if len(users) > 10: 
                        res += f"... va yana {len(users) - 10} ta foydalanuvchi."
                    res += "\n💡 *Profilni ko'rish uchun ID yuboring.*"
                    await update.message.reply_text(res, parse_mode=ParseMode.MARKDOWN)
                return
            
            elif text == "🕒 SO'NGGI KIRISHLAR":
                users = self.db.get_recent_logins(10)
                if not users: 
                    await update.message.reply_text("Hali hech kim kirmagan.")
                else:
                    res = "🕒 *SO'NGGI KIRISHLAR (Faollik)*\n\n"
                    for u in users:
                        admin_badge = "👑 " if u['is_admin'] else ""
                        seen_time = u['last_seen'].strftime('%Y-%m-%d %H:%M') if u['last_seen'] else "Noma'lum"
                        res += f"{admin_badge}*{u['full_name']}*\n  ⏰ {seen_time}\n  🆔 ID: {u['id']}\n\n"
                    res += "\n💡 *Profilni ko'rish uchun ID yuboring.*"
                    await update.message.reply_text(res, parse_mode=ParseMode.MARKDOWN)
                return
            
            elif text.isdigit():
                target_id = int(text)
                stats = self.db.get_user_stats_by_id(target_id)
                if stats:
                    u = stats['user']; f = stats['finance']; d = stats['debts']
                    bal_color = "🟢" if f['balance'] >= 0 else "🔴"
                    res = f"👤 *FOYDALANUVCHI PROFILI*\n\n👤 Ismi: {u['full_name']}\n🆔 ID: {u['id']}\n💵 Daromad: {f['total_income']:,.0f}\n💰 Xarajat: {f['total_expense']:,.0f}\n{bal_color} *QOLDIQ:* {f['balance']:,.0f}\n\n💸 *Faol qarzlar:*\n"
                    if d:
                        for debt in d:
                            icon = "📤" if debt['debt_type'] == 'gave' else "📥"
                            res += f"{icon} {debt['person_name']}: {debt['amount']:,.0f}\n"
                    else: 
                        res += "Qarzlar yo'q."
                    await update.message.reply_text(res, parse_mode=ParseMode.MARKDOWN)
                else: 
                    await update.message.reply_text("❌ Topilmadi.")
                return
            
            elif text == "📢 XABAR YUBORISH":
                await update.message.reply_text("✍️ Barchaga xabarni yozing:")
                context.user_data['broadcasting'] = True
                return
            
            elif context.user_data.get('broadcasting'):
                users = self.db.get_all_users()
                count = 0
                for u in users:
                    try:
                        await update.effective_message.bot.send_message(u['telegram_id'], f"📢 *ADMIN XABARI*\n\n{text}", parse_mode=ParseMode.MARKDOWN)
                        count += 1
                        await asyncio.sleep(0.05)
                    except: 
                        pass
                await update.message.reply_text(f"✅ {count} ta kishiga yuborildi.")
                context.user_data['broadcasting'] = False
                return
            
            elif text == "📊 GLOBAL STATISTIKA":
                stats = self.db.get_bot_stats()
                res = f"📊 *GLOBAL STATISTIKA*\n\n"
                res += f"👥 Jami foydalanuvchilar: {stats['users']}\n"
                res += f"🔔 Faol eslatmalar: {stats['reminders']}\n"
                res += f"💸 Faol qarzlar: {stats['debts']}\n"
                res += f"💰 Bot balansi: {stats['total_balance']:,.0f} so'm"
                await update.message.reply_text(res, parse_mode=ParseMode.MARKDOWN)
                return
            
            elif text == "🔙 ASOSIY MENYU":
                context.user_data.clear()
                await update.message.reply_text("Asosiy menyu", reply_markup=self.get_main_keyboard(uid))
                return

        # ================= SOZLAMALAR =================
        if text == "🗑️ Barchasini o'chirish":
            await update.message.reply_text("⚠️ Barcha ma'lumot o'chirilsinmi? `HA` / `YO'Q`", parse_mode=ParseMode.MARKDOWN)
            context.user_data['action'] = 'CONFIRM_CLEAR'
            return
        elif text == "💱 Valyuta: UZS":
            self.db.update_user_settings(user_id, currency='UZS')
            await update.message.reply_text("✅ Valyuta: O'zbek So'mi (UZS)", reply_markup=self.get_settings_keyboard())
            return
        elif text == "🇺🇿 O'zbek tili":
            self.db.update_user_settings(user_id, lang='uz')
            await update.message.reply_text("✅ Til o'zgartirildi: O'zbek tili", reply_markup=self.get_settings_keyboard())
            return
        elif text == "🇬🇧 English":
            self.db.update_user_settings(user_id, lang='en')
            await update.message.reply_text("✅ Language changed: English", reply_markup=self.get_settings_keyboard())
            return

        # ================= ESLATMA QO'SHISH (DAVOMI) =================
        if 'rem_step' in context.user_data:
            step = context.user_data['rem_step']
            if text == "🔙 Bekor qilish":
                context.user_data.clear()
                await update.message.reply_text("Bekor qilindi.", reply_markup=self.get_main_keyboard(uid))
                return
            
            if step == 1:
                context.user_data['rem_title'] = text
                context.user_data['rem_step'] = 2
                await update.message.reply_text(f"2-qadam. Eslatma *vaqtini* yozing (HH:MM):\nMasalan: 14:30", 
                                              reply_markup=ReplyKeyboardMarkup([["🔙 Bekor qilish"]], resize_keyboard=True), parse_mode=ParseMode.MARKDOWN)
                return
            
            if step == 2:
                try:
                    time_obj = datetime.strptime(text, "%H:%M").time()
                    now = datetime.now(TIMEZONE)
                    rem_time = datetime.combine(now.date(), time_obj, tzinfo=TIMEZONE)
                    if rem_time < now: 
                        rem_time += timedelta(days=1)
                    context.user_data['rem_time'] = rem_time
                    context.user_data['rem_step'] = 3
                    await update.message.reply_text("3-qadam. Qachon eslatilsin?", 
                                                  reply_markup=ReplyKeyboardMarkup([["🔁 Har kuni", "📅 Bugun"], ["🔙 Bekor qilish"]], resize_keyboard=True), parse_mode=ParseMode.MARKDOWN)
                    return
                except ValueError:
                    await update.message.reply_text("❌ Vaqt formati noto'g'ri. `HH:MM`", reply_markup=ReplyKeyboardMarkup([["🔙 Bekor qilish"]], resize_keyboard=True))
                    return
            
            if step == 3:
                if text == "🔁 Har kuni":
                    repeat = "daily"
                elif text == "📅 Bugun":
                    repeat = "none"
                else:
                    await update.message.reply_text("Iltimos, variantni tanlang.", reply_markup=ReplyKeyboardMarkup([["🔁 Har kuni", "📅 Bugun"], ["🔙 Bekor qilish"]], resize_keyboard=True))
                    return
                title = context.user_data.get('rem_title')
                rtime = context.user_data.get('rem_time')
                if self.db.add_reminder(user_id, title, "", rtime, repeat):
                    msg = f"✅ *Eslatma saqlandi!*\n\n📌 {title}\n⏰ {rtime.strftime('%d.%m %H:%M')} (Xorazm)"
                    if repeat == 'daily': 
                        msg += "\n🔁 Har kuni takrorlanadi"
                    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_main_keyboard(uid))
                else:
                    await update.message.reply_text("❌ Xatolik yuz berdi.", reply_markup=self.get_main_keyboard(uid))
                context.user_data.clear()
                return

        # ================= XARAJAT QO'SHISH =================
        elif text == "💰 XARAJAT":
            await update.message.reply_text("💰 *XARAJAT QO'SHISH*\n\nFormat: `Miqdor | Kategoriya | Tavsif`\nNamuna: `50000 | Taom | Lagmon`", parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove())
            context.user_data['action'] = 'ADD_EXPENSE'
            return

        # ================= DAROMAD QO'SHISH =================
        elif text == "💵 DAROMAD":
            await update.message.reply_text("💵 *DAROMAD QO'SHISH*\n\nFormat: `Miqdor | Manba | Tavsif`\nNamuna: `1000000 | Oylik Maosh | IT`", parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove())
            context.user_data['action'] = 'ADD_INCOME'
            return
        
        # ================= BYUDJET =================
        elif text == "🎯 BYUDJET":
            budgets = self.db.get_budgets(user_id)
            if not budgets:
                await update.message.reply_text("🎯 *BYUDJET*\nLimit belgilanmagan.", reply_markup=ReplyKeyboardMarkup([["➕ LIMIT QO'SHISH"], ["🔙 ORQAGA"]], resize_keyboard=True))
            else:
                res = "🎯 *BYUDJET:*\n\n"
                for b in budgets:
                    pct = (b['current_spent']/b['monthly_limit'])*100 if b['monthly_limit'] else 0
                    bar = "█"*int(pct/10) + "░"*(10-int(pct/10))
                    res += f"📂 {b['category']}\n{bar} {pct:.0f}%\n{b['current_spent']:,.0f} / {b['monthly_limit']:,.0f}\n\n"
                await update.message.reply_text(res, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardMarkup([["➕ LIMIT QO'SHISH"], ["🔙 ORQAGA"]], resize_keyboard=True))
            return
        
        elif text == "➕ LIMIT QO'SHISH":
            await update.message.reply_text("🎯 *LIMIT BELGILASH*\nFormat: `Kategoriya | Limit`\nNamuna: `Transport | 1000000`", parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove())
            context.user_data['action'] = 'SET_BUDGET'
            return

        # ================= VAZIFALAR =================
        elif text == "📅 VAZIFA":
            await update.message.reply_text("📅 *VAZIFA QO'SHISH*\nFormat: `Nomi | Vaqt`\nNamuna: `Dars | 08:30`", parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove())
            context.user_data['action'] = 'ADD_ACTIVITY'
            return
        
        elif text == "📋 BUGUNGI VAZIFALAR":
            acts = self.db.get_activities(user_id)
            if not acts: 
                await update.message.reply_text("Bugun vazifalar yo'q.")
            else:
                res = "📅 *BUGUN:*\n\n"
                for a in acts:
                    icon = "✅" if a['status'] == 'completed' else "⏳"
                    t = f"({a['activity_time']}) " if a['activity_time'] else ""
                    res += f"{icon} {t}{a['activity_name']} _[ID: {a['id']}]_\n"
                res += "\nBajarilganini belgilash uchun ID ni yuboring."
                await update.message.reply_text(res, parse_mode=ParseMode.MARKDOWN)
                context.user_data['action'] = 'COMPLETE_ACTIVITY'
            return

        # ================= ESLATMALARIM =================
        elif text == "🔔 ESLATMALARIM":
            rems = self.db.get_user_reminders(user_id)
            if not rems: 
                await update.message.reply_text("Eslatmalar yo'q.")
            else:
                res = "🔔 *ESLATMALAR:*\n\n"
                for r in rems:
                    rep = "🔁" if r['repeat_type'] == 'daily' else "📅"
                    time_str = r['reminder_time'].strftime('%d.%m.%Y %H:%M') if r['reminder_time'] else "Noma'lum"
                    res += f"{rep} *{r['title']}* - {time_str} (Xorazm)\n   ID: `{r['id']}`\n\n"
                res += "O'chirish uchun ID ni yuboring."
                await update.message.reply_text(res, parse_mode=ParseMode.MARKDOWN)
                context.user_data['action'] = 'DELETE_REMINDER_SINGLE'
            return

        # ================= YORDAM =================
        elif text == "🆘 YORDAM":
            help_text = """
🆘 *YORDAM MENYUSI*

Botdan foydalanish bo'yicha qo'llanma:

📊 *MATNLI DIAGRAMMALAR:*
- 📊 MATNLI DIAGRAMMALAR: Matn shaklida diagrammalar

📝 *ESLATMALAR:*
- ➕ ESLATMA: Yangi eslatma qo'shish
- 📋 BARCHA ESLATMALAR: Barcha eslatmalarni ko'rish
- 🗑️ O'CHIRISH: Eslatmalarni o'chirish

💰 *MOLIYA:*
- 💰 XARAJAT: Xarajatlarni kiritish
- 💵 DAROMAD: Daromadlarni kiritish
- 📋 BARCHA XARAJATLAR/DAROMADLAR: Tarixni ko'rish

💸 *QARZLAR:*
- ➕ QARZ QO'SHISH: Yangi qarz qo'shish
- 📋 BARCHA QARZLAR: Barcha qarzlarni ko'rish
- 📊 QARZ STATISTIKASI: Statistik ma'lumotlar

🎯 *BYUDJET:*
- ➕ LIMIT QO'SHISH: Byudjet limitini belgilash

📅 *VAZIFALAR:*
- 📅 VAZIFA: Kunlik vazifalarni boshqarish
- 📋 BUGUNGI VAZIFALAR: Bugungi vazifalarni ko'rish

⚙️ *SOZLAMALAR:*
- Til va valyutani o'zgartirish
- Barcha ma'lumotlarni o'chirish

Agar muammo bo'lsa, /start buyrug'ini qayta yuboring.
            """
            await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

        # ================= ACTION HANDLERS =================
        else:
            action = context.user_data.get('action')
            
            # ESLATMA O'CHIRISH (HAMMASI)
            if action == 'DELETE_REMINDER_CONFIRM':
                if text.upper() == 'HAMMASI':
                    count = self.db.delete_all_reminders(user_id)
                    await update.message.reply_text(f"✅ Barcha eslatmalar o'chirildi ({count} ta)", reply_markup=self.get_main_keyboard(uid))
                elif text == "🔙 BEKOR QILISH":
                    await update.message.reply_text("Bekor qilindi.", reply_markup=self.get_reminders_keyboard())
                else:
                    try:
                        rid = int(text)
                        if self.db.delete_reminder(rid, user_id): 
                            await update.message.reply_text("✅ Eslatma o'chirildi.", reply_markup=self.get_main_keyboard(uid))
                        else: 
                            await update.message.reply_text("❌ Topilmadi.", reply_markup=self.get_reminders_keyboard())
                    except: 
                        await update.message.reply_text("❌ ID raqam kiriting.", reply_markup=self.get_reminders_keyboard())
                context.user_data['action'] = None
            
            # XARAJAT QO'SHISH
            elif action == 'ADD_EXPENSE':
                parts = [p.strip() for p in text.split('|')]
                if len(parts) >= 2:
                    try:
                        amt = float(parts[0].replace(',', '.'))
                        cat = parts[1]
                        desc = parts[2] if len(parts) > 2 else ""
                        if self.db.add_expense(user_id, amt, cat, desc):
                            await update.message.reply_text(f"✅ Xarajat qo'shildi: {amt:,.0f} so'm", reply_markup=self.get_main_keyboard(uid))
                    except: 
                        await update.message.reply_text("❌ Xato format.", reply_markup=self.get_main_keyboard(uid))
                context.user_data['action'] = None

            # DAROMAD QO'SHISH
            elif action == 'ADD_INCOME':
                parts = [p.strip() for p in text.split('|')]
                if len(parts) >= 2:
                    try:
                        amt = float(parts[0].replace(',', '.'))
                        cat = parts[1]
                        desc = parts[2] if len(parts) > 2 else ""
                        if self.db.add_income(user_id, amt, cat, desc):
                            await update.message.reply_text(f"✅ Daromad qo'shildi: {amt:,.0f} so'm", reply_markup=self.get_main_keyboard(uid))
                    except: 
                        await update.message.reply_text("❌ Xato format.", reply_markup=self.get_main_keyboard(uid))
                context.user_data['action'] = None

            # QARZ QO'SHISH
            elif action == 'ADD_DEBT':
                parts = [p.strip() for p in text.split('|')]
                if len(parts) >= 3:
                    try:
                        name = parts[0]
                        amt = float(parts[1].replace(',', '.'))
                        dtype = parts[2].lower()
                        
                        due_date = None
                        if len(parts) >= 4 and parts[3]:
                            try:
                                due_date_str = parts[3]
                                due_date_obj = datetime.strptime(due_date_str, "%d.%m.%Y")
                                due_date = due_date_obj
                            except Exception as e:
                                logger.error(f"Due date parsing error: {e}")
                                due_date = None
                        
                        description = ""
                        if len(parts) >= 5:
                            description = parts[4]
                        
                        if dtype == 'berdim':
                            debt_type = 'gave'
                        elif dtype == 'oldim':
                            debt_type = 'took'
                        else:
                            debt_type = dtype
                        
                        if self.db.add_debt(user_id, name, amt, debt_type, description, due_date):
                            msg = f"✅ Qarz qo'shildi:\n👤 {name}\n💰 {amt:,.0f} so'm\n"
                            msg += f"📋 {'Berdingiz' if debt_type == 'gave' else 'Oldingiz'}\n"
                            if due_date:
                                msg += f"📅 Muddat: {parts[3]}\n"
                            if description:
                                msg += f"📝 Izoh: {description}"
                            
                            await update.message.reply_text(msg, reply_markup=self.get_main_keyboard(uid))
                        else:
                            await update.message.reply_text("❌ Qarz qo'shishda xatolik.", reply_markup=self.get_main_keyboard(uid))
                    except Exception as e:
                        logger.error(f"Debt add error: {e}")
                        await update.message.reply_text(f"❌ Xato format yoki tizim xatosi: {str(e)}", reply_markup=self.get_main_keyboard(uid))
                else:
                    await update.message.reply_text("❌ Format noto'g'ri. Format: `Ism | Miqdor | Turi | Muddat | Izoh`", reply_markup=self.get_main_keyboard(uid))
                context.user_data['action'] = None

            # BYUDJET LIMITI
            elif action == 'SET_BUDGET':
                parts = [p.strip() for p in text.split('|')]
                if len(parts) >= 2:
                    try:
                        cat, amt = parts[0], float(parts[1].replace(',', '.'))
                        self.db.set_budget_limit(user_id, cat, amt)
                        await update.message.reply_text(f"✅ Limit belgilandi: {cat} → {amt:,.0f} so'm", reply_markup=self.get_main_keyboard(uid))
                    except: 
                        await update.message.reply_text("❌ Xato.", reply_markup=self.get_main_keyboard(uid))
                context.user_data['action'] = None

            # VAZIFA QO'SHISH
            elif action == 'ADD_ACTIVITY':
                parts = [p.strip() for p in text.split('|')]
                if len(parts) >= 1:
                    name = parts[0]
                    time_str = parts[1] if len(parts) > 1 else None
                    if self.db.add_activity(user_id, name, time_str):
                        await update.message.reply_text("✅ Vazifa qo'shildi.", reply_markup=self.get_main_keyboard(uid))
                    else:
                        await update.message.reply_text("❌ Xato.", reply_markup=self.get_main_keyboard(uid))
                context.user_data['action'] = None

            # ESLATMA O'CHIRISH (1 TA)
            elif action == 'DELETE_REMINDER_SINGLE':
                try:
                    rid = int(text)
                    if self.db.delete_reminder(rid, user_id): 
                        await update.message.reply_text("🗑️ O'chirildi.", reply_markup=self.get_main_keyboard(uid))
                    else: 
                        await update.message.reply_text("❌ Topilmadi.", reply_markup=self.get_main_keyboard(uid))
                except: 
                    await update.message.reply_text("❌ ID raqam kiriting.", reply_markup=self.get_main_keyboard(uid))
                context.user_data['action'] = None

            # QARZ QAYTARISH
            elif action == 'RETURN_DEBT':
                try:
                    debt_id = int(text)
                    self.db.close_debt(debt_id, user_id)
                    await update.message.reply_text("✅ Qarz yopildi.", reply_markup=self.get_main_keyboard(uid))
                except: 
                    await update.message.reply_text("❌ Xato.", reply_markup=self.get_main_keyboard(uid))
                context.user_data['action'] = None
            
            # VAZIFA BAJARILDI
            elif action == 'COMPLETE_ACTIVITY':
                try:
                    act_id = int(text)
                    self.db.complete_activity(act_id, user_id)
                    await update.message.reply_text("✅ Bajarildi.", reply_markup=self.get_main_keyboard(uid))
                except: 
                    await update.message.reply_text("❌ Xato.", reply_markup=self.get_main_keyboard(uid))
                context.user_data['action'] = None

            # BARCHASINI O'CHIRISH
            elif action == 'CONFIRM_CLEAR':
                if text.upper() == 'HA':
                    self.db.clear_all_user_data(user_id)
                    await update.message.reply_text("🗑️ Barcha ma'lumot o'chirildi.", reply_markup=self.get_main_keyboard(uid))
                else: 
                    await update.message.reply_text("Bekor qilindi.", reply_markup=self.get_settings_keyboard())
                context.user_data['action'] = None
            
            # BOSHQA HARAKAT
            else:
                await update.message.reply_text("Buyruq aniqlanmadi. Menyuni tanlang.", reply_markup=self.get_main_keyboard(uid))

# ==================== FLASK APP ====================
app = Flask(__name__)

# Bot obyektini yaratish
bot_instance = SmartAssistantBot()

# Application yaratish
telegram_app = Application.builder().token(BOT_TOKEN).build()

# Handlers qo'shish
telegram_app.add_handler(CommandHandler("start", bot_instance.start))
telegram_app.add_handler(CommandHandler("admin", bot_instance.force_admin))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot_instance.handle_message))

# Database va scheduler
db = Database()
scheduler = ReminderScheduler(db)
scheduler.start()

print("🤖 Bot Flask + Polling rejimida ishga tushmoqda...")
print(f"👑 Admin ID: {ADMIN_IDS[0]}")
print(f"⏰ Vaqt zonasi: Xorazm (Asia/Tashkent)")
print("✅ SQLite datetime xatosi tuzatildi!")

# ==================== FLASK ENDPOINTS ====================
@app.route('/')
def home():
    return "🤖 Smart Assistant Bot ishlayapti! ✅ (Xorazm vaqti)"

@app.route('/health')
def health():
    return "OK", 200

# ==================== ASOSIY ISHGA TUSHIRISH ====================
if __name__ == '__main__':
    import signal
    
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    
    port = int(os.environ.get('PORT', 10000))
    
    def run_flask():
        from waitress import serve
        serve(app, host='0.0.0.0', port=port, threads=1)
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print(f"🌐 Flask server: http://0.0.0.0:{port}")
    print("🤖 Telegram bot polling ishga tushmoqda...")
    
    try:
        telegram_app.run_polling(
            drop_pending_updates=True,
            timeout=30,
            close_loop=False,
            stop_signals=[],
            bootstrap_retries=-1,
            allowed_updates=['message', 'callback_query']
        )
    except KeyboardInterrupt:
        print("\n🛑 Bot to'xtatildi")
    except Exception as e:
        print(f"❌ Xato: {e}")
        import time
        time.sleep(5)
        telegram_app.run_polling(
            drop_pending_updates=True,
            timeout=30,
            close_loop=False,
            stop_signals=[]
        )
