from datetime import datetime, date, timedelta

from config import WORK_START_HOUR, WORK_END_HOUR, SLOT_STEP_HOURS


def get_week_start(for_date: date | None = None) -> date:
    """Возвращает дату понедельника текущей (или заданной) недели."""
    d = for_date or date.today()
    return d - timedelta(days=d.weekday())


def generate_day_slots(target_date: date, duration_hours: int) -> list[datetime]:
    """Генерирует список теоретических начал слотов в рабочий день."""
    slots = []
    current = datetime(
        target_date.year, target_date.month, target_date.day, WORK_START_HOUR
    )
    end_limit = datetime(
        target_date.year, target_date.month, target_date.day, WORK_END_HOUR
    )
    while current + timedelta(hours=duration_hours) <= end_limit:
        slots.append(current)
        current += timedelta(hours=SLOT_STEP_HOURS)
    return slots


def is_working_day(d: date) -> bool:
    """Пн-Сб рабочие, воскресенье — выходной."""
    return d.weekday() < 6  # 6 = Sunday


def fmt_dt(dt: datetime) -> str:
    """Формат: 'Пт 11 апр, 10:00'"""
    days_ru = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    months_ru = [
        "", "янв", "фев", "мар", "апр", "май", "июн",
        "июл", "авг", "сен", "окт", "ноя", "дек",
    ]
    return f"{days_ru[dt.weekday()]} {dt.day} {months_ru[dt.month]}, {dt.strftime('%H:%M')}"


def fmt_date(d: date) -> str:
    """Формат: 'Пт 11 апреля'"""
    days_ru = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    months_ru = [
        "", "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря",
    ]
    return f"{days_ru[d.weekday()]}, {d.day} {months_ru[d.month]}"
