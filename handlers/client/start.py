from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from db import repository as repo
from keyboards.client_kb import main_menu_kb
from keyboards.admin_kb import admin_menu_kb

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    client = await repo.get_or_create_client(
        session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )

    if client.is_admin:
        await message.answer(
            f"Привет, {client.full_name}! Ты в режиме администратора.",
            reply_markup=admin_menu_kb(),
        )
    else:
        await message.answer(
            f"Привет, {client.full_name}! 👋\n\n"
            f"Добро пожаловать в автосервис.\n"
            f"Выбери нужное действие:",
            reply_markup=main_menu_kb(),
        )
