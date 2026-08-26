from typing import List, Optional
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


class Prompt(Base):
    """Represents a test prompt/question in the database."""

    __tablename__ = "prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)

    # One-to-many relationships
    answers: Mapped[List["Answer"]] = relationship(
        "Answer",
        back_populates="prompt",
        cascade="all, delete-orphan",
    )
    human_preferences: Mapped[List["HumanPreference"]] = relationship(
        "HumanPreference",
        back_populates="prompt",
        cascade="all, delete-orphan",
    )
    judge_decisions: Mapped[List["JudgeDecision"]] = relationship(
        "JudgeDecision",
        back_populates="prompt",
        cascade="all, delete-orphan",
    )


class Answer(Base):
    """Represents an LLM-generated response to a specific prompt."""

    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prompt_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("prompts.id", ondelete="CASCADE"),
        nullable=False,
    )
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    format_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="plain_text")

    # Many-to-one relationship back to Prompt
    prompt: Mapped["Prompt"] = relationship("Prompt", back_populates="answers")


class HumanPreference(Base):
    """Represents human evaluation data comparing two answers for a prompt."""

    __tablename__ = "human_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prompt_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("prompts.id", ondelete="CASCADE"),
        nullable=False,
    )
    answer_a_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("answers.id", ondelete="CASCADE"),
        nullable=False,
    )
    answer_b_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("answers.id", ondelete="CASCADE"),
        nullable=False,
    )
    winner_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("answers.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    prompt: Mapped["Prompt"] = relationship(
        "Prompt",
        back_populates="human_preferences",
    )

    # Explicit foreign keys definition for multiple fields targeting Answer
    answer_a: Mapped["Answer"] = relationship(
        "Answer",
        foreign_keys=[answer_a_id],
    )
    answer_b: Mapped["Answer"] = relationship(
        "Answer",
        foreign_keys=[answer_b_id],
    )
    winner: Mapped[Optional["Answer"]] = relationship(
        "Answer",
        foreign_keys=[winner_id],
    )


class JudgeDecision(Base):
    """Represents LLM-as-a-Judge evaluation decisions comparing two answers."""

    __tablename__ = "judge_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prompt_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("prompts.id", ondelete="CASCADE"),
        nullable=False,
    )
    judge_model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    answer_a_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("answers.id", ondelete="CASCADE"),
        nullable=False,
    )
    answer_b_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("answers.id", ondelete="CASCADE"),
        nullable=False,
    )
    position_a_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("answers.id", ondelete="CASCADE"),
        nullable=False,  # Tracks which answer was shown first to evaluate position bias
    )
    winner_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("answers.id", ondelete="SET NULL"),
        nullable=True,
    )
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    prompt: Mapped["Prompt"] = relationship(
        "Prompt",
        back_populates="judge_decisions",
    )

    # Explicit foreign keys definition for multiple fields targeting Answer
    answer_a: Mapped["Answer"] = relationship(
        "Answer",
        foreign_keys=[answer_a_id],
    )
    answer_b: Mapped["Answer"] = relationship(
        "Answer",
        foreign_keys=[answer_b_id],
    )
    position_a: Mapped["Answer"] = relationship(
        "Answer",
        foreign_keys=[position_a_id],
    )
    winner: Mapped[Optional["Answer"]] = relationship(
        "Answer",
        foreign_keys=[winner_id],
    )
