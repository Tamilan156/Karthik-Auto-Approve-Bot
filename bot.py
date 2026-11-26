
import os
import asyncio
from aiohttp import web
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ChatJoinRequestHandler,
    ChatMemberHandler,
    ContextTypes,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PORT = int(os.getenv("PORT", "10000"))

WELCOME_MESSAGE = os.getenv(
    "WELCOME_MESSAGE",
    "🎉 Welcome to My Cine Spot!\n\nEnjoy watching! ❤️"
)

channels = {}
recent_join_requests = set()
web_runner = None


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


async def send_welcome(context, user_id):
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=WELCOME_MESSAGE
        )
        return "✅ Sent"
    except Exception as e:
        print("Welcome message error:", e)
        return "⚠️ Not Sent"


def update_channel(chat):
    chat_id = chat.id

    if chat_id not in channels:
        channels[chat_id] = {
            "name": chat.title or "Unknown Channel",
            "joins": 0,
            "leaves": 0
        }
    else:
        channels[chat_id]["name"] = (
            chat.title or channels[chat_id]["name"]
        )


def user_details(user):
    name = user.full_name or "Unknown"
    username = f"@{user.username}" if user.username else "No username"

    return (
        f"Name: {name}\n"
        f"Username: {username}\n"
        f"User ID: {user.id}"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to My Cine Spot Bot!\n\n"
        "இந்த Bot-ல் Join Request தானாக Approve செய்யப்படும்.\n"
        "Channel-ல் Join ஆனதும் Welcome Message அனுப்பப்படும்."
    )


async def setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not is_admin(user.id):
        return

    global WELCOME_MESSAGE

    message = " ".join(context.args).strip()

    if not message:
        await update.message.reply_text(
            "❌ Usage:\n/setwelcome Your Welcome Message"
        )
        return

    WELCOME_MESSAGE = message

    await update.message.reply_text(
        "✅ Welcome Message Updated Successfully!"
    )


async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    await update.message.reply_text(
        f"📩 Current Welcome Message:\n\n{WELCOME_MESSAGE}"
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not channels:
        await update.message.reply_text(
            "இன்னும் எந்த Channel-லும் Bot activity இல்லை."
        )
        return

    result = "📊 MY CINE SPOT - CHANNEL STATS\n\n"

    for chat_id, data in channels.items():
        try:
            count = await context.bot.get_chat_member_count(chat_id)
            member_count = str(count)
        except Exception:
            member_count = "Unavailable"

        result += (
            f"📢 {data['name']}\n"
            f"🆔 {chat_id}\n"
            f"👥 Current Members: {member_count}\n"
            f"📥 Recorded Joins: {data['joins']}\n"
            f"📤 Recorded Leaves: {data['leaves']}\n\n"
        )

    await update.message.reply_text(result)


async def approve_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    request = update.chat_join_request
    chat = request.chat
    user = request.from_user

    update_channel(chat)

    key = (chat.id, user.id)
    recent_join_requests.add(key)

    try:
        await context.bot.approve_chat_join_request(
            chat_id=chat.id,
            user_id=user.id
        )
    except Exception as e:
        recent_join_requests.discard(key)
        await send_admin(
            context,
            f"❌ JOIN APPROVAL FAILED\n\n"
            f"Channel: {chat.title}\n"
            f"User ID: {user.id}\n"
            f"Error: {e}"
        )
        return

    channels[chat.id]["joins"] += 1

    welcome_status = await send_welcome(context, user.id)

    bot = await context.bot.get_me()

    message = (
        "🔔 JOIN REQUEST\n\n"
        f"Bot: @{bot.username}\n"
        f"Channel: {chat.title}\n"
        f"Channel ID: {chat.id}\n\n"
        f"{user_details(user)}\n\n"
        "Approval: ✅ Approved\n"
        f"Welcome: {welcome_status}"
    )

    await send_admin(context, message)


def is_member(member):
    return (
        member.status in ("member", "administrator", "creator")
        or (
            member.status == "restricted"
            and member.is_member
        )
    )


async def member_update(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    change = update.chat_member

    chat = change.chat
    old_member = change.old_chat_member
    new_member = change.new_chat_member
    user = new_member.user

    update_channel(chat)

    was_member = is_member(old_member)
    now_member = is_member(new_member)

    key = (chat.id, user.id)

    # New member joined
    if not was_member and now_member:

        # Join request handler already handled this member
        if key in recent_join_requests:
            recent_join_requests.discard(key)
            return

        channels[chat.id]["joins"] += 1

        welcome_status = await send_welcome(context, user.id)

        bot = await context.bot.get_me()

        message = (
            "🔔 NEW MEMBER JOINED\n\n"
            f"Bot: @{bot.username}\n"
            f"Channel: {chat.title}\n"
            f"Channel ID: {chat.id}\n\n"
            f"{user_details(user)}\n\n"
            "Status: ✅ Joined\n"
            f"Welcome: {welcome_status}"
        )

        await send_admin(context, message)

    # Member left or was removed
    elif was_member and not now_member:

        channels[chat.id]["leaves"] += 1

        message = (
            "📤 MEMBER LEFT\n\n"
            f"Channel: {chat.title}\n"
            f"Channel ID: {chat.id}\n\n"
            f"{user_details(user)}\n\n"
            "Status: ❌ Left"
        )

        await send_admin(context, message)


async def health(request):
    return web.Response(text="Bot is running!")


async def post_init(application):
    global web_runner

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


def main():
    if not BOT_TOKEN or not ADMIN_ID:
        raise RuntimeError("BOT_TOKEN and ADMIN_ID are required")

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setwelcome", setwelcome))
    application.add_handler(CommandHandler("welcome", welcome))
    application.add_handler(CommandHandler("stats", stats))

    application.add_handler(
        ChatJoinRequestHandler(approve_request)
    )

    application.add_handler(
        ChatMemberHandler(
            member_update,
            ChatMemberHandler.CHAT_MEMBER
        )
    )

    print("My Cine Spot Bot Started!")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
    
