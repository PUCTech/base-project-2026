"""Schemas de entrada e saída relacionados a usuário."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

USERNAME_PATTERN = r"^[a-zA-Z0-9_.-]+$"


class UserCreate(BaseModel):
    """Corpo de POST /auth/register."""

    username: str = Field(min_length=3, max_length=50, pattern=USERNAME_PATTERN)
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    """Corpo de POST /auth/login.

    Sem as restrições de tamanho e formato do cadastro: na autenticação, um
    valor fora do padrão é credencial errada (401), não erro de validação (422).
    Responder 422 aqui entregaria ao atacante a regra de formação das senhas.
    """

    username: str
    password: str


class UserRead(BaseModel):
    """Forma pública de um usuário.

    Note o que não está aqui: `password_hash`. Como a resposta é montada a
    partir deste schema, o hash não tem como vazar mesmo que o endpoint devolva
    o objeto do banco inteiro.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    created_at: datetime
