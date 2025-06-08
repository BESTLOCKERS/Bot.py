import os
import random
import asyncio
import datetime
import json
import time
import datetime
import pytz
from telegram import Update
from telegram.ext import CallbackContext
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, CallbackContext
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === CONFIGURATION ===
TOKEN = "7785114345:AAGX49LFQOnbnrpSB5gmGNinWqPCAnGI4wo"
ADMIN_ID = 6679094272  # Replace with your Telegram ID
USED_LINES_FILE = "used_lines.json"
LOG_FILE = "logs.json"
USER_ROLES_FILE = "user_roles.json"

DATABASE_FILES = {
    "CODM": "Cod.txt",
    "ML": "Ml.txt",
    "PUBG": "Pubg.txt",  # Existing Database
    "100082": "100082.txt",  # New Database for 100082
    "Authgop": "Authgop.txt",  # New Database for Authgop
    "Roblox": "Roblox.txt",  # New Database for Roblox
    "MTACC": "MTACC.txt",  # New Database for MTACC
    "Codashop": "Codashop.txt",  # New Database for Codashop
    "Valorant": "Valorant.txt",  # New Database for Valorant
    "Viva": "Viva.txt",  # New Database for Viva
    "Paypal": "Paypal.txt",  # New Database for Paypal
    "Spotify": "Spotify.txt",  # New Database for Spotify
    "Riot": "Riot.txt",  # New Database for Riot
    "Gmail": "Gmail.txt",  # New Database for Gmail
    "Netflix": "Netflix.txt",  # New Database for Netflix
    "8ball": "8ball.txt",  # New Database for 8ball
    "COC": "COC.txt",  # New Database for COC
    "Facebook": "Facebook.txt"  # New Database for Facebook
}
ACCESS_KEYS = {}  # {key: {"expires_at": timestamp}}
USER_ACCESS = {}  # {user_id: expiry_time or None}
USER_ROLES = {}  # {user_id: "admin"/"moderator"/"regular"}

def save_access_data():
    """Save the USER_ACCESS and ACCESS_KEYS to files."""
    with open("user_access.json", "w") as f:
        json.dump(USER_ACCESS, f, indent=4)

    with open("access_keys.json", "w") as f:
        json.dump(ACCESS_KEYS, f, indent=4)
    
    
# === PREDEFINED DURATIONS ===
DURATION_OPTIONS = {
    "1h": 60,       # 1 hour
    "1d": 1440,     # 1 day
    "3d": 4320,     # 3 days
    "7d": 10080,    # 7 days
    "lifetime": None,  # Lifetime (no expiration)
    "5m": 5,        # 5 minutes
    "10m": 10       # 10 minutes
}

# === FUNCTIONS: LOAD & SAVE LOGS ===
def load_logs():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_logs(data):
    with open(LOG_FILE, "w") as f:
        json.dump(data, f, indent=4)

logs = load_logs()

# === FUNCTIONS: LOAD & SAVE USER ROLES ===
def load_user_roles():
    if os.path.exists(USER_ROLES_FILE):
        with open(USER_ROLES_FILE, "r") as f:
            return json.load(f)
    return {}

def save_user_roles(data):
    with open(USER_ROLES_FILE, "w") as f:
        json.dump(data, f, indent=4)

USER_ROLES = load_user_roles()

