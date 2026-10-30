import asyncio
import logging
import sqlite3
import json
import html
import os
from datetime import datetime, date, timedelta
import calendar
import random
import io
import urllib.request
import urllib.parse
import urllib.error


from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# =========================================================
# SABBIR XYZ SHOP
# =========================================================
# Security: keep the bot token only in the hosting provider's environment variables.
# Never hard-code or commit a Telegram bot token into source control.
BOT_TOKEN = os.getenv("BOT_TOKEN", "8821523566:AAF1u4oV5VSEWxYFXWg7IJzjYYbnPQQfJQE").strip()
ADMIN_ID = 8752830051

BKASH = "01755-196906"
NAGAD = "01706-965471"
REF_REWARD = 5.0
REF_REWARD_LOW = 2.0
REF_REWARD_HIGH = 5.0
REF_THRESHOLD = 100.0
DB_FILE = "sabbir_xyz_shop.db"

logging.basicConfig(level=logging.INFO)
bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# =========================================================
# DATABASE
# =========================================================
def db():
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        username TEXT,
        phone TEXT,
        balance REAL DEFAULT 0,
        ref_by INTEGER,
        verified INTEGER DEFAULT 0,
        banned INTEGER DEFAULT 0,
        joined_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        description TEXT DEFAULT '',
        demo_file_id TEXT,
        demo_type TEXT,
        delivery_type TEXT,
        delivery_data TEXT,
        validity TEXT DEFAULT '',
        device_limit TEXT DEFAULT '',
        features TEXT DEFAULT '',
        expire_date TEXT DEFAULT '',
        stock_status INTEGER DEFAULT 1,
        product_type TEXT DEFAULT 'standard',
        apk_url TEXT DEFAULT '',
        active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS balance_deposits(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        payment_method TEXT DEFAULT '',
        pay_number TEXT DEFAULT '',
        screenshot_id TEXT DEFAULT '',
        status TEXT DEFAULT 'PENDING',
        created_at TEXT NOT NULL,
        processed_at TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        price REAL NOT NULL,
        status TEXT DEFAULT 'PENDING',
        txid TEXT,
        screenshot_id TEXT,
        pay_number TEXT,
        payment_method TEXT DEFAULT '',
        expiry_at TEXT DEFAULT '',
        referral_paid INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    );



    CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY,
        value TEXT
    );

    CREATE TABLE IF NOT EXISTS admins(
        user_id INTEGER PRIMARY KEY
    );

    CREATE TABLE IF NOT EXISTS support_messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT,
        username TEXT,
        chat_id INTEGER NOT NULL,
        message_id INTEGER NOT NULL,
        message_text TEXT DEFAULT '',
        status TEXT DEFAULT 'NEW',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS lucky_spins(
        user_id INTEGER NOT NULL,
        spin_date TEXT NOT NULL,
        prize INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        PRIMARY KEY(user_id, spin_date)
    );

    CREATE TABLE IF NOT EXISTS apk_plans(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        validity TEXT NOT NULL,
        price REAL NOT NULL DEFAULT 0,
        password TEXT NOT NULL DEFAULT '',
        device_limit TEXT DEFAULT '',
        stock_status INTEGER DEFAULT 1,
        active INTEGER DEFAULT 1,
        FOREIGN KEY(product_id) REFERENCES products(id)
    );

    CREATE TABLE IF NOT EXISTS apk_stock(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id INTEGER NOT NULL,
        password TEXT NOT NULL,
        status TEXT DEFAULT 'AVAILABLE',
        sold_order_id INTEGER,
        sold_user_id INTEGER,
        created_at TEXT NOT NULL,
        sold_at TEXT DEFAULT '',
        active INTEGER DEFAULT 1,
        FOREIGN KEY(plan_id) REFERENCES apk_plans(id)
    );
    """)

    for col, typ in [("payment_method", "TEXT DEFAULT ''"), ("expiry_at", "TEXT DEFAULT ''"), ("plan_id", "INTEGER"), ("apk_stock_id", "INTEGER"), ("delivery_password", "TEXT DEFAULT ''"), ("delivery_type_snapshot", "TEXT DEFAULT ''"), ("delivery_data_snapshot", "TEXT DEFAULT ''")]: 
        try:
            con.execute(f"ALTER TABLE orders ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass

    # Safe migrations for existing databases.
    for col, typ in [("device_limit", "TEXT DEFAULT ''")]:
        try:
            con.execute(f"ALTER TABLE apk_plans ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass

    for col, typ in [
        ("validity", "TEXT DEFAULT ''"),
        ("device_limit", "TEXT DEFAULT ''"),
        ("features", "TEXT DEFAULT ''"),
        ("expire_date", "TEXT DEFAULT ''"),
        ("stock_status", "INTEGER DEFAULT 1"),
        ("product_type", "TEXT DEFAULT 'standard'"),
        ("apk_url", "TEXT DEFAULT ''"),
    ]:
        try:
            con.execute(f"ALTER TABLE products ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass

    # Migrate legacy one-password APK plans into the new per-password stock table.
    try:
        legacy_plans = con.execute("SELECT id, password FROM apk_plans WHERE active=1 AND TRIM(password)<>''").fetchall()
        for lp in legacy_plans:
            exists = con.execute("SELECT 1 FROM apk_stock WHERE plan_id=? LIMIT 1", (lp["id"],)).fetchone()
            if not exists and str(lp["password"] or "").strip():
                con.execute("INSERT INTO apk_stock(plan_id,password,status,created_at) VALUES(?,?,?,?)", (lp["id"], str(lp["password"]).strip(), "AVAILABLE", datetime.now().isoformat()))
        con.commit()
    except Exception:
        logging.exception("Legacy APK stock migration failed")

    defaults = {
        "welcome": """🏪 ━✦ 𝐒𝐀𝐁𝐁𝐈𝐑 𝐗𝐘𝐙 𝐒𝐇𝐎𝐏 ✦━ 🏪
━━━━━━━━━━━━━━━━━━

👋 Welcome {name}


⭐ ━ SHOP FEATURES ━ ⭐
├ ✅ All Free Fire Hack
├ 🔑 Premium Game Keys
├ ⚡ Instant Delivery 24/7
├ 🔒 100% Secure Payment
├ 💸 Best Prices Guaranteed
├ 🎁 Referral Rewards
└ 🏆 Professional Support

━━━━━━━━━━━━━━━━━━
🚀 Click Shop Now to Start!""",
        "support": """🎫 ━ SUPPORT CENTER ━ 🎫
━━━━━━━━━━━━━━━━━━

Need help? We're here 24/7! 💬

├ Create a ticket for:
├ 🔑 Missing keys
├ 💳 Payment issues
├ ❓ General questions
└ 🚀 Instant support!

💡 How Support Works

├ 1️⃣ Click Telegram Support
├ 2️⃣ Click WhatsApp Support
├ 3️⃣ Click Send Trick button
└ ✅ Get help from admin!""",
        "deposit_message": """💰 ADD BALANCE

━━━━━━━━━━━━━━━━━━
💳 SELECT AMOUNT TO DEPOSIT:
━━━━━━━━━━━━━━━━━━

⚡ Payment Methods:
├ 🇧🇩 BKash (Bangladesh)
└ 🇧🇩 Nagad (Bangladesh)

✅ Use balance for purchases!""",
        "trick_message": """🎫 <b>OPEN SUPPORT TICKET</b>

━━━━━━━━━━━━━━━━━━
📝 <b>Enter Transaction ID</b>
━━━━━━━━━━━━━━━━━━

💡 <b>You can send:</b>
• Order ID (from purchases)
• Deposit ID (from balance topup)

📋 <b>Examples:</b>
• <code>ORD_1234567890_123</code>

• <code>DEP_1234567890_123</code>

⚠️ Only your own transactions!""",
        "referral": """🎁 REFER &amp; EARN

Apnar Referral Link diye Friends Invite korun.
Apnar Link theke kono Verified User Product Buy korle:

• ৳100 ba kom hole → ৳2 Commission
• ৳100 er beshi hole → ৳5 Commission paben.

Apnar Earn kora Commission directly Wallet-e Add hoye jabe.

🔗 <b>Your Referral Link:</b>

<code>{referral_link}</code>

👥 Total Referrals: <b>{referrals}</b>
💰 Wallet Balance: <b>৳{balance}</b>""",
        "verification_message": """🔐 ━━━ ACCOUNT VERIFICATION ━━━ 🔐

✨ Welcome to SABBIR XYZ SHOP!

To access all premium features,
please verify your account first.

━━━━━━━━━━━━━━━━━━

🛡️ Why Verify?

├ ✅ Secure your account
├ ⚡ Unlock all features
├ 💎 Access premium services
└ 🔒 Enhanced account protection

━━━━━━━━━━━━━━━━━━

👇 Click the button below to verify
your account and continue.

📱 Please share your phone number to complete verification.""",
        "shop_message": """🎮 <b>━ CHOOSE YOUR GAME ━</b> 🎮
━━━━━━━━━━━━━━━━━━

⭐ <b>Available Products</b>

├ 💸 <b>Premium Keys</b>
├ ⚡ <b>Instant Delivery</b>
├ 🔒 <b>Secure Payment</b>
└ 🏆 <b>24/7 Support</b>

📦 <b>Select a product below:</b>""",
        "lucky_spin_message": """🎰 <b>LUCKY SPIN</b>
━━━━━━━━━━━━━━━━━━

🎡 <b>Spin the wheel for rewards!</b>

🎁 <b>Possible Prizes:</b>
├ 💰 Free balance
├ 🎟️ Discount coupon
└ 😅 Better luck tomorrow

⏰ <b>1 free spin per day!</b>

━━━━━━━━━━━━━━━━━━""",
        "lucky_spin_used_message": "🎰 <b>LUCKY SPIN</b>\n\nআজকের Spin আপনি already ব্যবহার করেছেন.\n\n⏰ <b>Next Spin: Tomorrow</b>",
        "lucky_spin_win_message": "🎰 <b>SPIN RESULT</b>\n━━━━━━━━━━━━━━━━━━\n\n🎉🎉🎉\n\n💰 <b>YOU WON ৳{prize} BDT!</b>\n\n৳{prize} BDT has been added to your wallet balance!\nUse it on your next purchase!\n\n🎉🎉🎉\n\n━━━━━━━━━━━━━━━━━━\n🕐 Next spin available: <b>Tomorrow</b>",
        "lucky_spin_lose_message": "🎰 <b>SPIN RESULT</b>\n━━━━━━━━━━━━━━━━━━\n\n😅 <b>No Prize This Time!</b>\n\nDon't worry! Try again tomorrow for another chance to win!\n\n━━━━━━━━━━━━━━━━━━\n🕐 Next spin available: <b>Tomorrow</b>",
        "profile_message": """👤 ━ <b>YOUR PROFILE</b> ━ 👤
━━━━━━━━━━━━━━━━━━

🆔 <b>Account Information</b>

├ 🆔 User ID: <code>{user_id}</code>
└ 👤 Name: {name}

💰 <b>Balance Details</b>

└ 💵 Current: <b>৳{balance:.2f}</b>

📊 <b>Statistics</b>

├ 📦 Total Orders: {total_orders}
├ 💸 Total Spent: ৳{spent:.2f}
├ 💵 Total Deposited: ৳{deposited:.2f}
├ 🎁 Referral Earned: ৳{referral_earned:.2f}
└ 👥 Total Referrals: {total_referrals}

━━━━━━━━━━━━━━━━━━""",
        "my_orders_empty_message": """╭━━━━━━━━━━━━━━━━━━━━━━╮
      📦 <b>MY ORDERS</b>
╰━━━━━━━━━━━━━━━━━━━━━━╯

🛍️ <b>No orders yet</b>

আপনার কেনা Product এখানে সুন্দরভাবে দেখাবে।""",
        "howto": """📖 HOW TO USE

Product কিনতে SHOP NOW থেকে Product নির্বাচন করুন।
তারপর BUY NOW চাপুন, Payment করুন এবং SEND PROOF থেকে
Transaction ID, Screenshot ও Payment Number পাঠিয়ে Proof Submit করুন।""",
        "official_channel": "https://t.me/",
        "support_telegram": "https://t.me/",
        "support_whatsapp": "https://wa.me/",
        "owner_link": "https://t.me/",
        "payment_extra": """💸 টাকা Send করার পর SEND PROOF বাটনে ক্লিক করুন।
যে নম্বর থেকে টাকা পাঠিয়েছেন এবং Payment Screenshot দিন।
⏱️ Admin ৫ মিনিটের মধ্যে Payment check করে Accept/Reject করবে।""",
        "payment_bkash": BKASH,
        "payment_nagad": NAGAD,
        "bkash_qr": "",
        "nagad_qr": "",
        "referral_reward": str(REF_REWARD),
        "referral_reward_low": str(REF_REWARD_LOW),
        "referral_reward_high": str(REF_REWARD_HIGH),
        "referral_threshold": str(REF_THRESHOLD),
        "balance_add_message": """🎉 <b>WALLET BALANCE ADDED</b>\n\n✅ আপনার Wallet-এ <b>৳{amount} TK</b> যোগ করা হয়েছে।\n💳 <b>Current Balance: ৳{balance} TK</b>\n\n👤 User: {name}\n🆔 User ID: {user_id}""",
        "balance_remove_message": """⚠️ <b>WALLET BALANCE REMOVED</b>\n\n💸 আপনার Wallet থেকে <b>৳{amount} TK</b> কমানো হয়েছে।\n💳 <b>Current Balance: ৳{balance} TK</b>\n\n👤 User: {name}\n🆔 User ID: {user_id}""",
        "referral_join_message": """🎉 <b>NEW REFERRAL JOINED</b>\n\n👤 Name: {name}\n🔗 Username: @{username}\n🆔 User ID: {user_id}\n\nআপনার Referral Link থেকে নতুন User Account খুলেছে।""",
        "order_accept_message": """✅ <b>ORDER #{order_id} ACCEPTED</b>\n\n📦 <b>{product}</b>\n💰 Price: <b>৳{price} TK</b>\n\n📥 আপনার Product নিচে দেওয়া হচ্ছে।""",
        "order_reject_message": """❌ <b>ORDER #{order_id} REJECTED</b>\n\n📦 {product}\n\nআপনার Payment Proof সঠিক কিনা যাচাই করুন এবং প্রয়োজন হলে আবার চেষ্টা করুন。""",
        "ban_notification_enabled": "1",
        "ban_notification_message": """🚫 <b>ACCOUNT BANNED</b>\n\n⚠️ তোমাকে Admin ব্যান করেছে।\n\n📌 <b>কারণ:</b> {reason}\n\n🔓 আনব্যান হতে চাইলে নিচের <b>CONTACT ADMIN</b> বাটনে Admin-এর সাথে যোগাযোগ করো।""",
        "ban_contact_link": "https://t.me/",
        "ban_contact_button": "📞 CONTACT ADMIN",
        "admin_link": "https://t.me/",
    }
    for k, v in defaults.items():
        con.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))

    con.execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)", (ADMIN_ID,))
    # Freeze the current delivery content for legacy orders that predate the snapshot columns.
    # Future product edits will never change an order's saved delivery.
    try:
        con.execute("""
            UPDATE orders
            SET delivery_type_snapshot = COALESCE(NULLIF(delivery_type_snapshot,''), (SELECT delivery_type FROM products WHERE products.id=orders.product_id)),
                delivery_data_snapshot = COALESCE(NULLIF(delivery_data_snapshot,''), (SELECT delivery_data FROM products WHERE products.id=orders.product_id))
            WHERE status='COMPLETED' AND (delivery_type_snapshot='' OR delivery_data_snapshot='')
        """)
    except sqlite3.OperationalError:
        pass
    con.commit()
    con.close()


def get_setting(key):
    con = db()
    row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    con.close()
    return row["value"] if row else ""


def set_setting(key, value):
    con = db()
    con.execute(
        "INSERT INTO settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value)
    )
    con.commit()
    con.close()


def format_setting_message(key, **values):
    text = get_setting(key)
    try:
        return text.format(**values)
    except Exception:
        return text


def payment_number(method):
    key = "payment_bkash" if method == "bkash" else "payment_nagad"
    return get_setting(key) or (BKASH if method == "bkash" else NAGAD)


def bd_now():
    # Bangladesh local time (UTC+6), independent of server timezone.
    return datetime.utcnow() + timedelta(hours=6)


def calculate_expiry(validity, base=None):
    """Calculate a customer expiry date from product validity.
    Supports values such as 1 DAY, 7 DAYS, 1 MONTH, 3 MONTH, 1 YEAR.
    Returns an ISO datetime string or empty string when validity is unavailable.
    """
    raw = str(validity or "").strip().upper()
    if not raw:
        return ""
    import re
    m = re.search(r"(\d+(?:\.\d+)?)\s*(MINUTE|MINUTES|HOUR|HOURS|DAY|DAYS|WEEK|WEEKS|MONTH|MONTHS|YEAR|YEARS)", raw)
    if not m:
        return ""
    amount = float(m.group(1))
    unit = m.group(2)
    dt = base or bd_now()
    if unit.startswith("MINUTE"):
        from datetime import timedelta
        dt = dt + timedelta(minutes=amount)
    elif unit.startswith("HOUR"):
        from datetime import timedelta
        dt = dt + timedelta(hours=amount)
    elif unit.startswith("DAY"):
        from datetime import timedelta
        dt = dt + timedelta(days=amount)
    elif unit.startswith("WEEK"):
        from datetime import timedelta
        dt = dt + timedelta(weeks=amount)
    elif unit.startswith("YEAR"):
        years = int(amount)
        months_extra = round((amount - years) * 12)
        month_index = dt.month - 1 + years * 12 + months_extra
        year = dt.year + month_index // 12
        month = month_index % 12 + 1
        day = min(dt.day, calendar.monthrange(year, month)[1])
        dt = dt.replace(year=year, month=month, day=day)
    else:
        whole_months = int(amount)
        extra_days = round((amount - whole_months) * 30)
        month_index = dt.month - 1 + whole_months
        year = dt.year + month_index // 12
        month = month_index % 12 + 1
        day = min(dt.day, calendar.monthrange(year, month)[1])
        dt = dt.replace(year=year, month=month, day=day)
        if extra_days:
            from datetime import timedelta
            dt = dt + timedelta(days=extra_days)
    return dt.isoformat(timespec="seconds")


def format_expiry(expiry_at):
    if not expiry_at:
        return ""
    try:
        return datetime.fromisoformat(expiry_at).strftime("%-d %B %Y, %-I:%M %p")
    except Exception:
        return str(expiry_at)


def referral_reward():
    """Legacy/default referral reward helper kept for compatibility."""
    try:
        return float(get_setting("referral_reward") or REF_REWARD)
    except (TypeError, ValueError):
        return REF_REWARD


def _setting_float(key, default):
    try:
        return float(get_setting(key) or default)
    except (TypeError, ValueError):
        return float(default)


def referral_reward_for_price(price):
    """Default: ৳100 or less => ৳2, above ৳100 => ৳5."""
    threshold = _setting_float("referral_threshold", REF_THRESHOLD)
    low = _setting_float("referral_reward_low", REF_REWARD_LOW)
    high = _setting_float("referral_reward_high", REF_REWARD_HIGH)
    return high if float(price or 0) > threshold else low


def is_admin(user_id):
    con = db()
    ok = con.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,)).fetchone()
    con.close()
    return bool(ok)


def ensure_user(user_id, name, username=None, phone=None, ref_by=None):
    con = db()
    row = con.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        if ref_by == user_id:
            ref_by = None
        con.execute(
            """INSERT INTO users
               (id,name,username,phone,ref_by,verified,joined_at)
               VALUES(?,?,?,?,?,?,?)""",
            (user_id, name, username, phone, ref_by, 1 if phone else 0, datetime.now().isoformat())
        )
    else:
        con.execute(
            "UPDATE users SET name=?, username=?, phone=COALESCE(?,phone) WHERE id=?",
            (name, username, phone, user_id)
        )
    con.commit()
    con.close()


def user_banned(user_id):
    con = db()
    row = con.execute("SELECT banned FROM users WHERE id=?", (user_id,)).fetchone()
    con.close()
    return bool(row and row["banned"])


# =========================================================
# APK STOCK HELPERS
# =========================================================
def apk_stock_count(plan_id):
    con = db()
    n = con.execute("SELECT COUNT(*) n FROM apk_stock WHERE plan_id=? AND status='AVAILABLE' AND active=1", (plan_id,)).fetchone()["n"]
    con.close()
    return int(n or 0)


def sync_apk_plan_stock(con, plan_id):
    n = con.execute("SELECT COUNT(*) n FROM apk_stock WHERE plan_id=? AND status='AVAILABLE' AND active=1", (plan_id,)).fetchone()["n"]
    con.execute("UPDATE apk_plans SET stock_status=? WHERE id=?", (1 if n else 0, plan_id))
    return int(n or 0)


def claim_apk_stock(order_id, user_id, plan_id):
    """Atomically claim exactly one unused APK password for an order."""
    con = db()
    try:
        con.execute("BEGIN IMMEDIATE")
        existing = con.execute("SELECT apk_stock_id, delivery_password FROM orders WHERE id=?", (order_id,)).fetchone()
        if existing and existing["apk_stock_id"]:
            con.commit()
            return existing["apk_stock_id"], existing["delivery_password"]
        stock = con.execute(
            "SELECT id,password FROM apk_stock WHERE plan_id=? AND status='AVAILABLE' AND active=1 ORDER BY id LIMIT 1",
            (plan_id,)
        ).fetchone()
        if not stock:
            con.rollback()
            return None, None
        now = datetime.now().isoformat()
        changed = con.execute(
            "UPDATE apk_stock SET status='SOLD', sold_order_id=?, sold_user_id=?, sold_at=? WHERE id=? AND status='AVAILABLE'",
            (order_id, user_id, now, stock["id"])
        ).rowcount
        if changed != 1:
            con.rollback()
            return None, None
        con.execute("UPDATE orders SET apk_stock_id=?, delivery_password=? WHERE id=?", (stock["id"], stock["password"], order_id))
        sync_apk_plan_stock(con, plan_id)
        con.commit()
        return stock["id"], stock["password"]
    except Exception:
        con.rollback()
        logging.exception("APK stock claim failed")
        return None, None
    finally:
        con.close()


async def ensure_apk_stock_available(user_id, plan_id):
    if apk_stock_count(plan_id) <= 0:
        try:
            await bot.send_message(user_id, "❌ <b>STOCK OUT</b>\n\nএই Plan-এর কোনো Password এখন available নেই।\nঅন্য একটি Plan নির্বাচন করুন।", parse_mode="HTML")
        except Exception:
            pass
        return False
    return True


# =========================================================
# KEYBOARDS
# =========================================================
def btn(text, data):
    try:
        custom = get_setting("button_label:" + str(data)) or get_setting("button_label:" + str(data) + ":" + str(text))
        if custom:
            text = custom
    except Exception:
        pass
    return InlineKeyboardButton(text=text, callback_data=data)


def url_btn(text, url):
    try:
        custom = get_setting("button_label:url:" + str(text))
        if custom:
            text = custom
    except Exception:
        pass
    return InlineKeyboardButton(text=text, url=url)


def back(data="home"):
    return InlineKeyboardMarkup(
        inline_keyboard=[[btn("◀️ BACK", data)]]
    )


def home_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("🛍️ SHOP NOW", "shop")],
        [btn("👤 PROFILE", "profile"), btn("💳 DEPOSIT", "add_balance")],
        [btn("🎁 REFER", "refer"), btn("📦 MY ORDER", "my_products")],
        [btn("🎰 LUCKY SPIN", "lucky_spin")],
        [btn("🔔 ALL UPDATE", "channel")],
        [btn("🆘 SUPPORT", "support"), btn("📖 TUTORIAL", "howto")]
    ])


def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("📊 DASHBOARD", "adm_stats")],
        [btn("👥 USER MANAGEMENT", "adm_users"), btn("📦 PRODUCT MANAGEMENT", "adm_products")],
        [btn("🛒 ORDER MANAGEMENT", "adm_orders"), btn("💳 PAYMENT SETTINGS", "payment_settings")],
        [btn("🎁 REFERRAL SETTINGS", "adm_ref")],
        [btn("💬 SUPPORT SETTINGS", "adm_support")],
        [btn("🔔 ALL UPDATE", "set_channel"), btn("📺 TUTORIAL SETTINGS", "adm_howto")],
        [btn("📝 MESSAGE & BUTTON EDITOR", "adm_text_editor")],
        [btn("📣 BROADCAST", "adm_broadcast"), btn("👨‍💼 ADMIN MANAGEMENT", "adm_admins")],
        [btn("⚙️ GENERAL SETTINGS", "adm_settings")],
        [btn("🏠 MAIN MENU", "home")]
    ])


def user_management_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("👥 ALL USERS", "users_all"), btn("🔎 SEARCH USER", "users_search")],
        [btn("🚫 BAN USER", "users_ban"), btn("🔓 UNBAN USER", "users_unban")],
        [btn("📄 USER FILE", "users_file")],
        [btn("💰 BALANCE / TRANSFER", "users_balance")],
        [btn("📦 USER ORDERS", "users_orders"), btn("✉️ MESSAGE USER", "users_message")],
        [btn("📊 USER STATS", "users_stats")],
        [btn("◀️ BACK", "admin_home")]
    ])


def product_management_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("➕ ADD PRODUCT", "product_add"), btn("📋 ALL PRODUCTS", "product_all")],
        [btn("✏️ EDIT PRODUCT", "product_edit"), btn("🗑️ DELETE PRODUCT", "product_delete")],
        [btn("📦 DELIVERY / STOCK", "product_delivery")],
        [btn("◀️ BACK", "admin_home")]
    ])


def order_management_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("⏳ PENDING ORDERS", "orders_pending")],
        [btn("✅ COMPLETED ORDERS", "orders_completed")],
        [btn("❌ REJECTED ORDERS", "orders_rejected")],
        [btn("📋 ALL ORDERS", "orders_all")],
        [btn("◀️ BACK", "admin_home")]
    ])


def settings_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("🔔 ALL UPDATE", "set_channel"), btn("💳 PAYMENT SETTINGS", "payment_settings")],
        [btn("👤 ADMIN LINK", "set_admin_link"), btn("🚫 BAN SETTINGS", "ban_settings")],
        [btn("💬 SUPPORT SETTINGS", "adm_support")],
        [btn("📖 HOW TO USE", "adm_howto")],
        [btn("◀️ BACK", "admin_home")]
    ])


def support_settings_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("✈️ TELEGRAM SUPPORT", "set_support_telegram"), btn("🟢 WHATSAPP SUPPORT", "set_support_whatsapp")],
        [btn("📥 TRICK INBOX", "trick_inbox")],
        [btn("◀️ BACK", "admin_home")]
    ])


# =========================================================
# ADD PRODUCT TYPE
# =========================================================
def add_product_type_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("📦 FILE / VIDEO / OTHER", "product_type:standard")],
        [btn("📱 APK PRODUCT", "product_type:apk")],
        [btn("◀️ BACK", "adm_products")]
    ])


# =========================================================
# STATES
# =========================================================
class S(StatesGroup):
    phone = State()
    support = State()
    screenshot = State()
    pay_number = State()
    deposit_pay_number = State()
    deposit_screenshot = State()

    add_type = State()
    add_name = State()
    add_price = State()
    add_validity = State()
    add_device_limit = State()
    add_description = State()
    add_features = State()
    add_demo = State()
    add_delivery = State()
    apk_url = State()
    apk_demo = State()
    apk_plan_count = State()
    apk_plan_validity = State()
    apk_plan_price = State()
    apk_plan_device = State()
    apk_plan_stock_count = State()
    apk_plan_password = State()

    search_user = State()
    ban_user = State()
    ban_reason = State()
    ban_contact = State()
    unban_user = State()
    delete_user = State()
    message_user = State()

    edit_product_id = State()
    edit_price = State()
    edit_demo_id = State()
    edit_delivery_id = State()
    edit_delivery = State()
    plan_price = State()
    plan_validity = State()
    plan_password = State()
    plan_device = State()
    change_apk_link = State()
    add_plan_validity = State()
    add_plan_price = State()
    add_plan_device = State()
    add_plan_stock_count = State()
    add_plan_password = State()
    add_existing_stock_count = State()
    add_existing_stock_password = State()
    remove_stock = State()

    wallet_user = State()
    wallet_amount = State()
    wallet_message = State()
    money_user = State()
    money_amount = State()

    setting_key = State()
    setting_value = State()
    support_telegram = State()
    support_whatsapp = State()
    admin_link = State()
    howto_video = State()
    howto_link = State()
    payment_bkash = State()
    payment_nagad = State()
    payment_bkash_qr = State()
    payment_nagad_qr = State()
    referral_reward = State()
    referral_low_reward = State()
    referral_high_reward = State()
    referral_threshold = State()
    trick_reply = State()

    broadcast = State()
    add_admin = State()
    remove_admin = State()
    add_balance_amount = State()
    editor_button_key = State()
    editor_button_value = State()
    editor_message_key = State()
    editor_message_value = State()
    broadcast_post = State()
    broadcast_button_count = State()
    broadcast_button_name = State()
    broadcast_button_url = State()


