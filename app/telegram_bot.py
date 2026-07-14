import json
import os
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from telegram.ext import CallbackQueryHandler, JobQueue

from config import TELEGRAM_TOKEN
from config import AUTHORIZED_USERS
from ollama import OllamaClient

from assistant import Assistant

assistant = Assistant()

MAX_TELEGRAM_MESSAGE_LENGTH = 4000
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
NEWS_API_KEY = os.getenv("GNEWS_API_KEY") or os.getenv("NEWS_API_KEY")
WEATHER_CITY = os.getenv("WEATHER_CITY", "Vantaa")


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


def fetch_weather() -> str:

    try:
        forecast_url = (
            "https://api.open-meteo.com/v1/forecast?"
            "latitude=52.52&longitude=13.41&"
            "hourly=temperature_2m,precipitation,precipitation_probability,"
            "relative_humidity_2m,weather_code,wind_speed_10m&"
            "current=temperature_2m,is_day,precipitation,relative_humidity_2m,"
            "weather_code,wind_speed_10m&"
            "timezone=Europe/Helsinki"
        )
        forecast_response = requests.get(forecast_url, timeout=10)
        forecast_response.raise_for_status()
        forecast_data = forecast_response.json()

        return forecast_data
    except Exception as exc:
        return f"Weather update unavailable right now: {exc}"


def parse_weather_time(value: Optional[str], source_timezone: Optional[str] = None):
    if not value:
        return None

    try:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            tz_name = source_timezone or "GMT"
            dt = dt.replace(tzinfo=ZoneInfo(tz_name))
        return dt.astimezone(ZoneInfo("Europe/Helsinki"))
    except Exception:
        return None


def summarize_weather_forecast(weather_data: dict) -> str:
    try:
        current = weather_data.get("current", {})
        hourly = weather_data.get("hourly", {})
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        humidity = hourly.get("relative_humidity_2m", [])
        wind = hourly.get("wind_speed_10m", [])
        precipitation = hourly.get("precipitation", [])
        precipitation_probability = hourly.get("precipitation_probability", [])
        weather_codes = hourly.get("weather_code", [])

        if not times or not temps:
            return "Weather data unavailable."

        current_temp = current.get("temperature_2m")
        current_wind = current.get("wind_speed_10m")
        current_humidity = current.get("relative_humidity_2m")
        current_precipitation = current.get("precipitation")
        current_weather_code = current.get("weather_code")
        current_is_day = current.get("is_day")
        current_time = current.get("time")
        source_timezone = weather_data.get("timezone") or weather_data.get("timezone_abbreviation") or "GMT"

        current_dt = None
        if current_time:
            current_dt = parse_weather_time(current_time, source_timezone)
            current_time_str = current_dt.strftime("%I:%M %p") if current_dt else current_time
        else:
            current_time_str = "now"

        weather_code_map = {
            0: "clear sky",
            1: "mainly clear",
            2: "partly cloudy",
            3: "overcast",
            45: "fog",
            48: "depositing rime fog",
            51: "light drizzle",
            53: "moderate drizzle",
            55: "dense drizzle",
            61: "slight rain",
            63: "moderate rain",
            65: "heavy rain",
            71: "slight snow",
            73: "moderate snow",
            75: "heavy snow",
            95: "thunderstorm",
        }

        current_desc = weather_code_map.get(current_weather_code, f"weather code {current_weather_code}")
        day_state = "daytime" if current_is_day == 1 else "nighttime"

        summary_lines = []
        summary_lines.append(
            f"Current weather at {current_time_str} Helsinki time: {current_temp}°C, {current_desc}, humidity {current_humidity}%, precipitation {current_precipitation} mm, wind {current_wind} km/h, {day_state}."
        )

        sample_points = []
        start_index = 0
        if current_dt:
            for idx, time_value in enumerate(times):
                parsed_time = parse_weather_time(time_value, source_timezone)
                if parsed_time and parsed_time >= current_dt:
                    start_index = idx
                    break

        for i in range(start_index, min(start_index + 8, len(times))):
            time_value = times[i]
            temp_value = temps[i]
            humidity_value = humidity[i] if i < len(humidity) else None
            wind_value = wind[i] if i < len(wind) else None
            precip_value = precipitation[i] if i < len(precipitation) else None
            precip_prob_value = precipitation_probability[i] if i < len(precipitation_probability) else None
            weather_code_value = weather_codes[i] if i < len(weather_codes) else None
            weather_desc = weather_code_map.get(weather_code_value, f"weather code {weather_code_value}")

            local_dt = parse_weather_time(time_value, source_timezone)
            if local_dt:
                hour_label = local_dt.strftime("%I:%M %p")
            else:
                hour_label = time_value.split("T")[1]

            parts = [f"{hour_label}: {temp_value}°C, {weather_desc}"]
            if humidity_value is not None:
                parts.append(f"humidity {humidity_value}%")
            if precip_value is not None:
                parts.append(f"precipitation {precip_value} mm")
            if precip_prob_value is not None:
                parts.append(f"precip prob {precip_prob_value}%")
            if wind_value is not None:
                parts.append(f"wind {wind_value} km/h")
            sample_points.append("; ".join(parts))

        summary_lines.append("Next hours (Helsinki time): " + " | ".join(sample_points))
        return "\n".join(summary_lines)
    except Exception as exc:
        return f"Weather data unavailable: {exc}"


