from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from db import repository as repo
from filters.is_admin import IsAdmin
from utils.formatters import format_client_card

router = Router()


@router.message(IsAdmin(), F.text == "👥 Клиенты")
async def cmd_clients_help(message: Message) -> None:
    await message.answer(
        "Чтобы найти клиента, используйте команду:\n"
        "/client <Telegram ID>\n\n"
        "Например: /client 123456789\n\n"
        "Telegram ID клиента можно узнать, попросив его написать боту — "
        "ID отображается в уведомлениях о новых записях."
    )


@router.message(IsAdmin(), Command("client"))
async def cmd_client_card(message: Message, session: AsyncSession) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /client <Telegram ID>")
        return

    try:
        tg_id = int(parts[1].strip())
    except ValueError:
        await message.answer("Введите числовой Telegram ID")
        return

    client = await repo.get_client_by_telegram_id(session, tg_id)
    if not client:
        await message.answer(f"Клиент с ID {tg_id} не найден.")
        return

    vehicles = await repo.get_client_vehicles(session, client.id)
    appointments = await repo.get_client_appointments(session, client.id)
    avg_rating = await repo.get_client_avg_rating(session, client.id)

    text = format_client_card(client, vehicles, appointments, avg_rating)
    await message.answer(text)
