"""Schemas do chat."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatRequest(BaseModel):
    """Corpo de POST /chat."""

    message: str = Field(min_length=1, max_length=4000)

    @field_validator("message")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        """`min_length` sozinho aceita "   ": espaço em branco tem comprimento.

        Sem esta checagem, uma mensagem em branco seria válida e acabaria
        enviada ao provedor — gastando cota para receber nada de útil.
        """
        stripped = value.strip()
        if not stripped:
            raise ValueError("A mensagem não pode ser apenas espaços em branco.")
        return stripped


class ChatResponse(BaseModel):
    """Resposta de POST /chat."""

    reply: str
    created_at: datetime


class MessageRead(BaseModel):
    """Uma mensagem no histórico."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class ChatHistory(BaseModel):
    """Resposta de GET /chat/history."""

    messages: list[MessageRead]