# =========================================================
# USER START / VERIFICATION
# =========================================================
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()

    ref_by = None
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) == 2 and parts[1].isdigit():
        ref_by = int(parts[1])

    con = db()
    user = con.execute(
        "SELECT * FROM users WHERE id=?", (message.from_user.id,)
    ).fetchone()
    con.close()

    if not user:
        await state.update_data(ref_by=ref_by)
        kb = ReplyKeyboardMarkup(
            keyboard=[[
                KeyboardButton(
                    text="📱 SHARE PHONE NUMBER",
                    request_contact=True
                )
            ]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer(format_setting_message("verification_message"), reply_markup=kb, parse_mode="HTML")
        await state.set_state(S.phone)
        return

    if user_banned(message.from_user.id):
        await message.answer("🚫 আপনার Account বর্তমানে Banned।")
        return

    await message.answer(format_setting_message("welcome", name=message.from_user.full_name), reply_markup=home_kb())


@dp.message(S.phone, F.contact)
async def phone_received(message: Message, state: FSMContext):
    data = await state.get_data()
    ref_by = data.get("ref_by")

    ensure_user(
        message.from_user.id,
        message.from_user.full_name,
        message.from_user.username,
        message.contact.phone_number,
        ref_by
    )
    if ref_by and ref_by != message.from_user.id:
        try:
            notice = format_setting_message(
                "referral_join_message",
                name=message.from_user.full_name,
                username=message.from_user.username or "N/A",
                user_id=message.from_user.id
            )
            await bot.send_message(ref_by, notice, parse_mode="HTML")
        except Exception:
            pass
    await state.clear()
    # Remove the one-time phone-share keyboard permanently after verification.
    await message.answer(
        "✅ Account Verification Successful!",
        reply_markup=ReplyKeyboardRemove()
    )
    await message.answer(format_setting_message("welcome", name=message.from_user.full_name), reply_markup=home_kb())


# =========================================================
# HOME
# =========================================================
@dp.callback_query(F.data == "home")
async def cb_home(q: CallbackQuery, state: FSMContext):
    await state.clear()
    await q.message.edit_text(format_setting_message("welcome", name=q.from_user.full_name), reply_markup=home_kb())
    await q.answer()


# =========================================================
# ADD BALANCE
# =========================================================
def add_balance_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("💵 ৳50 BDT", "add_amount:50"), btn("💵 ৳100 BDT", "add_amount:100")],
        [btn("💵 ৳200 BDT", "add_amount:200"), btn("💵 ৳300 BDT", "add_amount:300")],
        [btn("💵 ৳400 BDT", "add_amount:400"), btn("💵 ৳500 BDT", "add_amount:500")],
        [btn("✏️ CUSTOM AMOUNT", "add_custom_amount")],
        [btn("◀️ BACK", "home")],
    ])

@dp.callback_query(F.data == "add_balance")
async def add_balance_menu(q: CallbackQuery, state: FSMContext):
    await state.clear()
    con=db(); row=con.execute("SELECT balance FROM users WHERE id=?",(q.from_user.id,)).fetchone(); con.close()
    balance=float(row["balance"] or 0) if row else 0
    await q.message.edit_text(format_setting_message("deposit_message"), reply_markup=add_balance_kb(), parse_mode="HTML")
    await q.answer()

@dp.callback_query(F.data.startswith("add_amount:"))
async def add_balance_preset(q: CallbackQuery, state: FSMContext):
    try: amount=float(q.data.split(":",1)[1])
    except (ValueError,IndexError): await q.answer("Invalid amount.",show_alert=True); return
    await state.clear(); await q.answer()
    await show_deposit_payment_method(q,amount)

@dp.callback_query(F.data == "add_custom_amount")
async def add_balance_custom(q: CallbackQuery, state: FSMContext):
    await state.set_state(S.add_balance_amount)
    await q.message.edit_text("💳 <b>CUSTOM AMOUNT</b>\n\nEnter the amount you would like to add to your wallet.\n<i>Currency: BDT (৳)</i>\n\nExample: <code>250</code>",reply_markup=back("add_balance"),parse_mode="HTML")
    await q.answer()

async def show_deposit_payment_method(q: CallbackQuery, amount: float):
    await q.message.edit_text("💳 <b>SELECT PAYMENT METHOD</b>\n\n" f"💰 Amount: <b>৳{amount:g}</b>\n\nChoose where you want to send the payment:",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("🇧🇩 BKASH",f"deposit_method:bkash:{amount:g}"),btn("🇧🇩 NAGAD",f"deposit_method:nagad:{amount:g}")],[btn("◀️ BACK","add_balance")]]),parse_mode="HTML")

@dp.callback_query(F.data.startswith("deposit_method:"))
async def deposit_method(q: CallbackQuery, state: FSMContext):
    _,method,amount=q.data.split(":",2); amount=float(amount); number=payment_number(method); label="BKASH" if method=="bkash" else "NAGAD"
    await state.update_data(deposit_amount=amount,deposit_method=method)
    await q.message.edit_text(f"💳 <b>MANUAL {label} DEPOSIT</b>\n\n💰 <b>Amount:</b> ৳{amount:g}\n📱 <b>{label} NUMBER:</b> <code>{html.escape(str(number))}</code>\n\nটাকা Send করার পর নিচের বাটনে চাপুন এবং Sender Number ও Screenshot দিন।",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("📤 SEND PROOF","deposit_send_proof")],[btn("◀️ BACK","add_balance")]]),parse_mode="HTML")
    await q.answer()

@dp.callback_query(F.data == "deposit_send_proof")
async def deposit_send_proof(q: CallbackQuery,state:FSMContext):
    data=await state.get_data()
    if not data.get("deposit_amount"): await q.answer("Deposit request পাওয়া যায়নি।",show_alert=True); return
    await state.set_state(S.deposit_pay_number)
    await q.message.edit_text("📸 <b>PAYMENT PROOF</b>\n\nযে নম্বর থেকে টাকা পাঠিয়েছেন সেটি লিখুন।\n\nউদাহরণ: <code>017xxxxxxxx</code>",reply_markup=back("add_balance"),parse_mode="HTML"); await q.answer()

@dp.message(S.add_balance_amount)
async def add_balance_amount(message: Message,state:FSMContext):
    try: amount=float((message.text or "").strip().replace(",",""))
    except ValueError: await message.answer("❌ Invalid amount. Enter a number, for example: <code>250</code> BDT.",parse_mode="HTML"); return
    if amount<=0: await message.answer("❌ Amount must be greater than 0."); return
    await state.clear(); await message.answer("💳 <b>SELECT PAYMENT METHOD</b>",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("🇧🇩 BKASH",f"deposit_method:bkash:{amount:g}"),btn("🇧🇩 NAGAD",f"deposit_method:nagad:{amount:g}")],[btn("◀️ BACK","add_balance")]]),parse_mode="HTML")

@dp.message(S.deposit_pay_number)
async def receive_deposit_pay_number(message: Message,state:FSMContext):
    number=(message.text or "").strip()
    if not number: await message.answer("❌ Payment number দিন."); return
    await state.update_data(deposit_pay_number=number); await state.set_state(S.deposit_screenshot); await message.answer("📸 এখন Payment Screenshot পাঠান।",reply_markup=back("add_balance"))

@dp.message(S.deposit_screenshot,F.photo)
async def receive_deposit_screenshot(message: Message,state:FSMContext):
    data=await state.get_data(); amount=float(data.get("deposit_amount") or 0); method=data.get("deposit_method",""); pay_number=data.get("deposit_pay_number","")
    if amount<=0: await state.clear(); await message.answer("❌ Deposit request পাওয়া যায়নি।",reply_markup=back("home")); return
    con=db(); cur=con.execute("INSERT INTO balance_deposits(user_id,amount,payment_method,pay_number,screenshot_id,status,created_at) VALUES(?,?,?,?,?,?,?)",(message.from_user.id,amount,method,pay_number,message.photo[-1].file_id,"PENDING",datetime.now().isoformat())); did=cur.lastrowid; user=con.execute("SELECT * FROM users WHERE id=?",(message.from_user.id,)).fetchone(); con.commit(); con.close(); await state.clear()
    await message.answer("✅ <b>DEPOSIT PROOF SUBMITTED</b>\n\nAdmin আপনার Payment যাচাই করে Accept/Reject করবেন।\n\nWallet balance approval-এর পর যোগ হবে।",reply_markup=back("home"),parse_mode="HTML")
    caption=f"💰 <b>NEW BALANCE DEPOSIT</b>\n━━━━━━━━━━━━━━━━━━\n🆔 Request: <code>#{did}</code>\n👤 User: {html.escape(str(user['name']))}\n🆔 User ID: <code>{user['id']}</code>\n💵 Amount: <b>৳{amount:g}</b>\n💳 Method: <b>{method.upper()}</b>\n📱 Sender: <code>{html.escape(pay_number)}</code>"
    kb=InlineKeyboardMarkup(inline_keyboard=[[btn("✅ ACCEPT",f"accept_deposit:{did}"),btn("❌ REJECT",f"reject_deposit:{did}")]])
    try: await bot.send_photo(ADMIN_ID,message.photo[-1].file_id,caption=caption,reply_markup=kb,parse_mode="HTML")
    except Exception: logging.exception("Admin deposit notification failed")

@dp.message(S.deposit_screenshot)
async def invalid_deposit_screenshot(message: Message): await message.answer("❌ Payment Screenshot হিসেবে একটি Photo পাঠান।")

@dp.callback_query(F.data.startswith("accept_deposit:"))
async def accept_deposit(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    did=int(q.data.split(":")[1]); con=db(); row=con.execute("SELECT * FROM balance_deposits WHERE id=?",(did,)).fetchone()
    if not row or row["status"]!="PENDING": con.close(); await q.answer("এই deposit already processed হয়েছে।",show_alert=True); return
    con.execute("UPDATE balance_deposits SET status='COMPLETED',processed_at=? WHERE id=?",(datetime.now().isoformat(),did)); con.execute("UPDATE users SET balance=balance+? WHERE id=?",(row["amount"],row["user_id"])); user=con.execute("SELECT balance FROM users WHERE id=?",(row["user_id"],)).fetchone(); con.commit(); con.close()
    await bot.send_message(row["user_id"],f"🎉 <b>WALLET BALANCE ADDED</b>\n\n✅ ৳{row['amount']:g} TK যোগ হয়েছে।\n💳 <b>Current Balance:</b> ৳{float(user['balance']):g}",parse_mode="HTML",reply_markup=back("home")); await q.answer("Deposit accepted")

@dp.callback_query(F.data.startswith("reject_deposit:"))
async def reject_deposit(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    did=int(q.data.split(":")[1]); con=db(); row=con.execute("SELECT * FROM balance_deposits WHERE id=?",(did,)).fetchone()
    if row and row["status"]=="PENDING": con.execute("UPDATE balance_deposits SET status='REJECTED',processed_at=? WHERE id=?",(datetime.now().isoformat(),did)); con.commit()
    con.close()
    if row: await bot.send_message(row["user_id"],f"❌ <b>DEPOSIT #{did} REJECTED</b>",parse_mode="HTML")
    await q.answer("Deposit rejected")

# =========================================================
# SHOP
# =========================================================
@dp.callback_query(F.data == "shop")
async def cb_shop(q: CallbackQuery):
    con = db()
    products = con.execute(
        "SELECT * FROM products WHERE active=1 ORDER BY id DESC"
    ).fetchall()
    con.close()

    if not products:
        await q.message.edit_text(
            "📦 এখন কোনো Product Available নেই।",
            reply_markup=back()
        )
        await q.answer()
        return

    # Product list deliberately has NO price.
    rows = [[btn(p["name"], f"product:{p['id']}")] for p in products]
    rows.append([btn("◀️ BACK", "home")])
    await q.message.edit_text(
        format_setting_message("shop_message"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML"
    )
    await q.answer()


@dp.callback_query(F.data.startswith("product:"))
async def cb_product(q: CallbackQuery):
    pid = int(q.data.split(":")[1])
    con = db()
    p = con.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    plans = con.execute("SELECT * FROM apk_plans WHERE product_id=? AND active=1 ORDER BY id", (pid,)).fetchall() if p and p["product_type"] == "apk" else []
    con.close()
    if not p or not p["active"]:
        await q.answer("Product পাওয়া যায়নি।", show_alert=True); return

    name = html.escape(str(p["name"] or "PRODUCT"))
    lines = [f"🛒 <b>{name}</b>", ""]

    if p["product_type"] == "apk":
        lines += ["📊 <b>STOCK & PRICING:</b>", "━━━━━━━━━━━━━━━━━━"]
        for plan in plans:
            available = apk_stock_count(plan["id"])
            icon = "✅" if available else "❌"
            stock = "In Stock" if available else "Stock Out"
            lines += [
                f"{icon} <b>{html.escape(str(plan['validity']))}</b>",
                f"├ 📦 Stock: {stock}",
                f"└ 💰 Price: <b>৳{plan['price']:g}</b>",
                ""
            ]
        if not plans:
            lines += ["⚠️ <b>No plan available</b>", ""]
        if p["features"]:
            lines += ["✅ <b>Features</b>"]
            for feat in str(p["features"]).splitlines():
                feat = feat.strip().lstrip("-•")
                if feat: lines.append(f"├ {html.escape(feat.strip())}")
            lines.append("")
        lines += ["━━━━━━━━━━━━━━━━━━", "🎯 <b>SELECT YOUR PLAN:</b>"]
        rows = []
        for plan in plans:
            available = apk_stock_count(plan["id"])
            status = "BUY" if available else "STOCK OUT"
            rows.append([btn(f"🛒 {status} {plan['validity']} — ৳{plan['price']:g}", f"buyplan:{pid}:{plan['id']}")])
        if p["demo_file_id"]:
            rows.append([btn("🎬 DEMO VIDEO", f"demo:{pid}")])
        rows.append([btn("◀️ BACK", "shop")])
    else:
        lines += ["📊 <b>STOCK & PRICING:</b>", "━━━━━━━━━━━━━━━━━━"]
        validity = str(p["validity"] or "")
        icon = "✅" if p["stock_status"] else "⚠️"
        stock = "In Stock" if p["stock_status"] else "Stock Out"
        lines += [f"{icon} <b>{html.escape(validity or 'Product')}</b>", f"├ 📦 Stock: {stock}", f"└ 💰 Price: <b>৳{p['price']:g}</b>", ""]
        if p["features"]:
            lines += ["✅ <b>Features</b>"]
            for feat in str(p["features"]).splitlines():
                feat = feat.strip().lstrip("-•")
                if feat: lines.append(f"├ {html.escape(feat.strip())}")
            lines.append("")
        if p["device_limit"]:
            lines += [f"📱 Device Limit: {html.escape(str(p['device_limit']))}", ""]
        lines += ["━━━━━━━━━━━━━━━━━━"]
        if p["description"]:
            lines += [html.escape(str(p["description"])), ""]
        rows=[]
        if p["demo_file_id"]: rows.append([btn("🎬 DEMO VIDEO", f"demo:{pid}")])
        rows.append([btn("🛒 BUY NOW", f"buy:{pid}")])
        rows.append([btn("◀️ BACK", "shop")])

    text="\n".join(lines)
    markup=InlineKeyboardMarkup(inline_keyboard=rows)
    if q.message.video or q.message.photo or q.message.document or q.message.animation:
        try: await q.message.delete()
        except Exception: pass
        await q.message.answer(text, reply_markup=markup, parse_mode="HTML")
    else:
        await q.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    await q.answer()


@dp.callback_query(F.data.startswith("buyplan:"))
async def cb_buy_plan(q: CallbackQuery):
    _, pid_s, plan_s = q.data.split(":")
    pid, plan_id = int(pid_s), int(plan_s)
    con=db(); p=con.execute("SELECT * FROM products WHERE id=? AND active=1 AND product_type='apk'",(pid,)).fetchone(); plan=con.execute("SELECT * FROM apk_plans WHERE id=? AND product_id=? AND active=1",(plan_id,pid)).fetchone(); con.close()
    if not p or not plan:
        await q.answer("Plan পাওয়া যায়নি।",show_alert=True); return
    if apk_stock_count(plan_id) <= 0:
        await q.answer("❌ এই Plan এখন Stock Out।",show_alert=True); return
    con=db(); wallet=con.execute("SELECT balance FROM users WHERE id=?",(q.from_user.id,)).fetchone(); con.close()
    balance=float(wallet["balance"] or 0) if wallet else 0
    text=("💳 <b>SELECT PAYMENT METHOD</b>\n"
          "━━━━━━━━━━━━━━━━━━\n\n"
          f"🎮 <b>{html.escape(str(p['name']))}</b>\n"
          f"⏱️ <b>Duration:</b> {html.escape(str(plan['validity']))}\n"
          f"💰 <b>Price:</b> <b>{plan['price']:g}৳ Tk</b>\n\n"
          f"💵 <b>Your Balance:</b> ৳{balance:g}\n\n"
          "💰 <b>CHOOSE PAYMENT:</b>")
    rows=[[btn("💰 PAY WITH WALLET BALANCE",f"wallet_buy:{pid}:{plan_id}")]]
    rows.append([btn("🛠️ PAY WITH MANUAL PAYMENT",f"manual_pay:{pid}:{plan_id}")])
    rows.append([btn("◀️ BACK",f"product:{pid}")])
    kb=InlineKeyboardMarkup(inline_keyboard=rows)
    await q.message.edit_text(text,reply_markup=kb,parse_mode="HTML"); await q.answer()


@dp.callback_query(F.data.startswith("demo:"))
async def cb_demo(q: CallbackQuery):
    pid = int(q.data.split(":")[1])
    con = db()
    p = con.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    con.close()

    if not p or not p["demo_file_id"]:
        await q.answer("Demo নেই।", show_alert=True)
        return

    # Demo media gets its own inline buttons directly underneath it.
    # No red emoji is used; Telegram controls the actual button colour/theme.
    demo_kb = InlineKeyboardMarkup(inline_keyboard=[
        [btn("🛒 BUY NOW", f"buy:{pid}")],
        [btn("◀️ BACK", f"product:{pid}")]
    ])

    if p["demo_type"] == "photo":
        await q.message.answer_photo(
            p["demo_file_id"],
            caption=f"DEMO — {p['name']}",
            reply_markup=demo_kb
        )
    elif p["demo_type"] == "video":
        await q.message.answer_video(
            p["demo_file_id"],
            caption=f"DEMO — {p['name']}",
            reply_markup=demo_kb
        )
    await q.answer()


def buy_now_text(product, balance=0):
    price=f"{product['price']:g}"
    validity=str(product['validity'] or '').strip()
    duration_line=f"⏱️ <b>Duration:</b> {html.escape(validity)}\n" if validity else ""
    return ("💳 <b>SELECT PAYMENT METHOD</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"🎮 <b>{html.escape(str(product['name']))}</b>\n"
            f"{duration_line}"
            f"💰 <b>Price:</b> <b>{price}৳ Tk</b>\n\n"
            f"💵 <b>Your Balance:</b> ৳{float(balance):g}\n\n"
            "💰 <b>CHOOSE PAYMENT:</b>")


def payment_method_text(product,method):
    price=f"{product['price']:.2f}"
    number=payment_number(method)
    label="BKASH" if method=="bkash" else "NAGAD"
    return (
        f"💳 <b>PAY WITH {label}</b>\n"
        "<i>MANUAL PAYMENT · ORDER CHECKOUT</i>\n\n"
        f"📦 <b>Product:</b> {html.escape(str(product['name']))}\n"
        f"💰 <b>Total Price:</b> ৳{price}\n\n"
        f"📱 <b>{label} NUMBER</b>\n"
        f"📱 <b>{html.escape(str(number))}</b>\n\n"
        "💸 টাকা Send করুন এই নাম্বারে।\n"
        "তারপর <b>SEND PROOF</b> বাটনে ক্লিক করে\n"
        "যে নম্বর থেকে টাকা পাঠিয়েছেন এবং Payment Screenshot দিন।\n\n"
        "⏱️ <i>Admin ৫ মিনিটের মধ্যে Payment check করে Accept/Reject করবে।</i>"
    )

async def show_payment_method(q,pid,method,plan_id=None):
    con=db(); p=con.execute("SELECT * FROM products WHERE id=?",(pid,)).fetchone(); plan=None
    if p and p["product_type"] == "apk" and plan_id:
        plan=con.execute("SELECT * FROM apk_plans WHERE id=? AND product_id=? AND active=1",(plan_id,pid)).fetchone()
    con.close()
    if not p:
        await q.answer("Product পাওয়া যায়নি।",show_alert=True); return
    if p["product_type"] == "apk" and not plan:
        await q.answer("Plan পাওয়া যায়নি।",show_alert=True); return

    if plan:
        price=f"{plan['price']:.2f}"; number=payment_number(method); label="BKASH" if method=="bkash" else "NAGAD"
        text=(f"💳 <b>✦ PAY WITH {label} ✦</b>\n━━━━━━━━━━━━━━━━━━\n"
              f"📱 <b>{html.escape(str(p['name']))}</b>\n"
              f"⏳ Plan: <b>{html.escape(str(plan['validity']))}</b>\n"
              f"💰 <b>PRICE: ৳{price}</b>\n\n"
              f"📱 <b>{label} NUMBER</b>\n<b>{html.escape(str(number))}</b>\n\n"
              "💸 টাকা Send করুন এই নাম্বারে।\nতারপর <b>SEND PROOF</b> বাটনে ক্লিক করে\nযে নম্বর থেকে টাকা পাঠিয়েছেন এবং Payment Screenshot দিন.")
        proof_cb=f"proof:{pid}:{method}:{plan_id}"
        back_cb=f"buyplan:{pid}:{plan_id}"
    else:
        text=payment_method_text(p,method)
        proof_cb=f"proof:{pid}:{method}"
        back_cb=f"buy:{pid}"

    qr=get_setting("bkash_qr" if method=="bkash" else "nagad_qr")
    # If QR exists, show QR first; then payment number/instructions below it.
    if qr:
        try:
            await q.message.delete()
        except Exception:
            pass
        try:
            await bot.send_photo(q.from_user.id, qr, caption=(f"{method.upper()} QR — {p['name']}"), parse_mode="HTML")
        except Exception:
            pass
        await bot.send_message(q.from_user.id,text,reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("📤 SEND PROOF",proof_cb)],[btn("◀️ BACK",back_cb)]]),parse_mode="HTML")
    else:
        await q.message.edit_text(text,reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("📤 SEND PROOF",proof_cb)],[btn("◀️ BACK",back_cb)]]),parse_mode="HTML")
    await q.answer()


@dp.callback_query(F.data.startswith("buy:"))
async def cb_buy(q):
    pid=int(q.data.split(":")[1])
    con=db(); p=con.execute("SELECT * FROM products WHERE id=? AND active=1",(pid,)).fetchone(); con.close()
    if not p:
        await q.answer("Product পাওয়া যায়নি।",show_alert=True); return
    if p["product_type"] == "apk":
        await cb_product(q); return
    rows=[[btn("💰 PAY WITH WALLET BALANCE", f"wallet_buy:{pid}")]]
    rows.append([btn("🛠️ PAY WITH MANUAL PAYMENT", f"manual_pay:{pid}")])
    rows.append([btn("◀️ BACK",f"product:{pid}")])
    markup=InlineKeyboardMarkup(inline_keyboard=rows)
    con=db(); wallet=con.execute("SELECT balance FROM users WHERE id=?",(q.from_user.id,)).fetchone(); con.close()
    balance=float(wallet["balance"] or 0) if wallet else 0
    text=buy_now_text(p,balance)
    if q.message.video or q.message.photo or q.message.document or q.message.animation:
        try: await q.message.delete()
        except Exception: pass
        await q.message.answer(text,reply_markup=markup,parse_mode="HTML")
    else:
        await q.message.edit_text(text,reply_markup=markup,parse_mode="HTML")
    await q.answer()

@dp.callback_query(F.data.startswith("manual_pay:"))
async def manual_pay_menu(q):
    parts=q.data.split(":"); pid=int(parts[1]); plan_id=int(parts[2]) if len(parts)>2 else None
    con=db(); p=con.execute("SELECT * FROM products WHERE id=? AND active=1",(pid,)).fetchone()
    plan=con.execute("SELECT * FROM apk_plans WHERE id=? AND product_id=? AND active=1",(plan_id,pid)).fetchone() if plan_id else None
    con.close()
    if not p or (plan_id and not plan):
        await q.answer("Product/Plan পাওয়া যায়নি।",show_alert=True); return
    price=plan["price"] if plan else p["price"]
    name=html.escape(str(p["name"]))
    plan_line=f"⏳ <b>Plan: {html.escape(str(plan['validity']))}</b>\n" if plan else ""
    await q.message.edit_text(
        "🛠️ <b>MANUAL PAYMENT</b>\n"
        "<i>PRODUCT PURCHASE · MANUAL CHECKOUT</i>\n\n"
        f"📦 <b>{name}</b>\n{plan_line}"
        f"💰 <b>Total Price: ৳{price:g}</b>\n\n"
        "পেমেন্ট পদ্ধতি নির্বাচন করুন।\n"
        "<i>Select your preferred payment method below.</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [btn("🟣 PAY WITH BKASH",f"pay_bkash:{pid}:{plan_id}" if plan_id else f"pay_bkash:{pid}"),btn("🟠 PAY WITH NAGAD",f"pay_nagad:{pid}:{plan_id}" if plan_id else f"pay_nagad:{pid}")],
            [btn("◀️ BACK",f"buyplan:{pid}:{plan_id}" if plan_id else f"buy:{pid}")]
        ]),parse_mode="HTML")
    await q.answer()


@dp.callback_query(F.data.startswith("pay_bkash:"))
async def cb_pay_bkash(q: CallbackQuery):
    parts=q.data.split(":"); await show_payment_method(q,int(parts[1]),"bkash",int(parts[2]) if len(parts)>2 else None)


@dp.callback_query(F.data.startswith("pay_nagad:"))
async def cb_pay_nagad(q: CallbackQuery):
    parts=q.data.split(":"); await show_payment_method(q,int(parts[1]),"nagad",int(parts[2]) if len(parts)>2 else None)


# =========================================================
# WALLET BUY
# =========================================================
async def deliver_product(user_id, product_row):
    dtype = str((product_row["delivery_type_snapshot"] if "delivery_type_snapshot" in product_row.keys() and product_row["delivery_type_snapshot"] else product_row["delivery_type"]) or "").strip().lower()
    data = product_row["delivery_data_snapshot"] if "delivery_data_snapshot" in product_row.keys() and product_row["delivery_data_snapshot"] else product_row["delivery_data"]

    if not data:
        await bot.send_message(
            user_id,
            "⚠️ Payment accepted হয়েছে, কিন্তু এই Product-এর Delivery Content সেট করা নেই।"
        )
        return False

    # DELIVERY COPY MODE:
    # Admin-এর পাঠানো/forward করা পুরো Telegram message-টাই copy করা হয়।
    # Retry করলে সাময়িক Telegram/API error-এর কারণে product আটকে যাবে না।
    if dtype == "copy" or (dtype not in {"text", "photo", "video", "document"} and str(data).strip().startswith("{")):
        try:
            src = json.loads(data)
            chat_id = int(src["chat_id"])
            message_id = int(src["message_id"])
        except Exception:
            logging.exception("Invalid delivery copy data")
            await bot.send_message(user_id, "⚠️ Product delivery data নষ্ট হয়েছে। Admin-কে জানান।")
            return False

        for attempt in range(3):
            try:
                await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=chat_id,
                    message_id=message_id
                )
                await bot.send_message(user_id, "🏠 <b>BACK TO MENU</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("🏠 BACK TO MENU", "home")]]), parse_mode="HTML")
                return True
            except Exception as e:
                logging.exception("Delivery copy failed (attempt %s/3): %s", attempt + 1, e)
                if attempt < 2:
                    await asyncio.sleep(1)
        await bot.send_message(
            user_id,
            "⚠️ Product delivery সাময়িকভাবে ব্যর্থ হয়েছে।\n\n📦 MY PRODUCTS থেকে আবার GET PRODUCT চাপুন অথবা Admin-কে জানান।"
        )
        return False

    # Backward compatibility for products saved by older versions.
    try:
        if dtype == "text":
            await bot.send_message(user_id, data)
        elif dtype == "photo":
            await bot.send_photo(user_id, data)
        elif dtype == "video":
            await bot.send_video(user_id, data)
        elif dtype == "document":
            await bot.send_document(user_id, data)
        else:
            await bot.send_message(user_id, "⚠️ Product delivery type পাওয়া যায়নি। Admin-কে জানান।")
            return False
        await bot.send_message(user_id, "🏠 <b>BACK TO MENU</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("🏠 BACK TO MENU", "home")]]), parse_mode="HTML")
        return True
    except Exception as e:
        logging.exception("Legacy product delivery failed: %s", e)
        await bot.send_message(user_id, "⚠️ Product delivery করতে সমস্যা হয়েছে। MY PRODUCTS থেকে আবার চেষ্টা করুন।")
        return False


async def notify_user_product_purchase(order):
    """Send a purchase-success notification before delivering non-APK products."""
    product_name = html.escape(str(order["name"] or "Product"))
    amount = float(order["price"] or 0)
    txid = str(order["txid"] or order["id"] or "N/A")
    lines = [
        "✅ <b>Payment Successful!</b>",
        "",
        f"📦 <b>Product:</b> {product_name}",
        f"💰 <b>Amount Paid:</b> ৳{amount:g} BDT",
        f"🧾 <b>Transaction / Order ID:</b> <code>{html.escape(txid)}</code>",
        "",
        "Your purchase is confirmed. Your product is below."
    ]
    await bot.send_message(
        int(order["user_id"]), "\n".join(lines), parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("🏠 BACK TO MENU", "home")]])
    )


