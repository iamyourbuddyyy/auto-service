import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    bot_token: str
    admin_password: str
    database_url: str
    tz: str


settings = Settings(
    bot_token=os.getenv("BOT_TOKEN", ""),
    admin_password=os.getenv("ADMIN_PASSWORD", ""),
    database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./autoservice.db"),
    tz=os.getenv("TZ", "Europe/Moscow"),
)

# Типы услуг: код → название + длительность в часах
SERVICE_TYPES: dict[str, dict] = {
    "to":         {"name": "ТО",              "duration": 1},
    "diagnostic": {"name": "Диагностика",     "duration": 1},
    "tire":       {"name": "Шиномонтаж",      "duration": 1},
    "body":       {"name": "Кузовной ремонт", "duration": 4},
    "electric":   {"name": "Электрика",       "duration": 2},
    "mechanic":   {"name": "Слесарка",        "duration": 2},
}

WORK_START_HOUR = 9
WORK_END_HOUR = 21
LIFT_COUNT = 4
MASTER_COUNT = 6
SLOT_STEP_HOURS = 1
MAX_SLOTS_SHOWN = 8
DAYS_AHEAD = 14  # Сколько дней вперёд искать свободные слоты
