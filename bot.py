
import os
import sqlite3
from aiohttp import web

from telegram import (
    Update,
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeChat,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ChatJoinRequestHandler,
    ChatMemberHandler,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PORT = int(os.getenv("PORT", "10000"))
DB_FILE = "bot_data.db"

DEFAULT_WELCOME = (
    "🎉✨ WELCOME TO MY CINE SPOT ✨🎉\n\n"
    "👋 Welcome, Dear!\n\n"
    "💖 H r u? Hope you're doing great!\n\n"
    "🍿 Enjoy Your Time With My Cine Spot! ❤️"
)

START_MESSAGE = (
    "👋✨ WELCOME TO MY CINE SPOT BOT ✨\n\n"
    "🎬 EVERY UPDATE AVAILABLE HERE!\n\n"
    "🔥 Movies • Web Series • Latest Updates\n\n"
    "📢 Don't Miss Any Updates!\n\n"
    "👇 JOIN OUR OFFICIAL CHANNEL\n\n"
    "🔗 https://whatsapp.com/channel/0029VbCN6zUFsn0b2goG6r2C\n\n"
    "❤️ Stay Connected With My Cine Spot!"
)

recent_requests = set()
web_runner = None


# DATABASE
def db():
    return sqlite3.connect(DB_FILE)


def init_db():
    with db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY,
                name TEXT,
                joins INTEGER DEFAULT 0,
                leaves INTEGER DEFAULT 0
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        con.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            ("welcome", DEFAULT_WELCOME)
        )


def get_welcome():
    with db() as con:
        row = con.execute(
            "SELECT value FROM settings WHERE key='welcome'"
        ).fetchone()
        return row[0] if row else DEFAULT_WELCOME


def save_welcome(message):
    with db() as con:
        con.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("welcome", message)
        )


def update_chat(chat):
    with db() as con:
        con.execute("""
            INSERT INTO chats (chat_id, name)
            VALUES (?, ?)
            ON CONFLICT(chat_id)
            DO UPDATE SET name=excluded.name
        """, (chat.id, chat.title or "Unknown"))


def count_event(chat, event):
    with db() as con:
        con.execute(
            f"UPDATE chats SET {event} = {event} + 1 WHERE chat_id=?",
            (chat.id,)
        )


def get_chats():
    with db() as con:
        return con.execute(
            "SELECT chat_id, name, joins, leaves FROM chats"
        ).fetchall()


def is_admin(user_id):
    return user_id == ADMIN_ID


async def send_admin(context, message):
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=message
        )
    except Exception as e:
        print("Admin notification error:", e)


def user_details(user):
    username = f"@{user.username}" if user.username else "No username"
    return (
        f"Name: {user.full_name}\n"
        f"Username: {username}\n"
        f"User ID: {user.id}"
    )


def is_member(member):
    return (
        member.status in ("member", "administrator", "creator")
        or (
            member.status == "restricted"
            and member.is_member
        )
    )


# START COMMAND
async def start(update, context):
    await update.message.reply_text(START_MESSAGE)


# SET WELCOME
async def setwelcome(update, context):
    if not is_admin(update.effective_user.id):
        return

    message = update.message.text.partition(" ")[2].strip()

    if not message:
        await update.message.reply_text(
            "❌ Usage:\n/setwelcome Your Welcome Message"
        )
        return

    save_welcome(message)

    await update.message.reply_text(
        "✅ Welcome Message Updated Successfully!\n"
        "இனி Group-ல் புதிய Member Join ஆனதும் இந்த Message வரும்."
    )


# VIEW WELCOME
async def welcome(update, context):
    if not is_admin(update.effective_user.id):
        return

    await update.message.reply_text(
        "📩 CURRENT WELCOME MESSAGE\n\n" + get_welcome()
    )


# STATS
async def stats(update, context):
    if not is_admin(update.effective_user.id):
        return

    chats = get_chats()

    if not chats:
        await update.message.reply_text(
            "இன்னும் எந்த Group / Channel activity-யும் இல்லை."
        )
        return

    result = "📊 MY CINE SPOT - STATISTICS\n\n"

    for chat_id, name, joins, leaves in chats:
        try:
            count = await context.bot.get_chat_member_count(chat_id)
            members = str(count)
        except Exception:
            members = "Unavailable"

        result += (
            f"📢 {name}\n"
            f"🆔 {chat_id}\n"
            f"👥 Current Members: {members}\n"
            f"📥 Recorded Joins: {joins}\n"
            f"📤 Recorded Leaves: {leaves}\n\n"
        )

    await update.message.reply_text(result)


