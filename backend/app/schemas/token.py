"""Schemas do token de acesso."""

from pydantic import BaseModel


class Token(BaseModel):
    """Resposta de POST /auth/login."""

    access_token: str
    # noqa S105: "bearer" é o tipo de token definido pela RFC 6750, não uma senha.
    token_type: str = "bearer"  # noqa: S105
    expires_in: int
