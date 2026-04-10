import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import settings
from db.engine import async_session, create_tables
from db import repository as repo
from middlewares.db_session import DbSessionMiddleware
from services import scheduler_jobs

# Handlers
from handlers.client import start, booking, my_appointments, review
from handlers.admin import auth, schedule, appointments, clients, broadcast

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Middleware: db session для всех типов апдейтов
    dp.message.middleware(DbSessionMiddleware(async_session))
    dp.callback_query.middleware(DbSessionMiddleware(async_session))

    # Регистрируем роутеры
    # Порядок важен: admin-роутеры раньше client (чтобы IsAdmin-фильтры срабатывали первыми)
    dp.include_router(auth.router)
    dp.include_router(schedule.router)
    dp.include_router(appointments.router)
    dp.include_router(clients.router)
    dp.include_router(broadcast.router)

    dp.include_router(start.router)
    dp.include_router(booking.router)
    dp.include_router(my_appointments.router)
    dp.include_router(review.router)

    # Инициализация БД и первичные данные
    await create_tables()
    async with async_session() as session:
        await repo.seed_masters_and_lifts(session)

    # APScheduler
    scheduler = AsyncIOScheduler(timezone=settings.tz)
    scheduler.add_job(
        scheduler_jobs.send_reminders_job,
        "interval",
        minutes=15,
        kwargs={"bot": bot, "session_factory": async_session},
    )
    scheduler.add_job(
        scheduler_jobs.send_review_requests_job,
        "interval",
        minutes=30,
        kwargs={"bot": bot, "session_factory": async_session},
    )
    scheduler.add_job(
        scheduler_jobs.auto_complete_job,
        "interval",
        minutes=30,
        kwargs={"session_factory": async_session},
    )
    scheduler.start()

    logger.info("Bot started")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
