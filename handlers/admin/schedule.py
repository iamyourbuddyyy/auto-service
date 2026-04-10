from datetime import date

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from db import repository as repo
from filters.is_admin import IsAdmin
from keyboards.admin_kb import schedule_period_kb, admin_menu_kb
from utils.datetime_utils import get_week_start, fmt_date
from utils.formatters import format_day_schedule, format_week_schedule

router = Router()


@router.message(IsAdmin(), F.text == "📅 Расписание")
async def cmd_schedule(message: Message) -> None:
    await message.answer("Выберите период:", reply_markup=schedule_period_kb())


@router.callback_query(IsAdmin(), F.data.startswith("schedule:day:"))
async def show_day_schedule(callback: CallbackQuery, session: AsyncSession) -> None:
    date_str = callback.data.split(":")[-1]
    target = date.fromisoformat(date_str)

    appointments = await repo.get_schedule_for_date(session, target)
    text = format_day_schedule(appointments, target)

    await callback.message.edit_text(text)
    await callback.answer()


@router.callback_query(IsAdmin(), F.data == "schedule:week")
async def show_week_schedule(callback: CallbackQuery, session: AsyncSession) -> None:
    week_start = get_week_start()
    appointments = await repo.get_schedule_for_week(session, week_start)
    text = format_week_schedule(appointments, week_start)

    await callback.message.edit_text(text)
    await callback.answer()
