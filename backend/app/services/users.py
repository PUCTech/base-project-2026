"""Regra de negócio de usuário.

Esta camada não conhece HTTP: não importa `Request`, não devolve `Response` e
não levanta `HTTPException`. Ela sinaliza problemas com exceções próprias, e o
router decide qual status code cada uma vira. É o que permite reaproveitar
estas funções em um comando de linha ou em um teste sem subir a API.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.schemas.user import UserCreate, UserUpdate
from app.services.security import (
    hash_password,
    verify_password,
    waste_time_like_a_verification,
)


class UsernameAlreadyExistsError(Exception):
    """O username pedido já pertence a outra conta."""


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def create_user(db: Session, data: UserCreate) -> User:
    """Cadastra um usuário, guardando apenas o hash da senha."""
    if get_user_by_username(db, data.username) is not None:
        raise UsernameAlreadyExistsError(data.username)

    user = User(username=data.username, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    """Devolve o usuário se as credenciais baterem, senão `None`.

    Quando o usuário não existe, ainda assim gastamos o tempo de uma
    verificação de senha. Sem isso, a resposta de "usuário inexistente" volta
    mais rápido, e a diferença de tempo denuncia quais contas existem — mesmo
    com o router respondendo a mesma mensagem nos dois casos.
    """
    user = get_user_by_username(db, username)
    if user is None:
        waste_time_like_a_verification()
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


def update_user(db: Session, user: User, data: UserUpdate) -> User:
    """Aplica uma atualização parcial no usuário.

    `exclude_unset` distingue "campo não enviado" de "campo enviado como null" —
    sem isso, um PATCH que muda só o username apagaria a senha.
    """
    changes = data.model_dump(exclude_unset=True, exclude_none=True)

    new_username = changes.get("username")
    if new_username is not None and new_username != user.username:
        if get_user_by_username(db, new_username) is not None:
            raise UsernameAlreadyExistsError(new_username)
        user.username = new_username

    new_password = changes.get("password")
    if new_password is not None:
        user.password_hash = hash_password(new_password)

    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user: User) -> None:
    """Remove o usuário. As mensagens vão junto, por cascata da FK."""
    db.delete(user)
    db.commit()