def fetch_news() -> str:

    try:
        if NEWS_API_KEY:
            url = "https://gnews.io/api/v4/top-headlines"
            params = {"token": NEWS_API_KEY, "lang": "en", "country": "us", "max": 3}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            articles = data.get("articles", [])
        else:
            return "News update unavailable right now: set GNEWS_API_KEY or NEWS_API_KEY."

        if not articles:
            return "No news headlines available right now."

        lines = ["Latest news:"]
        for article in articles[:3]:
            title = article.get("title") or "Untitled"
            lines.append(f"- {title}")
        return "\n".join(lines)
    except Exception as exc:
        return f"News update unavailable right now: {exc}"


def build_context_prompt(user_message: str, *, weather_summary: str, latest_news: str, now: str, is_daily_notification: bool = False) -> str:
    if is_daily_notification:
        instruction = (
            "morning daily notification\n"
            "Treat this as a short morning weather summary for the user. "
            "State current date/time as stated in the timestamp. Write one concise summary, as bullet points, very short using only the provided weather summary, and wish good morning. Also mention hourly temperature for the next 3 hours after the timestamp."
            "Do not invent missing details."
        )
    else:
        instruction = "Answer using only the weather/news summary above. Do not invent missing details."

    return (
        f"Current timestamp: {now}\n"
        f"Weather broadcast (hour-by-hour summary):\n{weather_summary}\n"
        f"Latest news data: {latest_news}\n\n"
        f"{instruction}\n"
        f"{user_message}"
    )


async def send_weather_notification(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(ZoneInfo("Europe/Helsinki")).isoformat()
    weather_data = fetch_weather()
    assistant.update_global_value("weather_broadcast", weather_data)
    assistant.update_global_value("current_timestamp", now)

    weather_summary = summarize_weather_forecast(weather_data)
    latest_news = assistant.state.get("latest_news", "No news available.")
    if not latest_news:
        latest_news = "No news available."

    prompt = build_context_prompt(
        "Please provide the morning daily weather summary.",
        weather_summary=weather_summary,
        latest_news=latest_news,
        now=now,
        is_daily_notification=True,
    )

    response = assistant.chat(prompt, save_to_history=False)
    for chunk in split_message(response):
        await context.bot.send_message(chat_id=AUTHORIZED_USERS, text=chunk)


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

    lower_message = user_message.lower()

    if "weather" in lower_message:
        now = datetime.now(ZoneInfo("Europe/Helsinki")).isoformat()
        weather_data = fetch_weather()
        assistant.update_global_value("weather_broadcast", weather_data)
        assistant.update_global_value("current_timestamp", now)

        weather_summary = summarize_weather_forecast(weather_data)
        latest_news = assistant.state.get("latest_news", "No news available.")
        if not latest_news:
            latest_news = "No news available."

        context_prompt = build_context_prompt(
            user_message,
            weather_summary=weather_summary,
            latest_news=latest_news,
            now=now,
            is_daily_notification=False,
        )

        response = assistant.chat(context_prompt)
        for chunk in split_message(response):
            await update.message.reply_text(chunk)
        return

    if "news" in lower_message:
        now = datetime.now(ZoneInfo("Europe/Helsinki")).isoformat()
        news_text = fetch_news()
        assistant.update_global_value("latest_news", news_text)
        assistant.update_global_value("current_timestamp", now)

        weather_data = assistant.state.get("weather_broadcast", "No weather available.")
        weather_summary = (
            summarize_weather_forecast(weather_data)
            if isinstance(weather_data, dict)
            else "No weather available."
        )

        context_prompt = build_context_prompt(
            user_message,
            weather_summary=weather_summary,
            latest_news=news_text,
            now=now,
            is_daily_notification=False,
        )

        response = assistant.chat(context_prompt)
        for chunk in split_message(response):
            await update.message.reply_text(chunk)
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

    if app.job_queue is None:
        app.job_queue = JobQueue()

    app.add_handler(

        CallbackQueryHandler(button)

    )
    
    app.add_handler(
        MessageHandler(filters.TEXT, handle_message)
    )

    app.job_queue.run_repeating(send_weather_notification, interval=86400, first=0)

    print("Telegram bot started!")

    app.run_polling()