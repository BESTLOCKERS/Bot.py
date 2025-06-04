import os
import json
import random
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Tuple
from telegram.ext.filters import User
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackContext,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# === CONFIGURATION ===
TOKEN = os.getenv("TELEGRAM_TOKEN", "7336045089:AAFInAeU-W1qf1GFl6rlAcN4KvYYwVr_oWY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6679094272"))
KEYS_FILE = "keys.json"
DATABASE_FILES = ["v1.txt", "v2.txt", "v3.txt", "v4.txt", "v5.txt"]
USED_ACCOUNTS_FILE = "used_accounts.txt"
LINES_TO_SEND = 200
BOT_USERNAME = "PremiumAccountGenBot"
MAX_KEYS_PER_GENERATION = 20
MAX_ACCOUNTS_PER_USER = 1000  # Daily limit per user
MAX_PREMIUM_ACCOUNTS = 5000   # Daily limit for premium users
REQUEST_COOLDOWN = 30  # Seconds between requests
PREMIUM_COOLDOWN = 10  # Seconds between requests for premium users
MAX_LOG_ENTRIES = 1000  # Maximum log entries to keep

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === DOMAIN LIST ===
DOMAINS = [
    "100082", "authgop", "mtacc", "garena", "roblox", "gaslite", 
    "mobilelegends", "pubg", "codashop", "facebook", "Instagram", 
    "netflix", "tiktok", "telegram", "freefire", "bloodstrike",
    "spotify", "discord", "twitch", "steam", "origin", "epicgames",
    "youtube", "amazon", "hulu", "disneyplus", "crunchyroll", "minecraft"
]

# Premium domains (require higher privileges)
PREMIUM_DOMAINS = [
    "netflix", "spotify", "disneyplus", "hulu", "youtube"
]

# === URL REMOVER FUNCTION ===
def remove_url_and_keep_user_pass(line):
    match = re.search(r'([^:]+:[^:]+)$', line.strip())  # Extract only username:password
    return match.group(1) if match else None

# === DATA MODELS ===
class KeyData:
    def __init__(self):
        self.keys: Dict[str, Optional[float]] = {}  # key: expiry_timestamp
        self.user_keys: Dict[str, Optional[float]] = {}  # user_id: expiry_timestamp
        self.user_stats: Dict[str, Dict[str, int]] = {}  # user_id: {"today": count, "date": YYYY-MM-DD}
        self.global_stats: Dict[str, int] = {"generated": 0, "keys_created": 0}
        self.logs: List[str] = []
        self.user_last_request: Dict[str, float] = {}  # user_id: last_request_timestamp
        self.premium_users: Set[str] = set()  # Users with premium access

    def to_dict(self):
        return {
            "keys": self.keys,
            "user_keys": self.user_keys,
            "user_stats": self.user_stats,
            "global_stats": self.global_stats,
            "logs": self.logs[-MAX_LOG_ENTRIES:],  # Keep only recent logs
            "user_last_request": self.user_last_request,
            "premium_users": list(self.premium_users)
        }

    @classmethod
    def from_dict(cls, data: dict):
        instance = cls()
        instance.keys = data.get("keys", {})
        instance.user_keys = data.get("user_keys", {})
        instance.user_stats = data.get("user_stats", {})
        instance.global_stats = data.get("global_stats", {"generated": 0, "keys_created": 0})
        instance.logs = data.get("logs", [])
        instance.user_last_request = data.get("user_last_request", {})
        instance.premium_users = set(data.get("premium_users", []))
        return instance

# === DATA MANAGEMENT ===
def load_keys() -> KeyData:
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE, "r", encoding="utf-8") as f:
                return KeyData.from_dict(json.load(f))
        except Exception as e:
            logger.error(f"Error loading keys: {e}")
            return KeyData()
    return KeyData()