# === FUNCTIONS: LOAD & SAVE USED LINES ===
def load_used_lines():
    """Load used lines from file."""
    if os.path.exists(USED_LINES_FILE):
        with open(USED_LINES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {game: [] for game in DATABASE_FILES.keys()}  # Default empty

def save_used_lines(data):
    """Save used lines to file."""
    with open(USED_LINES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# Load used lines on startup
used_lines = load_used_lines()

# Command handler for /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the /start command is issued."""
    user_id = update.message.from_user.id

    if has_access(user_id):
        await update.message.reply_text(
            "🌟 *Maligayang Pagdating sa My Generator TxT!* 🌟\n\n"
            "🔑 *May Access Ka Na!* 🎉\n\n"
            "Ngayon ay maaari mong gamitin ang bot upang mag-generate ng .txt files ng walang limitasyong paghahanap. 📝\n\n"
            "Narito ang ilan sa mga benepisyo ng iyong access:\n"
            "- ✅ Walang Limitasyong TxT Searches\n"
            "- ✅ Secure at Confidential Access 🔒\n"
            "- ✅ Mga Update sa Database 📈\n\n"
            "Pumili mula sa aming mga tampok gamit ang `/menu` para makapagsimula at maglaro o mag-explore ng mga options! 🎮\n"
            "Maraming Salamat sa pag-gamit ng aming serbisyo! 😊",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "🌟 *Maligayang Pagdating sa My Generator TxT!* 🌟\n\n"
            "🚫 *Access Restricted* 🚫\n\n"
            "Para magamit ang bot, kinakailangan mong i-redeem ang iyong access key. 🔑\n\n"
            "Narito ang mga benepisyo ng pagkakaroon ng key:\n"
            "- ✅ Walang Limitasyong TxT Searches\n"
            "- ✅ Secure at Confidential Access 🔒\n"
            "- ✅ Mga Update sa Database 📈\n\n"
            "Kung mayroon kang key, gamitin ang `/redeem <access_key>` upang i-redeem ito.\n\n"
            "*Halimbawa:* `/redeem 123456` (palitan ang `123456` ng iyong aktwal na key).\n\n"
            "Kung wala kang key, makipag-ugnayan sa admin para makakuha ng valid na access key. 📩",
            parse_mode="Markdown",
        )

# === FUNCTION: CHECK USER ACCESS ===
def has_access(user_id):
    if user_id not in USER_ACCESS:
        return False
    if USER_ACCESS[user_id] is None:
        return True
    return USER_ACCESS[user_id] > datetime.datetime.now().timestamp()

def is_user_admin(user_id):
    return USER_ROLES.get(user_id) == "admin"

# === GENERATE FILE ===
async def generate_file(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id

    if not has_access(user_id):
        await query.answer("🚫🖕 Bili Rin key Asa Kana Sa Hingi Putanginamo Ka🖕!!!")
        return

    _, game, lines_to_send = query.data.split(":")
    lines_to_send = int(lines_to_send)
    file_name = DATABASE_FILES.get(game)

    if not file_name or not os.path.exists(file_name):
        await query.message.edit_text("❌🖕 *Tanginamo Inubos Mona Uhaw Ka Kasi🖕!*")
        return

    await query.message.edit_text("⚙️🖕 *Mag Intay Ka Gago Ka Putanginamo ka!🖕* ⏳")
    await asyncio.sleep(2)

    with open(file_name, "r", encoding="utf-8") as f:
        all_lines = f.readlines()

    if not all_lines:
        await query.message.edit_text("❌ *Inubos Mona Putanginamo!!*")
        return

    # Remove used lines from available lines
    available_lines = list(set(all_lines) - set(used_lines.get(game, [])))

    if not available_lines:
        used_lines[game] = []  # Reset used lines if all are used
        available_lines = all_lines  # Refill with all lines

    selected_lines = random.sample(available_lines, min(lines_to_send, len(available_lines)))

    # Update used lines
    used_lines[game].extend(selected_lines)
    save_used_lines(used_lines)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result_file = f"HAZE/XAI_Premium_{game}_Site.txt"

    with open(result_file, "w", encoding="utf-8") as f:
        f.write(f"🚀 **Generated Data**\n📅 **Date & Time:** {timestamp}\n🎮 **Game:** {game}\n🔹 *Data Below:*\n")
        f.writelines(selected_lines)

    logs[user_id] = logs.get(user_id, 0) + 1
    save_logs(logs)

    # Custom success message
    success_message = (
        
        "════════════════════════\n"
        f"📅 Date and time: {timestamp}\n"
        f"🔍 Total lines found : {len(selected_lines)}\n"
        "════════════════════════\n"
        
    )

    with open(result_file, "rb") as f:
        await query.message.reply_document(document=InputFile(f), caption=success_message, parse_mode="Markdown")

# === GENERATE ONE-TIME USE KEY (ADMIN ONLY) ===
async def generate_key(update: Update, context: CallbackContext):
    # Ensure only the admin can generate keys
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text(
            "❌ *Access Denied!* 🚫\n\n"
            "You are not authorized to generate keys. Please contact an admin if you need access.", 
            parse_mode="Markdown"
        )
        return

    # Validate the duration argument
    if len(context.args) == 0 or context.args[0] not in DURATION_OPTIONS:
        await update.message.reply_text(
            "⚠️ *Invalid Duration!* ⏳\n\n"
            "Please use the following format to generate a key: \n\n"
            "`/genkey <5m|10m|1h|1d|3d|7d|lifetime>`\n\n"
            "*Examples:* \n"
            "`/genkey 1d` - Generates a key valid for 1 day\n"
            "`/genkey lifetime` - Generates a key without expiration", 
            parse_mode="Markdown"
        )
        return

    # Extract the duration and calculate expiration time
    duration_key = context.args[0]
    duration_minutes = DURATION_OPTIONS[duration_key]
    expires_at = None if duration_minutes is None else (datetime.datetime.now() + datetime.timedelta(minutes=duration_minutes)).timestamp()

    # Generate a unique access key
    key = ''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=16))
    while key in ACCESS_KEYS:
        key = ''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=16))

    # Save the generated key to the database
    ACCESS_KEYS[key] = {"expires_at": expires_at}
    save_access_data()  # Save the updated access data

    # Determine the expiry text
    expiry_text = f"{duration_key.replace('h', ' hour').replace('d', ' day')}" if expires_at else "*Lifetime*"

    # Send the response with a visually appealing design
    await update.message.reply_text(
        f"🎉 *Key Generation Successful!* ✅\n\n"
        "────────────────────────────────\n"
        f"🔑 *Generated Key:* `{key}`\n\n"
        f"⏳ *Validity:* {expiry_text}\n"
        "────────────────────────────────\n"
        "📁 *Keys have been successfully saved to the Database.*\n\n"
        "💡 *To redeem this key, use the command* `/redeem <your-key>` *on the bot.*",
        parse_mode="Markdown"
    )

    # Log the action for tracking purposes
    logger.info(f"Generated key {key} with expiration {expiry_text} by admin {update.message.from_user.id}")