async def deliver_apk_order(order, expiry_text=""):
    """Deliver the exact purchased APK password immediately after loading."""
    name = html.escape(str(order["name"] or "APK"))
    validity = html.escape(str(order["plan_validity"] or order["validity"] or "N/A"))
    password = html.escape(str(order["plan_password"] or order["delivery_password"] or "N/A"))
    url = str(order["apk_url"] or "").strip()

    lines = [
        "╔══════════════════════════════╗",
        "       ✅ <b>Payment Successful!</b>",
        "╚══════════════════════════════╝",
        "",
        f"🎮 <b>Product:</b> {name}",
        f"💰 <b>Amount Paid:</b> ৳{float(order['price'] or 0):g} BDT",
        f"🧾 <b>Transaction / Order ID:</b> <code>{html.escape(str(order['txid'] or order['id'] or 'N/A'))}</code>",
        f"⏳ <b>Duration:</b> {validity}",
        "📦 <b>Quantity:</b> 1",
        "",
        f"🔐 <b>APK Password / Key:</b> <code>{password}</code>",
        "",
        f"📢 <b>APK DOWNLOAD LINK:</b> 👉 {html.escape(url) if url else 'Not Set'}",
        "",
        "🙏 Thank you for your purchase!"
    ]
    kb = []
    if url:
        kb.append([InlineKeyboardButton(text="📥 DOWNLOAD APK", url=url)])
    kb.append([btn("🏠 BACK TO MENU", "home")])
    await bot.send_message(
        order["user_id"],
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )


async def pay_referrer_if_needed(order_id):
    con = db()
    order = con.execute(
        "SELECT * FROM orders WHERE id=?", (order_id,)
    ).fetchone()
    if not order or order["referral_paid"]:
        con.close()
        return

    user = con.execute(
        "SELECT ref_by,name,username FROM users WHERE id=?", (order["user_id"],)
    ).fetchone()

    if user and user["ref_by"]:
        reward=referral_reward_for_price(order["price"])
        con.execute("UPDATE users SET balance=balance+? WHERE id=?",(reward,user["ref_by"]))
        con.execute("UPDATE orders SET referral_paid=1 WHERE id=?",(order_id,))
        ref=con.execute("SELECT * FROM users WHERE id=?",(user["ref_by"],)).fetchone()
        new_balance=ref["balance"] if ref else 0
        con.commit()
        if ref:
            try:
                await bot.send_message(ref["id"],
                    "🎉 <b>REFERRAL REWARD</b>\n\n"
                    f"👤 Referred User: <b>{html.escape(str(user['name'] or 'User'))}</b>\n"
                    f"🆔 User ID: <code>{order['user_id']}</code>\n"
                    f"💰 Reward: <b>৳{reward:g}</b>\n\n"
                    f"✅ ৳{reward:g} আপনার Wallet-এ যোগ হয়েছে।\n"
                    f"💳 Current Balance: <b>৳{new_balance:g}</b>",parse_mode="HTML")
            except Exception:
                logging.exception("Referral notification failed")
    con.close()




ANIMATION_NAMES={
    1:"CLASSIC",2:"NEON",3:"PROGRESS",4:"CYBER",5:"MATRIX",
    6:"ROYAL",7:"PULSE",8:"WAVE",9:"SCAN",10:"ORBIT",
    11:"GLITCH",12:"JACKPOT",13:"FIRE",14:"ICE",15:"THUNDER",
    16:"GALAXY",17:"DIAMOND",18:"HACKER",19:"LASER",20:"ULTIMATE",
    21:"TERMINAL",22:"SHIELD",23:"ROCKET",24:"CIRCUIT",25:"PRISM",
    26:"RADAR",27:"ENERGY",28:"VAULT",29:"QUANTUM",30:"APEX"
}

# Three completely separate 30-style animation libraries.  The same number
# intentionally has a different visual sequence in each section.
_PRODUCT_STYLES = [
    lambda i,p,b,e: f"📦  ░▒▓ LOADING PRODUCT ▓▒░\n\n{'📦 '*(1+i%7)}\n\n{e}\n<code>{b}</code> {p}%",
    lambda i,p,b,e: f"⚡  PRODUCT NEON CHARGE\n\n{'🔵➡️ '*((i%4)+2)}\n\n{e}\nPOWER {p}%",
    lambda i,p,b,e: f"🎯  PRODUCT CHECKPOINT\n\n[{'█'*int(p/10)}{'░'*(10-int(p/10))}]\n\n{e}\nCHECK {p}%",
    lambda i,p,b,e: f"🖥️  PRODUCT SYSTEM BOOT\n\n<code>BOOT > CACHE > LOAD > VERIFY</code>\n\n{e}\nSYSTEM {p}%",
    lambda i,p,b,e: f"🟦  PRODUCT DATA MATRIX\n\n<code>{'01 10 11 00 '*3}\n{'10 01 00 11 '*3}</code>\n\n{e}\nDATA {p}%",
    lambda i,p,b,e: f"👑  PREMIUM PRODUCT\n\n👑  💎  📦  💎  👑\n\n{e}\n<code>{b}</code>",
    lambda i,p,b,e: f"💓  PRODUCT PULSE\n\n{'💙 '*(1+i%8)}\n\n{e}\nPULSE {p}%",
    lambda i,p,b,e: f"🌊  PRODUCT WAVE\n\n{'〰️'*((i%10)+3)}\n\n{e}\nFLOW {p}%",
    lambda i,p,b,e: f"🔍  PRODUCT SCANNER\n\n╞{'═'*((i%8)+3)}🔎\n\n{e}\nSCAN {p}%",
    lambda i,p,b,e: f"🌀  PRODUCT ORBIT\n\n      ◯\n   📦  ◉  💎\n      ◯\n\n{e}\nORBIT {p}%",
    lambda i,p,b,e: f"👾  PRODUCT GLITCH\n\n▓▒░ P R O D U C T ░▒▓\n\n{e}\nERR 0x{(i*17+3)%999:03d}",
    lambda i,p,b,e: f"💥  PRODUCT JACKPOT\n\n🎁 💎 📦 🏆 ⭐ 💰\n\n{e}\n<code>{b}</code> {p}%",
    lambda i,p,b,e: f"🔥  PRODUCT FIRE\n\n{'🔥'*(2+i%7)} ➜ 📦 ➜ 🚀\n\n{e}\nHEAT {p}%",
    lambda i,p,b,e: f"❄️  PRODUCT ICE\n\n❄️ 💠 🧊 💠 ❄️\n\n{e}\nCOOL {p}%",
    lambda i,p,b,e: f"⚡  PRODUCT THUNDER\n\n⚡〰️⚡〰️⚡〰️⚡\n\n{e}\nENERGY {p}%",
    lambda i,p,b,e: f"🌌  PRODUCT GALAXY\n\n🌟 ✦ 📦 ✦ 🪐 ✦ 🌟\n\n{e}\nSPACE {p}%",
    lambda i,p,b,e: f"💎  PRODUCT DIAMOND\n\n◇ ◆ ◇ 📦 ◇ ◆ ◇\n\n{e}\nQUALITY {p}%",
    lambda i,p,b,e: f"💻  PRODUCT HACKER\n\n<code>> FINDING ITEM\n> VERIFYING ITEM\n> READY</code>\n\n{e}",
    lambda i,p,b,e: f"🔴  PRODUCT LASER LOCK\n\n{'━'*((i%9)+2)}🔴📦\n\n{e}\nLOCK {p}%",
    lambda i,p,b,e: f"🏆  PRODUCT ULTIMATE\n\n👑 💎 📦 ⚡ 🚀 🏆\n\n{e}\n<code>{b}</code> {p}%",
    lambda i,p,b,e: f"⌨️  PRODUCT TERMINAL\n\n<code>> load_product()\n> status: RUNNING\n> step: {p}%</code>\n\n{e}",
    lambda i,p,b,e: f"🛡️  PRODUCT SHIELD\n\n╔══ 🛡️ 📦 🛡️ ══╗\n╚══════════════╝\n\n{e}\nSECURE {p}%",
    lambda i,p,b,e: f"🚀  PRODUCT ROCKET\n\n   🚀\n  📦💨\n 🚀💨💨\n\n{e}\nLIFT {p}%",
    lambda i,p,b,e: f"🔌  PRODUCT CIRCUIT\n\n⚡━━━🔵━━━📦━━━🔵━━━⚡\n\n{e}\nCIRCUIT {p}%",
    lambda i,p,b,e: f"🌈  PRODUCT PRISM\n\n🔷 ➜ 💎 ➜ 📦 ➜ 💎 ➜ 🔷\n\n{e}\nREFRACT {p}%",
    lambda i,p,b,e: f"📡  PRODUCT RADAR\n\n      ◉\n   ╱  📦  ╲\n  ╱{'━'*((i%6)+2)}╲\n\n{e}\nRADAR {p}%",
    lambda i,p,b,e: f"🔋  PRODUCT ENERGY\n\n🔋 {'▰'*int(p/10)}{'▱'*(10-int(p/10))}\n\n{e}\nCHARGE {p}%",
    lambda i,p,b,e: f"🔐  PRODUCT VAULT\n\n╭────🔐────╮\n│   📦💎   │\n╰──────────╯\n\n{e}\nVAULT {p}%",
    lambda i,p,b,e: f"⚛️  PRODUCT QUANTUM\n\n⚛️  ◇  📦  ◇  ⚛️\n\n{e}\nQUANTUM {p}%",
    lambda i,p,b,e: f"🏁  PRODUCT APEX\n\n🏁 ━━━ 📦 ━━━ 🏁\n\n{e}\nAPEX {p}%",
]

_PAYMENT_STYLES = [
    lambda i,p,b,e: f"💳  ░▒▓ PAYMENT START ▓▒░\n\n{'💳 '*(1+i%7)}\n\n{e}\n<code>{b}</code> {p}%",
    lambda i,p,b,e: f"⚡  PAYMENT NEON FLOW\n\n{'💜➡️ '*((i%4)+2)}\n\n{e}\nPOWER {p}%",
    lambda i,p,b,e: f"🎯  AMOUNT VALIDATION\n\n[{'█'*int(p/10)}{'░'*(10-int(p/10))}]\n\n{e}\nVALIDATE {p}%",
    lambda i,p,b,e: f"🖥️  GATEWAY BOOT\n\n<code>CONNECT > AUTH > TOKEN > LINK</code>\n\n{e}\nGATEWAY {p}%",
    lambda i,p,b,e: f"🟪  PAYMENT MATRIX\n\n<code>11 00 10 01 11\n01 10 11 00 01</code>\n\n{e}\nENCRYPT {p}%",
    lambda i,p,b,e: f"👑  PREMIUM PAYMENT\n\n👑  💳  🔐  💳  👑\n\n{e}\n<code>{b}</code>",
    lambda i,p,b,e: f"💓  PAYMENT HEARTBEAT\n\n{'💜 '*(1+i%8)}\n\n{e}\nHEARTBEAT {p}%",
    lambda i,p,b,e: f"🌊  PAYMENT SYNC\n\n{'〰️'*((i%10)+3)}\n\n{e}\nSYNC {p}%",
    lambda i,p,b,e: f"🔍  PAYMENT SCAN\n\n╞{'═'*((i%8)+3)}🔎\n\n{e}\nSCAN {p}%",
    lambda i,p,b,e: f"🌀  GATEWAY ORBIT\n\n      ◯\n   💳  ◉  🔐\n      ◯\n\n{e}\nORBIT {p}%",
    lambda i,p,b,e: f"👾  PAYMENT GLITCH\n\n▓▒░ G A T E W A Y ░▒▓\n\n{e}\nTOKEN 0x{(i*23+9)%999:03d}",
    lambda i,p,b,e: f"💥  PAYMENT LINK BOOST\n\n💳 🔗 💰 ⚡ 🔐 ⭐\n\n{e}\n<code>{b}</code> {p}%",
    lambda i,p,b,e: f"🔥  PAYMENT FIREWALL\n\n🔥 🔥 ➜ 💳 ➜ 🔐 ➜ 🔗\n\n{e}\nFIREWALL {p}%",
    lambda i,p,b,e: f"❄️  PAYMENT ICE LOCK\n\n❄️ 💠 🔐 💠 ❄️\n\n{e}\nLOCK {p}%",
    lambda i,p,b,e: f"⚡  PAYMENT THUNDER\n\n⚡〰️💳〰️⚡〰️🔗\n\n{e}\nENERGY {p}%",
    lambda i,p,b,e: f"🌌  PAYMENT GALAXY\n\n🌟 ✦ 💳 ✦ 🔗 ✦ 🌟\n\n{e}\nSPACE {p}%",
    lambda i,p,b,e: f"💎  PAYMENT DIAMOND\n\n◇ ◆ 💳 🔐 💳 ◆ ◇\n\n{e}\nQUALITY {p}%",
    lambda i,p,b,e: f"💻  PAYMENT TERMINAL\n\n<code>> AUTH PAYMENT\n> VERIFY AMOUNT\n> CREATE LINK</code>\n\n{e}",
    lambda i,p,b,e: f"🔴  PAYMENT LASER\n\n{'━'*((i%9)+2)}🔴🔗\n\n{e}\nTARGET {p}%",
    lambda i,p,b,e: f"🏆  PAYMENT ULTIMATE\n\n👑 💳 🔐 ⚡ 🔗 🏆\n\n{e}\n<code>{b}</code> {p}%",
    lambda i,p,b,e: f"⌨️  PAYMENT COMMAND\n\n<code>> create_payment()\n> status: PROCESSING\n> step: {p}%</code>\n\n{e}",
    lambda i,p,b,e: f"🛡️  PAYMENT SHIELD\n\n╔══ 🛡️ 💳 🛡️ ══╗\n╚══════════════╝\n\n{e}\nSECURE {p}%",
    lambda i,p,b,e: f"🚀  PAYMENT LAUNCH\n\n   🚀\n  💳💨\n 🔗💨💨\n\n{e}\nLAUNCH {p}%",
    lambda i,p,b,e: f"🔌  PAYMENT CIRCUIT\n\n⚡━━━💳━━━🔗━━━🔐━━━⚡\n\n{e}\nCIRCUIT {p}%",
    lambda i,p,b,e: f"🌈  PAYMENT PRISM\n\n🔷 ➜ 💳 ➜ 🔗 ➜ 💎 ➜ 🔷\n\n{e}\nREFRACT {p}%",
    lambda i,p,b,e: f"📡  PAYMENT RADAR\n\n      ◉\n   ╱  💳  ╲\n  ╱{'━'*((i%6)+2)}╲\n\n{e}\nRADAR {p}%",
    lambda i,p,b,e: f"🔋  PAYMENT ENERGY\n\n🔋 {'▰'*int(p/10)}{'▱'*(10-int(p/10))}\n\n{e}\nCHARGE {p}%",
    lambda i,p,b,e: f"🔐  PAYMENT VAULT\n\n╭────🔐────╮\n│  💳🔗   │\n╰──────────╯\n\n{e}\nVAULT {p}%",
    lambda i,p,b,e: f"⚛️  PAYMENT QUANTUM\n\n⚛️  ◇  💳  ◇  🔗  ◇\n\n{e}\nQUANTUM {p}%",
    lambda i,p,b,e: f"🏁  PAYMENT APEX\n\n🏁 ━━━ 💳 ━━━ 🔗 ━━━ 🏁\n\n{e}\nAPEX {p}%",
]

_DELIVERY_STYLES = [
    lambda i,p,b,e: f"🚚  ░▒▓ DELIVERY START ▓▒░\n\n{'🚚 '*(1+i%7)}\n\n{e}\n<code>{b}</code> {p}%",
    lambda i,p,b,e: f"⚡  DELIVERY NEON RUSH\n\n{'🚚💨 '*((i%4)+2)}\n\n{e}\nSPEED {p}%",
    lambda i,p,b,e: f"🎯  DELIVERY CHECKPOINT\n\n[{'█'*int(p/10)}{'░'*(10-int(p/10))}]\n\n{e}\nCHECK {p}%",
    lambda i,p,b,e: f"🖥️  DELIVERY SYSTEM\n\n<code>PACK > VERIFY > ROUTE > SEND</code>\n\n{e}\nSYSTEM {p}%",
    lambda i,p,b,e: f"🟩  DELIVERY MATRIX\n\n<code>10 11 00 01 10\n11 00 01 10 11</code>\n\n{e}\nROUTE {p}%",
    lambda i,p,b,e: f"👑  PREMIUM DELIVERY\n\n👑  📦  🚚  🔐  👑\n\n{e}\n<code>{b}</code>",
    lambda i,p,b,e: f"💓  DELIVERY PULSE\n\n{'🚚 '*(1+i%8)}\n\n{e}\nPULSE {p}%",
    lambda i,p,b,e: f"🌊  DELIVERY FLOW\n\n{'〰️🚚'*((i%6)+2)}\n\n{e}\nFLOW {p}%",
    lambda i,p,b,e: f"🔍  DELIVERY SCANNER\n\n╞{'═'*((i%8)+3)}📦\n\n{e}\nSCAN {p}%",
    lambda i,p,b,e: f"🌀  DELIVERY ORBIT\n\n      ◯\n   📦  ◉  🚚\n      ◯\n\n{e}\nORBIT {p}%",
    lambda i,p,b,e: f"👾  DELIVERY GLITCH\n\n▓▒░ D E L I V E R Y ░▒▓\n\n{e}\nROUTE 0x{(i*31+7)%999:03d}",
    lambda i,p,b,e: f"💥  DELIVERY BOOST\n\n📦 🚚 ⚡ 🚀 🏆 ⭐\n\n{e}\n<code>{b}</code> {p}%",
    lambda i,p,b,e: f"🔥  DELIVERY TURBO\n\n🔥 ➜ 📦 ➜ 🚚 ➜ 🚀\n\n{e}\nTURBO {p}%",
    lambda i,p,b,e: f"❄️  DELIVERY COOL\n\n❄️ 📦 🧊 🚚 ❄️\n\n{e}\nCOOL {p}%",
    lambda i,p,b,e: f"⚡  DELIVERY THUNDER\n\n⚡〰️📦〰️🚚〰️⚡\n\n{e}\nENERGY {p}%",
    lambda i,p,b,e: f"🌌  DELIVERY GALAXY\n\n🌟 ✦ 📦 ✦ 🚚 ✦ 🌟\n\n{e}\nSPACE {p}%",
    lambda i,p,b,e: f"💎  DELIVERY DIAMOND\n\n◇ ◆ 📦 🚚 📦 ◆ ◇\n\n{e}\nQUALITY {p}%",
    lambda i,p,b,e: f"💻  DELIVERY TERMINAL\n\n<code>> PACK ITEM\n> VERIFY ITEM\n> RELEASE ITEM</code>\n\n{e}",
    lambda i,p,b,e: f"🔴  DELIVERY LASER ROUTE\n\n{'━'*((i%9)+2)}🔴🚚\n\n{e}\nROUTE {p}%",
    lambda i,p,b,e: f"🏆  DELIVERY ULTIMATE\n\n👑 📦 🚚 ⚡ 🚀 🏆\n\n{e}\n<code>{b}</code> {p}%",
    lambda i,p,b,e: f"⌨️  DELIVERY COMMAND\n\n<code>> dispatch_product()\n> status: MOVING\n> step: {p}%</code>\n\n{e}",
    lambda i,p,b,e: f"🛡️  DELIVERY SHIELD\n\n╔══ 🛡️ 📦 🛡️ ══╗\n╚══════════════╝\n\n{e}\nSAFE {p}%",
    lambda i,p,b,e: f"🚀  DELIVERY LAUNCH\n\n   🚀\n  📦💨\n 🚚💨💨\n\n{e}\nLAUNCH {p}%",
    lambda i,p,b,e: f"🔌  DELIVERY CIRCUIT\n\n⚡━━━📦━━━🚚━━━🔐━━━⚡\n\n{e}\nCIRCUIT {p}%",
    lambda i,p,b,e: f"🌈  DELIVERY PRISM\n\n🔷 ➜ 📦 ➜ 🚚 ➜ 💎 ➜ 🔷\n\n{e}\nREFRACT {p}%",
    lambda i,p,b,e: f"📡  DELIVERY RADAR\n\n      ◉\n   ╱  🚚  ╲\n  ╱{'━'*((i%6)+2)}╲\n\n{e}\nRADAR {p}%",
    lambda i,p,b,e: f"🔋  DELIVERY ENERGY\n\n🔋 {'▰'*int(p/10)}{'▱'*(10-int(p/10))}\n\n{e}\nCHARGE {p}%",
    lambda i,p,b,e: f"🔐  DELIVERY VAULT\n\n╭────🔐────╮\n│  📦🚚   │\n╰──────────╯\n\n{e}\nVAULT {p}%",
    lambda i,p,b,e: f"⚛️  DELIVERY QUANTUM\n\n⚛️  ◇  📦  ◇  🚚  ◇\n\n{e}\nQUANTUM {p}%",
    lambda i,p,b,e: f"🏁  DELIVERY APEX\n\n🏁 ━━━ 📦 ━━━ 🚚 ━━━ 🏁\n\n{e}\nAPEX {p}%",
]

_preview_tasks = {}

def _preview_key(msg):
    return (msg.chat.id, msg.message_id)

async def _stop_preview(msg):
    task = _preview_tasks.get(_preview_key(msg))
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    _preview_tasks.pop(_preview_key(msg), None)

async def _preview_runner(msg, kind, design, duration, reply_markup):
    key=_preview_key(msg)
    try:
        await run_process_animation(msg,kind,design,duration,reply_markup)
    except asyncio.CancelledError:
        raise
    finally:
        if _preview_tasks.get(key) is asyncio.current_task():
            _preview_tasks.pop(key,None)

# Each section has its own 30-style visual library.
def animation_frame(kind, design, i):
    d=max(1,min(30,int(design or 1)))
    frame_total = 8 if kind == "payment" else 12 if kind == "delivery" else 18
    pct=min(100,int((i+1)*100/frame_total))
    filled=min(10,int(pct/10))
    bars='▰'*filled+'▱'*(10-filled)
    titles={"product":"📦 PRODUCT LOADING","payment":"🔗 PAYMENT LINK CREATE","delivery":"🚚 PRODUCT DELIVERY"}
    extras={
        "product":["📦 Preparing product...","⚡ Loading product data...","🎯 Checking product...","🖥️ Initializing product system...","🟦 Reading product data...","👑 Preparing premium item...","💓 Product engine running...","🌊 Loading product flow...","🔍 Scanning product...","🌀 Building product session...","👾 Processing secure data...","💥 Preparing your item...","🔥 Warming up product...","❄️ Cooling product cache...","⚡ Charging product engine...","🌌 Syncing product universe...","💎 Polishing premium product...","💻 Verifying secure data...","🔴 Locking product route...","🏆 Final premium preparation...","⌨️ Product command running...","🛡️ Protecting product...","🚀 Launching product load...","🔌 Connecting product nodes...","🌈 Refracting product data...","📡 Tracking product state...","🔋 Charging product engine...","🔐 Opening product vault...","⚛️ Quantum product sync...","🏁 Final product checkpoint..."],
        "payment":["💳 Preparing payment...","⚡ Connecting payment flow...","🎯 Validating amount...","🖥️ Starting secure gateway...","🟪 Encrypting payment data...","👑 Premium payment channel...","💓 Payment heartbeat...","🌊 Syncing payment...","🔍 Checking payment request...","🌀 Creating payment session...","👾 Securing transaction...","💥 Building payment link...","🔥 Activating payment channel...","❄️ Securing payment cache...","⚡ Charging gateway...","🌌 Syncing gateway nodes...","💎 Protecting payment data...","💻 Verifying gateway...","🔴 Locking payment route...","🏆 Finalizing payment link...","⌨️ Payment command running...","🛡️ Shielding transaction...","🚀 Launching payment request...","🔌 Connecting gateway circuit...","🌈 Refracting payment data...","📡 Tracking payment state...","🔋 Charging payment session...","🔐 Opening payment vault...","⚛️ Quantum payment sync...","🏁 Final payment checkpoint..."],
        "delivery":["📦 Preparing delivery...","⚡ Fast delivery engine...","🎯 Confirming delivery...","🖥️ Starting delivery system...","🟩 Packing delivery data...","👑 Premium delivery queue...","💓 Delivery heartbeat...","🌊 Sending through secure flow...","🔍 Checking delivery package...","🌀 Creating delivery session...","👾 Securing delivery data...","💥 Releasing product...","🔥 Fast-track delivery...","❄️ Cooling delivery cache...","⚡ Turbo delivery...","🌌 Routing delivery nodes...","💎 Protecting delivered item...","💻 Final security check...","🔴 Locking delivery route...","🏆 Final delivery preparation...","⌨️ Delivery command running...","🛡️ Shielding delivered item...","🚀 Launching delivery...","🔌 Connecting delivery nodes...","🌈 Refracting delivery data...","📡 Tracking delivery route...","🔋 Charging delivery engine...","🔐 Opening delivery vault...","⚛️ Quantum delivery sync...","🏁 Final delivery checkpoint..."]
    }
    if kind == "payment":
        return (
            "💳 <b>GENERATING PAYMENT LINK</b>\n\n"
            "We are retrieving your secure payment link from the gateway.\n\n"
            f"<code>{bars}</code>  <b>{pct}%</b>\n\n"
            "🔐 <i>Please wait while we prepare your payment...</i>"
        )
    extra=extras[kind][d-1]
    fn={"product":_PRODUCT_STYLES,"payment":_PAYMENT_STYLES,"delivery":_DELIVERY_STYLES}[kind][d-1]
    body=fn(i,pct,bars,extra)
    return f"{titles[kind]}\n\n{body}\n\n⏳ <b>PROCESSING...</b>"

