import asyncio
import logging
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from db.models import Appointment
from keyboards.client_kb import review_rating_kb
from utils.datetime_utils import fmt_dt

logger = logging.getLogger(__name__)


async def notify_booking_confirmed(bot: Bot, appt: Appointment) -> None:
    vehicle = f"{appt.vehicle.brand} {appt.vehicle.model} {appt.vehicle.year}"
    text = (
        f"✅ Запись подтверждена!\n\n"
        f"🔧 Услуга: {appt.service_type.name}\n"
        f"🚗 Авто: {vehicle}\n"
        f"📅 Дата и время: {fmt_dt(appt.start_dt)}\n"
        f"⏱ Длительность: {appt.service_type.duration_hours}ч\n"
        f"🏗 {appt.lift.name}\n\n"
        f"Ждём вас! Если планы изменятся — отмените запись в разделе «Мои записи»."
    )
    await _safe_send(bot, appt.client.telegram_id, text)


async def notify_booking_cancelled(bot: Bot, appt: Appointment, by_admin: bool = False) -> None:
    dt_str = fmt_dt(appt.start_dt)
    if by_admin:
        text = (
            f"❌ Ваша запись на {dt_str} ({appt.service_type.name}) была отменена администратором.\n"
            f"Приносим извинения. Свяжитесь с нами для переноса."
        )
    else:
        text = f"❌ Запись на {dt_str} ({appt.service_type.name}) отменена."
    await _safe_send(bot, appt.client.telegram_id, text)


async def send_reminder(bot: Bot, appt: Appointment, hours: int) -> None:
    vehicle = f"{appt.vehicle.brand} {appt.vehicle.model} {appt.vehicle.year}"
    if hours == 24:
        time_str = "завтра"
    else:
        time_str = f"через {hours} ч."
    text = (
        f"⏰ Напоминание!\n\n"
        f"Ваш визит {time_str}: {fmt_dt(appt.start_dt)}\n"
        f"🔧 {appt.service_type.name}\n"
        f"🚗 {vehicle}\n"
        f"🏗 {appt.lift.name}\n\n"
        f"Ждём вас!"
    )
    await _safe_send(bot, appt.client.telegram_id, text)


async def send_review_request(bot: Bot, appt: Appointment) -> None:
    text = (
        f"Как прошёл ваш визит?\n\n"
        f"🔧 {appt.service_type.name} | {fmt_dt(appt.start_dt)}\n\n"
        f"Оцените работу мастера:"
    )
    await _safe_send(
        bot,
        appt.client.telegram_id,
        text,
        reply_markup=review_rating_kb(appt.id),
    )


async def notify_admin_new_booking(
    bot: Bot, admin_telegram_ids: list[int], appt: Appointment
) -> None:
    vehicle = f"{appt.vehicle.brand} {appt.vehicle.model} {appt.vehicle.year}"
    text = (
        f"📝 Новая запись!\n\n"
        f"👤 {appt.client.full_name}\n"
        f"🔧 {appt.service_type.name}\n"
        f"🚗 {vehicle}\n"
        f"📅 {fmt_dt(appt.start_dt)}\n"
        f"🏗 {appt.lift.name}\n"
        f"👷 {appt.master.name if appt.master else '—'}"
    )
    for admin_id in admin_telegram_ids:
        await _safe_send(bot, admin_id, text)


async def send_broadcast(
    bot: Bot,
    client_telegram_ids: list[int],
    text: str,
) -> tuple[int, int]:
    """Рассылка. Возвращает (sent_count, failed_count)."""
    sent = 0
    failed = 0
    for tg_id in client_telegram_ids:
        try:
            await bot.send_message(tg_id, text)
            sent += 1
        except (TelegramForbiddenError, TelegramBadRequest):
            failed += 1
        except Exception as e:
            logger.warning(f"Broadcast error for {tg_id}: {e}")
            failed += 1
        await asyncio.sleep(0.05)  # антиспам
    return sent, failed


async def _safe_send(bot: Bot, telegram_id: int, text: str, **kwargs) -> None:
    try:
        await bot.send_message(telegram_id, text, **kwargs)
    except TelegramForbiddenError:
        logger.info(f"User {telegram_id} blocked the bot")
    except Exception as e:
        logger.warning(f"Failed to send message to {telegram_id}: {e}")
