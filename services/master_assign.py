from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from db import repository as repo
from utils.datetime_utils import get_week_start


class NoMasterAvailableError(Exception):
    pass


class NoLiftAvailableError(Exception):
    pass


def _slots_overlap(s1: datetime, e1: datetime, s2: datetime, e2: datetime) -> bool:
    return s1 < e2 and e1 > s2


async def assign_master(
    session: AsyncSession,
    start_dt: datetime,
    end_dt: datetime,
) -> int:
    """
    Назначает мастера с минимальной загрузкой за текущую неделю
    среди тех, кто свободен в запрошенный слот.
    """
    masters = await repo.get_active_masters(session)
    occupied = await repo.get_occupied_intervals(session, start_dt, end_dt)

    # Свободные мастера в данный слот
    free_master_ids = [
        m.id for m in masters
        if not any(
            o.get("master_id") == m.id
            and not o.get("is_block")
            and _slots_overlap(start_dt, end_dt, o["start_dt"], o["end_dt"])
            for o in occupied
        )
    ]

    if not free_master_ids:
        raise NoMasterAvailableError("Нет свободных мастеров на этот слот")

    # Загрузка за текущую неделю
    week_start_date = get_week_start()
    week_start = datetime.combine(week_start_date, datetime.min.time())
    week_end = week_start + timedelta(days=7)

    loads = await repo.get_master_weekly_hours(session, week_start, week_end)

    # Выбираем мастера с минимальной загрузкой
    best = min(free_master_ids, key=lambda mid: loads.get(mid, 0.0))
    return best


async def assign_lift(
    session: AsyncSession,
    start_dt: datetime,
    end_dt: datetime,
) -> int:
    """
    Назначает подъёмник с наименьшим количеством записей за неделю
    среди тех, кто свободен в запрошенный слот.
    """
    lifts = await repo.get_active_lifts(session)
    occupied = await repo.get_occupied_intervals(session, start_dt, end_dt)

    free_lift_ids = [
        l.id for l in lifts
        if not any(
            o["lift_id"] == l.id
            and _slots_overlap(start_dt, end_dt, o["start_dt"], o["end_dt"])
            for o in occupied
        )
    ]

    if not free_lift_ids:
        raise NoLiftAvailableError("Нет свободных подъёмников на этот слот")

    week_start_date = get_week_start()
    week_start = datetime.combine(week_start_date, datetime.min.time())
    week_end = week_start + timedelta(days=7)

    counts = await repo.get_lift_weekly_counts(session, week_start, week_end)

    best = min(free_lift_ids, key=lambda lid: counts.get(lid, 0))
    return best
