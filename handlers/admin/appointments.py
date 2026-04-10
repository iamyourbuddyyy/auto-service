import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from config import SERVICE_TYPES
from db import repository as repo
from filters.is_admin import IsAdmin
from keyboards.admin_kb import (
    lifts_kb, slots_admin_kb, admin_confirm_kb, admin_menu_kb, appointment_manage_kb
)
from keyboards.client_kb import services_kb
from services.availability import get_available_slots
from services.master_assign import assign_master, assign_lift, NoMasterAvailableError, NoLiftAvailableError
from services import notifications
from states.admin_states import AdminAddAppointment, AdminReschedule, AdminBlockSlot
from utils.datetime_utils import fmt_dt

logger = logging.getLogger(__name__)
router = Router()

SLOT_CACHE_KEY = "admin_available_slots"


# ─────────── Добавить запись вручную ───────────

@router.message(IsAdmin(), F.text == "➕ Добавить запись")
async def cmd_add_appointment(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Введите Telegram ID клиента (попросите клиента написать боту и узнайте его ID):"
    )
    await state.set_state(AdminAddAppointment.entering_client_telegram_id)


@router.message(AdminAddAppointment.entering_client_telegram_id)
async def on_client_id_entered(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.answer("Введите числовой Telegram ID:")
        return

    client = await repo.get_client_by_telegram_id(session, tg_id)
    if not client:
        await message.answer(
            f"Клиент с ID {tg_id} не найден. Попросите его написать /start боту сначала."
        )
        return

    await state.update_data(target_client_id=client.id, target_client_name=client.full_name)
    await message.answer(
        f"Клиент: {client.full_name}\n\nВыберите тип работ:",
        reply_markup=services_kb(),
    )
    await state.set_state(AdminAddAppointment.choosing_service)


@router.callback_query(AdminAddAppointment.choosing_service, F.data.startswith("service:"))
async def on_admin_service_chosen(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    code = callback.data.split(":")[1]
    service = SERVICE_TYPES[code]
    await state.update_data(service_code=code, service_name=service["name"], duration=service["duration"])

    await callback.message.edit_reply_markup()
    await callback.message.answer("Ищу свободные слоты...")

    slots = await get_available_slots(session, duration_hours=service["duration"])
    if not slots:
        await callback.message.answer("Нет свободных слотов на ближайшие 2 недели.")
        await state.clear()
        await callback.answer()
        return

    slots_data = [
        {"start": s.start_dt.isoformat(), "end": s.end_dt.isoformat(),
         "lift_id": s.lift_id, "master_id": s.master_id}
        for s in slots
    ]
    await state.update_data(**{SLOT_CACHE_KEY: slots_data})
    slot_tuples = [(s.start_dt, s.lift_id, s.master_id) for s in slots]

    await callback.message.answer(
        "Выберите слот:",
        reply_markup=slots_admin_kb(slot_tuples),
    )
    await state.set_state(AdminAddAppointment.choosing_slot)
    await callback.answer()


@router.callback_query(AdminAddAppointment.choosing_slot, F.data.startswith("admin_slot:"))
async def on_admin_slot_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    slots_data = data.get(SLOT_CACHE_KEY, [])

    if idx >= len(slots_data):
        await callback.answer("Слот недоступен")
        return

    chosen = slots_data[idx]
    await state.update_data(chosen_slot=chosen)
    await callback.message.edit_reply_markup()

    start_dt = datetime.fromisoformat(chosen["start"])
    text = (
        f"Клиент: {data['target_client_name']}\n"
        f"Услуга: {data['service_name']} ({data['duration']}ч)\n"
        f"Время: {fmt_dt(start_dt)}\n\n"
        f"Подтвердить запись?"
    )
    await callback.message.answer(text, reply_markup=admin_confirm_kb("admin_confirm_add"))
    await state.set_state(AdminAddAppointment.confirming)
    await callback.answer()


@router.callback_query(AdminAddAppointment.confirming, F.data == "admin_confirm_add")
async def on_admin_confirm_add(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    chosen = data["chosen_slot"]
    start_dt = datetime.fromisoformat(chosen["start"])
    end_dt = datetime.fromisoformat(chosen["end"])

    try:
        master_id = await assign_master(session, start_dt, end_dt)
        lift_id = await assign_lift(session, start_dt, end_dt)
    except (NoMasterAvailableError, NoLiftAvailableError) as e:
        await callback.message.edit_text(f"Ошибка: {e}")
        await state.clear()
        await callback.answer()
        return

    service_type = await repo.get_service_type_by_code(session, data["service_code"])

    # Берём первый активный автомобиль клиента
    vehicle = await repo.get_active_vehicle(session, data["target_client_id"])
    if not vehicle:
        await callback.message.answer(
            "У клиента нет сохранённых авто. Попросите его добавить авто через бот."
        )
        await state.clear()
        await callback.answer()
        return

    appt = await repo.create_appointment(
        session,
        client_id=data["target_client_id"],
        vehicle_id=vehicle.id,
        service_type_id=service_type.id,
        master_id=master_id,
        lift_id=lift_id,
        start_dt=start_dt,
        end_dt=end_dt,
        notes="Добавлено администратором",
    )

    await notifications.notify_booking_confirmed(callback.bot, appt)
    await callback.message.edit_text(f"✅ Запись создана! ID: {appt.id}")
    await state.clear()
    await callback.answer()


# ─────────── Закрыть слот ───────────

@router.message(IsAdmin(), F.text == "🔒 Закрыть слот")
async def cmd_block_slot(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    lifts = await repo.get_active_lifts(session)
    await message.answer("Выберите подъёмник:", reply_markup=lifts_kb(lifts, prefix="block_lift"))
    await state.set_state(AdminBlockSlot.choosing_lift)


@router.callback_query(AdminBlockSlot.choosing_lift, F.data.startswith("block_lift:"))
async def on_block_lift_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    lift_id = int(callback.data.split(":")[1])
    await state.update_data(block_lift_id=lift_id)
    await callback.message.edit_reply_markup()
    await callback.message.answer("Введите дату в формате ДД.ММ.ГГГГ (например: 15.04.2025):")
    await state.set_state(AdminBlockSlot.entering_date)
    await callback.answer()


@router.message(AdminBlockSlot.entering_date)
async def on_block_date_entered(message: Message, state: FSMContext) -> None:
    try:
        d = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
    except ValueError:
        await message.answer("Неверный формат даты. Введите ДД.ММ.ГГГГ:")
        return
    await state.update_data(block_date=d.isoformat())
    await message.answer("Введите час начала блокировки (0-21, например: 9):")
    await state.set_state(AdminBlockSlot.entering_start_hour)


@router.message(AdminBlockSlot.entering_start_hour)
async def on_block_start_hour(message: Message, state: FSMContext) -> None:
    try:
        hour = int(message.text.strip())
        if not (0 <= hour <= 21):
            raise ValueError
    except ValueError:
        await message.answer("Введите час от 0 до 21:")
        return
    await state.update_data(block_start_hour=hour)
    await message.answer("Введите час окончания блокировки (1-21, например: 18):")
    await state.set_state(AdminBlockSlot.entering_end_hour)


@router.message(AdminBlockSlot.entering_end_hour)
async def on_block_end_hour(message: Message, state: FSMContext) -> None:
    try:
        hour = int(message.text.strip())
        if not (1 <= hour <= 21):
            raise ValueError
    except ValueError:
        await message.answer("Введите час от 1 до 21:")
        return

    data = await state.get_data()
    if hour <= data["block_start_hour"]:
        await message.answer("Час окончания должен быть больше часа начала:")
        return

    await state.update_data(block_end_hour=hour)
    await message.answer("Введите причину блокировки (или отправьте '-' чтобы пропустить):")
    await state.set_state(AdminBlockSlot.entering_reason)


@router.message(AdminBlockSlot.entering_reason)
async def on_block_reason(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    reason = None if message.text.strip() == "-" else message.text.strip()

    from datetime import date as date_type
    d = date_type.fromisoformat(data["block_date"])
    start_dt = datetime(d.year, d.month, d.day, data["block_start_hour"])
    end_dt = datetime(d.year, d.month, d.day, data["block_end_hour"])

    client = await repo.get_client_by_telegram_id(session, message.from_user.id)

    await repo.create_blocked_slot(
        session,
        lift_id=data["block_lift_id"],
        start_dt=start_dt,
        end_dt=end_dt,
        reason=reason,
        created_by=client.id,
    )

    await message.answer(
        f"✅ Слот заблокирован:\n"
        f"{start_dt.strftime('%d.%m.%Y %H:%M')} — {end_dt.strftime('%H:%M')}",
        reply_markup=admin_menu_kb(),
    )
    await state.clear()


# ─────────── Перенос записи ───────────

@router.callback_query(IsAdmin(), F.data.startswith("reschedule:"))
async def on_reschedule(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    appt_id = int(callback.data.split(":")[1])
    appt = await repo.get_appointment_full(session, appt_id)
    if not appt:
        await callback.answer("Запись не найдена")
        return

    await state.update_data(reschedule_appt_id=appt_id, duration=appt.service_type.duration_hours)
    slots = await get_available_slots(session, duration_hours=appt.service_type.duration_hours)

    if not slots:
        await callback.message.answer("Нет свободных слотов для переноса.")
        await callback.answer()
        return

    slots_data = [
        {"start": s.start_dt.isoformat(), "end": s.end_dt.isoformat(),
         "lift_id": s.lift_id, "master_id": s.master_id}
        for s in slots
    ]
    await state.update_data(**{SLOT_CACHE_KEY: slots_data})
    slot_tuples = [(s.start_dt, s.lift_id, s.master_id) for s in slots]

    await callback.message.answer(
        "Выберите новое время:",
        reply_markup=slots_admin_kb(slot_tuples, prefix="reschedule_slot"),
    )
    await state.set_state(AdminReschedule.choosing_new_slot)
    await callback.answer()


@router.callback_query(AdminReschedule.choosing_new_slot, F.data.startswith("reschedule_slot:"))
async def on_reschedule_slot_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    slots_data = data.get(SLOT_CACHE_KEY, [])

    chosen = slots_data[idx]
    await state.update_data(chosen_slot=chosen)
    await callback.message.edit_reply_markup()

    start_dt = datetime.fromisoformat(chosen["start"])
    await callback.message.answer(
        f"Перенести на {fmt_dt(start_dt)}?",
        reply_markup=admin_confirm_kb("reschedule_confirm"),
    )
    await state.set_state(AdminReschedule.confirming)
    await callback.answer()


@router.callback_query(AdminReschedule.confirming, F.data == "reschedule_confirm")
async def on_reschedule_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    chosen = data["chosen_slot"]
    start_dt = datetime.fromisoformat(chosen["start"])
    end_dt = datetime.fromisoformat(chosen["end"])

    try:
        master_id = await assign_master(session, start_dt, end_dt)
        lift_id = await assign_lift(session, start_dt, end_dt)
    except (NoMasterAvailableError, NoLiftAvailableError) as e:
        await callback.message.edit_text(f"Ошибка: {e}")
        await state.clear()
        await callback.answer()
        return

    appt_id = data["reschedule_appt_id"]
    await repo.reschedule_appointment(session, appt_id, start_dt, end_dt, master_id, lift_id)

    appt = await repo.get_appointment_full(session, appt_id)
    if appt:
        await notifications.notify_booking_confirmed(callback.bot, appt)

    await callback.message.edit_text(f"✅ Запись перенесена на {fmt_dt(start_dt)}")
    await state.clear()
    await callback.answer()


# ─────────── Отмена записи администратором ───────────

@router.callback_query(IsAdmin(), F.data.startswith("admin_cancel_appt:"))
async def on_admin_cancel_appt(callback: CallbackQuery, session: AsyncSession) -> None:
    appt_id = int(callback.data.split(":")[1])
    appt = await repo.get_appointment_full(session, appt_id)
    if not appt:
        await callback.answer("Запись не найдена")
        return

    await repo.cancel_appointment(session, appt_id, reason="Отменено администратором")
    await notifications.notify_booking_cancelled(callback.bot, appt, by_admin=True)
    await callback.message.edit_text("✅ Запись отменена, клиент уведомлён.")
    await callback.answer()


@router.callback_query(F.data == "admin_cancel")
async def on_admin_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_reply_markup()
    await callback.message.answer("Действие отменено.", reply_markup=admin_menu_kb())
    await callback.answer()
