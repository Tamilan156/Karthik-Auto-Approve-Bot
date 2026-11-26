
import os
import logging
import time
from collections import defaultdict, deque

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ChatJoinRequestHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}
WELCOME_MESSAGE = os.getenv(
    "WELCOME_MESSAGE",
    "Welcome! Your join request has been approved."
)

SPAM_BAN_ENABLED = os.getenv("SPAM_BAN_ENABLED", "false").lower() == "true"
SPAM_THRESHOLD = int(os.getenv("SPAM_THRESHOLD", "5"))
SPAM_WINDOW_SECONDS = int(os.getenv("SPAM_WINDOW_SECONDS", "20"))

WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]
RENDER_URL = os.environ["RENDER_EXTERNAL_URL"].rstrip("/")
PORT = int(os.environ.get("PORT", "10000"))

user_messages = defaultdict(deque)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "Bot is running! Welcome."
    )


async def approve_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    request = update.chat_join_request

    try:
        await context.bot.approve_chat_join_request(
            chat_id=request.chat.id,
            user_id=request.from_user.id,
        )

        await context.bot.send_message(
            chat_id=request.chat.id,
            text=WELCOME_MESSAGE,
        )

        logger.info("Approved user %s", request.from_user.id)

    except Exception:
        logger.exception("Could not approve join request")


async def is_admin(update: Update) -> bool:
    user = update.effective_user
    if user and user.id in ADMIN_IDS:
        return True

    await update.effective_message.reply_text(
        "You are not authorized to use this command."
    )
    return False


async def ban_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not await is_admin(update):
        return

    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text(
            "Usage: /ban USER_ID"
        )
        return

    user_id = int(context.args[0])

    try:
        await context.bot.ban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=user_id,
        )
        await update.effective_message.reply_text(
            f"User {user_id} has been banned."
        )
    except Exception:
        logger.exception("Ban failed")
        await update.effective_message.reply_text(
            "Ban failed. Check bot permissions and user ID."
        )


async def unban_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not await is_admin(update):
        return

    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text(
            "Usage: /unban USER_ID"
        )
        return

    user_id = int(context.args[0])

    try:
        await context.bot.unban_chat_member(
            chat_id=update.effective_chat.id,
            user_id=user_id,
            only_if_banned=True,
        )
        await update.effective_message.reply_text(
            f"User {user_id} has been unbanned."
        )
    except Exception:
        logger.exception("Unban failed")
        await update.effective_message.reply_text(
            "Unban failed. Check bot permissions and user ID."
        )


async def detect_spam(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not SPAM_BAN_ENABLED:
        return

    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not user or not chat:
        return

    if user.is_bot or user.id in ADMIN_IDS:
        return

    now = time.monotonic()
    key = (chat.id, user.id)
    timestamps = user_messages[key]

    timestamps.append(now)

    while timestamps and now - timestamps[0] > SPAM_WINDOW_SECONDS:
        timestamps.popleft()

    if len(timestamps) >= SPAM_THRESHOLD:
        try:
            await context.bot.ban_chat_member(
                chat_id=chat.id,
                user_id=user.id,
            )
            user_messages.pop(key, None)
            logger.info("Spam banned user %s", user.id)
        except Exception:
            logger.exception("Spam ban failed")


def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        ChatJoinRequestHandler(approve_request)
    )
    application.add_handler(CommandHandler("ban", ban_user))
    application.add_handler(CommandHandler("unban", unban_user))

    application.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.TEXT
            & ~filters.COMMAND,
            detect_spam,
        )
    )

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="telegram",
        webhook_url=f"{RENDER_URL}/telegram",
        secret_token=WEBHOOK_SECRET,
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
  
