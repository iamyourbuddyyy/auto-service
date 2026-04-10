import logging
from datetime import datetime, timedelta

from aiogram import Bot
from sqlalchemy.ext.asyncio import async_sessionmaker

from db import repository as repo
from services import notifications

logger = logging.getLogger(__name__)


async def send_reminders_job(bot: Bot, session_factory: async_sessionmaker) -> None:
    """Отправляет напоминания за 24ч и за 2ч до записи."""
    now = datetime.now()

    async with session_factory() as session:
        # Напоминание за 24 часа (окно ±15 минут)
        w24_start = now + timedelta(hours=23, minutes=45)
        w24_end = now + timedelta(hours=24, minutes=15)
        appts_24h = await repo.get_appointments_for_reminder(session, w24_start, w24_end, "24h")
        for appt in appts_24h:
            await notifications.send_reminder(bot, appt, hours=24)
            await repo.mark_reminder_sent(session, appt.id, "24h")
            logger.info(f"Sent 24h reminder for appt {appt.id}")

        # Напоминание за 2 часа (окно ±15 минут)
        w2_start = now + timedelta(hours=1, minutes=45)
        w2_end = now + timedelta(hours=2, minutes=15)
        appts_2h = await repo.get_appointments_for_reminder(session, w2_start, w2_end, "2h")
        for appt in appts_2h:
            await notifications.send_reminder(bot, appt, hours=2)
            await repo.mark_reminder_sent(session, appt.id, "2h")
            logger.info(f"Sent 2h reminder for appt {appt.id}")


async def send_review_requests_job(bot: Bot, session_factory: async_sessionmaker) -> None:
    """Запрашивает отзыв через 30-90 минут после завершения визита."""
    now = datetime.now()
    end_after = now - timedelta(minutes=90)
    end_before = now - timedelta(minutes=30)

    async with session_factory() as session:
        appts = await repo.get_completed_without_review(session, end_after, end_before)
        for appt in appts:
            await notifications.send_review_request(bot, appt)
            logger.info(f"Sent review request for appt {appt.id}")


async def auto_complete_job(session_factory: async_sessionmaker) -> None:
    """Автоматически завершает записи, чьё время прошло >15 минут назад."""
    threshold = datetime.now() - timedelta(minutes=15)
    async with session_factory() as session:
        await repo.complete_past_appointments(session, threshold)
