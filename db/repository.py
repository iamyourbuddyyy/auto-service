from datetime import datetime, date, timedelta
from typing import Optional

from sqlalchemy import select, update, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import SERVICE_TYPES
from db.models import (
    Client, Vehicle, Master, Lift, ServiceType,
    Appointment, BlockedSlot, Review, Broadcast
)


# ─────────────────────────── CLIENTS ────────────────────────────

async def get_or_create_client(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str],
    full_name: str,
) -> Client:
    result = await session.execute(
        select(Client).where(Client.telegram_id == telegram_id)
    )
    client = result.scalar_one_or_none()
    if client:
        client.username = username
        client.full_name = full_name
        client.last_active_at = datetime.now()
        await session.commit()
        return client

    client = Client(
        telegram_id=telegram_id,
        username=username,
        full_name=full_name,
        last_active_at=datetime.now(),
    )
    session.add(client)
    await session.commit()
    await session.refresh(client)
    return client


async def get_client_by_telegram_id(
    session: AsyncSession, telegram_id: int
) -> Optional[Client]:
    result = await session.execute(
        select(Client).where(Client.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def set_admin(session: AsyncSession, telegram_id: int, is_admin: bool) -> None:
    await session.execute(
        update(Client)
        .where(Client.telegram_id == telegram_id)
        .values(is_admin=is_admin)
    )
    await session.commit()


async def get_all_admin_telegram_ids(session: AsyncSession) -> list[int]:
    result = await session.execute(
        select(Client.telegram_id).where(Client.is_admin == True)
    )
    return list(result.scalars().all())


async def get_clients_inactive_since(
    session: AsyncSession, since: datetime
) -> list[Client]:
    result = await session.execute(
        select(Client).where(
            and_(Client.last_active_at < since, Client.is_admin == False)
        )
    )
    return list(result.scalars().all())


async def get_all_clients(session: AsyncSession) -> list[Client]:
    result = await session.execute(
        select(Client).where(Client.is_admin == False)
    )
    return list(result.scalars().all())


async def touch_client(session: AsyncSession, telegram_id: int) -> None:
    await session.execute(
        update(Client)
        .where(Client.telegram_id == telegram_id)
        .values(last_active_at=datetime.now())
    )
    await session.commit()


# ─────────────────────────── VEHICLES ───────────────────────────

async def get_active_vehicle(
    session: AsyncSession, client_id: int
) -> Optional[Vehicle]:
    result = await session.execute(
        select(Vehicle).where(
            and_(Vehicle.client_id == client_id, Vehicle.is_active == True)
        ).order_by(Vehicle.created_at.desc())
    )
    return result.scalars().first()


async def create_vehicle(
    session: AsyncSession,
    client_id: int,
    brand: str,
    model: str,
    year: int,
) -> Vehicle:
    vehicle = Vehicle(client_id=client_id, brand=brand, model=model, year=year)
    session.add(vehicle)
    await session.commit()
    await session.refresh(vehicle)
    return vehicle


async def get_client_vehicles(
    session: AsyncSession, client_id: int
) -> list[Vehicle]:
    result = await session.execute(
        select(Vehicle)
        .where(and_(Vehicle.client_id == client_id, Vehicle.is_active == True))
        .order_by(Vehicle.created_at.desc())
    )
    return list(result.scalars().all())


# ─────────────────────────── MASTERS ────────────────────────────

async def get_active_masters(session: AsyncSession) -> list[Master]:
    result = await session.execute(
        select(Master).where(Master.is_active == True)
    )
    return list(result.scalars().all())


async def seed_masters_and_lifts(session: AsyncSession) -> None:
    """Заполняет мастеров и подъёмники при первом запуске."""
    masters_count = await session.scalar(select(func.count(Master.id)))
    if not masters_count:
        for i in range(1, 7):
            session.add(Master(name=f"Мастер {i}"))

    lifts_count = await session.scalar(select(func.count(Lift.id)))
    if not lifts_count:
        for i in range(1, 5):
            session.add(Lift(name=f"Подъёмник {i}"))

    service_count = await session.scalar(select(func.count(ServiceType.id)))
    if not service_count:
        for code, info in SERVICE_TYPES.items():
            session.add(ServiceType(
                code=code,
                name=info["name"],
                duration_hours=info["duration"],
            ))

    await session.commit()


async def get_service_type_by_code(
    session: AsyncSession, code: str
) -> Optional[ServiceType]:
    result = await session.execute(
        select(ServiceType).where(ServiceType.code == code)
    )
    return result.scalar_one_or_none()


async def get_active_lifts(session: AsyncSession) -> list[Lift]:
    result = await session.execute(
        select(Lift).where(Lift.is_active == True)
    )
    return list(result.scalars().all())


# ─────────────────────────── APPOINTMENTS ───────────────────────

async def create_appointment(
    session: AsyncSession,
    client_id: int,
    vehicle_id: int,
    service_type_id: int,
    master_id: Optional[int],
    lift_id: int,
    start_dt: datetime,
    end_dt: datetime,
    notes: Optional[str] = None,
) -> Appointment:
    appt = Appointment(
        client_id=client_id,
        vehicle_id=vehicle_id,
        service_type_id=service_type_id,
        master_id=master_id,
        lift_id=lift_id,
        start_dt=start_dt,
        end_dt=end_dt,
        notes=notes,
    )
    session.add(appt)
    await session.commit()
    await session.refresh(appt)
    # Загружаем связи для использования в уведомлениях
    result = await session.execute(
        select(Appointment)
        .options(
            selectinload(Appointment.client),
            selectinload(Appointment.vehicle),
            selectinload(Appointment.service_type),
            selectinload(Appointment.master),
            selectinload(Appointment.lift),
        )
        .where(Appointment.id == appt.id)
    )
    return result.scalar_one()


async def get_appointment_full(
    session: AsyncSession, appt_id: int
) -> Optional[Appointment]:
    result = await session.execute(
        select(Appointment)
        .options(
            selectinload(Appointment.client),
            selectinload(Appointment.vehicle),
            selectinload(Appointment.service_type),
            selectinload(Appointment.master),
            selectinload(Appointment.lift),
            selectinload(Appointment.review),
        )
        .where(Appointment.id == appt_id)
    )
    return result.scalar_one_or_none()


async def get_client_appointments(
    session: AsyncSession,
    client_id: int,
    status: Optional[str] = None,
) -> list[Appointment]:
    q = (
        select(Appointment)
        .options(
            selectinload(Appointment.service_type),
            selectinload(Appointment.vehicle),
            selectinload(Appointment.lift),
            selectinload(Appointment.master),
        )
        .where(Appointment.client_id == client_id)
    )
    if status:
        q = q.where(Appointment.status == status)
    q = q.order_by(Appointment.start_dt.desc())
    result = await session.execute(q)
    return list(result.scalars().all())


async def cancel_appointment(
    session: AsyncSession, appt_id: int, reason: str = ""
) -> None:
    await session.execute(
        update(Appointment)
        .where(Appointment.id == appt_id)
        .values(
            status="cancelled",
            cancel_reason=reason,
            cancelled_at=datetime.now(),
        )
    )
    await session.commit()


async def reschedule_appointment(
    session: AsyncSession,
    appt_id: int,
    new_start: datetime,
    new_end: datetime,
    new_master_id: Optional[int],
    new_lift_id: int,
) -> None:
    await session.execute(
        update(Appointment)
        .where(Appointment.id == appt_id)
        .values(
            start_dt=new_start,
            end_dt=new_end,
            master_id=new_master_id,
            lift_id=new_lift_id,
            reminder_24h_sent=False,
            reminder_2h_sent=False,
        )
    )
    await session.commit()


async def get_schedule_for_date(
    session: AsyncSession, target_date: date
) -> list[Appointment]:
    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = datetime.combine(target_date, datetime.max.time())
    result = await session.execute(
        select(Appointment)
        .options(
            selectinload(Appointment.client),
            selectinload(Appointment.vehicle),
            selectinload(Appointment.service_type),
            selectinload(Appointment.master),
            selectinload(Appointment.lift),
        )
        .where(
            and_(
                Appointment.start_dt >= day_start,
                Appointment.start_dt <= day_end,
                Appointment.status == "scheduled",
            )
        )
        .order_by(Appointment.lift_id, Appointment.start_dt)
    )
    return list(result.scalars().all())


async def get_schedule_for_week(
    session: AsyncSession, week_start: date
) -> list[Appointment]:
    start = datetime.combine(week_start, datetime.min.time())
    end = datetime.combine(week_start + timedelta(days=6), datetime.max.time())
    result = await session.execute(
        select(Appointment)
        .options(
            selectinload(Appointment.client),
            selectinload(Appointment.vehicle),
            selectinload(Appointment.service_type),
            selectinload(Appointment.master),
            selectinload(Appointment.lift),
        )
        .where(
            and_(
                Appointment.start_dt >= start,
                Appointment.start_dt <= end,
                Appointment.status == "scheduled",
            )
        )
        .order_by(Appointment.start_dt, Appointment.lift_id)
    )
    return list(result.scalars().all())


async def get_occupied_intervals(
    session: AsyncSession,
    date_from: datetime,
    date_to: datetime,
) -> list[dict]:
    """Возвращает занятые интервалы (записи + заблокированные слоты) в диапазоне дат."""
    appts = await session.execute(
        select(
            Appointment.lift_id,
            Appointment.master_id,
            Appointment.start_dt,
            Appointment.end_dt,
        ).where(
            and_(
                Appointment.status == "scheduled",
                Appointment.start_dt < date_to,
                Appointment.end_dt > date_from,
            )
        )
    )
    result = []
    for row in appts.all():
        result.append({
            "lift_id": row.lift_id,
            "master_id": row.master_id,
            "start_dt": row.start_dt,
            "end_dt": row.end_dt,
        })

    blocks = await session.execute(
        select(
            BlockedSlot.lift_id,
            BlockedSlot.start_dt,
            BlockedSlot.end_dt,
        ).where(
            and_(
                BlockedSlot.start_dt < date_to,
                BlockedSlot.end_dt > date_from,
            )
        )
    )
    for row in blocks.all():
        result.append({
            "lift_id": row.lift_id,
            "master_id": None,  # блок не привязан к мастеру
            "start_dt": row.start_dt,
            "end_dt": row.end_dt,
            "is_block": True,
        })

    return result


async def get_master_weekly_hours(
    session: AsyncSession, week_start: datetime, week_end: datetime
) -> dict[int, float]:
    """Возвращает суммарную загрузку каждого мастера за неделю (часы)."""
    result = await session.execute(
        select(
            Appointment.master_id,
            func.sum(
                (func.julianday(Appointment.end_dt) - func.julianday(Appointment.start_dt)) * 24
            ).label("hours")
        )
        .where(
            and_(
                Appointment.status == "scheduled",
                Appointment.master_id.isnot(None),
                Appointment.start_dt >= week_start,
                Appointment.end_dt <= week_end,
            )
        )
        .group_by(Appointment.master_id)
    )
    return {row.master_id: float(row.hours or 0) for row in result.all()}


async def get_lift_weekly_counts(
    session: AsyncSession, week_start: datetime, week_end: datetime
) -> dict[int, int]:
    """Возвращает кол-во записей каждого подъёмника за неделю."""
    result = await session.execute(
        select(Appointment.lift_id, func.count(Appointment.id).label("cnt"))
        .where(
            and_(
                Appointment.status == "scheduled",
                Appointment.start_dt >= week_start,
                Appointment.end_dt <= week_end,
            )
        )
        .group_by(Appointment.lift_id)
    )
    return {row.lift_id: int(row.cnt) for row in result.all()}


# ─────────── SCHEDULER: напоминания и авто-завершение ───────────

async def get_appointments_for_reminder(
    session: AsyncSession,
    window_start: datetime,
    window_end: datetime,
    reminder_type: str,  # "24h" | "2h"
) -> list[Appointment]:
    if reminder_type == "24h":
        sent_col = Appointment.reminder_24h_sent
    else:
        sent_col = Appointment.reminder_2h_sent

    result = await session.execute(
        select(Appointment)
        .options(
            selectinload(Appointment.client),
            selectinload(Appointment.service_type),
            selectinload(Appointment.vehicle),
            selectinload(Appointment.lift),
        )
        .where(
            and_(
                Appointment.status == "scheduled",
                sent_col == False,
                Appointment.start_dt >= window_start,
                Appointment.start_dt <= window_end,
            )
        )
    )
    return list(result.scalars().all())


async def mark_reminder_sent(
    session: AsyncSession, appt_id: int, reminder_type: str
) -> None:
    if reminder_type == "24h":
        values = {"reminder_24h_sent": True}
    else:
        values = {"reminder_2h_sent": True}
    await session.execute(
        update(Appointment).where(Appointment.id == appt_id).values(**values)
    )
    await session.commit()


async def complete_past_appointments(
    session: AsyncSession, end_before: datetime
) -> None:
    await session.execute(
        update(Appointment)
        .where(
            and_(
                Appointment.status == "scheduled",
                Appointment.end_dt < end_before,
            )
        )
        .values(status="completed")
    )
    await session.commit()


async def get_completed_without_review(
    session: AsyncSession,
    end_after: datetime,
    end_before: datetime,
) -> list[Appointment]:
    result = await session.execute(
        select(Appointment)
        .options(
            selectinload(Appointment.client),
            selectinload(Appointment.service_type),
            selectinload(Appointment.review),
        )
        .where(
            and_(
                Appointment.status == "completed",
                Appointment.end_dt >= end_after,
                Appointment.end_dt <= end_before,
            )
        )
    )
    appts = result.scalars().all()
    return [a for a in appts if a.review is None]


# ─────────────────────────── REVIEWS ────────────────────────────

async def create_review(
    session: AsyncSession,
    appointment_id: int,
    client_id: int,
    rating: int,
    comment: Optional[str],
) -> Review:
    review = Review(
        appointment_id=appointment_id,
        client_id=client_id,
        rating=rating,
        comment=comment,
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)
    return review


async def get_client_avg_rating(
    session: AsyncSession, client_id: int
) -> Optional[float]:
    result = await session.scalar(
        select(func.avg(Review.rating)).where(Review.client_id == client_id)
    )
    return float(result) if result else None


# ─────────────────────────── BLOCKED SLOTS ──────────────────────

async def create_blocked_slot(
    session: AsyncSession,
    lift_id: int,
    start_dt: datetime,
    end_dt: datetime,
    reason: Optional[str],
    created_by: int,
) -> BlockedSlot:
    slot = BlockedSlot(
        lift_id=lift_id,
        start_dt=start_dt,
        end_dt=end_dt,
        reason=reason,
        created_by=created_by,
    )
    session.add(slot)
    await session.commit()
    await session.refresh(slot)
    return slot


# ─────────────────────────── BROADCASTS ─────────────────────────

async def save_broadcast(
    session: AsyncSession,
    admin_id: int,
    filter_type: str,
    message_text: str,
    sent_count: int,
) -> Broadcast:
    b = Broadcast(
        admin_id=admin_id,
        filter_type=filter_type,
        message_text=message_text,
        sent_count=sent_count,
    )
    session.add(b)
    await session.commit()
    await session.refresh(b)
    return b
