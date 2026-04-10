from datetime import date
from collections import defaultdict

from db.models import Appointment, Client, Vehicle, Review
from utils.datetime_utils import fmt_date, fmt_dt


def format_day_schedule(appointments: list[Appointment], target_date: date) -> str:
    """Форматирует расписание на день по подъёмникам."""
    if not appointments:
        return f"📅 {fmt_date(target_date)}\n\nЗаписей нет."

    by_lift: dict[int, list[Appointment]] = defaultdict(list)
    for a in appointments:
        by_lift[a.lift_id].append(a)

    lines = [f"📅 {fmt_date(target_date)}\n"]
    for lift_id in sorted(by_lift):
        lift_name = appointments[0].lift.name if appointments else f"Подъёмник {lift_id}"
        # Найдём правильное название
        for a in appointments:
            if a.lift_id == lift_id:
                lift_name = a.lift.name
                break

        lines.append(f"🔧 {lift_name}:")
        for a in sorted(by_lift[lift_id], key=lambda x: x.start_dt):
            start = a.start_dt.strftime("%H:%M")
            end = a.end_dt.strftime("%H:%M")
            vehicle = f"{a.vehicle.brand} {a.vehicle.model} {a.vehicle.year}"
            master = a.master.name if a.master else "—"
            lines.append(
                f"  {start}–{end}  {a.service_type.name} | "
                f"{a.client.full_name} ({vehicle}) | {master}"
            )
        lines.append("")

    return "\n".join(lines).strip()


def format_week_schedule(appointments: list[Appointment], week_start: date) -> str:
    """Форматирует расписание на неделю."""
    if not appointments:
        return "Записей на этой неделе нет."

    by_date: dict[date, list[Appointment]] = defaultdict(list)
    for a in appointments:
        by_date[a.start_dt.date()].append(a)

    lines = ["📆 Расписание на неделю\n"]
    for d in sorted(by_date):
        lines.append(f"── {fmt_date(d)} ──")
        for a in sorted(by_date[d], key=lambda x: (x.lift_id, x.start_dt)):
            start = a.start_dt.strftime("%H:%M")
            end = a.end_dt.strftime("%H:%M")
            lines.append(
                f"  [{a.lift.name}] {start}–{end} {a.service_type.name} — {a.client.full_name}"
            )
        lines.append("")

    return "\n".join(lines).strip()


def format_client_card(
    client: Client,
    vehicles: list[Vehicle],
    appointments: list[Appointment],
    avg_rating: float | None,
) -> str:
    """Карточка клиента для администратора."""
    lines = [
        f"👤 {client.full_name}",
        f"Telegram: @{client.username or '—'} (ID: {client.telegram_id})",
        f"Телефон: {client.phone or '—'}",
        "",
    ]

    if vehicles:
        lines.append("🚗 Автомобили:")
        for v in vehicles:
            lines.append(f"  • {v.brand} {v.model} {v.year}")
        lines.append("")

    rating_str = f"{avg_rating:.1f} ⭐" if avg_rating else "нет оценок"
    lines.append(f"Средняя оценка: {rating_str}")
    lines.append(f"Всего визитов: {len(appointments)}")
    lines.append("")

    recent = [a for a in appointments if a.status == "completed"][:5]
    if recent:
        lines.append("📋 Последние визиты:")
        for a in recent:
            lines.append(
                f"  • {fmt_dt(a.start_dt)} — {a.service_type.name}"
            )

    return "\n".join(lines)


def format_appointment_confirm(
    service_name: str,
    duration: int,
    vehicle_str: str,
    slot_dt_str: str,
) -> str:
    return (
        f"✅ Подтвердите запись:\n\n"
        f"🔧 Услуга: {service_name} ({duration}ч)\n"
        f"🚗 Авто: {vehicle_str}\n"
        f"📅 Дата и время: {slot_dt_str}\n\n"
        f"Мастер будет назначен автоматически."
    )
