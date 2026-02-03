# bot.py - ADMIN PANEL ALOHIDA TUGMA BILAN

import os
import logging
import sqlite3
import asyncio
from datetime import datetime, timedelta, date
from decimal import Decimal, InvalidOperation
import threading
import time

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# ==================== KONFIGURATSIYA ====================
BOT_TOKEN = "8250421622:AAHpa6q_RMV1d3QNO4tM3YtT9h2jYJebvjw" 
ADMIN_IDS = [8014950410]

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

# ==================== DATABASE ====================
DB_NAME = 'smart_assistant.db'

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.init_tables()
    
    def init_tables(self):
        # Users
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                username TEXT,
                full_name TEXT,
                language TEXT DEFAULT "uz",
                currency TEXT DEFAULT "UZS",
                is_admin BOOLEAN DEFAULT 0,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Reminders
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                reminder_time TIMESTAMP NOT NULL,
                status TEXT DEFAULT "active",
                repeat_type TEXT DEFAULT "none",
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Expenses
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount DECIMAL(10, 2) NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                expense_date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
                income_date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Activities
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                activity_name TEXT NOT NULL,
                activity_time TIME,
                activity_date DATE NOT NULL,
                status TEXT DEFAULT "pending",
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                return_date TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        self.conn.commit()
        logger.info("Database initialized successfully")

    # --- USER METHODS ---
    def add_user(self, telegram_id: int, username: str, full_name: str):
        try:
            # Admin IDs ro'yxatidan tekshirish
            is_admin = 1 if telegram_id in ADMIN_IDS else 0
            
            # Avval foydalanuvchini qo'shamiz yoki mavjud bo'lsa o'zgartirmaymiz
            self.cursor.execute('''
                INSERT OR IGNORE INTO users (telegram_id, username, full_name, is_admin, last_seen) 
                VALUES (?, ?, ?, ?, ?)
            ''', (telegram_id, username, full_name, is_admin, datetime.now()))
            
            # Admin holatini yangilash (agar ADMIN_IDS da bo'lsa)
            if telegram_id in ADMIN_IDS:
                self.cursor.execute('''
                    UPDATE users 
                    SET username = ?, full_name = ?, is_admin = 1, last_seen = ? 
                    WHERE telegram_id = ?
                ''', (username, full_name, datetime.now(), telegram_id))
            else:
                # Oddiy foydalanuvchi uchun faqat last_seen ni yangilash
                self.cursor.execute('''
                    UPDATE users 
                    SET username = ?, full_name = ?, last_seen = ? 
                    WHERE telegram_id = ?
                ''', (username, full_name, datetime.now(), telegram_id))
            
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
        return dict(res) if res else None

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
            self.cursor.execute('INSERT INTO reminders (user_id, title, description, reminder_time, repeat_type) VALUES (?, ?, ?, ?, ?)', 
                             (user_id, title, description, reminder_time, repeat_type))
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            logger.error(f"Reminder add error: {e}")
            return None

    def update_reminder_time(self, rid: int, new_time: datetime):
        try:
            self.cursor.execute('UPDATE reminders SET reminder_time = ?, status = "active" WHERE id = ?', (new_time, rid))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Reminder update error: {e}")

    def delete_reminder(self, reminder_id: int, user_id: int):
        self.cursor.execute('DELETE FROM reminders WHERE id = ? AND user_id = ?', (reminder_id, user_id))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def get_user_reminders(self, user_id: int):
        self.cursor.execute('SELECT * FROM reminders WHERE user_id = ? AND status = "active" ORDER BY reminder_time ASC', (user_id,))
        return [dict(row) for row in self.cursor.fetchall()]

    # --- INCOME ---
    def add_income(self, user_id: int, amount: float, category: str, description: str, inc_date=None):
        try:
            if not inc_date: inc_date = date.today()
            self.cursor.execute('INSERT INTO income (user_id, amount, category, description, income_date) VALUES (?, ?, ?, ?, ?)', 
                             (user_id, amount, category, description, inc_date))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Income add error: {e}")
            return False

    def get_user_income(self, user_id: int, days=30):
        start_date = (date.today() - timedelta(days=days)).strftime('%Y-%m-%d')
        self.cursor.execute('SELECT * FROM income WHERE user_id = ? AND income_date >= ? ORDER BY income_date DESC', (user_id, start_date))
        return [dict(row) for row in self.cursor.fetchall()]

    # --- EXPENSES ---
    def add_expense(self, user_id: int, amount: float, category: str, description: str, exp_date=None):
        try:
            if not exp_date: exp_date = date.today()
            self.cursor.execute('INSERT INTO expenses (user_id, amount, category, description, expense_date) VALUES (?, ?, ?, ?, ?)', 
                             (user_id, amount, category, description, exp_date))
            
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

    def get_user_expenses(self, user_id: int, days=30):
        start_date = (date.today() - timedelta(days=days)).strftime('%Y-%m-%d')
        self.cursor.execute('SELECT * FROM expenses WHERE user_id = ? AND expense_date >= ? ORDER BY expense_date DESC', (user_id, start_date))
        return [dict(row) for row in self.cursor.fetchall()]

    # --- DEBTS ---
    def add_debt(self, user_id: int, person_name: str, amount: float, debt_type: str, description=""):
        try:
            self.cursor.execute('INSERT INTO debts (user_id, person_name, amount, debt_type, description) VALUES (?, ?, ?, ?, ?)', 
                             (user_id, person_name, amount, debt_type, description))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Debt add error: {e}")
            return False

    def get_user_debts(self, user_id: int):
        self.cursor.execute('SELECT * FROM debts WHERE user_id = ? AND status = "active" ORDER BY created_at DESC', (user_id,))
        return [dict(row) for row in self.cursor.fetchall()]

    def close_debt(self, debt_id: int, user_id: int):
        self.cursor.execute('UPDATE debts SET status = "returned", return_date = ? WHERE id = ? AND user_id = ?', 
                         (datetime.now(), debt_id, user_id))
        self.conn.commit()

    # --- ACTIVITIES ---
    def add_activity(self, user_id: int, name: str, time_str: str = None):
        try:
            self.cursor.execute('INSERT INTO daily_activities (user_id, activity_name, activity_time, activity_date) VALUES (?, ?, ?, ?)', 
                             (user_id, name, time_str, date.today()))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Activity add error: {e}")
            return False

    def get_activities(self, user_id: int):
        self.cursor.execute('SELECT * FROM daily_activities WHERE user_id = ? AND activity_date = date("now") ORDER BY activity_time ASC', (user_id,))
        return [dict(row) for row in self.cursor.fetchall()]
    
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
        self.cursor.execute('SELECT SUM(amount) as total FROM expenses WHERE user_id = ? AND strftime("%Y-%m", expense_date) = ?', (user_id, month_year))
        exp_data = self.cursor.fetchone()
        total_exp = exp_data['total'] or 0
        
        self.cursor.execute('SELECT SUM(amount) as total FROM income WHERE user_id = ? AND strftime("%Y-%m", income_date) = ?', (user_id, month_year))
        inc_data = self.cursor.fetchone()
        total_inc = inc_data['total'] or 0

        self.cursor.execute('SELECT category, SUM(amount) as total FROM expenses WHERE user_id = ? AND strftime("%Y-%m", expense_date) = ? GROUP BY category', (user_id, month_year))
        cats = self.cursor.fetchall()
        
        return {
            'total_expense': total_exp,
            'total_income': total_inc,
            'balance': total_inc - total_exp,
            'by_category': [dict(row) for row in cats]
        }

    # --- ADMIN SPECIFIC ---
    def get_all_users(self):
        self.cursor.execute('SELECT * FROM users ORDER BY registered_at DESC')
        return [dict(row) for row in self.cursor.fetchall()]

    def get_recent_logins(self, limit=10):
        """So'nggi kirgan foydalanuvchilarni olish (last_seen bo'yicha)"""
        self.cursor.execute('SELECT * FROM users ORDER BY last_seen DESC LIMIT ?', (limit,))
        return [dict(row) for row in self.cursor.fetchall()]

    def get_user_stats_by_id(self, user_id: int):
        self.cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user = self.cursor.fetchone()
        if not user: return None
        summary = self.get_financial_summary(user_id)
        debts = self.db_get_user_debts_by_id(user_id)
        return {'user': dict(user), 'finance': summary, 'debts': debts}
    
    def db_get_user_debts_by_id(self, user_id: int):
        self.cursor.execute('SELECT * FROM debts WHERE user_id = ? AND status = "active"', (user_id,))
        return [dict(row) for row in self.cursor.fetchall()]

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
        return {'users': users, 'reminders': rems, 'debts': debts, 'total_balance': total_inc - total_exp}

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
                now = datetime.now()
                self.db.cursor.execute('''
                    SELECT r.*, u.telegram_id FROM reminders r
                    JOIN users u ON r.user_id = u.id
                    WHERE r.status="active" AND r.reminder_time <= ?
                ''', (now,))
                rows = self.db.cursor.fetchall()
                
                for row in rows:
                    r = dict(row)
                    msg = f"🔔 *ESLATMA: {r['title']}*\n📝 {r['description']}\n⏰ {r['reminder_time']}"
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
        await bot.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN)
        
        if repeat_type == 'daily':
            self.db.cursor.execute('SELECT reminder_time FROM reminders WHERE id = ?', (rid,))
            old_time_res = self.db.cursor.fetchone()
            if old_time_res:
                old_time = datetime.strptime(old_time_res['reminder_time'], "%Y-%m-%d %H:%M:%S")
                next_time = old_time + timedelta(days=1)
                self.db.update_reminder_time(rid, next_time)
        else:
            self.db.cursor.execute('UPDATE reminders SET status="sent" WHERE id=?', (rid,))
            self.db.conn.commit()

