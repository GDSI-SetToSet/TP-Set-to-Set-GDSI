"""Alertas de seguridad clínicas/de esfuerzo para supervisión del entrenador (US-29)."""

from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship as orm_relationship

from backend.src.core.database import Base
from backend.src.models.user import new_id

SAFETY_ALERT_TYPES = ("PAIN", "REPEATED_DISCOMFORT", "EXCESSIVE_EFFORT")
SAFETY_ALERT_STATUSES = ("PENDING", "REVIEWED")
SAFETY_ALERT_ACTIONS = ("ADJUSTED_ROUTINE", "CONTACTED_STUDENT", "NO_ACTION")


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SafetyAlert(Base):
    __tablename__ = "safety_alerts"
    __table_args__ = (
        UniqueConstraint("dedup_key", name="uq_safety_alerts_dedup_key"),
        CheckConstraint(
            "alert_type IN ('PAIN', 'REPEATED_DISCOMFORT', 'EXCESSIVE_EFFORT')",
            name="ck_safety_alerts_type",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'REVIEWED')",
            name="ck_safety_alerts_status",
        ),
        CheckConstraint(
            "action_taken IS NULL OR action_taken IN ('ADJUSTED_ROUTINE', 'CONTACTED_STUDENT', 'NO_ACTION')",
            name="ck_safety_alerts_action",
        ),
        CheckConstraint(
            "rpe IS NULL OR rpe IN (9, 10)",
            name="ck_safety_alerts_rpe",
        ),
        Index("ix_safety_alerts_trainer_status_created", "trainer_id", "status", "created_at"),
        Index("ix_safety_alerts_relationship_status", "relationship_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    relationship_id: Mapped[str] = mapped_column(
        ForeignKey("training_relationships.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    trainer_id: Mapped[str] = mapped_column(
        ForeignKey("trainer_profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    student_id: Mapped[str] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("workout_sessions.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    report_id: Mapped[str | None] = mapped_column(
        ForeignKey("body_map_pain_reports.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    exercise_id: Mapped[str | None] = mapped_column(
        ForeignKey("exercises.id", ondelete="SET NULL"),
        nullable=True,
    )
    alert_type: Mapped[str] = mapped_column(String(32), nullable=False)
    zone: Mapped[str | None] = mapped_column(String(60), nullable=True)
    rpe: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dedup_key: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    action_taken: Mapped[str | None] = mapped_column(String(32), nullable=True)
    trainer_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    student_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    relationship: Mapped["TrainingRelationship"] = orm_relationship()  # noqa: F821
    trainer: Mapped["TrainerProfile"] = orm_relationship()  # noqa: F821
    student: Mapped["StudentProfile"] = orm_relationship()  # noqa: F821
    session: Mapped["WorkoutSession | None"] = orm_relationship()  # noqa: F821
    report: Mapped["BodyMapPainReport | None"] = orm_relationship()  # noqa: F821
    exercise: Mapped["Exercise | None"] = orm_relationship()  # noqa: F821
