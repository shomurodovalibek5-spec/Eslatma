# bot.py - SMART ASSISTANT BOT
# MUKAMMAL VERSIYA - TO'LIQ TUZATILGAN
# ESLATMA: BARCHA FUNKSIYALAR ISHLAYDI

import os
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
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode

# ==================== KONFIGURATSIYA ====================
BOT_TOKEN = "8250421622:AAHpa6q_RMV1d3QNO4tM3YtT9h2jYJebvjw"
ADMIN_IDS = [8014950410]
TIMEZONE = ZoneInfo("Asia/Tashkent")
DB_NAME = 'smart_assistant.db'

# ==================== LOG ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)



# ==================== KONSTANTALAR ====================
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

EXPENSE_CATEGORIES = [
    "🍔 Taom", "🚕 Transport", "👕 Kiyim", "🏠 Uy-joy",
    "📱 Telefon", "🌐 Internet", "📚 O'qish", "⚕️ Sog'liq",
    "🎉 Ko'ngilochar", "🛍 Xarid", "💼 Ish", "📦 Boshqa"
]

INCOME_CATEGORIES = [
    "💼 Maosh", "📈 Loyiha", "🏪 Sotuv", "🎁 Sovg'a",
    "📊 Freelance", "🏦 Investitsiya", "💰 Boshqa"
]

