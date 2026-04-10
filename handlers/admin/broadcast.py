from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from db import repository as repo
from filters.is_admin import IsAdmin
from keyboards.admin_kb import broadcast_filter_kb, admin_confirm_kb, admin_menu_kb
from services.notifications import send_broadcast
from states.admin_states import AdminBroadcast

router = Router()

FILTER_LABELS = {
    "all": "Все клиенты",
    "inactive_1m": "Не были 1+ месяц",
    "inactive_3m": "Не были 3+ месяца",
}


@router.message(IsAdmin(), F.text == "📢 Рассылка")
async def cmd_broadcast(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Кому отправить рассылку?", reply_markup=broadcast_filter_kb())
    await state.set_state(AdminBroadcast.choosing_filter)


@router.callback_query(AdminBroadcast.choosing_filter, F.data.startswith("bc_filter:"))
async def on_filter_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    filter_type = callback.data.split(":")[1]
    await state.update_data(bc_filter=filter_type, bc_filter_label=FILTER_LABELS.get(filter_type, filter_type))
    await callback.message.edit_reply_markup()
    await callback.message.answer(
        f"Фильтр: {FILTER_LABELS.get(filter_type)}\n\nВведите текст сообщения для рассылки:"
    )
    await state.set_state(AdminBroadcast.entering_text)
    await callback.answer()


@router.message(AdminBroadcast.entering_text)
async def on_broadcast_text(message: Message, state: FSMContext, session: AsyncSession) -> None:
    text = message.text.strip()
    if not text:
        await message.answer("Введите текст сообщения:")
        return

    data = await state.get_data()
    filter_type = data["bc_filter"]

    clients = await _get_filtered_clients(session, filter_type)
    await state.update_data(bc_text=text, bc_client_ids=[c.telegram_id for c in clients])

    preview = (
        f"📢 Предпросмотр рассылки\n\n"
        f"Получателей: {len(clients)}\n"
        f"Фильтр: {FILTER_LABELS.get(filter_type)}\n\n"
        f"──────────────\n"
        f"{text}\n"
        f"──────────────\n\n"
        f"Отправить?"
    )
    await message.answer(preview, reply_markup=admin_confirm_kb("bc_confirm"))
    await state.set_state(AdminBroadcast.confirming)


@router.callback_query(AdminBroadcast.confirming, F.data == "bc_confirm")
async def on_broadcast_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    client_ids = data["bc_client_ids"]
    text = data["bc_text"]

    await callback.message.edit_text(f"Отправляю {len(client_ids)} сообщений...")

    sent, failed = await send_broadcast(callback.bot, client_ids, text)

    admin = await repo.get_client_by_telegram_id(session, callback.from_user.id)
    await repo.save_broadcast(
        session,
        admin_id=admin.id,
        filter_type=data["bc_filter"],
        message_text=text,
        sent_count=sent,
    )

    await callback.message.answer(
        f"✅ Рассылка завершена!\n"
        f"Отправлено: {sent}\n"
        f"Ошибок: {failed}",
        reply_markup=admin_menu_kb(),
    )
    await state.clear()
    await callback.answer()


@router.message(IsAdmin(), F.text == "👤 Режим клиента")
async def cmd_client_mode(message: Message) -> None:
    from keyboards.client_kb import main_menu_kb
    await message.answer(
        "Переключено в режим клиента.\nЧтобы вернуться — нажмите /start",
        reply_markup=main_menu_kb(),
    )


async def _get_filtered_clients(session: AsyncSession, filter_type: str):
    if filter_type == "all":
        return await repo.get_all_clients(session)
    elif filter_type == "inactive_1m":
        since = datetime.now() - timedelta(days=30)
        return await repo.get_clients_inactive_since(session, since)
    elif filter_type == "inactive_3m":
        since = datetime.now() - timedelta(days=90)
        return await repo.get_clients_inactive_since(session, since)
    return []
