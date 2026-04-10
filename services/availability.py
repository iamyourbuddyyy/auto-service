from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from config import DAYS_AHEAD, MAX_SLOTS_SHOWN
from db import repository as repo
from utils.datetime_utils import generate_day_slots, is_working_day


@dataclass
class SlotInfo:
    start_dt: datetime
    end_dt: datetime
    lift_id: int
    master_id: Optional[int]


def _slots_overlap(s1: datetime, e1: datetime, s2: datetime, e2: datetime) -> bool:
    """Возвращает True если два интервала пересекаются."""
    return s1 < e2 and e1 > s2


async def get_available_slots(
    session: AsyncSession,
    duration_hours: int,
    start_from: date | None = None,
) -> list[SlotInfo]:
    """
    Возвращает список доступных слотов начиная с start_from (по умолчанию завтра).
    Максимум MAX_SLOTS_SHOWN слотов, смотрит до DAYS_AHEAD дней вперёд.
    """
    if start_from is None:
        start_from = date.today() + timedelta(days=1)

    search_end = start_from + timedelta(days=DAYS_AHEAD)

    # Загружаем все занятые интервалы за период поиска
    period_start = datetime.combine(start_from, datetime.min.time())
    period_end = datetime.combine(search_end, datetime.max.time())
    occupied = await repo.get_occupied_intervals(session, period_start, period_end)

    # Получаем активных мастеров и подъёмники
    masters = await repo.get_active_masters(session)
    lifts = await repo.get_active_lifts(session)

    master_ids = [m.id for m in masters]
    lift_ids = [l.id for l in lifts]

    result: list[SlotInfo] = []
    current_date = start_from

    while current_date < search_end and len(result) < MAX_SLOTS_SHOWN:
        if not is_working_day(current_date):
            current_date += timedelta(days=1)
            continue

        slots = generate_day_slots(current_date, duration_hours)
        for slot_start in slots:
            if len(result) >= MAX_SLOTS_SHOWN:
                break

            slot_end = slot_start + timedelta(hours=duration_hours)

            # Находим свободные подъёмники
            free_lift_id = _find_free_lift(slot_start, slot_end, lift_ids, occupied)
            if free_lift_id is None:
                continue

            # Находим свободного мастера (наименее загруженного)
            free_master_id = _find_free_master(slot_start, slot_end, master_ids, occupied)
            if free_master_id is None:
                continue

            result.append(SlotInfo(
                start_dt=slot_start,
                end_dt=slot_end,
                lift_id=free_lift_id,
                master_id=free_master_id,
            ))

        current_date += timedelta(days=1)

    return result


def _find_free_lift(
    slot_start: datetime,
    slot_end: datetime,
    lift_ids: list[int],
    occupied: list[dict],
) -> Optional[int]:
    """Возвращает ID первого свободного подъёмника или None."""
    for lift_id in lift_ids:
        busy = any(
            o["lift_id"] == lift_id and _slots_overlap(slot_start, slot_end, o["start_dt"], o["end_dt"])
            for o in occupied
        )
        if not busy:
            return lift_id
    return None


def _find_free_master(
    slot_start: datetime,
    slot_end: datetime,
    master_ids: list[int],
    occupied: list[dict],
) -> Optional[int]:
    """Возвращает ID первого свободного мастера (не из заблокированных слотов)."""
    for master_id in master_ids:
        busy = any(
            o.get("master_id") == master_id
            and _slots_overlap(slot_start, slot_end, o["start_dt"], o["end_dt"])
            for o in occupied
            if not o.get("is_block")  # блоки не привязаны к мастерам
        )
        if not busy:
            return master_id
    return None


async def is_slot_available(
    session: AsyncSession,
    start_dt: datetime,
    duration_hours: int,
) -> bool:
    """Проверяет доступность конкретного слота (для ручного добавления)."""
    end_dt = start_dt + timedelta(hours=duration_hours)
    occupied = await repo.get_occupied_intervals(session, start_dt, end_dt)

    masters = await repo.get_active_masters(session)
    lifts = await repo.get_active_lifts(session)

    free_lift = _find_free_lift(start_dt, end_dt, [l.id for l in lifts], occupied)
    free_master = _find_free_master(start_dt, end_dt, [m.id for m in masters], occupied)

    return free_lift is not None and free_master is not None
