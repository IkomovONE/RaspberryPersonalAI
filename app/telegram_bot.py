from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import TELEGRAM_TOKEN
from config import AUTHORIZED_USERS
from ollama import OllamaClient

ai = OllamaClient()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != AUTHORIZED_USERS:
        await update.message.reply_text("Sorry, this bot is private.")
        return

    if update.message is None:
        return
    
    

    user_message = update.message.text

    print(f"User: {user_message}")

    response = ai.ask(user_message)

    print(f"AI: {response}")

    await update.message.reply_text(response)


def run():

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(
        
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    print("Telegram bot started!")
    

    app.run_polling()