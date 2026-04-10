from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from db import repository as repo
from keyboards.client_kb import main_menu_kb
from states.booking_states import ReviewStates

router = Router()


@router.callback_query(F.data.startswith("review_rating:"))
async def on_review_rating(callback: CallbackQuery, state: FSMContext) -> None:
    _, appt_id_str, rating_str = callback.data.split(":")
    appt_id = int(appt_id_str)
    rating = int(rating_str)

    await state.set_state(ReviewStates.waiting_comment)
    await state.update_data(review_appt_id=appt_id, review_rating=rating)

    stars = "⭐" * rating
    await callback.message.edit_text(
        f"Вы поставили: {stars}\n\nОставьте комментарий или отправьте /skip:"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("review_skip:"))
async def on_review_skip(callback: CallbackQuery, session: AsyncSession) -> None:
    appt_id = int(callback.data.split(":")[1])
    await callback.message.edit_text("Спасибо за визит! Ждём вас снова.")
    await callback.answer()


@router.message(ReviewStates.waiting_comment)
async def on_review_comment(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    appt_id = data["review_appt_id"]
    rating = data["review_rating"]

    comment = None if message.text.strip() == "/skip" else message.text.strip()

    client = await repo.get_client_by_telegram_id(session, message.from_user.id)

    await repo.create_review(
        session,
        appointment_id=appt_id,
        client_id=client.id,
        rating=rating,
        comment=comment,
    )

    stars = "⭐" * rating
    await message.answer(
        f"Спасибо за отзыв! {stars}\nВаша оценка учтена.",
        reply_markup=main_menu_kb(),
    )
    await state.clear()
