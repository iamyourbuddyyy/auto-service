from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import SERVICE_TYPES


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Записаться")],
            [KeyboardButton(text="📋 Мои записи"), KeyboardButton(text="🚗 Мои авто")],
        ],
        resize_keyboard=True,
    )


def services_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, info in SERVICE_TYPES.items():
        builder.button(
            text=f"{info['name']} ({info['duration']}ч)",
            callback_data=f"service:{code}",
        )
    builder.button(text="❌ Отмена", callback_data="cancel_booking")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def vehicle_choice_kb(vehicles: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for v in vehicles:
        builder.button(
            text=f"{v.brand} {v.model} {v.year}",
            callback_data=f"vehicle:{v.id}",
        )
    builder.button(text="➕ Добавить новое авто", callback_data="vehicle:new")
    builder.button(text="❌ Отмена", callback_data="cancel_booking")
    builder.adjust(1)
    return builder.as_markup()


def slots_kb(slots: list[tuple]) -> InlineKeyboardMarkup:
    """slots: list of (slot_datetime, lift_id, master_id)"""
    from utils.datetime_utils import fmt_dt
    builder = InlineKeyboardBuilder()
    for i, (slot_dt, lift_id, master_id) in enumerate(slots):
        builder.button(
            text=fmt_dt(slot_dt),
            callback_data=f"slot:{i}",
        )
    builder.button(text="❌ Отмена", callback_data="cancel_booking")
    builder.adjust(2)
    return builder.as_markup()


def confirm_booking_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_booking"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_booking"),
        ]
    ])


def appointments_kb(appointments: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for a in appointments:
        start = a.start_dt.strftime("%d.%m %H:%M")
        builder.button(
            text=f"{start} — {a.service_type.name}",
            callback_data=f"appt:{a.id}",
        )
    builder.adjust(1)
    return builder.as_markup()


def appointment_detail_kb(appt_id: int, can_cancel: bool) -> InlineKeyboardMarkup:
    buttons = []
    if can_cancel:
        buttons.append([InlineKeyboardButton(
            text="❌ Отменить запись",
            callback_data=f"cancel_appt:{appt_id}",
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_appointments")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def review_rating_kb(appt_id: int) -> InlineKeyboardMarkup:
    stars = ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"]
    builder = InlineKeyboardBuilder()
    for i, s in enumerate(stars, 1):
        builder.button(text=s, callback_data=f"review_rating:{appt_id}:{i}")
    builder.button(text="Пропустить", callback_data=f"review_skip:{appt_id}")
    builder.adjust(5, 1)
    return builder.as_markup()