# === FUNCTION: REDEEM ACCESS KEY ===
async def redeem_key(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    
    if len(context.args) == 0:
        await update.message.reply_text(
            "⚠️ *Error!* No access key provided.\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "*Please provide a valid access key.*", 
            parse_mode="Markdown"
        )
        return

    access_key = context.args[0]
    
    if access_key in ACCESS_KEYS:
        key_data = ACCESS_KEYS[access_key]
        
        # Check for expiration
        if key_data["expires_at"] and key_data["expires_at"] < datetime.datetime.now().timestamp():
            await update.message.reply_text(
                "❌ *Your access key has expired!* \n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "Please try again with a valid key.", 
                parse_mode="Markdown"
            )
            # Remove the expired key from the database
            del ACCESS_KEYS[access_key]
            save_access_data()
            return
        
        # ✅ Success: Grant access and delete key from the database
        USER_ACCESS[user_id] = key_data["expires_at"]
        del ACCESS_KEYS[access_key]  # DELETE THE KEY AFTER REDEEMING!
        save_access_data()

        expiration_time = (datetime.datetime.fromtimestamp(key_data["expires_at"]).strftime("%Y-%m-%d %H:%M:%S") 
                           if key_data["expires_at"] else "*Lifetime*")

        username = f"@{update.message.from_user.username}" if update.message.from_user.username else "*No Username*"
        
        await update.message.reply_text(
            "*✨ Access Granted!* 🎉\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 *Username:* `{username}`\n"
            f"📅 *Access Expires:* `{expiration_time}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🎮 You are now authorized to generate access keys.\n"
            "────────────────────────────\n"
            "📝 Type `/menu` to proceed and select your game options.",
            parse_mode="Markdown"
        )
        
        # ✅ Log the successful redemption
        logger.info(f"Access key '{access_key}' redeemed successfully by user: {user_id} ({username})")

        return
    else:
        await update.message.reply_text(
            "❌ *Invalid access key!* \n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Please double-check your key and try again.", 
            parse_mode="Markdown"
        )
        
# === FUNCTION: CHOOSE LINES ===
async def choose_lines(update: Update, context: CallbackContext):
    query = update.callback_query
    _, game = query.data.split(":")

    keyboard = [
        [InlineKeyboardButton("🔸 100 Lines", callback_data=f"generate:{game}:100")],
        [InlineKeyboardButton("🔸 300 Lines", callback_data=f"generate:{game}:300")],
        [InlineKeyboardButton("🔸 500 Lines", callback_data=f"generate:{game}:500")],
        [InlineKeyboardButton("🔸 1000 Lines", callback_data=f"generate:{game}:1000")],
        [InlineKeyboardButton("🔸 3000 Lines", callback_data=f"generate:{game}:3000")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = (
        "╔════════════════════════════╗\n"
        "     📥 *SELECT LINES TO GENERATE*     \n"
        "╚════════════════════════════╝\n\n"
        "👉 *Please select the number of lines you want to generate:*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔸 `100` – Quick generation for small tasks.\n"
        "🔸 `300` – Ideal for moderate data generation.\n"
        "🔸 `500` – Balanced option for most cases.\n"
        "🔸 `1000` – High-volume generation.\n"
        "🔸 `3000` – Maximum generation for large data sets.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "💡 *Tip:* Choose the number of lines depending on your need and system capacity."
    )

    await query.message.edit_text(
        message_text, 
        parse_mode="Markdown", 
        reply_markup=reply_markup
    )
    
    
# === FUNCTION: MAIN MENU ===
async def main_menu(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if not has_access(user_id):
        await update.message.reply_text("🚫 *🖕Oh Tatanga Tanga Ka Nanaman🖕! Use `/key <access_key>`.*")
        return

    keyboard = [
        [InlineKeyboardButton("📂 Database", callback_data="database")],
        [InlineKeyboardButton("📜 Logs", callback_data="logs")],
        [InlineKeyboardButton("🛠️ Checker", callback_data="checker")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("🔥 *🖕Pili Ka Para Mamatay Na Mama Mo🖕!:*", parse_mode="Markdown", reply_markup=reply_markup)
    
    

    
    
# === FUNCTION: DATABASE MENU ===
async def database_menu(update: Update, context: CallbackContext):
    user_id = update.callback_query.from_user.id
    if not has_access(user_id):
        await update.callback_query.answer("🚫 Bobo kaba?!")
        return

    # Dynamically creating buttons for all available games
    keyboard = [[InlineKeyboardButton(game, callback_data=f"game:{game}")] for game in DATABASE_FILES.keys()]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.message.edit_text("⚡ *🖕Pumili Ka Ulit Papa Mo Mamamatay🖕!*", parse_mode="Markdown", reply_markup=reply_markup)

# === FUNCTION: LOGS MENU ===
# === FUNCTION: LOGS MENU ===
async def logs_menu(update: Update, context: CallbackContext):
    user_id = update.callback_query.from_user.id
    if not has_access(user_id):
        await update.callback_query.answer("🚫 Wala kang access, gago!")
        return

    # Ensure all user IDs are strings for consistency
    log_text = "\n".join([f"👤 `{user}`: {count} generated" for user, count in logs.items()])
    log_message = f"📜 **Generation Logs**\n\n{log_text if log_text else 'Wala pang kupal na nag-generate!'}"

    await update.callback_query.message.edit_text(log_message, parse_mode="Markdown")

# FUNCTION: PAGINATED DATABASE MENU
async def database_menu(update: Update, context: CallbackContext, page=0):
    user_id = update.callback_query.from_user.id
    if not has_access(user_id):
        await update.callback_query.answer("🚫 Wala kang access!")
        return

    items_per_page = 5
    keys = list(DATABASE_FILES.keys())
    start = page * items_per_page
    end = start + items_per_page
    paginated_keys = keys[start:end]

    keyboard = [[InlineKeyboardButton(game, callback_data=f"game:{game}")] for game in paginated_keys]

    if start > 0:
        keyboard.append([InlineKeyboardButton("⬅️ Previous", callback_data=f"page:{page-1}")])
    if end < len(keys):
        keyboard.append([InlineKeyboardButton("Next ➡️", callback_data=f"page:{page+1}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.edit_text("⚡ *Pumili ng Database:*", parse_mode="Markdown", reply_markup=reply_markup)

# CALLBACK HANDLER (UPDATE)
from telegram import InputFile  # Import ito para sa pag-send ng file

async def callback_handler(update: Update, context: CallbackContext):
    query = update.callback_query

    if query.data == "database":
        await database_menu(update, context)
    elif query.data.startswith("page:"):
        _, page = query.data.split(":")
        await database_menu(update, context, int(page))
    elif query.data.startswith("game:"):
        await choose_lines(update, context)
    elif query.data.startswith("generate:"):
        await generate_file(update, context)
    elif query.data == "checker":  # <-- Idinagdag para sa checker button
        await send_checker_file(update, context)  # Tatawagin ang function para mag-send ng .txt

async def send_checker_file(update: Update, context: CallbackContext):
    """Function para gumawa at magpadala ng .txt file."""
    file_path = "checker_result.txt"

    # Gumawa ng .txt file (palitan ito ng actual data mo)
    with open(file_path, "w") as file:
        file.write("Ito ang laman ng checker file.\nPwede mong baguhin ito.")

    # Mag-send ng file
    chat_id = update.callback_query.message.chat_id
    await context.bot.send_document(chat_id=chat_id, document=InputFile(file_path))

# === FEEDBACK COMMAND ===
async def feedback(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    feedback_text = " ".join(context.args)

    if not feedback_text:
        await update.message.reply_text("⚠️ *Please provide feedback after the command.*")
        return

    # Store or process the feedback here
    await update.message.reply_text(f"✅ Thank you for your feedback: {feedback_text}")

# === REMINDER COMMAND ===
async def reminder(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ *Please use: /reminder <time> <message>*")
        return
    
    time = int(context.args[0]) * 60  # Time in minutes
    message = " ".join(context.args[1:])
    
    await update.message.reply_text(f"✅ I'll remind you in {context.args[0]} minutes about: {message}")
    
    await asyncio.sleep(time)
    
    await update.message.reply_text(f"⏰ Reminder: {message}")
    
    # === DELETE ACCESS KEY (ADMIN ONLY) ===
async def delete_key(update: Update, context: CallbackContext):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ *Access denied. Only admins can delete keys.*", parse_mode="Markdown")
        return

    if len(context.args) == 0:
        await update.message.reply_text("⚠️ *Please use: `/delete <access_key>`* to delete a key.", parse_mode="Markdown")
        return

    key_to_delete = context.args[0]

    # Tingnan kung may existing key sa ACCESS_KEYS
    if key_to_delete in ACCESS_KEYS:
        # Alisin mula sa ACCESS_KEYS
        del ACCESS_KEYS[key_to_delete]

        # Hanapin ang user na gumamit ng key at alisin ito sa USER_ACCESS
        user_to_delete = None
        for user_id, expiry_time in USER_ACCESS.items():
            if expiry_time == ACCESS_KEYS.get(key_to_delete, {}).get("expires_at"):
                user_to_delete = user_id
                break

        if user_to_delete:
            del USER_ACCESS[user_to_delete]

        save_access_data()

        await update.message.reply_text(f"✅ *The key `{key_to_delete}` has been deleted successfully and the user no longer has access.*", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ *The key you provided is invalid or doesn't exist.*", parse_mode="Markdown")

# === FUNCTION: /HELP ===
     
   
async def help_command(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    help_text = (
        "╔════════════════════════════════╗\n"
        "      🎯 *BOT COMMANDS GUIDE* 🎯\n"
        "╚════════════════════════════════╝\n\n"
        
        "📌 *USER COMMANDS:*\n"
        "┌─────────────────────────────┐\n"
        "│ ✅ `/start` – Start the bot and check your access.\n"
        "│ ✅ `/redeem <access_key>` – Use an access key to gain access.\n"
        "│ ✅ `/menu` – Open the main menu.\n"
        "│ ✅ `/reminder <time> <message>` – Set a reminder after a certain time (in minutes).\n"
        "│ ✅ `/feedback <message>` – Send feedback to the bot.\n"
        "│ ✅ `/info` – Get information about the bot.\n"
        "│ ✅ `/status` – Check key expiration status.\n"
        "│ ✅ `/joke` – Get a random joke.\n"
        "│ ✅ `/ping` – Check the bot's connectivity.\n"
        "│ ✅ `/flip` – Flip a coin (Heads or Tails).\n"
        "│ ✅ `/calculate <expression>` – Perform a math calculation (e.g., `/calculate 5+3`).\n"
        "└─────────────────────────────┘\n\n"
        
        "👑 *ADMIN COMMANDS:*\n"
        "┌─────────────────────────────┐\n"
        "│ 🔒 `/genkey <5m|10m|1h|1d|3d|7d|lifetime>` – Generate a new access key.\n"
        "│ 🔒 `/logs` – View generated file logs.\n"
        "│ 🔒 `/delete <access_key>` – Delete an access key.\n"
        "│ 🔒 `/help` – Show this help message.\n"
        "│ 🔒 `/ban <user_id>` – Ban a user.\n"
        "│ 🔒 `/unban <user_id>` – Unban a user.\n"
        "│ 🔒 `/list` – Show a list of all active keys.\n"
        "└─────────────────────────────┘\n\n"
        
        "💡 *Tip:* Use the commands properly to maximize the bot's features!\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    await update.message.reply_text(help_text, parse_mode="Markdown")

# === STATUS COMMAND ===
async def status(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id

    if has_access(user_id):
        access_expiration = USER_ACCESS.get(user_id)
        expiration_time = (
            datetime.datetime.fromtimestamp(access_expiration).strftime("%Y-%m-%d %H:%M:%S") 
            if access_expiration 
            else "Lifetime"
        )

        total_generated_files = logs.get(user_id, 0)

        status_message = (
            "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            "┃       🔧 *STATUS INFO*        ┃\n"
            "┣━━━━━━━━━━━━━━━━━━━━━━━━━━━┫\n"
            f"┃ 👤 *User:* `{update.message.from_user.username}`\n"
            f"┃ 📂 *Total Generated Files:* `{total_generated_files} files`\n"
            f"┃ ⏳ *Access Expires at:* `{expiration_time}`\n"
            "┣━━━━━━━━━━━━━━━━━━━━━━━━━━━┫\n"
            "┃ ✅ *Access Status:* `ACTIVE`\n"
            "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
            "💡 *Tip:* Make sure to monitor your access expiration and file usage!"
        )
        await update.message.reply_text(status_message, parse_mode="Markdown")

    else:
        no_access_message = (
            "🚫 *ACCESS DENIED!*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "❌ *You don't have access to generate files!*\n\n"
            "🔑 *How to Gain Access:*\n"
            "➡️ Use `/redeem <access_key>` to redeem an access key.\n\n"
            "⚠️ *Make sure you have a valid key to continue using the bot.*"
        )
        await update.message.reply_text(no_access_message, parse_mode="Markdown")
        
# === INFO COMMAND ===
async def info_command(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    info_text = (
        "╔════════════════════════════╗\n"
        "      📝 *BOT INFORMATION*      \n"
        "╚════════════════════════════╝\n\n"
        
        "🔧 *Bot Name:* `My Generator TxT`\n"
        "📅 *Creation Date:* `March 2025`\n"
        "🌟 *Version:* `1.0.0`\n"
        "👨‍💻 *Developer:* `@ihatehaze`\n\n"
        
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *MAIN FEATURES:*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "✔️ Generate text files for various games and services.\n"
        "✔️ Access secured via unique access keys.\n"
        "✔️ Admins can manage user roles and keys.\n"
        "✔️ Set reminders for important tasks.\n"
        "✔️ Feedback system to improve the bot.\n"
        "✔️ Easy-to-use interface with fast response.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        "🛠️ *HOW TO USE:*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ `/start` – Check if you have access.\n"
        "2️⃣ `/redeem <access_key>` – Redeem an access key.\n"
        "3️⃣ `/menu` – Access the available options.\n"
        "4️⃣ Generate files by selecting your desired game.\n"
        "5️⃣ `/feedback <message>` – Provide feedback to improve the bot.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        "❓ *NEED HELP?*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📲 *Contact Admin:* `@ihatehaze`\n"
        "💬 *Community Chat:* `https://t.me/HiBembang`\n"
        "🚀 *Enjoy using the bot and make the most out of it!*"
    )
    
    await update.message.reply_text(info_text, parse_mode="Markdown")
    
#=== JOKES ===

JOKES = [
    # Corny Jokes
    "Bakit hindi makapunta ang kalendaryo sa party? Kasi fully booked na siya!",
    "Ano ang tawag sa matandang isda? Eh di fish-torian!",
    "Bakit laging malungkot ang kalendaryo? Kasi bilang na ang araw niya!",
    "Anong sabi ng pader sa isa pang pader? 'Kita tayo sa kanto!'",
    "Bakit hindi makapunta sa party ang escalator? Kasi umaakyat at bumababa siya ng kusa!",
    "Anong sabi ng saging sa tao? 'Balat mo rin!'",
    "Ano ang tawag sa grupo ng mga pusa? Meow-nity!",
    "Bakit hindi marunong sumayaw ang tubig? Kasi natutunaw siya sa pressure!",
    "Bakit hindi pwede sa diet ang gatas? Kasi full cream siya!",
    "Bakit matapang ang lapis? Kasi may lead siya!",

    # Knock-Knock Jokes
    "Knock knock! Who’s there? Lettuce. Lettuce who? Lettuce in, it’s cold outside!",
    "Knock knock! Who’s there? Boo. Boo who? Boo-wag kang umiyak, joke lang yun!",
    "Knock knock! Who’s there? Orange. Orange who? Orange you glad I didn’t say banana?",
    "Knock knock! Who’s there? Cow says. Cow says who? Cow says mooo!",
    "Knock knock! Who’s there? Olive. Olive who? Olive you and I miss you!",
    "Knock knock! Who’s there? Annie. Annie who? Annie thing you can do, I can do better!",
    "Knock knock! Who’s there? Tennis. Tennis who? Tennis five plus five!",
    "Knock knock! Who’s there? Tank. Tank who? Tank you very much!",
    "Knock knock! Who’s there? Leaf. Leaf who? Leaf me alone!",
    "Knock knock! Who’s there? Ice cream. Ice cream who? Ice cream every time I see a ghost!",

    # Math and Science Jokes
    "Bakit hindi makadiskarte ang triangle? Kasi wala siyang point!",
    "Bakit hindi pwedeng magdate ang dalawang parallel lines? Kasi hindi sila magkikita!",
    "Anong sabi ng atom kay electron? 'Stop being so negative!'",
    "Bakit nahihilo ang libro ng Math? Kasi punong-puno ng problems!",
    "Anong sabi ng proton sa neutron? 'Sige na, charge na kita!'",
    "Bakit mahirap makipag-usap sa mga oxygen atom? Kasi puro O2 sila!",
    "Bakit hindi tumataba ang zero? Kasi wala siyang laman!",
    "Anong tawag sa acid na mahilig sa party? Amino acid!",
    "Bakit nag-aaway ang mga number? Kasi may division sa kanila!",
    "Bakit hindi pwedeng mag-joke sa gulong? Kasi baka sumabog sa tawa!",

    # Food Jokes
    "Anong sabi ng kape sa gatas? 'Ikaw lang ang nagpapatamis ng buhay ko!'",
    "Bakit hindi nagustuhan ng itlog ang party? Kasi scrambled siya!",
    "Anong sabi ng tinapay sa palaman? 'Ikaw ang bumubuo sa buhay ko!'",
    "Bakit hindi marunong magtago ang pizza? Kasi palaging na-cheese siya!",
    "Bakit hindi marunong magbilang ang kalabasa? Kasi laging hollow siya!",
    "Anong sabi ng ice cream sa cone? 'Huwag mo akong iiwan, matutunaw ako!'",
    "Bakit hindi makalakad ang tsokolate? Kasi nadapa sa wrapper!",
    "Bakit natakot ang itlog sa kawali? Kasi baka siya ang next sa luto!",
    "Bakit mahilig sa party ang keso? Kasi gouda vibes siya!",
    "Bakit malungkot ang tinapay? Kasi wala siyang butter half!",

    # Dark but Funny Jokes
    "Bakit hindi makatawid ang multo? Kasi wala siyang katawan!",
    "Bakit hindi natulog ang kalabasa? Kasi may hollow feeling siya!",
    "Bakit takot sa araw ang bampira? Kasi natutunaw siya sa init ng love mo!",
    "Anong sabi ng skeleton sa waiter? 'Buto lang po ang gusto ko!'",
    "Bakit hindi makatulog ang zombie? Kasi gutom na naman siya sa utak!",
    "Bakit galit ang multo sa cellphone? Kasi mahina ang signal sa kabilang buhay!",
    "Anong sabi ng ghost sa horror movie? 'Bakit ako laging bida?'",
    "Bakit malungkot ang kalansay? Kasi broken hearted siya… literally!",
    "Bakit nag-resign ang multo sa trabaho? Kasi walang body na pumapansin sa kanya!",
    "Anong sabi ng vampire sa doktor? 'Paki-check nga po ang type ng blood ko!'"
]

async def joke(update: Update, context: CallbackContext):
    joke = random.choice(JOKES)
    await update.message.reply_text(f"😂 *Here's a joke for you:* \n\n{joke}", parse_mode="Markdown")
    
#==BAN AND UNBAN ==
BANNED_USERS = set()

async def ban(update: Update, context: CallbackContext):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ *Access denied.*", parse_mode="Markdown")
        return
    
    if not context.args:
        await update.message.reply_text("⚠️ *Please provide a user ID to ban.*")
        return
    
    user_id = int(context.args[0])
    BANNED_USERS.add(user_id)
    await update.message.reply_text(f"✅ *User {user_id} has been banned.*")

async def unban(update: Update, context: CallbackContext):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ *Access denied.*", parse_mode="Markdown")
        return
    
    if not context.args:
        await update.message.reply_text("⚠️ *Please provide a user ID to unban.*")
        return
    
    user_id = int(context.args[0])
    BANNED_USERS.discard(user_id)
    await update.message.reply_text(f"✅ *User {user_id} has been unbanned.*")



# === PING COMMAND (WITH ACCESS CHECK) ===
async def ping(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    
    if not has_access(user_id):  # I-check kung may access ang user
        await update.message.reply_text("🚫 Wala kang access para gamitin ang command na ito!")
        return
    
    start_time = time.time()
    message = await update.message.reply_text("🏓 Pinging...")
    end_time = time.time()
    ping_time = (end_time - start_time) * 1000  # Convert to milliseconds
    await message.edit_text(f"🏓 Pong! Response time: `{ping_time:.2f}ms`")
    
    # === FLIP COIN===
async def flip(update: Update, context: CallbackContext):
    result = random.choice(["🪙 Heads", "🪙 Tails"])
    await update.message.reply_text(f"🎯 *Result:* {result}")
    
    

# === CALCULATE ===
async def calculate(update: Update, context: CallbackContext):
    try:
        expression = " ".join(context.args)
        result = eval(expression)
        await update.message.reply_text(f"🧮 *Result:* `{result}`")
    except Exception:
        await update.message.reply_text("❌ *Invalid expression.*")

AUTHORIZED_USERS = set()  # Gumamit ng set para mabilis ang lookup
OWNER_ID = 6365514299  # Palitan ng Telegram ID mo

#=== TO APPROVE USER ===
async def allow_user(update: Update, context: CallbackContext):
    user = update.effective_user
    if user.id != OWNER_ID:
        await update.message.reply_text("🚫 *Only the owner can use this command.*", parse_mode="Markdown")
        return
    
    if not context.args:
        await update.message.reply_text("⚠️ *Please provide a user ID to allow.*", parse_mode="Markdown")
        return
    
    try:
        user_id = int(context.args[0])
        AUTHORIZED_USERS.add(user_id)
        await update.message.reply_text(f"✅ *User {user_id} has been authorized.*", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ *Invalid user ID.*", parse_mode="Markdown")

# === FUNCTION: CHECK ACCESS KEY STATUS ===


import datetime
import pytz

AUTHORIZED_USERS = {6365514299}
ACCESS_KEYS = {
    "gN3W6P4Peia9Mb3BuFPydQ": {
        "expires_at": 1735689600,
        "redeemed_at": 1701234567,
        "redeemed_by": 6365514299
    },
    "key2": {"expires_at": None, "redeemed_at": None, "redeemed_by": None},  
}

async def list_keys(update, context):
    user = update.effective_user

    # ✅ Check if user is authorized
    if user.id not in AUTHORIZED_USERS:
        await update.message.reply_text(
            "🚫 *You are not authorized to use this command.*\n\n"
            "Please contact the admin if you believe this is a mistake. 📝\n"
            "Only authorized users can view available keys.",
            parse_mode="Markdown"
        )
        return

    if not ACCESS_KEYS:
        await update.message.reply_text(
            "❌ *No available keys at the moment.*\n\n"
            "It seems there are no active keys available for redemption right now. 😔\n"
            "Please try again later or contact the admin for assistance.",
            parse_mode="Markdown"
        )
        return

    local_tz = pytz.timezone('Asia/Manila')
    now = datetime.datetime.now(local_tz)

    # ✅ Remove expired keys
    keys_to_delete = [
        key for key, key_data in ACCESS_KEYS.items()
        if key_data.get("expires_at") and key_data["expires_at"] <= now.timestamp()
    ]
    for key in keys_to_delete:
        ACCESS_KEYS.pop(key)

    if not ACCESS_KEYS:
        await update.message.reply_text(
            "❌ *All keys have expired.*\n\n"
            "It appears that all available keys have expired and are no longer valid. ⏳\n"
            "Please check back later or contact the admin for new keys.",
            parse_mode="Markdown"
        )
        return

    # ✅ Build the key list message
    result_message = "🔑 *Available Keys:*\n\n"
    for key in ACCESS_KEYS.keys():
        result_message += f"• `{key}`\n"

    # ✅ Send the message in chunks if it's too long
    for x in range(0, len(result_message), 4000):
        await update.message.reply_text(
            result_message[x:x + 4000],
            parse_mode="Markdown"
        )



# === MAIN FUNCTION ===
def main():
    app = Application.builder().token(TOKEN).build()

    # Add handlers and start the bot
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("menu", main_menu))
    app.add_handler(CommandHandler("delete", delete_key))
    app.add_handler(CommandHandler("redeem", redeem_key))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(CommandHandler("genkey", generate_key))
    app.add_handler(CommandHandler("feedback", feedback))
    app.add_handler(CommandHandler("reminder", reminder))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("info", info_command))
    app.add_handler(CommandHandler("joke", joke))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("flip", flip))
    app.add_handler(CommandHandler("calculate", calculate))
    app.add_handler(CommandHandler("list", list_keys))
    # Start the bot (remove extra indentation)
    app.run_polling()

if __name__ == "__main__":
    main()
    
    