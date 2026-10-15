"""Persistência das mensagens do chat."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Message

ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"


def save_exchange(db: Session, user_id: int, question: str, answer: str) -> Message:
    """Grava a pergunta e a resposta e devolve a linha da resposta.

    As duas linhas entram no mesmo commit. Gravar a pergunta antes de chamar o
    LLM deixaria perguntas órfãs no banco toda vez que o provedor falhasse —
    e o histórico passaria a mostrar perguntas que nunca foram respondidas.
    """
    db.add(Message(user_id=user_id, role=ROLE_USER, content=question))
    assistant_message = Message(user_id=user_id, role=ROLE_ASSISTANT, content=answer)
    db.add(assistant_message)

    db.commit()
    db.refresh(assistant_message)
    return assistant_message


def list_messages(db: Session, user_id: int, limit: int = 50) -> list[Message]:
    """Últimas mensagens do usuário, em ordem cronológica.

    O filtro por `user_id` vem do token, nunca da requisição — é isso que
    impede alguém de ler o histórico de outra conta.
    """
    # Busca as mais recentes primeiro para que o limite corte as antigas, e
    # depois inverte: o mais novo no fim é a ordem em que um chat é lido.
    recent = db.scalars(
        select(Message)
        .where(Message.user_id == user_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit)
    ).all()

    return list(reversed(recent))


def clear_messages(db: Session, user_id: int) -> None:
    """Apaga todo o histórico do usuário, numa instrução só."""
    db.execute(delete(Message).where(Message.user_id == user_id))
    db.commit()