# ==================== BOT LOGIC ====================
class SmartAssistantBot:
    def __init__(self):
        self.db = Database()
    
    def is_user_admin(self, telegram_id: int) -> bool:
        """Foydalanuvchining admin ekanligini tekshirish"""
        # 1. Global admin IDs ro'yxatidan tekshirish
        if telegram_id in ADMIN_IDS:
            return True
        
        # 2. Bazadan tekshirish
        user_info = self.db.get_user_info(telegram_id)
        if user_info and user_info.get('is_admin') == 1:
            return True
        
        return False

    def get_main_keyboard(self, telegram_id: int = None):
        """ASOSIY MENYU - Admin bo'lsa ADMIN PANEL tugmasi qo'shiladi"""
        base = [
            ["➕ ESLATMA", "💰 XARAJAT", "💵 DAROMAD"],
            ["📅 VAZIFA", "💸 QARZLARIM", "🎯 BYUDJET"],
            ["📊 HISOBOT", "⚙️ SOZLAMALAR", "🆘 YORDAM"]
        ]
        
        # Admin uchun alohida tugma
        if telegram_id and self.is_user_admin(telegram_id):
            base.append(["👑 ADMIN PANEL"])
        
        return ReplyKeyboardMarkup(base, resize_keyboard=True)

    def get_settings_keyboard(self):
        return ReplyKeyboardMarkup([
            ["🇺🇿 O'zbek tili", "🇬🇧 English"],
            ["💱 Valyuta: UZS", "🗑️ Barchasini o'chirish"],
            ["🔙 ORQAGA"]
        ], resize_keyboard=True)

    async def start(self, update, context):
        user = update.effective_user
        is_admin = self.db.add_user(user.id, user.username, user.full_name)
        
        txt = f"👋 Salom, {user.full_name}!\n\n🤖 *Smart Assistant Bot* ga xush kelibsiz."
        if is_admin: 
            txt += "\n\n👑 Siz Admin sifatida tizimga kirdingiz."
            # Admin statusini bazaga yozishni kuchaytiramiz
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
        """Admin statusini majburiy o'rnatish"""
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

        # Admin statusini yangi funksiya orqali tekshirish
        is_admin_status = self.is_user_admin(uid)
        
        if text == "🔙 ORQAGA":
            context.user_data.clear()
            # Asosiy menyuga qaytish (Admin o'z hisobiga ishlashi uchun)
            await update.message.reply_text("Asosiy menyu", reply_markup=self.get_main_keyboard(uid))
            return

        if text == "⚙️ SOZLAMALAR":
            context.user_data.clear()
            await update.message.reply_text("⚙️ *SOZLAMALAR*", reply_markup=self.get_settings_keyboard(), parse_mode=ParseMode.MARKDOWN)
            return

        # ================= ADMIN PANEL LOGICASI =================
        if text == "👑 ADMIN PANEL":
            if is_admin_status:
                stats = self.db.get_bot_stats()
                msg = f"👑 *ADMIN PANEL*\n\n"
                msg += f"👥 Foydalanuvchilar: {stats['users']}\n"
                msg += f"🔔 Faol eslatmalar: {stats['reminders']}\n"
                msg += f"💸 Faol qarzlar: {stats['debts']}\n"
                msg += f"💰 Bot balansi: {stats['total_balance']:,.0f} so'm\n\n"
                msg += "Boshqaruv bo'limini tanlang:"
                
                # Admin klaviaturasi
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
            # 1. Foydalanuvchilar ro'yxati
            if text == "👥 FOYDALANUVCHILAR":
                users = self.db.get_all_users()
                if not users: 
                    await update.message.reply_text("Foydalanuvchilar yo'q.")
                else:
                    res = "👥 *BARCHA FOYDALANUVCHILAR (Ro'yxat)*\n\n"
                    for u in users[:10]:
                        admin_badge = "👑 " if u['is_admin'] else ""
                        res += f"• {admin_badge}*{u['full_name']}*\n  ID: {u['id']} | @{u['username'] or 'no_user'}\n\n"
                    if len(users) > 10: 
                        res += f"... va yana {len(users) - 10} ta foydalanuvchi."
                    res += "\n💡 *Profilni ko'rish uchun ID yuboring.*"
                    await update.message.reply_text(res, parse_mode=ParseMode.MARKDOWN)
                return
            
            # 2. So'nggi kirishlar
            elif text == "🕒 SO'NGGI KIRISHLAR":
                users = self.db.get_recent_logins(10)
                if not users: 
                    await update.message.reply_text("Hali hech kim kirmagan.")
                else:
                    res = "🕒 *SO'NGGI KIRISHLAR (Faollik)*\n\n"
                    for u in users:
                        admin_badge = "👑 " if u['is_admin'] else ""
                        seen_time = u['last_seen']
                        res += f"{admin_badge}*{u['full_name']}*\n  ⏰ {seen_time}\n  🆔 ID: {u['id']}\n\n"
                    res += "\n💡 *Profilni ko'rish uchun ID yuboring.*"
                    await update.message.reply_text(res, parse_mode=ParseMode.MARKDOWN)
                return
            
            # 3. Profil ko'rish (ID orqali)
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
            
            # 4. Xabar yuborish
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
            
            # 5. Global Statistika
            elif text == "📊 GLOBAL STATISTIKA":
                stats = self.db.get_bot_stats()
                res = f"📊 *GLOBAL STATISTIKA*\n\n"
                res += f"👥 Jami foydalanuvchilar: {stats['users']}\n"
                res += f"🔔 Faol eslatmalar: {stats['reminders']}\n"
                res += f"💸 Faol qarzlar: {stats['debts']}\n"
                res += f"💰 Bot balansi: {stats['total_balance']:,.0f} so'm"
                await update.message.reply_text(res, parse_mode=ParseMode.MARKDOWN)
                return
            
            # 6. Asosiy menyuga qaytish
            elif text == "🔙 ASOSIY MENYU":
                context.user_data.clear()
                await update.message.reply_text("Asosiy menyu", reply_markup=self.get_main_keyboard(uid))
                return

        # ================= SOZLAMALAR =================
        if text == "🗑️ BARCHASINI O'CHIRISH":
            await update.message.reply_text("⚠️ Barcha ma'lumot o'chirilsinmi? `HA` / `YO'Q`", parse_mode=ParseMode.MARKDOWN)
            context.user_data['action'] = 'CONFIRM_CLEAR'
        elif text == "💱 Valyuta: UZS":
            self.db.update_user_settings(user_id, currency='UZS')
            await update.message.reply_text("✅ Valyuta: O'zbek So'mi (UZS)")
        elif text == "🇺🇿 O'zbek tili":
            self.db.update_user_settings(user_id, lang='uz')
            await update.message.reply_text("✅ Til o'zgartirildi: O'zbek tili")
        elif text == "🇬🇧 English":
            self.db.update_user_settings(user_id, lang='en')
            await update.message.reply_text("✅ Language changed: English")

        # ================= ESLATMA QO'SHISH =================
        elif text == "➕ ESLATMA":
            context.user_data.clear()
            context.user_data['rem_step'] = 1
            await update.message.reply_text("🔔 *Yangi eslatma qo'shish*\n\n1-qadam. Eslatma *nomini* yozing:",
                reply_markup=ReplyKeyboardMarkup([["🔙 Bekor qilish"]], resize_keyboard=True), parse_mode=ParseMode.MARKDOWN)
            return

        if context.user_data.get('rem_step') == 1:
            if text == "🔙 Bekor qilish":
                context.user_data.clear()
                await update.message.reply_text("Bekor qilindi.", reply_markup=self.get_main_keyboard(uid))
                return
            context.user_data['rem_title'] = text
            context.user_data['rem_step'] = 2
            await update.message.reply_text(f"2-qadam. Eslatma *vaqtini* yozing (HH:MM):\nMasalan: 14:30", 
                                          reply_markup=ReplyKeyboardMarkup([["🔙 Bekor qilish"]], resize_keyboard=True), parse_mode=ParseMode.MARKDOWN)
            return

        if context.user_data.get('rem_step') == 2:
            if text == "🔙 Bekor qilish":
                context.user_data.clear()
                await update.message.reply_text("Bekor qilindi.", reply_markup=self.get_main_keyboard(uid))
                return
            try:
                time_obj = datetime.strptime(text, "%H:%M")
                now = date.today()
                rem_time = datetime.combine(now, time_obj.time())
                if rem_time < datetime.now(): 
                    rem_time += timedelta(days=1)
                context.user_data['rem_time'] = rem_time
                context.user_data['rem_step'] = 3
                await update.message.reply_text("3-qadam. Qachon eslatilsin?", 
                                              reply_markup=ReplyKeyboardMarkup([["🔁 Har kuni", "📅 Bugun"], ["🔙 Bekor qilish"]], resize_keyboard=True), parse_mode=ParseMode.MARKDOWN)
            except ValueError:
                await update.message.reply_text("❌ Vaqt formati noto'g'ri. `HH:MM`")
            return

        if context.user_data.get('rem_step') == 3:
            if text == "🔙 Bekor qilish":
                context.user_data.clear()
                await update.message.reply_text("Bekor qilindi.", reply_markup=self.get_main_keyboard(uid))
                return
            repeat = "daily" if text == "🔁 Har kuni" else "none"
            title = context.user_data.get('rem_title')
            rtime = context.user_data.get('rem_time')
            if self.db.add_reminder(user_id, title, "", rtime, repeat):
                msg = f"✅ *Eslatma saqlandi!*\n\n📌 {title}\n⏰ {rtime.strftime('%d.%m %H:%M')}"
                if repeat == 'daily': 
                    msg += "\n🔁 Har kuni takrorlanadi"
                await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_main_keyboard(uid))
            context.user_data.clear()
            return

        # ================= OTHER FEATURES =================
        elif text == "💸 QARZLARIM":
            debts = self.db.get_user_debts(user_id)
            if not debts:
                await update.message.reply_text("📭 Qarzlar yo'q.", reply_markup=ReplyKeyboardMarkup([["➕ QARZ QO'SHISH"], ["🔙 ORQAGA"]], resize_keyboard=True))
            else:
                res = "💸 *QARZLAR:*\n\n"
                for d in debts:
                    icon = "📤" if d['debt_type'] == 'gave' else "📥"
                    type_txt = "Berdingiz" if d['debt_type'] == 'gave' else "Oldingiz"
                    res += f"{icon} *{d['person_name']}*: {d['amount']:,.0f} so'm ({type_txt}) | ID: `{d['id']}`\n\n"
                res += "Qaytarish uchun ID ni yuboring."
                await update.message.reply_text(res, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardMarkup([["➕ QARZ QO'SHISH"], ["🔙 ORQAGA"]], resize_keyboard=True))
                context.user_data['action'] = 'RETURN_DEBT'
        
        elif text == "➕ QARZ QO'SHISH":
            await update.message.reply_text("🆕 *QARZ QO'SHISH*\n\nFormat: `Ism | Miqdor | Turi`\nTuri: `berdim` yoki `oldim`\nNamuna: `Ali | 500000 | berdim`", parse_mode=ParseMode.MARKDOWN)
            context.user_data['action'] = 'ADD_DEBT'

        elif text == "💰 XARAJAT":
            await update.message.reply_text("💰 *XARAJAT QO'SHISH*\n\nFormat: `Miqdor | Kategoriya | Tavsif`\nNamuna: `50000 | Taom | Lagmon`", parse_mode=ParseMode.MARKDOWN)
            context.user_data['action'] = 'ADD_EXPENSE'

        elif text == "💵 DAROMAD":
            await update.message.reply_text("💵 *DAROMAD QO'SHISH*\n\nFormat: `Miqdor | Manba | Tavsif`\nNamuna: `1000000 | Oylik Maosh | IT`", parse_mode=ParseMode.MARKDOWN)
            context.user_data['action'] = 'ADD_INCOME'
        
        elif text == "📊 HISOBOT":
            summary = self.db.get_financial_summary(user_id)
            bal_color = "🟢" if summary['balance'] >= 0 else "🔴"
            msg = f"📊 *MO LIYAVIY HISOBOT (Oylik)*\n\n💵 Daromad: {summary['total_income']:,.0f} so'm\n💰 Xarajat: {summary['total_expense']:,.0f} so'm\n{bal_color} *QOLDIQ:* {summary['balance']:,.0f} so'm"
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

        elif text == "🎯 BYUDJET":
            budgets = self.db.get_budgets(user_id)
            if not budgets:
                await update.message.reply_text("🎯 *BYUDJET*\nLimit belgilanmagan.", reply_markup=ReplyKeyboardMarkup([["➕ LIMIT QO'SHISH"], ["🔙 ORQAGA"]], resize_keyboard=True))
            else:
                res = ""
                for b in budgets:
                    pct = (b['current_spent']/b['monthly_limit'])*100 if b['monthly_limit'] else 0
                    bar = "█"*int(pct/10) + "░"*(10-int(pct/10))
                    res += f"📂 {b['category']}\n{bar} {pct:.0f}%\n{b['current_spent']:,.0f} / {b['monthly_limit']:,.0f}\n\n"
                await update.message.reply_text(res, parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardMarkup([["➕ LIMIT QO'SHISH"], ["🔙 ORQAGA"]], resize_keyboard=True))
        
        elif text == "➕ LIMIT QO'SHISH":
            await update.message.reply_text("🎯 *LIMIT BELGILASH*\nFormat: `Kategoriya | Limit`\nNamuna: `Transport | 1000000`", parse_mode=ParseMode.MARKDOWN)
            context.user_data['action'] = 'SET_BUDGET'

        elif text == "📅 VAZIFA":
            await update.message.reply_text("📅 *VAZIFA QO'SHISH*\nFormat: `Nomi | Vaqt`\nNamuna: `Dars | 08:30`", parse_mode=ParseMode.MARKDOWN)
            context.user_data['action'] = 'ADD_ACTIVITY'
        
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

        elif text == "🔔 ESLATMALARIM":
            rems = self.db.get_user_reminders(user_id)
            if not rems: 
                await update.message.reply_text("Eslatmalar yo'q.")
            else:
                res = "🔔 *ESLATMALAR:*\n\n"
                for r in rems:
                    rep = "🔁" if r['repeat_type'] == 'daily' else "📅"
                    res += f"{rep} *{r['title']}* - {r['reminder_time']}\n   ID: `{r['id']}`\n\n"
                res += "O'chirish uchun ID ni yuboring."
                await update.message.reply_text(res, parse_mode=ParseMode.MARKDOWN)
                context.user_data['action'] = 'DELETE_REMINDER'

        else:
            action = context.user_data.get('action')
            
            if action == 'ADD_EXPENSE':
                parts = [p.strip() for p in text.split('|')]
                if len(parts) >= 2:
                    try:
                        amt = float(parts[0].replace(',', '.'))
                        cat = parts[1]
                        desc = parts[2] if len(parts) > 2 else ""
                        if self.db.add_expense(user_id, amt, cat, desc):
                            await update.message.reply_text(f"✅ Xarajat qo'shildi: {amt:,.0f} so'm")
                    except: 
                        await update.message.reply_text("❌ Xato format.")
                context.user_data['action'] = None

            elif action == 'ADD_INCOME':
                parts = [p.strip() for p in text.split('|')]
                if len(parts) >= 2:
                    try:
                        amt = float(parts[0].replace(',', '.'))
                        cat = parts[1]
                        desc = parts[2] if len(parts) > 2 else ""
                        if self.db.add_income(user_id, amt, cat, desc):
                            await update.message.reply_text(f"✅ Daromad qo'shildi: {amt:,.0f} so'm")
                    except: 
                        await update.message.reply_text("❌ Xato format.")
                context.user_data['action'] = None

            elif action == 'ADD_DEBT':
                parts = [p.strip() for p in text.split('|')]
                if len(parts) >= 3:
                    try:
                        name, amt, dtype = parts[0], float(parts[1].replace(',', '.')), parts[2].lower()
                        if dtype in ['berdim', 'oldim'] and self.db.add_debt(user_id, name, amt, dtype):
                            await update.message.reply_text(f"✅ Qayd qilindi.")
                    except: 
                        await update.message.reply_text("❌ Xato format.")
                context.user_data['action'] = None

            elif action == 'SET_BUDGET':
                parts = [p.strip() for p in text.split('|')]
                if len(parts) >= 2:
                    try:
                        cat, amt = parts[0], float(parts[1].replace(',', '.'))
                        self.db.set_budget_limit(user_id, cat, amt)
                        await update.message.reply_text(f"✅ Limit belgilandi.")
                    except: 
                        await update.message.reply_text("❌ Xato.")
                context.user_data['action'] = None

            elif action == 'ADD_ACTIVITY':
                parts = [p.strip() for p in text.split('|')]
                name, time_str = parts[0], (parts[1] if len(parts)>1 else None)
                if self.db.add_activity(user_id, name, time_str):
                    await update.message.reply_text("✅ Vazifa qo'shildi.")
                context.user_data['action'] = None

            elif action == 'DELETE_REMINDER':
                try:
                    if self.db.delete_reminder(int(text), user_id): 
                        await update.message.reply_text("🗑️ O'chirildi.")
                    else: 
                        await update.message.reply_text("❌ Topilmadi.")
                except: 
                    await update.message.reply_text("❌ ID raqam kiriting.")
                context.user_data['action'] = None

            elif action == 'RETURN_DEBT':
                try:
                    self.db.close_debt(int(text), user_id)
                    await update.message.reply_text("✅ Qarz yopildi.")
                except: 
                    await update.message.reply_text("❌ Xato.")
                context.user_data['action'] = None
            
            elif action == 'COMPLETE_ACTIVITY':
                try:
                    self.db.complete_activity(int(text), user_id)
                    await update.message.reply_text("✅ Bajarildi.")
                except: 
                    await update.message.reply_text("❌ Xato.")
                context.user_data['action'] = None

            elif action == 'CONFIRM_CLEAR':
                if text.upper() == 'HA':
                    self.db.clear_all_user_data(user_id)
                    await update.message.reply_text("🗑️ Barcha ma'lumot o'chirildi.", reply_markup=self.get_main_keyboard(uid))
                else: 
                    await update.message.reply_text("Bekor qilindi.")
                context.user_data['action'] = None
            
            else:
                await update.message.reply_text("Buyruq aniqlanmadi. Menyuni tanlang.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    bot_instance = SmartAssistantBot()
    
    app.add_handler(CommandHandler("start", bot_instance.start))
    app.add_handler(CommandHandler("admin", bot_instance.force_admin))  # yangi admin buyrug'i
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot_instance.handle_message))
    
    db = Database()
    scheduler = ReminderScheduler(db)
    scheduler.start()
    
    print("🤖 Bot ishga tushmoqda...")
    print(f"👑 Admin ID: {ADMIN_IDS[0]}")
    print("➡️ Botni ishga tushirish uchun:")
    print("1. /admin buyrug'ini yuboring")
    print("2. /start buyrug'ini yuboring")
    print("3. Endi '👑 ADMIN PANEL' tugmasi ko'rinishi kerak")
    
    app.run_polling()

if __name__ == '__main__':
    main()