import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from config import SERVICE_TYPES
from db import repository as repo
from keyboards.client_kb import (
    services_kb, vehicle_choice_kb, slots_kb, confirm_booking_kb, main_menu_kb
)
from services.availability import get_available_slots
from services.master_assign import assign_master, assign_lift, NoMasterAvailableError, NoLiftAvailableError
from services import notifications
from states.booking_states import BookingStates
from utils.datetime_utils import fmt_dt
from utils.formatters import format_appointment_confirm

logger = logging.getLogger(__name__)
router = Router()

SLOT_CACHE_KEY = "available_slots"


@router.message(F.text == "📝 Записаться")
async def cmd_start_booking(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Выберите тип работ:",
        reply_markup=services_kb(),
    )
    await state.set_state(BookingStates.choosing_service)


@router.callback_query(BookingStates.choosing_service, F.data.startswith("service:"))
async def on_service_chosen(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    code = callback.data.split(":")[1]
    if code not in SERVICE_TYPES:
        await callback.answer("Неизвестная услуга")
        return

    service = SERVICE_TYPES[code]
    await state.update_data(service_code=code, service_name=service["name"], duration=service["duration"])

    # Проверяем есть ли уже авто у клиента
    client = await repo.get_client_by_telegram_id(session, callback.from_user.id)
    vehicles = await repo.get_client_vehicles(session, client.id)

    await callback.message.edit_reply_markup()

    if vehicles:
        await callback.message.answer(
            f"Услуга: {service['name']} ({service['duration']}ч)\n\nВыберите автомобиль:",
            reply_markup=vehicle_choice_kb(vehicles),
        )
        await state.update_data(client_id=client.id)
        await state.set_state(BookingStates.choosing_vehicle)
    else:
        await callback.message.answer(
            f"Услуга: {service['name']} ({service['duration']}ч)\n\nВведите марку автомобиля (например: Toyota):"
        )
        await state.update_data(client_id=client.id)
        await state.set_state(BookingStates.entering_car_brand)

    await callback.answer()


@router.callback_query(BookingStates.choosing_vehicle, F.data.startswith("vehicle:"))
async def on_vehicle_chosen(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    value = callback.data.split(":")[1]
    await callback.message.edit_reply_markup()

    if value == "new":
        await callback.message.answer("Введите марку автомобиля (например: Toyota):")
        await state.set_state(BookingStates.entering_car_brand)
    else:
        vehicle_id = int(value)
        await state.update_data(vehicle_id=vehicle_id)
        await _show_slots(callback.message, state, session)

    await callback.answer()


@router.message(BookingStates.entering_car_brand)
async def on_brand_entered(message: Message, state: FSMContext) -> None:
    brand = message.text.strip()
    if not brand:
        await message.answer("Введите марку автомобиля:")
        return
    await state.update_data(car_brand=brand)
    await message.answer("Введите модель автомобиля (например: Camry):")
    await state.set_state(BookingStates.entering_car_model)


@router.message(BookingStates.entering_car_model)
async def on_model_entered(message: Message, state: FSMContext) -> None:
    model = message.text.strip()
    if not model:
        await message.answer("Введите модель автомобиля:")
        return
    await state.update_data(car_model=model)
    await message.answer("Введите год выпуска (например: 2019):")
    await state.set_state(BookingStates.entering_car_year)


@router.message(BookingStates.entering_car_year)
async def on_year_entered(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        year = int(message.text.strip())
        current_year = datetime.now().year
        if not (1980 <= year <= current_year + 1):
            raise ValueError
    except ValueError:
        await message.answer(f"Введите корректный год (1980 — {datetime.now().year + 1}):")
        return

    data = await state.get_data()
    vehicle = await repo.create_vehicle(
        session,
        client_id=data["client_id"],
        brand=data["car_brand"],
        model=data["car_model"],
        year=year,
    )
    await state.update_data(vehicle_id=vehicle.id)
    await _show_slots(message, state, session)


async def _show_slots(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    duration = data["duration"]

    await message.answer("Ищу свободные слоты...")

    slots = await get_available_slots(session, duration_hours=duration)

    if not slots:
        await message.answer(
            "К сожалению, свободных слотов нет на ближайшие 2 недели. "
            "Позвоните нам для записи.",
            reply_markup=main_menu_kb(),
        )
        await state.clear()
        return

    # Сохраняем слоты в state для последующего использования
    slots_data = [
        {"start": s.start_dt.isoformat(), "end": s.end_dt.isoformat(),
         "lift_id": s.lift_id, "master_id": s.master_id}
        for s in slots
    ]
    await state.update_data(**{SLOT_CACHE_KEY: slots_data})

    slot_tuples = [(s.start_dt, s.lift_id, s.master_id) for s in slots]
    await message.answer(
        "Выберите удобное время:",
        reply_markup=slots_kb(slot_tuples),
    )
    await state.set_state(BookingStates.choosing_slot)


@router.callback_query(BookingStates.choosing_slot, F.data.startswith("slot:"))
async def on_slot_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    slots_data = data.get(SLOT_CACHE_KEY, [])

    if idx >= len(slots_data):
        await callback.answer("Слот недоступен, попробуйте снова")
        return

    chosen = slots_data[idx]
    await state.update_data(chosen_slot=chosen)
    await callback.message.edit_reply_markup()

    start_dt = datetime.fromisoformat(chosen["start"])
    vehicle_id = data["vehicle_id"]
    # Получаем инфо о авто из state (если было введено вручную) — для отображения
    brand = data.get("car_brand", "")
    model = data.get("car_model", "")
    year = data.get("car_year_str", "")
    vehicle_str = f"{brand} {model} {year}".strip() if brand else f"ID {vehicle_id}"

    confirm_text = format_appointment_confirm(
        service_name=data["service_name"],
        duration=data["duration"],
        vehicle_str=vehicle_str,
        slot_dt_str=fmt_dt(start_dt),
    )

    await callback.message.answer(confirm_text, reply_markup=confirm_booking_kb())
    await state.set_state(BookingStates.confirming)
    await callback.answer()


@router.callback_query(BookingStates.confirming, F.data == "confirm_booking")
async def on_booking_confirmed(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    chosen = data["chosen_slot"]

    start_dt = datetime.fromisoformat(chosen["start"])
    end_dt = datetime.fromisoformat(chosen["end"])

    try:
        master_id = await assign_master(session, start_dt, end_dt)
        lift_id = await assign_lift(session, start_dt, end_dt)
    except (NoMasterAvailableError, NoLiftAvailableError):
        await callback.message.edit_reply_markup()
        await callback.message.answer(
            "Этот слот только что заняли. Выберите другое время.",
            reply_markup=main_menu_kb(),
        )
        await state.clear()
        await callback.answer()
        return

    client = await repo.get_client_by_telegram_id(session, callback.from_user.id)
    service_type = await repo.get_service_type_by_code(session, data["service_code"])

    appt = await repo.create_appointment(
        session,
        client_id=client.id,
        vehicle_id=data["vehicle_id"],
        service_type_id=service_type.id,
        master_id=master_id,
        lift_id=lift_id,
        start_dt=start_dt,
        end_dt=end_dt,
    )

    await callback.message.edit_reply_markup()
    await notifications.notify_booking_confirmed(callback.bot, appt)

    # Уведомляем всех админов
    admin_ids = await repo.get_all_admin_telegram_ids(session)
    await notifications.notify_admin_new_booking(callback.bot, admin_ids, appt)

    await callback.message.answer(
        "Запись оформлена! Ждём вас.",
        reply_markup=main_menu_kb(),
    )
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "cancel_booking")
async def on_cancel_booking(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_reply_markup()
    await callback.message.answer("Запись отменена.", reply_markup=main_menu_kb())
    await callback.answer()
