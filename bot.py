
import os
import asyncio
import logging

from aiohttp import web
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ChatJoinRequestHandler,
    ContextTypes,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

WELCOME_MESSAGE = os.getenv(
    "WELCOME_MESSAGE",
    "Welcome! Your join request has been approved."
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

stats = {"approved": 0}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to Karthik Auto Approve Bot!\n"
        "I automatically approve join requests."
    )


async def approve_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request = update.chat_join_request
    user = request.from_user

    try:
        await context.bot.approve_chat_join_request(
            chat_id=request.chat.id,
            user_id=user.id
        )

        stats["approved"] += 1

        logger.info("Approved user %s", user.id)

        try:
            await context.bot.send_message(
                chat_id=user.id,
                text=WELCOME_MESSAGE
            )
        except Exception:
            logger.info("Welcome message could not be delivered")

    except Exception:
        logger.exception("Approval failed")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        f"Bot Statistics\nTotal Approved: {stats['approved']}"
    )


async def health(request):
    return web.Response(text="Karthik Bot is Running!")


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing!")

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(ChatJoinRequestHandler(approve_request))

    await application.initialize()
    await application.start()
    await application.updater.start_polling(
        allowed_updates=["message", "chat_join_request"]
    )

    web_app = web.Application()
    web_app.router.add_get("/", health)
    web_app.router.add_get("/health", health)

    runner = web.AppRunner(web_app)
    await runner.setup()

    port = int(os.getenv("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info("Karthik Auto Approve Bot started")

    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
    
