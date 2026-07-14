from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from telegram.ext import CallbackQueryHandler

from config import TELEGRAM_TOKEN
from config import AUTHORIZED_USERS
from ollama import OllamaClient

from assistant import Assistant

assistant = Assistant()

MAX_TELEGRAM_MESSAGE_LENGTH = 4000


def split_message(text: str, max_length: int = MAX_TELEGRAM_MESSAGE_LENGTH):
    if len(text) <= max_length:
        return [text]

    chunks = []
    remaining = text

    while len(remaining) > max_length:
        split_index = remaining.rfind("\n", 0, max_length)
        if split_index == -1:
            split_index = remaining.rfind(" ", 0, max_length)

        if split_index <= 0:
            split_index = max_length

        chunk = remaining[:split_index].rstrip()
        if chunk:
            chunks.append(chunk)

        remaining = remaining[split_index:].lstrip()

    if remaining:
        chunks.append(remaining)

    return chunks


def chat_keyboard(action="switch"):

    keyboard = []

    for chat_name in assistant.list_chats():

        keyboard.append([

            InlineKeyboardButton(

                chat_name,

                callback_data=f"{action}:{chat_name}"

            )

        ])

    keyboard.append([

        InlineKeyboardButton(

            "➕ New Chat",

            callback_data="newchat"

        )

    ])

    return InlineKeyboardMarkup(keyboard)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.message is None:
        return

    user_message = update.message.text.strip()

    # Authorization
    if update.effective_user.id != AUTHORIZED_USERS:
        await update.message.reply_text("Sorry, this bot is private.")
        return

    if context.user_data.get("awaiting_chat_name"):
        context.user_data["awaiting_chat_name"] = False

        if not user_message:
            await update.message.reply_text("Please enter a chat name.")
            return

        if assistant.new_chat(user_message):
            await update.message.reply_text(
                f'Created and switched to "{user_message}".'
            )
        else:
            await update.message.reply_text(
                "A chat with that name already exists."
            )

        return

    #
    # Commands
    #

    if user_message.startswith("/newchat"):

        name = user_message.removeprefix("/newchat").strip()

        if not name:
            context.user_data["awaiting_chat_name"] = True
            await update.message.reply_text("What would be the name for the chat?")
            return

        if assistant.new_chat(name):
            await update.message.reply_text(
                f'Created and switched to "{name}".'
            )
        else:
            await update.message.reply_text(
                "A chat with that name already exists."
            )

        return

    if user_message.startswith("/switch"):

        name = user_message.removeprefix("/switch").strip()

        if assistant.switch_chat(name):
            await update.message.reply_text(
                f'Switched to "{name}".'
            )
        else:
            await update.message.reply_text(
                "Chat not found."
            )

        return

    if user_message in {"/chats", "/list"}:

        await update.message.reply_text(
            "Choose a chat:",
            reply_markup=chat_keyboard("switch")
        )

        return

    if user_message == "/deletechat":

        await update.message.reply_text(
            "Select a chat to delete:",
            reply_markup=chat_keyboard("delete")
        )

        return

    #
    # Normal AI conversation
    #

    response = assistant.chat(user_message)

    for chunk in split_message(response):
        await update.message.reply_text(chunk)

async def button(update, context):

    query = update.callback_query

    await query.answer()

    data = query.data

    if data.startswith("switch:"):

        chat_name = data.split(":", 1)[1]

        assistant.switch_chat(chat_name)

        await query.edit_message_text(

            f"Switched to {assistant.current_chat_name()}",

            reply_markup=chat_keyboard("switch")

        )

    elif data.startswith("delete:"):

        chat_name = data.split(":", 1)[1]

        assistant.delete_chat(chat_name)

        await query.edit_message_text(
            f"Deleted chat '{chat_name}'.",
            reply_markup=chat_keyboard("delete")
        )

    elif data == "newchat":

        context.user_data["awaiting_chat_name"] = True

        await query.edit_message_text(
            "What would be the name for the chat?"
        )


def run():

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(

        CallbackQueryHandler(button)

    )
    
    app.add_handler(
        MessageHandler(filters.TEXT, handle_message)
    )

    print("Telegram bot started!")

    app.run_polling()