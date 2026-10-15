"""Tabelas `recipes`, `recipe_ingredients` e `recipe_steps`."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    servings: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    # Tempo total em minutos. NULL quando o autor não informou.
    prep_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    difficulty: Mapped[str] = mapped_column(String(10), nullable=False, default="facil")
    # Só o nome do arquivo gerado pelo servidor — nunca o nome que veio no
    # upload. Ver services/storage.py.
    image_filename: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by_ai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    author: Mapped["User"] = relationship()  # noqa: F821
    # delete-orphan: tirar um ingrediente da lista e salvar apaga a linha. É o
    # que permite o PUT substituir a receita inteira com uma atribuição.
    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="recipe",
        order_by="RecipeIngredient.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    steps: Mapped[list["RecipeStep"]] = relationship(
        back_populates="recipe",
        order_by="RecipeStep.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Recipe id={self.id} title={self.title!r}>"


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recipes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Ordem explícita: o banco não garante a ordem das linhas, e numa lista de
    # ingredientes a ordem é informação.
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # NULL em "sal a gosto".
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # "picada", "em temperatura ambiente"...
    note: Mapped[str | None] = mapped_column(String(100), nullable=True)

    recipe: Mapped[Recipe] = relationship(back_populates="ingredients")


class RecipeStep(Base):
    __tablename__ = "recipe_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recipes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    # Quando o passo tem espera ("asse por 40 minutos"), o modo cozinha oferece
    # um timer com esse valor.
    timer_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    recipe: Mapped[Recipe] = relationship(back_populates="steps")
