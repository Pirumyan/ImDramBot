import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

CATEGORIES = {
    "1": "Еда 🍔",
    "2": "Кафе и доставка ☕",
    "3": "Транспорт 🚕",
    "4": "Жильё 🏠",
    "5": "Коммунальные 💡",
    "6": "Здоровье 💊",
    "7": "Одежда 👕",
    "8": "Развлечения 🎯",
    "9": "Другое 📦"
}

NORMS = {
    "Еда 🍔": (0.3, 0.35),
    "Жильё 🏠": (0.25, 0.35),
    "Коммунальные 💡": (0.1, 0.2),
    "Кафе и доставка ☕": (0, 0.15),
    "Транспорт 🚕": (0.1, 0.2)
}

INCOME_CATEGORIES = {
    "1": "Зарплата 💰",
    "2": "Перевод 💸",
    "3": "Кешбэк 🪙",
    "4": "Крипта 💎",
    "5": "Другое 📦"
}

ADMIN_ID = int(os.getenv("ADMIN_ID", 416416790))
