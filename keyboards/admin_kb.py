from datetime import date, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.datetime_utils import fmt_date


def admin_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Расписание")],
            [KeyboardButton(text="➕ Добавить запись"), KeyboardButton(text="🔒 Закрыть слот")],
            [KeyboardButton(text="👥 Клиенты"), KeyboardButton(text="📢 Рассылка")],
            [KeyboardButton(text="👤 Режим клиента")],
        ],
        resize_keyboard=True,
    )


def schedule_period_kb() -> InlineKeyboardMarkup:
    today = date.today()
    tomorrow = today + timedelta(days=1)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Сегодня", callback_data=f"schedule:day:{today.isoformat()}"),
            InlineKeyboardButton(text="Завтра", callback_data=f"schedule:day:{tomorrow.isoformat()}"),
        ],
        [InlineKeyboardButton(text="Эта неделя", callback_data="schedule:week")],
    ])


def lifts_kb(lifts: list, prefix: str = "lift") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for lift in lifts:
        builder.button(text=lift.name, callback_data=f"{prefix}:{lift.id}")
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    builder.adjust(2, 1)
    return builder.as_markup()


def slots_admin_kb(slots: list[tuple], prefix: str = "admin_slot") -> InlineKeyboardMarkup:
    from utils.datetime_utils import fmt_dt
    builder = InlineKeyboardBuilder()
    for i, (slot_dt, lift_id, master_id) in enumerate(slots):
        builder.button(
            text=fmt_dt(slot_dt),
            callback_data=f"{prefix}:{i}",
        )
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    builder.adjust(2)
    return builder.as_markup()


def admin_confirm_kb(confirm_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=confirm_cb),
            InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel"),
        ]
    ])


def broadcast_filter_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Все клиенты", callback_data="bc_filter:all")],
        [InlineKeyboardButton(text="Не были 1+ месяц", callback_data="bc_filter:inactive_1m")],
        [InlineKeyboardButton(text="Не были 3+ месяца", callback_data="bc_filter:inactive_3m")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")],
    ])


def appointment_manage_kb(appt_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Перенести", callback_data=f"reschedule:{appt_id}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"admin_cancel_appt:{appt_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_cancel")],
    ])
