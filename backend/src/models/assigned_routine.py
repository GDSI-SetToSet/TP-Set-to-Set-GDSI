from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.core.database import Base
from backend.src.models.exercise import Exercise
from backend.src.models.user import new_id


class AssignedRoutine(Base):
    __tablename__ = "assigned_routines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    trainer_id: Mapped[str] = mapped_column(
        ForeignKey("trainer_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    student_id: Mapped[str] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    template_id: Mapped[str | None] = mapped_column(
        ForeignKey("routine_templates.id", ondelete="SET NULL"), index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    duration_weeks: Mapped[int] = mapped_column(Integer, nullable=False)
    intensity: Mapped[str] = mapped_column(String(16), nullable=False)
    # 'PENDING_REVIEW' (borrador IA) o 'APPROVED' (revisada y aprobada por el entrenador)
    status: Mapped[str] = mapped_column(String(16), default="PENDING_REVIEW", nullable=False)
    adaptation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    trainer: Mapped["TrainerProfile"] = relationship()  # noqa: F821
    student: Mapped["StudentProfile"] = relationship()  # noqa: F821
    template: Mapped["RoutineTemplate | None"] = relationship()  # noqa: F821
    days: Mapped[list["AssignedRoutineDay"]] = relationship(
        back_populates="routine", cascade="all, delete-orphan", order_by="AssignedRoutineDay.order_index"
    )

    @property
    def exercise_count(self) -> int:
        return sum(len(block.exercises) for day in self.days for block in day.blocks)


class AssignedRoutineDay(Base):
    __tablename__ = "assigned_routine_days"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    routine_id: Mapped[str] = mapped_column(
        ForeignKey("assigned_routines.id", ondelete="CASCADE"), index=True, nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    routine: Mapped[AssignedRoutine] = relationship(back_populates="days")
    blocks: Mapped[list["AssignedRoutineBlock"]] = relationship(
        back_populates="day", cascade="all, delete-orphan", order_by="AssignedRoutineBlock.order_index"
    )


class AssignedRoutineBlock(Base):
    __tablename__ = "assigned_routine_blocks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    day_id: Mapped[str] = mapped_column(
        ForeignKey("assigned_routine_days.id", ondelete="CASCADE"), index=True, nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    day: Mapped[AssignedRoutineDay] = relationship(back_populates="blocks")
    exercises: Mapped[list["AssignedRoutineExercise"]] = relationship(
        back_populates="block", cascade="all, delete-orphan", order_by="AssignedRoutineExercise.order_index"
    )


class AssignedRoutineExercise(Base):
    __tablename__ = "assigned_routine_exercises"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    block_id: Mapped[str] = mapped_column(
        ForeignKey("assigned_routine_blocks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    exercise_id: Mapped[str] = mapped_column(ForeignKey("exercises.id"), index=True, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    sets: Mapped[int] = mapped_column(Integer, nullable=False)
    reps: Mapped[str] = mapped_column(String(50), nullable=False)
    rest_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    adaptation_notes: Mapped[str | None] = mapped_column(String(255), nullable=True)

    block: Mapped[AssignedRoutineBlock] = relationship(back_populates="exercises")
    exercise: Mapped[Exercise] = relationship()