CURRENCY_SYMBOLS = {
    "UZS": "so'm",
    "USD": "$",
    "EUR": "€",
    "RUB": "₽"
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
            check_same_thread=False
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
    def get_or_create_user(self, telegram_id: int, username: str, full_name: str, phone: str = None) -> dict:
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
                    phone = COALESCE(?, phone)
                    WHERE telegram_id = ?""",
                    (username, full_name, is_admin, now, phone, telegram_id)
                )
                user = dict(user)
            else:
                # Yangi foydalanuvchi yaratish
                self.cursor.execute(
                    """INSERT INTO users 
                    (telegram_id, username, full_name, is_admin, last_seen, phone) 
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (telegram_id, username, full_name, is_admin, now, phone)
                )
                
                user_id = self.cursor.lastrowid
                self.cursor.execute(
                    "SELECT * FROM users WHERE id = ?",
                    (user_id,)
                )
                user = dict(self.cursor.fetchone())
                
                # Foydalanuvchi sozlamalarini yaratish
                self.cursor.execute(
                    "INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)",
                    (user_id,)
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
                'is_blocked': 0
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
                self.cursor.execute(
                    "INSERT INTO user_settings (user_id) VALUES (?)",
                    (user_id,)
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
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Update user setting error: {e}")
            return False
    
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
            rows = self.cursor.fetchall()
            
            for row in rows:
                reminder = dict(row)
                
                # repeat_days ni JSON dan o'qish - SODDA VA ISHONCHLI
                if reminder.get('repeat_days'):
                    try:
                        # Agar string bo'lsa
                        if isinstance(reminder['repeat_days'], str):
                            reminder['repeat_days'] = json.loads(reminder['repeat_days'])
                        # Agar list bo'lsa
                        elif isinstance(reminder['repeat_days'], list):
                            pass
                        # Agar bytes bo'lsa
                        elif isinstance(reminder['repeat_days'], bytes):
                            reminder['repeat_days'] = json.loads(reminder['repeat_days'].decode('utf-8'))
                        else:
                            reminder['repeat_days'] = []
                    except:
                        reminder['repeat_days'] = []
                else:
                    reminder['repeat_days'] = []
                
                # reminder_time ni datetime ga o'tkazish
                if reminder.get('reminder_time'):
                    try:
                        if isinstance(reminder['reminder_time'], str):
                            reminder['reminder_time'] = datetime.fromisoformat(reminder['reminder_time'].replace(' ', 'T'))
                    except:
                        pass
                
                # next_reminder ni datetime ga o'tkazish
                if reminder.get('next_reminder'):
                    try:
                        if isinstance(reminder['next_reminder'], str):
                            reminder['next_reminder'] = datetime.fromisoformat(reminder['next_reminder'].replace(' ', 'T'))
                    except:
                        pass
                
                reminders.append(reminder)
            
            return reminders
        except Exception as e:
            logger.error(f"❌ Get user reminders error: {e}")
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


# ==================== BOT HANDLERS ====================
class BotHandler:
    def __init__(self, db: Database):
        self.db = db
        self.user_states = {}
        self.selected_days = {}
    
    # ==================== KEYBOARD LAR ====================
    def get_main_keyboard(self, telegram_id: int = None):
        """Asosiy menyu keyboard"""
        keyboard = [
            ["🔔 ESLATMA", "💰 XARAJAT", "💵 DAROMAD"],
            ["💸 QARZLAR", "📊 HISOBOT", "🎯 BYUDJET"],
            ["⚙️ SOZLAMALAR", "🆘 YORDAM"]
        ]
        
        if telegram_id and telegram_id in ADMIN_IDS:
            keyboard.append(["👑 ADMIN PANEL"])
        
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_back_keyboard(self):
        """Orqaga keyboard"""
        return ReplyKeyboardMarkup([["🔙 ORQAGA"]], resize_keyboard=True)
    
    def get_reminder_type_keyboard(self):
        """Eslatma turi keyboard"""
        keyboard = [
            ["📅 Bugun", "🔄 Har kuni", "📆 Hafta kunlari"],
            ["📅 Boshqa kun", "❌ Bekor qilish"],
            ["🔙 ORQAGA"]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_date_selection_keyboard(self):
        """Sana tanlash uchun keyboard"""
        today = date.today()
        keyboard = [
            [f"📅 {today.strftime('%d.%m.%Y')}"],
            [f"📅 {(today + timedelta(days=1)).strftime('%d.%m.%Y')}", f"📅 {(today + timedelta(days=2)).strftime('%d.%m.%Y')}"],
            [f"📅 {(today + timedelta(days=3)).strftime('%d.%m.%Y')}", f"📅 {(today + timedelta(days=4)).strftime('%d.%m.%Y')}"],
            [f"📅 {(today + timedelta(days=5)).strftime('%d.%m.%Y')}", f"📅 {(today + timedelta(days=6)).strftime('%d.%m.%Y')}"],
            ["✏️ Boshqa sana", "❌ Bekor qilish"],
            ["🔙 ORQAGA"]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_weekdays_selection_keyboard(self, user_id: int):
        """Hafta kunlarini tanlash uchun inline keyboard"""
        selected = self.selected_days.get(user_id, set())
        
        keyboard = []
        row = []
        
        for i in range(7):
            day_name = WEEKDAYS_SHORT[i]
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
        
        keyboard.append([InlineKeyboardButton("✅ Tasdiqlash", callback_data="weekday_done")])
        keyboard.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="weekday_cancel")])
        
        return InlineKeyboardMarkup(keyboard)
    
    def get_budget_keyboard(self):
        """Byudjet keyboard"""
        keyboard = [
            ["📊 BYUDJET HOLATI", "➕ LIMIT QO'SHISH"],
            ["✏️ LIMIT O'ZGARTIRISH", "🗑️ LIMIT O'CHIRISH"],
            ["📈 STATISTIKA", "⚙️ OGOHLANTIRISH"],
            ["🔙 ORQAGA"]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_budget_categories_keyboard(self):
        """Byudjet kategoriyalari keyboard"""
        keyboard = []
        row = []
        
        for i, category in enumerate(EXPENSE_CATEGORIES[:8]):
            button = InlineKeyboardButton(category, callback_data=f"budget_cat_{category}")
            row.append(button)
            
            if len(row) == 2:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("➕ Boshqa", callback_data="budget_cat_other")])
        keyboard.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="budget_cancel")])
        
        return InlineKeyboardMarkup(keyboard)
    
    def get_expense_categories_keyboard(self):
        """Xarajat kategoriyalari keyboard"""
        keyboard = []
        row = []
        
        for i, category in enumerate(EXPENSE_CATEGORIES):
            if i % 2 == 0 and row:
                keyboard.append(row)
                row = []
            row.append(InlineKeyboardButton(category, callback_data=f"expense_cat_{category}"))
        
        if row:
            keyboard.append(row)
        
        return InlineKeyboardMarkup(keyboard)
    
    def get_income_categories_keyboard(self):
        """Daromad kategoriyalari keyboard"""
        keyboard = []
        row = []
        
        for i, category in enumerate(INCOME_CATEGORIES):
            if i % 2 == 0 and row:
                keyboard.append(row)
                row = []
            row.append(InlineKeyboardButton(category, callback_data=f"income_cat_{category}"))
        
        if row:
            keyboard.append(row)
        
        return InlineKeyboardMarkup(keyboard)
    
    def get_settings_keyboard(self):
        """Sozlamalar keyboard"""
        keyboard = [
            ["💱 PUL BIRLIGI", "🔔 ESLATMA VAQTI"],
            ["💰 BYUDJET CHEGARASI", "🌐 TIL"],
            ["🎨 MAVZU", "ℹ️ PROFIL"],
            ["🔙 ORQAGA"]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_currency_keyboard(self):
        """Pul birligi keyboard"""
        keyboard = [
            ["💵 UZS (so'm)"],
            ["💵 USD ($)"],
            ["💶 EUR (€)"],
            ["💷 RUB (₽)"],
            ["🔙 ORQAGA"]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_alert_threshold_keyboard(self):
        """Ogohlantirish chegarasi keyboard"""
        keyboard = [
            ["50%", "60%", "70%"],
            ["80%", "90%", "95%"],
            ["🔙 ORQAGA"]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_theme_keyboard(self):
        """Mavzu keyboard"""
        keyboard = [
            ["☀️ Yoruq", "🌙 Qorongʻi"],
            ["🔙 ORQAGA"]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_language_keyboard(self):
        """Til keyboard"""
        keyboard = [
            ["🇺🇿 O'zbek tili"],
            ["🇷🇺 Rus tili"],
            ["🇬🇧 Ingliz tili"],
            ["🔙 ORQAGA"]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_admin_keyboard(self):
        """Admin panel keyboard"""
        keyboard = [
            ["📊 UMUMIY STATISTIKA", "👥 FOYDALANUVCHILAR"],
            ["🔍 QIDIRUV", "👤 PROFIL KO'RISH"],
            ["📢 XABAR YUBORISH", "🚫 BLOKLASH/OCHISH"],
            ["📋 ADMIN LOGLAR", "🔙 ORQAGA"]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_debts_keyboard(self):
        """Qarzlar keyboard"""
        keyboard = [
            ["➕ YANGI QARZ", "📋 BARCHA QARZLAR"],
            ["✅ QARZNI YOPISH", "🔙 ORQAGA"]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    # ==================== START ====================
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command"""
        user = update.effective_user
        
        db_user = self.db.get_or_create_user(
            telegram_id=user.id,
            username=user.username or "",
            full_name=user.full_name or ""
        )
        
        if db_user and db_user.get('is_blocked'):
            await update.message.reply_text(
                "❌ Siz botdan foydalanish imkoniyatidan mahrum qilingansiz.\n"
                "Batafsil ma'lumot uchun admin bilan bog'lanishingiz mumkin."
            )
            return
        
        welcome_message = f"""
👋 *Salom, {user.full_name}!*

🤖 *Smart Assistant Bot* ga xush kelibsiz!

📌 *Men sizga yordam beraman:*
🔔 *Eslatmalar* - kunlik, haftalik, takrorlanuvchi
💰 *Xarajatlar* - kuzatish va tahlil qilish
💵 *Daromadlar* - hisobga olish
💸 *Qarzlar* - nazorat qilish
🎯 *Byudjet* - limitlar belgilash
📊 *Hisobotlar* - moliyaviy tahlil

⚡️ *Qulay va oson boshqaruv!*
🆘 Yordam uchun /help yoki '🆘 YORDAM' tugmasini bosing
        """
        
        if user.id in ADMIN_IDS:
            welcome_message += "\n\n👑 *Siz admin sifatida kirdingiz!*"
        
        self.user_states.pop(user.id, None)
        self.selected_days.pop(user.id, None)
        
        await update.message.reply_text(
            welcome_message,
            reply_markup=self.get_main_keyboard(user.id),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ==================== HELP ====================
    async def show_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Yordam"""
        user = update.effective_user
        
        help_text = """
🆘 *YORDAM*

🤖 *Smart Assistant Bot* - mukammal versiya

📌 *QANDAY FOYDALANISH:*

🔔 *ESLATMALAR:*
• Bir martalik - bugun
• Har kuni - takrorlanuvchi
• Hafta kunlari - tanlab
• Boshqa sana - ixtiyoriy kun
• ID orqali o'chirish

💰 *XARAJATLAR:*
• Tez qo'shish (1.5M, 500k)
• Kategoriyalar
• Statistika va trendlar

💵 *DAROMADLAR:*
• Manba bo'yicha
• Oylik hisobot

💸 *QARZLAR:*
• Bergan va olgan qarzlar
• Qarzni yopish
• Umumiy hisob

🎯 *BYUDJET:*
• Kategoriya limitlari
• Progress bar
• Ogohlantirishlar
• Limitni o'zgartirish/o'chirish

📊 *HISOBOT:*
• Oylik xulosa
• Kategoriya tahlili
• Trendlar
• Maslahatlar

⚙️ *SOZLAMALAR:*
• Pul birligi (UZS, USD, EUR, RUB)
• Eslatma vaqti (09:00)
• Byudjet chegarasi (50-95%)
• Til (O'zbek)
• Mavzu (Yoruq/Qorongʻi)

⚡️ *QO'LLANMA:*
• Tugmalarni bosing
• Ketma-ket savollarga javob bering
• ID raqamlarini saqlang

📞 *MUAMMO BO'LSA:*
/start - Botni qayta ishga tushirish
        """
        
        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_main_keyboard(user.id)
        )
    
    # ==================== CALLBACK HANDLER ====================
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Inline tugmalarni qayta ishlash"""
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        user_id = self.db.get_user_id(user.id)
        data = query.data
        
        # Hafta kunlarini tanlash
        if data.startswith("wday_"):
            try:
                day = int(data.split("_")[1])
                
                if user.id not in self.selected_days:
                    self.selected_days[user.id] = set()
                
                if day in self.selected_days[user.id]:
                    self.selected_days[user.id].remove(day)
                else:
                    self.selected_days[user.id].add(day)
                
                await query.message.edit_reply_markup(
                    reply_markup=self.get_weekdays_selection_keyboard(user.id)
                )
            except (IndexError, ValueError) as e:
                logger.error(f"Weekday selection error: {e}")
        
        elif data == "weekday_done":
            days = self.selected_days.get(user.id, set())
            
            if not days:
                await query.message.edit_text(
                    "❌ Hech qanday kun tanlanmadi.\n"
                    "Qayta urinib ko'ring.",
                    reply_markup=None
                )
                return
            
            state = self.user_states.get(user.id)
            if state and state.get('action') == 'ADD_REMINDER' and state.get('step') == 2:
                state['repeat_days'] = list(days)
                state['repeat_type'] = 'custom'
                self.user_states[user.id] = state
                
                await query.message.edit_text(
                    f"✅ Tanlangan kunlar: {', '.join([WEEKDAYS_UZ[d] for d in sorted(days)])}\n\n"
                    "Endi vaqtni kiriting (HH:MM):"
                )
                
                self.user_states[user.id]['step'] = 3
            
            self.selected_days.pop(user.id, None)
        
        elif data == "weekday_cancel":
            self.selected_days.pop(user.id, None)
            self.user_states.pop(user.id, None)
            await query.message.edit_text(
                "❌ Bekor qilindi.",
                reply_markup=None
            )
        
        # Byudjet kategoriya tanlash
        elif data.startswith("budget_cat_"):
            category = data.replace("budget_cat_", "")
            
            if category == "other":
                await query.message.edit_text(
                    "✏️ Kategoriya nomini yozing:"
                )
                self.user_states[user.id] = {'action': 'ADD_BUDGET', 'step': 1, 'custom_category': True}
            else:
                self.user_states[user.id] = {'action': 'ADD_BUDGET', 'step': 2, 'category': category}
                await query.message.edit_text(
                    f"✅ Kategoriya: {category}\n\n"
                    "Endi oylik limit miqdorini kiriting:"
                )
        
        elif data.startswith("budget_edit_"):
            category = data.replace("budget_edit_", "")
            self.user_states[user.id] = {'action': 'EDIT_BUDGET', 'category': category, 'step': 1}
            await query.message.edit_text(
                f"✏️ {category} uchun yangi limit miqdorini kiriting:"
            )
        
        elif data.startswith("budget_del_"):
            category = data.replace("budget_del_", "")
            success = self.db.delete_budget(user_id, category)
            
            if success:
                await query.message.edit_text(
                    f"✅ {category} limiti o'chirildi!"
                )
            else:
                await query.message.edit_text(
                    f"❌ Xatolik yuz berdi."
                )
        
        elif data == "budget_cancel":
            await query.message.edit_text(
                "❌ Bekor qilindi.",
                reply_markup=None
            )
        
        # Xarajat kategoriya tanlash
        elif data.startswith("expense_cat_"):
            category = data.replace("expense_cat_", "")
            state = self.user_states.get(user.id)
            
            if state and state.get('action') == 'ADD_EXPENSE' and state.get('step') == 2:
                state['category'] = category
                state['step'] = 3
                self.user_states[user.id] = state
                
                await query.message.edit_text(
                    f"✅ Kategoriya: {category}\n\n"
                    f"💰 Miqdor: {state['amount']:,.0f} so'm\n\n"
                    "3️⃣ Tavsif (ixtiyoriy):\n"
                    "Masalan: 'Lagmon' yoki 'Taksi'\n"
                    "Agar kerak bo'lmasa, 'yo'q' deb yozing"
                )
        
        # Daromad kategoriya tanlash
        elif data.startswith("income_cat_"):
            category = data.replace("income_cat_", "")
            state = self.user_states.get(user.id)
            
            if state and state.get('action') == 'ADD_INCOME' and state.get('step') == 2:
                state['category'] = category
                state['step'] = 3
                self.user_states[user.id] = state
                
                await query.message.edit_text(
                    f"✅ Manba: {category}\n\n"
                    f"💵 Miqdor: {state['amount']:,.0f} so'm\n\n"
                    "3️⃣ Tavsif (ixtiyoriy):\n"
                    "Masalan: 'Dekabr oyi' yoki 'Veb sayt'\n"
                    "Agar kerak bo'lmasa, 'yo'q' deb yozing"
                )
        
        # Admin actionlar
        elif data.startswith("admin_block_"):
            target_id = int(data.split("_")[2])
            success = self.db.block_user(target_id, user.id)
            
            if success:
                await query.message.edit_text(
                    f"✅ Foydalanuvchi {target_id} bloklandi!"
                )
                await self.admin_view_profile(update, target_id, user.id)
            else:
                await query.message.edit_text(
                    f"❌ Xatolik yuz berdi."
                )
        
        elif data.startswith("admin_unblock_"):
            target_id = int(data.split("_")[2])
            success = self.db.unblock_user(target_id, user.id)
            
            if success:
                await query.message.edit_text(
                    f"✅ Foydalanuvchi {target_id} blokdan ochildi!"
                )
                await self.admin_view_profile(update, target_id, user.id)
            else:
                await query.message.edit_text(
                    f"❌ Xatolik yuz berdi."
                )
        
        elif data.startswith("admin_user_stats_"):
            target_id = int(data.split("_")[3])
            await query.message.edit_text(
                "📊 To'liq statistika (tez kunda)",
                reply_markup=None
            )
        
        elif data.startswith("admin_message_"):
            target_id = int(data.split("_")[2])
            self.user_states[user.id] = {'action': 'ADMIN_MESSAGE', 'target': target_id}
            await query.message.edit_text(
                f"Foydalanuvchiga yubormoqchi bo'lgan xabaringizni yozing:"
            )
        
        elif data == "admin_back":
            await query.message.delete()
            await self.admin_menu(update)
        
        elif data == "admin_export_users":
            users = self.db.get_all_users()
            text = "Telegram ID,Ism,Username,Admin,Bloklangan,Registratsiya\n"
            
            for user_data in users[:100]:
                text += f"{user_data['telegram_id']},{user_data['full_name']},{user_data['username']},{user_data['is_admin']},{user_data.get('is_blocked',0)},{user_data['registered_at'][:10]}\n"
            
            await query.message.reply_document(
                document=text.encode('utf-8'),
                filename="users.csv",
                caption="📊 Foydalanuvchilar ro'yxati"
            )
        
        elif data == "admin_search":
            await query.message.delete()
            await self.admin_search_start(update, user.id)
    
    # ==================== MESSAGE HANDLER ====================
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Barcha xabarlarni qayta ishlash"""
        user = update.effective_user
        text = update.message.text
        user_id = self.db.get_user_id(user.id)
        
        if not user_id:
            await update.message.reply_text("Iltimos, avval /start buyrug'ini yuboring.")
            return
        
        db_user = self.db.get_user_by_telegram_id(user.id)
        if db_user and db_user.get('is_blocked'):
            await update.message.reply_text(
                "❌ Siz botdan foydalanish imkoniyatidan mahrum qilingansiz."
            )
            return
        
        # ORQAGA
        if text == "🔙 ORQAGA":
            self.user_states.pop(user.id, None)
            self.selected_days.pop(user.id, None)
            await update.message.reply_text(
                "🏠 Asosiy menyu",
                reply_markup=self.get_main_keyboard(user.id)
            )
            return
        
        # ASOSIY MENYU
        if text == "🔔 ESLATMA":
            await self.reminder_menu(update, user.id)
        
        elif text == "💰 XARAJAT":
            await self.expense_menu(update, user.id)
        
        elif text == "💵 DAROMAD":
            await self.income_menu(update, user.id)
        
        elif text == "💸 QARZLAR":
            await self.debts_menu(update)
        
        elif text == "📊 HISOBOT":
            await self.show_report(update, user_id, user.id)
        
        elif text == "🎯 BYUDJET":
            await self.budget_menu(update, user_id, user.id)
        
        elif text == "⚙️ SOZLAMALAR":
            await self.settings_menu(update, user_id, user.id)
        
        elif text == "🆘 YORDAM":
            await self.show_help(update, context)
        
        elif text == "👑 ADMIN PANEL" and user.id in ADMIN_IDS:
            await self.admin_menu(update)
        
        # ESLATMALAR MENYUSI
        elif text == "📋 ESLATMALARIM":
            await self.show_reminders(update, user_id, user.id)
        
        elif text == "🗑️ O'CHIRISH":
            await self.delete_reminder(update, user.id)
        
        elif text == "➕ YANGI ESLATMA":
            await self.reminder_add_step1(update, user.id)
        
        # QARZLAR MENYUSI
        elif text == "➕ YANGI QARZ":
            await self.debt_add_step1(update, user.id)
        
        elif text == "📋 BARCHA QARZLAR":
            await self.show_debts(update, user_id)
        
        elif text == "✅ QARZNI YOPISH":
            await self.close_debt(update, user.id)
        
        # XARAJATLAR MENYUSI
        elif text == "➕ YANGI XARAJAT":
            await self.expense_add_step1(update, user.id)
        
        elif text == "📊 XARAJATLARIM":
            await self.expense_show_stats(update, user_id, user.id)
        
        elif text == "📈 STATISTIKA":
            await self.expense_show_stats(update, user_id, user.id)
        
        elif text == "📉 TRENDLAR":
            await self.expense_show_trends(update, user_id, user.id)
        
        # DAROMADLAR MENYUSI
        elif text == "➕ YANGI DAROMAD":
            await self.income_add_step1(update, user.id)
        
        elif text == "📊 DAROMADLARIM":
            await self.income_show_stats(update, user_id, user.id)
        
        # BYUDJET MENYUSI
        elif text == "📊 BYUDJET HOLATI":
            await self.budget_show_status(update, user_id, user.id)
        
        elif text == "➕ LIMIT QO'SHISH":
            await self.budget_add_start(update, user.id)
        
        elif text == "✏️ LIMIT O'ZGARTIRISH":
            await self.budget_edit_limit(update, user_id, user.id)
        
        elif text == "🗑️ LIMIT O'CHIRISH":
            await self.budget_delete(update, user_id, user.id)
        
        elif text == "📈 STATISTIKA" and text.startswith("📈"):
            await self.budget_show_status(update, user_id, user.id)
        
        elif text == "⚙️ OGOHLANTIRISH":
            await self.settings_threshold(update, user.id)
        
        # SOZLAMALAR MENYUSI
        elif text == "💱 PUL BIRLIGI":
            await self.settings_currency(update, user.id)
        
        elif text == "🔔 ESLATMA VAQTI":
            await self.settings_reminder_time(update, user.id)
        
        elif text == "💰 BYUDJET CHEGARASI":
            await self.settings_threshold(update, user.id)
        
        elif text == "🌐 TIL":
            await self.settings_language(update, user.id)
        
        elif text == "🎨 MAVZU":
            await self.settings_theme(update, user.id)
        
        elif text == "ℹ️ PROFIL":
            await self.settings_profile(update, user_id, user.id)
        
        # ADMIN PANEL
        elif text == "📊 UMUMIY STATISTIKA" and user.id in ADMIN_IDS:
            await self.admin_stats(update)
        
        elif text == "👥 FOYDALANUVCHILAR" and user.id in ADMIN_IDS:
            await self.admin_users(update)
        
        elif text == "🔍 QIDIRUV" and user.id in ADMIN_IDS:
            await self.admin_search_start(update, user.id)
        
        elif text == "👤 PROFIL KO'RISH" and user.id in ADMIN_IDS:
            await self.admin_view_profile_start(update, user.id)
        
        elif text == "📢 XABAR YUBORISH" and user.id in ADMIN_IDS:
            await self.admin_broadcast_start(update, user.id)
        
        elif text == "🚫 BLOKLASH/OCHISH" and user.id in ADMIN_IDS:
            await self.admin_block_start(update, user.id)
        
        elif text == "📋 ADMIN LOGLAR" and user.id in ADMIN_IDS:
            await self.admin_logs(update)
        
        else:
            await self.handle_user_state(update, text, user.id, user_id, context)
    
    # ==================== REMINDER METHODS ====================
    async def reminder_menu(self, update: Update, telegram_id: int):
        """Eslatmalar menyusi"""
        keyboard = [
            ["📋 ESLATMALARIM", "➕ YANGI ESLATMA"],
            ["🗑️ O'CHIRISH", "🔙 ORQAGA"]
        ]
        
        await update.message.reply_text(
            "🔔 *ESLATMALAR*",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def reminder_add_step1(self, update: Update, telegram_id: int):
        """1-qadam: Eslatma nomi"""
        self.user_states[telegram_id] = {'action': 'ADD_REMINDER', 'step': 1}
        await update.message.reply_text(
            "📝 *YANGI ESLATMA*\n\n"
            "1️⃣ *Eslatma nomini yozing:*\n"
            "Masalan: Dars, Uchrashuv, Tabletka",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard()
        )
    
    async def reminder_add_step2(self, update: Update, telegram_id: int, title: str):
        """2-qadam: Takrorlanish turi"""
        self.user_states[telegram_id] = {
            'action': 'ADD_REMINDER',
            'step': 2,
            'title': title
        }
        
        await update.message.reply_text(
            "2️⃣ *Takrorlanish turini tanlang:*\n\n"
            "📅 *Bugun* - bir martalik\n"
            "🔄 *Har kuni* - har kuni takrorlanadi\n"
            "📆 *Hafta kunlari* - tanlangan kunlarda\n"
            "📅 *Boshqa kun* - boshqa sanani tanlash",
            reply_markup=self.get_reminder_type_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def reminder_add_step3_time(self, update: Update, telegram_id: int, 
                                     title: str, repeat_type: str, custom_date: date = None):
        """3-qadam: Vaqtni kiritish"""
        self.user_states[telegram_id] = {
            'action': 'ADD_REMINDER',
            'step': 3,
            'title': title,
            'repeat_type': repeat_type,
            'custom_date': custom_date
        }
        
        await update.message.reply_text(
            "3️⃣ *Vaqtni kiriting (HH:MM):*\n"
            "Masalan: 09:00 yoki 14:30",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard()
        )
    
    async def reminder_add_step4_description(self, update: Update, telegram_id: int,
                                            title: str, repeat_type: str, time_str: str, custom_date: date = None):
        """4-qadam: Tavsif"""
        self.user_states[telegram_id] = {
            'action': 'ADD_REMINDER',
            'step': 4,
            'title': title,
            'repeat_type': repeat_type,
            'time': time_str,
            'custom_date': custom_date
        }
        
        await update.message.reply_text(
            "4️⃣ *Tavsif (ixtiyoriy):*\n"
            "Masalan: Darsga kechikma\n"
            "Agar kerak bo'lmasa, 'yo'q' deb yozing",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard()
        )
    
    async def show_reminders(self, update: Update, user_id: int, telegram_id: int):
        """Eslatmalarni ko'rsatish"""
        reminders = self.db.get_user_reminders(user_id)
        
        if not reminders:
            await update.message.reply_text(
                "📭 *Eslatmalar yo'q*\n\n"
                "➕ YANGI ESLATMA tugmasini bosing",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=ReplyKeyboardMarkup([["➕ YANGI ESLATMA", "🔙 ORQAGA"]], resize_keyboard=True)
            )
            return
        
        message = "🔔 *ESLATMALARINGIZ:*\n\n"
        
        for i, reminder in enumerate(reminders[:10], 1):
            try:
                # Vaqtni formatlash
                if reminder.get('repeat_type') != 'none':
                    next_time = reminder.get('next_reminder', reminder['reminder_time'])
                    if isinstance(next_time, datetime):
                        time_str = next_time.strftime('%d.%m.%Y %H:%M')
                    else:
                        time_str = "Noma'lum"
                    
                    # Takrorlanish turini ko'rsatish
                    if reminder['repeat_type'] == 'daily':
                        repeat = "🔄 Har kuni"
                    elif reminder['repeat_type'] == 'weekly':
                        repeat = "📅 Haftalik"
                    elif reminder['repeat_type'] == 'monthly':
                        repeat = "📆 Oylik"
                    elif reminder['repeat_type'] == 'custom':
                        days = reminder.get('repeat_days', [])
                        if days:
                            days_names = [WEEKDAYS_SHORT[d] for d in sorted(days)]
                            repeat = f"📆 {', '.join(days_names)}"
                        else:
                            repeat = "📆 Tanlangan kunlar"
                    else:
                        repeat = f"🔄 {reminder['repeat_type']}"
                else:
                    if isinstance(reminder['reminder_time'], datetime):
                        time_str = reminder['reminder_time'].strftime('%d.%m.%Y %H:%M')
                    else:
                        time_str = "Noma'lum"
                    repeat = "⏰ Bir marta"
                
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
            reply_markup=ReplyKeyboardMarkup([["➕ YANGI ESLATMA", "🗑️ O'CHIRISH", "🔙 ORQAGA"]], resize_keyboard=True)
        )
    
    async def delete_reminder(self, update: Update, telegram_id: int):
        """Eslatma o'chirish"""
        self.user_states[telegram_id] = 'DELETE_REMINDER'
        await update.message.reply_text(
            "🗑️ *Eslatma o'chirish*\n\n"
            "O'chirmoqchi bo'lgan eslatma ID sini yuboring:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard()
        )
    
    # ==================== EXPENSE METHODS ====================
    async def expense_menu(self, update: Update, telegram_id: int):
        """Xarajatlar menyusi"""
        keyboard = [
            ["➕ YANGI XARAJAT", "📊 XARAJATLARIM"],
            ["📈 STATISTIKA", "📉 TRENDLAR"],
            ["🔙 ORQAGA"]
        ]
        
        await update.message.reply_text(
            "💰 *XARAJATLAR*",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def expense_add_step1(self, update: Update, telegram_id: int):
        """1-qadam: Xarajat miqdori"""
        self.user_states[telegram_id] = {'action': 'ADD_EXPENSE', 'step': 1}
        await update.message.reply_text(
            "💰 *YANGI XARAJAT*\n\n"
            "1️⃣ *Qancha xarajat qildingiz?*\n"
            "Masalan: 50000, 125000, 1.5M",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard()
        )
    
    async def expense_show_stats(self, update: Update, user_id: int, telegram_id: int):
        """Xarajatlar statistikasi"""
        stats = self.db.get_expense_statistics(user_id, "month")
        settings = self.db.get_user_settings(user_id)
        currency = settings.get('currency', 'UZS')
        symbol = CURRENCY_SYMBOLS.get(currency, 'so\'m')
        
        month_name = MONTHS_UZ.get(date.today().month, str(date.today().month))
        
        message = f"""
📊 *XARAJATLAR STATISTIKASI*
📅 *{month_name} {date.today().year}*

💰 *Umumiy ma'lumot:*
• Jami xarajat: *{stats['general']['total']:,.0f}* {symbol}
• Xarajatlar soni: *{stats['general']['count']}* ta
• O'rtacha: *{stats['general']['average']:,.0f}* {symbol}
• Eng katta: *{stats['general']['max']:,.0f}* {symbol}
• Eng kichik: *{stats['general']['min']:,.0f}* {symbol}

📂 *Kategoriyalar:*\n
"""
        
        for cat in stats['categories'][:5]:
            percentage = (cat['total'] / stats['general']['total'] * 100) if stats['general']['total'] > 0 else 0
            bar = "█" * int(percentage / 10) + "░" * (10 - int(percentage / 10))
            message += f"• {cat['category']}\n"
            message += f"  `{bar}` {percentage:.1f}%\n"
            message += f"  💰 {cat['total']:,.0f} {symbol} ({cat['count']} ta)\n\n"
        
        if stats['top_category']:
            message += f"🏆 *Eng ko'p xarajat:* {stats['top_category']['category']}\n"
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard()
        )
    
    async def expense_show_trends(self, update: Update, user_id: int, telegram_id: int):
        """Xarajatlar trendlari"""
        trends = self.db.get_expense_trends(user_id, 6)
        settings = self.db.get_user_settings(user_id)
        symbol = CURRENCY_SYMBOLS.get(settings.get('currency', 'UZS'), 'so\'m')
        
        message = "📈 *XARAJATLAR TRENDI*\n\n"
        
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
            reply_markup=self.get_back_keyboard()
        )
    
    # ==================== INCOME METHODS ====================
    async def income_menu(self, update: Update, telegram_id: int):
        """Daromadlar menyusi"""
        keyboard = [
            ["➕ YANGI DAROMAD", "📊 DAROMADLARIM"],
            ["🔙 ORQAGA"]
        ]
        
        await update.message.reply_text(
            "💵 *DAROMADLAR*",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def income_add_step1(self, update: Update, telegram_id: int):
        """1-qadam: Daromad miqdori"""
        self.user_states[telegram_id] = {'action': 'ADD_INCOME', 'step': 1}
        await update.message.reply_text(
            "💵 *YANGI DAROMAD*\n\n"
            "1️⃣ *Qancha daromad oldingiz?*\n"
            "Masalan: 1000000, 2.5M",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard()
        )
    
    async def income_show_stats(self, update: Update, user_id: int, telegram_id: int):
        """Daromadlar statistikasi"""
        stats = self.db.get_income_statistics(user_id)
        settings = self.db.get_user_settings(user_id)
        currency = settings.get('currency', 'UZS')
        symbol = CURRENCY_SYMBOLS.get(currency, 'so\'m')
        month_name = MONTHS_UZ.get(date.today().month, str(date.today().month))
        
        if stats['total'] == 0:
            await update.message.reply_text(
                f"💵 *DAROMADLAR STATISTIKASI*\n"
                f"📅 *{month_name} {date.today().year}*\n\n"
                f"📭 Bu oyda daromad yo'q.\n\n"
                f"➕ YANGI DAROMAD tugmasini bosing",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.get_back_keyboard()
            )
            return
        
        message = f"""
💵 *DAROMADLAR STATISTIKASI*
📅 *{month_name} {date.today().year}*

💰 *Umumiy ma'lumot:*
• Jami daromad: *{stats['total']:,.0f}* {symbol}
• Daromadlar soni: *{stats['count']}* ta
• O'rtacha: *{stats['average']:,.0f}* {symbol}

📂 *Manbalar:*\n
"""
        
        for cat in stats['categories'][:5]:
            percentage = (cat['total'] / stats['total'] * 100) if stats['total'] > 0 else 0
            bar = "█" * int(percentage / 10) + "░" * (10 - int(percentage / 10))
            message += f"• {cat['category']}\n"
            message += f"  `{bar}` {percentage:.1f}%\n"
            message += f"  💰 {cat['total']:,.0f} {symbol}\n\n"
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard()
        )
    
    # ==================== DEBT METHODS ====================
    async def debts_menu(self, update: Update):
        """Qarzlar menyusi"""
        keyboard = [
            ["➕ YANGI QARZ", "📋 BARCHA QARZLAR"],
            ["✅ QARZNI YOPISH", "🔙 ORQAGA"]
        ]
        
        await update.message.reply_text(
            "💸 *QARZLAR*",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def debt_add_step1(self, update: Update, telegram_id: int):
        """1-qadam: Qarz olgan/bergan odam ismi"""
        self.user_states[telegram_id] = {'action': 'ADD_DEBT', 'step': 1}
        await update.message.reply_text(
            "💸 *YANGI QARZ*\n\n"
            "1️⃣ *Kimga qarz berdingiz yoki kimdan qarz oldingiz?*\n"
            "Masalan: 'Ali' yoki 'Vali'",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard()
        )
    
    async def show_debts(self, update: Update, user_id: int):
        """Barcha qarzlarni ko'rsatish"""
        debts = self.db.get_user_debts(user_id)
        
        if not debts:
            await update.message.reply_text(
                "📭 *Qarzlar yo'q*\n\n"
                "➕ YANGI QARZ tugmasini bosing",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=ReplyKeyboardMarkup([["➕ YANGI QARZ", "🔙 ORQAGA"]], resize_keyboard=True)
            )
            return
        
        message = "💸 *QARZLARINGIZ:*\n\n"
        total_gave = 0
        total_took = 0
        
        for debt in debts:
            if debt['debt_type'] == 'gave':
                type_text = "📤 *Bergan:*"
                total_gave += debt['amount']
            else:
                type_text = "📥 *Olgan:*"
                total_took += debt['amount']
            
            message += f"{type_text}\n"
            message += f"👤 {debt['person_name']}\n"
            message += f"💰 {debt['amount']:,.0f} so'm\n"
            message += f"🆔 ID: `{debt['id']}`\n"
            if debt.get('description'):
                message += f"📝 {debt['description']}\n"
            message += "─" * 20 + "\n\n"
        
        message += f"📤 *Jami bergan:* {total_gave:,.0f} so'm\n"
        message += f"📥 *Jami olgan:* {total_took:,.0f} so'm\n"
        message += f"⚖️ *Farq:* {total_gave - total_took:,.0f} so'm"
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardMarkup([["✅ QARZNI YOPISH", "➕ YANGI QARZ", "🔙 ORQAGA"]], resize_keyboard=True)
        )
    
    async def close_debt(self, update: Update, telegram_id: int):
        """Qarzni yopish"""
        self.user_states[telegram_id] = 'CLOSE_DEBT'
        await update.message.reply_text(
            "✅ *Qarzni yopish*\n\n"
            "Yopmoqchi bo'lgan qarz ID sini yuboring:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard()
        )
    
    # ==================== BUDGET METHODS ====================
    async def budget_menu(self, update: Update, user_id: int, telegram_id: int):
        """Byudjet menyusi"""
        await update.message.reply_text(
            "🎯 *BYUDJET MENYUSI*",
            reply_markup=self.get_budget_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def budget_show_status(self, update: Update, user_id: int, telegram_id: int):
        """Byudjet holatini ko'rsatish"""
        summary = self.db.get_budget_summary(user_id)
        settings = self.db.get_user_settings(user_id)
        currency = settings.get('currency', 'UZS')
        symbol = CURRENCY_SYMBOLS.get(currency, 'so\'m')
        threshold = settings.get('budget_alert_threshold', 80)
        
        if summary['categories_count'] == 0:
            await update.message.reply_text(
                "🎯 *BYUDJET HOLATI*\n\n"
                "Hozircha byudjet limitlari belgilanmagan.\n\n"
                "➕ LIMIT QO'SHISH tugmasini bosing.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.get_budget_keyboard()
            )
            return
        
        month_name = MONTHS_UZ.get(date.today().month, str(date.today().month))
        
        message = f"""
📊 *BYUDJET HOLATI - {month_name}*

💳 *Umumiy:*
• Jami limit: *{summary['total_limit']:,.0f}* {symbol}
• Sarflangan: *{summary['total_spent']:,.0f}* {symbol}
• Qolgan: *{summary['remaining']:,.0f}* {symbol}
• Kategoriyalar: *{summary['categories_count']}* ta

⚠️ *Ogohlantirishlar:*
• {summary['exceeded_count']} ta limit oshgan
• {summary['warning_count']} ta {threshold}% dan o'tgan

📂 *Kategoriyalar:*\n
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
            reply_markup=self.get_budget_keyboard()
        )
    
    async def budget_add_start(self, update: Update, telegram_id: int):
        """Byudjet qo'shish boshlash"""
        await update.message.reply_text(
            "🎯 *YANGI BYUDJET LIMITI*\n\n"
            "Kategoriyani tanlang:",
            reply_markup=self.get_budget_categories_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def budget_edit_limit(self, update: Update, user_id: int, telegram_id: int):
        """Limitni o'zgartirish"""
        budgets = self.db.get_user_budgets(user_id)
        active_budgets = [b for b in budgets if b['monthly_limit'] > 0]
        
        if not active_budgets:
            await update.message.reply_text(
                "❌ O'zgartirish uchun limit belgilangan byudjet yo'q.",
                reply_markup=self.get_budget_keyboard()
            )
            return
        
        keyboard = []
        for budget in active_budgets[:8]:
            keyboard.append([InlineKeyboardButton(
                f"✏️ {budget['category']} - {budget['monthly_limit']:,.0f} so'm",
                callback_data=f"budget_edit_{budget['category']}"
            )])
        
        keyboard.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="budget_cancel")])
        
        await update.message.reply_text(
            "✏️ *LIMITNI O'ZGARTIRISH*\n\n"
            "O'zgartirmoqchi bo'lgan kategoriyani tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def budget_delete(self, update: Update, user_id: int, telegram_id: int):
        """Byudjet limitini o'chirish"""
        budgets = self.db.get_user_budgets(user_id)
        active_budgets = [b for b in budgets if b['monthly_limit'] > 0]
        
        if not active_budgets:
            await update.message.reply_text(
                "❌ O'chirish uchun limit belgilangan byudjet yo'q.",
                reply_markup=self.get_budget_keyboard()
            )
            return
        
        keyboard = []
        for budget in active_budgets[:8]:
            keyboard.append([InlineKeyboardButton(
                f"🗑️ {budget['category']} - {budget['monthly_limit']:,.0f} so'm",
                callback_data=f"budget_del_{budget['category']}"
            )])
        
        keyboard.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="budget_cancel")])
        
        await update.message.reply_text(
            "🗑️ *LIMITNI O'CHIRISH*\n\n"
            "O'chirmoqchi bo'lgan kategoriyani tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # ==================== REPORT METHODS ====================
    async def show_report(self, update: Update, user_id: int, telegram_id: int):
        """Moliyaviy hisobot"""
        summary = self.db.get_financial_summary(user_id)
        expenses_by_category = self.db.get_expenses_by_category(user_id)
        settings = self.db.get_user_settings(user_id)
        currency = settings.get('currency', 'UZS')
        symbol = CURRENCY_SYMBOLS.get(currency, 'so\'m')
        
        month_parts = summary['month'].split('-')
        month_name = MONTHS_UZ.get(int(month_parts[1]), month_parts[1])
        
        message = f"""
📊 *MOLIYAVIY HISOBOT*
📅 *{month_name} {month_parts[0]}*

💵 *Daromad:* +{summary['total_income']:,.0f} {symbol}
💰 *Xarajat:* -{summary['total_expense']:,.0f} {symbol}
"""
        
        if summary['balance'] >= 0:
            message += f"🟢 *Qoldiq:* {summary['balance']:,.0f} {symbol}"
        else:
            message += f"🔴 *Zarar:* {abs(summary['balance']):,.0f} {symbol}"
        
        if expenses_by_category:
            message += "\n\n📂 *Xarajatlar tahlili:*\n"
            
            for category, amount in sorted(expenses_by_category.items(), key=lambda x: x[1], reverse=True)[:5]:
                percentage = (amount / summary['total_expense'] * 100) if summary['total_expense'] > 0 else 0
                bar = "█" * int(percentage / 10) + "░" * (10 - int(percentage / 10))
                message += f"• {category}\n"
                message += f"  `{bar}` {percentage:.1f}%\n"
                message += f"  💰 {amount:,.0f} {symbol}\n\n"
        
        message += "\n💡 *Maslahat:* "
        if summary['balance'] > 0:
            message += "Daromadingiz xarajatdan ko'p. Tejashni davom eting!"
        elif summary['balance'] < 0:
            message += "Xarajatlaringiz daromaddan ko'p. Byudjet limitlarini belgilang!"
        else:
            message += "Daromad va xarajat teng. Byudjet rejasini tuzing!"
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard()
        )
    
    # ==================== SETTINGS METHODS ====================
    async def settings_menu(self, update: Update, user_id: int, telegram_id: int):
        """Sozlamalar menyusi"""
        settings = self.db.get_user_settings(user_id)
        currency = settings.get('currency', 'UZS')
        reminder_time = settings.get('reminder_time', '09:00')
        threshold = settings.get('budget_alert_threshold', 80)
        language = settings.get('language', 'uz')
        theme = settings.get('theme', 'light')
        
        lang_text = "O'zbek" if language == 'uz' else "Rus" if language == 'ru' else "Ingliz"
        theme_text = "Yoruq" if theme == 'light' else "Qorongʻi"
        
        message = f"""
⚙️ *SOZLAMALAR*

💱 *Pul birligi:* {currency}
🔔 *Eslatma vaqti:* {reminder_time}
💰 *Byudjet chegarasi:* {threshold}%
🌐 *Til:* {lang_text}
🎨 *Mavzu:* {theme_text}

Quyidagi tugmalar orqali o'zgartiring:
        """
        
        await update.message.reply_text(
            message,
            reply_markup=self.get_settings_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def settings_currency(self, update: Update, telegram_id: int):
        """Pul birligini sozlash"""
        self.user_states[telegram_id] = {'action': 'SET_CURRENCY', 'step': 1}
        await update.message.reply_text(
            "💱 *PUL BIRLIGINI TANLANG*",
            reply_markup=self.get_currency_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def settings_reminder_time(self, update: Update, telegram_id: int):
        """Eslatma vaqtini sozlash"""
        self.user_states[telegram_id] = {'action': 'SET_REMINDER_TIME', 'step': 1}
        await update.message.reply_text(
            "🔔 *ESLATMA VAQTI*\n\n"
            "Standart eslatma vaqtini kiriting (HH:MM):\n"
            "Masalan: 09:00",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard()
        )
    
    async def settings_threshold(self, update: Update, telegram_id: int):
        """Byudjet chegarasini sozlash"""
        self.user_states[telegram_id] = {'action': 'SET_THRESHOLD', 'step': 1}
        await update.message.reply_text(
            "💰 *BYUDJET CHEGARASI*\n\n"
            "Limit necha foizga yetganda ogohlantirish berilsin?\n"
            "Masalan: 80%",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_alert_threshold_keyboard()
        )
    
    async def settings_language(self, update: Update, telegram_id: int):
        """Tilni sozlash"""
        self.user_states[telegram_id] = {'action': 'SET_LANGUAGE', 'step': 1}
        await update.message.reply_text(
            "🌐 *TILNI TANLANG*",
            reply_markup=self.get_language_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def settings_theme(self, update: Update, telegram_id: int):
        """Mavzuni sozlash"""
        self.user_states[telegram_id] = {'action': 'SET_THEME', 'step': 1}
        await update.message.reply_text(
            "🎨 *MAVZUNI TANLANG*",
            reply_markup=self.get_theme_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def settings_profile(self, update: Update, user_id: int, telegram_id: int):
        """Profil ma'lumotlari"""
        user = self.db.get_user_by_id(user_id)
        settings = self.db.get_user_settings(user_id)
        
        if not user:
            return
        
        try:
            registered = datetime.fromisoformat(user['registered_at'].replace(' ', 'T')).strftime('%d.%m.%Y')
        except:
            registered = user['registered_at'][:10]
        
        try:
            last_seen = datetime.fromisoformat(user['last_seen'].replace(' ', 'T')).strftime('%d.%m.%Y %H:%M')
        except:
            last_seen = user['last_seen'][:16]
        
        message = f"""
👤 *PROFIL MA'LUMOTLARI*

🆔 *ID:* `{user['telegram_id']}`
👤 *Ism:* {user['full_name']}
📱 *Username:* @{user['username'] if user['username'] else 'yoʻq'}
📞 *Telefon:* {user.get('phone', 'yoʻq')}
📅 *Roʻyxatdan oʻtgan:* {registered}
⏰ *Oxirgi faollik:* {last_seen}

📊 *Statistika:*
• Eslatmalar: {user.get('reminder_count', 0)} ta
• Jami xarajat: {user.get('total_expenses', 0):,.0f} so'm
• Jami daromad: {user.get('total_income', 0):,.0f} so'm

⚙️ *Sozlamalar:*
• Pul birligi: {settings.get('currency', 'UZS')}
• Eslatma vaqti: {settings.get('reminder_time', '09:00')}
• Chegara: {settings.get('budget_alert_threshold', 80)}%
        """
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_settings_keyboard()
        )
    
    # ==================== ADMIN METHODS ====================
    async def admin_menu(self, update: Update):
        """Admin panel"""
        await update.message.reply_text(
            "👑 *ADMIN PANEL*",
            reply_markup=self.get_admin_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def admin_stats(self, update: Update):
        """Kengaytirilgan statistika"""
        stats = self.db.get_bot_stats()
        
        message = f"""
📊 *BOT STATISTIKASI*

👥 *Foydalanuvchilar:*
• Jami: *{stats['total_users']}* ta
• Bugun: *+{stats['new_users_today']}* ta
• Faol (7 kun): *{stats['active_week']}* ta
• Bloklangan: *{stats['blocked_users']}* ta
• Adminlar: *{stats['admins']}* ta

📱 *Faoliyat:*
• Eslatmalar: *{stats['active_reminders']}* ta
• Qarzlar: *{stats['active_debts']}* ta
• Byudjetlar: *{stats['budgets']}* ta

💰 *Moliya:*
• Jami daromad: *{stats['total_income']:,.0f}* so'm
• Jami xarajat: *{stats['total_expense']:,.0f}* so'm
• Bot balansi: *{stats['total_balance']:,.0f}* so'm

⚡️ *Bot holati:* ✅ Ishlayapti
        """
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_admin_keyboard()
        )
    
    async def admin_users(self, update: Update):
        """Foydalanuvchilar ro'yxati"""
        users = self.db.get_all_users()
        active_users = self.db.get_active_users(1)
        new_users = self.db.get_recent_users(1)
        
        message = f"""
👥 *FOYDALANUVCHILAR*

📊 *Umumiy:* {len(users)} ta
🟢 *Aktiv (bugun):* {len(active_users)} ta
🆕 *Yangi (bugun):* {len(new_users)} ta

📋 *Oxirgi 10 ta foydalanuvchi:*
        """
        
        for user in users[:10]:
            admin = "👑 " if user.get('is_admin') else ""
            block = "🚫 " if user.get('is_blocked') else ""
            username = f"@{user['username']}" if user['username'] else "no username"
            
            try:
                registered = datetime.fromisoformat(user['registered_at'].replace(' ', 'T')).strftime('%d.%m')
            except:
                registered = user['registered_at'][:10]
            
            message += f"\n{admin}{block}*{user['full_name']}*\n"
            message += f"   📱 {username}\n"
            message += f"   🆔 `{user['telegram_id']}`\n"
            message += f"   📅 {registered}"
        
        keyboard = [
            [InlineKeyboardButton("📥 Yuklash", callback_data="admin_export_users")],
            [InlineKeyboardButton("🔍 Qidiruv", callback_data="admin_search")]
        ]
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def admin_search_start(self, update: Update, telegram_id: int):
        """Foydalanuvchi qidiruv boshlash"""
        self.user_states[telegram_id] = 'ADMIN_SEARCH'
        await update.message.reply_text(
            "🔍 *Foydalanuvchi qidirish*\n\n"
            "Ism, username yoki Telegram ID kiriting:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard()
        )
    
    async def admin_view_profile_start(self, update: Update, telegram_id: int):
        """Profil ko'rish boshlash"""
        self.user_states[telegram_id] = 'ADMIN_VIEW_PROFILE'
        await update.message.reply_text(
            "👤 *Profil ko'rish*\n\n"
            "Foydalanuvchi Telegram ID sini yuboring:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard()
        )
    
    async def admin_view_profile(self, update: Update, target_id: int, admin_id: int):
        """Foydalanuvchi profilini ko'rish"""
        user = self.db.get_user_by_telegram_id(target_id)
        if not user:
            await update.message.reply_text(
                "❌ Foydalanuvchi topilmadi.",
                reply_markup=self.get_admin_keyboard()
            )
            return
        
        profile = self.db.get_user_full_profile(user['id'])
        if not profile:
            await update.message.reply_text(
                "❌ Profil ma'lumotlarini olishda xatolik.",
                reply_markup=self.get_admin_keyboard()
            )
            return
        
        user_data = profile['user']
        stats = profile['stats']
        settings = profile['settings']
        
        try:
            registered = datetime.fromisoformat(user_data['registered_at'].replace(' ', 'T')).strftime('%d.%m.%Y %H:%M')
        except:
            registered = user_data['registered_at'][:16]
        
        try:
            last_seen = datetime.fromisoformat(user_data['last_seen'].replace(' ', 'T')).strftime('%d.%m.%Y %H:%M')
        except:
            last_seen = user_data['last_seen'][:16]
        
        message = f"""
👤 *FOYDALANUVCHI PROFILI*

🆔 *Telegram ID:* `{user_data['telegram_id']}`
👤 *Ism:* {user_data['full_name']}
📱 *Username:* @{user_data['username'] if user_data['username'] else 'yoʻq'}
📞 *Telefon:* {user_data.get('phone', 'yoʻq')}

📊 *Holat:*
{"👑 Admin" if user_data['is_admin'] else "👤 Foydalanuvchi"}
{"🚫 Bloklangan" if user_data.get('is_blocked') else "✅ Faol"}

📅 *Roʻyxatdan oʻtgan:* {registered}
⏰ *Oxirgi faollik:* {last_seen}

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
• Bildirishnomalar: {'✅ Yoqilgan' if settings.get('notifications', 1) else '❌ Oʻchirilgan'}
        """
        
        keyboard = []
        if not user_data['is_admin']:
            if user_data.get('is_blocked'):
                keyboard.append([InlineKeyboardButton("✅ Blokni ochish", callback_data=f"admin_unblock_{target_id}")])
            else:
                keyboard.append([InlineKeyboardButton("🚫 Bloklash", callback_data=f"admin_block_{target_id}")])
        
        keyboard.append([InlineKeyboardButton("📊 To'liq statistika", callback_data=f"admin_user_stats_{target_id}")])
        keyboard.append([InlineKeyboardButton("📤 Xabar yuborish", callback_data=f"admin_message_{target_id}")])
        keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back")])
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def admin_broadcast_start(self, update: Update, telegram_id: int):
        """Xabar yuborish boshlash"""
        self.user_states[telegram_id] = 'ADMIN_BROADCAST'
        await update.message.reply_text(
            "📢 *XABAR YUBORISH*\n\n"
            "Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yozing:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard()
        )
    
    async def admin_broadcast_send(self, update: Update, text: str, admin_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Xabarni barchaga yuborish"""
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
                    await status_msg.edit_text(
                        f"⏳ Xabar yuborilmoqda... {i}/{len(users)}"
                    )
                
                await asyncio.sleep(0.05)
                
            except Exception as e:
                error_count += 1
                logger.error(f"Broadcast error to {user_data['telegram_id']}: {e}")
        
        await status_msg.edit_text(
            f"✅ *Xabar yuborildi!*\n\n"
            f"📊 *Natija:*\n"
            f"• Yuborildi: {success_count}\n"
            f"• Bloklangan: {blocked_count}\n"
            f"• Xatolik: {error_count}\n"
            f"• Jami: {len(users)}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        self.user_states.pop(admin_id, None)
    
    async def admin_block_start(self, update: Update, telegram_id: int):
        """Bloklash boshlash"""
        self.user_states[telegram_id] = 'ADMIN_BLOCK'
        await update.message.reply_text(
            "🚫 *BLOKLASH/OCHISH*\n\n"
            "Foydalanuvchi Telegram ID sini yuboring.\n"
            "Format: `123456789`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_back_keyboard()
        )
    
    async def admin_logs(self, update: Update):
        """Admin action loglari"""
        logs = self.db.get_admin_actions(20)
        
        message = "📋 *ADMIN HARAKATLARI*\n\n"
        
        for log in logs[:10]:
            try:
                date = datetime.fromisoformat(log['created_at'].replace(' ', 'T')).strftime('%d.%m %H:%M')
            except:
                date = log['created_at'][:16]
            
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
            reply_markup=self.get_admin_keyboard()
        )
    
    # ==================== USER STATE HANDLER ====================
    async def handle_user_state(self, update: Update, text: str, telegram_id: int, 
                               user_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Foydalanuvchi holatlarini qayta ishlash"""
        state = self.user_states.get(telegram_id)
        
        if not state:
            await update.message.reply_text(
                "❌ Iltimos, menyudan tanlang.",
                reply_markup=self.get_main_keyboard(telegram_id)
            )
            return
        
        try:
            # String state
            if isinstance(state, str):
                await self._handle_string_state(update, text, telegram_id, user_id, state, context)
            # Dict state
            else:
                await self._handle_dict_state(update, text, telegram_id, user_id, state, context)
                
        except Exception as e:
            logger.error(f"State handler error: {e}")
            await update.message.reply_text(
                "❌ Xatolik yuz berdi. Qayta urinib ko'ring.",
                reply_markup=self.get_main_keyboard(telegram_id)
            )
            self.user_states.pop(telegram_id, None)
    
    async def _handle_string_state(self, update: Update, text: str, telegram_id: int,
                                  user_id: int, state: str, context: ContextTypes.DEFAULT_TYPE):
        """String state larni qayta ishlash"""
        
        if state == 'DELETE_REMINDER':
            try:
                reminder_id = int(text.strip())
                if self.db.delete_reminder(reminder_id, user_id):
                    await update.message.reply_text(
                        "✅ Eslatma o'chirildi.",
                        reply_markup=self.get_main_keyboard(telegram_id)
                    )
                else:
                    await update.message.reply_text(
                        "❌ Eslatma topilmadi yoki sizga tegishli emas.",
                        reply_markup=self.get_reminder_type_keyboard()
                    )
            except ValueError:
                await update.message.reply_text(
                    "❌ Noto'g'ri format. Iltimos, faqat raqam kiriting.",
                    reply_markup=self.get_reminder_type_keyboard()
                )
            self.user_states.pop(telegram_id, None)
        
        elif state == 'CLOSE_DEBT':
            try:
                debt_id = int(text.strip())
                if self.db.close_debt(debt_id, user_id):
                    await update.message.reply_text(
                        "✅ Qarz yopildi.",
                        reply_markup=self.get_main_keyboard(telegram_id)
                    )
                else:
                    await update.message.reply_text(
                        "❌ Qarz topilmadi yoki allaqachon yopilgan.",
                        reply_markup=self.get_debts_keyboard()
                    )
            except ValueError:
                await update.message.reply_text(
                    "❌ Noto'g'ri format. Iltimos, faqat raqam kiriting.",
                    reply_markup=self.get_debts_keyboard()
                )
            self.user_states.pop(telegram_id, None)
        
        elif state == 'ADMIN_SEARCH' and telegram_id in ADMIN_IDS:
            users = self.db.search_users(text)
            
            if not users:
                await update.message.reply_text(
                    "❌ Hech narsa topilmadi.",
                    reply_markup=self.get_admin_keyboard()
                )
                self.user_states.pop(telegram_id, None)
                return
            
            message = f"🔍 *Qidiruv natijalari:*\n\n"
            
            for user_data in users[:10]:
                block = "🚫 " if user_data.get('is_blocked') else ""
                admin = "👑 " if user_data.get('is_admin') else ""
                username = f"@{user_data['username']}" if user_data['username'] else "no username"
                
                message += f"{admin}{block}*{user_data['full_name']}*\n"
                message += f"   📱 {username}\n"
                message += f"   🆔 `{user_data['telegram_id']}`\n\n"
            
            keyboard = []
            for user_data in users[:5]:
                keyboard.append([InlineKeyboardButton(
                    f"👤 {user_data['full_name'][:20]}",
                    callback_data=f"admin_user_stats_{user_data['telegram_id']}"
                )])
            
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
            )
            self.user_states.pop(telegram_id, None)
        
        elif state == 'ADMIN_VIEW_PROFILE' and telegram_id in ADMIN_IDS:
            try:
                target_id = int(text.strip())
                await self.admin_view_profile(update, target_id, telegram_id)
            except ValueError:
                await update.message.reply_text(
                    "❌ Noto'g'ri format. Iltimos, faqat raqam kiriting.",
                    reply_markup=self.get_admin_keyboard()
                )
            self.user_states.pop(telegram_id, None)
        
        elif state == 'ADMIN_BROADCAST' and telegram_id in ADMIN_IDS:
            await self.admin_broadcast_send(update, text, telegram_id, context)
        
        elif state == 'ADMIN_BLOCK' and telegram_id in ADMIN_IDS:
            try:
                target_id = int(text.strip())
                
                user_data = self.db.get_user_by_telegram_id(target_id)
                if not user_data:
                    await update.message.reply_text(
                        "❌ Foydalanuvchi topilmadi.",
                        reply_markup=self.get_admin_keyboard()
                    )
                    self.user_states.pop(telegram_id, None)
                    return
                
                if user_data.get('is_blocked'):
                    success = self.db.unblock_user(target_id, telegram_id)
                    action = "blokdan ochildi"
                else:
                    success = self.db.block_user(target_id, telegram_id)
                    action = "bloklandi"
                
                if success:
                    await update.message.reply_text(
                        f"✅ Foydalanuvchi {target_id} {action}!",
                        reply_markup=self.get_admin_keyboard()
                    )
                else:
                    await update.message.reply_text(
                        "❌ Xatolik yuz berdi.",
                        reply_markup=self.get_admin_keyboard()
                    )
                    
            except ValueError:
                await update.message.reply_text(
                    "❌ Noto'g'ri format. Iltimos, faqat raqam kiriting.",
                    reply_markup=self.get_admin_keyboard()
                )
            self.user_states.pop(telegram_id, None)
        
        elif state == 'ADMIN_MESSAGE' and telegram_id in ADMIN_IDS:
            target_id = self.user_states[telegram_id].get('target')
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=f"📩 *Admin xabari*\n\n{text}",
                    parse_mode=ParseMode.MARKDOWN
                )
                await update.message.reply_text(
                    f"✅ Xabar yuborildi!",
                    reply_markup=self.get_admin_keyboard()
                )
            except Exception as e:
                await update.message.reply_text(
                    f"❌ Xatolik: {e}",
                    reply_markup=self.get_admin_keyboard()
                )
            self.user_states.pop(telegram_id, None)
    
    async def _handle_dict_state(self, update: Update, text: str, telegram_id: int,
                                user_id: int, state: dict, context: ContextTypes.DEFAULT_TYPE):
        """Dict state larni qayta ishlash"""
        action = state.get('action')
        step = state.get('step', 1)
        
        # ESLATMA QO'SHISH
        if action == 'ADD_REMINDER':
            if step == 1:
                await self.reminder_add_step2(update, telegram_id, text)
            
            elif step == 2:
                if text == "📅 Bugun":
                    await self.reminder_add_step3_time(update, telegram_id, state['title'], "none", date.today())
                elif text == "🔄 Har kuni":
                    await self.reminder_add_step3_time(update, telegram_id, state['title'], "daily", None)
                elif text == "📆 Hafta kunlari":
                    self.selected_days[telegram_id] = set()
                    await update.message.reply_text(
                        "📆 *Hafta kunlarini tanlang:*\n"
                        "Bir nechta kun tanlashingiz mumkin.\n"
                        "Tugatgach 'Tasdiqlash' tugmasini bosing.",
                        reply_markup=self.get_weekdays_selection_keyboard(telegram_id),
                        parse_mode=ParseMode.MARKDOWN
                    )
                elif text == "📅 Boshqa kun":
                    await update.message.reply_text(
                        "📅 *Sana tanlang:*",
                        reply_markup=self.get_date_selection_keyboard(),
                        parse_mode=ParseMode.MARKDOWN
                    )
                    self.user_states[telegram_id]['step'] = 5
                elif text == "❌ Bekor qilish":
                    self.user_states.pop(telegram_id, None)
                    await update.message.reply_text(
                        "❌ Bekor qilindi.",
                        reply_markup=self.get_main_keyboard(telegram_id)
                    )
                else:
                    await update.message.reply_text(
                        "❌ Noto'g'ri tanlov. Qayta urinib ko'ring.",
                        reply_markup=self.get_reminder_type_keyboard()
                    )
            
            elif step == 3:
                try:
                    datetime.strptime(text, "%H:%M")
                    custom_date = state.get('custom_date')
                    await self.reminder_add_step4_description(update, telegram_id, 
                                                            state['title'], state['repeat_type'], 
                                                            text, custom_date)
                except ValueError:
                    await update.message.reply_text(
                        "❌ Vaqt noto'g'ri. HH:MM formatida kiriting.\n"
                        "Masalan: 14:30",
                        reply_markup=self.get_back_keyboard()
                    )
            
            elif step == 4:
                title = state['title']
                repeat_type = state['repeat_type']
                time_str = state['time']
                custom_date = state.get('custom_date')
                description = "" if text.lower() in ['yo\'q', 'yoq', 'no'] else text
                
                try:
                    now = datetime.now(TIMEZONE)
                    time_obj = datetime.strptime(time_str, "%H:%M").time()
                    
                    if custom_date:
                        reminder_date = custom_date
                    else:
                        reminder_date = now.date()
                    
                    reminder_time = datetime.combine(reminder_date, time_obj, tzinfo=TIMEZONE)
                    
                    if repeat_type == "none" and reminder_time <= now:
                        reminder_time += timedelta(days=1)
                    
                    repeat_days = state.get('repeat_days')
                    
                    success = self.db.add_reminder(
                        user_id=user_id,
                        title=title,
                        reminder_time=reminder_time,
                        description=description,
                        repeat_type=repeat_type,
                        repeat_days=repeat_days
                    )
                    
                    if success:
                        time_display = reminder_time.strftime('%d.%m.%Y %H:%M')
                        
                        if repeat_type == 'none':
                            repeat_text = "⏰ Bir marta"
                        elif repeat_type == 'daily':
                            repeat_text = "🔄 Har kuni"
                        elif repeat_type == 'custom' and repeat_days:
                            days_names = [WEEKDAYS_UZ[d] for d in sorted(repeat_days)]
                            repeat_text = f"📆 {', '.join(days_names)}"
                        else:
                            repeat_text = f"🔄 {repeat_type}"
                        
                        await update.message.reply_text(
                            f"✅ *Eslatma saqlandi!*\n\n"
                            f"📌 *{title}*\n"
                            f"⏰ {time_display}\n"
                            f"{repeat_text}\n"
                            f"{'📝 ' + description if description else ''}",
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=self.get_main_keyboard(telegram_id)
                        )
                    else:
                        await update.message.reply_text(
                            "❌ Xatolik yuz berdi. Qayta urinib ko'ring.",
                            reply_markup=self.get_main_keyboard(telegram_id)
                        )
                    
                    self.selected_days.pop(telegram_id, None)
                    self.user_states.pop(telegram_id, None)
                    
                except Exception as e:
                    logger.error(f"Reminder save error: {e}")
                    await update.message.reply_text(
                        "❌ Xatolik yuz berdi.",
                        reply_markup=self.get_main_keyboard(telegram_id)
                    )
                    self.user_states.pop(telegram_id, None)
            
            elif step == 5:
                # Boshqa sana tanlash
                if text.startswith("📅 "):
                    try:
                        date_str = text.replace("📅 ", "")
                        custom_date = datetime.strptime(date_str, '%d.%m.%Y').date()
                        await self.reminder_add_step3_time(update, telegram_id, 
                                                         state['title'], "none", custom_date)
                    except:
                        await update.message.reply_text(
                            "❌ Sana noto'g'ri. Qayta urinib ko'ring.",
                            reply_markup=self.get_date_selection_keyboard()
                        )
                elif text == "✏️ Boshqa sana":
                    await update.message.reply_text(
                        "📅 *Sanani kiriting (DD.MM.YYYY):*\n"
                        "Masalan: 25.12.2025",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=self.get_back_keyboard()
                    )
                    self.user_states[telegram_id]['step'] = 6
                elif text == "❌ Bekor qilish":
                    self.user_states.pop(telegram_id, None)
                    await update.message.reply_text(
                        "❌ Bekor qilindi.",
                        reply_markup=self.get_main_keyboard(telegram_id)
                    )
                else:
                    await update.message.reply_text(
                        "❌ Noto'g'ri tanlov.",
                        reply_markup=self.get_date_selection_keyboard()
                    )
            
            elif step == 6:
                try:
                    custom_date = datetime.strptime(text, '%d.%m.%Y').date()
                    await self.reminder_add_step3_time(update, telegram_id, 
                                                     state['title'], "none", custom_date)
                except:
                    await update.message.reply_text(
                        "❌ Sana noto'g'ri. DD.MM.YYYY formatida kiriting.\n"
                        "Masalan: 25.12.2025",
                        reply_markup=self.get_back_keyboard()
                    )
        
        # XARAJAT QO'SHISH
        elif action == 'ADD_EXPENSE':
            if step == 1:
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
                    
                    self.user_states[telegram_id] = {
                        'action': 'ADD_EXPENSE',
                        'step': 2,
                        'amount': amount
                    }
                    
                    await update.message.reply_text(
                        "2️⃣ *Kategoriyani tanlang:*",
                        reply_markup=self.get_expense_categories_keyboard(),
                        parse_mode=ParseMode.MARKDOWN
                    )
                except ValueError:
                    await update.message.reply_text(
                        "❌ Miqdor noto'g'ri. Raqam kiriting.\n"
                        "Masalan: 50000, 125000, 1.5M",
                        reply_markup=self.get_back_keyboard()
                    )
            
            elif step == 3:
                amount = state['amount']
                category = state['category']
                description = "" if text.lower() in ['yo\'q', 'yoq', 'no'] else text
                
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
                        f"✅ *Xarajat saqlandi!*\n\n"
                        f"💰 {amount:,.0f} {symbol}\n"
                        f"🏷️ {category}\n"
                        f"{'📝 ' + description if description else ''}",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=self.get_main_keyboard(telegram_id)
                    )
                    
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
                                        f"⚠️ *Ogohlantirish!*\n\n"
                                        f"📂 {category}\n"
                                        f"Limitning {percentage}% sarflandi!\n"
                                        f"💰 {budget['current_spent']:,.0f} / {budget['monthly_limit']:,.0f} {symbol}",
                                        parse_mode=ParseMode.MARKDOWN
                                    )
                                elif alert.startswith('exceeded'):
                                    over = alert.split(':')[1]
                                    await update.message.reply_text(
                                        f"🔴 *Limit oshib ketdi!*\n\n"
                                        f"📂 {category}\n"
                                        f"Limit {over} {symbol}ga oshib ketdi!\n"
                                        f"💰 {budget['current_spent']:,.0f} / {budget['monthly_limit']:,.0f} {symbol}",
                                        parse_mode=ParseMode.MARKDOWN
                                    )
                else:
                    await update.message.reply_text(
                        "❌ Xatolik yuz berdi. Qayta urinib ko'ring.",
                        reply_markup=self.get_main_keyboard(telegram_id)
                    )
                
                self.user_states.pop(telegram_id, None)
        
        # DAROMAD QO'SHISH
        elif action == 'ADD_INCOME':
            if step == 1:
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
                    
                    self.user_states[telegram_id] = {
                        'action': 'ADD_INCOME',
                        'step': 2,
                        'amount': amount
                    }
                    
                    await update.message.reply_text(
                        "2️⃣ *Manbani tanlang:*",
                        reply_markup=self.get_income_categories_keyboard(),
                        parse_mode=ParseMode.MARKDOWN
                    )
                except ValueError:
                    await update.message.reply_text(
                        "❌ Miqdor noto'g'ri. Raqam kiriting.",
                        reply_markup=self.get_back_keyboard()
                    )
            
            elif step == 3:
                amount = state['amount']
                category = state['category']
                description = "" if text.lower() in ['yo\'q', 'yoq', 'no'] else text
                
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
                        f"✅ *Daromad saqlandi!*\n\n"
                        f"💵 +{amount:,.0f} {symbol}\n"
                        f"🏷️ {category}\n"
                        f"{'📝 ' + description if description else ''}",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=self.get_main_keyboard(telegram_id)
                    )
                else:
                    await update.message.reply_text(
                        "❌ Xatolik yuz berdi.",
                        reply_markup=self.get_main_keyboard(telegram_id)
                    )
                
                self.user_states.pop(telegram_id, None)
        
        # QARZ QO'SHISH
        elif action == 'ADD_DEBT':
            if step == 1:
                self.user_states[telegram_id] = {
                    'action': 'ADD_DEBT',
                    'step': 2,
                    'person_name': text
                }
                await update.message.reply_text(
                    "2️⃣ *Qarz miqdorini kiriting:*\n"
                    "Masalan: 500000",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=self.get_back_keyboard()
                )
            
            elif step == 2:
                try:
                    amount = float(text.replace(',', '.'))
                    self.user_states[telegram_id] = {
                        'action': 'ADD_DEBT',
                        'step': 3,
                        'person_name': state['person_name'],
                        'amount': amount
                    }
                    await update.message.reply_text(
                        "3️⃣ *Qarz turini tanlang:*\n"
                        "• berdim - Siz berdingiz\n"
                        "• oldim - Siz oldingiz",
                        reply_markup=ReplyKeyboardMarkup([
                            ["berdim", "oldim"],
                            ["🔙 ORQAGA"]
                        ], resize_keyboard=True),
                        parse_mode=ParseMode.MARKDOWN
                    )
                except ValueError:
                    await update.message.reply_text(
                        "❌ Miqdor noto'g'ri. Raqam kiriting.",
                        reply_markup=self.get_back_keyboard()
                    )
            
            elif step == 3:
                if text.lower() not in ['berdim', 'oldim']:
                    await update.message.reply_text(
                        "❌ Iltimos, 'berdim' yoki 'oldim' deb tanlang.",
                        reply_markup=self.get_back_keyboard()
                    )
                    return
                
                debt_type = 'gave' if text.lower() == 'berdim' else 'took'
                
                self.user_states[telegram_id] = {
                    'action': 'ADD_DEBT',
                    'step': 4,
                    'person_name': state['person_name'],
                    'amount': state['amount'],
                    'debt_type': debt_type
                }
                await update.message.reply_text(
                    "4️⃣ *Tavsif (ixtiyoriy):*\n"
                    "Agar kerak bo'lmasa, 'yo'q' deb yozing",
                    reply_markup=self.get_back_keyboard(),
                    parse_mode=ParseMode.MARKDOWN
                )
            
            elif step == 4:
                description = "" if text.lower() in ['yo\'q', 'yoq', 'no'] else text
                
                success = self.db.add_debt(
                    user_id=user_id,
                    person_name=state['person_name'],
                    amount=state['amount'],
                    debt_type=state['debt_type'],
                    description=description
                )
                
                if success:
                    type_text = "Berdingiz" if state['debt_type'] == 'gave' else "Oldingiz"
                    await update.message.reply_text(
                        f"✅ *Qarz saqlandi!*\n\n"
                        f"👤 {state['person_name']}\n"
                        f"💰 {state['amount']:,.0f} so'm\n"
                        f"📋 {type_text}\n"
                        f"{'📝 ' + description if description else ''}",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=self.get_main_keyboard(telegram_id)
                    )
                else:
                    await update.message.reply_text(
                        "❌ Xatolik yuz berdi.",
                        reply_markup=self.get_main_keyboard(telegram_id)
                    )
                
                self.user_states.pop(telegram_id, None)
        
        # BYUDJET QO'SHISH
        elif action == 'ADD_BUDGET':
            if step == 1 and state.get('custom_category'):
                category = text
                self.user_states[telegram_id] = {
                    'action': 'ADD_BUDGET',
                    'step': 2,
                    'category': category
                }
                await update.message.reply_text(
                    f"✅ Kategoriya: {category}\n\n"
                    "Endi oylik limit miqdorini kiriting:",
                    reply_markup=self.get_back_keyboard()
                )
            
            elif step == 2:
                try:
                    limit = float(text.replace(',', '.'))
                    category = state['category']
                    
                    success = self.db.set_budget_limit(user_id, category, limit)
                    
                    if success:
                        settings = self.db.get_user_settings(user_id)
                        symbol = CURRENCY_SYMBOLS.get(settings.get('currency', 'UZS'), 'so\'m')
                        
                        await update.message.reply_text(
                            f"✅ *Byudjet limiti saqlandi!*\n\n"
                            f"🏷️ {category}\n"
                            f"💰 {limit:,.0f} {symbol}\n\n"
                            f"Limit {settings.get('budget_alert_threshold', 80)}% ga yetganda ogohlantirish olasiz.",
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=self.get_budget_keyboard()
                        )
                    else:
                        await update.message.reply_text(
                            "❌ Xatolik yuz berdi.",
                            reply_markup=self.get_budget_keyboard()
                        )
                    
                    self.user_states.pop(telegram_id, None)
                    
                except ValueError:
                    await update.message.reply_text(
                        "❌ Miqdor noto'g'ri. Raqam kiriting.",
                        reply_markup=self.get_back_keyboard()
                    )
        
        # BYUDJET O'ZGARTIRISH
        elif action == 'EDIT_BUDGET':
            if step == 1:
                try:
                    limit = float(text.replace(',', '.'))
                    category = state['category']
                    
                    success = self.db.set_budget_limit(user_id, category, limit)
                    
                    if success:
                        settings = self.db.get_user_settings(user_id)
                        symbol = CURRENCY_SYMBOLS.get(settings.get('currency', 'UZS'), 'so\'m')
                        
                        await update.message.reply_text(
                            f"✅ *Limit o'zgartirildi!*\n\n"
                            f"🏷️ {category}\n"
                            f"💰 {limit:,.0f} {symbol}",
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=self.get_budget_keyboard()
                        )
                    else:
                        await update.message.reply_text(
                            "❌ Xatolik yuz berdi.",
                            reply_markup=self.get_budget_keyboard()
                        )
                    
                    self.user_states.pop(telegram_id, None)
                    
                except ValueError:
                    await update.message.reply_text(
                        "❌ Miqdor noto'g'ri. Raqam kiriting.",
                        reply_markup=self.get_back_keyboard()
                    )
        
        # SOZLAMALAR
        elif action == 'SET_CURRENCY':
            currency_map = {
                "💵 UZS (so'm)": "UZS",
                "💵 USD ($)": "USD",
                "💶 EUR (€)": "EUR",
                "💷 RUB (₽)": "RUB"
            }
            
            currency = currency_map.get(text, "UZS")
            success = self.db.update_user_setting(user_id, 'currency', currency)
            
            if success:
                await update.message.reply_text(
                    f"✅ *Pul birligi o'zgartirildi!*\n\n"
                    f"💱 {text}",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=self.get_settings_keyboard()
                )
            else:
                await update.message.reply_text(
                    "❌ Xatolik yuz berdi.",
                    reply_markup=self.get_settings_keyboard()
                )
            
            self.user_states.pop(telegram_id, None)
        
        elif action == 'SET_REMINDER_TIME':
            try:
                datetime.strptime(text, "%H:%M")
                
                success = self.db.update_user_setting(user_id, 'reminder_time', text)
                
                if success:
                    await update.message.reply_text(
                        f"✅ *Eslatma vaqti o'zgartirildi!*\n\n"
                        f"🔔 {text}",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=self.get_settings_keyboard()
                    )
                else:
                    await update.message.reply_text(
                        "❌ Xatolik yuz berdi.",
                        reply_markup=self.get_settings_keyboard()
                    )
                
                self.user_states.pop(telegram_id, None)
                
            except ValueError:
                await update.message.reply_text(
                    "❌ Vaqt noto'g'ri. HH:MM formatida kiriting.",
                    reply_markup=self.get_back_keyboard()
                )
        
        elif action == 'SET_THRESHOLD':
            try:
                threshold = int(text.replace('%', ''))
                if threshold < 1 or threshold > 100:
                    raise ValueError
                
                success = self.db.update_user_setting(user_id, 'budget_alert_threshold', threshold)
                
                if success:
                    await update.message.reply_text(
                        f"✅ *Ogohlantirish chegarasi o'zgartirildi!*\n\n"
                        f"💰 {threshold}%",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=self.get_settings_keyboard()
                    )
                else:
                    await update.message.reply_text(
                        "❌ Xatolik yuz berdi.",
                        reply_markup=self.get_settings_keyboard()
                    )
                
                self.user_states.pop(telegram_id, None)
                
            except ValueError:
                await update.message.reply_text(
                    "❌ Noto'g'ri qiymat. 1-100 oralig'ida raqam kiriting.",
                    reply_markup=self.get_back_keyboard()
                )
        
        elif action == 'SET_LANGUAGE':
            lang_map = {
                "🇺🇿 O'zbek tili": "uz",
                "🇷🇺 Rus tili": "ru",
                "🇬🇧 Ingliz tili": "en"
            }
            
            language = lang_map.get(text, "uz")
            
            if language != "uz":
                await update.message.reply_text(
                    "🌐 *Til sozlamalari*\n\n"
                    "Hozircha faqat O'zbek tili qo'llab-quvvatlanadi.\n"
                    "Tez kunda boshqa tillar ham qo'shiladi!",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=self.get_settings_keyboard()
                )
            else:
                success = self.db.update_user_setting(user_id, 'language', language)
                if success:
                    await update.message.reply_text(
                        "✅ *Til o'zgartirildi!*\n\n"
                        "🇺🇿 O'zbek tili",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=self.get_settings_keyboard()
                    )
            
            self.user_states.pop(telegram_id, None)
        
        elif action == 'SET_THEME':
            theme = "light" if text == "☀️ Yoruq" else "dark" if text == "🌙 Qorongʻi" else None
            
            if theme:
                success = self.db.update_user_setting(user_id, 'theme', theme)
                
                if success:
                    await update.message.reply_text(
                        f"✅ *Mavzu o'zgartirildi!*\n\n"
                        f"🎨 {text}",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=self.get_settings_keyboard()
                    )
                else:
                    await update.message.reply_text(
                        "❌ Xatolik yuz berdi.",
                        reply_markup=self.get_settings_keyboard()
                    )
            
            self.user_states.pop(telegram_id, None)


# ==================== SCHEDULER ====================
class ReminderScheduler:
    def __init__(self, db: Database, bot_token: str):
        self.db = db
        self.bot_token = bot_token
        self.running = False
        self.sent_reminders = set()  # Bugun yuborilgan eslatmalarni eslab qolish
    
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
                
                time.sleep(30)  # Har 30 sekundda tekshiradi
                
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(60)
    
    def _check_reminders(self, now: datetime):
        """Eslatmalarni tekshirish va yuborish"""
        try:
            reminders = self.db.get_due_reminders()
            
            for reminder in reminders:
                try:
                    # Bloklangan foydalanuvchini tekshirish
                    if reminder.get('is_blocked'):
                        continue
                    
                    # Bugun yuborilgan eslatmalarni tekshirish
                    reminder_key = f"{reminder['id']}_{now.strftime('%Y-%m-%d')}"
                    if reminder_key in self.sent_reminders:
                        continue
                    
                    telegram_id = reminder['telegram_id']
                    title = reminder['title']
                    
                    # Eslatma vaqtini aniqlash
                    if reminder.get('next_reminder'):
                        reminder_time = reminder['next_reminder']
                    else:
                        reminder_time = reminder['reminder_time']
                    
                    if isinstance(reminder_time, str):
                        reminder_time = datetime.fromisoformat(reminder_time.replace(' ', 'T'))
                    
                    # Vaqtni solishtirish (daqiqagacha)
                    now_rounded = now.replace(second=0, microsecond=0)
                    reminder_rounded = reminder_time.replace(second=0, microsecond=0)
                    
                    # Agar vaqt mos kelsa
                    if now_rounded == reminder_rounded:
                        message = f"🔔 *ESLATMA: {title}*\n"
                        message += f"⏰ {reminder_time.strftime('%H:%M')}"
                        
                        if reminder.get('description'):
                            message += f"\n📝 {reminder['description']}"
                        
                        # Takrorlanuvchi eslatma ekanligini ko'rsatish
                        if reminder['repeat_type'] == 'daily':
                            message += f"\n🔄 Har kuni"
                        elif reminder['repeat_type'] == 'custom' and reminder.get('repeat_days'):
                            days = reminder['repeat_days']
                            days_names = [WEEKDAYS_UZ[d] for d in sorted(days)]
                            message += f"\n📆 {', '.join(days_names)}"
                        
                        # Xabarni yuborish
                        self._send_reminder(telegram_id, message, reminder['id'])
                        
                        # Bugun yuborilgan deb belgilash
                        self.sent_reminders.add(reminder_key)
                        
                        # Eslatma yuborilganligini log qilish
                        self.db.log_reminder_sent(reminder['id'], reminder['user_db_id'])
                        
                        # Keyingi eslatma vaqtini yangilash
                        self.db.update_reminder_next_time(reminder['id'])
                    
                except Exception as e:
                    logger.error(f"Reminder send error: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Check reminders error: {e}")
    
    def _check_budgets(self):
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
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            from telegram import Bot
            bot = Bot(token=self.bot_token)
            
            message = f"⚠️ *Ogohlantirish!*\n\n"
            message += f"📂 {category}\n"
            message += f"💰 Sarflangan: {spent:,.0f} so'm\n"
            message += f"🎯 Limit: {limit:,.0f} so'm\n"
            message += f"📊 Limitning {percentage:.0f}% ga yetdingiz!"
            
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
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            from telegram import Bot
            bot = Bot(token=self.bot_token)
            
            message = f"🔴 *Limit oshib ketdi!*\n\n"
            message += f"📂 {category}\n"
            message += f"💰 Sarflangan: {spent:,.0f} so'm\n"
            message += f"🎯 Limit: {limit:,.0f} so'm\n"
            message += f"⚠️ Limit {over} so'mga oshib ketdi!"
            
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
# ==================== ASOSIY ====================
def main():
    print("=" * 60)
    print("🤖 Smart Assistant Bot - WINDOWS VERSIYA")
    print("=" * 60)
    print(f"👑 Admin ID: {ADMIN_IDS}")
    print(f"⏰ Timezone: {TIMEZONE}")
    print("=" * 60)
    
    db = None
    try:
        db = Database()
        bot_handler = BotHandler(db)
        
        # Windows uchun - lock faylni bot papkasiga yaratish
        lock_file = 'bot.lock'  # Shu papkada bot.lock fayl yaratiladi
        
        if not os.path.exists(lock_file):
            # Lock fayl yaratish
            with open(lock_file, 'w') as f:
                f.write(str(os.getpid()))
            print("✅ Lock fayl yaratildi")
            
            application = Application.builder().token(BOT_TOKEN).build()
            
            application.add_handler(CommandHandler("start", bot_handler.start))
            application.add_handler(CommandHandler("help", bot_handler.show_help))
            application.add_handler(CallbackQueryHandler(bot_handler.handle_callback))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot_handler.handle_message))
            
            scheduler = ReminderScheduler(db, BOT_TOKEN)
            scheduler.start()
            
            print("✅ Bot muvaffaqiyatli yuklandi!")
            print("🔄 Polling ishga tushmoqda...")
            print("=" * 60)
            print("⚠️  Botni to'xtatish uchun: Ctrl+C bosing")
            print("=" * 60)
            
            application.run_polling(drop_pending_updates=True)
        else:
            print("⚠️ Bot allaqachon ishlamoqda!")
            print(f"   Lock fayl mavjud: {lock_file}")
            print("   Agar bot ishlamayotgan bo'lsa, bot.lock faylini o'chirib qayta ishga tushiring.")
            
    except Exception as e:
        print(f"❌ Xatolik: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Lock faylni o'chirish
        if os.path.exists('bot.lock'):
            try:
                os.remove('bot.lock')
                print("✅ Lock fayl o'chirildi")
            except:
                pass
        if db:
            db.close()
        print("🤖 Bot to'xtatildi.")

if __name__ == '__main__':
    main()
