from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    choosing_service = State()
    choosing_vehicle = State()      # выбор из сохранённых или "добавить новое"
    entering_car_brand = State()
    entering_car_model = State()
    entering_car_year = State()
    choosing_slot = State()
    confirming = State()


class ReviewStates(StatesGroup):
    waiting_rating = State()
    waiting_comment = State()
