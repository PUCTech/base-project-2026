"""Tabelas `recipe_favorites`, `recipe_ratings` e `recipe_comments`."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, SmallInteger, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RecipeFavorite(Base):
    """Associação usuário ↔ receita favorita.

    A chave primária é o par (usuário, receita): favoritar duas vezes não cria
    duas linhas — o banco simplesmente não permite.
    """

    __tablename__ = "recipe_favorites"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    recipe_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RecipeRating(Base):
    """Uma nota de 1 a 5 por usuário por receita."""

    __tablename__ = "recipe_ratings"
    __table_args__ = (
        # A validação do Pydantic já barra nota fora da faixa na API. A
        # constraint protege o dado contra qualquer outro caminho de escrita —
        # um script, uma migração, um INSERT manual.
        CheckConstraint("stars BETWEEN 1 AND 5", name="ck_recipe_ratings_stars"),
    )

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    recipe_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    stars: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class RecipeComment(Base):
    __tablename__ = "recipe_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recipes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    author_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    author: Mapped["User"] = relationship()  # noqa: F821