# AUTO APPROVE JOIN REQUEST
async def approve_request(update, context):
    request = update.chat_join_request
    chat = request.chat
    user = request.from_user

    update_chat(chat)
    key = (chat.id, user.id)
    recent_requests.add(key)

    try:
        await context.bot.approve_chat_join_request(
            chat_id=chat.id,
            user_id=user.id
        )
    except Exception as e:
        recent_requests.discard(key)
        await send_admin(
            context,
            f"❌ JOIN APPROVAL FAILED\n\n"
            f"Channel: {chat.title}\n"
            f"User ID: {user.id}\n"
            f"Error: {e}"
        )
        return

    count_event(chat, "joins")

    bot = await context.bot.get_me()

    await send_admin(
        context,
        "🔔 JOIN REQUEST\n\n"
        f"Bot: @{bot.username}\n"
        f"Channel: {chat.title}\n"
        f"Channel ID: {chat.id}\n\n"
        f"{user_details(user)}\n\n"
        "Approval: ✅ Approved\n"
        "Welcome: Group Welcome applies when joining the Group"
    )


# GROUP / CHANNEL MEMBER UPDATES
async def member_update(update, context):
    change = update.chat_member

    chat = change.chat
    old_member = change.old_chat_member
    new_member = change.new_chat_member
    user = new_member.user

    if user.is_bot:
        return

    update_chat(chat)

    was_member = is_member(old_member)
    now_member = is_member(new_member)

    key = (chat.id, user.id)

    if not was_member and now_member:

        if key in recent_requests:
            recent_requests.discard(key)
            return

        count_event(chat, "joins")

        # Group welcome message
        if chat.type in ("group", "supergroup"):
            try:
                await context.bot.send_message(
                    chat_id=chat.id,
                    text=get_welcome()
                )
                welcome_status = "✅ Sent in Group"
            except Exception as e:
                print("Group welcome error:", e)
                welcome_status = "⚠️ Not Sent"
        else:
            welcome_status = "Channel member joined"

        bot = await context.bot.get_me()

        await send_admin(
            context,
            "🔔 NEW MEMBER JOINED\n\n"
            f"Bot: @{bot.username}\n"
            f"Chat: {chat.title}\n"
            f"Chat ID: {chat.id}\n\n"
            f"{user_details(user)}\n\n"
            "Status: ✅ Joined\n"
            f"Welcome: {welcome_status}"
        )

    elif was_member and not now_member:

        count_event(chat, "leaves")

        await send_admin(
            context,
            "📤 MEMBER LEFT\n\n"
            f"Chat: {chat.title}\n"
            f"Chat ID: {chat.id}\n\n"
            f"{user_details(user)}\n\n"
            "Status: ❌ Left"
        )


# HEALTH SERVER
async def health(request):
    return web.Response(text="My Cine Spot Bot is running!")


async def post_init(application):
    global web_runner

    # Public command menu
    await application.bot.set_my_commands([
        BotCommand("start", "Start My Cine Spot Bot")
    ], scope=BotCommandScopeDefault())

    # Admin-only command menu
    if ADMIN_ID:
        await application.bot.set_my_commands([
            BotCommand("start", "Start My Cine Spot Bot"),
            BotCommand("setwelcome", "Set Group Welcome Message"),
            BotCommand("welcome", "View Welcome Message"),
            BotCommand("stats", "View Channel / Group Statistics"),
        ], scope=BotCommandScopeChat(chat_id=ADMIN_ID))

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    web_runner = web.AppRunner(app)
    await web_runner.setup()

    site = web.TCPSite(
        web_runner,
        "0.0.0.0",
        PORT
    )
    await site.start()

    print("Health server started")


async def post_shutdown(application):
    global web_runner

    if web_runner:
        await web_runner.cleanup()


# MAIN
def main():
    if not BOT_TOKEN or not ADMIN_ID:
        raise RuntimeError(
            "BOT_TOKEN and ADMIN_ID are required"
        )

    init_db()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )
    application.add_handler(
        CommandHandler("setwelcome", setwelcome)
    )
    application.add_handler(
        CommandHandler("welcome", welcome)
    )
    application.add_handler(
        CommandHandler("stats", stats)
    )

    application.add_handler(
        ChatJoinRequestHandler(approve_request)
    )

    application.add_handler(
        ChatMemberHandler(
            member_update,
            ChatMemberHandler.CHAT_MEMBER
        )
    )

    print("MY CINE SPOT BOT STARTED!")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
            
