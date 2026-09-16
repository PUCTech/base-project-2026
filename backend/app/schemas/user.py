"""Schemas de entrada e saída relacionados a usuário."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class UserUpdate(BaseModel):
    """Corpo de PATCH /users/me — atualização parcial.

    Ambos os campos são opcionais, mas o corpo não pode vir vazio: um PATCH sem
    nenhum campo é quase sempre um erro do cliente, e responder 200 sem ter
    mudado nada esconde esse erro em vez de denunciá-lo.
    """

    username: str | None = Field(default=None, min_length=3, max_length=50, pattern=USERNAME_PATTERN)
    password: str | None = Field(default=None, min_length=8, max_length=128)

    @model_validator(mode="after")
    def _require_at_least_one_field(self) -> "UserUpdate":
        if self.username is None and self.password is None:
            raise ValueError("Informe ao menos um campo para atualizar.")
        return self