async def run_process_animation(msg, kind, design, duration=6.5, reply_markup=None):
    # Keep Telegram edits low enough to avoid FloodWait, and NEVER let an
    # animation edit error block the actual payment/product delivery.
    frames = 8 if duration <= 4 else 12
    delay = max(0.25, duration / frames)
    for i in range(frames):
        try:
            await msg.edit_text(
                animation_frame(kind, design, i),
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
        except Exception as e:
            # A temporary Telegram edit/FloodWait error must not stop the flow.
            logging.warning("%s animation frame %s failed: %s", kind, i + 1, e)
        if i < frames - 1:
            await asyncio.sleep(delay)

    # Always attempt the final 100% frame before returning.
    try:
        await msg.edit_text(
            animation_frame(kind, design, frames - 1),
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        # Give Telegram a short moment to render the confirmed 100% frame
        # before the caller starts the actual product delivery.
        if duration <= 5:
            await asyncio.sleep(0.35)
    except Exception as e:
        logging.warning("%s animation final frame failed: %s", kind, e)
    return msg

async def send_process_animation(user_id, kind, design=None, duration=6.5):
    # Product-loading animation is intentionally disabled as requested.
    # Payment-link and delivery animations remain enabled; lucky-spin animation is separate.
    if kind == "product":
        return None
    # Fixed animation designs; admin settings cannot change these.
    d = "2" if kind == "delivery" else "3"
    try:
        msg=await bot.send_message(user_id,animation_frame(kind,d,0),parse_mode="HTML")
    except Exception as e:
        # If the animation message itself cannot be sent, payment/delivery
        # must still continue normally.
        logging.warning("%s animation message send failed: %s", kind, e)
        return None
    try:
        await run_process_animation(msg,kind,d,duration)
    except Exception as e:
        logging.warning("%s animation failed: %s", kind, e)
    return msg

async def delivery_loading(user_id):
    # Payment complete -> 3.5 sec delivery animation -> auto delivery.
    return await send_process_animation(user_id,"delivery",None,4.5)

# =========================================================
# PAYMENT PROOF
# =========================================================
@dp.callback_query(F.data.startswith("proof:"))
async def cb_proof(q: CallbackQuery, state: FSMContext):
    parts=q.data.split(":")
    pid=int(parts[1]); method=parts[2] if len(parts)>2 else ""; plan_id=int(parts[3]) if len(parts)>3 and parts[3] else None
    await state.update_data(product_id=pid, payment_method=method, plan_id=plan_id)
    await state.set_state(S.pay_number)
    await q.message.edit_text(
        "📸 <b>PAYMENT PROOF</b>\n━━━━━━━━━━━━━━━━━━\n\n📦 Product-এর জন্য যে নম্বর থেকে টাকা পাঠিয়েছেন সেটি লিখুন।\n\nউদাহরণ: <code>017xxxxxxxx</code>",
        reply_markup=back(f"product:{pid}"), parse_mode="HTML"
    )
    await q.answer()


@dp.message(S.pay_number)
async def receive_pay_number(message: Message, state: FSMContext):
    number = (message.text or "").strip()
    if not number:
        await message.answer("❌ Payment number দিন।")
        return
    await state.update_data(pay_number=number)
    await state.set_state(S.screenshot)
    await message.answer("📸 এখন Payment Screenshot পাঠান।", reply_markup=back("home"))


@dp.message(S.screenshot, F.photo)
async def receive_screenshot(message: Message, state: FSMContext):
    data = await state.get_data()
    pid = data["product_id"]
    con = db()
    p = con.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    plan = con.execute("SELECT * FROM apk_plans WHERE id=? AND product_id=? AND active=1", (data.get("plan_id"), pid)).fetchone() if data.get("plan_id") else None
    if not p or not p["active"] or (p["product_type"] == "standard" and not p["stock_status"]) or (p["product_type"] == "apk" and (not plan or apk_stock_count(plan["id"]) <= 0)):
        con.close(); await state.clear(); await message.answer("❌ Product বর্তমানে Out of Stock।", reply_markup=back("home")); return
    cur = con.execute(
        """INSERT INTO orders (user_id,product_id,price,status,screenshot_id,pay_number,payment_method,expiry_at,plan_id,created_at,delivery_type_snapshot,delivery_data_snapshot) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (message.from_user.id, pid, (plan["price"] if plan else p["price"]), "PENDING", message.photo[-1].file_id, data["pay_number"], data.get("payment_method",""), "", data.get("plan_id"), datetime.now().isoformat(), p["delivery_type"] or "", p["delivery_data"] or "")
    )
    oid = cur.lastrowid; con.commit(); con.close(); await state.clear()
    await message.answer(
        "✅ <b>PAYMENT PROOF SUBMITTED</b>\n"
        "আপনার পেমেন্ট প্রুফ অ্যাডমিনের কাছে পাঠানো হয়েছে।\n\n"
        "⏳ Admin আপনার পেমেন্ট যাচাই করবেন।\n"
        "<i>Your product will be delivered after approval.</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("🏠 BACK TO MENU", "home")]]), parse_mode="HTML"
    )
    # Send proof immediately to admin; no extra SEND ADMIN step.
    con = db()
    order = con.execute("SELECT o.*,p.name FROM orders o JOIN products p ON p.id=o.product_id WHERE o.id=?", (oid,)).fetchone()
    user = con.execute("SELECT * FROM users WHERE id=?", (message.from_user.id,)).fetchone(); con.close()
    proof_lines = [
        "💳 <b>✦ NEW PAYMENT PROOF ✦</b>",
        "━━━━━━━━━━━━━━━━━━",
        f"🆔 <b>Request:</b> <code>#{oid}</code>",
        "",
        f"👤 <b>User:</b> {html.escape(str(user['name']))}",
        f"🆔 <b>User ID:</b> <code>{user['id']}</code>",
        "",
        f"📦 <b>Product:</b> {html.escape(str(order['name']))}",
    ]
    if plan:
        proof_lines.append(f"⏳ <b>Plan:</b> {html.escape(str(plan['validity']))}")
    proof_lines += [
        f"💰 <b>Amount:</b> ৳{order['price']:.2f}",
        f"📱 <b>Sender Number:</b> <code>{html.escape(str(order['pay_number'] or 'N/A'))}</code>",
        f"💳 <b>Method:</b> {html.escape(str((order['payment_method'] or 'PAYMENT').upper()))}",
        f"⏱ <b>Time:</b> {datetime.now().strftime('%d-%m-%Y %I:%M %p')}",
        "━━━━━━━━━━━━━━━━━━",
        "",
        "👇 Payment যাচাই করে Accept অথবা Reject করুন।",
    ]
    text = "\n".join(proof_lines)
    kb = InlineKeyboardMarkup(inline_keyboard=[[btn("✅ ACCEPT", f"accept_order:{oid}"), btn("❌ REJECT", f"reject_order:{oid}")]])
    try: await bot.send_photo(ADMIN_ID, order["screenshot_id"], caption=text, reply_markup=kb, parse_mode="HTML")
    except Exception: logging.exception("Admin proof notification failed")


@dp.message(S.screenshot)
async def invalid_screenshot(message: Message):
    await message.answer("❌ Payment Screenshot হিসেবে একটি Photo পাঠান।")



@dp.callback_query(F.data.startswith("accept_order:"))
async def cb_accept_order(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    oid = int(q.data.split(":")[1])
    con=db()
    order=con.execute("""SELECT o.*,p.name,p.validity,p.device_limit,p.delivery_type,p.delivery_data,p.product_type,p.apk_url,p.demo_file_id,
                               ap.validity plan_validity,ap.device_limit plan_device_limit,ap.password plan_password,ap.price plan_price
                               FROM orders o JOIN products p ON p.id=o.product_id
                               LEFT JOIN apk_plans ap ON ap.id=o.plan_id
                               WHERE o.id=?""",(oid,)).fetchone()
    con.close()
    if not order:
        await q.answer("Order পাওয়া যায়নি।",show_alert=True); return
    if order["status"] != "PENDING":
        await q.answer("এই Order already processed হয়েছে।",show_alert=True); return

    expiry_validity=order["plan_validity"] if order["product_type"]=="apk" else order["validity"]
    expiry_at=calculate_expiry(expiry_validity,bd_now())

    # APK orders must claim one real unused password before completion.
    if order["product_type"]=="apk":
        stock_id,password=await asyncio.to_thread(claim_apk_stock,oid,order["user_id"],order["plan_id"])
        if not stock_id:
            await q.answer("❌ এই Plan এখন Stock Out। Order Accept করা যাবে না।",show_alert=True)
            return
        con=db(); con.execute("UPDATE orders SET status='COMPLETED',expiry_at=? WHERE id=? AND status='PENDING'",(expiry_at,oid)); con.commit(); con.close()
        # Refresh order so delivery uses the exact claimed password.
        con=db(); order=con.execute("""SELECT o.*,p.name,p.validity,p.device_limit,p.delivery_type,p.delivery_data,p.product_type,p.apk_url,p.demo_file_id,
                                          ap.validity plan_validity,ap.device_limit plan_device_limit,ap.price plan_price,COALESCE(o.delivery_password, ap.password) plan_password
                                          FROM orders o JOIN products p ON p.id=o.product_id LEFT JOIN apk_plans ap ON ap.id=o.plan_id WHERE o.id=?""",(oid,)).fetchone(); con.close()
    else:
        con=db(); con.execute("UPDATE orders SET status='COMPLETED',expiry_at=? WHERE id=? AND status='PENDING'",(expiry_at,oid)); con.commit(); con.close()

    await pay_referrer_if_needed(oid)
    await notify_admin_purchase(oid, order["payment_method"] or "Manual Payment")
    expiry_text=format_expiry(expiry_at)

    # Keep the user on the loading screen for 3 seconds.
    # Then delete it first and immediately send the purchased product.
    loading=await delivery_loading(order["user_id"])
    try:
        await loading.delete()
    except Exception:
        logging.exception("Loading message delete failed")

    delivery_ok=True
    try:
        if order["product_type"]=="apk":
            await deliver_apk_order(order,expiry_text)
        else:
            await notify_user_product_purchase(order)
            delivery_ok=await deliver_product(order["user_id"],order)
    except Exception:
        logging.exception("Final product delivery failed")
        delivery_ok=False

    if not delivery_ok:
        await bot.send_message(
            order["user_id"],
            "⚠️ <b>Payment Successful</b>, কিন্তু Product Delivery করতে সমস্যা হয়েছে।\n\n📦 নিচের বাটন থেকে আবার চেষ্টা করুন।",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [btn("📦 GET PRODUCT AGAIN",f"redeliver:{oid}")],
                [btn("◀️ BACK", "home")]
            ])
        )
    await q.message.edit_text(f"✅ ORDER #{oid} ACCEPTED",reply_markup=back("adm_orders")); await q.answer()


@dp.callback_query(F.data.startswith("reject_order:"))
async def cb_reject_order(q: CallbackQuery):
    if not is_admin(q.from_user.id):
        return

    oid = int(q.data.split(":")[1])
    con = db()
    order = con.execute(
        "SELECT user_id FROM orders WHERE id=?", (oid,)
    ).fetchone()
    if order and order["status"] == "PENDING":
        con.execute(
            "UPDATE orders SET status='REJECTED' WHERE id=?", (oid,)
        )
        con.commit()
    con.close()

    if order:
        con2=db(); prow=con2.execute("SELECT name FROM products WHERE id=(SELECT product_id FROM orders WHERE id=?)",(oid,)).fetchone(); con2.close()
        notice=format_setting_message("order_reject_message",order_id=oid,product=(prow["name"] if prow else "Product"))
        await bot.send_message(order["user_id"],notice,parse_mode="HTML",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("🔙 BACK TO MENU","home")]]))
    await q.message.edit_text(f"❌ ORDER #{oid} REJECTED",reply_markup=back("adm_orders"))
    await q.answer()


@dp.callback_query(F.data == "support")
async def user_support(q: CallbackQuery):
    kb=[[url_btn("TELEGRAM SUPPORT",get_setting("support_telegram")), url_btn("WHATSAPP SUPPORT",get_setting("support_whatsapp"))], [btn("🎯 TRICK SEND","new_trick")], [btn("◀️ BACK","home")]]
    text=format_setting_message("support")
    await q.message.edit_text(text,reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),parse_mode="HTML")
    await q.answer()

@dp.callback_query(F.data == "new_trick")
async def new_trick(q: CallbackQuery,state:FSMContext):
    await state.set_state(S.support)
    await q.message.edit_text(format_setting_message("trick_message"),reply_markup=back("support"),parse_mode="HTML")
    await q.answer()

@dp.message(S.support)
async def save_support_message(message: Message,state:FSMContext):
    text=message.text or message.caption or ""
    con=db(); con.execute("INSERT INTO support_messages(user_id,name,username,chat_id,message_id,message_text,status,created_at) VALUES(?,?,?,?,?,?,?,?)",(message.from_user.id,message.from_user.full_name,message.from_user.username or "",message.chat.id,message.message_id,text,"NEW",datetime.now().isoformat())); con.commit(); con.close()
    try:
        await bot.send_message(ADMIN_ID, "🎯 <b>NEW TRICK / SUPPORT TICKET</b>\n━━━━━━━━━━━━━━━━━━\n👤 <b>User:</b> " + html.escape(message.from_user.full_name) + "\n🆔 <b>User ID:</b> <code>" + str(message.from_user.id) + "</code>\n🔗 <b>Username:</b> @" + html.escape(message.from_user.username or "N/A") + "\n\n📩 <b>Message:</b>\n" + html.escape(text or "📎 Media/Attachment"), parse_mode="HTML")
        await bot.copy_message(ADMIN_ID,message.chat.id,message.message_id)
    except Exception: pass
    await state.clear()
    await message.answer("✅ Your support ticket has been sent to Admin.",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("🏠 MAIN MENU","home")]]))

@dp.callback_query(F.data == "refer")
async def user_refer(q: CallbackQuery):
    me=await bot.get_me(); link=f"https://t.me/{me.username}?start={q.from_user.id}"
    con=db(); u=con.execute("SELECT balance FROM users WHERE id=?",(q.from_user.id,)).fetchone(); count=con.execute("SELECT COUNT(*) n FROM users WHERE ref_by=?",(q.from_user.id,)).fetchone()["n"]; con.close()
    text=format_setting_message("referral", referral_link=html.escape(link), referrals=count, balance=f"{float(u['balance'] if u else 0):g}")
    share_url="https://t.me/share/url?url=" + urllib.parse.quote(link, safe="") + "&text=" + urllib.parse.quote("Join SABBIR XYZ SHOP using my referral link!", safe="")
    share_text=get_setting("button_label:share_referral") or "🎁 SHARE REFERRAL LINK"
    await q.message.edit_text(text,reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=share_text,url=share_url)],[btn("◀️ BACK","home")]]),parse_mode="HTML"); await q.answer()

@dp.callback_query(F.data == "howto")
async def user_howto(q: CallbackQuery):
    text = ("📺 <b>━ VIDEO TUTORIALS ━</b> 📺\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "🎬 <b>Learn How To Use Our Products</b>\n\n"
            "├ 📱 <b>Step-by-step guides</b>\n"
            "├ 🎮 <b>Game setup tutorials</b>\n"
            "├ ⚙️ <b>Installation help</b>\n"
            "└ 💡 <b>Tips & tricks</b>\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "👆 <b>Click the button below:</b>")
    link=get_setting("howto_link"); video=get_setting("howto_video_id")
    rows=[]
    if link: rows.append([url_btn("▶️ HOW TO PURCHASE",link)])
    elif video: rows.append([btn("▶️ HOW TO PURCHASE","howto_play_video")])
    rows.append([btn("◀️ BACK TO MAIN MENU","home")])
    await q.message.edit_text(text,reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),parse_mode="HTML"); await q.answer()

@dp.callback_query(F.data == "howto_play_video")
async def howto_play_video(q: CallbackQuery):
    video=get_setting("howto_video_id")
    if not video:
        await q.answer("Tutorial video has not been added yet.",show_alert=True); return
    await q.message.answer_video(video,caption="📺 HOW TO PURCHASE",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("◀️ BACK TO TUTORIALS","howto")],[btn("⌂ BACK TO MAIN MENU","home")]]))
    await q.answer()

@dp.callback_query(F.data == "channel")
async def user_channel(q: CallbackQuery):
    url=get_setting("official_channel")
    if not url or url=="https://t.me/": await q.answer("All Update link এখনো সেট করা হয়নি।",show_alert=True); return
    await q.message.edit_text("🔔 <b>ALL UPDATE</b>\n\nআমাদের All Update Channel-এ Join করুন।",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[url_btn("🔔 JOIN ALL UPDATE",url)],[btn("◀️ BACK","home")]]),parse_mode="HTML"); await q.answer()

LUCKY_DESIGNS={
    1:"CLASSIC EMOJI",2:"R + S NEON",3:"PROGRESS",4:"NEON RING",5:"JACKPOT MATRIX",6:"ROYAL CASCADE",
    7:"CYBER WHEEL",8:"NEON SLOT",9:"GALAXY ROLL",10:"FIRE & ICE",11:"DIAMOND RUSH",12:"MONEY RAIN",
    13:"CROWN VAULT",14:"RAINBOW FLIP",15:"MEGA JACKPOT"
}

async def run_lucky_animation(msg, design="8", duration=5, reply_markup=None):
    d=8; frames=20; delay=duration/frames
    for i in range(frames):
        if d==1:
            symbols=list("🎰🎁💎💰🏆🍀⭐🔥⚡🎯")
            text="\n".join(" ".join(random.choice(symbols) for _ in range(w)) for w in (6,8,10,12,12,10,8,6))
            title="🎰 <b>LUCKY SPIN</b>"
        elif d==2:
            palette=["🔴","🟢","🔵","🟡","🟣","🟠","🩷","🩵","🟤","⚫","⚪","🩶"]
            widths=(4,5,6,7,6,5,4); rows=[]
            for w in widths:
                rows.append("  "*(7-w)+"    ".join(f"{random.choice(palette)}R + {random.choice(palette)}S" for _ in range(w)))
            text="\n".join(rows); title="⚡ <b>R + S NEON</b>"
        elif d==3:
            pct=min(100, int((i+1)*100/frames)); filled=int(pct/10); text=f"🎁   💎   💰   🎉   🏆   🍀\n\n<code>{'▰'*filled+'▱'*(10-filled)}</code>  {pct}%"; title="🎰 <b>PROGRESS SPIN</b>"
        elif d==4:
            rings=["◉","◎","◌","○"]; icons=["💎","⚡","🔥","🎯","💰","👑"]; text=f"             {rings[i%4]}\n\n       {'  '.join(icons[(i+j)%6] for j in range(6))}\n\n             {rings[i%4]}"; title="💠 <b>NEON RING</b>"
        elif d==5:
            syms=["💎","💰","7️⃣","🔥","👑","🎁","⭐","🍀"]; text="\n".join("      "+"  ".join(syms[(i+r*2+c*3)%len(syms)] for c in range(5)) for r in range(5)); title="👑 <b>JACKPOT MATRIX</b>"
        elif d==6:
            pct=min(100,int((i+1)*100/frames)); bar='▰'*int(pct/10)+'▱'*(10-int(pct/10)); title="👑 <b>ROYAL CASCADE</b>"; text=f"        👑  💎  🏆  💰\n\n        <code>{bar}</code>\n\n              {pct}%"
        elif d==7:
            wheel=["◐","◓","◑","◒"]; text=f"           {wheel[i%4]}\n\n     🟦  🟪  🟩  🟨  🟥\n     🟨  💎  🎁  💰  🟦\n     🟥  🏆  7️⃣  🍀  🟩"; title="🌀 <b>CYBER WHEEL</b>"
        elif d==8:
            slots=["7️⃣","💎","🍀","💰","🔥","⭐"]; a=i%6; text=f"<code>▰  {slots[a]}  ▰  {slots[(a+1)%6]}  ▰  {slots[(a+2)%6]}  ▰</code>"; title="🎰 <b>NEON SLOT</b>"
        elif d==9:
            stars=["🌌","✨","🌟","💫","☄️"]; text="\n".join("     "+"  ".join(stars[(i+j+r)%5] for j in range(5)) for r in range(5)); title="🌌 <b>GALAXY ROLL</b>"
        elif d==10:
            text=f"🔥  🔥  🔥  🔥  🔥\n\n        {['❄️','🔥','❄️','🔥'][i%4]}  <b>VS</b>  {['🔥','❄️','🔥','❄️'][i%4]}\n\n❄️  ❄️  ❄️  ❄️  ❄️"; title="🔥❄️ <b>FIRE & ICE</b>"
        elif d==11:
            diamonds=["💎","🔷","🔹","🔸","💠"]; text="\n".join("      "+"  ".join(diamonds[(i+j)%5] for j in range(5)) for _ in range(4)); title="💎 <b>DIAMOND RUSH</b>"
        elif d==12:
            coins=["💰","🪙","💵","💸","💳"]; text="\n".join("   "+"  ".join(coins[(i+j)%5] for j in range(6)) for _ in range(4)); title="💸 <b>MONEY RAIN</b>"
        elif d==13:
            crown=["👑","💎","🏆","🔐","💰"]; text=f"        {'  '.join(crown[(i+j)%5] for j in range(5))}\n\n           🔐\n\n        {'  '.join(crown[(i+j+2)%5] for j in range(5))}"; title="👑 <b>CROWN VAULT</b>"
        elif d==14:
            colors=["🔴","🟠","🟡","🟢","🔵","🟣"]; text="\n".join("      "+"  ".join(colors[(i+j+r)%6] for j in range(6)) for r in range(5)); title="🌈 <b>RAINBOW FLIP</b>"
        else:
            nums=["💰","💎","7️⃣","👑","🎁","🏆","⭐"]; text=f"        {'  '.join(nums[(i+j)%7] for j in range(7))}\n\n             💥\n\n        {'  '.join(nums[(i+j+3)%7] for j in range(7))}"; title="💥 <b>MEGA JACKPOT</b>"
        body=f"{title}\n<i>PREMIUM REWARD EXPERIENCE</i>\n\n{text}\n\n⚡ <b>SPINNING...</b>\n<i>আপনার রিওয়ার্ড প্রস্তুত হচ্ছে · Your reward is on the way</i>"
        try: await msg.edit_text(body,reply_markup=reply_markup,parse_mode="HTML")
        except Exception: pass
        await asyncio.sleep(delay)

@dp.callback_query(F.data == "lucky_spin")
async def lucky_spin_menu(q: CallbackQuery):
    admin = is_admin(q.from_user.id)
    today=bd_now().date().isoformat()
    con=db(); used=None if admin else con.execute("SELECT 1 FROM lucky_spins WHERE user_id=? AND spin_date=?",(q.from_user.id,today)).fetchone(); con.close()
    if used:
        await q.message.edit_text(format_setting_message("lucky_spin_used_message"),reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("◀️ BACK","home")]]),parse_mode="HTML"); await q.answer(); return
    info = "👑 <b>Admin-এর জন্য Unlimited Spin ON</b>\n💰 প্রতিবার জেতা Reward Wallet-এ যোগ হবে।" if admin else "🎁 প্রতিদিন ১ বার Spin করতে পারবেন।\n💰 Win হলে টাকা আপনার Wallet-এ যোগ হবে।"
    await q.message.edit_text(format_setting_message("lucky_spin_message"),reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("🎰 SPIN NOW","spin_now")],[btn("◀️ BACK TO MAIN MENU","home")]]),parse_mode="HTML"); await q.answer()

@dp.callback_query(F.data == "spin_now")
async def lucky_spin_now(q: CallbackQuery):
    today=bd_now().date().isoformat(); admin=is_admin(q.from_user.id)
    con=db(); used=None if admin else con.execute("SELECT 1 FROM lucky_spins WHERE user_id=? AND spin_date=?",(q.from_user.id,today)).fetchone(); con.close()
    if used:
        await q.answer("আজকের Spin already ব্যবহার করেছেন।",show_alert=True); return
    design="8"  # Fixed NEON SLOT animation; admin selection is disabled.
    await run_lucky_animation(q.message,"8",5)
    roll=random.random()
    if roll<0.45: prize=0
    elif roll<0.95: prize=random.randint(1,10)
    else: prize=random.randint(11,20)
    con=db()
    try:
        if not admin:
            con.execute("INSERT INTO lucky_spins(user_id,spin_date,prize,created_at) VALUES(?,?,?,?)",(q.from_user.id,today,prize,datetime.now().isoformat()))
        if prize: con.execute("UPDATE users SET balance=balance+? WHERE id=?",(prize,q.from_user.id))
        con.commit()
    except sqlite3.IntegrityError:
        con.close(); await q.answer("আজকের Spin already নেওয়া হয়েছে।",show_alert=True); return
    con.close()
    if prize:
        result=format_setting_message("lucky_spin_win_message", prize=prize)
    else:
        result=format_setting_message("lucky_spin_lose_message")
    rows=[[btn("⌂ BACK TO MAIN MENU","home")]]
    await q.message.edit_text(result,reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),parse_mode="HTML"); await q.answer()

# =========================================================
# PROFILE / ORDERS / REF / SUPPORT / CHANNEL / OWNER / HOWTO
# =========================================================
@dp.callback_query(F.data == "profile")
async def cb_profile(q: CallbackQuery):
    con = db()
    u = con.execute(
        "SELECT * FROM users WHERE id=?", (q.from_user.id,)
    ).fetchone()
    total = con.execute(
        "SELECT COUNT(*) n FROM orders WHERE user_id=?",
        (q.from_user.id,)
    ).fetchone()["n"]
    pending = con.execute(
        "SELECT COUNT(*) n FROM orders WHERE user_id=? AND status='PENDING'",
        (q.from_user.id,)
    ).fetchone()["n"]
    completed = con.execute(
        "SELECT COUNT(*) n FROM orders WHERE user_id=? AND status='COMPLETED'",
        (q.from_user.id,)
    ).fetchone()["n"]

    # Profile statistics are displayed in BDT only.
    spent = con.execute(
        "SELECT COALESCE(SUM(price),0) n FROM orders WHERE user_id=? AND status='COMPLETED'",
        (q.from_user.id,)
    ).fetchone()["n"]
    deposited = 0.0  # Deposit ledger is not present in the current schema.
    referral_earned = 0.0
    ref_rows = con.execute(
        "SELECT o.price FROM orders o JOIN users u ON u.id=o.user_id WHERE u.ref_by=? AND o.referral_paid=1 AND o.status='COMPLETED'",
        (q.from_user.id,)
    ).fetchall()
    for rr in ref_rows:
        referral_earned += referral_reward_for_price(rr["price"])
    referrals = con.execute(
        "SELECT COUNT(*) n FROM users WHERE ref_by=?",
        (q.from_user.id,)
    ).fetchone()["n"]
    con.close()

    text = format_setting_message(
        "profile_message",
        user_id=u["id"],
        name=html.escape(str(u["name"])),
        balance=float(u["balance"]),
        total_orders=total,
        spent=float(spent),
        deposited=float(deposited),
        referral_earned=float(referral_earned),
        total_referrals=referrals
    )
    await q.message.edit_text(text, reply_markup=back(), parse_mode="HTML")
    await q.answer()


@dp.callback_query(F.data == "orders")
async def cb_orders(q):
    """Legacy My Orders entry kept for compatibility."""
    await show_my_products(q)


@dp.callback_query(F.data == "my_products")
async def show_my_products(q: CallbackQuery):
    """Premium My Orders list with compact status cards."""
    con = db()
    rows = con.execute(
        """SELECT o.*, p.name, p.validity, p.device_limit, p.features, p.description,
                  p.delivery_type, p.delivery_data, p.active
           FROM orders o JOIN products p ON p.id=o.product_id
           WHERE o.user_id=? AND o.status='COMPLETED'
           ORDER BY o.id DESC LIMIT 50""",
        (q.from_user.id,)
    ).fetchall()
    con.close()

    if not rows:
        await q.message.edit_text(
            format_setting_message("my_orders_empty_message"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("🛒 SHOP NOW", "shop")],[btn("🏠 BACK TO MENU", "home")]]),
            parse_mode="HTML"
        )
        await q.answer(); return

    active=[]; expired=[]
    for r in rows:
        status="🟢 ACTIVE"
        if r["expiry_at"]:
            try:
                if datetime.fromisoformat(r["expiry_at"]) < bd_now(): status="🔴 EXPIRED"
            except Exception: pass
        (active if status=="🟢 ACTIVE" else expired).append((r,status))

    lines=["╔══════════════════════════════╗","        🧾 <b>MY ORDERS</b>","╚══════════════════════════════╝","", "✨ <b>YOUR PURCHASE HISTORY</b>", ""]
    if active:
        lines.append("🟢 <b>ACTIVE ORDERS</b>")
        for r,_ in active[:10]:
            exp=format_expiry(r["expiry_at"]) if r["expiry_at"] else "No expiry"
            lines += ["┌──────────────────────────────┐", f"│ 🟢 <b>ORDER #{r['id']}</b>", f"│ 📦 {html.escape(str(r['name'] or 'PRODUCT'))}", f"│ 💰 ৳{r['price']:g}  •  ⏳ {html.escape(exp)}", "└──────────────────────────────┘", ""]
    if expired:
        lines.append("🔴 <b>EXPIRED ORDERS</b>")
        for r,_ in expired[:10]:
            exp=format_expiry(r["expiry_at"]) if r["expiry_at"] else "Expired"
            lines += ["┌──────────────────────────────┐", f"│ 🔴 <b>ORDER #{r['id']}</b>", f"│ 📦 {html.escape(str(r['name'] or 'PRODUCT'))}", f"│ 💰 ৳{r['price']:g}  •  ⏳ {html.escape(exp)}", "└──────────────────────────────┘", ""]
    lines.append("👇 <i>Order details দেখতে নিচের button চাপুন</i>")

    keyboard=[]
    for r,status in [(x[0],x[1]) for x in active[:10]+expired[:10]]:
        keyboard.append([btn(f"{status}  #{r['id']} • {str(r['name'] or 'PRODUCT')[:22]}",f"order_detail:{r['id']}")])
    keyboard += [[btn("🛒 BUY NEW PRODUCT", "shop")],[btn("🏠 BACK TO MENU", "home")]]
    await q.message.edit_text("\n".join(lines),reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),parse_mode="HTML")
    await q.answer()


@dp.callback_query(F.data.startswith("order_detail:"))
async def order_detail(q):
    oid=int(q.data.split(":")[1])
    con=db()
    r=con.execute(
        """SELECT o.*,p.name,p.validity,p.device_limit,p.features,p.description
           FROM orders o JOIN products p ON p.id=o.product_id
           WHERE o.id=? AND o.user_id=?""",
        (oid,q.from_user.id)
    ).fetchone()
    con.close()
    if not r:
        await q.answer("Order পাওয়া যায়নি।",show_alert=True)
        return

    rows=[]
    if r["status"]=="COMPLETED":
        rows.append([btn("📦 VIEW MY PRODUCT",f"my_product:{oid}")])
    rows.append([btn("◀️ BACK","my_products")])
    await q.message.edit_text(
        f"📦 <b>ORDER #{oid}</b>\n\n"
        f"🏷️ Product: <b>{html.escape(str(r['name']))}</b>\n"
        f"💰 Price: <b>৳{r['price']:g} TK</b>\n"
        f"📌 Status: <b>{r['status']}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML"
    )
    await q.answer()


@dp.callback_query(F.data.startswith("my_product:"))
async def my_product(q: CallbackQuery):
    """Show the full purchased-product details and allow re-delivery."""
    oid = int(q.data.split(":")[1])
    con = db()
    row = con.execute(
        """SELECT o.*, p.name, p.validity, p.device_limit, p.features, p.product_type, p.apk_url,
                  p.description, p.demo_file_id, p.demo_type,
                  p.delivery_type, p.delivery_data, o.delivery_type_snapshot, o.delivery_data_snapshot,
                  ap.validity plan_validity, ap.device_limit plan_device_limit, ap.password legacy_plan_password, COALESCE(o.delivery_password, ap.password) plan_password
           FROM orders o JOIN products p ON p.id=o.product_id
           LEFT JOIN apk_plans ap ON ap.id=o.plan_id
           WHERE o.id=? AND o.user_id=? AND o.status='COMPLETED'""",
        (oid, q.from_user.id)
    ).fetchone()
    con.close()
    if not row:
        await q.answer("Product পাওয়া যায়নি।", show_alert=True)
        return

    name = html.escape(str(row["name"] or "PRODUCT"))
    lines = [
        "╭━━━━━━━━━━━━━━━━━━━━━━╮",
        "✦ <b>𝐌𝐘 𝐏𝐑𝐎𝐃𝐔𝐂𝐓</b> ✦",
        "╰━━━━━━━━━━━━━━━━━━━━━━╯",
        "",
        f"<b>{name}</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]
    if row["description"]:
        lines += [f"🏷️ {html.escape(str(row['description']))}", ""]
    lines += [f"💰 <b>PRICE: ৳{row['price']:g}</b>", ""]
    if row["product_type"] == "apk":
        lines += [f"⏳ Plan: <b>{html.escape(str(row['plan_validity'] or 'N/A'))}</b>"]
        device_value = row['plan_device_limit'] or row['device_limit']
        if device_value:
            lines += [f"📱 Device Limit: <b>{html.escape(str(device_value))}</b>"]
        lines += [""]
        lines += ["🔐 <b>APK PASSWORD</b>", f"<code>{html.escape(str(row['plan_password'] or 'N/A'))}</code>", ""]
    if row["validity"] and row["product_type"] != "apk":
        lines += [f"⏳ Validity: {html.escape(str(row['validity']))}", ""]
    if row["device_limit"]:
        lines += [f"📱 Device Limit: {html.escape(str(row['device_limit']))}", ""]
    if row["features"]:
        lines += [f"⭐ Features: {html.escape(str(row['features']))}", ""]
    if row["expiry_at"]:
        lines += [f"📅 Expire Date: <b>{html.escape(format_expiry(row['expiry_at']))}</b>", ""]
    lines += [
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"🧾 Purchase ID: <code>#{oid}</code>",
        "",
        "📥 আপনার কেনা Product আবার নিতে নিচের বাটনে চাপুন।"
    ]

    keyboard=[]
    if row["product_type"] == "apk" and row["apk_url"]:
        keyboard.append([InlineKeyboardButton(text="📥 DOWNLOAD APK", url=row["apk_url"])])
    if row["delivery_data"] or row["product_type"] == "apk":
        keyboard.append([btn("📥 GET PRODUCT AGAIN", f"redeliver:{oid}")])
    if row["demo_file_id"]:
        keyboard.append([btn("🎬 DEMO VIDEO", f"demo:{row['product_id']}")])
    keyboard.append([btn("🛒 BUY NEW PRODUCT", "shop")])
    keyboard.append([btn("◀️ BACK", "my_products")])

    await q.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )
    await q.answer()


@dp.callback_query(F.data.startswith("redeliver:"))
async def redeliver_product(q: CallbackQuery):
    oid=int(q.data.split(":")[1])
    con=db(); row=con.execute("""SELECT o.*,p.name,p.delivery_type,p.delivery_data,o.delivery_type_snapshot,o.delivery_data_snapshot,p.product_type,p.apk_url,p.device_limit,ap.validity plan_validity,ap.device_limit plan_device_limit,ap.password legacy_plan_password,COALESCE(o.delivery_password, ap.password) plan_password
                               FROM orders o JOIN products p ON p.id=o.product_id
                               LEFT JOIN apk_plans ap ON ap.id=o.plan_id
                               WHERE o.id=? AND o.user_id=? AND o.status='COMPLETED'""",(oid,q.from_user.id)).fetchone(); con.close()
    if not row: await q.answer("এই Product আপনার কেনা নয়।",show_alert=True); return
    await q.answer("📥 Product আবার পাঠানো হচ্ছে...")
    loading=await delivery_loading(q.from_user.id)
    if row["product_type"]=="apk":
        await deliver_apk_order(row,format_expiry(row["expiry_at"]))
    else:
        if not (row["delivery_data_snapshot"] if "delivery_data_snapshot" in row.keys() and row["delivery_data_snapshot"] else row["delivery_data"]):
            await bot.send_message(q.from_user.id,"⚠️ এই Product-এর Delivery Content নেই।")
        else:
            await deliver_product(q.from_user.id,row)
    try: await loading.delete()
    except Exception: pass
    await q.message.answer(f"✅ <b>{html.escape(str(row['name']))}</b> আবার পাঠানো হয়েছে।",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("📦 VIEW MY PRODUCT",f"my_product:{oid}")],[btn("◀️ MY PRODUCTS","my_products")]]),parse_mode="HTML")


@dp.callback_query(F.data == "adm_support")
async def adm_support(q: CallbackQuery):
    await q.message.edit_text("💬 <b>SUPPORT SETTINGS</b>\n━━━━━━━━━━━━━━━━━━\n\nTelegram/WhatsApp link, New Trick এবং Trick Inbox এখান থেকে manage করুন।", reply_markup=support_settings_kb(), parse_mode="HTML"); await q.answer()

@dp.callback_query(F.data == "set_admin_link")
async def set_admin_link(q, state):
    if not is_admin(q.from_user.id): return
    current = get_setting("admin_link")
    await state.set_state(S.admin_link)
    await q.message.edit_text(
        f"👤 <b>ADMIN LINK</b>\n━━━━━━━━━━━━━━━━━━\n\nবর্তমান Link: <code>{html.escape(current or 'Not Set')}</code>\n\nনতুন Admin Telegram Link পাঠান।\nউদাহরণ: https://t.me/YourUsername",
        reply_markup=back("adm_settings"), parse_mode="HTML"
    )
    await q.answer()

@dp.message(S.admin_link)
async def save_admin_link(message, state):
    if not is_admin(message.from_user.id): return
    link = (message.text or "").strip()
    if not (link.startswith("https://t.me/") or link.startswith("tg://")):
        await message.answer("❌ সঠিক Telegram Admin Link দিন।\nউদাহরণ: https://t.me/YourUsername", reply_markup=back("adm_settings"))
        return
    set_setting("admin_link", link)
    # Keep existing Ban Contact Admin button synchronized with the saved Admin Link.
    set_setting("ban_contact_link", link)
    await state.clear()
    await message.answer("✅ Admin Link সফলভাবে Updated হয়েছে।", reply_markup=back("adm_settings"))

@dp.callback_query(F.data == "set_support_telegram")
async def set_support_telegram(q,state):
    await state.set_state(S.support_telegram); await q.message.edit_text("✈️ নতুন Telegram Support Link দিন।", reply_markup=back("adm_support")); await q.answer()

@dp.message(S.support_telegram)
async def save_support_telegram(message,state):
    set_setting("support_telegram", (message.text or "").strip()); await state.clear(); await message.answer("✅ Telegram Support Link Updated.", reply_markup=back("adm_support"))

@dp.callback_query(F.data == "set_support_whatsapp")
async def set_support_whatsapp(q,state):
    await state.set_state(S.support_whatsapp); await q.message.edit_text("🟢 নতুন WhatsApp Support Link দিন।", reply_markup=back("adm_support")); await q.answer()

@dp.message(S.support_whatsapp)
async def save_support_whatsapp(message,state):
    set_setting("support_whatsapp", (message.text or "").strip()); await state.clear(); await message.answer("✅ WhatsApp Support Link Updated.", reply_markup=back("adm_support"))

@dp.callback_query(F.data == "adm_howto")
async def adm_howto(q):
    await q.message.edit_text("📖 <b>HOW TO USE SETTINGS</b>\n━━━━━━━━━━━━━━━━━━\n\nVideo, Link বা Instruction Text যেটা দরকার সেট করুন।", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("🎥 SET VIDEO","howto_add_video"),btn("🔗 SET LINK","howto_add_link")],[btn("📝 EDIT TEXT","howto_edit_text")],[btn("🗑️ REMOVE VIDEO","howto_delete_video"),btn("🗑️ REMOVE LINK","howto_delete_link")],[btn("◀️ BACK","admin_home")]]), parse_mode="HTML"); await q.answer()


# =========================================================
# SUPPORT / TRICK INBOX
# =========================================================
@dp.callback_query(F.data == "trick_inbox")
async def trick_inbox(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    con=db(); rows=con.execute("SELECT id,user_id,name,username,message_text,status,created_at FROM support_messages ORDER BY id DESC LIMIT 50").fetchall(); con.close()
    kb=[]
    for r in rows:
        icon="🆕" if r["status"]=="NEW" else "✅"
        label=f"{icon} #{r['id']} • {r['name'][:18]} • {str(r['message_text'] or 'Media')[:18]}"
        kb.append([btn(label,f"trick_detail:{r['id']}")])
    kb.append([btn("◀️ BACK","adm_support")])
    await q.message.edit_text("📥 <b>TRICK INBOX</b>\n\nUser-এর পাঠানো সব New Trick/Support message এখানে পাবেন।",reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),parse_mode="HTML"); await q.answer()

@dp.callback_query(F.data.startswith("trick_detail:"))
async def trick_detail(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    mid=int(q.data.split(":")[1]); con=db(); r=con.execute("SELECT * FROM support_messages WHERE id=?",(mid,)).fetchone(); con.close()
    if not r: await q.answer("Trick পাওয়া যায়নি।",show_alert=True); return
    con=db(); con.execute("UPDATE support_messages SET status='VIEWED' WHERE id=?",(mid,)); con.commit(); con.close()
    text=(f"📨 <b>TRICK #{r['id']}</b>\n━━━━━━━━━━━━━━━━━━\n👤 {html.escape(r['name'] or '')}\n🔗 @{html.escape(r['username'] or 'N/A')}\n🆔 <code>{r['user_id']}</code>\n🕒 {html.escape(r['created_at'])}\n📌 Status: VIEWED\n\n{html.escape(r['message_text'] or '📎 Media/Attachment')}")
    await q.message.edit_text(text,reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("✉️ REPLY USER",f"trick_message:{r['user_id']}" )],[btn("🗑️ DELETE",f"trick_delete:{mid}" )],[btn("◀️ BACK","trick_inbox")]]),parse_mode="HTML"); await q.answer()

@dp.callback_query(F.data.startswith("trick_delete:"))
async def trick_delete(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    mid=int(q.data.split(":")[1]); con=db(); con.execute("DELETE FROM support_messages WHERE id=?",(mid,)); con.commit(); con.close(); await q.answer("Deleted"); await trick_inbox(q)

@dp.callback_query(F.data.startswith("trick_message:"))
async def trick_message(q: CallbackQuery,state: FSMContext):
    if not is_admin(q.from_user.id): return
    uid=int(q.data.split(":")[1]); await state.update_data(trick_reply_uid=uid); await state.set_state(S.trick_reply); await q.message.edit_text("✉️ User-কে যে Reply পাঠাতে চান সেটি লিখুন।",reply_markup=back("trick_inbox")); await q.answer()

@dp.message(S.trick_reply)
async def save_trick_reply(message: Message,state: FSMContext):
    if not is_admin(message.from_user.id): return
    data=await state.get_data(); uid=data.get("trick_reply_uid"); await state.clear()
    try:
        await bot.send_message(uid,message.text or message.caption or "📎 Admin sent an attachment")
        con=db(); con.execute("UPDATE support_messages SET status='REPLIED' WHERE id=(SELECT id FROM support_messages WHERE user_id=? ORDER BY id DESC LIMIT 1)",(uid,)); con.commit(); con.close()
        await message.answer("✅ Reply User-এর কাছে পাঠানো হয়েছে।",reply_markup=back("trick_inbox"))
    except Exception as e:
        await message.answer("❌ User-কে Message পাঠানো যায়নি।",reply_markup=back("trick_inbox"))


# =========================================================
# HOW TO USE / OFFICIAL CHANNEL / BROADCAST / GENERAL SETTINGS
# =========================================================
@dp.callback_query(F.data == "howto_add_video")
async def howto_add_video(q: CallbackQuery,state: FSMContext):
    if not is_admin(q.from_user.id): return
    await state.set_state(S.howto_video); await q.message.edit_text("🎥 একটি Telegram Video পাঠান।",reply_markup=back("adm_howto")); await q.answer()

@dp.message(S.howto_video,F.video)
async def save_howto_video(message: Message,state: FSMContext):
    if not is_admin(message.from_user.id): return
    set_setting("howto_video_id",message.video.file_id); set_setting("howto_link",""); await state.clear(); await message.answer("✅ HOW TO USE Video Saved.",reply_markup=back("adm_howto"))

@dp.message(S.howto_video)
async def invalid_howto_video(message: Message):
    await message.answer("❌ একটি Telegram Video পাঠান।")

@dp.callback_query(F.data == "howto_add_link")
async def howto_add_link(q: CallbackQuery,state: FSMContext):
    if not is_admin(q.from_user.id): return
    await state.set_state(S.howto_link); await q.message.edit_text("🔗 How To Use Link দিন (https://...):",reply_markup=back("adm_howto")); await q.answer()

@dp.message(S.howto_link)
async def save_howto_link(message: Message,state: FSMContext):
    if not is_admin(message.from_user.id): return
    url=(message.text or "").strip()
    if not (url.startswith("https://") or url.startswith("http://")):
        await message.answer("❌ সঠিক http/https Link দিন।"); return
    set_setting("howto_link",url); set_setting("howto_video_id",""); await state.clear(); await message.answer("✅ HOW TO USE Link Saved.",reply_markup=back("adm_howto"))

@dp.callback_query(F.data == "howto_edit_text")
async def howto_edit_text(q: CallbackQuery,state: FSMContext):
    if not is_admin(q.from_user.id): return
    await state.update_data(setting_key="howto",setting_parent="adm_howto"); await state.set_state(S.setting_value); await q.message.edit_text("📝 HOW TO USE TEXT\n\nনতুন Text পাঠান।",reply_markup=back("adm_howto")); await q.answer()

@dp.callback_query(F.data == "howto_delete_video")
async def howto_delete_video(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    set_setting("howto_video_id",""); await adm_howto(q)

@dp.callback_query(F.data == "howto_delete_link")
async def howto_delete_link(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    set_setting("howto_link",""); await adm_howto(q)

@dp.callback_query(F.data == "set_channel")
async def set_channel(q: CallbackQuery,state: FSMContext):
    if not is_admin(q.from_user.id): return
    current=get_setting("official_channel")
    await state.update_data(setting_key="official_channel",setting_parent="admin_home"); await state.set_state(S.setting_value)
    await q.message.edit_text(f"📢 OFFICIAL CHANNEL\n\nCurrent: {html.escape(current or '(Not set)')}\n\nনতুন Channel Link দিন।",reply_markup=back("admin_home"),parse_mode="HTML"); await q.answer()

@dp.callback_query(F.data == "adm_broadcast")
async def adm_broadcast(q: CallbackQuery,state: FSMContext):
    if not is_admin(q.from_user.id): return
    await state.set_state(S.broadcast_post)
    await q.message.edit_text("📣 <b>BROADCAST</b>\n\nপ্রথমে যে পোস্টটি সবাইকে পাঠাতে চান সেটি পাঠান।\nText, Photo, Video বা Document পাঠাতে পারবেন।",reply_markup=back("admin_home"),parse_mode="HTML")
    await q.answer()

async def _send_broadcast(post: Message, buttons=None):
    con=db(); users=con.execute("SELECT id FROM users WHERE banned=0").fetchall(); con.close(); sent=0
    markup=None
    if buttons:
        rows=[]
        for name,url in buttons:
            rows.append([url_btn(name,url)])
        markup=InlineKeyboardMarkup(inline_keyboard=rows)
    for u in users:
        try:
            await bot.copy_message(chat_id=u["id"],from_chat_id=post.chat.id,message_id=post.message_id,reply_markup=markup)
            sent+=1
        except Exception: pass
    return sent

@dp.message(S.broadcast_post)
async def broadcast_post_received(message: Message,state:FSMContext):
    if not is_admin(message.from_user.id): return
    await state.update_data(broadcast_chat_id=message.chat.id,broadcast_message_id=message.message_id,broadcast_buttons=[])
    await state.set_state(S.broadcast_button_count)
    await message.answer("🔘 পোস্টের নিচে কোনো Button রাখতে চান?\n\nচাইলে Button-এর সংখ্যা পাঠান (যেমন: <code>1</code>, <code>2</code>)।\nButton না চাইলে <code>/skip</code> পাঠান।",parse_mode="HTML",reply_markup=back("admin_home"))

@dp.message(S.broadcast_button_count)
async def broadcast_button_count(message: Message,state:FSMContext):
    if not is_admin(message.from_user.id): return
    value=(message.text or "").strip()
    if value.lower()=="/skip":
        data=await state.get_data(); await state.clear()
        post=type("Post",(),{"chat":type("Chat",(),{"id":data["broadcast_chat_id"]})(),"message_id":data["broadcast_message_id"]})()
        sent=await _send_broadcast(post,[])
        await message.answer(f"📣 Broadcast Complete\n\n✅ Sent: {sent}",reply_markup=admin_kb()); return
    try: n=int(value)
    except ValueError:
        await message.answer("❌ শুধু Button-এর সংখ্যা পাঠান। যেমন: <code>1</code>",parse_mode="HTML"); return
    if n<1 or n>10:
        await message.answer("❌ 1 থেকে 10টি Button দেওয়া যাবে।"); return
    await state.update_data(broadcast_button_total=n,broadcast_button_index=1,broadcast_buttons=[])
    await state.set_state(S.broadcast_button_name)
    await message.answer("1️⃣ Button #1-এর <b>নাম</b> পাঠান।",parse_mode="HTML")

@dp.message(S.broadcast_button_name)
async def broadcast_button_name(message: Message,state:FSMContext):
    if not is_admin(message.from_user.id): return
    name=(message.text or "").strip()
    if not name or len(name)>64:
        await message.answer("❌ Button name 1-64 characters হতে হবে।"); return
    data=await state.get_data(); await state.update_data(current_button_name=name)
    await state.set_state(S.broadcast_button_url)
    await message.answer(f"🔗 Button <b>{data.get('broadcast_button_index',1)}</b>-এ click করলে কোন URL-এ যাবে?\n\nhttps://... Link পাঠান।",parse_mode="HTML")

@dp.message(S.broadcast_button_url)
async def broadcast_button_url(message: Message,state:FSMContext):
    if not is_admin(message.from_user.id): return
    url=(message.text or "").strip()
    if not (url.startswith("https://") or url.startswith("http://") or url.startswith("tg://")):
        await message.answer("❌ সঠিক http/https/tg:// URL পাঠান।"); return
    data=await state.get_data(); buttons=list(data.get("broadcast_buttons") or []); buttons.append((data.get("current_button_name","Button"),url)); idx=int(data.get("broadcast_button_index",1)); total=int(data.get("broadcast_button_total",1))
    if idx<total:
        await state.update_data(broadcast_buttons=buttons,broadcast_button_index=idx+1)
        await state.set_state(S.broadcast_button_name)
        await message.answer(f"{idx+1}️⃣ Button #{idx+1}-এর <b>নাম</b> পাঠান।",parse_mode="HTML"); return
    chat_id=data["broadcast_chat_id"]; msg_id=data["broadcast_message_id"]; await state.clear()
    post=type("Post",(),{"chat":type("Chat",(),{"id":chat_id})(),"message_id":msg_id})()
    sent=await _send_broadcast(post,buttons)
    await message.answer(f"📣 Broadcast Complete\n\n🔘 Buttons: {len(buttons)}\n✅ Sent: {sent}",reply_markup=admin_kb())

@dp.callback_query(F.data == "ban_settings")
async def ban_settings(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    enabled = get_setting("ban_notification_enabled") != "0"
    link = get_setting("ban_contact_link") or get_setting("owner_link") or ""
    button = get_setting("ban_contact_button") or "📞 CONTACT ADMIN"
    text = (
        "🚫 <b>BAN SETTINGS</b>\n\n"
        f"🔔 Ban Notification: <b>{'ON' if enabled else 'OFF'}</b>\n"
        f"🔗 Contact Link: <code>{html.escape(link or '(Not set)')}</code>\n"
        f"🔘 Contact Button: <b>{html.escape(button)}</b>\n\n"
        "এই Settings থেকে Ban message, Contact Link এবং Button আলাদা করে পরিবর্তন করতে পারবেন।\n"
        "Ban করার সময় Reason optional থাকবে।"
    )
    kb=InlineKeyboardMarkup(inline_keyboard=[
        [btn("🔔 TURN OFF" if enabled else "🔔 TURN ON", "ban_toggle")],
        [btn("📝 CHANGE BAN MESSAGE", "ban_change_message")],
        [btn("🔗 CHANGE CONTACT LINK", "ban_change_link")],
        [btn("🔘 CHANGE BUTTON TEXT", "ban_change_button")],
        [btn("◀️ BACK", "adm_settings")]
    ])
    await q.message.edit_text(text,reply_markup=kb,parse_mode="HTML"); await q.answer()

@dp.callback_query(F.data == "ban_toggle")
async def ban_toggle(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    current=get_setting("ban_notification_enabled") != "0"
    set_setting("ban_notification_enabled", "0" if current else "1")
    await ban_settings(q)

@dp.callback_query(F.data == "ban_change_message")
async def ban_change_message(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    await state.update_data(setting_key="ban_notification_message",setting_parent="ban_settings")
    await state.set_state(S.setting_value)
    await q.message.edit_text("📝 <b>CHANGE BAN MESSAGE</b>\n\n{reason} লিখলে সেখানে Ban করার Reason বসবে।\n\nনতুন message পাঠান।",reply_markup=back("ban_settings"),parse_mode="HTML"); await q.answer()

@dp.callback_query(F.data == "ban_change_link")
async def ban_change_link(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    await state.update_data(setting_key="ban_contact_link",setting_parent="ban_settings")
    await state.set_state(S.setting_value)
    await q.message.edit_text("🔗 <b>CHANGE CONTACT LINK</b>\n\nTelegram profile/channel URL পাঠান।\nউদাহরণ: https://t.me/username",reply_markup=back("ban_settings"),parse_mode="HTML"); await q.answer()

@dp.callback_query(F.data == "ban_change_button")
async def ban_change_button(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    await state.update_data(setting_key="ban_contact_button",setting_parent="ban_settings")
    await state.set_state(S.setting_value)
    await q.message.edit_text("🔘 <b>CHANGE BUTTON TEXT</b>\n\nনতুন button text পাঠান।",reply_markup=back("ban_settings"),parse_mode="HTML"); await q.answer()

async def notify_user_banned(uid, reason="", contact_link=""):
    if get_setting("ban_notification_enabled") == "0":
        return
    reason = (reason or "Admin-এর সিদ্ধান্ত অনুযায়ী").strip()
    template = get_setting("ban_notification_message") or "🚫 <b>ACCOUNT BANNED</b>\n\n⚠️ তোমাকে Admin ব্যান করেছে।\n\n📌 <b>কারণ:</b> {reason}\n\n🔓 আনব্যান হতে চাইলে নিচের <b>CONTACT ADMIN</b> বাটনে Admin-এর সাথে যোগাযোগ করো।"
    try:
        msg = format_setting_message("ban_notification_message", reason=html.escape(reason)) if get_setting("ban_notification_message") else template.replace("{reason}", html.escape(reason))
        link = contact_link or get_setting("ban_contact_link") or get_setting("owner_link") or "https://t.me/"
        button = get_setting("ban_contact_button") or "📞 CONTACT ADMIN"
        # Banned user: CONTACT ADMIN only. /start is intentionally not shown here.
        kb = InlineKeyboardMarkup(inline_keyboard=[[url_btn(button, link)]]) if link.startswith(("http://","https://","tg://")) else None
        await bot.send_message(uid,msg,reply_markup=kb,parse_mode="HTML")
    except Exception:
        logging.exception("Failed to send ban notification to %s", uid)

@dp.callback_query(F.data == "adm_settings")
async def adm_settings(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    await q.message.edit_text("⚙️ <b>GENERAL SETTINGS</b>\n\nনিচের Section থেকে Bot settings manage করুন।",reply_markup=settings_kb(),parse_mode="HTML"); await q.answer()

@dp.callback_query(F.data == "change_ref_reward")
async def change_ref_reward(q: CallbackQuery,state: FSMContext):
    if not is_admin(q.from_user.id): return
    await state.set_state(S.referral_high_reward)
    await q.message.edit_text(
        f"💰 Current > ৳100 Reward: ৳{_setting_float('referral_reward_high', REF_REWARD_HIGH):g}\n\nনতুন > ৳100 Referral Reward লিখুন।",
        reply_markup=back("adm_ref")
    )
    await q.answer()

@dp.message(S.referral_high_reward)
async def save_ref_high_reward(message: Message,state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: value=float((message.text or "").strip())
    except ValueError:
        await message.answer("❌ শুধু সংখ্যা দিন।"); return
    if value < 0:
        await message.answer("❌ Reward 0 বা তার বেশি হতে হবে।"); return
    set_setting("referral_reward_high",str(value)); await state.clear()
    await message.answer(f"✅ > ৳100 Referral Reward ৳{value:g} করা হয়েছে।",reply_markup=back("adm_ref"))

@dp.callback_query(F.data == "change_ref_low")
async def change_ref_low(q: CallbackQuery,state: FSMContext):
    if not is_admin(q.from_user.id): return
    await state.set_state(S.referral_low_reward)
    await q.message.edit_text(
        f"💰 Current ৳100 বা কম Reward: ৳{_setting_float('referral_reward_low', REF_REWARD_LOW):g}\n\nনতুন ৳100 বা কম Referral Reward লিখুন।",
        reply_markup=back("adm_ref")
    )
    await q.answer()

@dp.message(S.referral_low_reward)
async def save_ref_low_reward(message: Message,state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: value=float((message.text or "").strip())
    except ValueError:
        await message.answer("❌ শুধু সংখ্যা দিন।"); return
    if value < 0:
        await message.answer("❌ Reward 0 বা তার বেশি হতে হবে।"); return
    set_setting("referral_reward_low",str(value)); await state.clear()
    await message.answer(f"✅ ৳100 বা কম Referral Reward ৳{value:g} করা হয়েছে।",reply_markup=back("adm_ref"))

@dp.callback_query(F.data == "change_ref_threshold")
async def change_ref_threshold(q: CallbackQuery,state: FSMContext):
    if not is_admin(q.from_user.id): return
    await state.set_state(S.referral_threshold)
    await q.message.edit_text(
        f"📊 Current Threshold: ৳{_setting_float('referral_threshold', REF_THRESHOLD):g}\n\nনতুন Referral Threshold লিখুন।",
        reply_markup=back("adm_ref")
    )
    await q.answer()

@dp.message(S.referral_threshold)
async def save_ref_threshold(message: Message,state: FSMContext):
    if not is_admin(message.from_user.id): return
    try: value=float((message.text or "").strip())
    except ValueError:
        await message.answer("❌ শুধু সংখ্যা দিন।"); return
    if value < 0:
        await message.answer("❌ Threshold 0 বা তার বেশি হতে হবে।"); return
    set_setting("referral_threshold",str(value)); await state.clear()
    await message.answer(f"✅ Referral Threshold ৳{value:g} করা হয়েছে।",reply_markup=back("adm_ref"))

@dp.callback_query(F.data == "adm_ref")
async def adm_ref(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    threshold=_setting_float("referral_threshold",REF_THRESHOLD)
    low=_setting_float("referral_reward_low",REF_REWARD_LOW)
    high=_setting_float("referral_reward_high",REF_REWARD_HIGH)
    text=(f"🎁 <b>REFERRAL SETTINGS</b>\n\n"
          f"📊 Threshold: <b>৳{threshold:g}</b>\n"
          f"💰 ৳{threshold:g} বা কম: <b>৳{low:g}</b>\n"
          f"💎 ৳{threshold:g}-এর বেশি: <b>৳{high:g}</b>\n\n"
          "Completed Product purchase হলে এই নিয়মে Referral Commission যোগ হবে।")
    kb=InlineKeyboardMarkup(inline_keyboard=[
        [btn("💰 CHANGE LOW REWARD", "change_ref_low")],
        [btn("💎 CHANGE HIGH REWARD", "change_ref_reward")],
        [btn("📊 CHANGE THRESHOLD", "change_ref_threshold")],
        [btn("◀️ BACK", "admin_home")]
    ])
    await q.message.edit_text(text,reply_markup=kb,parse_mode="HTML"); await q.answer()

@dp.message(S.setting_value)
async def save_setting_value(message: Message,state:FSMContext):
    if not is_admin(message.from_user.id): return
    data=await state.get_data(); key=data.get("setting_key"); parent=data.get("setting_parent","admin_home")
    if not key: await state.clear(); await message.answer("❌ Setting key পাওয়া যায়নি।",reply_markup=admin_kb()); return
    value=(message.text or "").strip()
    if not value: await message.answer("❌ Empty value দেওয়া যাবে না।"); return
    if key == "ban_contact_link" and not value.startswith(("http://","https://","tg://")):
        await message.answer("❌ Valid Telegram URL দিন। Example: https://t.me/username"); return
    if key == "ban_notification_message" and "{reason}" not in value:
        await message.answer("❌ Ban message-এর মধ্যে <code>{reason}</code> রাখতে হবে।",parse_mode="HTML"); return
    set_setting(key,value); await state.clear(); await message.answer(f"✅ <b>{html.escape(key)}</b> Updated.",reply_markup=back(parent),parse_mode="HTML")

@dp.callback_query(F.data.startswith("wallet_buy:"))
async def wallet_buy(q: CallbackQuery):
    parts=q.data.split(":"); pid=int(parts[1]); plan_id=int(parts[2]) if len(parts)>2 else None
    con=db(); p=con.execute("SELECT * FROM products WHERE id=? AND active=1",(pid,)).fetchone(); u=con.execute("SELECT * FROM users WHERE id=?",(q.from_user.id,)).fetchone(); plan=con.execute("SELECT * FROM apk_plans WHERE id=? AND product_id=? AND active=1",(plan_id,pid)).fetchone() if plan_id else None; con.close()
    if not p or not u: await q.answer("Product/User পাওয়া যায়নি।",show_alert=True); return
    if p["product_type"]=="apk":
        if not plan: await q.answer("Plan পাওয়া যায়নি।",show_alert=True); return
        if apk_stock_count(plan_id) <= 0: await q.answer("❌ এই Plan এখন Stock Out।",show_alert=True); return
        price=float(plan["price"]); validity=plan["validity"]
    else:
        if not p["stock_status"]: await q.answer("❌ Stock Out",show_alert=True); return
        price=float(p["price"]); validity=p["validity"]
    if float(u["balance"]) < price: await q.answer("❌ Wallet Balance কম।",show_alert=True); return

    expiry=calculate_expiry(validity,bd_now())
    # Create the order first; APK stock is atomically claimed below.
    con=db(); cur=con.execute("INSERT INTO orders(user_id,product_id,price,status,payment_method,expiry_at,plan_id,created_at,delivery_type_snapshot,delivery_data_snapshot) VALUES(?,?,?,?,?,?,?,?,?,?)",(q.from_user.id,pid,price,"PENDING","WALLET",expiry,plan_id,datetime.now().isoformat(),p["delivery_type"] or "",p["delivery_data"] or "")); oid=cur.lastrowid; con.commit(); con.close()
    if p["product_type"]=="apk":
        stock_id,password=await asyncio.to_thread(claim_apk_stock,oid,q.from_user.id,plan_id)
        if not stock_id:
            con=db(); con.execute("UPDATE orders SET status='REJECTED' WHERE id=?",(oid,)); con.commit(); con.close()
            await q.answer("❌ এই Plan এখন Stock Out।",show_alert=True); return
    # Deduct wallet only after stock is safely reserved.
    con=db();
    changed=con.execute("UPDATE users SET balance=balance-? WHERE id=? AND balance>=?",(price,q.from_user.id,price)).rowcount
    if changed != 1:
        con.execute("UPDATE orders SET status='REJECTED' WHERE id=?",(oid,));
        if p["product_type"]=="apk" and stock_id:
            con.execute("UPDATE apk_stock SET status='AVAILABLE',sold_order_id=NULL,sold_user_id=NULL,sold_at='' WHERE id=?",(stock_id,))
            sync_apk_plan_stock(con,plan_id)
        con.commit(); con.close(); await q.answer("❌ Wallet Balance কম।",show_alert=True); return
    con.execute("UPDATE orders SET status='COMPLETED' WHERE id=?",(oid,)); con.commit(); con.close()
    await pay_referrer_if_needed(oid)
    await notify_admin_purchase(oid, "Wallet Balance")
    loading=await delivery_loading(q.from_user.id)
    con=db(); order=con.execute("SELECT o.*,p.name,p.product_type,p.apk_url,p.delivery_type,p.delivery_data,p.validity,p.device_limit,p.demo_file_id,ap.validity plan_validity,ap.device_limit plan_device_limit,ap.price plan_price,COALESCE(o.delivery_password, ap.password) plan_password FROM orders o JOIN products p ON p.id=o.product_id LEFT JOIN apk_plans ap ON ap.id=o.plan_id WHERE o.id=?",(oid,)).fetchone(); con.close()
    try:
        await loading.delete()
    except Exception:
        pass
    if order["product_type"]=="apk": await deliver_apk_order(order,format_expiry(expiry))
    else:
        await notify_user_product_purchase(order)
        await deliver_product(q.from_user.id,order)
    await q.answer("✅ Purchase Successful")

# =========================================================
# PAYMENT SETTINGS — MANUAL PAYMENT ONLY
# =========================================================
@dp.callback_query(F.data == "payment_settings")
async def payment_settings(q):
    if not is_admin(q.from_user.id): return
    await q.message.edit_text(
        "💳 <b>PAYMENT SETTINGS</b>\n\n"
        f"📱 bKash: <b>{html.escape(payment_number('bkash'))}</b>\n"
        f"💵 Nagad: <b>{html.escape(payment_number('nagad'))}</b>\n\n"
        "🛠️ <b>Manual Payment Only</b>\n"
        "Auto Payment Gateway বর্তমানে সম্পূর্ণ বন্ধ।",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [btn("📱 CHANGE BKASH NUMBER","change_bkash_number")],
            [btn("💵 CHANGE NAGAD NUMBER","change_nagad_number")],
            [btn("📷 SET BKASH QR","set_bkash_qr")],
            [btn("📷 SET NAGAD QR","set_nagad_qr")],
            [btn("🗑️ DELETE BKASH QR","delete_bkash_qr")],
            [btn("🗑️ DELETE NAGAD QR","delete_nagad_qr")],
            [btn("◀️ BACK","adm_settings")]
        ]),parse_mode="HTML")
    await q.answer()
@dp.callback_query(F.data == "change_bkash_number")
async def change_bkash_number(q,state): await state.set_state(S.payment_bkash); await q.message.edit_text(f"📱 Current: <b>{html.escape(payment_number('bkash'))}</b>\n\nনতুন bKash Number দিন।",reply_markup=back("payment_settings"),parse_mode="HTML"); await q.answer()
@dp.message(S.payment_bkash)
async def save_bkash_number(message,state): set_setting("payment_bkash",(message.text or "").strip()); await state.clear(); await message.answer("✅ bKash Number Updated.",reply_markup=back("payment_settings"))
@dp.callback_query(F.data == "change_nagad_number")
async def change_nagad_number(q,state): await state.set_state(S.payment_nagad); await q.message.edit_text(f"💵 Current: <b>{html.escape(payment_number('nagad'))}</b>\n\nনতুন Nagad Number দিন।",reply_markup=back("payment_settings"),parse_mode="HTML"); await q.answer()
@dp.message(S.payment_nagad)
async def save_nagad_number(message,state): set_setting("payment_nagad",(message.text or "").strip()); await state.clear(); await message.answer("✅ Nagad Number Updated.",reply_markup=back("payment_settings"))
@dp.callback_query(F.data == "set_bkash_qr")
async def set_bkash_qr(q,state): await state.set_state(S.payment_bkash_qr); await q.message.edit_text("📷 bKash QR Image পাঠান।",reply_markup=back("payment_settings")); await q.answer()
@dp.message(S.payment_bkash_qr,F.photo)
async def save_bkash_qr(message,state): set_setting("bkash_qr",message.photo[-1].file_id); await state.clear(); await message.answer("✅ bKash QR Saved.",reply_markup=back("payment_settings"))
@dp.message(S.payment_bkash_qr)
async def invalid_bkash_qr(message): await message.answer("❌ QR Image হিসেবে Photo পাঠান।")
@dp.callback_query(F.data == "set_nagad_qr")
async def set_nagad_qr(q,state): await state.set_state(S.payment_nagad_qr); await q.message.edit_text("📷 Nagad QR Image পাঠান।",reply_markup=back("payment_settings")); await q.answer()
@dp.message(S.payment_nagad_qr,F.photo)
async def save_nagad_qr(message,state): set_setting("nagad_qr",message.photo[-1].file_id); await state.clear(); await message.answer("✅ Nagad QR Saved.",reply_markup=back("payment_settings"))
@dp.message(S.payment_nagad_qr)
async def invalid_nagad_qr(message): await message.answer("❌ QR Image হিসেবে Photo পাঠান।")
@dp.callback_query(F.data == "delete_bkash_qr")
async def delete_bkash_qr(q): set_setting("bkash_qr",""); await payment_settings(q)
@dp.callback_query(F.data == "delete_nagad_qr")
async def delete_nagad_qr(q): set_setting("nagad_qr",""); await payment_settings(q)

# =========================================================
# BUTTON & MESSAGE EDITOR
# =========================================================
EDITOR_BUTTONS = {
    "shop": "🛍️ SHOP NOW", "profile": "👤 PROFILE", "add_balance": "💳 DEPOSIT",
    "refer": "🎁 REFER", "my_products": "📦 MY ORDER", "lucky_spin": "🎰 LUCKY SPIN",
    "channel": "🔔 ALL UPDATE", "support": "🆘 SUPPORT", "howto": "📖 TUTORIAL",
    "home": "🏠 MAIN MENU", "new_trick": "🎯 TRICK SEND", "share_referral": "🎁 SHARE REFERRAL LINK",
    "add_amount:50": "💵 ৳50 BDT", "add_amount:100": "💵 ৳100 BDT", "add_amount:200": "💵 ৳200 BDT",
    "add_amount:300": "💵 ৳300 BDT", "add_amount:400": "💵 ৳400 BDT", "add_amount:500": "💵 ৳500 BDT",
    "add_custom_amount": "✏️ CUSTOM AMOUNT", "spin_now": "🎰 SPIN NOW", "deposit_send_proof": "📤 SEND PROOF",
    "channel": "🔔 ALL UPDATE", "product": "🛒 BUY NOW", "demo": "🎬 DEMO VIDEO",
}


EDITOR_MESSAGES = {
    "welcome": "Welcome / Main Menu Message", "verification_message": "Account Verification Message",
    "shop_message": "Shop Now Message", "profile_message": "Profile Message", "deposit_message": "Deposit Message",
    "support": "Support Center Message", "trick_message": "Send Trick / Support Ticket Message",
    "referral": "Referral Message (supports {referral_link}, {referrals}, {balance})", "howto": "Tutorial Message",
    "lucky_spin_message": "Lucky Spin Message", "lucky_spin_used_message": "Lucky Spin Used Message",
    "lucky_spin_win_message": "Lucky Spin Win Result ({prize})", "lucky_spin_lose_message": "Lucky Spin Lose Result",
    "my_orders_empty_message": "My Order Empty Message", "payment_extra": "Manual Payment Instructions",
    "balance_add_message": "Balance Added Notification", "balance_remove_message": "Balance Removed Notification",
    "referral_join_message": "Referral Join Notification", "order_accept_message": "Order Accepted Message",
    "order_reject_message": "Order Rejected Message",
}


@dp.callback_query(F.data == "adm_text_editor")
async def adm_text_editor(q: CallbackQuery):
    if not is_admin(q.from_user.id):
        await q.answer("Access denied.", show_alert=True); return
    await q.message.edit_text(
        "📝 <b>BUTTON & MESSAGE EDITOR</b>\n\n"
        "Choose what you want to edit. The current value will be shown before you enter a replacement.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [btn("🔘 EDIT BUTTON LABEL", "adm_edit_button_list")],
            [btn("💬 EDIT MESSAGE TEXT", "adm_edit_message_list")],
            [btn("◀️ BACK", "admin_home")],
        ]), parse_mode="HTML")
    await q.answer()

@dp.callback_query(F.data == "adm_edit_button_list")
async def adm_edit_button_list(q: CallbackQuery):
    if not is_admin(q.from_user.id):
        await q.answer("Access denied.", show_alert=True); return
    rows=[]
    for key, label in EDITOR_BUTTONS.items():
        setting_key = "button_label:" + key
        current=get_setting(setting_key) or (get_setting("button_label:" + key + ":" + label) if not key.startswith("url:") else get_setting("button_label:" + key.replace("url:","url:",1))) or label
        rows.append([InlineKeyboardButton(text=current[:48], callback_data="adm_edit_button:"+key)])
    rows.append([btn("◀️ BACK", "adm_text_editor")])
    await q.message.edit_text("🔘 <b>SELECT A BUTTON</b>\n\nCurrent custom labels are shown below. Select one to preview and edit it.", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    await q.answer()

@dp.callback_query(F.data.startswith("adm_edit_button:"))
async def adm_edit_button(q: CallbackQuery, state: FSMContext):
    if not is_admin(q.from_user.id):
        await q.answer("Access denied.", show_alert=True); return
    key=q.data.split(":",1)[1]
    if key not in EDITOR_BUTTONS:
        await q.answer("Unknown button.", show_alert=True); return
    label=EDITOR_BUTTONS[key]
    setting_key = "button_label:" + key
    current=get_setting(setting_key) or get_setting("button_label:" + key + ":" + label) or label
    await state.update_data(editor_key=key, editor_original_label=label)
    await state.set_state(S.editor_button_value)
    await q.message.edit_text(
        "🔘 <b>EDIT BUTTON LABEL</b>\n\n"
        f"<b>Button ID:</b> <code>{html.escape(key)}</code>\n"
        f"<b>Current Label:</b> {html.escape(current)}\n\n"
        "Send the new button label, or send /cancel to keep the current label.",
        reply_markup=back("adm_edit_button_list"), parse_mode="HTML")
    await q.answer()

@dp.message(S.editor_button_value)
async def save_editor_button(message: Message, state: FSMContext):
    data=await state.get_data(); key=data.get("editor_key"); original=data.get("editor_original_label", "")
    value=(message.text or "").strip()
    await state.clear()
    if value.lower()=="/cancel":
        await message.answer("No changes made.", reply_markup=back("adm_text_editor")); return
    if not value or len(value)>64:
        await message.answer("Button label must be between 1 and 64 characters. No changes saved.", reply_markup=back("adm_text_editor")); return
    setting_key = "button_label:" + str(key)
    set_setting(setting_key, value)
    await message.answer("✅ Button label updated. Callback behavior was not changed.", reply_markup=back("adm_text_editor"))

@dp.callback_query(F.data == "adm_edit_message_list")
async def adm_edit_message_list(q: CallbackQuery):
    if not is_admin(q.from_user.id):
        await q.answer("Access denied.", show_alert=True); return
    rows=[]
    for key,label in EDITOR_MESSAGES.items():
        rows.append([btn(label, "adm_edit_message:"+key)])
    rows.append([btn("◀️ BACK", "adm_text_editor")])
    await q.message.edit_text("💬 <b>SELECT A MESSAGE</b>\n\nChoose a message template to preview and edit.", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")
    await q.answer()

@dp.callback_query(F.data.startswith("adm_edit_message:"))
async def adm_edit_message(q: CallbackQuery, state: FSMContext):
    if not is_admin(q.from_user.id):
        await q.answer("Access denied.", show_alert=True); return
    key=q.data.split(":",1)[1]
    if key not in EDITOR_MESSAGES:
        await q.answer("Unknown message.", show_alert=True); return
    current=get_setting(key)
    await state.update_data(editor_message_key=key)
    await state.set_state(S.editor_message_value)
    await q.message.edit_text(
        "💬 <b>EDIT MESSAGE TEXT</b>\n\n"
        f"<b>Template:</b> {html.escape(EDITOR_MESSAGES[key])}\n"
        "<b>Current Message:</b>\n"
        f"<pre>{html.escape((current or '(empty)')[:3000])}</pre>\n\n"
        "Send the complete replacement text. HTML formatting supported by the bot may be used. Send /cancel to keep the current message.",
        reply_markup=back("adm_edit_message_list"), parse_mode="HTML")
    await q.answer()

@dp.message(S.editor_message_value)
async def save_editor_message(message: Message, state: FSMContext):
    data=await state.get_data(); key=data.get("editor_message_key")
    value=message.text or ""
    await state.clear()
    if value.strip().lower()=="/cancel":
        await message.answer("No changes made.", reply_markup=back("adm_text_editor")); return
    if not value.strip() or len(value)>4000:
        await message.answer("Message must be between 1 and 4000 characters. No changes saved.", reply_markup=back("adm_text_editor")); return
    set_setting(str(key), value)
    await message.answer("✅ Message template updated.", reply_markup=back("adm_text_editor"))

# =========================================================
# ADMIN MANAGEMENT
# =========================================================
@dp.callback_query(F.data == "adm_admins")
async def adm_admins(q: CallbackQuery):
    con = db()
    admins = con.execute("SELECT user_id FROM admins").fetchall()
    con.close()

    text = "👨‍💼 ADMIN MANAGEMENT\n\n"
    text += "\n".join([f"• {a['user_id']}" for a in admins])

    await q.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [btn("➕ ADD ADMIN", "add_admin")],
            [btn("🗑️ REMOVE ADMIN", "remove_admin")],
            [btn("◀️ BACK", "admin_home")]
        ])
    )
    await q.answer()


@dp.callback_query(F.data == "add_admin")
async def add_admin(q: CallbackQuery, state: FSMContext):
    await q.message.edit_text(
        "➕ ADD ADMIN\n\nTelegram ID লিখুন:",
        reply_markup=back("adm_admins")
    )
    await state.set_state(S.add_admin)
    await q.answer()


@dp.message(S.add_admin)
async def save_admin(message: Message, state: FSMContext):
    await state.clear()
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("সঠিক Telegram ID দিন।")
        return
    con = db()
    con.execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)", (uid,))
    con.commit()
    con.close()
    await message.answer("✅ Admin Added Successfully.", reply_markup=back("adm_admins"))


@dp.callback_query(F.data == "remove_admin")
async def remove_admin(q: CallbackQuery, state: FSMContext):
    await q.message.edit_text(
        "🗑️ REMOVE ADMIN\n\nTelegram ID লিখুন:",
        reply_markup=back("adm_admins")
    )
    await state.set_state(S.remove_admin)
    await q.answer()


@dp.message(S.remove_admin)
async def save_remove_admin(message: Message, state: FSMContext):
    await state.clear()
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("সঠিক Telegram ID দিন।")
        return
    if uid == ADMIN_ID:
        await message.answer("❌ Main Admin remove করা যাবে না.", reply_markup=admin_kb())
        return
    con = db()
    con.execute("DELETE FROM admins WHERE user_id=?", (uid,))
    con.commit()
    con.close()
    await message.answer("✅ Admin Removed Successfully.", reply_markup=back("adm_admins"))




# =========================================================
# ADMIN ENTRY / NAVIGATION
# =========================================================
@dp.message(Command("admin"))
async def admin_command(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("⚙️ <b>SABBIR XYZ SHOP — ADMIN PANEL</b>\n\nএকটি Section নির্বাচন করুন:", reply_markup=admin_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "admin_home")
async def admin_home(q: CallbackQuery, state: FSMContext):
    if not is_admin(q.from_user.id):
        await q.answer("Access denied.", show_alert=True); return
    await state.clear()
    await q.message.edit_text("⚙️ <b>SABBIR XYZ SHOP — ADMIN PANEL</b>\n\nএকটি Section নির্বাচন করুন:", reply_markup=admin_kb(), parse_mode="HTML")
    await q.answer()


# =========================================================
# WORKING ADMIN MANAGEMENT HANDLERS
# =========================================================
@dp.callback_query(F.data == "adm_stats")
async def admin_dashboard(q: CallbackQuery):
    if not is_admin(q.from_user.id):
        await q.answer("Access denied.", show_alert=True); return
    con = db()
    users = con.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
    banned = con.execute("SELECT COUNT(*) n FROM users WHERE banned=1").fetchone()["n"]
    products = con.execute("SELECT COUNT(*) n FROM products WHERE active=1").fetchone()["n"]
    stock = con.execute("SELECT COUNT(*) n FROM products WHERE active=1 AND stock_status=1").fetchone()["n"]
    pending = con.execute("SELECT COUNT(*) n FROM orders WHERE status='PENDING'").fetchone()["n"]
    completed = con.execute("SELECT COUNT(*) n FROM orders WHERE status='COMPLETED'").fetchone()["n"]
    rejected = con.execute("SELECT COUNT(*) n FROM orders WHERE status='REJECTED'").fetchone()["n"]
    spent = con.execute("SELECT COALESCE(SUM(price),0) n FROM orders WHERE status='COMPLETED'").fetchone()["n"]
    con.close()
    text = (
        "📊 <b>SABBIR XYZ SHOP — DASHBOARD</b>\n\n"
        f"👥 Users: <b>{users}</b>\n🚫 Banned: <b>{banned}</b>\n"
        f"📦 Active Products: <b>{products}</b>\n✅ In Stock: <b>{stock}</b>\n\n"
        f"⏳ Pending Orders: <b>{pending}</b>\n"
        f"✅ Completed: <b>{completed}</b>\n❌ Rejected: <b>{rejected}</b>\n"
        f"💰 Completed Sales: <b>৳{spent:g}</b>"
    )
    await q.message.edit_text(text, reply_markup=back("admin_home"), parse_mode="HTML")
    await q.answer()


@dp.callback_query(F.data == "adm_users")
async def admin_users(q: CallbackQuery):
    if not is_admin(q.from_user.id):
        return
    await q.message.edit_text("👥 <b>USER MANAGEMENT</b>\n\nএকটি অপশন নির্বাচন করুন:", reply_markup=user_management_kb(), parse_mode="HTML")
    await q.answer()


@dp.callback_query(F.data == "users_file")
async def admin_users_file(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    con=db(); rows=con.execute("SELECT id,name,username,balance,banned,joined_at FROM users ORDER BY joined_at DESC").fetchall(); con.close()
    lines=["USER ID,NAME,USERNAME,BALANCE,BANNED,JOINED"]
    for r in rows:
        vals=[str(r["id"]),str(r["name"] or "").replace(","," "),str(r["username"] or "").replace(","," "),str(r["balance"] or 0),str(r["banned"]),str(r["joined_at"] or "")]
        lines.append(",".join(vals))
    data="\n".join(lines).encode("utf-8")
    await q.message.answer_document(BufferedInputFile(data,filename="SABBIR_XYZ_USERS.csv"),caption=f"📄 <b>USER FILE</b>\n\n👥 Total Users: <b>{len(rows)}</b>",parse_mode="HTML")
    await q.answer("User file sent.")

@dp.callback_query(F.data == "users_all")
async def admin_users_all(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    con=db(); rows=con.execute("SELECT id,name,username,balance,banned FROM users ORDER BY joined_at DESC LIMIT 50").fetchall(); con.close()
    kb=[]
    for r in rows:
        label=f"{r['name'][:24]} • {r['id']}" + (" 🚫" if r['banned'] else "")
        kb.append([btn(label, f"user_detail:{r['id']}")])
    kb.append([btn("◀️ BACK", "adm_users")])
    await q.message.edit_text(f"👥 <b>ALL USERS</b>\n\nShowing: {len(rows)}", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    await q.answer()


@dp.callback_query(F.data.startswith("user_detail:"))
async def admin_user_detail(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    uid=int(q.data.split(":",1)[1]); con=db()
    u=con.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone()
    orders=con.execute("SELECT COUNT(*) n FROM orders WHERE user_id=?",(uid,)).fetchone()["n"] if u else 0
    spent=con.execute("SELECT COALESCE(SUM(price),0) n FROM orders WHERE user_id=? AND status='COMPLETED'",(uid,)).fetchone()["n"] if u else 0
    con.close()
    if not u:
        await q.answer("User পাওয়া যায়নি।",show_alert=True); return
    text=(f"👤 <b>USER DETAILS</b>\n\n🆔 ID: <code>{u['id']}</code>\n"
          f"👤 Name: {html.escape(str(u['name'] or 'N/A'))}\n🔗 Username: @{html.escape(str(u['username'] or 'N/A'))}\n"
          f"💰 Balance: <b>৳{u['balance']:g}</b>\n📦 Orders: {orders}\n💳 Spent: ৳{spent:g}\n"
          f"📅 Joined: {u['joined_at']}\n📌 Status: {'🚫 BANNED' if u['banned'] else '✅ ACTIVE'}")
    kb=[[btn("🚫 BAN",f"users_ban_one:{uid}"),btn("🔓 UNBAN",f"users_unban_one:{uid}")],
        [btn("💰 BALANCE",f"user_balance_one:{uid}"),btn("📦 ORDERS",f"user_orders_one:{uid}")],
        [btn("✉️ MESSAGE",f"user_message_one:{uid}")],[btn("◀️ BACK","users_all")]]
    await q.message.edit_text(text,reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),parse_mode="HTML"); await q.answer()


@dp.callback_query(F.data == "users_search")
async def admin_user_search(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    await q.message.edit_text("🔎 <b>SEARCH USER</b>\n\nTelegram ID অথবা @username লিখুন:",reply_markup=back("adm_users"),parse_mode="HTML")
    await state.set_state(S.search_user); await q.answer()


@dp.message(S.search_user)
async def save_user_search(message: Message,state:FSMContext):
    query=(message.text or "").strip().lstrip("@")
    await state.clear(); con=db()
    if query.isdigit():
        u=con.execute("SELECT * FROM users WHERE id=?",(int(query),)).fetchone()
    else:
        u=con.execute("SELECT * FROM users WHERE lower(username)=lower(?)",(query,)).fetchone()
    con.close()
    if not u:
        await message.answer("❌ User পাওয়া যায়নি।",reply_markup=back("adm_users")); return
    await message.answer(f"👤 User পাওয়া গেছে: <b>{html.escape(str(u['name']))}</b>\n🆔 <code>{u['id']}</code>\n💰 ৳{u['balance']:g}",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("👤 OPEN USER",f"user_detail:{u['id']}" )],[btn("◀️ BACK","adm_users")]]),parse_mode="HTML")


@dp.callback_query(F.data == "users_ban")
async def admin_ban_menu(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    await q.message.edit_text("🚫 <b>BAN USER</b>\n\nTelegram ID লিখুন:",reply_markup=back("adm_users"),parse_mode="HTML"); await state.set_state(S.ban_user); await q.answer()

@dp.message(S.ban_user)
async def admin_ban_save(message: Message,state:FSMContext):
    try: uid=int((message.text or "").strip())
    except: await message.answer("❌ সঠিক Telegram ID দিন।",reply_markup=back("adm_users")); return
    if uid==ADMIN_ID: await state.clear(); await message.answer("❌ Main Admin ban করা যাবে না।",reply_markup=back("adm_users")); return
    await state.update_data(ban_uid=uid)
    await state.set_state(S.ban_reason)
    await message.answer("📝 <b>BAN REASON</b>\n\nকারণ লিখুন। কারণ না দিতে চাইলে নিচের <b>⏭️ SKIP</b> চাপুন বা <code>/skip</code> পাঠান।",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("⏭️ SKIP", "ban_skip_reason")],[btn("◀️ BACK", "adm_users")]]),parse_mode="HTML")

@dp.callback_query(F.data.startswith("users_ban_one:"))
async def admin_ban_one(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    uid=int(q.data.split(":")[1])
    if uid==ADMIN_ID: await q.answer("Main Admin ban করা যাবে না।",show_alert=True); return
    await state.update_data(ban_uid=uid,ban_return="users_all")
    await state.set_state(S.ban_reason)
    await q.message.edit_text("📝 <b>BAN REASON</b>\n\nকারণ লিখুন। কারণ না দিতে চাইলে নিচের <b>⏭️ SKIP</b> চাপুন বা <code>/skip</code> পাঠান।",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("⏭️ SKIP", "ban_skip_reason")],[btn("◀️ BACK", "users_all")]]),parse_mode="HTML"); await q.answer()

@dp.callback_query(F.data == "ban_skip_reason")
async def ban_skip_reason(q: CallbackQuery, state:FSMContext):
    if not is_admin(q.from_user.id): return
    data=await state.get_data(); await state.update_data(ban_reason="")
    await state.set_state(S.ban_contact)
    await q.message.edit_text("🔗 <b>CONTACT ADMIN LINK</b>\n\nএই Ban-এর জন্য আলাদা Contact Link দিতে চাইলে পাঠান।\nনা দিলে নিচের <b>⏭️ SKIP</b> চাপুন—Admin Settings-এর default link ব্যবহার হবে।",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("⏭️ SKIP", "ban_skip_contact")],[btn("◀️ BACK", data.get("ban_return","adm_users"))]]),parse_mode="HTML"); await q.answer()

@dp.message(S.ban_reason)
async def admin_ban_reason(message: Message,state:FSMContext):
    data=await state.get_data(); reason=(message.text or "").strip()
    if reason.lower()=="/skip": reason=""
    await state.update_data(ban_reason=reason)
    await state.set_state(S.ban_contact)
    await message.answer("🔗 <b>CONTACT ADMIN LINK</b>\n\nএই Ban-এর জন্য আলাদা Contact Link পাঠান।\nনা দিলে <code>/skip</code> পাঠান—Admin Settings-এর default link ব্যবহার হবে।",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("⏭️ SKIP", "ban_skip_contact")],[btn("◀️ BACK", data.get("ban_return","adm_users"))]]),parse_mode="HTML")

@dp.callback_query(F.data == "ban_skip_contact")
async def ban_skip_contact(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    data=await state.get_data(); await finalize_ban(q.from_user.id,int(data.get("ban_uid",0)),data.get("ban_reason", ""),"",state)
    await q.message.edit_text("🚫 <b>User Banned Successfully.</b>",reply_markup=back(data.get("ban_return","adm_users")),parse_mode="HTML"); await q.answer()

@dp.message(S.ban_contact)
async def admin_ban_contact(message: Message,state:FSMContext):
    data=await state.get_data(); link=(message.text or "").strip()
    if link.lower()=="/skip": link=""
    uid=int(data.get("ban_uid",0))
    await finalize_ban(message.from_user.id,uid,data.get("ban_reason", ""),link,state)
    await message.answer("🚫 <b>User Banned Successfully.</b>",reply_markup=back(data.get("ban_return","adm_users")),parse_mode="HTML")

async def finalize_ban(admin_uid, uid, reason, contact_link, state):
    if not is_admin(admin_uid) or not uid:
        await state.clear(); return
    con=db(); row=con.execute("SELECT id FROM users WHERE id=?",(uid,)).fetchone()
    if not row:
        con.close(); await state.clear(); return
    con.execute("UPDATE users SET banned=1 WHERE id=?",(uid,)); con.commit(); con.close(); await state.clear()
    await notify_user_banned(uid,reason,contact_link)

@dp.callback_query(F.data == "users_unban")
async def admin_unban_menu(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    await q.message.edit_text("🔓 <b>UNBAN USER</b>\n\nTelegram ID লিখুন:",reply_markup=back("adm_users"),parse_mode="HTML"); await state.set_state(S.unban_user); await q.answer()

@dp.message(S.unban_user)
async def admin_unban_save(message: Message,state:FSMContext):
    await state.clear()
    try: uid=int((message.text or "").strip())
    except: await message.answer("❌ সঠিক Telegram ID দিন।",reply_markup=back("adm_users")); return
    con=db(); row=con.execute("SELECT banned FROM users WHERE id=?",(uid,)).fetchone(); con.execute("UPDATE users SET banned=0 WHERE id=?",(uid,)); con.commit(); con.close()
    await notify_user_unbanned(uid)
    await message.answer("🔓 User Unbanned Successfully.",reply_markup=back("adm_users"))

@dp.callback_query(F.data.startswith("users_unban_one:"))
async def admin_unban_one(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    uid=int(q.data.split(":")[1]); con=db(); con.execute("UPDATE users SET banned=0 WHERE id=?",(uid,)); con.commit(); con.close(); await notify_user_unbanned(uid); await q.answer("User unbanned."); await q.message.edit_text("🔓 User Unbanned Successfully.",reply_markup=back("users_all"))

async def notify_user_unbanned(uid):
    try:
        link=get_setting("ban_contact_link") or get_setting("owner_link")
        rows=[]
        if link and link.startswith(("http://","https://","tg://")):
            rows.append([url_btn("📞 CONTACT ADMIN",link)])
        try:
            me=await bot.get_me()
            if me.username:
                rows.append([url_btn("🔄 /start BOT",f"https://t.me/{me.username}?start=1")])
        except Exception:
            pass
        kb=InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
        await bot.send_message(uid,"🔓 <b>ACCOUNT UNBANNED</b>\n\n✅ তোমার Account আবার Unbanned করা হয়েছে।\nএখন তুমি Bot-এর সব সুবিধা ব্যবহার করতে পারবে।",reply_markup=kb,parse_mode="HTML")
    except Exception:
        logging.exception("Failed to send unban notification to %s",uid)


@dp.callback_query(F.data == "users_balance")
async def admin_balance_menu(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    await q.message.edit_text("💰 <b>BALANCE / TRANSFER</b>\n\nআগে Telegram ID দিন:",reply_markup=back("adm_users"),parse_mode="HTML"); await state.set_state(S.wallet_user); await q.answer()

@dp.message(S.wallet_user)
async def admin_balance_user(message: Message,state:FSMContext):
    try: uid=int((message.text or "").strip())
    except: await message.answer("❌ সঠিক Telegram ID দিন।"); return
    con=db(); u=con.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone(); con.close()
    if not u: await message.answer("❌ User পাওয়া যায়নি।",reply_markup=back("adm_users")); await state.clear(); return
    await state.update_data(uid=uid); await state.set_state(S.wallet_amount); await message.answer("💰 Amount লিখুন।\nAdd করতে positive (যেমন 100), remove করতে negative (যেমন -50):")

async def send_balance_transfer_notification(uid, u, amount, new_balance, admin_name, note=""):
    direction = "যোগ করা হয়েছে" if amount >= 0 else "কমানো হয়েছে"
    icon = "🎉" if amount >= 0 else "⚠️"
    lines = [
        f"{icon} <b>WALLET BALANCE UPDATED</b>",
        "",
        f"💰 Amount: <b>{abs(amount):g} Tk</b>",
        f"💳 Current Balance: <b>{new_balance:g} Tk</b>",
        f"👨‍💼 Admin: <b>{html.escape(str(admin_name or 'Admin'))}</b>",
    ]
    if note:
        lines += ["", f"📝 Message: {html.escape(note)}"]
    lines += ["", f"✅ {abs(amount):g} Tk আপনার Wallet-এ {direction}।"]
    await bot.send_message(
        uid,
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("👤 BACK TO PROFILE", "profile")]])
    )


@dp.message(S.wallet_amount)
async def admin_balance_amount(message: Message,state:FSMContext):
    try: amount=float((message.text or "").strip())
    except: await message.answer("❌ সঠিক amount দিন।"); return
    if amount == 0:
        await message.answer("❌ Amount 0 হতে পারবে না।"); return
    data=await state.get_data(); uid=data["uid"]
    con=db(); u=con.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone()
    if not u: con.close(); await state.clear(); await message.answer("❌ User পাওয়া যায়নি।"); return
    new=max(0,float(u["balance"])+amount)
    con.execute("UPDATE users SET balance=? WHERE id=?",(new,uid)); con.commit(); con.close()
    admin_label = message.from_user.full_name or "Admin"
    if message.from_user.username:
        admin_label += f" (@{message.from_user.username})"
    await state.update_data(amount=amount,new_balance=new,admin_name=admin_label)
    await state.set_state(S.wallet_message)
    await message.answer(
        "📝 <b>Optional Message</b>\n\nUser-কে কোনো Message দিতে চাইলে লিখুন।\nনা চাইলে নিচের <b>⏭️ SKIP</b> চাপুন বা <code>/skip</code> লিখুন।",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("⏭️ SKIP", "message_user_skip")],[btn("◀️ BACK", "adm_users")]])
    )


@dp.message(S.wallet_message)
async def admin_balance_message(message: Message,state:FSMContext):
    data=await state.get_data()
    uid=data.get("uid"); amount=float(data.get("amount",0)); new=float(data.get("new_balance",0)); admin_name=data.get("admin_name") or message.from_user.full_name
    note=(message.text or "").strip()
    if note == "/skip": note=""
    await state.clear()
    try:
        await send_balance_transfer_notification(uid, None, amount, new, admin_name, note)
    except Exception:
        logging.exception("Balance transfer notification failed")
    await message.answer(f"✅ Balance updated.\n💰 New Balance: {new:g} Tk",reply_markup=back("adm_users"))

@dp.callback_query(F.data.startswith("user_balance_one:"))
async def admin_balance_one(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    uid=int(q.data.split(":")[1]); await state.update_data(uid=uid); await state.set_state(S.wallet_amount); await q.message.edit_text(f"💰 User <code>{uid}</code>\n\nAmount দিন। Add: 100 | Remove: -50",reply_markup=back("adm_users"),parse_mode="HTML"); await q.answer()


@dp.callback_query(F.data == "users_orders")
async def admin_users_orders(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    await q.message.edit_text("📦 <b>USER ORDERS</b>\n\nTelegram ID লিখে দেখুন:",reply_markup=back("adm_users"),parse_mode="HTML"); await q.answer()

@dp.callback_query(F.data.startswith("user_orders_one:"))
async def admin_user_orders_one(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    uid=int(q.data.split(":")[1]); con=db(); rows=con.execute("SELECT o.id,o.price,o.status,o.created_at,p.name FROM orders o LEFT JOIN products p ON p.id=o.product_id WHERE o.user_id=? ORDER BY o.id DESC LIMIT 30",(uid,)).fetchall(); con.close()
    text=f"📦 <b>ORDERS — {uid}</b>\n\n"+ ("\n".join(f"#{r['id']} • {html.escape(str(r['name'] or 'Deleted'))} • ৳{r['price']:g} • {r['status']}" for r in rows) if rows else "No orders.")
    await q.message.edit_text(text,reply_markup=back(f"user_detail:{uid}"),parse_mode="HTML"); await q.answer()

@dp.callback_query(F.data == "users_stats")
async def admin_user_stats(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    con=db(); total=con.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]; verified=con.execute("SELECT COUNT(*) n FROM users WHERE verified=1").fetchone()["n"]; banned=con.execute("SELECT COUNT(*) n FROM users WHERE banned=1").fetchone()["n"]; balance=con.execute("SELECT COALESCE(SUM(balance),0) n FROM users").fetchone()["n"]; con.close()
    await q.message.edit_text(f"📊 <b>USER STATS</b>\n\n👥 Total: {total}\n✅ Verified: {verified}\n🚫 Banned: {banned}\n💰 Wallet Liability: ৳{balance:g}",reply_markup=back("adm_users"),parse_mode="HTML"); await q.answer()

@dp.callback_query(F.data.startswith("user_message_one:"))
async def admin_message_one(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    uid=int(q.data.split(":")[1]); await state.update_data(uid=uid); await state.set_state(S.message_user); await q.message.edit_text("✉️ User-কে যে message পাঠাতে চান লিখুন:",reply_markup=back("adm_users")); await q.answer()

@dp.callback_query(F.data == "users_message")
async def admin_message_menu(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    await q.message.edit_text("✉️ <b>MESSAGE USER</b>\n\nTelegram ID দিন:",reply_markup=back("adm_users"),parse_mode="HTML"); await state.set_state(S.message_user); await q.answer()

@dp.callback_query(F.data == "message_user_skip")
async def message_user_skip(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    data=await state.get_data()
    uid=data.get("uid")
    amount=float(data.get("amount",0))
    new=float(data.get("new_balance",0))
    admin_name=data.get("admin_name") or q.from_user.full_name
    await state.clear()
    if uid:
        try: await send_balance_transfer_notification(uid,None,amount,new,admin_name,"")
        except Exception: logging.exception("Balance transfer notification failed")
    await q.message.edit_text("✅ Balance updated.",reply_markup=back("adm_users")); await q.answer()

@dp.message(S.message_user)
async def admin_message_user(message: Message,state:FSMContext):
    data=await state.get_data()
    if "uid" not in data:
        try: uid=int((message.text or "").strip())
        except: await message.answer("❌ সঠিক Telegram ID দিন।"); return
        await state.update_data(uid=uid); await message.answer("এখন message লিখুন:"); return
    uid=data["uid"]; await state.clear()
    try: await bot.send_message(uid,message.text); await message.answer("✅ Message Sent.",reply_markup=back("adm_users"))
    except Exception as e: await message.answer("❌ Message পাঠানো যায়নি।",reply_markup=back("adm_users"))


@dp.callback_query(F.data == "adm_products")
async def admin_products(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    await q.message.edit_text("📦 <b>PRODUCT MANAGEMENT</b>\n\nProduct-এর কাজ নির্বাচন করুন:",reply_markup=product_management_kb(),parse_mode="HTML"); await q.answer()

@dp.callback_query(F.data == "product_add")
async def admin_product_add(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    await state.clear(); await q.message.edit_text("➕ <b>ADD PRODUCT</b>\n\nআপনি কোন ধরনের Product Add করতে চান?",reply_markup=add_product_type_kb(),parse_mode="HTML"); await q.answer()


@dp.callback_query(F.data.startswith("product_type:"))
async def admin_product_type(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    kind=q.data.split(":")[1]
    await state.clear(); await state.update_data(product_type=kind)
    await state.set_state(S.add_name)
    await q.message.edit_text(("📱 <b>APK PRODUCT</b>\n\n1️⃣ APK Name দিন:" if kind=="apk" else "📦 <b>FILE / VIDEO / OTHER</b>\n\n1️⃣ Product Name দিন:"),reply_markup=back("adm_products"),parse_mode="HTML"); await q.answer()


@dp.message(S.add_name)
async def admin_add_name(message: Message,state:FSMContext):
    v=(message.text or "").strip()
    if not v: await message.answer("❌ Product Name দিন।"); return
    data=await state.get_data(); await state.update_data(name=v)
    if data.get("product_type")=="apk":
        await state.set_state(S.apk_url); await message.answer("2️⃣ 📥 APK Download Link দিন (https://...):")
    else:
        await state.set_state(S.add_price); await message.answer("2️⃣ 💰 Price (৳) দিন:")


@dp.message(S.add_price)
async def admin_add_price(message: Message,state:FSMContext):
    try: price=float((message.text or "").strip())
    except: await message.answer("❌ শুধু Price-এর সংখ্যা দিন।"); return
    if price<0: await message.answer("❌ Price 0-এর কম হতে পারবে না।"); return
    await state.update_data(price=price); await state.set_state(S.add_features); await message.answer("3️⃣ ✨ Features দিন।\nপ্রতি Feature নতুন লাইনে লিখুন। /skip দিলে বাদ যাবে।", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("⏭️ SKIP", "add_features_skip")],[btn("◀️ BACK", "adm_products")]]))


@dp.message(S.add_features)
async def admin_add_features(message: Message,state:FSMContext):
    v=(message.text or "").strip(); await state.update_data(features="" if v=="/skip" else v); await state.set_state(S.add_demo); await message.answer("4️⃣ 🎬 Demo Photo/Video পাঠান, অথবা /skip লিখুন:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("⏭️ SKIP", "add_demo_skip")],[btn("◀️ BACK", "adm_products")]]))


@dp.callback_query(F.data == "add_features_skip")
async def add_features_skip(q: CallbackQuery, state:FSMContext):
    if not is_admin(q.from_user.id): return
    await state.update_data(features="")
    await state.set_state(S.add_demo)
    await q.message.edit_text("4️⃣ 🎬 Demo Photo/Video পাঠান, অথবা নিচের SKIP চাপুন:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("⏭️ SKIP", "add_demo_skip")],[btn("◀️ BACK", "adm_products")]]))
    await q.answer()

@dp.callback_query(F.data == "add_demo_skip")
async def add_demo_skip(q: CallbackQuery, state:FSMContext):
    if not is_admin(q.from_user.id): return
    await state.update_data(demo_file_id=None,demo_type=None)
    data=await state.get_data()
    if data.get("product_type")=="apk":
        await state.set_state(S.apk_plan_count)
        await q.message.edit_text("4️⃣ 📊 কয়টি Plan থাকবে? শুধু সংখ্যা দিন।\nExample: 3")
    else:
        await state.set_state(S.add_validity)
        await q.message.edit_text("5️⃣ ⏳ Product Validity / Duration দিন।\nExample: 1 Hour / 1 Day / 7 Days / 1 Month")
    await q.answer()

@dp.message(S.add_demo)
async def admin_add_demo(message: Message,state:FSMContext):
    if message.text and message.text.strip()=="/skip": await state.update_data(demo_file_id=None,demo_type=None)
    elif message.photo: await state.update_data(demo_file_id=message.photo[-1].file_id,demo_type="photo")
    elif message.video: await state.update_data(demo_file_id=message.video.file_id,demo_type="video")
    else: await message.answer("❌ Photo/Video দিন অথবা /skip লিখুন।"); return
    data=await state.get_data()
    if data.get("product_type")=="apk":
        await state.set_state(S.apk_plan_count); await message.answer("3️⃣ 🎬 Demo saved.\n\n4️⃣ 📊 কয়টি Plan থাকবে? শুধু সংখ্যা দিন।\nExample: 3")
    else:
        await state.set_state(S.add_validity); await message.answer("5️⃣ ⏳ Product Validity / Duration দিন।\nExample: 1 Hour / 1 Day / 7 Days / 1 Month")


@dp.message(S.add_validity)
async def admin_add_validity(message: Message,state:FSMContext):
    v=(message.text or "").strip()
    if not v or v=="/skip": await message.answer("❌ Validity অবশ্যই দিতে হবে। Example: 1 Day"); return
    await state.update_data(validity=v); await state.set_state(S.add_device_limit); await message.answer("6️⃣ 📱 কয়টি Device চলবে? সংখ্যা দিন।\nExample: 1")


@dp.message(S.add_device_limit)
async def admin_add_device_limit(message: Message,state:FSMContext):
    v=(message.text or "").strip()
    try:
        n=int(v)
        if n<1: raise ValueError
    except Exception:
        await message.answer("❌ Device সংখ্যা 1 বা তার বেশি দিন। Example: 1"); return
    await state.update_data(device_limit=str(n)); await state.set_state(S.add_delivery); await message.answer("7️⃣ 📦 Delivery Product Message পাঠান/Forward করুন।\nএটাই Customer-এর কাছে delivery হবে।")


@dp.message(S.add_delivery)
async def admin_add_delivery(message: Message,state:FSMContext):
    data=await state.get_data(); dtype="copy"; ddata=json.dumps({"chat_id":message.chat.id,"message_id":message.message_id})
    con=db(); cur=con.execute("INSERT INTO products(name,price,description,demo_file_id,demo_type,delivery_type,delivery_data,validity,device_limit,features,stock_status,product_type,apk_url,active) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(data["name"],data["price"],"",data.get("demo_file_id"),data.get("demo_type"),dtype,ddata,data["validity"],data.get("device_limit",""),data.get("features",""),1,"standard","",1)); con.commit(); pid=cur.lastrowid; con.close(); await state.clear(); await message.answer(f"✅ <b>Product Added Successfully</b>\n\n📦 {html.escape(data['name'])}\n⏳ {html.escape(data['validity'])}\n💰 ৳{data['price']:g} TK\n🆔 Product ID: <code>{pid}</code>",reply_markup=back("adm_products"),parse_mode="HTML")


@dp.message(S.apk_url)
async def admin_apk_url(message: Message,state:FSMContext):
    url=(message.text or "").strip()
    if not (url.startswith("https://") or url.startswith("http://")):
        await message.answer("❌ Valid APK Download Link দিন। https:// দিয়ে শুরু হতে হবে।"); return
    await state.update_data(apk_url=url); await state.set_state(S.apk_demo); await message.answer("3️⃣ 🎬 Demo Photo/Video পাঠান অথবা /skip লিখুন।\nDemo দিলে User-এর কাছে 🎬 DEMO VIDEO button দেখাবে; না দিলে button দেখাবে না।", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn("⏭️ SKIP", "apk_demo_skip")],[btn("◀️ BACK", "adm_products")]]))


@dp.callback_query(F.data == "apk_demo_skip")
async def apk_demo_skip(q: CallbackQuery, state:FSMContext):
    if not is_admin(q.from_user.id): return
    await state.update_data(demo_file_id=None,demo_type=None)
    await state.set_state(S.apk_plan_count)
    await q.message.edit_text("4️⃣ 📊 কয়টি Plan থাকবে? শুধু সংখ্যা দিন।\nExample: 3")
    await q.answer()

@dp.message(S.apk_demo)
async def admin_apk_demo(message: Message,state:FSMContext):
    if message.text and message.text.strip()=="/skip": await state.update_data(demo_file_id=None,demo_type=None)
    elif message.video: await state.update_data(demo_file_id=message.video.file_id,demo_type="video")
    elif message.photo: await state.update_data(demo_file_id=message.photo[-1].file_id,demo_type="photo")
    else: await message.answer("❌ Demo Photo/Video পাঠান অথবা /skip লিখুন।"); return
    await state.set_state(S.apk_plan_count); await message.answer("4️⃣ 📊 কয়টি Plan থাকবে? শুধু সংখ্যা দিন।\nExample: 3")


@dp.message(S.apk_plan_count)
async def admin_apk_plan_count(message: Message,state:FSMContext):
    try: count=int((message.text or "").strip())
    except: await message.answer("❌ শুধু সংখ্যা দিন। Example: 3"); return
    if count<1 or count>20: await message.answer("❌ Plan 1 থেকে 20-এর মধ্যে হতে হবে।"); return
    await state.update_data(plan_count=count,plan_index=1,plans=[]); await state.set_state(S.apk_plan_validity); await message.answer("📋 <b>PLAN 1/{}</b>\n\n⏳ Validity / Duration দিন।\nExample: 1 Hour / 1 Day / 7 Days".format(count),parse_mode="HTML")


@dp.message(S.apk_plan_validity)
async def admin_apk_plan_validity(message: Message,state:FSMContext):
    v=(message.text or "").strip()
    if not v: await message.answer("❌ Validity দিন।"); return
    await state.update_data(current_validity=v); await state.set_state(S.apk_plan_price); await message.answer("💰 এই Plan-এর Price (৳) দিন:")


@dp.message(S.apk_plan_price)
async def admin_apk_plan_price(message: Message,state:FSMContext):
    try: price=float((message.text or "").strip())
    except: await message.answer("❌ সঠিক Price দিন।"); return
    if price<0: await message.answer("❌ Price 0-এর কম হতে পারবে না।"); return
    await state.update_data(current_price=price); await state.set_state(S.apk_plan_device); await message.answer("📱 এই Plan-এ কয়টি Device চলবে? সংখ্যা দিন।\nExample: 1")


@dp.message(S.apk_plan_device)
async def admin_apk_plan_device(message: Message,state:FSMContext):
    v=(message.text or "").strip()
    try:
        n=int(v)
        if n<1: raise ValueError
    except Exception:
        await message.answer("❌ Device সংখ্যা 1 বা তার বেশি দিন। Example: 1"); return
    await state.update_data(current_device=str(n)); await state.set_state(S.apk_plan_stock_count); await message.answer("📦 এই Plan-এ কয়টি Password/Stock থাকবে?\nExample: 5")


@dp.message(S.apk_plan_stock_count)
async def admin_apk_plan_stock_count(message: Message,state:FSMContext):
    try:
        count=int((message.text or "").strip())
        if count<1 or count>500: raise ValueError
    except Exception:
        await message.answer("❌ Stock সংখ্যা 1 থেকে 500-এর মধ্যে দিন।"); return
    await state.update_data(current_stock_count=count,current_passwords=[],password_index=1); await state.set_state(S.apk_plan_password); await message.answer(f"🔐 Password 1/{count} দিন:")


@dp.message(S.apk_plan_password)
async def admin_apk_plan_password(message: Message,state:FSMContext):
    data=await state.get_data(); passwords=list(data.get("current_passwords",[]))
    # Accept many passwords at once, one per line (e.g. 098\n008\nJJH\nHKK).
    incoming=[x.strip() for x in (message.text or "").splitlines() if x.strip()]
    if not incoming: await message.answer("❌ Password দিন। প্রতি লাইনে একটি করে Password দিতে পারেন।"); return
    for password in incoming:
        if password in passwords: continue
        passwords.append(password)
    total=int(data["current_stock_count"]); plan_idx=int(data["plan_index"]); plan_count=int(data["plan_count"])
    if len(passwords)<total:
        await state.update_data(current_passwords=passwords,password_index=len(passwords)+1); await message.answer(f"🔐 আরও {total-len(passwords)}টি Password দিন। চাইলে একসাথে প্রতি লাইনে একটি করে দিতে পারেন।"); return
    passwords=passwords[:total]
    plans=list(data.get("plans",[]))
    plans.append({"validity":data["current_validity"],"price":float(data["current_price"]),"device_limit":data["current_device"],"passwords":passwords})
    if plan_idx<plan_count:
        await state.update_data(plans=plans,plan_index=plan_idx+1,current_passwords=[],password_index=1)
        await state.set_state(S.apk_plan_validity)
        await message.answer(f"📋 <b>PLAN {plan_idx+1}/{plan_count}</b>\n\n⏳ Validity / Duration দিন।\nExample: 1 Hour / 1 Day / 7 Days",parse_mode="HTML")
        return

    # Finalize APK product with one stock row per password.
    # Use one transaction so a failed final save cannot leave a broken/partial product.
    con = db()
    try:
        cur = con.execute(
            "INSERT INTO products(name,price,description,demo_file_id,demo_type,delivery_type,delivery_data,validity,device_limit,features,stock_status,product_type,apk_url,active) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (data["name"], 0, "", data.get("demo_file_id"), data.get("demo_type"), "", "", "", "", "", 1, "apk", data["apk_url"], 1)
        )
        pid = cur.lastrowid
        for plan in plans:
            cur2 = con.execute(
                "INSERT INTO apk_plans(product_id,validity,price,password,device_limit,stock_status,active) VALUES(?,?,?,?,?,1,1)",
                (pid, plan["validity"], plan["price"], plan["passwords"][0], plan["device_limit"])
            )
            plan_id = cur2.lastrowid
            for pw in plan["passwords"]:
                con.execute(
                    "INSERT INTO apk_stock(plan_id,password,status,created_at) VALUES(?,?,?,?)",
                    (plan_id, pw, "AVAILABLE", datetime.now().isoformat())
                )
            sync_apk_plan_stock(con, plan_id)
        con.commit()
    except Exception:
        con.rollback()
        logging.exception("APK product creation failed")
        await message.answer(
            "❌ <b>APK Product তৈরি করা যায়নি।</b>\n\n"
            "শেষ Password নেওয়ার সময় Database Error হয়েছে।\n"
            "আবার চেষ্টা করুন।",
            parse_mode="HTML",
            reply_markup=back("adm_products")
        )
        return
    finally:
        con.close()

    await state.clear()
    await message.answer(
        f"✅ <b>APK PRODUCT ADDED SUCCESSFULLY</b>\n\n"
        f"📱 {html.escape(data['name'])}\n"
        f"📊 Plans: <b>{plan_count}</b>\n"
        f"📦 Total Password Stock: <b>{sum(len(x['passwords']) for x in plans)}</b>\n"
        f"🔗 APK Link Saved\n"
        f"🎬 Demo: {'✅ Added' if data.get('demo_file_id') else '❌ Not Added'}",
        reply_markup=back("adm_products"),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "product_all")
async def admin_product_all(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    con=db(); rows=con.execute("SELECT * FROM products WHERE active=1 ORDER BY id DESC").fetchall(); con.close(); kb=[]
    for r in rows:
        if r["product_type"] == "apk":
            con2=db(); pc=con2.execute("SELECT COUNT(*) n FROM apk_plans WHERE product_id=? AND active=1",(r["id"],)).fetchone()["n"]
            sc=con2.execute("SELECT COUNT(*) n FROM apk_stock s JOIN apk_plans ap ON ap.id=s.plan_id WHERE ap.product_id=? AND ap.active=1 AND s.status='AVAILABLE' AND s.active=1",(r["id"],)).fetchone()["n"]; con2.close()
            kb.append([btn(f"📱 {r['name'][:25]} • {pc} Plans • {sc} Stock",f"product_manage:{r['id']}")])
        else:
            kb.append([btn(f"📦 {r['name'][:30]} • ৳{r['price']:g} • {'IN' if r['stock_status'] else 'OUT'}",f"product_manage:{r['id']}")])
    kb.append([btn("◀️ BACK","adm_products")]); text="📋 <b>ALL PRODUCTS</b>\n\n"+(f"Total: {len(rows)}" if rows else "No products.")
    await q.message.edit_text(text,reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),parse_mode="HTML"); await q.answer()

@dp.callback_query(F.data == "product_edit")
async def admin_product_edit(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    await admin_product_all(q)

@dp.callback_query(F.data == "product_delete")
async def admin_product_delete_menu(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    await admin_product_all(q)

@dp.callback_query(F.data == "product_delivery")
async def admin_product_delivery_menu(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    await admin_product_all(q)

@dp.callback_query(F.data.startswith("product_manage:"))
async def admin_product_manage(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    pid=int(q.data.split(":")[1]); con=db(); p=con.execute("SELECT * FROM products WHERE id=?",(pid,)).fetchone(); plans=con.execute("SELECT * FROM apk_plans WHERE product_id=? AND active=1 ORDER BY id",(pid,)).fetchall() if p and p["product_type"]=="apk" else []; con.close()
    if not p: await q.answer("Product নেই।",show_alert=True); return
    if p["product_type"]=="apk":
        lines=[f"📱 <b>{html.escape(str(p['name']))}</b>","",f"🔗 APK Link: {html.escape(str(p['apk_url'] or 'N/A'))}",f"🎬 Demo: {'✅ Added' if p['demo_file_id'] else '❌ Not Added'}","","📊 <b>PLANS</b>","━━━━━━━━━━━━━━━━━━"]
        for pl in plans:
            available=apk_stock_count(pl["id"])
            lines += [f"{'✅' if available else '❌'} {html.escape(str(pl['validity']))} — ৳{pl['price']:g} — {'IN' if available else 'OUT'} • {available} stock"]
        kb=[[btn("📊 MANAGE PLANS",f"manage_plans:{pid}"),btn("🎬 CHANGE DEMO",f"change_demo:{pid}")],[btn("🔗 CHANGE APK LINK",f"change_apk_link:{pid}")],[btn("🗑️ DELETE",f"delete_product:{pid}")],[btn("◀️ BACK","product_all")]]
    else:
        text=(f"📦 <b>{html.escape(str(p['name']))}</b>\n\n💰 Price: <b>৳{p['price']:g}</b>\n⏳ Validity: {html.escape(str(p['validity'] or 'N/A'))}\n📱 Device: {html.escape(str(p['device_limit'] or 'N/A'))}\n✨ Features: {html.escape(str(p['features'] or 'N/A'))}\n📦 Stock: {'✅ IN STOCK' if p['stock_status'] else '❌ OUT OF STOCK'}")
        lines=[text]
        kb=[[btn("💰 CHANGE PRICE",f"change_price:{pid}"),btn("🎬 CHANGE DEMO",f"change_demo:{pid}")],[btn("📦 CHANGE DELIVERY",f"change_delivery:{pid}"),btn("🔄 STOCK ON/OFF",f"toggle_stock:{pid}")],[btn("🗑️ DELETE",f"delete_product:{pid}")],[btn("◀️ BACK","product_all")]]
    await q.message.edit_text("\n".join(lines),reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),parse_mode="HTML"); await q.answer()


@dp.callback_query(F.data.startswith("manage_plans:"))
async def manage_plans(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    pid=int(q.data.split(":")[1]); con=db(); rows=con.execute("SELECT * FROM apk_plans WHERE product_id=? AND active=1 ORDER BY id",(pid,)).fetchall(); con.close()
    kb=[]
    for r in rows:
        available=apk_stock_count(r["id"])
        kb.append([btn(f"{'✅' if available else '❌'} {r['validity']} • ৳{r['price']:g} • {available} Stock",f"plan_manage:{r['id']}")])
    kb.append([btn("➕ ADD PLAN",f"add_plan:{pid}")]); kb.append([btn("◀️ BACK",f"product_manage:{pid}")])
    await q.message.edit_text("📊 <b>APK PLANS</b>\n\nAdmin-এর জন্য Available Stock count দেখানো হচ্ছে:",reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),parse_mode="HTML"); await q.answer()


@dp.callback_query(F.data.startswith("plan_manage:"))
async def plan_manage(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    plan_id=int(q.data.split(":")[1]); con=db(); r=con.execute("SELECT ap.*,p.name FROM apk_plans ap JOIN products p ON p.id=ap.product_id WHERE ap.id=?",(plan_id,)).fetchone(); available=con.execute("SELECT COUNT(*) n FROM apk_stock WHERE plan_id=? AND status='AVAILABLE' AND active=1",(plan_id,)).fetchone()["n"] if r else 0; sold=con.execute("SELECT COUNT(*) n FROM apk_stock WHERE plan_id=? AND status='SOLD' AND active=1",(plan_id,)).fetchone()["n"] if r else 0; con.close()
    if not r: await q.answer("Plan নেই।",show_alert=True); return
    text=(f"📱 <b>{html.escape(str(r['name']))}</b>\n\n⏳ Validity: <b>{html.escape(str(r['validity']))}</b>\n💰 Price: <b>৳{r['price']:g}</b>\n📱 Device Limit: <b>{html.escape(str(r['device_limit'] or 'N/A'))}</b>\n📦 Available Stock: <b>{available}</b>\n📤 Sold: <b>{sold}</b>\n📊 Status: <b>{'IN STOCK' if available else 'STOCK OUT'}</b>")
    kb=[[btn("💰 CHANGE PRICE",f"plan_price:{plan_id}"),btn("⏳ CHANGE VALIDITY",f"plan_validity:{plan_id}")],[btn("📱 CHANGE DEVICE",f"plan_device:{plan_id}"),btn("🔐 ADD PASSWORDS",f"plan_add_stock:{plan_id}")],[btn("📦 VIEW STOCK",f"plan_stock_list:{plan_id}"),btn("🗑️ DELETE PLAN",f"plan_delete:{plan_id}")],[btn("◀️ BACK",f"manage_plans:{r['product_id']}")]]
    await q.message.edit_text(text,reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),parse_mode="HTML"); await q.answer()


@dp.callback_query(F.data.startswith("add_plan:"))
async def add_plan_start(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    pid=int(q.data.split(":")[1]); await state.update_data(pid=pid); await state.set_state(S.add_plan_validity); await q.message.edit_text("⏳ New Plan Validity / Duration দিন:",reply_markup=back(f"manage_plans:{pid}")); await q.answer()
@dp.message(S.add_plan_validity)
async def add_plan_validity(message: Message,state:FSMContext):
    v=(message.text or "").strip()
    if not v: await message.answer("❌ Validity দিন।"); return
    await state.update_data(plan_validity=v); await state.set_state(S.add_plan_price); await message.answer("💰 New Plan Price (৳) দিন:")
@dp.message(S.add_plan_price)
async def add_plan_price(message: Message,state:FSMContext):
    try: value=float((message.text or "").strip())
    except: await message.answer("❌ সঠিক Price দিন।"); return
    if value<0: await message.answer("❌ Price 0-এর কম হতে পারবে না।"); return
    await state.update_data(plan_price=value); await state.set_state(S.add_plan_device); await message.answer("📱 New Plan-এ কয়টি Device চলবে? Example: 1")
@dp.message(S.add_plan_device)
async def add_plan_device(message: Message,state:FSMContext):
    v=(message.text or "").strip()
    try:
        n=int(v)
        if n<1: raise ValueError
    except Exception:
        await message.answer("❌ Device সংখ্যা 1 বা তার বেশি দিন।"); return
    await state.update_data(plan_device=str(n)); await state.set_state(S.add_plan_stock_count); await message.answer("📦 এই Plan-এ কয়টি নতুন Password থাকবে? Example: 5")
@dp.message(S.add_plan_stock_count)
async def add_plan_stock_count(message: Message,state:FSMContext):
    try:
        n=int((message.text or "").strip())
        if n<1 or n>500: raise ValueError
    except Exception:
        await message.answer("❌ Stock সংখ্যা 1 থেকে 500-এর মধ্যে দিন।"); return
    await state.update_data(plan_stock_count=n,plan_passwords=[],plan_password_index=1); await state.set_state(S.add_plan_password); await message.answer(f"🔐 Password 1/{n} দিন:")
@dp.message(S.add_plan_password)
async def add_plan_password(message: Message,state:FSMContext):
    d=await state.get_data(); arr=list(d.get("plan_passwords",[]))
    incoming=[x.strip() for x in (message.text or "").splitlines() if x.strip()]
    if not incoming: await message.answer("❌ Password দিন। প্রতি লাইনে একটি করে Password দিতে পারেন।"); return
    for pw in incoming:
        if pw not in arr: arr.append(pw)
    total=int(d["plan_stock_count"])
    if len(arr)<total:
        await state.update_data(plan_passwords=arr,plan_password_index=len(arr)+1); await message.answer(f"🔐 আরও {total-len(arr)}টি Password দিন। চাইলে একসাথে প্রতি লাইনে একটি করে দিতে পারেন।"); return
    arr=arr[:total]
    con=db(); cur=con.execute("INSERT INTO apk_plans(product_id,validity,price,password,device_limit,stock_status,active) VALUES(?,?,?,?,?,1,1)",(d["pid"],d["plan_validity"],d["plan_price"],arr[0],d["plan_device"])); plan_id=cur.lastrowid
    for pw in arr: con.execute("INSERT INTO apk_stock(plan_id,password,status,created_at) VALUES(?,?,?,?)",(plan_id,pw,"AVAILABLE",datetime.now().isoformat()))
    sync_apk_plan_stock(con,plan_id); con.commit(); con.close(); await state.clear(); await message.answer(f"✅ New APK Plan Added.\n📦 Stock: {total}",reply_markup=back(f"manage_plans:{d['pid']}"))


@dp.callback_query(F.data.startswith("plan_price:"))
async def plan_price_start(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    plan_id=int(q.data.split(":")[1]); await state.update_data(plan_id=plan_id); await state.set_state(S.plan_price); await q.message.edit_text("💰 নতুন Plan Price (৳) দিন:",reply_markup=back(f"plan_manage:{plan_id}")); await q.answer()
@dp.message(S.plan_price)
async def plan_price_save(message: Message,state:FSMContext):
    try: value=float((message.text or "").strip())
    except: await message.answer("❌ সঠিক Price দিন।"); return
    if value<0: await message.answer("❌ Price 0-এর কম হতে পারবে না।"); return
    d=await state.get_data(); con=db(); con.execute("UPDATE apk_plans SET price=? WHERE id=?",(value,d["plan_id"])); con.commit(); con.close(); await state.clear(); await message.answer("✅ Plan Price Updated.",reply_markup=back(f"plan_manage:{d['plan_id']}"))

@dp.callback_query(F.data.startswith("plan_validity:"))
async def plan_validity_start(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    plan_id=int(q.data.split(":")[1]); await state.update_data(plan_id=plan_id); await state.set_state(S.plan_validity); await q.message.edit_text("⏳ নতুন Validity / Duration দিন:",reply_markup=back(f"plan_manage:{plan_id}")); await q.answer()
@dp.message(S.plan_validity)
async def plan_validity_save(message: Message,state:FSMContext):
    v=(message.text or "").strip()
    if not v: await message.answer("❌ Validity দিন।"); return
    d=await state.get_data(); con=db(); con.execute("UPDATE apk_plans SET validity=? WHERE id=?",(v,d["plan_id"])); con.commit(); con.close(); await state.clear(); await message.answer("✅ Plan Validity Updated.",reply_markup=back(f"plan_manage:{d['plan_id']}"))

@dp.callback_query(F.data.startswith("plan_device:"))
async def plan_device_start(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    plan_id=int(q.data.split(":")[1]); await state.update_data(plan_id=plan_id); await state.set_state(S.plan_device); await q.message.edit_text("📱 নতুন Device Limit দিন:",reply_markup=back(f"plan_manage:{plan_id}")); await q.answer()
@dp.message(S.plan_device)
async def plan_device_save(message: Message,state:FSMContext):
    v=(message.text or "").strip()
    try:
        n=int(v)
        if n<1: raise ValueError
    except Exception:
        await message.answer("❌ Device সংখ্যা 1 বা তার বেশি দিন।"); return
    d=await state.get_data(); con=db(); con.execute("UPDATE apk_plans SET device_limit=? WHERE id=?",(str(n),d["plan_id"])); con.commit(); con.close(); await state.clear(); await message.answer("✅ Device Limit Updated.",reply_markup=back(f"plan_manage:{d['plan_id']}"))

@dp.callback_query(F.data.startswith("plan_add_stock:"))
async def plan_add_stock_start(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    plan_id=int(q.data.split(":")[1]); await state.update_data(plan_id=plan_id,existing_stock_passwords=[],existing_stock_index=1); await state.set_state(S.add_existing_stock_count); await q.message.edit_text("📦 কয়টি নতুন Password যোগ করবেন? Example: 5",reply_markup=back(f"plan_manage:{plan_id}")); await q.answer()

@dp.message(S.add_existing_stock_count)
async def add_existing_stock_count(message: Message,state:FSMContext):
    try:
        n=int((message.text or "").strip())
        if n<1 or n>500: raise ValueError
    except Exception:
        await message.answer("❌ Stock সংখ্যা 1 থেকে 500-এর মধ্যে দিন।"); return
    await state.update_data(existing_stock_count=n,existing_stock_passwords=[],existing_stock_index=1); await state.set_state(S.add_existing_stock_password); await message.answer(f"🔐 Password 1/{n} দিন:")

@dp.message(S.add_existing_stock_password)
async def add_existing_stock_password(message: Message,state:FSMContext):
    pw=(message.text or "").strip()
    if not pw: await message.answer("❌ Password দিন।"); return
    d=await state.get_data(); plan_id=int(d["plan_id"]); arr=list(d.get("existing_stock_passwords",[]))
    con=db(); duplicate=con.execute("SELECT 1 FROM apk_stock WHERE plan_id=? AND password=? AND active=1",(plan_id,pw)).fetchone(); con.close()
    if duplicate or pw in arr:
        await message.answer("❌ এই Password এই Plan-এ আগে আছে। অন্য Password দিন."); return
    arr.append(pw); idx=int(d["existing_stock_index"]); total=int(d["existing_stock_count"])
    if idx<total:
        await state.update_data(existing_stock_passwords=arr,existing_stock_index=idx+1); await message.answer(f"🔐 Password {idx+1}/{total} দিন:"); return
    con=db()
    for item in arr: con.execute("INSERT INTO apk_stock(plan_id,password,status,created_at) VALUES(?,?,?,?)",(plan_id,item,"AVAILABLE",datetime.now().isoformat()))
    sync_apk_plan_stock(con,plan_id); con.commit(); con.close(); await state.clear(); await message.answer(f"✅ {total}টি Password Stock-এ যোগ হয়েছে।",reply_markup=back(f"plan_manage:{plan_id}"))

@dp.callback_query(F.data.startswith("plan_stock_list:"))
async def plan_stock_list(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    plan_id=int(q.data.split(":")[1]); con=db(); r=con.execute("SELECT * FROM apk_plans WHERE id=?",(plan_id,)).fetchone(); rows=con.execute("SELECT * FROM apk_stock WHERE plan_id=? AND active=1 ORDER BY id",(plan_id,)).fetchall(); con.close()
    if not r: await q.answer("Plan নেই।",show_alert=True); return
    lines=[f"🔐 <b>STOCK — {html.escape(str(r['validity']))}</b>","━━━━━━━━━━━━━━━━━━"]
    for i,row in enumerate(rows,1):
        status="✅ AVAILABLE" if row["status"]=="AVAILABLE" else "📤 SOLD"
        pw=html.escape(str(row["password"]))
        lines.append(f"#{row['id']} • <code>{pw}</code> — {status}")
    if len(lines)==2: lines.append("No stock.")
    kb=[[btn("➕ ADD PASSWORDS",f"plan_add_stock:{plan_id}"),btn("🗑️ REMOVE UNUSED",f"plan_remove_stock:{plan_id}")],[btn("◀️ BACK",f"plan_manage:{plan_id}")]]
    await q.message.edit_text("\n".join(lines),reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),parse_mode="HTML"); await q.answer()

@dp.callback_query(F.data.startswith("plan_remove_stock:"))
async def plan_remove_stock_start(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    plan_id=int(q.data.split(":")[1]); await state.update_data(plan_id=plan_id); await state.set_state(S.remove_stock); await q.message.edit_text("🗑️ Stock ID দিন যেটা remove করতে চান।\nশুধু AVAILABLE stock remove করা যাবে।",reply_markup=back(f"plan_stock_list:{plan_id}")); await q.answer()

@dp.message(S.remove_stock)
async def plan_remove_stock_save(message: Message,state:FSMContext):
    try: sid=int((message.text or "").strip())
    except Exception:
        await message.answer("❌ সঠিক Stock ID দিন।"); return
    d=await state.get_data(); plan_id=int(d["plan_id"]); con=db(); r=con.execute("SELECT status FROM apk_stock WHERE id=? AND plan_id=? AND active=1",(sid,plan_id)).fetchone()
    if not r:
        con.close(); await message.answer("❌ Stock পাওয়া যায়নি।"); return
    if r["status"] != "AVAILABLE":
        con.close(); await message.answer("❌ Sold Stock remove করা যাবে না।"); return
    con.execute("UPDATE apk_stock SET active=0 WHERE id=?",(sid,)); sync_apk_plan_stock(con,plan_id); con.commit(); con.close(); await state.clear(); await message.answer("✅ Unused Password removed.",reply_markup=back(f"plan_stock_list:{plan_id}"))


@dp.callback_query(F.data.startswith("plan_delete:"))
async def plan_delete(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    plan_id=int(q.data.split(":")[1]); con=db(); r=con.execute("SELECT product_id FROM apk_plans WHERE id=?",(plan_id,)).fetchone();
    if r:
        con.execute("UPDATE apk_plans SET active=0,stock_status=0 WHERE id=?",(plan_id,)); con.execute("UPDATE apk_stock SET active=0 WHERE plan_id=? AND status='AVAILABLE'",(plan_id,)); con.commit()
    con.close(); await q.answer("Plan deleted."); await manage_plans(q)


@dp.callback_query(F.data.startswith("change_apk_link:"))
async def change_apk_link_start(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    pid=int(q.data.split(":")[1]); await state.update_data(pid=pid); await state.set_state(S.change_apk_link); await q.message.edit_text("🔗 নতুন APK Download Link দিন:",reply_markup=back(f"product_manage:{pid}")); await q.answer()
@dp.message(S.change_apk_link)
async def change_apk_link_save(message: Message,state:FSMContext):
    url=(message.text or "").strip()
    if not (url.startswith("https://") or url.startswith("http://")): await message.answer("❌ Valid URL দিন।"); return
    d=await state.get_data(); con=db(); con.execute("UPDATE products SET apk_url=? WHERE id=?",(url,d['pid'])); con.commit(); con.close(); await state.clear(); await message.answer("✅ APK Download Link Updated.",reply_markup=back(f"product_manage:{d['pid']}"))

@dp.callback_query(F.data.startswith("change_price:"))
async def admin_change_price(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    pid=int(q.data.split(":")[1]); await state.update_data(pid=pid); await state.set_state(S.edit_price); await q.message.edit_text("💰 নতুন Price (৳) দিন:",reply_markup=back("product_all")); await q.answer()

@dp.message(S.edit_price)
async def admin_save_price(message: Message,state:FSMContext):
    try: price=float((message.text or "").strip())
    except: await message.answer("❌ সঠিক Price দিন।"); return
    data=await state.get_data(); con=db(); con.execute("UPDATE products SET price=? WHERE id=?",(price,data["pid"])); con.commit(); con.close(); await state.clear(); await message.answer("✅ Price Updated.",reply_markup=back("product_all"))

@dp.callback_query(F.data.startswith("toggle_stock:"))
async def admin_toggle_stock(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    pid=int(q.data.split(":")[1]); con=db(); p=con.execute("SELECT stock_status FROM products WHERE id=?",(pid,)).fetchone();
    if p: con.execute("UPDATE products SET stock_status=? WHERE id=?",(0 if p["stock_status"] else 1,pid)); con.commit()
    con.close(); await q.answer("Stock status updated."); await admin_product_manage(q)

@dp.callback_query(F.data.startswith("change_demo:"))
async def admin_change_demo(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    pid=int(q.data.split(":")[1]); await state.update_data(pid=pid); await state.set_state(S.edit_demo_id); await q.message.edit_text("🎬 নতুন Demo Photo/Video পাঠান:",reply_markup=back("product_all")); await q.answer()

@dp.message(S.edit_demo_id)
async def admin_save_demo(message: Message,state:FSMContext):
    data=await state.get_data()
    if message.photo: fid,typ=message.photo[-1].file_id,"photo"
    elif message.video: fid,typ=message.video.file_id,"video"
    else: await message.answer("Photo অথবা Video দিন।"); return
    con=db(); con.execute("UPDATE products SET demo_file_id=?,demo_type=? WHERE id=?",(fid,typ,data["pid"])); con.commit(); con.close(); await state.clear(); await message.answer("✅ Demo Updated.",reply_markup=back("product_all"))

@dp.callback_query(F.data.startswith("change_delivery:"))
async def admin_change_delivery(q: CallbackQuery,state:FSMContext):
    if not is_admin(q.from_user.id): return
    pid=int(q.data.split(":")[1]); await state.update_data(pid=pid); await state.set_state(S.edit_delivery); await q.message.edit_text("📦 নতুন Delivery message পাঠান/forward করুন:",reply_markup=back("product_all")); await q.answer()

@dp.message(S.edit_delivery)
async def admin_save_delivery(message: Message,state:FSMContext):
    data=await state.get_data(); con=db(); con.execute("UPDATE products SET delivery_type='copy',delivery_data=? WHERE id=?",(json.dumps({"chat_id":message.chat.id,"message_id":message.message_id}),data["pid"])); con.commit(); con.close(); await state.clear(); await message.answer("✅ Delivery Updated.",reply_markup=back("product_all"))

@dp.callback_query(F.data.startswith("delete_product:"))
async def admin_delete_product(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    pid=int(q.data.split(":")[1]); con=db(); con.execute("UPDATE products SET active=0 WHERE id=?",(pid,)); con.commit(); con.close(); await q.message.edit_text("🗑️ Product Deleted Successfully.",reply_markup=back("product_all")); await q.answer()


@dp.callback_query(F.data == "adm_orders")
async def admin_orders(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    await q.message.edit_text("🛒 <b>ORDER MANAGEMENT</b>\n\nএকটি Order Section নির্বাচন করুন:",reply_markup=order_management_kb(),parse_mode="HTML"); await q.answer()

async def admin_order_list(q: CallbackQuery,status=None):
    if not is_admin(q.from_user.id): return
    con=db();
    if status: rows=con.execute("SELECT o.*,p.name FROM orders o LEFT JOIN products p ON p.id=o.product_id WHERE o.status=? ORDER BY o.id DESC LIMIT 50",(status,)).fetchall()
    else: rows=con.execute("SELECT o.*,p.name FROM orders o LEFT JOIN products p ON p.id=o.product_id ORDER BY o.id DESC LIMIT 50").fetchall()
    con.close(); kb=[]
    for r in rows:
        kb.append([btn(f"#{r['id']} • {str(r['name'] or 'Deleted')[:22]} • ৳{r['price']:g} • {r['status']}",f"admin_order_detail:{r['id']}")])
    kb.append([btn("◀️ BACK","adm_orders")]); text="🛒 <b>ORDERS</b>\n\n"+(f"Total: {len(rows)}" if rows else "No orders found.")
    await q.message.edit_text(text,reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),parse_mode="HTML"); await q.answer()

@dp.callback_query(F.data == "orders_pending")
async def admin_orders_pending(q: CallbackQuery): await admin_order_list(q,"PENDING")
@dp.callback_query(F.data == "orders_completed")
async def admin_orders_completed(q: CallbackQuery): await admin_order_list(q,"COMPLETED")
@dp.callback_query(F.data == "orders_rejected")
async def admin_orders_rejected(q: CallbackQuery): await admin_order_list(q,"REJECTED")
@dp.callback_query(F.data == "orders_all")
async def admin_orders_all(q: CallbackQuery): await admin_order_list(q)

@dp.callback_query(F.data.startswith("admin_order_detail:"))
async def admin_order_detail(q: CallbackQuery):
    if not is_admin(q.from_user.id): return
    oid=int(q.data.split(":")[1]); con=db(); r=con.execute("SELECT o.*,p.name FROM orders o LEFT JOIN products p ON p.id=o.product_id WHERE o.id=?",(oid,)).fetchone(); con.close()
    if not r: await q.answer("Order নেই।",show_alert=True); return
    plan_text=""
    if r["plan_id"]:
        con2=db(); pl=con2.execute("SELECT validity FROM apk_plans WHERE id=?",(r["plan_id"],)).fetchone(); con2.close()
        if pl: plan_text=f"\n⏳ Plan: {html.escape(str(pl['validity']))}"
    text=(f"🧾 <b>ORDER #{r['id']}</b>\n\n👤 User ID: <code>{r['user_id']}</code>\n📦 Product: {html.escape(str(r['name'] or 'Deleted'))}{plan_text}\n💰 Price: ৳{r['price']:g}\n📌 Status: {r['status']}\n📱 Payment: {html.escape(str(r['payment_method'] or 'N/A'))}\n🕒 {r['created_at']}")
    kb=[]
    if r['status']=="PENDING": kb.append([btn("✅ ACCEPT",f"accept_order:{oid}"),btn("❌ REJECT",f"reject_order:{oid}")])
    kb.append([btn("◀️ BACK","orders_all")])
    await q.message.edit_text(text,reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),parse_mode="HTML"); await q.answer()


# =========================================================
# TELEGRAM MENU COMMANDS
# =========================================================
async def set_commands():
    from aiogram.types import BotCommand
    await bot.set_my_commands([
        BotCommand(command="start", description="বট চালু করুন"),
        BotCommand(command="admin", description="Admin Panel")
    ])


# =========================================================
# MAIN
# =========================================================
async def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN পাওয়া যায়নি। Render > Environment-এ BOT_TOKEN নামে "
            "নতুন BotFather token সেট করে redeploy করুন।"
        )

    try:
        # Validate the token before database setup or command registration so a bad
        # token produces a clear error instead of failing later in set_my_commands().
        me = await bot.get_me()
        logging.info("Telegram token validated for @%s (id=%s)", me.username, me.id)
        init_db()
        await set_commands()
        logging.info("SABBIR XYZ SHOP BOT IS ONLINE; starting long polling")
        await dp.start_polling(bot)
    except Exception:
        logging.exception(
            "Bot startup failed. If Telegram returned 404/Not Found, create a new "
            "token with @BotFather and update Render's BOT_TOKEN environment variable."
        )
        raise
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
