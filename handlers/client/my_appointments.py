from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from db import repository as repo
from keyboards.client_kb import appointments_kb, appointment_detail_kb, main_menu_kb
from services import notifications
from utils.datetime_utils import fmt_dt

router = Router()


@router.message(F.text == "📋 Мои записи")
async def cmd_my_appointments(message: Message, session: AsyncSession) -> None:
    client = await repo.get_client_by_telegram_id(session, message.from_user.id)
    if not client:
        await message.answer("Сначала нажмите /start")
        return

    appointments = await repo.get_client_appointments(session, client.id, status="scheduled")

    if not appointments:
        await message.answer("У вас нет активных записей.", reply_markup=main_menu_kb())
        return

    await message.answer(
        f"Ваши активные записи ({len(appointments)}):",
        reply_markup=appointments_kb(appointments),
    )


@router.callback_query(F.data.startswith("appt:"))
async def on_appointment_detail(callback: CallbackQuery, session: AsyncSession) -> None:
    appt_id = int(callback.data.split(":")[1])
    appt = await repo.get_appointment_full(session, appt_id)

    if not appt:
        await callback.answer("Запись не найдена")
        return

    vehicle = f"{appt.vehicle.brand} {appt.vehicle.model} {appt.vehicle.year}"
    master = appt.master.name if appt.master else "будет назначен"
    text = (
        f"📋 Запись #{appt.id}\n\n"
        f"📅 {fmt_dt(appt.start_dt)}\n"
        f"🔧 {appt.service_type.name}\n"
        f"🚗 {vehicle}\n"
        f"🏗 {appt.lift.name}\n"
        f"👷 {master}\n"
        f"Статус: {_status_ru(appt.status)}"
    )

    can_cancel = (
        appt.status == "scheduled"
        and appt.start_dt > datetime.now()
        and appt.client.telegram_id == callback.from_user.id
    )

    await callback.message.edit_text(text, reply_markup=appointment_detail_kb(appt.id, can_cancel))
    await callback.answer()


@router.callback_query(F.data.startswith("cancel_appt:"))
async def on_cancel_appointment(callback: CallbackQuery, session: AsyncSession) -> None:
    appt_id = int(callback.data.split(":")[1])
    appt = await repo.get_appointment_full(session, appt_id)

    if not appt or appt.client.telegram_id != callback.from_user.id:
        await callback.answer("Нет доступа")
        return

    await repo.cancel_appointment(session, appt_id, reason="Отменено клиентом")
    await notifications.notify_booking_cancelled(callback.bot, appt, by_admin=False)

    await callback.message.edit_text("✅ Запись отменена.")
    await callback.answer("Запись отменена")


@router.callback_query(F.data == "back_to_appointments")
async def on_back_to_appointments(callback: CallbackQuery, session: AsyncSession) -> None:
    client = await repo.get_client_by_telegram_id(session, callback.from_user.id)
    appointments = await repo.get_client_appointments(session, client.id, status="scheduled")

    if not appointments:
        await callback.message.edit_text("У вас нет активных записей.")
        await callback.answer()
        return

    await callback.message.edit_text(
        f"Ваши активные записи ({len(appointments)}):",
        reply_markup=appointments_kb(appointments),
    )
    await callback.answer()


@router.message(F.text == "🚗 Мои авто")
async def cmd_my_vehicles(message: Message, session: AsyncSession) -> None:
    client = await repo.get_client_by_telegram_id(session, message.from_user.id)
    if not client:
        await message.answer("Сначала нажмите /start")
        return

    vehicles = await repo.get_client_vehicles(session, client.id)
    if not vehicles:
        await message.answer("У вас нет сохранённых автомобилей.", reply_markup=main_menu_kb())
        return

    lines = ["🚗 Ваши автомобили:\n"]
    for v in vehicles:
        lines.append(f"• {v.brand} {v.model} {v.year}")

    await message.answer("\n".join(lines), reply_markup=main_menu_kb())


def _status_ru(status: str) -> str:
    return {
        "scheduled": "Запланировано",
        "completed": "Завершено",
        "cancelled": "Отменено",
        "no_show": "Не явился",
    }.get(status, status)
