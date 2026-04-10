from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import repository as repo
from keyboards.admin_kb import admin_menu_kb
from keyboards.client_kb import main_menu_kb

router = Router()


@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /admin <пароль>")
        return

    password = parts[1].strip()
    if password != settings.admin_password:
        await message.answer("Неверный пароль.")
        return

    await repo.get_or_create_client(
        session,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )
    await repo.set_admin(session, message.from_user.id, True)
    await message.answer(
        "Вы добавлены как администратор.",
        reply_markup=admin_menu_kb(),
    )


@router.message(Command("unadmin"))
async def cmd_unadmin(message: Message, session: AsyncSession) -> None:
    """Убрать себя из администраторов."""
    await repo.set_admin(session, message.from_user.id, False)
    await message.answer("Вы больше не администратор.", reply_markup=main_menu_kb())
