from datetime import datetime
from sqlalchemy import (
    Integer, String, Boolean, DateTime, Text,
    ForeignKey, Index, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.engine import Base


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64))
    full_name: Mapped[str] = mapped_column(String(256), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="client")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="client")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    brand: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    client: Mapped["Client"] = relationship(back_populates="vehicles")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="vehicle")

    __table_args__ = (
        Index("ix_vehicles_client_active", "client_id", "is_active"),
    )


class Master(Base):
    __tablename__ = "masters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    appointments: Mapped[list["Appointment"]] = relationship(back_populates="master")


class Lift(Base):
    __tablename__ = "lifts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    appointments: Mapped[list["Appointment"]] = relationship(back_populates="lift")
    blocked_slots: Mapped[list["BlockedSlot"]] = relationship(back_populates="lift")


class ServiceType(Base):
    __tablename__ = "service_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    duration_hours: Mapped[int] = mapped_column(Integer, nullable=False)

    appointments: Mapped[list["Appointment"]] = relationship(back_populates="service_type")


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False)
    service_type_id: Mapped[int] = mapped_column(ForeignKey("service_types.id"), nullable=False)
    master_id: Mapped[int | None] = mapped_column(ForeignKey("masters.id"))
    lift_id: Mapped[int] = mapped_column(ForeignKey("lifts.id"), nullable=False)
    start_dt: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_dt: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # scheduled | completed | cancelled | no_show
    status: Mapped[str] = mapped_column(String(16), default="scheduled")
    notes: Mapped[str | None] = mapped_column(Text)
    reminder_24h_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_2h_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    client: Mapped["Client"] = relationship(back_populates="appointments")
    vehicle: Mapped["Vehicle"] = relationship(back_populates="appointments")
    service_type: Mapped["ServiceType"] = relationship(back_populates="appointments")
    master: Mapped["Master | None"] = relationship(back_populates="appointments")
    lift: Mapped["Lift"] = relationship(back_populates="appointments")
    review: Mapped["Review | None"] = relationship(back_populates="appointment", uselist=False)

    __table_args__ = (
        Index("ix_appt_lift_time", "lift_id", "start_dt", "end_dt"),
        Index("ix_appt_master_time", "master_id", "start_dt", "end_dt"),
        Index("ix_appt_start_status", "start_dt", "status"),
        Index("ix_appt_client_status", "client_id", "status"),
    )


class BlockedSlot(Base):
    __tablename__ = "blocked_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lift_id: Mapped[int] = mapped_column(ForeignKey("lifts.id"), nullable=False)
    start_dt: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_dt: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)

    lift: Mapped["Lift"] = relationship(back_populates="blocked_slots")

    __table_args__ = (
        Index("ix_blocked_lift_time", "lift_id", "start_dt", "end_dt"),
    )


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    appointment_id: Mapped[int] = mapped_column(
        ForeignKey("appointments.id"), unique=True, nullable=False
    )
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    appointment: Mapped["Appointment"] = relationship(back_populates="review")


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    filter_type: Mapped[str] = mapped_column(String(32), nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
