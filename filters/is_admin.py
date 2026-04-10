from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from db import repository as repo
from db.engine import async_session


class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        telegram_id = event.from_user.id if event.from_user else None
        if not telegram_id:
            return False
        async with async_session() as session:
            client = await repo.get_client_by_telegram_id(session, telegram_id)
            return client is not None and client.is_admin
