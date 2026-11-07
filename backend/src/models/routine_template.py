from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.core.database import Base
from backend.src.models.exercise import Exercise
from backend.src.models.user import new_id


class RoutineTemplate(Base):
    __tablename__ = "routine_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    trainer_id: Mapped[str] = mapped_column(
        ForeignKey("trainer_profiles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    duration_weeks: Mapped[int] = mapped_column(Integer, nullable=False)
    intensity: Mapped[str] = mapped_column(String(16), nullable=False)
    has_no_materials_alternative: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    trainer: Mapped["TrainerProfile"] = relationship()  # noqa: F821
    days: Mapped[list["RoutineTemplateDay"]] = relationship(
        back_populates="template", cascade="all, delete-orphan", order_by="RoutineTemplateDay.order_index"
    )

    @property
    def trainer_name(self) -> str | None:
        return self.trainer.full_name

    @property
    def exercise_count(self) -> int:
        return sum(len(block.exercises) for day in self.days for block in day.blocks)


class RoutineTemplateDay(Base):
    __tablename__ = "routine_template_days"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    template_id: Mapped[str] = mapped_column(
        ForeignKey("routine_templates.id", ondelete="CASCADE"), index=True, nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    template: Mapped[RoutineTemplate] = relationship(back_populates="days")
    blocks: Mapped[list["RoutineTemplateBlock"]] = relationship(
        back_populates="day", cascade="all, delete-orphan", order_by="RoutineTemplateBlock.order_index"
    )


class RoutineTemplateBlock(Base):
    __tablename__ = "routine_template_blocks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    day_id: Mapped[str] = mapped_column(
        ForeignKey("routine_template_days.id", ondelete="CASCADE"), index=True, nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    day: Mapped[RoutineTemplateDay] = relationship(back_populates="blocks")
    exercises: Mapped[list["RoutineTemplateExercise"]] = relationship(
        back_populates="block", cascade="all, delete-orphan", order_by="RoutineTemplateExercise.order_index"
    )
    estimate: Mapped["RoutineTemplateBlockEstimate | None"] = relationship(
        back_populates="block", cascade="all, delete-orphan", uselist=False
    )

    @property
    def estimated_duration_minutes(self) -> int | None:
        return self.estimate.estimated_duration_minutes if self.estimate else None


class RoutineTemplateExercise(Base):
    __tablename__ = "routine_template_exercises"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    block_id: Mapped[str] = mapped_column(
        ForeignKey("routine_template_blocks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    exercise_id: Mapped[str] = mapped_column(ForeignKey("exercises.id"), index=True, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    sets: Mapped[int] = mapped_column(Integer, nullable=False)
    reps: Mapped[str] = mapped_column(String(50), nullable=False)
    rest_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    block: Mapped[RoutineTemplateBlock] = relationship(back_populates="exercises")
    exercise: Mapped[Exercise] = relationship()
    prescription: Mapped["RoutineTemplateExercisePrescription | None"] = relationship(
        back_populates="routine_exercise", cascade="all, delete-orphan", uselist=False
    )

    @property
    def target_weight_kg(self) -> Decimal | None:
        return self.prescription.target_weight_kg if self.prescription else None


class RoutineTemplateBlockEstimate(Base):
    __tablename__ = "routine_template_block_estimates"

    block_id: Mapped[str] = mapped_column(
        ForeignKey("routine_template_blocks.id", ondelete="CASCADE"), primary_key=True
    )
    estimated_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    block: Mapped[RoutineTemplateBlock] = relationship(back_populates="estimate")


class RoutineTemplateExercisePrescription(Base):
    __tablename__ = "routine_template_exercise_prescriptions"

    routine_exercise_id: Mapped[str] = mapped_column(
        ForeignKey("routine_template_exercises.id", ondelete="CASCADE"), primary_key=True
    )
    target_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)

    routine_exercise: Mapped[RoutineTemplateExercise] = relationship(back_populates="prescription")
