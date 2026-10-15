"""Schemas das funções de IA da cozinha."""

from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.schemas.pantry import PantryItemCreate
from app.schemas.shopping import ShoppingItemIn


class RecipeDraftRequest(BaseModel):
    """Corpo de POST /ai/recipe-draft."""

    request: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)]
    # Por padrão a receita parte do que a pessoa tem. Desligado, a IA escreve
    # livremente — útil para transformar em receita um texto do chat.
    use_pantry: bool = True


class PantryParseRequest(BaseModel):
    """Corpo de POST /ai/pantry-parse."""

    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)]


class PantryParseResponse(BaseModel):
    items: list[PantryItemCreate]


class ShoppingSuggestRequest(BaseModel):
    """Corpo de POST /ai/shopping-suggestions."""

    goal: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
        | None
    ) = None


class ShoppingSuggestion(ShoppingItemIn):
    """Um item sugerido. Herda as regras de um item digitado na lista."""

    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]


class ShoppingSuggestResponse(BaseModel):
    suggestions: list[ShoppingSuggestion]
