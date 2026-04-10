from aiogram.fsm.state import State, StatesGroup


class AdminAddAppointment(StatesGroup):
    entering_client_telegram_id = State()
    choosing_service = State()
    choosing_slot = State()
    confirming = State()


class AdminReschedule(StatesGroup):
    choosing_new_slot = State()
    confirming = State()


class AdminBlockSlot(StatesGroup):
    choosing_lift = State()
    entering_date = State()
    entering_start_hour = State()
    entering_end_hour = State()
    entering_reason = State()


class AdminBroadcast(StatesGroup):
    choosing_filter = State()
    entering_text = State()
    confirming = State()
