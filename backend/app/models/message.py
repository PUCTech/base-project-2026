"""Tabela `messages`."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        # ondelete no banco + passive_deletes no relationship: apagar o usuário
        # apaga as mensagens em uma instrução, sem carregar tudo em memória.
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # 'user' para a pergunta, 'assistant' para a resposta do LLM — o mesmo
    # vocabulário que as APIs de LLM usam para histórico.
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="messages")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Message id={self.id} user_id={self.user_id} role={self.role!r}>"
