from dotenv import load_dotenv
import os

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL")
MODEL = os.getenv("MODEL")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
AUTHORIZED_USERS = int(os.getenv("AUTHORIZED_USERS"))

