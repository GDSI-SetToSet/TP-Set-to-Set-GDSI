from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.core.database import Base
from backend.src.models.user import new_id


class BodyMapPainReport(Base):
    __tablename__ = "body_map_pain_reports"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "idempotency_key",
            name="uq_body_map_student_idempotency",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    relationship_id: Mapped[str | None] = mapped_column(
        ForeignKey("training_relationships.id", ondelete="SET NULL"), index=True, nullable=True
    )
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("workout_sessions.id", ondelete="SET NULL"), index=True, nullable=True
    )
    exercise_id: Mapped[str | None] = mapped_column(
        ForeignKey("exercises.id", ondelete="SET NULL"), index=True, nullable=True
    )
    context: Mapped[str] = mapped_column(String(32), nullable=False)  # POST_SESSION, IN_EXERCISE
    action_taken: Mapped[str | None] = mapped_column(String(32), nullable=True)  # NONE, VARIANT_OFFERED, etc.
    idempotency_key: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)

    student: Mapped["StudentProfile"] = relationship()  # noqa: F821
    session: Mapped["WorkoutSession | None"] = relationship()  # noqa: F821
    exercise: Mapped["Exercise | None"] = relationship()  # noqa: F821
    zones: Mapped[list["BodyMapPainReportZone"]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="BodyMapPainReportZone.zone",
    )


class BodyMapPainReportZone(Base):
    __tablename__ = "body_map_pain_report_zones"
    __table_args__ = (UniqueConstraint("report_id", "zone", name="uq_body_map_report_zone"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    report_id: Mapped[str] = mapped_column(
        ForeignKey("body_map_pain_reports.id", ondelete="CASCADE"), index=True, nullable=False
    )
    zone: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    intensity: Mapped[str] = mapped_column(String(20), index=True, nullable=False)  # NORMAL, DISCOMFORT, PAIN
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)

    report: Mapped["BodyMapPainReport"] = relationship(back_populates="zones")
