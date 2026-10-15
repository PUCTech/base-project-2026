"""Tabela `shopping_items` — a lista de compras de cada usuário."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ShoppingItem(Base):
    __tablename__ = "shopping_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_key: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    category: Mapped[str] = mapped_column(String(20), nullable=False, default="outros")
    # Marcado = já está no carrinho. Finalizar a compra leva os marcados para
    # a despensa.
    checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # De onde o item veio: digitado ("manual"), do que falta numa receita
    # ("receita") ou de uma sugestão da IA ("ia"). Só para exibir.
    source: Mapped[str] = mapped_column(String(10), nullable=False, default="manual")
    # SET NULL, e não CASCADE: apagar a receita não deve tirar da lista um
    # item que a pessoa ainda pretende comprar.
    recipe_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ShoppingItem id={self.id} user_id={self.user_id} name={self.name!r}>"
