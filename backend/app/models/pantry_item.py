"""Tabela `pantry_items` — a despensa de cada usuário."""

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PantryItem(Base):
    __tablename__ = "pantry_items"
    __table_args__ = (
        # Um item por ingrediente em cada despensa. O serviço já confere isso
        # antes de gravar, para devolver uma mensagem útil; a constraint é o que
        # garante a regra mesmo quando duas requisições chegam juntas e as duas
        # passam pela conferência antes de qualquer uma gravar.
        UniqueConstraint("user_id", "name_key", name="uq_pantry_items_user_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # O nome como o usuário escreveu, para exibir.
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # O nome normalizado ("Tomates" → "tomate"), para comparar. Guardado em
    # coluna própria para que a comparação seja uma igualdade indexável, e não
    # uma normalização recalculada em cada linha a cada consulta.
    name_key: Mapped[str] = mapped_column(String(100), nullable=False)
    # Float e não Numeric: é quantidade de cozinha, não dinheiro. NULL significa
    # "tenho, mas não controlo quanto" (sal, azeite); 0 significa "acabou".
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    category: Mapped[str] = mapped_column(String(20), nullable=False, default="outros")
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<PantryItem id={self.id} user_id={self.user_id} name={self.name!r}>"
