"""Rotas de autenticação.

O router só traduz HTTP: recebe o corpo já validado pelo Pydantic, chama o
serviço e transforma o resultado em status code. Nenhuma regra de negócio mora
aqui.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserLogin, UserRead
from app.services.tokens import create_access_token
from app.services.users import (
    UsernameAlreadyExistsError,
    authenticate_user,
    create_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Mensagem única para "usuário não existe" e "senha errada". Distinguir os dois
# casos daria ao atacante uma forma barata de descobrir quais contas existem.
INVALID_CREDENTIALS = "Usuário ou senha inválidos"


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra um usuário",
)
def register(data: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    try:
        user = create_user(db, data)
    except UsernameAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este nome de usuário já está em uso",
        ) from None

    # O response_model recorta a resposta: mesmo devolvendo o objeto do banco
    # inteiro, `password_hash` não chega ao cliente.
    return user


@router.post(
    "/login",
    response_model=Token,
    summary="Autentica e devolve o token de acesso",
)
def login(data: UserLogin, db: Session = Depends(get_db)) -> Token:
    user = authenticate_user(db, data.username, data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token, expires_in = create_access_token(user.id)
    return Token(access_token=access_token, expires_in=expires_in)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Dados do usuário autenticado",
)
def read_me(current_user: User = Depends(get_current_user)) -> UserRead:
    """O usuário sai do token — o cliente não escolhe de quem são os dados."""
    return current_user