def save_keys(data: KeyData):
    try:
        with open(KEYS_FILE, "w", encoding="utf-8") as f:
            json.dump(data.to_dict(), f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving keys: {e}")

keys_data = load_keys()

# === UTILITY FUNCTIONS ===
def generate_random_key(length: int = 16) -> str:
    """Generate a random alphanumeric key"""
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "PREMIUM-" + ''.join(random.choices(chars, k=length))

def get_expiry_time(duration: str) -> Optional[float]:
    """Convert duration string to expiry timestamp"""
    now = datetime.now()
    duration_map = {
        "1m": 60, "5m": 300, "15m": 900,
        "1h": 3600, "6h": 21600, "12h": 43200,
        "1d": 86400, "3d": 259200, "7d": 604800,
        "14d": 1209600, "30d": 2592000
    }
    if duration == "lifetime":
        return None
    if duration in duration_map:
        return (now + timedelta(seconds=duration_map[duration])).timestamp()
    return None

def format_time(seconds: float) -> str:
    """Convert seconds to human-readable time"""
    periods = [
        ('day', 86400),
        ('hour', 3600),
        ('minute', 60),
        ('second', 1)
    ]
    result = []
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            if period_value > 0:
                result.append(f"{int(period_value)} {period_name}{'s' if period_value != 1 else ''}")
    return ', '.join(result) if result else "0 seconds"

async def send_large_message(update: Update, text: str, max_length: int = 4000):
    """Split large messages into chunks"""
    for i in range(0, len(text), max_length):
        if update.callback_query:
            await update.callback_query.message.reply_text(text[i:i+max_length], parse_mode="Markdown")
        else:
            await update.message.reply_text(text[i:i+max_length], parse_mode="Markdown")

def get_used_accounts() -> Set[str]:
    """Load used accounts from file"""
    try:
        with open(USED_ACCOUNTS_FILE, "r", encoding="utf-8", errors="ignore") as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        return set()
    except Exception as e:
        logger.error(f"Error loading used accounts: {e}")
        return set()

def save_used_accounts(accounts: Set[str]):
    """Save used accounts to file"""
    try:
        with open(USED_ACCOUNTS_FILE, "a", encoding="utf-8", errors="ignore") as f:
            f.write("\n".join(accounts) + "\n")
    except Exception as e:
        logger.error(f"Error saving used accounts: {e}")

def update_user_stats(user_id: str, count: int):
    """Update user statistics with daily limits"""
    today = datetime.now().strftime("%Y-%m-%d")
    if user_id not in keys_data.user_stats:
        keys_data.user_stats[user_id] = {"date": today, "today": 0}
    
    if keys_data.user_stats[user_id]["date"] != today:
        keys_data.user_stats[user_id] = {"date": today, "today": 0}
    
    keys_data.user_stats[user_id]["today"] += count
    keys_data.global_stats["generated"] += count

def check_user_limit(user_id: str) -> bool:
    """Check if user has exceeded daily limit"""
    today = datetime.now().strftime("%Y-%m-%d")
    if user_id not in keys_data.user_stats:
        return False
    if keys_data.user_stats[user_id]["date"] != today:
        return False
    
    max_limit = MAX_PREMIUM_ACCOUNTS if is_premium_user(user_id) else MAX_ACCOUNTS_PER_USER
    return keys_data.user_stats[user_id]["today"] >= max_limit

def check_cooldown(user_id: str) -> Optional[float]:
    """Check if user is on cooldown and return remaining time if true"""
    last_request = keys_data.user_last_request.get(user_id, 0)
    current_time = datetime.now().timestamp()
    elapsed = current_time - last_request
    
    cooldown = PREMIUM_COOLDOWN if is_premium_user(user_id) else REQUEST_COOLDOWN
    if elapsed < cooldown:
        return cooldown - elapsed
    return None

def update_last_request(user_id: str):
    """Update the last request time for a user"""
    keys_data.user_last_request[user_id] = datetime.now().timestamp()

def is_premium_user(user_id: str) -> bool:
    """Check if user has premium status"""
    return user_id in keys_data.premium_users

def is_premium_domain(domain: str) -> bool:
    """Check if domain requires premium access"""
    return domain.lower() in [d.lower() for d in PREMIUM_DOMAINS]

def is_valid_key(user_id: str) -> bool:
    """Check if user has a valid key"""
    if user_id in keys_data.premium_users:
        return True
    
    if user_id not in keys_data.user_keys:
        return False
    
    expiry = keys_data.user_keys[user_id]
    if expiry is None:  # Lifetime key
        return True
    
    if datetime.now().timestamp() > expiry:
        del keys_data.user_keys[user_id]
        save_keys(keys_data)
        return False
    
    return True

# === MENU SYSTEM ===
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the main menu with options + referral tracking"""
    from pathlib import Path
    import json

    user_id = str(update.effective_user.id)
    args = context.args if hasattr(context, "args") else []

    # ✅ Save user to users.json
    USERS_FILE = Path("users.json")
    USERS_FILE.touch(exist_ok=True)

    def get_all_users():
        try:
            return json.loads(USERS_FILE.read_text() or "[]")
        except json.JSONDecodeError:
            return []

    def save_user(user_id):
        users = get_all_users()
        if user_id not in users:
            users.append(user_id)
            USERS_FILE.write_text(json.dumps(users, indent=2))

    save_user(user_id)

    # ✅ Handle referral tracking
    REFERRAL_FILE = Path("referrals.json")
    REFERRAL_FILE.touch(exist_ok=True)

    try:
        referrals = json.loads(REFERRAL_FILE.read_text() or "{}")
    except json.JSONDecodeError:
        referrals = {}

    if args and args[0].startswith("ref_"):
        referrer_id = args[0].split("ref_")[1]
        if referrer_id != user_id:
            ref_data = referrals.get(referrer_id, {"referred_users": [], "credits": 0})
            if user_id not in ref_data["referred_users"]:
                ref_data["referred_users"].append(user_id)
                ref_data["credits"] += 2
                referrals[referrer_id] = ref_data
                REFERRAL_FILE.write_text(json.dumps(referrals, indent=2))

                try:
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=f"🎉 Someone just used your referral link!\nYou earned +2 credits 💰"
                    )
                except Exception as e:
                    print(f"[Referral Notify Error] {e}")

    # ✅ Main menu UI (with video generation)
    keyboard = [
        [InlineKeyboardButton("🔑 Generate Accounts", callback_data="main_generate")],
        [InlineKeyboardButton("🥵 BOLD GENERATOR", callback_data="main_video")],
        [InlineKeyboardButton("ℹ️ Bot Info", callback_data="main_info"),
         InlineKeyboardButton("📊 Stats", callback_data="main_stats")],
        [InlineKeyboardButton("🆘 Help", callback_data="main_help"),
         InlineKeyboardButton("📞 Contact Admin", callback_data="main_contact")],
        [InlineKeyboardButton("🔗 Referral", callback_data="main_referral")]
    ]

    if user_id == str(ADMIN_ID):
        keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data="main_admin")])

    premium_status = "🌟 PREMIUM USER" if is_premium_user(user_id) else ""

    if update.callback_query:
        await update.callback_query.message.edit_text(
            f"🎮 *Account Generator Bot* {premium_status}\n\nSelect an option:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"🎮 *Account Generator Bot* {premium_status}\n\nSelect an option:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )




async def generate_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show domain selection menu"""
    query = update.callback_query
    await query.answer()
    
    chat_id = str(query.message.chat_id)
    if not is_valid_key(chat_id):
        return await query.message.reply_text("🚨 You need a valid key to use this feature!")

    keyboard = []
    for i in range(0, len(DOMAINS), 2):
        row = []
        if i < len(DOMAINS):
            domain = DOMAINS[i]
            emoji = "✨" if is_premium_domain(domain) else "🔹"
            row.append(InlineKeyboardButton(f"{emoji} {domain}", callback_data=f"generate_{domain}"))
        if i+1 < len(DOMAINS):
            domain = DOMAINS[i+1]
            emoji = "✨" if is_premium_domain(domain) else "🔹"
            row.append(InlineKeyboardButton(f"{emoji} {domain}", callback_data=f"generate_{domain}"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_back")])
    
    await query.message.edit_text(
        "🛠 **Select a domain to generate:**\n✨ = Premium domain (requires premium key)",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def premium_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show premium features menu"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    is_premium = is_premium_user(user_id)
    
    keyboard = [
        [InlineKeyboardButton("💎 Premium Domains", callback_data="premium_domains")],
        [InlineKeyboardButton("🚀 Faster Generation", callback_data="premium_speed")],
        [InlineKeyboardButton("📈 Higher Limits", callback_data="premium_limits")]
    ]
    
    if not is_premium:
        keyboard.append([InlineKeyboardButton("🛒 Get Premium", callback_data="premium_buy")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_back")])
    
    status = "🌟 You are a PREMIUM user!" if is_premium else "🔹 Regular user (upgrade for more features)"
    
    await query.message.edit_text(
        f"🎁 *Premium Features*\n\n{status}\n\n"
        "💎 *Benefits:*\n"
        "- Access to premium domains\n"
        "- Faster generation times\n"
        "- Higher daily limits\n"
        "- Priority support\n\n"
        "Select an option to learn more:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
async def send_video_demo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        with open("demo.mp4", "rb") as video_file:
            await context.bot.send_video(
                chat_id=query.message.chat_id,
                video=video_file,
                caption="🎬 Here's your demo video!"
            )
    except FileNotFoundError:
        await query.message.reply_text("❌ Video file not found. Please upload 'demo.mp4' to your bot directory.")
        
        
async def video_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("🥵 BOLD 1", callback_data="video_1"), InlineKeyboardButton("🥵 BOLD 2", callback_data="video_2")],
        [InlineKeyboardButton("🥵 BOLD 3", callback_data="video_3"), InlineKeyboardButton("🥵 BOLD 4", callback_data="video_4")],
        [InlineKeyboardButton("🥵 BOLD 5", callback_data="video_5"), InlineKeyboardButton("🥵 BOLD 6", callback_data="video_6")],
        [InlineKeyboardButton("🥵 BOLD 7", callback_data="video_7")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_back")]
    ]

    await query.message.edit_text(
        "📽 *Select a video to view:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
async def send_video_by_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    video_num = query.data.split("_")[1]
    filename = f"video{video_num}.mp4"

    try:
        with open(filename, "rb") as f:
            await context.bot.send_video(
                chat_id=query.message.chat_id,
                video=f,
                caption=f"🥵 Here's *BOLD {video_num}*",
                parse_mode="Markdown"
            )
    except FileNotFoundError:
        await query.message.reply_text(f"❌ File '{filename}' not found.")
            
    
    
async def block_generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("❌ This command can only be accessed using buttons.")
        

async def generate_filtered_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate and send accounts for selected domain"""
    
    if not update.callback_query:
        if update.message:
            await update.message.reply_text("❌ This command can only be used via button selection.")
        return

    query = update.callback_query
    await query.answer()
    
    chat_id = str(query.message.chat_id)
    user_id = str(query.from_user.id)

    cooldown = check_cooldown(user_id)
    if cooldown:
        return await query.message.reply_text(
            f"⏳ Please wait {format_time(cooldown)} before making another request."
        )
    
    if not is_valid_key(chat_id):
        return await query.message.reply_text("🚨 You need a valid key to use this feature!")

    if check_user_limit(chat_id):
        return await query.message.reply_text(
            "⚠️ You've reached your daily limit of accounts!\n"
            "Try again tomorrow or contact admin for premium access."
        )

    selected_domain = query.data.replace("generate_", "")
    
    if is_premium_domain(selected_domain) and not is_premium_user(user_id):
        return await query.message.reply_text(
            "🔒 This is a premium domain!\n"
            "You need a premium account to generate these accounts.\n\n"
            "Use /premium to learn more."
        )

    processing_msg = await query.message.reply_text("⚡ **Processing... Please wait 2-5 seconds.**")
    update_last_request(user_id)

    try:
        used_accounts = get_used_accounts()
        matched_lines = []
        
        for db_file in DATABASE_FILES:
            if len(matched_lines) >= LINES_TO_SEND:
                break
            
            try:
                with open(db_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        stripped_line = line.strip()
                        if (selected_domain.lower() in stripped_line.lower() and 
                            stripped_line not in used_accounts and 
                            len(stripped_line.split(":")) >= 2):
                            matched_lines.append(stripped_line)
                            if len(matched_lines) >= LINES_TO_SEND:
                                break
            except Exception as e:
                logger.error(f"Error reading {db_file}: {e}")
                continue

        if not matched_lines:
            return await processing_msg.edit_text(f"❌ No accounts found for {selected_domain}. Try another domain.")

        save_used_accounts(set(matched_lines))
        update_user_stats(chat_id, len(matched_lines))
        save_keys(keys_data)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"PREMIUM_{selected_domain}_{timestamp}.txt"
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"🔥 Premium Accounts Generator\n")
            f.write(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"🔍 Domain: {selected_domain}\n")
            f.write(f"📦 Accounts: {len(matched_lines)}\n\n")
            f.write("\n".join(matched_lines))

        await asyncio.sleep(2)  # Simulate processing time

        expiry = keys_data.user_keys.get(chat_id, None)
        expiry_text = "Lifetime" if expiry is None else datetime.fromtimestamp(expiry).strftime('%Y-%m-%d %H:%M:%S')
        
        max_limit = MAX_PREMIUM_ACCOUNTS if is_premium_user(user_id) else MAX_ACCOUNTS_PER_USER
        caption = (
            f"✅ *{selected_domain.upper()} Accounts Generated!*\n"
            f"📦 *Count:* `{len(matched_lines)}`\n"
            f"⏳ *Key Expires:* `{expiry_text}`\n"
            f"📊 *Daily Usage:* `{keys_data.user_stats.get(chat_id, {}).get('today', 0)}/{max_limit}`\n\n"
            f"💡 *Tip:* Use accounts quickly as they may become invalid over time."
        )
        
        await processing_msg.delete()
        with open(filename, "rb") as f:
            await query.message.reply_document(
                document=InputFile(f, filename=filename),
                caption=caption,
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Error generating accounts: {e}")
        await processing_msg.edit_text("❌ An error occurred while generating accounts. Please try again.")
    finally:
        if 'filename' in locals() and os.path.exists(filename):
            os.remove(filename)

from telegram import Update
from telegram.ext import ContextTypes

user_file_state = set()


async def handle_generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ This command can only be accessed via button selection.")

        



async def generate_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to generate premium keys."""

    # ✅ Get chat_id safely (supports message or callback)
    chat_id = (
        update.effective_user.id if update.message else update.callback_query.from_user.id
    )

    if str(chat_id) != str(ADMIN_ID):
        msg_target = update.message or update.callback_query.message
        return await msg_target.reply_text("❌ You are not authorized to generate keys!")

    # ✅ Validate args
    if not context.args or context.args[0] not in [
        "1m", "5m", "15m", "1h", "6h", "12h", "1d", "3d", "7d", "14d", "30d", "lifetime", "premium"
    ]:
        msg_target = update.message or update.callback_query.message
        return await msg_target.reply_text(
            "⚠ *Usage:* `/genkey <duration> [amount]`\n"
            "*Examples:*\n"
            "• `/genkey 1h` - Single 1-hour key\n"
            "• `/genkey 1d 5` - Five 1-day keys\n"
            "• `/genkey premium 3` - Three premium keys\n"
            "*Durations:* 1m, 5m, 15m, 1h, 6h, 12h, 1d, 3d, 7d, 14d, 30d, lifetime, premium",
            parse_mode="Markdown"
        )

    duration = context.args[0]
    amount = 1 if len(context.args) < 2 else min(int(context.args[1]), MAX_KEYS_PER_GENERATION)

    keys_generated = []
    for _ in range(amount):
        new_key = generate_random_key()

        if duration == "premium":
            keys_data.keys[new_key] = "premium"
        else:
            expiry = get_expiry_time(duration)
            keys_data.keys[new_key] = expiry

        keys_generated.append(new_key)

    keys_data.global_stats["keys_created"] += amount
    save_keys(keys_data)

    key_list = "\n".join(f"`{key}`" for key in keys_generated)
    msg_target = update.message or update.callback_query.message
    await msg_target.reply_text(
        f"✅ *Generated {amount} {duration} key(s):*\n{key_list}\n\n"
        f"*Total active keys:* `{len(keys_data.keys)}`",
        parse_mode="Markdown"
    )
    
    # Set state in user_data
async def request_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_user.id)
    context.user_data["awaiting_key_input"] = True
    await update.message.reply_text("🥵 *ENTER YOUR KEY:*", parse_mode="Markdown")
    
async def handle_key_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)
    text = update.message.text.strip()

    if context.user_data.get("awaiting_key_input"):
        context.args = [text]  # Inject the key as if it was passed in the command
        await redeem_key(update, context)
        context.user_data["awaiting_key_input"] = False


from datetime import datetime  # Fix: use correct import

from datetime import datetime

async def redeem_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Redeem a premium key"""
    chat_id = str(update.effective_user.id)
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.full_name

    # Check for key in args
    if not context.args or len(context.args) != 1:
        return await update.message.reply_text(
            "⚠ *Usage:* `/key` (bot will ask you to send the key!)\n"
            "Get a key from the bot admin to access premium features.",
            parse_mode="Markdown"
        )

    entered_key = context.args[0]

    if entered_key not in keys_data.keys:
        return await update.message.reply_text("❌ Invalid or expired key!")

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    expiry_text = ""
    key_type = ""

    # Handle premium key
    if keys_data.keys[entered_key] == "premium":
        keys_data.premium_users.add(chat_id)
        del keys_data.keys[entered_key]
        save_keys(keys_data)

        await update.message.reply_text(
            "🎉 *Premium Account Activated!*\n\n"
            "🌟 *Benefits unlocked:*\n"
            "- Access to premium domains\n"
            "- Faster generation times\n"
            "- Higher daily limits\n"
            "- Priority support\n\n"
            "Use /generate to start!",
            parse_mode="Markdown"
        )

        expiry_text = "Unlimited"
        key_type = "Premium"

    else:
        expiry = keys_data.keys[entered_key]

        if expiry is not None and datetime.now().timestamp() > expiry:
            del keys_data.keys[entered_key]
            save_keys(keys_data)
            return await update.message.reply_text("❌ This key has expired!")

        # Avoid downgrade
        if chat_id in keys_data.user_keys:
            old_expiry = keys_data.user_keys[chat_id]
            if old_expiry is None or (expiry and old_expiry > expiry):
                return await update.message.reply_text(
                    f"⚠ You already have a better active key!\n"
                    f"Current expiry: `{'Lifetime' if old_expiry is None else datetime.fromtimestamp(old_expiry).strftime('%Y-%m-%d %H:%M:%S')}`",
                    parse_mode="Markdown"
                )

        keys_data.user_keys[chat_id] = expiry
        del keys_data.keys[entered_key]
        save_keys(keys_data)

        expiry_text = "Unlimited" if expiry is None else datetime.fromtimestamp(expiry).strftime('%Y-%m-%d %H:%M:%S')
        key_type = "Lifetime" if expiry is None else "Timed"

        await update.message.reply_text(
            f"✅ *Key activated successfully!*\n"
            f"⏳ *Expires:* `{expiry_text}`\n"
            f"💎 *Features unlocked:*\n"
            f"- Generate premium accounts\n"
            f"- Priority access\n"
            f"- Daily limit: {MAX_ACCOUNTS_PER_USER} accounts\n\n"
            f"Use /start to generate!",
            parse_mode="Markdown"
        )

    # Global Redemption Alert (skip notifying self)
    announcement = (
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔥 *KEY REDEMPTION ALERT*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕵️ Username: {username}\n"
        f"👤 User ID: {user.id}\n"
        f"🔐 Key Type: {key_type}\n"
        f"🗓️ Redeemed At: {now_str}\n"
        f"⏱️ Time Left: {expiry_text}\n"
        f"🧭 [Profile: CLICK HERE](tg://user?id={user.id})\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🧠 Access Unlocked ✅"
    )

    for uid in keys_data.user_keys:
        if str(uid) == chat_id:
            continue
        try:
            await context.bot.send_message(chat_id=uid, text=announcement, parse_mode="Markdown")
        except Exception as e:
            print(f"[Broadcast Error] {uid}: {e}")


            
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show admin panel"""
    query = update.callback_query
    await query.answer()
    
    if str(query.from_user.id) != str(ADMIN_ID):
        return await query.message.reply_text("❌ Access denied!")

    keyboard = [
    [InlineKeyboardButton("📋 View Logs", callback_data="admin_logs"),
     InlineKeyboardButton("📊 View Stats", callback_data="admin_stats")],
    [InlineKeyboardButton("🔑 Generate Keys", callback_data="admin_genkeys"),
     InlineKeyboardButton("👥 Manage Users", callback_data="admin_users")],
    [InlineKeyboardButton("🗑 Clear Logs", callback_data="admin_clearlogs"),
     InlineKeyboardButton("🔄 Update Bot", callback_data="admin_update")],
    [InlineKeyboardButton("🔙 Back", callback_data="main_back")]
]


    
    await query.message.edit_text(
        "👑 *Admin Panel*\nSelect an option:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
   
        
async def view_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if str(query.from_user.id) != str(ADMIN_ID):
        return await query.message.reply_text("❌ Access denied!")

    if not keys_data.user_keys and not keys_data.premium_users:
        return await query.message.reply_text("📂 No active users.")

    log_text = "📋 *Active Users*\n\n"

    if keys_data.premium_users:
        log_text += "🌟 *Premium Users*\n"
        for user in keys_data.premium_users:
            usage = keys_data.user_stats.get(user, {}).get("today", 0)
            log_text += f"👤 User: `{user}`\n📊 Usage: `{usage}/{MAX_PREMIUM_ACCOUNTS}`\n\n"

    for user, expiry in keys_data.user_keys.items():
        expiry_text = "Lifetime" if expiry is None else datetime.fromtimestamp(expiry).strftime('%Y-%m-%d %H:%M:%S')
        usage = keys_data.user_stats.get(user, {}).get("today", 0)
        log_text += f"👤 User: `{user}`\n⏳ Expiry: `{expiry_text}`\n📊 Usage: `{usage}/{MAX_ACCOUNTS_PER_USER}`\n\n"

    # ✅ THIS LINE FIXES THE ERROR
    await send_large_message(update, log_text)


async def view_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed statistics"""
    query = update.callback_query
    await query.answer()
    
    active_users = len(keys_data.user_keys)
    premium_users = len(keys_data.premium_users)
    active_keys = len(keys_data.keys)
    total_generated = keys_data.global_stats.get("generated", 0)
    keys_created = keys_data.global_stats.get("keys_created", 0)
    
    stats_text = (
        f"📊 *Bot Statistics*\n\n"
        f"🔢 Total Accounts Generated: `{total_generated}`\n"
        f"🔑 Total Keys Created: `{keys_created}`\n"
        f"👥 Active Users: `{active_users}`\n"
        f"🌟 Premium Users: `{premium_users}`\n"
        f"🔑 Available Keys: `{active_keys}`\n\n"
        f"🌐 Supported Domains: `{len(DOMAINS)}`\n"
        f"💎 Premium Domains: `{len(PREMIUM_DOMAINS)}`\n"
        f"📂 Database Files: `{len(DATABASE_FILES)}`"
    )
    
    await query.message.edit_text(stats_text, parse_mode="Markdown")

async def clear_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear all user logs"""
    query = update.callback_query
    await query.answer()
    
    if str(query.from_user.id) != str(ADMIN_ID):
        return await query.message.reply_text("❌ Access denied!")

    keys_data.user_keys = {}
    keys_data.user_stats = {}
    keys_data.premium_users = set()
    save_keys(keys_data)
    await query.message.reply_text("✅ All user logs and stats have been cleared!")

async def manage_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manage users interface"""
    query = update.callback_query
    await query.answer()
    
    if str(query.from_user.id) != str(ADMIN_ID):
        return await query.message.reply_text("❌ Access denied!")

    keyboard = [
        [InlineKeyboardButton("➕ Add Premium User", callback_data="admin_add_premium")],
        [InlineKeyboardButton("➖ Remove Premium User", callback_data="admin_remove_premium")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_back")]
    ]
    
    await query.message.edit_text(
        "👥 *User Management*\nSelect an option:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def add_premium_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add premium user"""
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(
        "👤 *Add Premium User*\n\n"
        "Send the user ID to grant premium access:",
        parse_mode="Markdown"
    )
    
    context.user_data["awaiting_user_id"] = "add_premium"

async def remove_premium_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove premium user"""
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(
        "👤 *Remove Premium User*\n\n"
        "Send the user ID to revoke premium access:",
        parse_mode="Markdown"
    )
    
    context.user_data["awaiting_user_id"] = "remove_premium"

async def handle_user_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user ID input for premium management"""
    if not context.user_data.get("awaiting_user_id"):
        return
    
    action = context.user_data["awaiting_user_id"]
    user_id = update.message.text.strip()
    
    if action == "add_premium":
        keys_data.premium_users.add(user_id)
        await update.message.reply_text(f"✅ User {user_id} has been granted premium access!")
    elif action == "remove_premium":
        if user_id in keys_data.premium_users:
            keys_data.premium_users.remove(user_id)
            await update.message.reply_text(f"✅ User {user_id} has been removed from premium access!")
        else:
            await update.message.reply_text(f"❌ User {user_id} is not a premium user!")
    
    save_keys(keys_data)
    context.user_data["awaiting_user_id"] = None

async def bot_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot information"""
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(
        "ℹ️ *Bot Information*\n\n"
        "🔹 *Name:* Premium Account Generator\n"
        "🔹 *Version:* 4.0 (Enhanced)\n"
        "🔹 *Developer:* NAME\n\n"
        "💎 *Features:*\n"
        "- Fast account generation\n"
        "- Multiple domains supported\n"
        "- Premium key system\n"
        "- Daily account limits\n"
        "- Regular database updates\n"
        "- Premium domains available\n\n"
        "Use /generate to start!",
        parse_mode="Markdown"
    )

async def bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show public statistics"""
    query = update.callback_query
    await query.answer()
    
    total_generated = keys_data.global_stats.get("generated", 0)
    premium_domains = "\n".join(f"• {domain}" for domain in PREMIUM_DOMAINS)
    
    await query.message.edit_text(
        f"📊 *Public Statistics*\n\n"
        f"🔢 Total Accounts Generated: `{total_generated}`\n"
        f"🌐 Supported Domains: `{len(DOMAINS)}`\n\n"
        f"💎 *Premium Domains:*\n{premium_domains}\n\n"
        f"🔥 *More features coming soon!*",
        parse_mode="Markdown"
    )

async def bot_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message"""
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(
        "🆘 *Help Center*\n\n"
        "🔹 *How to use:*\n"
        "1. Get a premium key from admin\n"
        "2. Redeem it with `/key <your_key>`\n"
        "3. Use `/generate` to select a domain\n\n"
        "📌 *Commands:*\n"
        "- /start - Show main menu\n"
        "- /key <key> - Redeem premium key\n"
        "- /generate - Generate accounts\n"
        "- /premium - Premium features info\n"
        "- /help - Show this message\n\n"
        "⚠ *Note:*\n"
        f"- Regular limit: {MAX_ACCOUNTS_PER_USER} accounts/day\n"
        f"- Premium limit: {MAX_PREMIUM_ACCOUNTS} accounts/day\n"
        "- Keys are required for generation\n"
        "- Premium domains require special access",
        parse_mode="Markdown"
    )

async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show contact information"""
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(
        "📞 *Contact Admin*\n\n"
        "For support, key requests, or premium access:\n\n"
        f"🔹 Telegram: @{context.bot.username}\n"
        "🔹 Email: youremail@example.com\n\n"
        "Please be patient for a response.",
        parse_mode="Markdown"
    )

async def handle_premium_domains_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show premium domains information"""
    query = update.callback_query
    await query.answer()
    
    domains = "\n".join(f"✨ {domain}" for domain in PREMIUM_DOMAINS)
    await query.message.edit_text(
        f"💎 *Premium Domains*\n\n{domains}\n\n"
        "These domains require a premium account to generate.",
        parse_mode="Markdown"
    )

async def handle_premium_speed_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show premium speed benefits"""
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(
        "🚀 *Premium Speed Benefits*\n\n"
        "Premium users enjoy:\n"
        f"- Faster generation times (2-5 seconds vs 5-10 for regular users)\n"
        f"- Reduced cooldown: {PREMIUM_COOLDOWN}s vs {REQUEST_COOLDOWN}s\n"
        "- Priority queue placement\n\n"
        "This means you can generate accounts much faster when you need them!",
        parse_mode="Markdown"
    )

async def handle_premium_limits_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show premium limits benefits"""
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(
        "📈 *Premium Limits Benefits*\n\n"
        "Premium users enjoy higher daily limits:\n"
        f"- Regular users: {MAX_ACCOUNTS_PER_USER} accounts/day\n"
        f"- Premium users: {MAX_PREMIUM_ACCOUNTS} accounts/day\n\n"
        "This allows you to generate more accounts when you need them!",
        parse_mode="Markdown"
    )

async def handle_premium_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle premium purchase request"""
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(
        "🛒 *Get Premium Access*\n\n"
        "To get premium access, please contact the admin:\n"
        f"👉 @{context.bot.username}\n\n"
        "Premium benefits include:\n"
        "- Access to premium domains\n"
        "- Faster generation times\n"
        "- Higher daily limits\n"
        "- Priority support",
        parse_mode="Markdown"
    )

async def handle_admin_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle bot update request"""
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(
        "🔄 *Bot Update*\n\n"
        "This feature would update the bot's database and code.\n"
        "Not implemented in this version.",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    text = update.message.text.lower()
    
    if text in ["/start", "start", "menu"]:
        await show_main_menu(update, context)
    elif text in ["help", "info"]:
        await bot_help(update, context)
    elif text == "generate":
        await generate_menu(update, context)
    elif text == "premium":
        await premium_menu(update, context)
    elif text.isdigit() and context.user_data.get("awaiting_user_id"):
        await handle_user_id_input(update, context)
    elif data == "main_referral":
        await send_referral_panel(update, context)
    
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors and notify admin"""
    logger.error(f"Update {update} caused error: {context.error}")
    
    if ADMIN_ID:
        error_msg = (
            f"⚠️ *Error occurred:*\n"
            f"```python\n{context.error}\n```\n"
            f"*Update:*\n`{update}`"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=error_msg, parse_mode="Markdown")

async def admin_generate_key_ui(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["awaiting_key_amount"] = True
    await query.edit_message_text("🔢 How many keys do you want to generate?")
    
async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_key_amount"):
        try:
            count = int(update.message.text)
            context.user_data["key_count"] = count
            context.user_data["awaiting_key_amount"] = False

            keyboard = [
                [InlineKeyboardButton("1m", callback_data="genkeyui:1m"), InlineKeyboardButton("5m", callback_data="genkeyui:5m"), InlineKeyboardButton("15m", callback_data="genkeyui:15m")],
                [InlineKeyboardButton("1h", callback_data="genkeyui:1h"), InlineKeyboardButton("6h", callback_data="genkeyui:6h"), InlineKeyboardButton("12h", callback_data="genkeyui:12h")],
                [InlineKeyboardButton("1d", callback_data="genkeyui:1d"), InlineKeyboardButton("3d", callback_data="genkeyui:3d"), InlineKeyboardButton("7d", callback_data="genkeyui:7d")],
                [InlineKeyboardButton("30d", callback_data="genkeyui:30d"), InlineKeyboardButton("lifetime", callback_data="genkeyui:lifetime")]
            ]

            await update.message.reply_text(
                "⏳ *Choose key duration:*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number.")
            
async def handle_duration_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    duration = query.data.split(":")[1]
    count = context.user_data.get("key_count", 1)

    keys = []
    for _ in range(count):
        new_key = generate_random_key()
        expiry = None if duration == "lifetime" else get_expiry_time(duration)
        keys_data.keys[new_key] = expiry
        keys.append(new_key)

    keys_data.global_stats["keys_created"] += count
    save_keys(keys_data)

    key_list = "\n".join(f"`{key}`" for key in keys)
    await query.edit_message_text(
        f"✅ *Generated {count} key(s) for {duration}:*\n\n{key_list}",
        parse_mode="Markdown"
    )
    
async def send_referral_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    bot_username = context.bot.username
    referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

    from pathlib import Path
    import json

    REFERRAL_FILE = Path("referrals.json")
    if REFERRAL_FILE.exists():
        referrals = json.loads(REFERRAL_FILE.read_text())
        data = referrals.get(user_id, {"referred_users": [], "credits": 0})
        credits = data["credits"]
        total_refs = len(data["referred_users"])
    else:
        credits = 0
        total_refs = 0

    text = (
        "🔗 *Your Referral Dashboard:*\n\n"
        f"👥 Total Invited: `{total_refs}`\n"
        f"💎 Referral Credits: `{credits}`\n\n"
        f"*Your Link:*\n[Click to copy]({referral_link})\n\n"
        "➡️ Share this link — you'll earn *2 credits* when someone joins and redeems a key!"
    )

    await update.callback_query.message.edit_text(text, parse_mode="Markdown")

async def admin_generate_key_ui(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("1m", callback_data="genkeyui:1m"), InlineKeyboardButton("5m", callback_data="genkeyui:5m"), InlineKeyboardButton("15m", callback_data="genkeyui:15m")],
        [InlineKeyboardButton("1h", callback_data="genkeyui:1h"), InlineKeyboardButton("6h", callback_data="genkeyui:6h"), InlineKeyboardButton("12h", callback_data="genkeyui:12h")],
        [InlineKeyboardButton("1d", callback_data="genkeyui:1d"), InlineKeyboardButton("3d", callback_data="genkeyui:3d"), InlineKeyboardButton("7d", callback_data="genkeyui:7d")],
        [InlineKeyboardButton("14d", callback_data="genkeyui:14d"), InlineKeyboardButton("30d", callback_data="genkeyui:30d"), InlineKeyboardButton("Lifetime", callback_data="genkeyui:lifetime")]
    ]

    await query.edit_message_text(
        "🧭 *Choose key duration:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    
DURATION_SECONDS = {
    "1m": 60, "5m": 300, "15m": 900,
    "1h": 3600, "6h": 21600, "12h": 43200,
    "1d": 86400, "3d": 259200, "7d": 604800,
    "14d": 1209600, "30d": 2592000
}

async def handle_duration_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    duration = query.data.split(":")[1]
    count = 1  # generate 1 key by default

    keys = []
    for _ in range(count):
        new_key = generate_random_key()
        expiry = None if duration == "lifetime" else int(time.time()) + DURATION_SECONDS.get(duration, 86400)
        keys_data.keys[new_key] = expiry
        keys.append(new_key)

    keys_data.global_stats["keys_created"] += count
    save_keys(keys_data)

    key_list = "\n".join(f"`{key}`" for key in keys)
    await query.edit_message_text(
        f"✅ *Generated {count} key(s) for {duration}:*\n\n{key_list}",
        parse_mode="Markdown"
    )
    




    

from telegram.ext import filters, Application, CommandHandler, CallbackQueryHandler, MessageHandler
from telegram.ext.filters import User

def setup_bot_handlers(application: Application):
    """Set up all bot handlers"""

    # --- Command Handlers ---
    application.add_handler(CommandHandler("start", show_main_menu))
    application.add_handler(CommandHandler("generate", block_generate_command))  # Block direct /generate
    application.add_handler(CommandHandler("premium", premium_menu))
    application.add_handler(CommandHandler("help", bot_help))
    application.add_handler(CommandHandler("stats", bot_stats))
    application.add_handler(CommandHandler("key", request_key))
    application.add_handler(CommandHandler("genkey", generate_key))
    application.add_handler(CommandHandler("logs", view_logs))

    # --- General Message Handlers ---
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_key_input))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))  # General fallback

    # --- Callback Query Handlers ---
    application.add_handler(CallbackQueryHandler(show_main_menu, pattern="^main_back$"))
    application.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_back$"))
    application.add_handler(CallbackQueryHandler(generate_menu, pattern="^main_generate$"))
    application.add_handler(CallbackQueryHandler(premium_menu, pattern="^main_premium$"))
    application.add_handler(CallbackQueryHandler(bot_info, pattern="^main_info$"))
    application.add_handler(CallbackQueryHandler(bot_stats, pattern="^main_stats$"))
    application.add_handler(CallbackQueryHandler(bot_help, pattern="^main_help$"))
    application.add_handler(CallbackQueryHandler(contact_admin, pattern="^main_contact$"))
    application.add_handler(CallbackQueryHandler(admin_panel, pattern="^main_admin$"))
    application.add_handler(CallbackQueryHandler(send_referral_panel, pattern="^main_referral$"))

    # --- Premium Info ---
    application.add_handler(CallbackQueryHandler(handle_premium_domains_info, pattern="^premium_domains$"))
    application.add_handler(CallbackQueryHandler(handle_premium_speed_info, pattern="^premium_speed$"))
    application.add_handler(CallbackQueryHandler(handle_premium_limits_info, pattern="^premium_limits$"))
    application.add_handler(CallbackQueryHandler(handle_premium_purchase, pattern="^premium_buy$"))

    # --- Generation ---
    application.add_handler(CallbackQueryHandler(generate_filtered_accounts, pattern="^generate_"))

    # --- Admin Panel Actions ---
    application.add_handler(CallbackQueryHandler(view_logs, pattern="^admin_logs$"))
    application.add_handler(CallbackQueryHandler(view_stats, pattern="^admin_stats$"))
    application.add_handler(CallbackQueryHandler(manage_users, pattern="^admin_users$"))
    application.add_handler(CallbackQueryHandler(add_premium_user, pattern="^admin_add_premium$"))
    application.add_handler(CallbackQueryHandler(remove_premium_user, pattern="^admin_remove_premium$"))
    application.add_handler(CallbackQueryHandler(clear_logs, pattern="^admin_clearlogs$"))
    application.add_handler(CallbackQueryHandler(handle_admin_update, pattern="^admin_update$"))
    
    application.add_handler(CallbackQueryHandler(video_menu, pattern="^main_video$"))
    application.add_handler(CallbackQueryHandler(send_video_by_number, pattern="^video_"))
   
    # --- Admin: Generate Keys Flow ---
    application.add_handler(CallbackQueryHandler(admin_generate_key_ui, pattern="^admin_genkeys$"))
    application.add_handler(CallbackQueryHandler(handle_duration_selection, pattern="^genkeyui:"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))  # Amount input

    # --- Admin: Announcement Flow ---
    

    from telegram.ext.filters import User





    # --- Error Handler ---
    application.add_error_handler(error_handler)


def main():
    """Start the bot"""
    app = Application.builder().token(TOKEN).build()
    setup_bot_handlers(app)
    
    # Check for required files
    for db_file in DATABASE_FILES:
        if not os.path.exists(db_file):
            logger.warning(f"Database file not found: {db_file}")
    
    logger.info("🤖 Premium Account Generator Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
