"""Schemas da lista de compras."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import Category, ItemName, PositiveQuantity, Unit
from app.schemas.pantry import PantryItemRead

ShoppingSource = Literal["manual", "receita", "ia"]


class ShoppingItemIn(BaseModel):
    name: ItemName
    quantity: PositiveQuantity = None
    unit: Unit = None
    category: Category = "outros"


class ShoppingAdd(BaseModel):
    """Corpo de POST /shopping-list.

    Sempre uma lista, mesmo para um item só: o formulário manda um, a
    sugestão da IA manda vários, e os dois passam pelo mesmo caminho — e pela
    mesma regra de juntar itens repetidos.
    """

    items: list[ShoppingItemIn] = Field(min_length=1, max_length=100)
    # O cliente só pode declarar "manual" ou "ia". "receita" é exclusivo da
    # rota que calcula o que falta, que é quem sabe de qual receita veio.
    source: Literal["manual", "ia"] = "manual"


class ShoppingItemUpdate(BaseModel):
    name: ItemName | None = None
    quantity: PositiveQuantity = None
    unit: Unit = None
    category: Category | None = None
    checked: bool | None = None

    @model_validator(mode="after")
    def _require_at_least_one_field(self) -> "ShoppingItemUpdate":
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar.")
        for field in ("name", "category", "checked"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"O campo {field} não pode ser apagado.")
        return self


class ShoppingItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    quantity: float | None
    unit: str | None
    category: Category
    checked: bool
    source: ShoppingSource
    recipe_id: int | None
    created_at: datetime


class FromRecipeResult(BaseModel):
    """Resposta de POST /shopping-list/from-recipe/{id}."""

    # Quantos ingredientes faltavam e foram para a lista. Zero quer dizer que a
    # despensa já tem tudo.
    added: int
    items: list[ShoppingItemRead]


class CheckoutResult(BaseModel):
    """Resposta de POST /shopping-list/checkout."""

    moved: int
    pantry: list[PantryItemRead]
